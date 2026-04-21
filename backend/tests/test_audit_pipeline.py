from __future__ import annotations
import logging
from datetime import UTC, datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.db import Base
from app.models import Audit
from app.tasks import (
    enqueue_audit_processing,
    process_audit,
    process_audit_collect_competitors,
    process_audit_extract_features,
    process_audit_fetch_target,
    process_audit_finalize,
    process_audit_generate_recommendations,
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
        'app.tasks.build_competitor_results',
        lambda query, target_url, top_n: [
            {
                'url': 'https://competitor-a.example',
                'domain': 'competitor-a.example',
                'title': 'Competitor A',
                'score': 82.4,
                'features': {
                    'text_length_chars': 18,
                    'query_in_text': 1,
                    'semantic_similarity': 0.87,
                },
                'fetch_status': 'success',
                'fetch_method': 'http',
                'fetch_error_code': None,
                'fetch_error_message': None,
            },
            {
                'url': 'https://competitor-b.example',
                'domain': 'competitor-b.example',
                'title': 'Competitor B',
                'score': None,
                'features': None,
                'fetch_status': 'failed',
                'fetch_method': 'browser',
                'fetch_error_code': 'http_403',
                'fetch_error_message': 'HTTP 403',
            },
        ],
    )
    monkeypatch.setattr(
        'app.tasks.build_comparison_summary',
        lambda user_features, user_score, competitor_results: {
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
        assert stored is not None
        assert stored.status == 'completed_with_warnings'
        assert stored.extracted_text == 'Title Body'
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
    log_messages = [record.getMessage() for record in caplog.records if record.name == 'app.tasks']
    assert any('step=fetch event=started' in message for message in log_messages)
    assert any('step=fetch event=completed' in message and 'status=success' in message for message in log_messages)
    assert any('step=features event=completed' in message for message in log_messages)
    assert any('step=scoring event=completed' in message and 'final_score=77.5000' in message for message in log_messages)
    assert any('step=competitors event=completed' in message and 'competitors_found=2' in message for message in log_messages)
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
        assert stored.extracted_text is None
        assert stored.features is None
        assert stored.score is None
        assert stored.score_breakdown is None
        assert stored.competitor_results is None
        assert stored.comparison_summary is None
        assert stored.recommendations is None
        assert stored.warnings == []
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
    monkeypatch.setattr('app.tasks.process_audit.delay', fail_delay)
    monkeypatch.setattr('app.tasks.Thread', FakeThread)
    enqueue_audit_processing('audit-queue')
    assert started == [
        ('process_audit', ('audit-queue',), True),
        ('started', (), True),
    ]


def test_stage_tasks_are_registered_for_distributed_execution():
    assert process_audit.name == 'app.process_audit'
    assert process_audit_fetch_target.name == 'app.process_audit_fetch_target'
    assert process_audit_extract_features.name == 'app.process_audit_extract_features'
    assert process_audit_score_target.name == 'app.process_audit_score_target'
    assert process_audit_collect_competitors.name == 'app.process_audit_collect_competitors'
    assert process_audit_generate_recommendations.name == 'app.process_audit_generate_recommendations'
    assert process_audit_finalize.name == 'app.process_audit_finalize'
