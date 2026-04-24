from __future__ import annotations
import logging
from datetime import UTC, datetime
import pytest
from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.celery_app import (
    AUDIT_COMPETITORS_QUEUE,
    AUDIT_COMPETITOR_PAGES_QUEUE,
    AUDIT_FEATURES_QUEUE,
    AUDIT_FETCH_QUEUE,
    AUDIT_FINALIZE_QUEUE,
    AUDIT_HEAVY_ANALYSIS_QUEUE,
    AUDIT_PIPELINE_QUEUE,
    AUDIT_RECOMMENDATIONS_QUEUE,
    AUDIT_SCORING_QUEUE,
    celery_app,
    resolve_task_queue,
)
from app.db import Base
from app.models import Audit, AuditCompetitor, AuditEvent
from app.tasks import (
    _dispatch_stage_task,
    enqueue_audit_processing,
    process_audit,
    process_audit_analyze_competitor_page,
    process_audit_aggregate_competitors,
    process_audit_collect_competitor_page,
    process_audit_collect_competitors,
    process_audit_extract_features,
    process_audit_fetch_target,
    process_audit_finalize,
    process_audit_generate_recommendations,
    process_audit_run_heavy_analysis,
    process_audit_score_target,
)
def test_process_audit_pipeline_saves_results(monkeypatch, tmp_path, caplog):
    db_path = tmp_path / 'pipeline.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)
    monkeypatch.setattr(
        'app.tasks.fetch_page',
        lambda url, use_browser=True: {
            'status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'final_url': url,
            'http_status': 200,
            'html': '<html><body><h1>Title</h1><p>Body</p></body></html>',
            'text': 'Title Body',
        },
    )
    monkeypatch.setattr(
        'app.tasks.build_features',
        lambda html, text, query: {
            'text_length_chars': 10,
            'query_in_text': 1,
            'semantic_similarity': 0.81,
        },
    )
    monkeypatch.setattr(
        'app.tasks.explain_score',
        lambda features: {
            'final_score': 77.5,
            'rule_score': 74.0,
            'ml_score': 84.0,
            'methodology': '╨в╨╡╤Б╤В╨╛╨▓╨░╤П ╨╝╨╡╤В╨╛╨┤╨╛╨╗╨╛╨│╨╕╤П',
            'model_info': {'source': 'bootstrap'},
            'positives': [
                {
                    'code': 'GOOD_TITLE',
                    'label': '╨Х╤Б╤В╤М title',
                    'impact': 7.0,
                    'detail': 'Title ╨╜╨░╨╣╨┤╨╡╨╜',
                }
            ],
            'negatives': [
                {
                    'code': 'SHORT_TEXT',
                    'label': '╨Ь╨░╨╗╨╛ ╤В╨╡╨║╤Б╤В╨░',
                    'impact': -4.0,
                    'detail': '╨в╨╡╨║╤Б╤В ╨║╨╛╤А╨╛╤В╨║╨╕╨╣',
                }
            ],
            'factors': [],
        },
    )
    monkeypatch.setattr(
        'app.tasks.search_competitor_pages',
        lambda query, target_url, limit: [
            {
                'url': 'https://competitor-a.example',
                'domain': 'competitor-a.example',
                'title': 'Competitor A',
                'snippet': 'Snippet A',
                'rank': 1,
                'serp_page': 0,
            },
            {
                'url': 'https://competitor-b.example',
                'domain': 'competitor-b.example',
                'title': 'Competitor B',
                'snippet': 'Snippet B',
                'rank': 2,
                'serp_page': 0,
            },
        ],
    )
    def fake_fetch_competitor_page(result):
        url = str(result['url'])
        success = 'competitor-a' in url
        return {
            'url': url,
            'domain': str(result['domain']),
            'title': str(result['title']),
            'snippet': str(result['snippet']),
            'serp_rank': int(result.get('rank') or result.get('serp_rank') or 0),
            'serp_page': int(result['serp_page']),
            'fetch_status': 'success' if success else 'failed',
            'fetch_method': 'http' if success else 'browser',
            'fetch_error_code': None if success else 'http_403',
            'fetch_error_message': None if success else 'HTTP 403',
            'snapshot': {
                'requested_url': url,
                'final_url': url,
                'status_code': 200,
                'fetch_method': 'http',
                'html': '<html><body><h1>Competitor A</h1><p>Body</p></body></html>',
                'text': 'Competitor A Body',
                'json_ld': [],
            }
            if success
            else None,
        }

    def fake_analyze_competitor_snapshot(result, query, snapshot):
        assert query == 'plastic windows'
        assert isinstance(snapshot, dict)
        return {
            'url': str(result['url']),
            'domain': str(result['domain']),
            'title': str(result['title']),
            'snippet': str(result['snippet']),
            'serp_rank': int(result.get('rank') or result.get('serp_rank') or 0),
            'serp_page': int(result['serp_page']),
            'fetch_status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'score': 82.4,
            'features': {
                'text_length_chars': 18,
                'query_in_text': 1,
                'semantic_similarity': 0.87,
            },
        }

    monkeypatch.setattr('app.tasks.fetch_competitor_page', fake_fetch_competitor_page)
    monkeypatch.setattr('app.tasks.analyze_competitor_snapshot', fake_analyze_competitor_snapshot)
    monkeypatch.setattr(
        'app.tasks.build_comparison_summary',
        lambda user_features, user_score, competitor_results, **kwargs: {
            'user_score': 77.5,
            'competitors_average_score': 82.4,
            'score_difference': -4.9,
            'competitors_count': 1,
            'competitors_found': 2,
            'competitors_analyzed': 1,
            'competitors_failed': 1,
        },
    )
    monkeypatch.setattr(
        'app.tasks.generate_recommendations',
        lambda page_features, page_score, competitor_pages_features: [
            {
                'code': 'TEST_REC',
                'priority': 'medium',
                'message': 'Test recommendation',
            }
        ],
    )
    with testing_session_local() as db:
        audit = Audit(
            id='audit-1',
            query='plastic windows',
            target_url='https://example.com',
            top_n=5,
            status='queued',
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(audit)
        db.commit()
    caplog.set_level(logging.INFO, logger='app.tasks')
    result = process_audit.run('audit-1')
    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-1')
        competitors = db.scalars(select(AuditCompetitor).where(AuditCompetitor.audit_id == 'audit-1')).all()
        audit_events = db.scalars(
            select(AuditEvent)
            .where(AuditEvent.audit_id == 'audit-1')
            .order_by(AuditEvent.id.asc())
        ).all()
        assert stored is not None
        assert stored.status == 'completed_with_warnings'
        assert stored.competitor_processing_status == 'aggregated'
        assert stored.extracted_text == 'Title Body'
        assert stored.feature_schema_version == 'v2'
        assert isinstance(stored.query_intent, dict)
        assert 'label' in stored.query_intent
        assert isinstance(stored.target_snapshot, dict)
        assert stored.target_snapshot['requested_url'] == 'https://example.com'
        assert stored.target_snapshot['final_url'] == 'https://example.com'
        assert stored.target_snapshot['document']['h1_texts'] == ['Title']
        assert isinstance(stored.heavy_analysis, dict)
        assert stored.heavy_analysis['schema_version'] == 'heavy-analysis-v1'
        assert stored.heavy_analysis['features']['heavy_analysis_available'] == 1
        assert stored.target_fetch_status == 'success'
        assert stored.target_fetch_method == 'http'
        assert stored.target_fetch_error_code is None
        assert stored.failure_context is None
        assert stored.score == 77.5
        assert stored.comparison_summary == {
            'user_score': 77.5,
            'competitors_average_score': 82.4,
            'score_difference': -4.9,
            'competitors_count': 1,
            'competitors_found': 2,
            'competitors_analyzed': 1,
            'competitors_failed': 1,
        }
        assert stored.recommendations == [
            {
                'code': 'TEST_REC',
                'priority': 'medium',
                'message': 'Test recommendation',
            }
        ]
        assert stored.warnings is not None
        assert len(stored.warnings) == 2
        expected_warning_prefix = (
            r"\u041e\u0431\u0440\u0430\u0431\u043e\u0442\u0430\u043d\u043e 1 \u0438\u0437 2"
            .encode('ascii')
            .decode('unicode_escape')
        )
        expected_warning_subject = (
            r"\u043a\u043e\u043d\u043a\u0443\u0440\u0435\u043d\u0442\u043d\u044b\u0445 \u0441\u0442\u0440\u0430\u043d\u0438\u0446"
            .encode('ascii')
            .decode('unicode_escape')
        )
        assert stored.warnings[0].startswith(expected_warning_prefix)
        assert expected_warning_subject in stored.warnings[0]
        assert stored.updated_at is not None
        assert len(competitors) == 2
        assert {item.status for item in competitors} == {'completed', 'failed'}
        assert {item.fetch_status for item in competitors} == {'success', 'failed'}
        assert len(audit_events) > 0
        assert audit_events[0].stage == 'pipeline'
        assert audit_events[0].event == 'started'
        assert all(event.processing_version == 1 for event in audit_events)
        assert any(event.stage == 'fetch' and event.event == 'completed' and event.duration_ms is not None for event in audit_events)
        assert any(event.event == 'dispatched' and isinstance(event.details, dict) and event.details.get('queue') for event in audit_events)
        assert any(event.stage == 'pipeline' and event.event == 'completed' for event in audit_events)
    log_messages = [record.getMessage() for record in caplog.records if record.name == 'app.tasks']
    assert any('step=fetch event=started' in message for message in log_messages)
    assert any('step=fetch event=completed' in message and 'status=success' in message for message in log_messages)
    assert any('step=heavy_analysis event=completed' in message for message in log_messages)
    assert any('step=features event=completed' in message for message in log_messages)
    assert any('step=scoring event=completed' in message and 'final_score=77.5000' in message for message in log_messages)
    assert any('step=competitors event=completed' in message and 'competitors_found=2' in message for message in log_messages)
    assert any('step=competitor_page event=completed' in message and 'competitor_id=' in message for message in log_messages)
    assert any('step=competitor_analysis event=completed' in message and 'competitor_id=' in message for message in log_messages)
    assert any('step=competitor_aggregation event=completed' in message and 'competitors_found=2' in message for message in log_messages)
    assert any('step=recommendations event=completed' in message and 'recommendations_count=1' in message for message in log_messages)
    assert any('step=pipeline event=completed' in message and 'final_status=completed_with_warnings' in message for message in log_messages)
    assert result == {
        'audit_id': 'audit-1',
        'status': 'completed_with_warnings',
        'score': 77.5,
        'competitors_count': 2,
        'recommendations_count': 1,
    }
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
def test_process_audit_fails_when_target_fetch_fails(monkeypatch, tmp_path):
    db_path = tmp_path / 'pipeline-failed.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)
    monkeypatch.setattr(
        'app.tasks.fetch_page',
        lambda url, use_browser=True: {
            'status': 'failed',
            'fetch_method': 'browser',
            'fetch_error_code': 'http_403',
            'fetch_error_message': 'HTTP 403',
            'final_url': url,
            'http_status': 403,
            'html': None,
            'text': None,
        },
    )
    with testing_session_local() as db:
        audit = Audit(
            id='audit-2',
            query='seo audit',
            target_url='https://blocked.example.com',
            top_n=5,
            status='queued',
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(audit)
        db.commit()
    result = process_audit.run('audit-2')
    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-2')
        assert stored is not None
        assert stored.status == 'failed'
        assert stored.target_fetch_status == 'failed'
        assert stored.target_fetch_method == 'browser'
        assert stored.target_fetch_error_code == 'http_403'
        assert stored.feature_schema_version == 'v2'
        assert isinstance(stored.target_snapshot, dict)
        assert stored.target_snapshot['status_code'] == 403
        assert stored.error_message == 'HTTP 403'
        assert stored.failure_context == {
            'stage': 'fetch',
            'code': 'http_403',
            'message': 'HTTP 403',
            'details': {
                'fetch_method': 'browser',
                'http_status': 403,
            },
        }
    assert result == {
        'audit_id': 'audit-2',
        'status': 'failed',
        'error_code': 'http_403',
    }
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
def test_process_audit_clears_stale_results_when_retry_fails(monkeypatch, tmp_path):
    db_path = tmp_path / 'pipeline-retry-failed.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)
    monkeypatch.setattr(
        'app.tasks.fetch_page',
        lambda url, use_browser=True: {
            'status': 'failed',
            'fetch_method': 'browser',
            'fetch_error_code': 'http_403',
            'fetch_error_message': 'HTTP 403',
            'final_url': url,
            'http_status': 403,
            'html': None,
            'text': None,
        },
    )
    with testing_session_local() as db:
        audit = Audit(
            id='audit-3',
            query='seo audit',
            target_url='https://example.com',
            top_n=5,
            status='completed',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            extracted_text='old text',
            features={'query_in_text': 1},
            score=88.0,
            score_breakdown={'final_score': 88.0},
            competitor_results=[{'url': 'https://competitor.example'}],
            comparison_summary={'user_score': 88.0},
            recommendations=[{'code': 'OLD', 'priority': 'low', 'message': 'stale'}],
            warnings=['stale warning'],
        )
        db.add(audit)
        db.commit()
    result = process_audit.run('audit-3')
    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-3')
        assert stored is not None
        assert stored.status == 'failed'
        assert stored.error_message == 'HTTP 403'
        assert stored.target_fetch_status == 'failed'
        assert stored.target_fetch_method == 'browser'
        assert stored.target_fetch_error_code == 'http_403'
        assert stored.feature_schema_version == 'v2'
        assert isinstance(stored.target_snapshot, dict)
        assert stored.target_snapshot['status_code'] == 403
        assert stored.failure_context == {
            'stage': 'fetch',
            'code': 'http_403',
            'message': 'HTTP 403',
            'details': {
                'fetch_method': 'browser',
                'http_status': 403,
            },
        }
        assert stored.extracted_text is None
        assert stored.features is None
        assert stored.score is None
        assert stored.score_breakdown is None
        assert stored.competitor_results is None
        assert stored.comparison_summary is None
        assert stored.recommendations is None
        assert stored.warnings == []
    assert result == {
        'audit_id': 'audit-3',
        'status': 'failed',
        'error_code': 'http_403',
    }
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
def test_process_audit_marks_unexpected_exception_as_failed_and_clears_outputs(monkeypatch, tmp_path, caplog):
    db_path = tmp_path / 'pipeline-exception.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)
    monkeypatch.setattr(
        'app.tasks.fetch_page',
        lambda url, use_browser=True: {
            'status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'final_url': url,
            'http_status': 200,
            'html': '<html><body><p>Body</p></body></html>',
            'text': 'Body',
        },
    )
    def fail_build_features(html, text, query):
        raise RuntimeError('feature extraction exploded')
    monkeypatch.setattr('app.tasks.build_features', fail_build_features)
    with testing_session_local() as db:
        audit = Audit(
            id='audit-4',
            query='seo audit',
            target_url='https://example.com',
            top_n=5,
            status='completed_with_warnings',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            extracted_text='old text',
            features={'query_in_text': 1},
            score=91.0,
            score_breakdown={'final_score': 91.0},
            competitor_results=[{'url': 'https://competitor.example'}],
            comparison_summary={'user_score': 91.0},
            recommendations=[{'code': 'OLD', 'priority': 'low', 'message': 'stale'}],
            warnings=['stale warning'],
        )
        db.add(audit)
        db.commit()
    caplog.set_level(logging.INFO, logger='app.tasks')
    with pytest.raises(RuntimeError, match='feature extraction exploded'):
        process_audit.run('audit-4')
    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-4')
        audit_events = db.scalars(
            select(AuditEvent)
            .where(AuditEvent.audit_id == 'audit-4')
            .order_by(AuditEvent.id.asc())
        ).all()
        assert stored is not None
        assert stored.status == 'failed'
        assert stored.error_message == 'feature extraction exploded'
        assert stored.failure_context == {
            'stage': 'features',
            'code': 'runtime_error',
            'message': 'feature extraction exploded',
            'details': None,
        }
        assert stored.target_fetch_status == 'success'
        assert stored.target_fetch_method == 'http'
        assert stored.target_fetch_error_code is None
        assert stored.target_fetch_error_message is None
        assert stored.feature_schema_version == 'v2'
        assert isinstance(stored.target_snapshot, dict)
        assert stored.target_snapshot['final_url'] == 'https://example.com'
        assert stored.extracted_text is None
        assert stored.features is None
        assert stored.score is None
        assert stored.score_breakdown is None
        assert stored.competitor_results is None
        assert stored.comparison_summary is None
        assert stored.recommendations is None
        assert stored.warnings == []
        assert any(event.stage == 'features' and event.event == 'failed' and event.duration_ms is not None for event in audit_events)
        assert any(
            event.stage == 'pipeline'
            and event.event == 'failed'
            and isinstance(event.details, dict)
            and event.details.get('failure_stage') == 'features'
            for event in audit_events
        )
    log_messages = [record.getMessage() for record in caplog.records if record.name == 'app.tasks']
    assert any('step=features event=started' in message for message in log_messages)
    assert any('step=features event=failed' in message and 'feature extraction exploded' in message for message in log_messages)
    assert any(
        'step=pipeline event=failed' in message
        and 'feature extraction exploded' in message
        and 'failure_stage=features' in message
        for message in log_messages
    )
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
def test_enqueue_audit_processing_falls_back_when_celery_enqueue_fails(monkeypatch):
    started: list[tuple[str, tuple[object, ...], bool]] = []
    class FakeThread:
        def __init__(self, target, args, daemon):
            started.append((target.__name__, args, daemon))
        def start(self):
            started.append(('started', (), True))
    def fail_delay(audit_id: str):
        raise RuntimeError(f'queue down for {audit_id}')
    monkeypatch.setattr('app.tasks._redis_available', lambda: True)
    monkeypatch.setattr('app.tasks.process_audit.apply_async', lambda args, queue: fail_delay(str(args[0])))
    monkeypatch.setattr('app.tasks.Thread', FakeThread)
    enqueue_audit_processing('audit-queue')
    assert started == [
        ('process_audit', ('audit-queue',), True),
        ('started', (), True),
    ]


def test_enqueue_audit_processing_routes_start_task_to_pipeline_queue(monkeypatch):
    captured: dict[str, object] = {}

    def fake_apply_async(*, args, queue):
        captured['args'] = args
        captured['queue'] = queue

    monkeypatch.setattr('app.tasks._redis_available', lambda: True)
    monkeypatch.setattr('app.tasks.process_audit.apply_async', fake_apply_async)

    enqueue_audit_processing('audit-start-queue')

    assert captured == {
        'args': ('audit-start-queue',),
        'queue': AUDIT_PIPELINE_QUEUE,
    }


def test_stage_tasks_are_registered_for_distributed_execution():
    assert process_audit.name == 'app.process_audit'
    assert process_audit_fetch_target.name == 'app.process_audit_fetch_target'
    assert process_audit_run_heavy_analysis.name == 'app.process_audit_run_heavy_analysis'
    assert process_audit_extract_features.name == 'app.process_audit_extract_features'
    assert process_audit_score_target.name == 'app.process_audit_score_target'
    assert process_audit_collect_competitors.name == 'app.process_audit_collect_competitors'
    assert process_audit_collect_competitor_page.name == 'app.process_audit_collect_competitor_page'
    assert process_audit_analyze_competitor_page.name == 'app.process_audit_analyze_competitor_page'
    assert process_audit_aggregate_competitors.name == 'app.process_audit_aggregate_competitors'
    assert process_audit_generate_recommendations.name == 'app.process_audit_generate_recommendations'
    assert process_audit_finalize.name == 'app.process_audit_finalize'
    assert resolve_task_queue(process_audit.name) == AUDIT_PIPELINE_QUEUE
    assert resolve_task_queue(process_audit_fetch_target.name) == AUDIT_FETCH_QUEUE
    assert resolve_task_queue(process_audit_run_heavy_analysis.name) == AUDIT_HEAVY_ANALYSIS_QUEUE
    assert resolve_task_queue(process_audit_extract_features.name) == AUDIT_FEATURES_QUEUE
    assert resolve_task_queue(process_audit_score_target.name) == AUDIT_SCORING_QUEUE
    assert resolve_task_queue(process_audit_collect_competitors.name) == AUDIT_COMPETITORS_QUEUE
    assert resolve_task_queue(process_audit_collect_competitor_page.name) == AUDIT_COMPETITOR_PAGES_QUEUE
    assert resolve_task_queue(process_audit_analyze_competitor_page.name) == AUDIT_HEAVY_ANALYSIS_QUEUE
    assert resolve_task_queue(process_audit_aggregate_competitors.name) == AUDIT_COMPETITORS_QUEUE
    assert resolve_task_queue(process_audit_generate_recommendations.name) == AUDIT_RECOMMENDATIONS_QUEUE
    assert resolve_task_queue(process_audit_finalize.name) == AUDIT_FINALIZE_QUEUE


def test_process_audit_resumes_current_stage_without_incrementing_processing_version(monkeypatch, tmp_path):
    db_path = tmp_path / 'pipeline-resume.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)
    monkeypatch.setattr('app.tasks._redis_available', lambda: True)

    dispatched: list[tuple[tuple[object, ...], str]] = []

    def fake_apply_async(*, args, queue):
        dispatched.append((args, queue))

    monkeypatch.setattr('app.tasks.process_audit_score_target.apply_async', fake_apply_async)

    with testing_session_local() as db:
        audit = Audit(
            id='audit-resume',
            query='seo audit',
            target_url='https://example.com',
            top_n=5,
            status='processing',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            processing_version=7,
            orchestration_stage='scoring',
            extracted_text='Body',
            features={'query_in_text': 1},
        )
        db.add(audit)
        db.commit()

    result = process_audit.run('audit-resume')

    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-resume')
        assert stored is not None
        assert stored.processing_version == 7
        assert stored.orchestration_stage == 'scoring'

    assert dispatched == [
        (
            ('audit-resume', 7),
            AUDIT_SCORING_QUEUE,
        )
    ]
    assert result == {
        'audit_id': 'audit-resume',
        'status': 'processing',
        'next_stage': 'app.process_audit_score_target',
        'next_queue': AUDIT_SCORING_QUEUE,
        'dispatch_mode': 'queued',
    }

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_stage_task_ignores_stale_processing_version(monkeypatch, tmp_path):
    db_path = tmp_path / 'pipeline-stale-version.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)

    with testing_session_local() as db:
        audit = Audit(
            id='audit-stale',
            query='seo audit',
            target_url='https://example.com',
            top_n=5,
            status='processing',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            processing_version=3,
            orchestration_stage='features',
            extracted_text='Body',
            target_html='<html></html>',
        )
        db.add(audit)
        db.commit()

    result = process_audit_extract_features.run('audit-stale', 2)

    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-stale')
        assert stored is not None
        assert stored.processing_version == 3
        assert stored.orchestration_stage == 'features'
        assert stored.features is None

    assert result == {
        'audit_id': 'audit-stale',
        'status': 'ignored',
        'reason': 'stale_processing_version',
        'processing_version': 2,
        'current_version': 3,
        'current_stage': 'features',
    }

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_process_audit_extract_features_rebuilds_from_saved_snapshot(monkeypatch, tmp_path):
    db_path = tmp_path / 'pipeline-snapshot-features.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)

    captured: dict[str, str] = {}

    def fake_build_features(html, text, query):
        captured['html'] = html
        captured['text'] = text
        captured['query'] = query
        return {
            'text_length_chars': len(text),
            'query_in_text': 1,
            'semantic_similarity': 0.91,
        }

    monkeypatch.setattr('app.tasks.build_features', fake_build_features)
    monkeypatch.setattr(
        'app.tasks._dispatch_stage_task',
        lambda task, audit_id, processing_version=None: {
            'audit_id': audit_id,
            'status': 'processing',
            'next_stage': task.name,
        },
    )

    with testing_session_local() as db:
        audit = Audit(
            id='audit-snapshot-features',
            query='seo audit',
            target_url='https://example.com',
            top_n=5,
            status='processing',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            processing_version=1,
            orchestration_stage='features',
            target_snapshot={
                'requested_url': 'https://example.com',
                'final_url': 'https://example.com/final',
                'status_code': 200,
                'fetch_method': 'http',
                'response_headers': {},
                'redirect_chain': [],
                'html': '<html><body><h1>Snapshot</h1><p>Body</p></body></html>',
                'text': 'Snapshot Body',
                'json_ld': [],
            },
            extracted_text=None,
            target_html=None,
        )
        db.add(audit)
        db.commit()

    result = process_audit_extract_features.run('audit-snapshot-features', 1)

    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-snapshot-features')
        assert stored is not None
        assert stored.feature_schema_version == 'v2'
        assert stored.features is not None
        assert stored.features['text_length_chars'] == len('Snapshot Body')
        assert stored.features['query_in_text'] == 1
        assert stored.features['semantic_similarity'] == 0.91
        assert stored.features['http_status_code'] == 200
        assert stored.features['page_indexable'] == 1
        assert stored.features['canonical_present'] == 0
        assert stored.target_html is None
        assert isinstance(stored.target_snapshot, dict)
        assert stored.target_snapshot['final_url'] == 'https://example.com/final'

    assert captured == {
        'html': '<html><body><h1>Snapshot</h1><p>Body</p></body></html>',
        'text': 'Snapshot Body',
        'query': 'seo audit',
    }
    assert result == {
        'audit_id': 'audit-snapshot-features',
        'status': 'processing',
        'next_stage': 'app.process_audit_score_target',
    }

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_process_audit_run_heavy_analysis_persists_payload_and_routes_to_features(monkeypatch, tmp_path):
    db_path = tmp_path / 'pipeline-heavy-analysis.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)
    monkeypatch.setattr(
        'app.tasks._dispatch_stage_task',
        lambda task, audit_id, processing_version=None, **kwargs: {
            'audit_id': audit_id,
            'status': 'processing',
            'next_stage': task.name,
            'next_queue': resolve_task_queue(task.name),
        },
    )

    with testing_session_local() as db:
        audit = Audit(
            id='audit-heavy-analysis',
            query='seo audit',
            target_url='https://example.com',
            top_n=5,
            status='processing',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            processing_version=1,
            orchestration_stage='heavy_analysis',
            target_snapshot={
                'requested_url': 'https://example.com',
                'final_url': 'https://example.com',
                'status_code': 200,
                'fetch_method': 'browser',
                'response_headers': {},
                'redirect_chain': [],
                'html': '<html><head><meta name="viewport" content="width=device-width"><script type="application/ld+json">{"@type":"Organization"}</script></head><body><h1>Title</h1><p>Body</p></body></html>',
                'text': 'Title Body',
                'json_ld': ['{"@type":"Organization"}'],
            },
        )
        db.add(audit)
        db.commit()

    result = process_audit_run_heavy_analysis.run('audit-heavy-analysis', 1)

    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-heavy-analysis')
        assert stored is not None
        assert stored.orchestration_stage == 'features'
        assert isinstance(stored.heavy_analysis, dict)
        assert stored.heavy_analysis['summary']['analyzer_count'] == 4
        assert stored.heavy_analysis['features']['structured_data_business_schema_present'] == 1
        assert stored.heavy_analysis['features']['rendering_browser_fetch_used'] == 1

    assert result == {
        'audit_id': 'audit-heavy-analysis',
        'status': 'processing',
        'next_stage': 'app.process_audit_extract_features',
        'next_queue': AUDIT_FEATURES_QUEUE,
    }

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_dispatch_stage_task_routes_next_stage_to_stage_queue(monkeypatch):
    captured: dict[str, object] = {}

    def fake_apply_async(*, args, queue):
        captured['args'] = args
        captured['queue'] = queue

    monkeypatch.setattr('app.tasks._redis_available', lambda: True)
    monkeypatch.setattr('app.tasks.process_audit_fetch_target.apply_async', fake_apply_async)

    result = _dispatch_stage_task(process_audit_fetch_target, 'audit-queue-routing')

    assert captured == {
        'args': ('audit-queue-routing',),
        'queue': AUDIT_FETCH_QUEUE,
    }
    assert result == {
        'audit_id': 'audit-queue-routing',
        'status': 'processing',
        'next_stage': 'app.process_audit_fetch_target',
        'next_queue': AUDIT_FETCH_QUEUE,
        'dispatch_mode': 'queued',
    }


def test_dispatch_stage_task_runs_inline_when_runtime_guard_blocks_queue(monkeypatch):
    captured: dict[str, object] = {'ran_inline': False}

    class Decision:
        action = 'inline'
        reason = 'queue_capacity_guard'
        message = 'Queue is degraded.'
        details = {'pressure_status': 'backlogged'}

    monkeypatch.setattr('app.tasks.evaluate_queue_dispatch', lambda queue_name: Decision())
    monkeypatch.setattr('app.tasks._redis_available', lambda: True)
    monkeypatch.setattr(
        'app.tasks.process_audit_fetch_target.run',
        lambda audit_id: captured.update({'ran_inline': True, 'audit_id': audit_id}) or {'audit_id': audit_id, 'status': 'inline'},
    )
    monkeypatch.setattr(
        'app.tasks.process_audit_fetch_target.apply_async',
        lambda *args, **kwargs: pytest.fail('queue dispatch should be blocked by runtime guard'),
    )

    result = _dispatch_stage_task(process_audit_fetch_target, 'audit-inline-guard')

    assert captured == {
        'ran_inline': True,
        'audit_id': 'audit-inline-guard',
    }
    assert result == {
        'audit_id': 'audit-inline-guard',
        'status': 'inline',
    }


def test_collect_competitors_fans_out_competitor_page_tasks(monkeypatch, tmp_path):
    db_path = tmp_path / 'pipeline-fanout.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)
    monkeypatch.setattr('app.tasks._redis_available', lambda: True)
    monkeypatch.setattr(
        'app.tasks.search_competitor_pages',
        lambda query, target_url, limit: [
            {
                'url': 'https://competitor-a.example',
                'domain': 'competitor-a.example',
                'title': 'Competitor A',
                'snippet': 'Snippet A',
                'rank': 1,
                'serp_page': 0,
            },
            {
                'url': 'https://competitor-b.example',
                'domain': 'competitor-b.example',
                'title': 'Competitor B',
                'snippet': 'Snippet B',
                'rank': 2,
                'serp_page': 0,
            },
        ],
    )
    dispatched: list[tuple[tuple[object, ...], str]] = []

    def fake_apply_async(*, args, queue):
        dispatched.append((args, queue))

    monkeypatch.setattr('app.tasks.process_audit_collect_competitor_page.apply_async', fake_apply_async)

    with testing_session_local() as db:
        audit = Audit(
            id='audit-fanout',
            query='seo audit',
            target_url='https://example.com',
            top_n=5,
            status='processing',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            processing_version=1,
            orchestration_stage='competitors',
            features={'query_in_text': 1},
            score=88.0,
        )
        db.add(audit)
        db.commit()

    result = process_audit_collect_competitors.run('audit-fanout', 1)

    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-fanout')
        competitors = db.scalars(select(AuditCompetitor).where(AuditCompetitor.audit_id == 'audit-fanout')).all()
        assert stored is not None
        assert stored.competitor_processing_status == 'collecting'
        assert len(competitors) == 2
        assert {item.status for item in competitors} == {'pending'}

    assert len(dispatched) == 2
    assert {queue for _, queue in dispatched} == {AUDIT_COMPETITOR_PAGES_QUEUE}
    assert {str(args[0]) for args, _ in dispatched} == {'audit-fanout'}
    assert result == {
        'audit_id': 'audit-fanout',
        'status': 'processing',
        'next_stage': 'app.process_audit_collect_competitor_page',
        'next_queue': AUDIT_COMPETITOR_PAGES_QUEUE,
        'dispatch_mode': 'queued',
        'processing_version': 1,
        'competitor_tasks_dispatched': 2,
        'competitor_tasks_enqueued': 2,
    }

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_collect_competitors_runs_competitor_processing_inline_when_runtime_guard_blocks_fanout(monkeypatch, tmp_path):
    db_path = tmp_path / 'pipeline-fanout-inline-guard.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)
    monkeypatch.setattr('app.tasks._redis_available', lambda: False)
    monkeypatch.setattr(
        'app.tasks.search_competitor_pages',
        lambda query, target_url, limit: [
            {
                'url': 'https://competitor-a.example',
                'domain': 'competitor-a.example',
                'title': 'Competitor A',
                'snippet': 'Snippet A',
                'rank': 1,
                'serp_page': 0,
            },
            {
                'url': 'https://competitor-b.example',
                'domain': 'competitor-b.example',
                'title': 'Competitor B',
                'snippet': 'Snippet B',
                'rank': 2,
                'serp_page': 0,
            },
        ],
    )

    class Decision:
        action = 'inline'
        reason = 'queue_capacity_guard'
        message = 'Competitor fan-out queue is degraded.'
        details = {'pressure_status': 'backlogged'}

    monkeypatch.setattr(
        'app.tasks.evaluate_queue_dispatch',
        lambda queue_name: Decision(),
    )
    monkeypatch.setattr(
        'app.tasks.process_audit_collect_competitor_page.apply_async',
        lambda *args, **kwargs: pytest.fail('competitor fan-out should not enqueue when runtime guard blocks the queue'),
    )
    def fake_fetch_competitor_page(result):
        url = str(result['url'])
        return {
            'url': url,
            'domain': str(result['domain']),
            'title': str(result['title']),
            'snippet': str(result['snippet']),
            'serp_rank': int(result.get('rank') or result.get('serp_rank') or 0),
            'serp_page': int(result['serp_page']),
            'fetch_status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'snapshot': {
                'requested_url': url,
                'final_url': url,
                'status_code': 200,
                'fetch_method': 'http',
                'html': '<html><body><h1>Competitor</h1><p>Body</p></body></html>',
                'text': 'Competitor Body',
                'json_ld': [],
            },
        }

    def fake_analyze_competitor_snapshot(result, query, snapshot):
        assert query == 'seo audit'
        assert isinstance(snapshot, dict)
        return {
            'url': str(result['url']),
            'domain': str(result['domain']),
            'title': str(result['title']),
            'snippet': str(result['snippet']),
            'serp_rank': int(result.get('rank') or result.get('serp_rank') or 0),
            'serp_page': int(result['serp_page']),
            'fetch_status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'score': 81.0,
            'features': {
                'text_length_chars': 20,
                'query_in_text': 1,
                'semantic_similarity': 0.82,
            },
        }

    monkeypatch.setattr('app.tasks.fetch_competitor_page', fake_fetch_competitor_page)
    monkeypatch.setattr('app.tasks.analyze_competitor_snapshot', fake_analyze_competitor_snapshot)
    monkeypatch.setattr(
        'app.tasks.build_comparison_summary',
        lambda user_features, user_score, competitor_results, **kwargs: {
            'user_score': user_score,
            'competitors_average_score': 81.0,
            'score_difference': 0.0,
            'competitors_count': 2,
            'competitors_found': 2,
            'competitors_analyzed': 2,
            'competitors_failed': 0,
        },
    )
    monkeypatch.setattr('app.tasks.generate_recommendations', lambda page_features, page_score, competitor_pages_features: [])

    with testing_session_local() as db:
        audit = Audit(
            id='audit-fanout-inline',
            query='seo audit',
            target_url='https://example.com',
            top_n=5,
            status='processing',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            processing_version=1,
            orchestration_stage='competitors',
            features={'query_in_text': 1},
            score=88.0,
        )
        db.add(audit)
        db.commit()

    result = process_audit_collect_competitors.run('audit-fanout-inline', 1)

    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-fanout-inline')
        competitors = db.scalars(select(AuditCompetitor).where(AuditCompetitor.audit_id == 'audit-fanout-inline')).all()
        assert stored is not None
        assert stored.status == 'completed'
        assert stored.competitor_processing_status == 'aggregated'
        assert len(competitors) == 2
        assert {item.status for item in competitors} == {'completed'}

    assert result == {
        'audit_id': 'audit-fanout-inline',
        'status': 'completed',
        'score': 88.0,
        'competitors_count': 2,
        'recommendations_count': 0,
    }

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_competitor_page_completion_dispatches_aggregation_once(monkeypatch, tmp_path):
    db_path = tmp_path / 'pipeline-aggregation-race.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)
    monkeypatch.setattr('app.tasks._redis_available', lambda: True)
    monkeypatch.setattr(
        'app.tasks.fetch_competitor_page',
        lambda result: {
            'url': str(result['url']),
            'domain': str(result['domain']),
            'title': str(result['title']),
            'snippet': str(result['snippet']),
            'serp_rank': int(result.get('rank') or result.get('serp_rank') or 0),
            'serp_page': int(result['serp_page']),
            'fetch_status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'snapshot': {
                'requested_url': str(result['url']),
                'final_url': str(result['url']),
                'status_code': 200,
                'fetch_method': 'http',
                'html': '<html><body><h1>Competitor</h1><p>Body</p></body></html>',
                'text': 'Competitor Body',
                'json_ld': [],
            },
        },
    )
    monkeypatch.setattr(
        'app.tasks.analyze_competitor_snapshot',
        lambda result, query, snapshot: {
            'url': str(result['url']),
            'domain': str(result['domain']),
            'title': str(result['title']),
            'snippet': str(result['snippet']),
            'serp_rank': int(result.get('rank') or result.get('serp_rank') or 0),
            'serp_page': int(result['serp_page']),
            'fetch_status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'score': 81.5,
            'features': {
                'text_length_chars': 20,
                'query_in_text': 1,
                'semantic_similarity': 0.83,
            },
        },
    )

    analysis_dispatched: list[tuple[tuple[object, ...], str]] = []
    aggregation_dispatched: list[tuple[tuple[object, ...], str]] = []

    def fake_analysis_apply_async(*, args, queue):
        analysis_dispatched.append((args, queue))

    def fake_aggregation_apply_async(*, args, queue):
        aggregation_dispatched.append((args, queue))

    monkeypatch.setattr('app.tasks.process_audit_analyze_competitor_page.apply_async', fake_analysis_apply_async)
    monkeypatch.setattr('app.tasks.process_audit_aggregate_competitors.apply_async', fake_aggregation_apply_async)

    with testing_session_local() as db:
        audit = Audit(
            id='audit-aggregation-race',
            query='seo audit',
            target_url='https://example.com',
            top_n=5,
            status='processing',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            processing_version=1,
            orchestration_stage='competitors',
            competitor_processing_status='collecting',
            features={'query_in_text': 1},
            score=88.0,
        )
        db.add(audit)
        db.add(
            AuditCompetitor(
                id='competitor-1',
                audit_id='audit-aggregation-race',
                url='https://competitor-1.example',
                domain='competitor-1.example',
                title='Competitor 1',
                snippet='Snippet 1',
                serp_rank=1,
                serp_page=0,
                status='pending',
                created_at=datetime.now(UTC).replace(tzinfo=None),
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        db.add(
            AuditCompetitor(
                id='competitor-2',
                audit_id='audit-aggregation-race',
                url='https://competitor-2.example',
                domain='competitor-2.example',
                title='Competitor 2',
                snippet='Snippet 2',
                serp_rank=2,
                serp_page=0,
                status='pending',
                created_at=datetime.now(UTC).replace(tzinfo=None),
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        db.commit()

    first_result = process_audit_collect_competitor_page.run('audit-aggregation-race', 1, 'competitor-1')
    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-aggregation-race')
        competitor_1 = db.get(AuditCompetitor, 'competitor-1')
        assert stored is not None
        assert stored.competitor_processing_status == 'collecting'
        assert competitor_1 is not None
        assert competitor_1.status == 'analysis_pending'
    assert aggregation_dispatched == []
    assert first_result == {
        'audit_id': 'audit-aggregation-race',
        'status': 'processing',
        'next_stage': 'app.process_audit_analyze_competitor_page',
        'next_queue': AUDIT_HEAVY_ANALYSIS_QUEUE,
        'dispatch_mode': 'queued',
    }

    fetch_second_result = process_audit_collect_competitor_page.run('audit-aggregation-race', 1, 'competitor-2')
    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-aggregation-race')
        competitor_2 = db.get(AuditCompetitor, 'competitor-2')
        assert stored is not None
        assert stored.competitor_processing_status == 'collecting'
        assert competitor_2 is not None
        assert competitor_2.status == 'analysis_pending'

    assert analysis_dispatched == [
        (
            ('audit-aggregation-race', 1, 'competitor-1'),
            AUDIT_HEAVY_ANALYSIS_QUEUE,
        ),
        (
            ('audit-aggregation-race', 1, 'competitor-2'),
            AUDIT_HEAVY_ANALYSIS_QUEUE,
        )
    ]
    assert aggregation_dispatched == []
    assert fetch_second_result == {
        'audit_id': 'audit-aggregation-race',
        'status': 'processing',
        'next_stage': 'app.process_audit_analyze_competitor_page',
        'next_queue': AUDIT_HEAVY_ANALYSIS_QUEUE,
        'dispatch_mode': 'queued',
    }

    first_analysis_result = process_audit_analyze_competitor_page.run('audit-aggregation-race', 1, 'competitor-1')
    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-aggregation-race')
        competitor_1 = db.get(AuditCompetitor, 'competitor-1')
        assert stored is not None
        assert stored.competitor_processing_status == 'collecting'
        assert competitor_1 is not None
        assert competitor_1.status == 'completed'
    assert first_analysis_result == {
        'audit_id': 'audit-aggregation-race',
        'competitor_id': 'competitor-1',
        'status': 'processing',
    }
    assert aggregation_dispatched == []

    second_analysis_result = process_audit_analyze_competitor_page.run('audit-aggregation-race', 1, 'competitor-2')
    with testing_session_local() as db:
        stored = db.get(Audit, 'audit-aggregation-race')
        assert stored is not None
        assert stored.competitor_processing_status == 'aggregating'

    assert aggregation_dispatched == [
        (
            ('audit-aggregation-race', 1),
            AUDIT_COMPETITORS_QUEUE,
        )
    ]
    assert second_analysis_result == {
        'audit_id': 'audit-aggregation-race',
        'status': 'processing',
        'next_stage': 'app.process_audit_aggregate_competitors',
        'next_queue': AUDIT_COMPETITORS_QUEUE,
        'dispatch_mode': 'queued',
    }

    duplicate_result = process_audit_analyze_competitor_page.run('audit-aggregation-race', 1, 'competitor-2')
    assert duplicate_result == {
        'audit_id': 'audit-aggregation-race',
        'competitor_id': 'competitor-2',
        'status': 'completed',
    }
    assert aggregation_dispatched == [
        (
            ('audit-aggregation-race', 1),
            AUDIT_COMPETITORS_QUEUE,
        )
    ]

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_competitor_page_duplicate_delivery_does_not_repeat_network_fetch(monkeypatch, tmp_path):
    db_path = tmp_path / 'pipeline-duplicate-delivery.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)

    fetch_calls: list[str] = []

    def fake_fetch(result):
        fetch_calls.append(str(result['url']))
        return {
            'url': str(result['url']),
            'domain': str(result['domain']),
            'title': str(result['title']),
            'snippet': str(result['snippet']),
            'serp_rank': int(result.get('rank') or result.get('serp_rank') or 0),
            'serp_page': int(result['serp_page']),
            'fetch_status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'snapshot': {
                'requested_url': str(result['url']),
                'final_url': str(result['url']),
                'status_code': 200,
                'fetch_method': 'http',
                'html': '<html><body><h1>Competitor</h1><p>Body</p></body></html>',
                'text': 'Competitor Body',
                'json_ld': [],
            },
        }

    monkeypatch.setattr('app.tasks.fetch_competitor_page', fake_fetch)
    monkeypatch.setattr('app.tasks._dispatch_competitor_aggregation_if_ready', lambda audit_id, processing_version: None)

    with testing_session_local() as db:
        audit = Audit(
            id='audit-duplicate-delivery',
            query='seo audit',
            target_url='https://example.com',
            top_n=5,
            status='processing',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            processing_version=4,
            orchestration_stage='competitors',
            competitor_processing_status='collecting',
            features={'query_in_text': 1},
            score=88.0,
        )
        competitor = AuditCompetitor(
            id='competitor-duplicate',
            audit_id='audit-duplicate-delivery',
            url='https://competitor-duplicate.example',
            domain='competitor-duplicate.example',
            title='Competitor Duplicate',
            snippet='Snippet duplicate',
            serp_rank=1,
            serp_page=0,
            status='pending',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(audit)
        db.add(competitor)
        db.commit()

        competitor.status = 'processing'
        competitor.updated_at = datetime.now(UTC).replace(tzinfo=None)
        db.commit()

    duplicate_result = process_audit_collect_competitor_page.run('audit-duplicate-delivery', 4, 'competitor-duplicate')

    assert duplicate_result == {
        'audit_id': 'audit-duplicate-delivery',
        'competitor_id': 'competitor-duplicate',
        'status': 'processing',
    }
    assert fetch_calls == []

    with testing_session_local() as db:
        competitor = db.get(AuditCompetitor, 'competitor-duplicate')
        assert competitor is not None
        assert competitor.status == 'processing'

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_competitor_analysis_duplicate_delivery_does_not_repeat_heavy_analysis(monkeypatch, tmp_path):
    db_path = tmp_path / 'pipeline-duplicate-analysis-delivery.db'
    engine = create_engine(
        f'sqlite:///{db_path}',
        connect_args={'check_same_thread': False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    monkeypatch.setattr('app.tasks.SessionLocal', testing_session_local)

    analysis_calls: list[str] = []

    def fake_analyze(result, query, snapshot):
        analysis_calls.append(str(result['url']))
        return {
            'url': str(result['url']),
            'domain': str(result['domain']),
            'title': str(result['title']),
            'snippet': str(result['snippet']),
            'serp_rank': int(result.get('rank') or result.get('serp_rank') or 0),
            'serp_page': int(result['serp_page']),
            'fetch_status': 'success',
            'fetch_method': 'http',
            'fetch_error_code': None,
            'fetch_error_message': None,
            'score': 80.0,
            'features': {
                'text_length_chars': 20,
                'query_in_text': 1,
                'semantic_similarity': 0.82,
            },
        }

    monkeypatch.setattr('app.tasks.analyze_competitor_snapshot', fake_analyze)
    monkeypatch.setattr('app.tasks._dispatch_competitor_aggregation_if_ready', lambda audit_id, processing_version: None)

    with testing_session_local() as db:
        audit = Audit(
            id='audit-duplicate-analysis-delivery',
            query='seo audit',
            target_url='https://example.com',
            top_n=5,
            status='processing',
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
            processing_version=4,
            orchestration_stage='competitors',
            competitor_processing_status='collecting',
            features={'query_in_text': 1},
            score=88.0,
        )
        competitor = AuditCompetitor(
            id='competitor-duplicate-analysis',
            audit_id='audit-duplicate-analysis-delivery',
            url='https://competitor-duplicate.example',
            domain='competitor-duplicate.example',
            title='Competitor Duplicate',
            snippet='Snippet duplicate',
            serp_rank=1,
            serp_page=0,
            status='analyzing',
            snapshot={
                'requested_url': 'https://competitor-duplicate.example',
                'final_url': 'https://competitor-duplicate.example',
                'status_code': 200,
                'fetch_method': 'http',
                'html': '<html><body><h1>Competitor</h1><p>Body</p></body></html>',
                'text': 'Competitor Body',
                'json_ld': [],
            },
            created_at=datetime.now(UTC).replace(tzinfo=None),
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(audit)
        db.add(competitor)
        db.commit()

    duplicate_result = process_audit_analyze_competitor_page.run(
        'audit-duplicate-analysis-delivery',
        4,
        'competitor-duplicate-analysis',
    )

    assert duplicate_result == {
        'audit_id': 'audit-duplicate-analysis-delivery',
        'competitor_id': 'competitor-duplicate-analysis',
        'status': 'analyzing',
    }
    assert analysis_calls == []

    with testing_session_local() as db:
        competitor = db.get(AuditCompetitor, 'competitor-duplicate-analysis')
        assert competitor is not None
        assert competitor.status == 'analyzing'

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_celery_config_declares_stage_queues_and_routes():
    configured_queues = {queue.name for queue in celery_app.conf.task_queues}

    assert configured_queues == {
        AUDIT_PIPELINE_QUEUE,
        AUDIT_FETCH_QUEUE,
        AUDIT_HEAVY_ANALYSIS_QUEUE,
        AUDIT_FEATURES_QUEUE,
        AUDIT_SCORING_QUEUE,
        AUDIT_COMPETITORS_QUEUE,
        AUDIT_COMPETITOR_PAGES_QUEUE,
        AUDIT_RECOMMENDATIONS_QUEUE,
        AUDIT_FINALIZE_QUEUE,
    }
    assert celery_app.conf.task_default_queue == AUDIT_PIPELINE_QUEUE
    assert celery_app.conf.task_routes['app.process_audit']['queue'] == AUDIT_PIPELINE_QUEUE
    assert celery_app.conf.task_routes['app.process_audit_fetch_target']['queue'] == AUDIT_FETCH_QUEUE
    assert celery_app.conf.task_routes['app.process_audit_run_heavy_analysis']['queue'] == AUDIT_HEAVY_ANALYSIS_QUEUE
    assert celery_app.conf.task_routes['app.process_audit_extract_features']['queue'] == AUDIT_FEATURES_QUEUE
    assert celery_app.conf.task_routes['app.process_audit_score_target']['queue'] == AUDIT_SCORING_QUEUE
    assert celery_app.conf.task_routes['app.process_audit_collect_competitors']['queue'] == AUDIT_COMPETITORS_QUEUE
    assert celery_app.conf.task_routes['app.process_audit_collect_competitor_page']['queue'] == AUDIT_COMPETITOR_PAGES_QUEUE
    assert celery_app.conf.task_routes['app.process_audit_analyze_competitor_page']['queue'] == AUDIT_HEAVY_ANALYSIS_QUEUE
    assert celery_app.conf.task_routes['app.process_audit_aggregate_competitors']['queue'] == AUDIT_COMPETITORS_QUEUE
    assert celery_app.conf.task_routes['app.process_audit_generate_recommendations']['queue'] == AUDIT_RECOMMENDATIONS_QUEUE
    assert celery_app.conf.task_routes['app.process_audit_finalize']['queue'] == AUDIT_FINALIZE_QUEUE
