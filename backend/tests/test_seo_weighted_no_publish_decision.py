from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.ml.model import save_model
from app.ml.seo_weighted_no_publish_decision import (
    run_d49_no_publish_decision,
    validate_d48_keep_current_report,
)


class ConstantModel:
    def predict(self, rows):
        return [77.0 for _ in rows]


def _save_current_model(path: Path) -> None:
    save_model(
        model=ConstantModel(),
        metrics={
            "rmse": 11.973977,
            "mae": 8.113452,
            "spearman_mean": 0.415837,
            "ndcg_at_10": 0.97438,
            "top_3_hit_rate": 0.95,
            "validation_queries": 20.0,
        },
        model_path=path,
        metadata={
            "artifact_version": "dataset-v3-d37-20260501200434",
            "artifact_family": "page_quality_model",
            "dataset_version": "dataset-v3-d37",
            "model_schema_version": "v3",
            "source": "local_dataset",
            "published_at": "2026-05-01T20:04:34+00:00",
            "trained_at": "2026-05-01T19:43:01+00:00",
            "rows_count": 885,
            "queries_count": 99,
            "domains_count": 568,
        },
    )
    path.with_suffix(".metadata.json").write_text(
        json.dumps(
            {
                "artifact_version": "dataset-v3-d37-20260501200434",
                "artifact_family": "page_quality_model",
                "artifact_path": str(path),
                "model_schema_version": "v3",
                "dataset_metadata": {"dataset_version": "dataset-v3-d37"},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _d48_report(*, recommendation: str = "keep_current", product_passed: bool = False) -> dict:
    return {
        "task": "D48",
        "dataset_version": "dataset-v4",
        "decision": {
            "publish_recommendation": recommendation,
            "selected_candidate": "pointwise_catboost" if recommendation == "publish_candidate" else None,
            "reason": "no_candidate_passed_product_critical_guardrails",
        },
        "production_artifact": {"changed_by_d48": False},
        "shadow_benchmark": {
            "reference_model": {
                "metrics": {
                    "rmse": 11.973977,
                    "mae": 8.113452,
                    "spearman_mean": 0.415837,
                    "ndcg_at_10": 0.97438,
                    "top_3_hit_rate": 0.95,
                    "validation_queries": 20.0,
                }
            },
            "candidate_comparisons": [
                {
                    "candidate_name": "pointwise_catboost",
                    "model_path": "artifacts/page_quality_model.dataset-v4-seo-weighted-catboost-candidate.pkl",
                    "candidate_metrics": {
                        "rmse": 1.8421,
                        "mae": 1.231731,
                        "spearman_mean": 0.959054,
                        "ndcg_at_10": 0.998348,
                        "top_3_hit_rate": 0.65,
                        "validation_queries": 20.0,
                    },
                    "reference_metrics": {
                        "rmse": 11.973977,
                        "mae": 8.113452,
                        "spearman_mean": 0.415837,
                        "ndcg_at_10": 0.97438,
                        "top_3_hit_rate": 0.95,
                        "validation_queries": 20.0,
                    },
                    "metric_deltas": {
                        "rmse": -10.131877,
                        "mae": -6.881721,
                        "spearman_mean": 0.543217,
                        "ndcg_at_10": 0.023968,
                        "top_3_hit_rate": -0.3,
                    },
                    "guardrails": {
                        "publish_gate_passed": False,
                        "rejection_reasons": ["top_3_hit_rate_regressed"],
                    },
                }
            ],
        },
        "product_guardrails": {
            "pointwise_catboost": {
                "passed": product_passed,
                "failed_checks": [] if product_passed else ["base_shadow_publish_gate_passed"],
                "feature_importance_guardrail": {
                    "passed": False,
                    "top_feature": "word_count",
                    "top_feature_group": "supporting",
                },
                "score_response_guardrail": {
                    "passed": True,
                    "average_critical_drop": 21.3917,
                    "average_supporting_drop": 3.9823,
                },
            }
        },
        "metric_deltas_by_candidate": {"pointwise_catboost": {"top_3_hit_rate": -0.3}},
    }


def test_run_d49_no_publish_decision_writes_report_without_mutating_model(tmp_path: Path) -> None:
    model_path = tmp_path / "artifacts" / "page_quality_model.pkl"
    report_path = tmp_path / "d48-report.json"
    output_json = tmp_path / "d49" / "d49-report.json"
    output_md = tmp_path / "d49" / "d49-report.md"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    _save_current_model(model_path)
    report_path.write_text(json.dumps(_d48_report(), ensure_ascii=False), encoding="utf-8")
    before = model_path.read_bytes()

    report = run_d49_no_publish_decision(
        d48_report_path=report_path,
        production_model_path=model_path,
        report_json_path=output_json,
        report_markdown_path=output_md,
        check_results=[{"name": "backend pytest", "status": "passed"}],
        generated_at=datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
    )

    assert model_path.read_bytes() == before
    assert report["decision"]["decision"] == "keep_current"
    assert report["decision"]["publish_action"] == "no_publish"
    assert report["decision"]["production_artifact_unchanged"] is True
    assert report["candidate_decisions"][0]["publish_allowed"] is False
    assert report["candidate_decisions"][0]["product_failed_checks"] == ["base_shadow_publish_gate_passed"]
    assert report["invariants"]["runtime_dataset_version"] == "dataset-v3-d37"
    assert report["verification"]["status"] == "passed"
    assert Path(report["report_paths"]["json_path"]).exists()
    assert "# D49 No-Publish Decision" in Path(report["report_paths"]["markdown_path"]).read_text(encoding="utf-8")


def test_validate_d48_keep_current_report_rejects_publish_candidate() -> None:
    with pytest.raises(ValueError, match="keep-current"):
        validate_d48_keep_current_report(_d48_report(recommendation="publish_candidate"))


def test_validate_d48_keep_current_report_rejects_product_gate_passing_candidate() -> None:
    with pytest.raises(ValueError, match="product-critical guardrails"):
        validate_d48_keep_current_report(_d48_report(product_passed=True))
