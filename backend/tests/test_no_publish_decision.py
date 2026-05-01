import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.ml.model import save_model
from app.ml.no_publish_decision import (
    build_runtime_smoke_verification,
    run_no_publish_decision,
    sha1_file,
    validate_keep_reference_shadow_report,
)


class ConstantModel:
    def predict(self, rows):
        return [50.0 for _ in rows]


def _save_reference_artifact(model_path: Path) -> None:
    artifact_version = "reference-v1"
    save_model(
        model=ConstantModel(),
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
            "source": "local_dataset",
            "published_at": "2026-04-21T17:49:01.452372+00:00",
            "trained_at": "2026-04-21T17:49:03.706834+00:00",
            "rows_count": 436,
            "queries_count": 47,
            "domains_count": 385,
        },
    )
    metadata_path = model_path.with_suffix(".metadata.json")
    metadata_path.write_text(
        json.dumps(
            {
                "artifact_version": artifact_version,
                "artifact_family": "page_quality_model",
                "artifact_path": str(model_path),
                "model_schema_version": "v1",
            }
        ),
        encoding="utf-8",
    )
    versioned_dir = model_path.parent / "versions"
    versioned_dir.mkdir(parents=True, exist_ok=True)
    versioned_model_path = versioned_dir / f"{model_path.stem}--{artifact_version}{model_path.suffix}"
    shutil.copy2(model_path, versioned_model_path)
    shutil.copy2(metadata_path, versioned_model_path.with_suffix(".metadata.json"))


def _shadow_report(*, recommendation: str = "keep_reference", gate_passed: bool = False) -> dict:
    return {
        "generated_at": "2026-05-01T18:00:00+00:00",
        "dataset_version": "dataset-v2",
        "rows_count": 885,
        "queries_count": 99,
        "decision": {
            "publish_recommendation": recommendation,
            "selected_candidate": "pointwise_catboost" if recommendation == "publish_candidate" else None,
            "reason": "no_candidate_passed_all_publish_gates",
        },
        "reference_model": {
            "metrics": {
                "rmse": 27.980756,
                "mae": 23.858757,
                "spearman_mean": 0.153604,
                "ndcg_at_10": 0.909302,
                "top_3_hit_rate": 0.95,
                "validation_queries": 20.0,
            }
        },
        "candidates": [
            {
                "candidate_name": "pointwise_catboost",
                "candidate_family": "pointwise",
                "status": "available",
                "model_path": "artifacts/page_quality_model.dataset-v2-expert-catboost-candidate.pkl",
                "model_info": {
                    "artifact_version": "dataset-v2-pointwise_catboost",
                    "dataset_version": "dataset-v2",
                },
                "model_schema_version": "v2",
                "model_type": "CatBoostRegressor",
                "feature_count": 108,
            }
        ],
        "candidate_comparisons": [
            {
                "candidate_name": "pointwise_catboost",
                "candidate_family": "pointwise",
                "model_path": "artifacts/page_quality_model.dataset-v2-expert-catboost-candidate.pkl",
                "candidate_metrics": {
                    "rmse": 14.980677,
                    "mae": 12.003497,
                    "spearman_mean": 0.404524,
                    "ndcg_at_10": 0.947887,
                    "top_3_hit_rate": 0.8,
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
                    "spearman_mean": 0.25092,
                    "ndcg_at_10": 0.038585,
                    "top_3_hit_rate": -0.15,
                    "rmse": -13.000079,
                    "mae": -11.85526,
                },
                "guardrails": {
                    "publish_gate_passed": gate_passed,
                    "checks": {
                        "candidate_available": True,
                        "ndcg_at_10_not_worse": True,
                        "top_3_hit_rate_not_worse": False,
                    },
                    "rejection_reasons": [] if gate_passed else ["top_3_hit_rate_regressed"],
                    "thresholds": {"absolute_error_tolerance_ratio": 0.05},
                },
            }
        ],
        "best_candidate_by_ranking_metrics": {"candidate_name": "pointwise_catboost"},
        "smoke_explainability": {
            "requested_queries_count": 4,
            "covered_queries_count": 4,
            "exact_match_queries_count": 3,
            "fallback_match_queries_count": 1,
            "missing_queries_count": 0,
        },
        "explainability_sensibility": {"passed": True},
    }


def _smoke_summary(*, dataset_version: str = "ru_commercial_dataset-20260421-primary", schema: str = "v1") -> dict:
    return {
        "generated_at": "2026-05-01T19:00:00.000Z",
        "audit_id": "audit-1",
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


def test_run_no_publish_decision_writes_keep_reference_report_without_mutating_model(tmp_path):
    model_path = tmp_path / "artifacts" / "page_quality_model.pkl"
    shadow_report_path = tmp_path / "d35-shadow-report.json"
    smoke_summary_path = tmp_path / "d36-smoke-summary.json"
    output_dir = tmp_path / "d36"
    _save_reference_artifact(model_path)
    shadow_report_path.write_text(json.dumps(_shadow_report()), encoding="utf-8")
    smoke_summary_path.write_text(json.dumps(_smoke_summary()), encoding="utf-8")
    before_sha1 = sha1_file(model_path)
    before_bytes = model_path.read_bytes()

    report = run_no_publish_decision(
        shadow_report_path=shadow_report_path,
        production_model_path=model_path,
        output_dir=output_dir,
        check_results=[
            {"name": "npm run build", "status": "passed"},
            {"name": "npm run site:check", "status": "passed"},
            {"name": "backend pytest", "status": "passed"},
        ],
        runtime_smoke_summary_path=smoke_summary_path,
        generated_at=datetime(2026, 5, 1, 19, 30, tzinfo=UTC),
    )

    assert model_path.read_bytes() == before_bytes
    assert sha1_file(model_path) == before_sha1
    assert report["decision"]["decision"] == "keep_reference"
    assert report["decision"]["publish_action"] == "no_publish"
    assert report["decision"]["production_artifact_unchanged"] is True
    assert report["candidate_rejections"][0]["rejection_reasons"] == ["top_3_hit_rate_regressed"]
    assert report["rollback_reference"]["versioned_reference_model_available"] is True
    assert report["verification"]["status"] == "passed"
    assert report["verification"]["runtime_smoke"]["status"] == "passed"
    assert report["invariants"]["runtime_dataset_version"] == "ru_commercial_dataset-20260421-primary"
    assert report["invariants"]["runtime_model_schema_version"] == "v1"

    saved_report = json.loads(Path(report["report_paths"]["json_path"]).read_text(encoding="utf-8"))
    markdown_report = Path(report["report_paths"]["markdown_path"]).read_text(encoding="utf-8")
    assert saved_report["decision"]["selected_candidate"] is None
    assert saved_report["decision"]["selected_runtime_artifact"]["model_sha1"] == before_sha1
    assert "# D36 Keep-Reference Decision" in markdown_report


def test_validate_keep_reference_shadow_report_rejects_publish_recommendation():
    with pytest.raises(ValueError, match="keep_reference"):
        validate_keep_reference_shadow_report(_shadow_report(recommendation="publish_candidate"))


def test_validate_keep_reference_shadow_report_rejects_gate_passing_candidate():
    with pytest.raises(ValueError, match="pass all publish gates"):
        validate_keep_reference_shadow_report(_shadow_report(gate_passed=True))


def test_runtime_smoke_verification_detects_selected_model_mismatch(tmp_path):
    smoke_path = tmp_path / "smoke.json"
    smoke_path.write_text(json.dumps(_smoke_summary(dataset_version="dataset-v2", schema="v2")), encoding="utf-8")

    verification = build_runtime_smoke_verification(
        smoke_path,
        expected_dataset_version="ru_commercial_dataset-20260421-primary",
        expected_model_schema_version="v1",
    )

    assert verification["status"] == "failed"
    assert "runtime_dataset_version_mismatch" in verification["failures"]
    assert "runtime_model_schema_version_mismatch" in verification["failures"]
