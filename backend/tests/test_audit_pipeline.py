from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Audit
from app.tasks import process_audit


def test_process_audit_pipeline_saves_results(monkeypatch, tmp_path):
    db_path = tmp_path / "pipeline.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr("app.tasks.SessionLocal", testing_session_local)
    monkeypatch.setattr(
        "app.tasks.fetch_page",
        lambda url, use_browser=True: {
            "status": "success",
            "fetch_method": "http",
            "fetch_error_code": None,
            "fetch_error_message": None,
            "final_url": url,
            "http_status": 200,
            "html": "<html><body><h1>Title</h1><p>Body</p></body></html>",
            "text": "Title Body",
        },
    )
    monkeypatch.setattr(
        "app.tasks.build_features",
        lambda html, text, query: {
            "text_length_chars": 10,
            "query_in_text": 1,
            "semantic_similarity": 0.81,
        },
    )
    monkeypatch.setattr(
        "app.tasks.explain_score",
        lambda features: {
            "final_score": 77.5,
            "rule_score": 74.0,
            "ml_score": 84.0,
            "methodology": "Тестовая методология",
            "positives": [
                {
                    "code": "GOOD_TITLE",
                    "label": "Есть title",
                    "impact": 7.0,
                    "detail": "Title найден",
                }
            ],
            "negatives": [
                {
                    "code": "SHORT_TEXT",
                    "label": "Мало текста",
                    "impact": -4.0,
                    "detail": "Текст короткий",
                }
            ],
            "factors": [],
        },
    )
    monkeypatch.setattr(
        "app.tasks.build_competitor_results",
        lambda query, target_url, top_n: [
            {
                "url": "https://competitor-a.example",
                "domain": "competitor-a.example",
                "title": "Competitor A",
                "score": 82.4,
                "features": {
                    "text_length_chars": 18,
                    "query_in_text": 1,
                    "semantic_similarity": 0.87,
                },
                "fetch_status": "success",
                "fetch_method": "http",
                "fetch_error_code": None,
                "fetch_error_message": None,
            },
            {
                "url": "https://competitor-b.example",
                "domain": "competitor-b.example",
                "title": "Competitor B",
                "score": None,
                "features": None,
                "fetch_status": "failed",
                "fetch_method": "browser",
                "fetch_error_code": "http_403",
                "fetch_error_message": "HTTP 403",
            },
        ],
    )
    monkeypatch.setattr(
        "app.tasks.build_comparison_summary",
        lambda user_features, user_score, competitor_results: {
            "user_score": 77.5,
            "competitors_average_score": 82.4,
            "score_difference": -4.9,
            "competitors_count": 1,
            "competitors_found": 2,
            "competitors_analyzed": 1,
            "competitors_failed": 1,
        },
    )
    monkeypatch.setattr(
        "app.tasks.generate_recommendations",
        lambda page_features, page_score, competitor_pages_features: [
            {
                "code": "TEST_REC",
                "priority": "medium",
                "message": "Test recommendation",
            }
        ],
    )

    with testing_session_local() as db:
        audit = Audit(
            id="audit-1",
            query="plastic windows",
            target_url="https://example.com",
            top_n=5,
            status="queued",
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(audit)
        db.commit()

    result = process_audit.run("audit-1")

    with testing_session_local() as db:
        stored = db.get(Audit, "audit-1")
        assert stored is not None
        assert stored.status == "completed_with_warnings"
        assert stored.extracted_text == "Title Body"
        assert stored.target_fetch_status == "success"
        assert stored.target_fetch_method == "http"
        assert stored.target_fetch_error_code is None
        assert stored.score == 77.5
        assert stored.comparison_summary == {
            "user_score": 77.5,
            "competitors_average_score": 82.4,
            "score_difference": -4.9,
            "competitors_count": 1,
            "competitors_found": 2,
            "competitors_analyzed": 1,
            "competitors_failed": 1,
        }
        assert stored.recommendations == [
            {
                "code": "TEST_REC",
                "priority": "medium",
                "message": "Test recommendation",
            }
        ]
        assert stored.warnings
        assert "Обработано 1 из 2" in stored.warnings[0]
        assert stored.updated_at is not None

    assert result == {
        "audit_id": "audit-1",
        "status": "completed_with_warnings",
        "score": 77.5,
        "competitors_count": 2,
        "recommendations_count": 1,
    }

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_process_audit_fails_when_target_fetch_fails(monkeypatch, tmp_path):
    db_path = tmp_path / "pipeline-failed.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.create_all(bind=engine)

    monkeypatch.setattr("app.tasks.SessionLocal", testing_session_local)
    monkeypatch.setattr(
        "app.tasks.fetch_page",
        lambda url, use_browser=True: {
            "status": "failed",
            "fetch_method": "browser",
            "fetch_error_code": "http_403",
            "fetch_error_message": "HTTP 403",
            "final_url": url,
            "http_status": 403,
            "html": None,
            "text": None,
        },
    )

    with testing_session_local() as db:
        audit = Audit(
            id="audit-2",
            query="seo audit",
            target_url="https://blocked.example.com",
            top_n=5,
            status="queued",
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(audit)
        db.commit()

    result = process_audit.run("audit-2")

    with testing_session_local() as db:
        stored = db.get(Audit, "audit-2")
        assert stored is not None
        assert stored.status == "failed"
        assert stored.target_fetch_status == "failed"
        assert stored.target_fetch_method == "browser"
        assert stored.target_fetch_error_code == "http_403"
        assert stored.error_message == "HTTP 403"

    assert result == {
        "audit_id": "audit-2",
        "status": "failed",
        "error_code": "http_403",
    }

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
