from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from app.ml.model import load_model_artifact, load_saved_model, save_model
from app.ml.no_publish_decision import sha1_file
import app.ml.v5_competitiveness_publish as d58


class ConstantModel:
    def __init__(self, value: float = 50.0) -> None:
        self.value = float(value)

    def predict(self, rows):
        return [self.value for _ in rows]


def _save_artifact(
    path: Path,
    *,
    dataset_version: str,
    artifact_version: str,
    candidate_name: str | None = None,
) -> None:
    metrics = {
        "mae": 1.2 if candidate_name else 8.0,
        "rmse": 1.8 if candidate_name else 9.0,
        "spearman_mean": 0.95 if candidate_name else 0.5,
        "ndcg_at_10": 0.998 if candidate_name else 0.98,
        "top_3_hit_rate": 0.6 if candidate_name else 0.9,
    }
    metadata = {
        "artifact_version": artifact_version,
        "artifact_family": "page_quality_model",
        "dataset_version": dataset_version,
        "model_schema_version": "v3",
        "model_type": "ConstantModel",
        "feature_columns": ["semantic_similarity", "intent_alignment_score"],
        "rows_count": 8,
        "queries_count": 2,
        "domains_count": 2,
        "metrics_summary": metrics,
    }
    if candidate_name:
        metadata.update(
            {
                "candidate_name": candidate_name,
                "candidate_family": "pointwise",
                "non_production": True,
                "runtime_enabled": False,
                "publish_decision_required": "D58",
                "feature_importance_summary": {
                    "available": True,
                    "top_features": [{"feature": "intent_alignment_score", "importance": 12.0}],
                },
            }
        )
    save_model(ConstantModel(), metrics=metrics, model_path=path, metadata=metadata)


def _shadow_report(candidate_path: Path) -> dict[str, object]:
    return {
        "reference_model": {
            "candidate_name": "reference_artifact",
            "status": "available",
            "metrics": {
                "mae": 8.0,
                "spearman_mean": 0.5,
                "ndcg_at_10": 0.98,
                "top_3_hit_rate": 0.9,
            },
        },
        "candidates": [
            {
                "candidate_name": "pointwise_catboost_v5",
                "status": "available",
                "model_path": str(candidate_path),
                "metrics": {
                    "mae": 1.2,
                    "spearman_mean": 0.95,
                    "ndcg_at_10": 0.998,
                    "top_3_hit_rate": 0.6,
                },
            }
        ],
        "candidate_comparisons": [
            {
                "candidate_name": "pointwise_catboost_v5",
                "model_path": str(candidate_path),
                "candidate_metrics": {
                    "mae": 1.2,
                    "spearman_mean": 0.95,
                    "ndcg_at_10": 0.998,
                    "top_3_hit_rate": 0.6,
                },
                "reference_metrics": {
                    "mae": 8.0,
                    "spearman_mean": 0.5,
                    "ndcg_at_10": 0.98,
                    "top_3_hit_rate": 0.9,
                },
                "metric_deltas": {
                    "mae": -6.8,
                    "spearman_mean": 0.45,
                    "ndcg_at_10": 0.018,
                    "top_3_hit_rate": -0.3,
                },
            }
        ],
    }


def test_run_d58_publishes_gate_passing_competitiveness_candidate(monkeypatch, tmp_path: Path) -> None:
    reference_path = tmp_path / "artifacts" / "page_quality_model.pkl"
    candidate_path = tmp_path / "artifacts" / "candidate.pkl"
    output_dir = tmp_path / "d58"
    report_json_path = output_dir / "report.json"
    report_md_path = output_dir / "report.md"
    versions_dir = tmp_path / "versions"
    _save_artifact(reference_path, dataset_version="dataset-v3-d37", artifact_version="current")
    _save_artifact(
        candidate_path,
        dataset_version="dataset-v5",
        artifact_version="dataset-v5-d53-pointwise_catboost_v5",
        candidate_name="pointwise_catboost_v5",
    )
    before_sha1 = sha1_file(reference_path)
    monkeypatch.setattr(d58, "build_d54_validation_rows", lambda: ([{"query": "a"}], [{"query": "b"}], {}))
    monkeypatch.setattr(d58, "build_d54_shadow_benchmark", lambda **kwargs: _shadow_report(candidate_path))
    monkeypatch.setattr(
        d58,
        "build_d54_product_guardrails",
        lambda **kwargs: {
            "pointwise_catboost_v5": {
                "passed": True,
                "failed_checks": [],
                "serp_alignment_diagnostics": {"blocking": False, "warnings": ["top_3_hit_rate_below_reference"]},
                "page_quality_checks": {"mae_comparable_or_better": True},
                "product_guardrail_checks": {"feature_dominance_guardrail_passed": True},
                "recommendation_consistency": {"passed": True},
            }
        },
    )
    monkeypatch.setattr("app.ml.controlled_publish.VERSIONED_ARTIFACTS_DIR", versions_dir)

    report = d58.run_d58_competitiveness_publish(
        reference_model_path=reference_path,
        candidate_model_paths=(candidate_path,),
        output_dir=output_dir,
        report_json_path=report_json_path,
        report_markdown_path=report_md_path,
        check_results=[{"name": "pytest", "status": "passed"}],
        generated_at=datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
    )

    published = load_model_artifact(reference_path)
    published_raw = load_saved_model(reference_path)
    assert sha1_file(reference_path) != before_sha1
    assert published["dataset_version"] == "dataset-v5"
    assert published_raw["candidate_name"] == "pointwise_catboost_v5"
    assert published_raw["runtime_enabled"] is True
    assert report["decision"]["decision"] == "publish_candidate"
    assert report["production_artifact"]["changed_by_d58"] is True
    assert report["rollback_reference"]["rollback_model_sha1"] == before_sha1
    assert Path(report["publish_result"]["versioned_model_path"]).exists()
    assert json.loads(report_json_path.read_text(encoding="utf-8"))["task"] == "D58"
    assert "# D58 Competitiveness Scorecard" in report_md_path.read_text(encoding="utf-8")


def test_run_d58_keeps_current_when_scorecard_fails(monkeypatch, tmp_path: Path) -> None:
    reference_path = tmp_path / "artifacts" / "page_quality_model.pkl"
    candidate_path = tmp_path / "artifacts" / "candidate.pkl"
    output_dir = tmp_path / "d58"
    _save_artifact(reference_path, dataset_version="dataset-v3-d37", artifact_version="current")
    _save_artifact(
        candidate_path,
        dataset_version="dataset-v5",
        artifact_version="dataset-v5-d53-pointwise_catboost_v5",
        candidate_name="pointwise_catboost_v5",
    )
    before = reference_path.read_bytes()
    monkeypatch.setattr(d58, "build_d54_validation_rows", lambda: ([{"query": "a"}], [{"query": "b"}], {}))
    monkeypatch.setattr(d58, "build_d54_shadow_benchmark", lambda **kwargs: _shadow_report(candidate_path))
    monkeypatch.setattr(
        d58,
        "build_d54_product_guardrails",
        lambda **kwargs: {"pointwise_catboost_v5": {"passed": False, "failed_checks": ["feature_dominance_guardrail_passed"]}},
    )

    report = d58.run_d58_competitiveness_publish(
        reference_model_path=reference_path,
        candidate_model_paths=(candidate_path,),
        output_dir=output_dir,
        report_json_path=output_dir / "report.json",
        report_markdown_path=output_dir / "report.md",
    )

    assert reference_path.read_bytes() == before
    assert report["decision"]["decision"] == "keep_current"
    assert report["publish_result"] is None
    assert report["production_artifact"]["changed_by_d58"] is False
