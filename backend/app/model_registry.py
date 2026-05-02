from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from app.ml.model import BACKEND_DIR, DEFAULT_MODEL_PATH
from app.ml.publish import ARTIFACTS_DIR, VERSIONED_ARTIFACTS_DIR, build_artifact_metadata_path

CONTROLLED_PUBLISH_REPORT_NAME = "controlled-publish-report.json"
GOLDEN_REPLAY_REPORT_NAME = "golden-replay-report.json"
MODEL_ARTIFACT_PREFIX = "page_quality_model--"
MODEL_ARTIFACT_SUFFIX = ".pkl"

ROLE_ORDER = {"current": 0, "rollback": 1, "archived": 2}
WARNING_CODES = {
    "artifact_missing",
    "artifact_sha1_missing",
    "artifact_sha1_mismatch",
    "metadata_missing",
    "metadata_sha1_missing",
    "metadata_sha1_mismatch",
}


@dataclass
class EvidenceIndex:
    by_sha1: dict[str, dict[str, Any]] = field(default_factory=dict)
    by_artifact_version: dict[str, dict[str, Any]] = field(default_factory=dict)


def _checked_at() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha1_file(path: Path | None) -> str | None:
    if path is None or not path.exists():
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


def _safe_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _as_path(value: Any) -> Path | None:
    raw = _safe_str(value)
    if raw is None:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0].lower() == "backend":
        return BACKEND_DIR.parent / path
    return BACKEND_DIR / path


def _path_key(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve(strict=False)).casefold()
    except OSError:
        return str(path).casefold()


def _display_path(value: Any) -> str | None:
    if value is None:
        return None
    path = value if isinstance(value, Path) else Path(str(value))
    try:
        resolved = path.resolve(strict=False) if path.is_absolute() else path
        if path.is_absolute():
            for root in (BACKEND_DIR, BACKEND_DIR.parent):
                try:
                    return resolved.relative_to(root).as_posix()
                except ValueError:
                    continue
        return str(path).replace("\\", "/")
    except (OSError, ValueError):
        return str(value).replace("\\", "/")


def _metadata_dataset(metadata: dict[str, Any], model_info: dict[str, Any]) -> dict[str, Any]:
    dataset_metadata = metadata.get("dataset_metadata") if isinstance(metadata.get("dataset_metadata"), dict) else {}
    return {
        "dataset_version": dataset_metadata.get("dataset_version")
        or metadata.get("dataset_version")
        or model_info.get("dataset_version"),
        "rows_count": _safe_int(dataset_metadata.get("rows_count") or metadata.get("rows_count") or model_info.get("rows_count")),
        "queries_count": _safe_int(
            dataset_metadata.get("queries_count") or metadata.get("queries_count") or model_info.get("queries_count")
        ),
        "domains_count": _safe_int(
            dataset_metadata.get("domains_count") or metadata.get("domains_count") or model_info.get("domains_count")
        ),
    }


def _metadata_model(metadata: dict[str, Any], model_info: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": metadata.get("source") or model_info.get("source"),
        "model_type": metadata.get("model_type") or model_info.get("model_type"),
        "model_schema_version": metadata.get("model_schema_version") or model_info.get("model_schema_version"),
        "feature_count": _safe_int(metadata.get("feature_count") or model_info.get("feature_count")),
        "trained_at": metadata.get("trained_at") or model_info.get("trained_at"),
        "published_at": metadata.get("published_at") or model_info.get("published_at"),
        "artifact_version": metadata.get("artifact_version") or model_info.get("artifact_version"),
        "artifact_family": metadata.get("artifact_family") or model_info.get("artifact_family") or "page_quality_model",
    }


def _metadata_metrics(metadata: dict[str, Any], model_info: dict[str, Any]) -> dict[str, Any]:
    metadata_metrics = metadata.get("metrics_summary") if isinstance(metadata.get("metrics_summary"), dict) else {}
    model_metrics = model_info.get("metrics_summary") if isinstance(model_info.get("metrics_summary"), dict) else {}
    return {**model_metrics, **metadata_metrics}


def _metadata_publish(metadata: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    shadow_decision = metadata.get("shadow_decision") if isinstance(metadata.get("shadow_decision"), dict) else {}
    return {
        "candidate_name": metadata.get("candidate_name") or evidence.get("selected_candidate"),
        "candidate_family": metadata.get("candidate_family"),
        "publish_action": evidence.get("publish_action"),
        "publish_recommendation": shadow_decision.get("publish_recommendation") or evidence.get("publish_decision"),
        "selected_candidate": shadow_decision.get("selected_candidate") or evidence.get("selected_candidate"),
        "reason": shadow_decision.get("reason") or evidence.get("reason"),
    }


def _append_warning(warnings: list[dict[str, str]], code: str, message: str, path: str | None = None) -> None:
    warning = {"code": code, "message": message}
    if path:
        warning["path"] = path
    warnings.append(warning)


def _merge_evidence(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    for key, value in source.items():
        if value is None:
            continue
        if key == "warnings" and isinstance(value, list):
            target[key] = [*target.get(key, []), *value]
        elif key not in target or target[key] in (None, "", [], {}):
            target[key] = value
    return target


def _put_evidence(index: EvidenceIndex, *, sha1: str | None, artifact_version: str | None, evidence: dict[str, Any]) -> None:
    if sha1:
        _merge_evidence(index.by_sha1.setdefault(sha1, {}), evidence)
    if artifact_version:
        _merge_evidence(index.by_artifact_version.setdefault(artifact_version, {}), evidence)


def _report_paths(report_path: Path, report: dict[str, Any]) -> dict[str, str | None]:
    report_paths = report.get("report_paths") if isinstance(report.get("report_paths"), dict) else {}
    markdown_path = report_paths.get("markdown_path") or str(report_path.with_suffix(".md"))
    return {
        "report_path": _display_path(report_paths.get("json_path") or report_path),
        "report_markdown_path": _display_path(markdown_path),
    }


def _controlled_publish_evidence(report_path: Path, report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    paths = _report_paths(report_path, report)
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    shadow_evidence = report.get("shadow_evidence") if isinstance(report.get("shadow_evidence"), dict) else {}
    verification = report.get("verification") if isinstance(report.get("verification"), dict) else {}
    runtime_smoke = verification.get("runtime_smoke") if isinstance(verification.get("runtime_smoke"), dict) else {}

    current_evidence = {
        "publish_report_path": paths["report_path"],
        "publish_report_markdown_path": paths["report_markdown_path"],
        "shadow_report_path": _display_path(shadow_evidence.get("shadow_report_path")),
        "smoke_summary_path": _display_path(runtime_smoke.get("summary_path")),
        "publish_action": decision.get("publish_action"),
        "publish_decision": decision.get("decision"),
        "selected_candidate": decision.get("selected_candidate"),
        "reason": decision.get("reason"),
    }

    rollback_evidence = {
        "publish_report_path": paths["report_path"],
        "publish_report_markdown_path": paths["report_markdown_path"],
        "rollback_source": "controlled_publish_rollback_reference",
        "publish_action": "rollback_reference",
        "reason": "Preserved as rollback reference before controlled publish.",
    }
    return current_evidence, rollback_evidence


def _index_controlled_publish_report(index: EvidenceIndex, report_path: Path) -> None:
    report = _read_json(report_path)
    if not report:
        return
    publish_result = report.get("publish_result") if isinstance(report.get("publish_result"), dict) else {}
    production_before = report.get("production_before") if isinstance(report.get("production_before"), dict) else {}
    rollback_reference = report.get("rollback_reference") if isinstance(report.get("rollback_reference"), dict) else {}
    current_evidence, rollback_evidence = _controlled_publish_evidence(report_path, report)

    current_model_info = publish_result.get("model_info") if isinstance(publish_result.get("model_info"), dict) else {}
    current_sha1 = _safe_str(publish_result.get("versioned_model_sha1") or publish_result.get("published_model_sha1"))
    current_artifact_version = _safe_str(publish_result.get("artifact_version") or current_model_info.get("artifact_version"))
    _put_evidence(
        index,
        sha1=current_sha1,
        artifact_version=current_artifact_version,
        evidence={**current_evidence, "model_info": current_model_info},
    )

    rollback_model_info = production_before.get("model_info") if isinstance(production_before.get("model_info"), dict) else {}
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    rollback_sha1 = _safe_str(
        rollback_reference.get("rollback_model_sha1")
        or production_before.get("model_sha1")
        or decision.get("production_artifact_sha1_before")
    )
    rollback_artifact_version = _safe_str(rollback_model_info.get("artifact_version"))
    _put_evidence(
        index,
        sha1=rollback_sha1,
        artifact_version=rollback_artifact_version,
        evidence={**rollback_evidence, "model_info": rollback_model_info},
    )


def _index_golden_replay_report(index: EvidenceIndex, report_path: Path) -> None:
    report = _read_json(report_path)
    if not report:
        return
    paths = _report_paths(report_path, report)
    evidence = {
        "golden_replay_report_path": paths["report_path"],
        "golden_replay_report_markdown_path": paths["report_markdown_path"],
        "golden_replay_decision": (report.get("decision") if isinstance(report.get("decision"), dict) else {}).get("status"),
    }
    model_status = report.get("model_status") if isinstance(report.get("model_status"), dict) else {}
    model = model_status.get("model") if isinstance(model_status.get("model"), dict) else {}
    rollback = report.get("rollback_reference") if isinstance(report.get("rollback_reference"), dict) else {}

    _put_evidence(
        index,
        sha1=_safe_str(model_status.get("artifact_sha1")),
        artifact_version=_safe_str(model.get("artifact_version")),
        evidence=evidence,
    )
    _put_evidence(
        index,
        sha1=_safe_str(rollback.get("model_sha1") or rollback.get("artifact_sha1")),
        artifact_version=_safe_str(rollback.get("artifact_version")),
        evidence=evidence,
    )


def build_evidence_index(evidence_dir: str | Path = ARTIFACTS_DIR / "ranking-benchmarks") -> EvidenceIndex:
    root = Path(evidence_dir)
    index = EvidenceIndex()
    if not root.exists():
        return index
    for report_path in sorted(root.rglob(CONTROLLED_PUBLISH_REPORT_NAME)):
        _index_controlled_publish_report(index, report_path)
    for report_path in sorted(root.rglob(GOLDEN_REPLAY_REPORT_NAME)):
        _index_golden_replay_report(index, report_path)
    return index


def _lookup_evidence(index: EvidenceIndex, *, sha1: str | None, artifact_version: str | None) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    if artifact_version and artifact_version in index.by_artifact_version:
        _merge_evidence(evidence, index.by_artifact_version[artifact_version])
    if sha1 and sha1 in index.by_sha1:
        _merge_evidence(evidence, index.by_sha1[sha1])
    return evidence


def _build_registry_record(
    *,
    role: str,
    artifact_path: Path,
    metadata_path: Path,
    metadata: dict[str, Any],
    evidence: dict[str, Any],
    expected_artifact_sha1: str | None = None,
    expected_metadata_sha1: str | None = None,
) -> dict[str, Any]:
    artifact_sha1 = _sha1_file(artifact_path)
    metadata_sha1 = _sha1_file(metadata_path)
    model_info = evidence.get("model_info") if isinstance(evidence.get("model_info"), dict) else {}
    model = _metadata_model(metadata, model_info)
    dataset = _metadata_dataset(metadata, model_info)
    warnings: list[dict[str, str]] = []

    if not artifact_path.exists():
        _append_warning(warnings, "artifact_missing", "Model artifact file is missing.", _display_path(artifact_path))
    if artifact_sha1 is None:
        _append_warning(warnings, "artifact_sha1_missing", "Model artifact SHA1 could not be computed.", _display_path(artifact_path))
    if expected_artifact_sha1 and artifact_sha1 and expected_artifact_sha1 != artifact_sha1:
        _append_warning(warnings, "artifact_sha1_mismatch", "Model artifact SHA1 does not match rollback metadata.", _display_path(artifact_path))

    if not metadata_path.exists():
        _append_warning(warnings, "metadata_missing", "Public metadata sidecar is missing.", _display_path(metadata_path))
    if metadata_sha1 is None:
        _append_warning(warnings, "metadata_sha1_missing", "Public metadata sidecar SHA1 could not be computed.", _display_path(metadata_path))
    if expected_metadata_sha1 and metadata_sha1 and expected_metadata_sha1 != metadata_sha1:
        _append_warning(warnings, "metadata_sha1_mismatch", "Public metadata SHA1 does not match rollback metadata.", _display_path(metadata_path))
    if role == "rollback" and not expected_metadata_sha1:
        _append_warning(warnings, "metadata_sha1_missing", "Rollback reference does not declare metadata SHA1.", _display_path(metadata_path))

    return {
        "id": f"{role}:{model.get('artifact_version') or artifact_path.name}",
        "role": role,
        "status": "warning" if warnings else "ok",
        "artifact_path": _display_path(artifact_path),
        "artifact_sha1": artifact_sha1,
        "expected_artifact_sha1": expected_artifact_sha1,
        "artifact_sha1_matches": None
        if expected_artifact_sha1 is None or artifact_sha1 is None
        else expected_artifact_sha1 == artifact_sha1,
        "metadata_path": _display_path(metadata_path),
        "metadata_sha1": metadata_sha1,
        "expected_metadata_sha1": expected_metadata_sha1,
        "metadata_sha1_matches": None
        if expected_metadata_sha1 is None or metadata_sha1 is None
        else expected_metadata_sha1 == metadata_sha1,
        "model": model,
        "dataset": dataset,
        "metrics_summary": _metadata_metrics(metadata, model_info),
        "publish": _metadata_publish(metadata, evidence),
        "evidence": {key: value for key, value in evidence.items() if key != "model_info"},
        "warnings": warnings,
    }


def _versioned_artifacts(versions_dir: Path) -> list[Path]:
    if not versions_dir.exists():
        return []
    return sorted(
        path
        for path in versions_dir.glob(f"{MODEL_ARTIFACT_PREFIX}*{MODEL_ARTIFACT_SUFFIX}")
        if path.is_file() and not path.name.endswith(".metadata.pkl")
    )


def _is_current_versioned_artifact(
    path: Path,
    *,
    active_sha1: str | None,
    active_artifact_version: str | None,
) -> bool:
    if active_sha1 and _sha1_file(path) == active_sha1:
        return True
    metadata = _read_json(build_artifact_metadata_path(path))
    return bool(active_artifact_version and metadata.get("artifact_version") == active_artifact_version)


def _is_rollback_artifact(path: Path, *, rollback_path: Path | None, rollback_sha1: str | None) -> bool:
    if rollback_path and _path_key(path) == _path_key(rollback_path):
        return True
    return bool(rollback_sha1 and _sha1_file(path) == rollback_sha1)


def _build_rollback_check(rollback_reference: dict[str, Any], rollback_record: dict[str, Any] | None) -> dict[str, Any]:
    rollback_path = _as_path(rollback_reference.get("rollback_model_path"))
    metadata_path = _as_path(rollback_reference.get("rollback_metadata_path"))
    artifact_sha1 = _safe_str(rollback_reference.get("rollback_model_sha1")) or (
        rollback_record.get("artifact_sha1") if rollback_record else None
    )
    metadata_sha1 = _safe_str(rollback_reference.get("rollback_metadata_sha1")) or (
        rollback_record.get("metadata_sha1") if rollback_record else None
    )

    checklist = [
        {
            "code": "dry_run_only",
            "status": "info",
            "label": "Rollback is read-only in the product UI.",
            "detail": "The UI exposes evidence and checklist state only; actual rollback remains an engineering operation.",
        },
        {
            "code": "rollback_artifact_present",
            "status": "pass" if rollback_path and rollback_path.exists() else "warn",
            "label": "Rollback artifact exists.",
            "detail": "The previous production model file must be available before a controlled rollback.",
            "path": _display_path(rollback_path) if rollback_path else None,
        },
        {
            "code": "rollback_artifact_sha1_present",
            "status": "pass" if artifact_sha1 else "warn",
            "label": "Rollback artifact SHA1 is known.",
            "detail": "The model file hash is required to verify the rollback target.",
            "path": _display_path(rollback_path) if rollback_path else None,
        },
        {
            "code": "rollback_metadata_present",
            "status": "pass" if metadata_path and metadata_path.exists() else "warn",
            "label": "Rollback metadata sidecar exists.",
            "detail": "The public metadata sidecar keeps dataset, schema and model evidence visible after rollback.",
            "path": _display_path(metadata_path) if metadata_path else None,
        },
        {
            "code": "rollback_metadata_sha1_present",
            "status": "pass" if metadata_sha1 else "warn",
            "label": "Rollback metadata SHA1 is known.",
            "detail": "The metadata hash is required to detect sidecar drift before rollback.",
            "path": _display_path(metadata_path) if metadata_path else None,
        },
    ]
    warnings = [item for item in checklist if item["status"] == "warn"]
    return {
        "status": "warning" if warnings else "ok",
        "dry_run_only": True,
        "target_artifact_path": _display_path(rollback_path) if rollback_path else None,
        "target_artifact_sha1": artifact_sha1,
        "target_metadata_path": _display_path(metadata_path) if metadata_path else None,
        "target_metadata_sha1": metadata_sha1,
        "checklist": checklist,
        "warnings": warnings,
    }


def build_model_registry_payload(
    *,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    versions_dir: str | Path = VERSIONED_ARTIFACTS_DIR,
    evidence_dir: str | Path = ARTIFACTS_DIR / "ranking-benchmarks",
    checked_at: str | None = None,
) -> dict[str, Any]:
    active_path = Path(model_path)
    resolved_versions_dir = Path(versions_dir)
    active_metadata_path = build_artifact_metadata_path(active_path)
    active_metadata = _read_json(active_metadata_path)
    active_sha1 = _sha1_file(active_path)
    active_artifact_version = _safe_str(active_metadata.get("artifact_version"))
    rollback_reference = (
        active_metadata.get("rollback_reference")
        if isinstance(active_metadata.get("rollback_reference"), dict)
        else {}
    )
    rollback_path = _as_path(rollback_reference.get("rollback_model_path"))
    rollback_sha1 = _safe_str(rollback_reference.get("rollback_model_sha1"))
    rollback_metadata_path = _as_path(rollback_reference.get("rollback_metadata_path"))
    rollback_metadata_sha1 = _safe_str(rollback_reference.get("rollback_metadata_sha1"))
    evidence_index = build_evidence_index(evidence_dir)

    records: list[dict[str, Any]] = [
        _build_registry_record(
            role="current",
            artifact_path=active_path,
            metadata_path=active_metadata_path,
            metadata=active_metadata,
            evidence=_lookup_evidence(index=evidence_index, sha1=active_sha1, artifact_version=active_artifact_version),
        )
    ]
    seen_paths = {_path_key(active_path)}
    rollback_record: dict[str, Any] | None = None

    for artifact_path in _versioned_artifacts(resolved_versions_dir):
        if _is_current_versioned_artifact(
            artifact_path,
            active_sha1=active_sha1,
            active_artifact_version=active_artifact_version,
        ):
            seen_paths.add(_path_key(artifact_path))
            continue
        artifact_sha1 = _sha1_file(artifact_path)
        metadata_path = build_artifact_metadata_path(artifact_path)
        metadata = _read_json(metadata_path)
        artifact_version = _safe_str(metadata.get("artifact_version"))
        role = "rollback" if _is_rollback_artifact(artifact_path, rollback_path=rollback_path, rollback_sha1=rollback_sha1) else "archived"
        expected_artifact_sha1 = rollback_sha1 if role == "rollback" else None
        expected_metadata_sha1 = rollback_metadata_sha1 if role == "rollback" else None
        record = _build_registry_record(
            role=role,
            artifact_path=artifact_path,
            metadata_path=metadata_path,
            metadata=metadata,
            evidence=_lookup_evidence(index=evidence_index, sha1=artifact_sha1, artifact_version=artifact_version),
            expected_artifact_sha1=expected_artifact_sha1,
            expected_metadata_sha1=expected_metadata_sha1,
        )
        records.append(record)
        seen_paths.add(_path_key(artifact_path))
        if role == "rollback":
            rollback_record = record

    if rollback_path is not None and _path_key(rollback_path) not in seen_paths:
        metadata_path = rollback_metadata_path or build_artifact_metadata_path(rollback_path)
        metadata = _read_json(metadata_path)
        record = _build_registry_record(
            role="rollback",
            artifact_path=rollback_path,
            metadata_path=metadata_path,
            metadata=metadata,
            evidence=_lookup_evidence(index=evidence_index, sha1=rollback_sha1, artifact_version=_safe_str(metadata.get("artifact_version"))),
            expected_artifact_sha1=rollback_sha1,
            expected_metadata_sha1=rollback_metadata_sha1,
        )
        records.append(record)
        rollback_record = record

    rollback_check = _build_rollback_check(rollback_reference, rollback_record)
    sorted_records = sorted(
        records,
        key=lambda record: (
            ROLE_ORDER.get(str(record.get("role")), 99),
            str(record.get("model", {}).get("published_at") or ""),
            str(record.get("model", {}).get("artifact_version") or ""),
        ),
    )
    warning_count = sum(len(record.get("warnings") or []) for record in sorted_records) + len(rollback_check["warnings"])
    return {
        "status": "empty" if not sorted_records else "warning" if warning_count else "ok",
        "checked_at": checked_at or _checked_at(),
        "artifact_family": "page_quality_model",
        "active_artifact_sha1": active_sha1,
        "rollback_artifact_sha1": rollback_sha1,
        "summary": {
            "record_count": len(sorted_records),
            "current_count": sum(1 for record in sorted_records if record.get("role") == "current"),
            "rollback_count": sum(1 for record in sorted_records if record.get("role") == "rollback"),
            "archived_count": sum(1 for record in sorted_records if record.get("role") == "archived"),
            "warning_count": warning_count,
        },
        "records": sorted_records,
        "rollback_check": rollback_check,
        "invariants": {
            "dry_run_only": True,
            "does_not_execute_rollback": True,
            "does_not_mutate_model_artifacts": True,
            "warning_codes": sorted(WARNING_CODES),
        },
    }
