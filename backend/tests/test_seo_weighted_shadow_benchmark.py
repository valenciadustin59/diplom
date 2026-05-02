from __future__ import annotations

from app.ml.seo_weighted_shadow_benchmark import _feature_importance_guardrail, build_d48_decision


def test_feature_importance_guardrail_rejects_supporting_top_feature() -> None:
    candidate = {
        "feature_importance_summary": {
            "available": True,
            "top_features": [
                {"feature": "word_count", "importance": 12.0},
                {"feature": "unique_word_count", "importance": 5.0},
                {"feature": "page_indexable", "importance": 4.0},
                {"feature": "canonical_signal_score", "importance": 3.0},
            ],
        }
    }

    guardrail = _feature_importance_guardrail(candidate)

    assert guardrail["passed"] is False
    assert guardrail["top_feature"] == "word_count"
    assert guardrail["top_feature_group"] == "supporting"
    assert "top_feature_is_not_supporting" in guardrail["failed_checks"]


def test_d48_decision_keeps_current_when_no_candidate_passes_product_gate() -> None:
    shadow_report = {
        "reference_model": {
            "candidate_name": "reference",
            "status": "available",
            "metrics": {
                "spearman_mean": 0.4,
                "ndcg_at_10": 0.97,
                "top_3_hit_rate": 0.95,
                "mae": 8.0,
            },
        },
        "candidates": [
            {
                "candidate_name": "pointwise_catboost",
                "status": "available",
                "metrics": {
                    "spearman_mean": 0.95,
                    "ndcg_at_10": 0.99,
                    "top_3_hit_rate": 0.65,
                    "mae": 1.2,
                },
            }
        ],
    }

    decision = build_d48_decision(
        shadow_report=shadow_report,
        product_guardrails={"pointwise_catboost": {"passed": False}},
    )

    assert decision["publish_recommendation"] == "keep_current"
    assert decision["selected_candidate"] is None
    assert decision["reason"] == "no_candidate_passed_product_critical_guardrails"


def test_d48_decision_can_select_product_gate_passing_candidate() -> None:
    shadow_report = {
        "reference_model": {
            "candidate_name": "reference",
            "status": "available",
            "metrics": {
                "spearman_mean": 0.4,
                "ndcg_at_10": 0.97,
                "top_3_hit_rate": 0.9,
                "mae": 8.0,
            },
        },
        "candidates": [
            {
                "candidate_name": "pointwise_catboost",
                "status": "available",
                "metrics": {
                    "spearman_mean": 0.95,
                    "ndcg_at_10": 0.99,
                    "top_3_hit_rate": 0.95,
                    "mae": 1.2,
                },
            }
        ],
    }

    decision = build_d48_decision(
        shadow_report=shadow_report,
        product_guardrails={"pointwise_catboost": {"passed": True}},
    )

    assert decision["publish_recommendation"] == "publish_candidate"
    assert decision["selected_candidate"] == "pointwise_catboost"
