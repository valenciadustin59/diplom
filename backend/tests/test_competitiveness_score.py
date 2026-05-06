from app.competitiveness import build_competitiveness_score
from app.competitors import (
    build_comparison_summary,
    build_competitor_candidate_limit,
    build_competitor_context_quality,
)
from app.models import AuditCompetitor
from app.tasks import _build_competitor_aggregation_result


def _competitor(score: float, *, rank: int = 1, features: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "url": f"https://competitor-{rank}.example/",
        "domain": f"competitor-{rank}.example",
        "serp_rank": rank,
        "fetch_status": "success",
        "score": score,
        "features": features or {"semantic_similarity": 0.8, "word_count": 500, "text_length_chars": 3200},
    }


def _failed_competitor(code: str = "http_403", *, rank: int = 1) -> dict[str, object]:
    return {
        "url": f"https://failed-{rank}.example/",
        "domain": f"failed-{rank}.example",
        "serp_rank": rank,
        "score": None,
        "features": None,
        "fetch_status": "failed",
        "fetch_error_code": code,
    }


def test_competitiveness_score_keeps_primary_score_without_enough_competitors():
    result = build_competitiveness_score(
        user_score=74.0,
        competitor_results=[_competitor(88.0)],
        requested_top_n=10,
    )

    assert result["context_available"] is False
    assert result["score_basis"] == "primary_page_score"
    assert result["primary_page_score"] == 74.0
    assert result["competitiveness_score"] == 74.0
    assert result["position_band"] == "not_enough_data"


def test_competitiveness_score_penalizes_clear_gap_to_top10_peers():
    result = build_competitiveness_score(
        user_score=70.0,
        competitor_results=[_competitor(85.0), _competitor(90.0), _competitor(82.0)],
        requested_top_n=10,
    )

    assert result["context_available"] is True
    assert result["score_basis"] == "competitiveness_score"
    assert result["competitiveness_score"] < result["primary_page_score"]
    assert result["competitor_average_score"] == 85.6667
    assert result["best_score_gap"] == -20.0
    assert result["position_band"] in {"behind", "far_behind"}


def test_competitiveness_score_rewards_page_that_beats_processed_peers_but_stays_bounded():
    result = build_competitiveness_score(
        user_score=93.0,
        competitor_results=[_competitor(82.0), _competitor(86.0), _competitor(78.0)],
        requested_top_n=10,
    )

    assert result["context_available"] is True
    assert result["competitiveness_score"] >= result["primary_page_score"]
    assert result["competitiveness_score"] <= 100.0
    assert result["position_band"] == "leading"
    assert result["score_percentile"] == 100.0


def test_comparison_summary_exposes_primary_and_competitiveness_scores():
    summary = build_comparison_summary(
        user_features={"semantic_similarity": 0.7},
        user_score=70.0,
        competitor_results=[_competitor(85.0), _competitor(90.0)],
        requested_top_n=10,
    )

    assert summary["primary_page_score"] == 70.0
    assert summary["competitiveness_score"] == summary["user_score"]
    assert summary["competitiveness_score"] < summary["primary_page_score"]
    assert summary["competitors_average_score"] == 87.5
    assert summary["score_difference"] == round(summary["competitiveness_score"] - 87.5, 4)
    assert summary["primary_score_difference"] == -17.5
    assert summary["score_basis"] == "competitiveness_score"
    assert summary["competitor_context_status"] == "ready"
    assert summary["competitor_context_quality"]["score_safe_to_compare"] is True


def test_comparison_summary_keeps_competitor_average_empty_without_enough_context():
    summary = build_comparison_summary(
        user_features={"semantic_similarity": 0.7},
        user_score=70.0,
        competitor_results=[_competitor(85.0)],
        requested_top_n=10,
    )

    assert summary["score_basis"] == "primary_page_score"
    assert summary["competitors_average_score"] is None
    assert summary["score_difference"] is None
    assert summary["primary_score_difference"] is None
    assert summary["competitiveness_position_band"] == "not_enough_data"
    assert summary["competitor_context_status"] == "insufficient_processed_competitors"
    assert summary["competitor_context_quality"]["score_safe_to_compare"] is False


def test_competitor_context_quality_marks_partial_but_usable_fetch_context():
    quality = build_competitor_context_quality(
        [_competitor(83.0), _competitor(79.0), _failed_competitor("browser_blocked")],
        requested_top_n=5,
    )

    assert quality["status"] == "partial_but_usable"
    assert quality["context_available"] is True
    assert quality["score_safe_to_compare"] is True
    assert quality["coverage_ratio"] == 0.4
    assert quality["fetch_error_codes"] == {"browser_blocked": 1}


def test_competitor_context_quality_blocks_fake_average_when_all_competitors_fail():
    summary = build_comparison_summary(
        user_features={"semantic_similarity": 0.7},
        user_score=70.0,
        competitor_results=[_failed_competitor("http_403"), _failed_competitor("timeout")],
        requested_top_n=10,
    )

    assert summary["competitors_average_score"] is None
    assert summary["score_difference"] is None
    assert summary["score_basis"] == "primary_page_score"
    assert summary["competitor_context_status"] == "insufficient_processed_competitors"
    assert summary["competitor_context_quality"]["fetch_error_codes"] == {"http_403": 1, "timeout": 1}


def test_competitor_candidate_limit_adds_bounded_replacement_pool():
    assert build_competitor_candidate_limit(5) == 8
    assert build_competitor_candidate_limit(10) == 15
    assert build_competitor_candidate_limit(100) == 100


def test_competitor_context_quality_v2_replaces_failed_and_low_score_candidates():
    summary = build_comparison_summary(
        user_features={"semantic_similarity": 0.7},
        user_score=70.0,
        competitor_results=[
            _failed_competitor("http_403", rank=1),
            _competitor(82.0, rank=2),
            _competitor(1.6, rank=3),
            _competitor(78.0, rank=4),
            _competitor(88.0, rank=5),
        ],
        requested_top_n=2,
    )

    quality = summary["competitor_context_quality"]
    assert quality["schema_version"] == "competitor-context-quality-v2"
    assert quality["requested_top_n"] == 2
    assert quality["collected_candidates"] == 5
    assert quality["accepted_competitors"] == 2
    assert quality["discarded_competitors"] == 2
    assert quality["replacement_attempts"] == 2
    assert quality["replacements_used"] == 1
    assert quality["discard_reasons"] == {"bot_block_suspected": 1, "score_below_minimum": 1}
    assert summary["competitor_context_status"] == "ready"
    assert summary["competitors_average_score"] == 80.0


def test_competitor_context_quality_discards_thin_successful_snapshot():
    quality = build_competitor_context_quality(
        [
            _competitor(
                66.0,
                rank=1,
                features={"semantic_similarity": 0.4, "word_count": 8, "text_length_chars": 80},
            ),
            _competitor(81.0, rank=2),
            _competitor(84.0, rank=3),
        ],
        requested_top_n=2,
    )

    assert quality["accepted_competitors"] == 2
    assert quality["discarded_competitors"] == 1
    assert quality["replacement_attempts"] == 1
    assert quality["discard_reasons"] == {"thin_content": 1}
    assert quality["status"] == "ready"


def test_competitor_aggregation_promotes_competitiveness_score_to_summary():
    result = _build_competitor_aggregation_result(
        user_features={"semantic_similarity": 0.7, "technical_seo_score": 0.6},
        user_score=70.0,
        competitors=[
            AuditCompetitor(
                id="competitor-a",
                audit_id="audit-a",
                url="https://competitor-a.example",
                domain="competitor-a.example",
                fetch_status="success",
                score=85.0,
                features={"semantic_similarity": 0.8, "technical_seo_score": 0.7},
                serp_rank=1,
                serp_page=0,
            ),
            AuditCompetitor(
                id="competitor-b",
                audit_id="audit-a",
                url="https://competitor-b.example",
                domain="competitor-b.example",
                fetch_status="success",
                score=90.0,
                features={"semantic_similarity": 0.9, "technical_seo_score": 0.8},
                serp_rank=2,
                serp_page=0,
            ),
        ],
        query_intent=None,
        requested_top_n=10,
    )

    summary = result["comparison_summary"]
    assert summary["score_basis"] == "competitiveness_score"
    assert summary["primary_page_score"] == 70.0
    assert summary["competitiveness_score"] == summary["user_score"]
    assert summary["competitiveness"]["requested_top_n"] == 10
    assert result["user_features"]["serp_relative_context_available"] == 1


def test_competitor_aggregation_marks_discarded_candidates_and_uses_only_accepted_context():
    result = _build_competitor_aggregation_result(
        user_features={"semantic_similarity": 0.7, "technical_seo_score": 0.6},
        user_score=72.0,
        competitors=[
            AuditCompetitor(
                id="competitor-failed",
                audit_id="audit-b",
                url="https://failed.example",
                domain="failed.example",
                fetch_status="failed",
                fetch_error_code="http_403",
                score=None,
                features=None,
                serp_rank=1,
                serp_page=0,
            ),
            AuditCompetitor(
                id="competitor-low",
                audit_id="audit-b",
                url="https://low.example",
                domain="low.example",
                fetch_status="success",
                score=2.5,
                features={"semantic_similarity": 0.1, "technical_seo_score": 0.1, "word_count": 20, "text_length_chars": 220},
                serp_rank=2,
                serp_page=0,
            ),
            AuditCompetitor(
                id="competitor-good-a",
                audit_id="audit-b",
                url="https://good-a.example",
                domain="good-a.example",
                fetch_status="success",
                score=86.0,
                features={"semantic_similarity": 0.8, "technical_seo_score": 0.7, "word_count": 700, "text_length_chars": 4200},
                serp_rank=3,
                serp_page=0,
            ),
            AuditCompetitor(
                id="competitor-good-b",
                audit_id="audit-b",
                url="https://good-b.example",
                domain="good-b.example",
                fetch_status="success",
                score=89.0,
                features={"semantic_similarity": 0.9, "technical_seo_score": 0.8, "word_count": 800, "text_length_chars": 5000},
                serp_rank=4,
                serp_page=0,
            ),
        ],
        query_intent=None,
        requested_top_n=2,
    )

    statuses = {item["domain"]: item["competitor_context_status"] for item in result["competitor_results"]}
    assert statuses == {
        "failed.example": "discarded",
        "low.example": "discarded",
        "good-a.example": "accepted",
        "good-b.example": "accepted",
    }
    assert result["comparison_summary"]["accepted_competitors"] == 2
    assert result["comparison_summary"]["discard_reasons"] == {
        "bot_block_suspected": 1,
        "score_below_minimum": 1,
    }
    assert result["comparison_summary"]["competitors_average_score"] == 87.5
    assert result["user_features"]["serp_relative_context_count"] == 2
