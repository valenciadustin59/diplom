from __future__ import annotations

from app.ml.competitiveness_release_policy import (
    COMPETITIVENESS_RELEASE_POLICY_VERSION,
    build_competitiveness_release_scorecard,
    build_recommendation_consistency_contract,
    competitiveness_candidate_sort_key,
    split_shadow_rejection_reasons,
)


def _passing_auxiliary_guardrails() -> dict[str, dict[str, object]]:
    return {
        "feature_dominance": {"passed": True},
        "score_response": {"passed": True},
        "prediction_bounds": {"passed": True},
    }


def test_competitiveness_scorecard_treats_top3_regression_as_diagnostic() -> None:
    auxiliary = _passing_auxiliary_guardrails()

    scorecard = build_competitiveness_release_scorecard(
        candidate_name="pointwise_catboost_v5",
        candidate_metrics={
            "mae": 1.2,
            "spearman_mean": 0.95,
            "ndcg_at_10": 0.998,
            "top_3_hit_rate": 0.6,
        },
        reference_metrics={
            "mae": 8.0,
            "spearman_mean": 0.51,
            "ndcg_at_10": 0.981,
            "top_3_hit_rate": 0.9,
        },
        base_guardrails={
            "publish_gate_passed": False,
            "checks": {"candidate_available": True},
            "rejection_reasons": ["top_3_hit_rate_regressed"],
        },
        **auxiliary,
    )

    assert scorecard["policy_version"] == COMPETITIVENESS_RELEASE_POLICY_VERSION
    assert scorecard["passed"] is True
    assert scorecard["failed_checks"] == []
    assert scorecard["metric_groups"]["page_quality_competitiveness"]["blocking"] is True
    assert scorecard["metric_groups"]["serp_alignment"]["blocking"] is False
    assert scorecard["base_page_quality_rejection_reasons"] == []
    assert scorecard["base_serp_alignment_rejection_reasons"] == ["top_3_hit_rate_regressed"]
    assert scorecard["serp_alignment_diagnostics"]["warnings"] == [
        "top_3_hit_rate_below_diagnostic_floor",
        "top_3_hit_rate_below_reference",
    ]


def test_competitiveness_scorecard_still_blocks_page_quality_regression() -> None:
    auxiliary = _passing_auxiliary_guardrails()

    scorecard = build_competitiveness_release_scorecard(
        candidate_name="ranking_aware_catboost_v5",
        candidate_metrics={
            "mae": 14.5,
            "spearman_mean": 0.95,
            "ndcg_at_10": 0.998,
            "top_3_hit_rate": 1.0,
        },
        reference_metrics={
            "mae": 8.0,
            "spearman_mean": 0.51,
            "ndcg_at_10": 0.981,
            "top_3_hit_rate": 0.9,
        },
        base_guardrails={"publish_gate_passed": True, "checks": {"candidate_available": True}},
        **auxiliary,
    )

    assert scorecard["passed"] is False
    assert scorecard["failed_checks"] == ["mae_comparable_or_better"]
    assert scorecard["metric_groups"]["serp_alignment"]["warnings"] == []


def test_recommendation_consistency_failed_evidence_blocks_release() -> None:
    auxiliary = _passing_auxiliary_guardrails()
    evidence = build_recommendation_consistency_contract(
        candidate_name="pointwise_catboost_v5",
        evidence={"status": "failed", "passed": False, "reason": "priority_inversion"},
    )

    scorecard = build_competitiveness_release_scorecard(
        candidate_name="pointwise_catboost_v5",
        candidate_metrics={"mae": 1.2, "spearman_mean": 0.95, "ndcg_at_10": 0.998},
        reference_metrics={"mae": 8.0, "spearman_mean": 0.51, "ndcg_at_10": 0.981},
        base_guardrails={"publish_gate_passed": True, "checks": {"candidate_available": True}},
        recommendation_consistency=evidence,
        **auxiliary,
    )

    assert scorecard["passed"] is False
    assert "recommendation_consistency_not_failed" in scorecard["failed_checks"]
    assert scorecard["recommendation_consistency"]["status"] == "failed"


def test_competitiveness_sort_key_excludes_serp_alignment_metric() -> None:
    current = {"metrics": {"spearman_mean": 0.51, "ndcg_at_10": 0.981, "mae": 8.0, "top_3_hit_rate": 0.9}}
    lower_top3_better_quality = {
        "metrics": {"spearman_mean": 0.95, "ndcg_at_10": 0.998, "mae": 1.2, "top_3_hit_rate": 0.6}
    }

    assert competitiveness_candidate_sort_key(lower_top3_better_quality) > competitiveness_candidate_sort_key(current)


def test_split_shadow_rejection_reasons_separates_serp_alignment() -> None:
    reasons = split_shadow_rejection_reasons(["top_3_hit_rate_regressed", "mae_not_comparable"])

    assert reasons["serp_alignment"] == ["top_3_hit_rate_regressed"]
    assert reasons["page_quality_competitiveness"] == ["mae_not_comparable"]
