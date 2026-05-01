from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from app.ml.model import DEFAULT_MODEL_PATH, load_model_artifact
from app.ml.publish import ARTIFACTS_DIR, build_artifact_metadata_path


DEFAULT_D35_SHADOW_REPORT_PATH = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v2-d35" / "shadow-benchmark-guardrails-report.json"
DEFAULT_D36_DECISION_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v2-d36"
NO_PUBLISH_REPORT_JSON_NAME = "no-publish-decision-report.json"
NO_PUBLISH_REPORT_MARKDOWN_NAME = "no-publish-decision-report.md"
SUCCESS_AUDIT_STATUSES = {"completed", "completed_with_warnings"}
PASSED_STATUS = "passed"


def sha1_file(path: str | Path) -> str:
    resolved_path = Path(path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"File not found: {resolved_path}")
    digest = hashlib.sha1()
    with resolved_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_object(path: str | Path) -> dict[str, Any]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"JSON file not found: {resolved_path}")
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {resolved_path}")
    return payload


def _optional_json(path: str | Path) -> dict[str, Any] | None:
    return load_json_object(path) if Path(path).exists() else None


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _selected_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    keys = ("rmse", "mae", "spearman_mean", "ndcg_at_10", "top_3_hit_rate", "validation_queries")
    return {key: metrics[key] for key in keys if key in metrics}


def _artifact_model_info(artifact: dict[str, Any]) -> dict[str, Any]:
    dataset_metadata = artifact.get("dataset_metadata") if isinstance(artifact.get("dataset_metadata"), dict) else {}
    feature_columns = artifact.get("feature_columns") if isinstance(artifact.get("feature_columns"), (list, tuple)) else []
    return {
        "artifact_version": artifact.get("artifact_version"),
        "artifact_family": artifact.get("artifact_family"),
        "model_type": artifact.get("model_type"),
        "model_schema_version": artifact.get("model_schema_version"),
        "source": artifact.get("source"),
        "trained_at": artifact.get("trained_at"),
        "published_at": artifact.get("published_at"),
        "feature_count": len(feature_columns),
        "dataset_version": dataset_metadata.get("dataset_version") or artifact.get("dataset_version"),
        "rows_count": _safe_int(dataset_metadata.get("rows_count") or artifact.get("rows_count")),
        "queries_count": _safe_int(dataset_metadata.get("queries_count") or artifact.get("queries_count")),
        "domains_count": _safe_int(dataset_metadata.get("domains_count") or artifact.get("domains_count")),
        "metrics_summary": artifact.get("metrics_summary") if isinstance(artifact.get("metrics_summary"), dict) else {},
    }


def build_production_artifact_state(model_path: str | Path = DEFAULT_MODEL_PATH) -> dict[str, Any]:
    resolved_model_path = Path(model_path)
    artifact = load_model_artifact(resolved_model_path)
    if artifact is None:
        raise ValueError(f"Production artifact is not available: {resolved_model_path}")
    metadata_path = build_artifact_metadata_path(resolved_model_path)
    return {
        "model_path": str(resolved_model_path),
        "model_sha1": sha1_file(resolved_model_path),
        "model_size_bytes": resolved_model_path.stat().st_size,
        "public_metadata_path": str(metadata_path),
        "public_metadata_sha1": sha1_file(metadata_path) if metadata_path.exists() else None,
        "public_metadata": _optional_json(metadata_path),
        "model_info": _artifact_model_info(artifact),
    }


def build_versioned_reference_state(production_state: dict[str, Any], *, versions_dir: str | Path | None = None) -> dict[str, Any]:
    model_path = Path(str(production_state["model_path"]))
    model_info = production_state.get("model_info") if isinstance(production_state.get("model_info"), dict) else {}
    artifact_version = model_info.get("artifact_version")
    resolved_versions_dir = Path(versions_dir) if versions_dir is not None else model_path.parent / "versions"
    versioned_model_path = resolved_versions_dir / f"{model_path.stem}--{artifact_version}{model_path.suffix}" if artifact_version else None
    versioned_metadata_path = build_artifact_metadata_path(versioned_model_path) if versioned_model_path is not None else None
    return {
        "rollback_required": False,
        "rollback_reason": "No artifact was published in D36; the current production alias remains selected.",
        "current_alias_model_path": production_state["model_path"],
        "current_alias_model_sha1": production_state["model_sha1"],
        "current_alias_metadata_path": production_state.get("public_metadata_path"),
        "current_alias_metadata_sha1": production_state.get("public_metadata_sha1"),
        "versioned_reference_model_path": str(versioned_model_path) if versioned_model_path is not None else None,
        "versioned_reference_model_available": bool(versioned_model_path and versioned_model_path.exists()),
        "versioned_reference_model_sha1": sha1_file(versioned_model_path) if versioned_model_path is not None and versioned_model_path.exists() else None,
        "versioned_reference_metadata_path": str(versioned_metadata_path) if versioned_metadata_path is not None else None,
        "versioned_reference_metadata_available": bool(versioned_metadata_path and versioned_metadata_path.exists()),
        "versioned_reference_metadata_sha1": sha1_file(versioned_metadata_path) if versioned_metadata_path is not None and versioned_metadata_path.exists() else None,
    }


def validate_keep_reference_shadow_report(shadow_report: dict[str, Any]) -> None:
    decision = shadow_report.get("decision") if isinstance(shadow_report.get("decision"), dict) else {}
    recommendation = decision.get("publish_recommendation")
    if recommendation != "keep_reference":
        raise ValueError(f"D36 no-publish path requires D35 keep_reference recommendation, got {recommendation!r}")
    passing_candidates = [
        str(comparison.get("candidate_name") or "unknown")
        for comparison in shadow_report.get("candidate_comparisons", [])
        if isinstance(comparison, dict)
        and isinstance(comparison.get("guardrails"), dict)
        and comparison["guardrails"].get("publish_gate_passed") is True
    ]
    if passing_candidates:
        raise ValueError("D36 no-publish path expects no D35 candidate to pass all publish gates: " + ", ".join(passing_candidates))


def summarize_candidate_rejections(shadow_report: dict[str, Any]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for comparison in shadow_report.get("candidate_comparisons", []):
        if not isinstance(comparison, dict):
            continue
        guardrails = comparison.get("guardrails") if isinstance(comparison.get("guardrails"), dict) else {}
        checks = guardrails.get("checks") if isinstance(guardrails.get("checks"), dict) else {}
        candidate_metrics = comparison.get("candidate_metrics") if isinstance(comparison.get("candidate_metrics"), dict) else {}
        reference_metrics = comparison.get("reference_metrics") if isinstance(comparison.get("reference_metrics"), dict) else {}
        metric_deltas = comparison.get("metric_deltas") if isinstance(comparison.get("metric_deltas"), dict) else {}
        summaries.append({
            "candidate_name": comparison.get("candidate_name"),
            "candidate_family": comparison.get("candidate_family"),
            "model_path": comparison.get("model_path"),
            "publish_gate_passed": bool(guardrails.get("publish_gate_passed")),
            "rejection_reasons": list(guardrails.get("rejection_reasons") or []),
            "failed_checks": [check_name for check_name, passed in checks.items() if isinstance(passed, bool) and not passed],
            "candidate_metrics": _selected_metrics(candidate_metrics),
            "reference_metrics": _selected_metrics(reference_metrics),
            "metric_deltas": _selected_metrics(metric_deltas),
            "thresholds": guardrails.get("thresholds") if isinstance(guardrails.get("thresholds"), dict) else {},
        })
    return summaries


def summarize_candidate_artifacts(shadow_report: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for candidate in shadow_report.get("candidates", []):
        if isinstance(candidate, dict):
            model_info = candidate.get("model_info") if isinstance(candidate.get("model_info"), dict) else {}
            artifacts.append({
                "candidate_name": candidate.get("candidate_name"),
                "candidate_family": candidate.get("candidate_family"),
                "status": candidate.get("status"),
                "model_path": candidate.get("model_path"),
                "artifact_version": model_info.get("artifact_version"),
                "dataset_version": model_info.get("dataset_version"),
                "model_schema_version": candidate.get("model_schema_version"),
                "model_type": candidate.get("model_type"),
                "feature_count": candidate.get("feature_count"),
            })
    return artifacts


def build_runtime_smoke_verification(
    runtime_smoke_summary_path: str | Path | None,
    *,
    expected_dataset_version: str | None,
    expected_model_schema_version: str | None,
) -> dict[str, Any]:
    if runtime_smoke_summary_path is None:
        return {"status": "pending", "summary_path": None, "reason": "runtime_smoke_not_recorded"}
    resolved_path = Path(runtime_smoke_summary_path)
    if not resolved_path.exists():
        return {"status": "missing", "summary_path": str(resolved_path), "reason": "runtime_smoke_summary_missing"}
    summary = load_json_object(resolved_path)
    model_info = summary.get("model_info") if isinstance(summary.get("model_info"), dict) else {}
    frontend_routes = summary.get("frontend_routes") if isinstance(summary.get("frontend_routes"), dict) else {}
    invalid_routes = [
        route for route, route_summary in frontend_routes.items()
        if not (
            isinstance(route_summary, dict)
            and route_summary.get("status") == 200
            and route_summary.get("has_root") is True
            and route_summary.get("has_vite_entry") is True
        )
    ]
    failures: list[str] = []
    if summary.get("health_ready_status") != "ready":
        failures.append("health_ready_not_ready")
    if summary.get("ready_worker_count") != 4:
        failures.append("unexpected_worker_count")
    if summary.get("ready_missing_queues"):
        failures.append("missing_worker_queues")
    if summary.get("audit_status") not in SUCCESS_AUDIT_STATUSES:
        failures.append("audit_not_completed")
    if _safe_int(summary.get("competitors_analyzed")) <= 0:
        failures.append("no_competitors_analyzed")
    if expected_dataset_version and model_info.get("dataset_version") != expected_dataset_version:
        failures.append("runtime_dataset_version_mismatch")
    if expected_model_schema_version and model_info.get("model_schema_version") != expected_model_schema_version:
        failures.append("runtime_model_schema_version_mismatch")
    if invalid_routes:
        failures.append("frontend_routes_invalid")
    return {
        "status": PASSED_STATUS if not failures else "failed",
        "summary_path": str(resolved_path),
        "generated_at": summary.get("generated_at"),
        "audit_id": summary.get("audit_id"),
        "audit_status": summary.get("audit_status"),
        "health_ready_status": summary.get("health_ready_status"),
        "ready_worker_count": summary.get("ready_worker_count"),
        "ready_missing_queues": summary.get("ready_missing_queues"),
        "competitors_found": summary.get("competitors_found"),
        "competitors_analyzed": summary.get("competitors_analyzed"),
        "competitors_failed": summary.get("competitors_failed"),
        "recommendation_total": summary.get("recommendation_total"),
        "model_info": model_info,
        "frontend_routes_count": len(frontend_routes),
        "invalid_frontend_routes": invalid_routes,
        "failures": failures,
    }


def build_verification_summary(
    *,
    check_results: list[dict[str, Any]] | None = None,
    runtime_smoke_summary_path: str | Path | None = None,
    expected_dataset_version: str | None = None,
    expected_model_schema_version: str | None = None,
) -> dict[str, Any]:
    checks = list(check_results or [])
    runtime_smoke = build_runtime_smoke_verification(
        runtime_smoke_summary_path,
        expected_dataset_version=expected_dataset_version,
        expected_model_schema_version=expected_model_schema_version,
    )
    statuses = [check.get("status") for check in checks] + [runtime_smoke.get("status")]
    status = PASSED_STATUS if statuses and all(item == PASSED_STATUS for item in statuses) else "failed" if "failed" in statuses else "pending"
    return {"status": status, "checks": checks, "runtime_smoke": runtime_smoke}


def build_no_publish_decision_report(
    *,
    shadow_report: dict[str, Any],
    shadow_report_path: str | Path,
    production_state: dict[str, Any],
    production_sha1_before: str,
    production_sha1_after: str,
    verification: dict[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    validate_keep_reference_shadow_report(shadow_report)
    shadow_decision = shadow_report.get("decision") if isinstance(shadow_report.get("decision"), dict) else {}
    production_model_info = production_state.get("model_info") if isinstance(production_state.get("model_info"), dict) else {}
    reference_model = shadow_report.get("reference_model") if isinstance(shadow_report.get("reference_model"), dict) else {}
    smoke_explainability = shadow_report.get("smoke_explainability") if isinstance(shadow_report.get("smoke_explainability"), dict) else {}
    explainability = shadow_report.get("explainability_sensibility") if isinstance(shadow_report.get("explainability_sensibility"), dict) else {}
    return {
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "task": "D36",
        "decision": {
            "decision": "keep_reference",
            "publish_action": "no_publish",
            "reason": "d35_no_candidate_passed_all_publish_gates",
            "d35_publish_recommendation": shadow_decision.get("publish_recommendation"),
            "d35_reason": shadow_decision.get("reason"),
            "selected_candidate": None,
            "selected_runtime_artifact": production_state,
            "production_artifact_sha1_before": production_sha1_before,
            "production_artifact_sha1_after": production_sha1_after,
            "production_artifact_unchanged": production_sha1_before == production_sha1_after,
        },
        "shadow_evidence": {
            "shadow_report_path": str(Path(shadow_report_path)),
            "shadow_report_generated_at": shadow_report.get("generated_at"),
            "dataset_version": shadow_report.get("dataset_version"),
            "rows_count": shadow_report.get("rows_count"),
            "queries_count": shadow_report.get("queries_count"),
            "reference_metrics": _selected_metrics(reference_model.get("metrics") if isinstance(reference_model.get("metrics"), dict) else {}),
            "best_candidate_by_ranking_metrics": shadow_report.get("best_candidate_by_ranking_metrics", {}).get("candidate_name") if isinstance(shadow_report.get("best_candidate_by_ranking_metrics"), dict) else None,
            "smoke_explainability": {key: smoke_explainability.get(key) for key in ("requested_queries_count", "covered_queries_count", "exact_match_queries_count", "fallback_match_queries_count", "missing_queries_count")},
            "explainability_sensibility_passed": explainability.get("passed"),
        },
        "candidate_artifacts": summarize_candidate_artifacts(shadow_report),
        "candidate_rejections": summarize_candidate_rejections(shadow_report),
        "rollback_reference": build_versioned_reference_state(production_state),
        "verification": verification,
        "invariants": {
            "production_model_path": production_state["model_path"],
            "production_model_sha1": production_state["model_sha1"],
            "runtime_dataset_version": production_model_info.get("dataset_version"),
            "runtime_model_schema_version": production_model_info.get("model_schema_version"),
            "candidate_artifacts_are_not_runtime_selected": True,
        },
    }


def _inline_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_no_publish_decision_markdown(report: dict[str, Any]) -> str:
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    selected_artifact = decision.get("selected_runtime_artifact") if isinstance(decision.get("selected_runtime_artifact"), dict) else {}
    model_info = selected_artifact.get("model_info") if isinstance(selected_artifact.get("model_info"), dict) else {}
    rollback = report.get("rollback_reference") if isinstance(report.get("rollback_reference"), dict) else {}
    verification = report.get("verification") if isinstance(report.get("verification"), dict) else {}
    runtime_smoke = verification.get("runtime_smoke") if isinstance(verification.get("runtime_smoke"), dict) else {}
    shadow_evidence = report.get("shadow_evidence") if isinstance(report.get("shadow_evidence"), dict) else {}
    lines = [
        "# D36 Keep-Reference Decision", "",
        f"- Decision: `{decision.get('decision')}`",
        f"- Publish action: `{decision.get('publish_action')}`",
        f"- Reason: `{decision.get('reason')}`",
        f"- D35 recommendation: `{decision.get('d35_publish_recommendation')}`",
        f"- D35 reason: `{decision.get('d35_reason')}`",
        f"- Production SHA1 before: `{decision.get('production_artifact_sha1_before')}`",
        f"- Production SHA1 after: `{decision.get('production_artifact_sha1_after')}`",
        f"- Production artifact unchanged: `{decision.get('production_artifact_unchanged')}`",
        "", "## Selected Runtime Artifact", "",
        f"- Path: `{selected_artifact.get('model_path')}`",
        f"- SHA1: `{selected_artifact.get('model_sha1')}`",
        f"- Artifact version: `{model_info.get('artifact_version')}`",
        f"- Dataset version: `{model_info.get('dataset_version')}`",
        f"- Model schema version: `{model_info.get('model_schema_version')}`",
        f"- Model type: `{model_info.get('model_type')}`",
        f"- Feature count: `{model_info.get('feature_count')}`",
        "", "## Shadow Evidence", "",
        f"- D35 report: `{shadow_evidence.get('shadow_report_path')}`",
        f"- Dataset version: `{shadow_evidence.get('dataset_version')}`",
        f"- Reference metrics: `{_inline_json(shadow_evidence.get('reference_metrics'))}`",
        f"- Smoke explainability: `{_inline_json(shadow_evidence.get('smoke_explainability'))}`",
        f"- Explainability sensibility passed: `{shadow_evidence.get('explainability_sensibility_passed')}`",
        "", "## Candidate Rejections", "",
    ]
    for rejection in report.get("candidate_rejections", []):
        if isinstance(rejection, dict):
            reasons = ", ".join(str(reason) for reason in rejection.get("rejection_reasons", [])) or "none"
            lines.extend([
                f"### {rejection.get('candidate_name')}",
                f"- Candidate family: `{rejection.get('candidate_family')}`",
                f"- Model path: `{rejection.get('model_path')}`",
                f"- Publish gate passed: `{rejection.get('publish_gate_passed')}`",
                f"- Rejection reasons: `{reasons}`",
                f"- Candidate metrics: `{_inline_json(rejection.get('candidate_metrics'))}`",
                f"- Metric deltas vs reference: `{_inline_json(rejection.get('metric_deltas'))}`", "",
            ])
    lines.extend([
        "## Rollback Reference", "",
        f"- Rollback required: `{rollback.get('rollback_required')}`",
        f"- Reason: {rollback.get('rollback_reason')}",
        f"- Current alias path: `{rollback.get('current_alias_model_path')}`",
        f"- Current alias SHA1: `{rollback.get('current_alias_model_sha1')}`",
        f"- Versioned reference path: `{rollback.get('versioned_reference_model_path')}`",
        f"- Versioned reference available: `{rollback.get('versioned_reference_model_available')}`",
        f"- Versioned reference SHA1: `{rollback.get('versioned_reference_model_sha1')}`",
        "", "## Verification", "",
        f"- Overall status: `{verification.get('status')}`",
        f"- Runtime smoke status: `{runtime_smoke.get('status')}`",
        f"- Runtime smoke summary: `{runtime_smoke.get('summary_path')}`",
        f"- Runtime smoke audit: `{runtime_smoke.get('audit_id')}`",
        f"- Runtime smoke model info: `{_inline_json(runtime_smoke.get('model_info'))}`",
    ])
    for check in verification.get("checks", []):
        if isinstance(check, dict):
            lines.append(f"- `{check.get('name')}`: `{check.get('status')}`")
    return "\n".join(lines).strip() + "\n"


def write_no_publish_decision_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    json_path = resolved_output_dir / NO_PUBLISH_REPORT_JSON_NAME
    markdown_path = resolved_output_dir / NO_PUBLISH_REPORT_MARKDOWN_NAME
    report_paths = {"json_path": str(json_path), "markdown_path": str(markdown_path)}
    report_with_paths = {**report, "report_paths": report_paths}
    json_path.write_text(json.dumps(report_with_paths, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_no_publish_decision_markdown(report_with_paths), encoding="utf-8")
    return report_paths


def run_no_publish_decision(
    *,
    shadow_report_path: str | Path = DEFAULT_D35_SHADOW_REPORT_PATH,
    production_model_path: str | Path = DEFAULT_MODEL_PATH,
    output_dir: str | Path = DEFAULT_D36_DECISION_OUTPUT_DIR,
    check_results: list[dict[str, Any]] | None = None,
    runtime_smoke_summary_path: str | Path | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    production_sha1_before = sha1_file(production_model_path)
    shadow_report = load_json_object(shadow_report_path)
    production_state = build_production_artifact_state(production_model_path)
    model_info = production_state.get("model_info") if isinstance(production_state.get("model_info"), dict) else {}
    verification = build_verification_summary(
        check_results=check_results,
        runtime_smoke_summary_path=runtime_smoke_summary_path,
        expected_dataset_version=model_info.get("dataset_version"),
        expected_model_schema_version=model_info.get("model_schema_version"),
    )
    production_sha1_after = sha1_file(production_model_path)
    if production_sha1_before != production_sha1_after:
        raise RuntimeError(f"Production artifact changed while generating D36 evidence: {production_sha1_before} -> {production_sha1_after}")
    report = build_no_publish_decision_report(
        shadow_report=shadow_report,
        shadow_report_path=shadow_report_path,
        production_state=production_state,
        production_sha1_before=production_sha1_before,
        production_sha1_after=production_sha1_after,
        verification=verification,
        generated_at=generated_at,
    )
    report_paths = write_no_publish_decision_report(report, output_dir)
    return {**report, "report_paths": report_paths}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shadow-report", default=str(DEFAULT_D35_SHADOW_REPORT_PATH))
    parser.add_argument("--production-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_D36_DECISION_OUTPUT_DIR))
    parser.add_argument("--runtime-smoke-summary", default=None)
    args = parser.parse_args()
    report = run_no_publish_decision(
        shadow_report_path=args.shadow_report,
        production_model_path=args.production_model,
        output_dir=args.output_dir,
        runtime_smoke_summary_path=args.runtime_smoke_summary,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
