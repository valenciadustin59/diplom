from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from app.ml.model import BACKEND_DIR, DEFAULT_MODEL_PATH, FEATURE_COLUMNS, load_model_artifact
from app.ml.publish import build_artifact_metadata_path


def _checked_at() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _sha1_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha1()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_path(value: Any) -> str | None:
    if not value:
        return None
    try:
        path = Path(str(value))
        if not path.is_absolute():
            return str(path)
        return str(path.resolve(strict=False).relative_to(BACKEND_DIR))
    except (OSError, ValueError):
        return str(value)


def _artifact_model_section(artifact: dict[str, Any], public_metadata: dict[str, Any]) -> dict[str, Any]:
    feature_columns = artifact.get("feature_columns")
    feature_count = len(feature_columns) if isinstance(feature_columns, (list, tuple)) else len(FEATURE_COLUMNS)
    return {
        "source": artifact.get("source") or public_metadata.get("source") or "unknown",
        "model_type": artifact.get("model_type") or public_metadata.get("model_type"),
        "model_schema_version": artifact.get("model_schema_version") or public_metadata.get("model_schema_version"),
        "feature_count": feature_count,
        "trained_at": artifact.get("trained_at") or public_metadata.get("trained_at"),
        "published_at": artifact.get("published_at") or public_metadata.get("published_at"),
        "artifact_version": artifact.get("artifact_version") or public_metadata.get("artifact_version"),
        "artifact_family": artifact.get("artifact_family") or public_metadata.get("artifact_family"),
    }


def _artifact_dataset_section(artifact: dict[str, Any], public_metadata: dict[str, Any]) -> dict[str, Any]:
    artifact_metadata = artifact.get("dataset_metadata") if isinstance(artifact.get("dataset_metadata"), dict) else {}
    public_dataset = (
        public_metadata.get("dataset_metadata") if isinstance(public_metadata.get("dataset_metadata"), dict) else {}
    )
    dataset_metadata = {**public_dataset, **artifact_metadata}
    return {
        "dataset_version": dataset_metadata.get("dataset_version") or artifact.get("dataset_version"),
        "rows_count": _safe_int(dataset_metadata.get("rows_count") or artifact.get("rows_count")),
        "queries_count": _safe_int(dataset_metadata.get("queries_count") or artifact.get("queries_count")),
        "domains_count": _safe_int(dataset_metadata.get("domains_count") or artifact.get("domains_count")),
        "categories_count": _safe_int(dataset_metadata.get("categories_count")),
        "cities_count": _safe_int(dataset_metadata.get("cities_count")),
        "failure_rate": dataset_metadata.get("failure_rate"),
        "query_coverage_ratio": dataset_metadata.get("query_coverage_ratio"),
        "attempted_query_coverage_ratio": dataset_metadata.get("attempted_query_coverage_ratio"),
        "manifest_generated_at": dataset_metadata.get("manifest_generated_at"),
    }


def _publish_section(public_metadata: dict[str, Any]) -> dict[str, Any]:
    shadow_decision = public_metadata.get("shadow_decision") if isinstance(public_metadata.get("shadow_decision"), dict) else {}
    return {
        "candidate_name": public_metadata.get("candidate_name"),
        "candidate_family": public_metadata.get("candidate_family"),
        "shadow_report_path": _safe_path(public_metadata.get("shadow_report_path")),
        "publish_recommendation": shadow_decision.get("publish_recommendation"),
        "selected_candidate": shadow_decision.get("selected_candidate"),
        "reason": shadow_decision.get("reason"),
    }


def _rollback_section(public_metadata: dict[str, Any]) -> dict[str, Any]:
    rollback = (
        public_metadata.get("rollback_reference")
        if isinstance(public_metadata.get("rollback_reference"), dict)
        else {}
    )
    rollback_model_path = _safe_path(rollback.get("rollback_model_path"))
    return {
        "available": bool(rollback_model_path),
        "model_path": rollback_model_path,
        "model_sha1": rollback.get("rollback_model_sha1"),
        "metadata_path": _safe_path(rollback.get("rollback_metadata_path")),
        "metadata_sha1": rollback.get("rollback_metadata_sha1"),
    }


def build_model_status_payload(model_path: str | Path = DEFAULT_MODEL_PATH) -> dict[str, Any]:
    resolved_model_path = Path(model_path)
    metadata_path = build_artifact_metadata_path(resolved_model_path)

    try:
        artifact = load_model_artifact(resolved_model_path)
        public_metadata = _read_json(metadata_path)
    except Exception as error:  # pragma: no cover - exercised through endpoint fallback behavior.
        return {
            "status": "error",
            "checked_at": _checked_at(),
            "artifact_path": _safe_path(resolved_model_path),
            "metadata_path": _safe_path(metadata_path),
            "error": str(error),
            "model": None,
            "dataset": None,
            "metrics_summary": {},
            "publish": {},
            "rollback": {"available": False},
        }

    if artifact is None:
        return {
            "status": "fallback",
            "checked_at": _checked_at(),
            "artifact_path": _safe_path(resolved_model_path),
            "metadata_path": _safe_path(metadata_path),
            "error": "Production model artifact was not found.",
            "model": None,
            "dataset": None,
            "metrics_summary": {},
            "publish": {},
            "rollback": {"available": False},
        }

    source = str(artifact.get("source") or "")
    status = "fallback" if source == "bootstrap" else "active"
    metrics_summary = artifact.get("metrics_summary") if isinstance(artifact.get("metrics_summary"), dict) else {}

    return {
        "status": status,
        "checked_at": _checked_at(),
        "artifact_path": _safe_path(resolved_model_path),
        "artifact_sha1": _sha1_file(resolved_model_path),
        "metadata_path": _safe_path(metadata_path),
        "metadata_sha1": _sha1_file(metadata_path),
        "model": _artifact_model_section(artifact, public_metadata),
        "dataset": _artifact_dataset_section(artifact, public_metadata),
        "metrics_summary": metrics_summary,
        "publish": _publish_section(public_metadata),
        "rollback": _rollback_section(public_metadata),
    }
