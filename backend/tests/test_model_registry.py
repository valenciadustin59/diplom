import hashlib
import json
from pathlib import Path

from app.ml.publish import build_artifact_metadata_path
from app.model_registry import build_model_registry_payload


def _write_bytes(path: Path, payload: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def test_model_registry_discovers_current_and_rollback_evidence(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    versions_dir = artifacts_dir / "versions"
    evidence_dir = artifacts_dir / "ranking-benchmarks"
    model_path = _write_bytes(artifacts_dir / "page_quality_model.pkl", b"catboost-v3")
    current_version_path = _write_bytes(
        versions_dir / "page_quality_model--dataset-v3-d37-20260501200434.pkl",
        b"catboost-v3",
    )
    rollback_path = _write_bytes(
        versions_dir / "page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl",
        b"rf-v1",
    )
    rollback_metadata_path = build_artifact_metadata_path(rollback_path)
    _write_json(
        rollback_metadata_path,
        {
            "artifact_version": "ru_commercial_dataset-20260421-primary-20260421174901",
            "artifact_family": "page_quality_model",
            "model_type": "RandomForestRegressor",
            "source": "local_dataset",
            "feature_count": 59,
            "published_at": "2026-04-21T17:49:01+00:00",
            "dataset_metadata": {
                "dataset_version": "ru_commercial_dataset-20260421-primary",
                "rows_count": 436,
                "queries_count": 47,
                "domains_count": 385,
            },
            "metrics_summary": {"top_3_hit_rate": 0.9, "ndcg_at_10": 0.844962},
        },
    )
    _write_json(
        build_artifact_metadata_path(current_version_path),
        {
            "artifact_version": "dataset-v3-d37-20260501200434",
            "artifact_family": "page_quality_model",
            "model_type": "CatBoostRegressor",
            "model_schema_version": "v3",
            "source": "local_dataset",
            "feature_count": 148,
            "published_at": "2026-05-01T20:04:34+00:00",
            "dataset_metadata": {"dataset_version": "dataset-v3-d37", "rows_count": 885, "queries_count": 99},
        },
    )
    _write_json(
        build_artifact_metadata_path(model_path),
        {
            "artifact_version": "dataset-v3-d37-20260501200434",
            "artifact_family": "page_quality_model",
            "model_type": "CatBoostRegressor",
            "model_schema_version": "v3",
            "source": "local_dataset",
            "feature_count": 148,
            "published_at": "2026-05-01T20:04:34+00:00",
            "dataset_metadata": {"dataset_version": "dataset-v3-d37", "rows_count": 885, "queries_count": 99},
            "shadow_report_path": "artifacts/ranking-benchmarks/dataset-v3-d37-shadow/shadow-benchmark-guardrails-report.json",
            "shadow_decision": {
                "publish_recommendation": "publish_candidate",
                "selected_candidate": "pointwise_catboost",
                "reason": "candidate_passed_all_publish_gates_and_outperformed_reference",
            },
            "rollback_reference": {
                "rollback_model_path": str(rollback_path),
                "rollback_model_sha1": _sha1(rollback_path),
                "rollback_metadata_path": str(rollback_metadata_path),
                "rollback_metadata_sha1": _sha1(rollback_metadata_path),
            },
        },
    )
    _write_json(
        evidence_dir / "dataset-v3-d37-d38" / "controlled-publish-report.json",
        {
            "decision": {
                "decision": "publish_candidate",
                "publish_action": "controlled_publish",
                "selected_candidate": "pointwise_catboost",
                "reason": "candidate_passed_all_publish_gates_and_outperformed_reference",
                "production_artifact_sha1_before": _sha1(rollback_path),
                "production_artifact_sha1_after": _sha1(model_path),
            },
            "shadow_evidence": {
                "shadow_report_path": "artifacts/ranking-benchmarks/dataset-v3-d37-shadow/shadow-benchmark-guardrails-report.json",
            },
            "production_before": {
                "model_sha1": _sha1(rollback_path),
                "model_info": {
                    "artifact_version": "ru_commercial_dataset-20260421-primary-20260421174901",
                    "model_type": "RandomForestRegressor",
                    "model_schema_version": "v1",
                    "dataset_version": "ru_commercial_dataset-20260421-primary",
                    "feature_count": 59,
                    "rows_count": 436,
                    "queries_count": 47,
                },
            },
            "rollback_reference": {"rollback_model_sha1": _sha1(rollback_path)},
            "publish_result": {
                "artifact_version": "dataset-v3-d37-20260501200434",
                "published_model_sha1": _sha1(model_path),
                "versioned_model_sha1": _sha1(current_version_path),
                "model_info": {
                    "artifact_version": "dataset-v3-d37-20260501200434",
                    "model_type": "CatBoostRegressor",
                    "model_schema_version": "v3",
                    "dataset_version": "dataset-v3-d37",
                    "feature_count": 148,
                },
            },
            "verification": {
                "runtime_smoke": {
                    "status": "passed",
                    "summary_path": "..\\output\\runtime-smoke\\d38-smoke-summary.json",
                },
            },
            "report_paths": {
                "json_path": "artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.json",
                "markdown_path": "artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.md",
            },
        },
    )
    _write_json(
        evidence_dir / "dataset-v3-d41" / "golden-replay-report.json",
        {
            "model_status": {
                "artifact_sha1": _sha1(model_path),
                "model": {
                    "artifact_version": "dataset-v3-d37-20260501200434",
                    "model_type": "CatBoostRegressor",
                    "model_schema_version": "v3",
                },
            },
            "rollback_reference": {
                "model_sha1": _sha1(rollback_path),
                "artifact_version": "ru_commercial_dataset-20260421-primary-20260421174901",
            },
            "decision": {"status": "passed"},
            "report_paths": {
                "json_path": "artifacts/ranking-benchmarks/dataset-v3-d41/golden-replay-report.json",
                "markdown_path": "artifacts/ranking-benchmarks/dataset-v3-d41/golden-replay-report.md",
            },
        },
    )

    payload = build_model_registry_payload(
        model_path=model_path,
        versions_dir=versions_dir,
        evidence_dir=evidence_dir,
        checked_at="2026-05-02T00:00:00+00:00",
    )

    assert payload["status"] == "ok"
    assert payload["summary"] == {
        "record_count": 2,
        "current_count": 1,
        "rollback_count": 1,
        "archived_count": 0,
        "warning_count": 0,
    }
    assert [record["role"] for record in payload["records"]] == ["current", "rollback"]
    current, rollback = payload["records"]
    assert current["model"]["model_type"] == "CatBoostRegressor"
    assert current["model"]["model_schema_version"] == "v3"
    assert current["dataset"]["dataset_version"] == "dataset-v3-d37"
    assert current["evidence"]["publish_report_path"].endswith("controlled-publish-report.json")
    assert current["evidence"]["smoke_summary_path"] == "../output/runtime-smoke/d38-smoke-summary.json"
    assert current["evidence"]["golden_replay_report_path"].endswith("golden-replay-report.json")
    assert current["evidence"]["golden_replay_decision"] == "passed"
    assert rollback["model"]["model_type"] == "RandomForestRegressor"
    assert rollback["model"]["model_schema_version"] == "v1"
    assert rollback["evidence"]["golden_replay_report_path"].endswith("golden-replay-report.json")
    assert rollback["artifact_sha1_matches"] is True
    assert rollback["metadata_sha1_matches"] is True
    assert payload["rollback_check"]["status"] == "ok"
    assert payload["rollback_check"]["dry_run_only"] is True
    assert payload["invariants"]["does_not_execute_rollback"] is True


def test_model_registry_warns_when_rollback_metadata_is_missing(tmp_path: Path):
    artifacts_dir = tmp_path / "artifacts"
    versions_dir = artifacts_dir / "versions"
    model_path = _write_bytes(artifacts_dir / "page_quality_model.pkl", b"catboost-v3")
    rollback_path = _write_bytes(versions_dir / "page_quality_model--previous.pkl", b"rf-v1")
    missing_metadata_path = build_artifact_metadata_path(rollback_path)
    _write_json(
        build_artifact_metadata_path(model_path),
        {
            "artifact_version": "dataset-v3-d37-20260501200434",
            "model_type": "CatBoostRegressor",
            "model_schema_version": "v3",
            "dataset_metadata": {"dataset_version": "dataset-v3-d37"},
            "rollback_reference": {
                "rollback_model_path": str(rollback_path),
                "rollback_model_sha1": _sha1(rollback_path),
                "rollback_metadata_path": str(missing_metadata_path),
            },
        },
    )

    payload = build_model_registry_payload(
        model_path=model_path,
        versions_dir=versions_dir,
        evidence_dir=artifacts_dir / "missing-evidence",
        checked_at="2026-05-02T00:00:00+00:00",
    )

    rollback = next(record for record in payload["records"] if record["role"] == "rollback")
    warning_codes = {warning["code"] for warning in rollback["warnings"]}
    checklist_warnings = {item["code"] for item in payload["rollback_check"]["warnings"]}

    assert payload["status"] == "warning"
    assert "metadata_missing" in warning_codes
    assert "metadata_sha1_missing" in warning_codes
    assert "rollback_metadata_present" in checklist_warnings
    assert "rollback_metadata_sha1_present" in checklist_warnings
