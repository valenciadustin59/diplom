import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.ml.controlled_publish import (
    run_controlled_publish,
    update_controlled_publish_verification,
    validate_publish_shadow_report,
)
from app.ml.model import load_model_artifact, save_model
from app.ml.model_schema import get_model_feature_schema
from app.ml.no_publish_decision import sha1_file


class ConstantModel:
    def __init__(self, value: float):
        self.value = value

    def predict(self, rows):
        return [self.value for _ in rows]


V1_COLUMNS = get_model_feature_schema("v1").feature_columns
V3_COLUMNS = get_model_feature_schema("v3").feature_columns


def _write_public_metadata(model_path: Path, *, artifact_version: str, schema: str) -> None:
    model_path.with_suffix(".metadata.json").write_text(
        json.dumps(
            {
                "artifact_version": artifact_version,
                "artifact_family": model_path.stem,
                "artifact_path": str(model_path),
                "model_schema_version": schema,
            }
        ),
        encoding="utf-8",
    )


def _save_reference_artifact(model_path: Path) -> None:
    artifact_version = "reference-v1"
    save_model(
        model=ConstantModel(45.0),
        metrics={
            "rmse": 27.980756,
            "mae": 23.858757,
            "spearman_mean": 0.153604,
            "ndcg_at_10": 0.909302,
            "top_3_hit_rate": 0.95,
            "validation_queries": 20.0,
        },
        model_path=model_path,
        metadata={
            "artifact_version": artifact_version,
            "artifact_family": "page_quality_model",
            "dataset_version": "ru_commercial_dataset-20260421-primary",
            "model_schema_version": "v1",
            "feature_columns": list(V1_COLUMNS),
            "source": "local_dataset",
            "published_at": "2026-04-21T17:49:01.452372+00:00",
            "trained_at": "2026-04-21T17:49:03.706834+00:00",
            "rows_count": 436,
            "queries_count": 47,
            "domains_count": 385,
        },
    )
    _write_public_metadata(model_path, artifact_version=artifact_version, schema="v1")
    versioned_dir = model_path.parent / "versions"
    versioned_dir.mkdir(parents=True, exist_ok=True)
    versioned_model_path = versioned_dir / f"{model_path.stem}--{artifact_version}{model_path.suffix}"
    shutil.copy2(model_path, versioned_model_path)
    shutil.copy2(model_path.with_suffix(".metadata.json"), versioned_model_path.with_suffix(".metadata.json"))


def _save_candidate_artifact(candidate_path: Path) -> None:
    save_model(
        model=ConstantModel(88.0),
        metrics={
            "rmse": 14.865537,
            "mae": 11.774165,
            "spearman_mean": 0.421894,
            "ndcg_at_10": 0.945929,
            "top_3_hit_rate": 0.95,
            "validation_queries": 20.0,
            "split_mode": "group_by_query",
        },
        model_path=candidate_path,
        metadata={
            "artifact_version": "dataset-v3-d37-pointwise_catboost",
            "artifact_family": "page_quality_model.dataset-v3-d37-catboost-candidate",
            "dataset_version": "dataset-v3-d37",
            "model_schema_version": "v3",
            "feature_columns": list(V3_COLUMNS),
            "source": "local_dataset",
            "model_type": "CatBoostRegressor",
            "candidate_name": "pointwise_catboost",
            "candidate_family": "pointwise",
            "trained_at": "2026-05-01T19:43:01.259677+00:00",
            "rows_count": 885,
            "queries_count": 99,
            "domains_count": 568,
            "feature_importance_summary": {
                "available": True,
                "top_features": [{"feature": "intent_alignment_score", "importance": 3.0}],
            },
        },
    )


def _shadow_report(candidate_path: Path, *, recommendation: str = "publish_candidate", gate_passed: bool = True) -> dict:
    return {
        "generated_at": "2026-05-01T19:43:28.520794+00:00",
        "dataset_version": "dataset-v3-d37",
        "rows_count": 885,
        "queries_count": 99,
        "decision": {
            "publish_recommendation": recommendation,
            "selected_candidate": "pointwise_catboost" if recommendation == "publish_candidate" else None,
            "reason": "candidate_passed_all_publish_gates_and_outperformed_reference",
        },
        "reference_model": {
            "metrics": {
                "rmse": 27.980756,
                "mae": 23.858757,
                "spearman_mean": 0.153604,
                "ndcg_at_10": 0.909302,
                "top_3_hit_rate": 0.95,
            }
        },
        "candidates": [
            {
                "candidate_name": "pointwise_catboost",
                "candidate_family": "pointwise",
                "status": "available",
                "model_path": str(candidate_path),
                "model_schema_version": "v3",
                "model_type": "CatBoostRegressor",
                "feature_count": len(V3_COLUMNS),
            }
        ],
        "candidate_comparisons": [
            {
                "candidate_name": "pointwise_catboost",
                "candidate_family": "pointwise",
                "model_path": str(candidate_path),
                "candidate_metrics": {
                    "rmse": 14.865537,
                    "mae": 11.774165,
                    "spearman_mean": 0.421894,
                    "ndcg_at_10": 0.945929,
                    "top_3_hit_rate": 0.95,
                    "validation_queries": 20.0,
                },
                "reference_metrics": {
                    "rmse": 27.980756,
                    "mae": 23.858757,
                    "spearman_mean": 0.153604,
                    "ndcg_at_10": 0.909302,
                    "top_3_hit_rate": 0.95,
                    "validation_queries": 20.0,
                },
                "metric_deltas": {
                    "spearman_mean": 0.26829,
                    "ndcg_at_10": 0.036627,
                    "top_3_hit_rate": 0.0,
                    "rmse": -13.115219,
                    "mae": -12.084592,
                },
                "guardrails": {
                    "publish_gate_passed": gate_passed,
                    "checks": {
                        "candidate_available": True,
                        "ndcg_at_10_not_worse": True,
                        "top_3_hit_rate_not_worse": True,
                        "mae_not_worse": True,
                    },
                    "rejection_reasons": [] if gate_passed else ["top_3_hit_rate_regressed"],
                },
            }
        ],
        "smoke_explainability": {
            "requested_queries_count": 4,
            "covered_queries_count": 4,
            "exact_match_queries_count": 3,
            "fallback_match_queries_count": 1,
            "missing_queries_count": 0,
            "model_guardrails": {"pointwise_catboost": {"passed": True}},
        },
        "explainability_sensibility": {"passed": True},
    }


def _smoke_summary(*, dataset_version: str = "dataset-v3-d37", schema: str = "v3") -> dict:
    return {
        "generated_at": "2026-05-02T01:00:00.000Z",
        "audit_id": "audit-d38",
        "health_ready_status": "ready",
        "ready_worker_count": 4,
        "ready_missing_queues": [],
        "audit_status": "completed",
        "competitors_found": 2,
        "competitors_analyzed": 2,
        "competitors_failed": 0,
        "recommendation_total": 13,
        "model_info": {"dataset_version": dataset_version, "model_schema_version": schema},
        "frontend_routes": {"/": {"status": 200, "has_root": True, "has_vite_entry": True}},
    }


def test_run_controlled_publish_replaces_alias_and_preserves_rollback(monkeypatch, tmp_path):
    model_path = tmp_path / "artifacts" / "page_quality_model.pkl"
    candidate_path = tmp_path / "artifacts" / "page_quality_model.dataset-v3-d37-catboost-candidate.pkl"
    shadow_report_path = tmp_path / "shadow-report.json"
    output_dir = tmp_path / "d38"
    versions_dir = tmp_path / "versions"
    _save_reference_artifact(model_path)
    _save_candidate_artifact(candidate_path)
    shadow_report_path.write_text(json.dumps(_shadow_report(candidate_path)), encoding="utf-8")
    before_sha1 = sha1_file(model_path)
    monkeypatch.setattr("app.ml.controlled_publish.VERSIONED_ARTIFACTS_DIR", versions_dir)

    report = run_controlled_publish(
        shadow_report_path=shadow_report_path,
        candidate_model_path=candidate_path,
        production_model_path=model_path,
        output_dir=output_dir,
        check_results=[{"name": "backend pytest", "status": "passed"}],
        generated_at=datetime(2026, 5, 2, 1, 0, tzinfo=UTC),
    )

    published_artifact = load_model_artifact(model_path)
    assert published_artifact["dataset_version"] == "dataset-v3-d37"
    assert published_artifact["model_schema_version"] == "v3"
    assert published_artifact["model_type"] == "CatBoostRegressor"
    assert len(published_artifact["feature_columns"]) == len(V3_COLUMNS)
    assert sha1_file(model_path) != before_sha1
    assert Path(report["rollback_reference"]["rollback_model_path"]).exists()
    assert report["rollback_reference"]["rollback_model_sha1"] == before_sha1
    assert Path(report["publish_result"]["versioned_model_path"]).exists()
    assert report["decision"]["production_artifact_changed"] is True
    assert report["verification"]["status"] == "pending"
    assert "# D38 Controlled Publish Decision" in Path(report["report_paths"]["markdown_path"]).read_text(encoding="utf-8")


def test_update_controlled_publish_verification_marks_runtime_smoke_passed(monkeypatch, tmp_path):
    model_path = tmp_path / "artifacts" / "page_quality_model.pkl"
    candidate_path = tmp_path / "artifacts" / "page_quality_model.dataset-v3-d37-catboost-candidate.pkl"
    shadow_report_path = tmp_path / "shadow-report.json"
    smoke_summary_path = tmp_path / "d38-smoke-summary.json"
    output_dir = tmp_path / "d38"
    _save_reference_artifact(model_path)
    _save_candidate_artifact(candidate_path)
    shadow_report_path.write_text(json.dumps(_shadow_report(candidate_path)), encoding="utf-8")
    smoke_summary_path.write_text(json.dumps(_smoke_summary()), encoding="utf-8")
    monkeypatch.setattr("app.ml.controlled_publish.VERSIONED_ARTIFACTS_DIR", tmp_path / "versions")
    report = run_controlled_publish(
        shadow_report_path=shadow_report_path,
        candidate_model_path=candidate_path,
        production_model_path=model_path,
        output_dir=output_dir,
    )

    updated_report = update_controlled_publish_verification(
        report_path=report["report_paths"]["json_path"],
        runtime_smoke_summary_path=smoke_summary_path,
        check_results=[{"name": "backend pytest", "status": "passed"}],
    )

    assert updated_report["verification"]["status"] == "passed"
    assert updated_report["verification"]["runtime_smoke"]["status"] == "passed"


def test_validate_publish_shadow_report_rejects_non_publish_decision():
    with pytest.raises(ValueError, match="publish_candidate"):
        validate_publish_shadow_report(_shadow_report(Path("candidate.pkl"), recommendation="keep_reference"))


def test_validate_publish_shadow_report_rejects_failed_gate():
    with pytest.raises(ValueError, match="publish guardrails"):
        validate_publish_shadow_report(_shadow_report(Path("candidate.pkl"), gate_passed=False))
