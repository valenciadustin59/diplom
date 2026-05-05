from app.competitiveness import build_competitiveness_score
from app.competitors import build_comparison_summary
from app.models import AuditCompetitor
from app.tasks import _build_competitor_aggregation_result


def _competitor(score: float) -> dict[str, object]:
    return {
        "score": score,
        "features": {"semantic_similarity": 0.8},
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
