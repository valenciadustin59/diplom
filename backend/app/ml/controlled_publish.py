from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
from typing import Any

from app.ml.model import DEFAULT_MODEL_PATH, clear_model_cache, load_model_artifact, load_saved_model, save_model
from app.ml.no_publish_decision import (
    build_production_artifact_state,
    build_verification_summary,
    load_json_object,
    sha1_file,
)
from app.ml.publish import (
    ARTIFACTS_DIR,
    VERSIONED_ARTIFACTS_DIR,
    build_artifact_metadata_path,
    build_artifact_public_metadata,
    build_primary_artifact_version,
    write_artifact_public_metadata,
)


DEFAULT_D37_SHADOW_REPORT_PATH = (
    ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v3-d37-shadow" / "shadow-benchmark-guardrails-report.json"
)
DEFAULT_D38_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v3-d37-d38"
DEFAULT_D37_CATBOOST_CANDIDATE_PATH = ARTIFACTS_DIR / "page_quality_model.dataset-v3-d37-catboost-candidate.pkl"
CONTROLLED_PUBLISH_REPORT_JSON_NAME = "controlled-publish-report.json"
CONTROLLED_PUBLISH_REPORT_MARKDOWN_NAME = "controlled-publish-report.md"


def _selected_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    keys = ("rmse", "mae", "spearman_mean", "ndcg_at_10", "top_3_hit_rate", "validation_queries", "split_mode")
    return {key: metrics[key] for key in keys if key in metrics}


def _find_named_entry(entries: Any, selected_candidate_name: str) -> dict[str, Any] | None:
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("candidate_name") == selected_candidate_name:
            return entry
    return None


def validate_publish_shadow_report(
    shadow_report: dict[str, Any],
    *,
    selected_candidate_name: str = "pointwise_catboost",
) -> dict[str, Any]:
    decision = shadow_report.get("decision") if isinstance(shadow_report.get("decision"), dict) else {}
    if decision.get("publish_recommendation") != "publish_candidate":
        raise ValueError(
            "Controlled publish requires shadow benchmark recommendation 'publish_candidate', "
            f"got {decision.get('publish_recommendation')!r}."
        )
    if decision.get("selected_candidate") != selected_candidate_name:
        raise ValueError(
            f"Controlled publish expected selected candidate {selected_candidate_name!r}, "
            f"got {decision.get('selected_candidate')!r}."
        )

    candidate = _find_named_entry(shadow_report.get("candidates"), selected_candidate_name)
    if candidate is None or candidate.get("status") != "available":
        raise ValueError(f"Selected candidate {selected_candidate_name!r} is not available in shadow report.")

    comparison = _find_named_entry(shadow_report.get("candidate_comparisons"), selected_candidate_name)
    guardrails = comparison.get("guardrails") if isinstance(comparison, dict) else {}
    if not isinstance(guardrails, dict) or guardrails.get("publish_gate_passed") is not True:
        raise ValueError(f"Selected candidate {selected_candidate_name!r} did not pass publish guardrails.")
    rejection_reasons = guardrails.get("rejection_reasons") or []
    if rejection_reasons:
        raise ValueError(
            f"Selected candidate {selected_candidate_name!r} has rejection reasons: "
            + ", ".join(str(reason) for reason in rejection_reasons)
        )

    explainability = shadow_report.get("explainability_sensibility")
    if isinstance(explainability, dict) and explainability.get("passed") is not True:
        raise ValueError("Controlled publish requires explainability sensibility to pass.")

    smoke = shadow_report.get("smoke_explainability") if isinstance(shadow_report.get("smoke_explainability"), dict) else {}
    model_guardrails = smoke.get("model_guardrails") if isinstance(smoke.get("model_guardrails"), dict) else {}
    selected_smoke_guardrail = model_guardrails.get(selected_candidate_name)
    if isinstance(selected_smoke_guardrail, dict) and selected_smoke_guardrail.get("passed") is not True:
        raise ValueError("Controlled publish requires selected candidate smoke explainability to pass.")

    return {
        "decision": decision,
        "candidate": candidate,
        "comparison": comparison,
        "guardrails": guardrails,
    }


def _artifact_model_info(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_version": artifact.get("artifact_version"),
        "artifact_family": artifact.get("artifact_family"),
        "model_type": artifact.get("model_type"),
        "model_schema_version": artifact.get("model_schema_version"),
        "source": artifact.get("source"),
        "trained_at": artifact.get("trained_at"),
        "published_at": artifact.get("published_at"),
        "feature_count": len(artifact.get("feature_columns") or []),
        "dataset_version": artifact.get("dataset_version"),
        "rows_count": artifact.get("rows_count"),
        "queries_count": artifact.get("queries_count"),
        "domains_count": artifact.get("domains_count"),
        "metrics_summary": artifact.get("metrics_summary") if isinstance(artifact.get("metrics_summary"), dict) else {},
    }


def ensure_rollback_reference(production_state: dict[str, Any], *, model_path: str | Path = DEFAULT_MODEL_PATH) -> dict[str, Any]:
    resolved_model_path = Path(model_path)
    model_info = production_state.get("model_info") if isinstance(production_state.get("model_info"), dict) else {}
    artifact_version = str(model_info.get("artifact_version") or "unversioned-reference")
    rollback_model_path = VERSIONED_ARTIFACTS_DIR / f"{resolved_model_path.stem}--{artifact_version}{resolved_model_path.suffix}"
    rollback_metadata_path = build_artifact_metadata_path(rollback_model_path)
    alias_metadata_path = build_artifact_metadata_path(resolved_model_path)

    rollback_model_path.parent.mkdir(parents=True, exist_ok=True)
    created_model_copy = False
    created_metadata_copy = False
    if not rollback_model_path.exists():
        shutil.copy2(resolved_model_path, rollback_model_path)
        created_model_copy = True
    if alias_metadata_path.exists() and not rollback_metadata_path.exists():
        shutil.copy2(alias_metadata_path, rollback_metadata_path)
        created_metadata_copy = True

    return {
        "rollback_model_path": str(rollback_model_path),
        "rollback_model_sha1": sha1_file(rollback_model_path),
        "rollback_metadata_path": str(rollback_metadata_path),
        "rollback_metadata_sha1": sha1_file(rollback_metadata_path) if rollback_metadata_path.exists() else None,
        "created_model_copy": created_model_copy,
        "created_metadata_copy": created_metadata_copy,
        "source_model_path": production_state.get("model_path"),
        "source_model_sha1": production_state.get("model_sha1"),
        "source_metadata_path": production_state.get("public_metadata_path"),
        "source_metadata_sha1": production_state.get("public_metadata_sha1"),
    }


def build_controlled_versioned_artifact_path(model_path: str | Path, artifact_version: str) -> Path:
    resolved_model_path = Path(model_path)
    return VERSIONED_ARTIFACTS_DIR / f"{resolved_model_path.stem}--{artifact_version}{resolved_model_path.suffix}"


def _candidate_dataset_metadata(candidate_artifact: dict[str, Any], candidate_raw: dict[str, Any]) -> dict[str, Any]:
    raw_dataset_metadata = candidate_raw.get("dataset_metadata")
    if isinstance(raw_dataset_metadata, dict):
        return dict(raw_dataset_metadata)
    return {
        "dataset_version": candidate_artifact.get("dataset_version"),
        "rows_count": candidate_artifact.get("rows_count"),
        "queries_count": candidate_artifact.get("queries_count"),
        "domains_count": candidate_artifact.get("domains_count"),
        "split_mode": candidate_artifact.get("metrics_summary", {}).get("split_mode")
        if isinstance(candidate_artifact.get("metrics_summary"), dict)
        else None,
    }


def _publish_candidate_to_alias(
    *,
    candidate_model_path: str | Path,
    production_model_path: str | Path,
    shadow_report_path: str | Path,
    shadow_selection: dict[str, Any],
    rollback_reference: dict[str, Any],
    published_at: datetime,
) -> dict[str, Any]:
    resolved_candidate_model_path = Path(candidate_model_path)
    resolved_production_model_path = Path(production_model_path)
    candidate_raw = load_saved_model(resolved_candidate_model_path)
    candidate_artifact = load_model_artifact(resolved_candidate_model_path)
    if not isinstance(candidate_raw, dict) or candidate_artifact is None:
        raise ValueError(f"Candidate artifact is not loadable: {resolved_candidate_model_path}")
    if candidate_artifact.get("model_schema_version") != "v3":
        raise ValueError(f"D38 expects a v3 candidate, got {candidate_artifact.get('model_schema_version')!r}")
    if candidate_raw.get("candidate_name") != shadow_selection["decision"].get("selected_candidate"):
        raise ValueError(
            "Candidate artifact name does not match shadow decision: "
            f"{candidate_raw.get('candidate_name')!r} vs {shadow_selection['decision'].get('selected_candidate')!r}"
        )

    dataset_version = str(candidate_artifact.get("dataset_version") or candidate_raw.get("dataset_version") or "dataset-v3-d37")
    artifact_version = build_primary_artifact_version(dataset_version, published_at)
    dataset_metadata = _candidate_dataset_metadata(candidate_artifact, candidate_raw)
    metadata = {
        "artifact_version": artifact_version,
        "artifact_family": resolved_production_model_path.stem,
        "published_at": published_at.isoformat(),
        "trained_at": candidate_raw.get("trained_at"),
        "source": candidate_raw.get("source", "local_dataset"),
        "model_type": candidate_raw.get("model_type", candidate_artifact.get("model_type")),
        "dataset_version": dataset_version,
        "rows_count": candidate_artifact.get("rows_count"),
        "queries_count": candidate_artifact.get("queries_count"),
        "domains_count": candidate_artifact.get("domains_count"),
        "dataset_metadata": dataset_metadata,
        "model_schema_version": candidate_artifact.get("model_schema_version"),
        "feature_columns": candidate_artifact.get("feature_columns"),
        "candidate_name": candidate_raw.get("candidate_name"),
        "candidate_family": candidate_raw.get("candidate_family"),
        "feature_importance_summary": candidate_raw.get("feature_importance_summary"),
        "d38_publish": {
            "source_candidate_path": str(resolved_candidate_model_path),
            "source_candidate_sha1": sha1_file(resolved_candidate_model_path),
            "shadow_report_path": str(Path(shadow_report_path)),
            "shadow_decision": shadow_selection.get("decision"),
            "rollback_reference": rollback_reference,
        },
    }
    save_model(
        model=candidate_raw["model"],
        metrics=candidate_raw.get("metrics") if isinstance(candidate_raw.get("metrics"), dict) else {},
        model_path=resolved_production_model_path,
        metadata=metadata,
    )
    clear_model_cache()
    published_artifact = load_model_artifact(resolved_production_model_path)
    if published_artifact is None:
        raise RuntimeError(f"Published artifact is not loadable: {resolved_production_model_path}")

    versioned_model_path = build_controlled_versioned_artifact_path(resolved_production_model_path, artifact_version)
    versioned_model_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved_production_model_path, versioned_model_path)

    alias_metadata = {
        **build_artifact_public_metadata(published_artifact, resolved_production_model_path),
        "candidate_name": candidate_raw.get("candidate_name"),
        "candidate_family": candidate_raw.get("candidate_family"),
        "feature_importance_summary": candidate_raw.get("feature_importance_summary"),
        "shadow_report_path": str(Path(shadow_report_path)),
        "shadow_decision": shadow_selection.get("decision"),
        "rollback_reference": rollback_reference,
    }
    alias_metadata_path = write_artifact_public_metadata(
        alias_metadata,
        build_artifact_metadata_path(resolved_production_model_path),
    )
    versioned_metadata_path = write_artifact_public_metadata(
        {**alias_metadata, "artifact_path": str(versioned_model_path)},
        build_artifact_metadata_path(versioned_model_path),
    )
    return {
        "artifact_version": artifact_version,
        "candidate_model_path": str(resolved_candidate_model_path),
        "candidate_model_sha1": sha1_file(resolved_candidate_model_path),
        "published_model_path": str(resolved_production_model_path),
        "published_model_sha1": sha1_file(resolved_production_model_path),
        "published_metadata_path": str(alias_metadata_path),
        "published_metadata_sha1": sha1_file(alias_metadata_path),
        "versioned_model_path": str(versioned_model_path),
        "versioned_model_sha1": sha1_file(versioned_model_path),
        "versioned_metadata_path": str(versioned_metadata_path),
        "versioned_metadata_sha1": sha1_file(versioned_metadata_path),
        "model_info": _artifact_model_info(published_artifact),
    }


def build_controlled_publish_report(
    *,
    shadow_report: dict[str, Any],
    shadow_report_path: str | Path,
    shadow_selection: dict[str, Any],
    production_before: dict[str, Any],
    production_after: dict[str, Any],
    rollback_reference: dict[str, Any],
    publish_result: dict[str, Any],
    verification: dict[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    comparison = shadow_selection.get("comparison") if isinstance(shadow_selection.get("comparison"), dict) else {}
    candidate_metrics = comparison.get("candidate_metrics") if isinstance(comparison.get("candidate_metrics"), dict) else {}
    reference_metrics = comparison.get("reference_metrics") if isinstance(comparison.get("reference_metrics"), dict) else {}
    metric_deltas = comparison.get("metric_deltas") if isinstance(comparison.get("metric_deltas"), dict) else {}
    return {
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "task": "D38",
        "decision": {
            "decision": "publish_candidate",
            "publish_action": "controlled_publish",
            "selected_candidate": shadow_selection["decision"].get("selected_candidate"),
            "reason": shadow_selection["decision"].get("reason"),
            "production_artifact_sha1_before": production_before.get("model_sha1"),
            "production_artifact_sha1_after": production_after.get("model_sha1"),
            "production_artifact_changed": production_before.get("model_sha1") != production_after.get("model_sha1"),
        },
        "shadow_evidence": {
            "shadow_report_path": str(Path(shadow_report_path)),
            "shadow_report_generated_at": shadow_report.get("generated_at"),
            "dataset_version": shadow_report.get("dataset_version"),
            "rows_count": shadow_report.get("rows_count"),
            "queries_count": shadow_report.get("queries_count"),
            "candidate_metrics": _selected_metrics(candidate_metrics),
            "reference_metrics": _selected_metrics(reference_metrics),
            "metric_deltas": _selected_metrics(metric_deltas),
            "guardrails": shadow_selection.get("guardrails"),
            "smoke_explainability": {
                key: shadow_report.get("smoke_explainability", {}).get(key)
                for key in (
                    "requested_queries_count",
                    "covered_queries_count",
                    "exact_match_queries_count",
                    "fallback_match_queries_count",
                    "missing_queries_count",
                )
                if isinstance(shadow_report.get("smoke_explainability"), dict)
            },
            "explainability_sensibility_passed": shadow_report.get("explainability_sensibility", {}).get("passed")
            if isinstance(shadow_report.get("explainability_sensibility"), dict)
            else None,
        },
        "production_before": production_before,
        "production_after": production_after,
        "rollback_reference": rollback_reference,
        "publish_result": publish_result,
        "verification": verification,
        "invariants": {
            "expected_runtime_dataset_version": publish_result.get("model_info", {}).get("dataset_version"),
            "expected_runtime_model_schema_version": publish_result.get("model_info", {}).get("model_schema_version"),
            "expected_runtime_model_type": publish_result.get("model_info", {}).get("model_type"),
            "expected_feature_count": publish_result.get("model_info", {}).get("feature_count"),
            "rollback_available": Path(str(rollback_reference.get("rollback_model_path"))).exists(),
        },
    }


def _inline_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_controlled_publish_markdown(report: dict[str, Any]) -> str:
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    publish_result = report.get("publish_result") if isinstance(report.get("publish_result"), dict) else {}
    model_info = publish_result.get("model_info") if isinstance(publish_result.get("model_info"), dict) else {}
    rollback = report.get("rollback_reference") if isinstance(report.get("rollback_reference"), dict) else {}
    verification = report.get("verification") if isinstance(report.get("verification"), dict) else {}
    runtime_smoke = verification.get("runtime_smoke") if isinstance(verification.get("runtime_smoke"), dict) else {}
    shadow_evidence = report.get("shadow_evidence") if isinstance(report.get("shadow_evidence"), dict) else {}
    lines = [
        "# D38 Controlled Publish Decision",
        "",
        f"- Decision: `{decision.get('decision')}`",
        f"- Publish action: `{decision.get('publish_action')}`",
        f"- Selected candidate: `{decision.get('selected_candidate')}`",
        f"- Reason: `{decision.get('reason')}`",
        f"- Production SHA1 before: `{decision.get('production_artifact_sha1_before')}`",
        f"- Production SHA1 after: `{decision.get('production_artifact_sha1_after')}`",
        f"- Production artifact changed: `{decision.get('production_artifact_changed')}`",
        "",
        "## Published Runtime Artifact",
        "",
        f"- Path: `{publish_result.get('published_model_path')}`",
        f"- SHA1: `{publish_result.get('published_model_sha1')}`",
        f"- Artifact version: `{model_info.get('artifact_version')}`",
        f"- Dataset version: `{model_info.get('dataset_version')}`",
        f"- Model schema version: `{model_info.get('model_schema_version')}`",
        f"- Model type: `{model_info.get('model_type')}`",
        f"- Feature count: `{model_info.get('feature_count')}`",
        f"- Versioned artifact: `{publish_result.get('versioned_model_path')}`",
        "",
        "## Shadow Evidence",
        "",
        f"- D37 shadow report: `{shadow_evidence.get('shadow_report_path')}`",
        f"- Candidate metrics: `{_inline_json(shadow_evidence.get('candidate_metrics'))}`",
        f"- Reference metrics: `{_inline_json(shadow_evidence.get('reference_metrics'))}`",
        f"- Metric deltas: `{_inline_json(shadow_evidence.get('metric_deltas'))}`",
        f"- Explainability sensibility passed: `{shadow_evidence.get('explainability_sensibility_passed')}`",
        "",
        "## Rollback Reference",
        "",
        f"- Rollback model path: `{rollback.get('rollback_model_path')}`",
        f"- Rollback model SHA1: `{rollback.get('rollback_model_sha1')}`",
        f"- Rollback metadata path: `{rollback.get('rollback_metadata_path')}`",
        "",
        "## Verification",
        "",
        f"- Overall status: `{verification.get('status')}`",
        f"- Runtime smoke status: `{runtime_smoke.get('status')}`",
        f"- Runtime smoke summary: `{runtime_smoke.get('summary_path')}`",
        f"- Runtime smoke audit: `{runtime_smoke.get('audit_id')}`",
        f"- Runtime smoke model info: `{_inline_json(runtime_smoke.get('model_info'))}`",
    ]
    for check in verification.get("checks", []):
        if isinstance(check, dict):
            lines.append(f"- `{check.get('name')}`: `{check.get('status')}`")
    return "\n".join(lines).strip() + "\n"


def write_controlled_publish_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    json_path = resolved_output_dir / CONTROLLED_PUBLISH_REPORT_JSON_NAME
    markdown_path = resolved_output_dir / CONTROLLED_PUBLISH_REPORT_MARKDOWN_NAME
    report_paths = {"json_path": str(json_path), "markdown_path": str(markdown_path)}
    report_with_paths = {**report, "report_paths": report_paths}
    json_path.write_text(json.dumps(report_with_paths, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_controlled_publish_markdown(report_with_paths), encoding="utf-8")
    return report_paths


def update_controlled_publish_verification(
    *,
    report_path: str | Path,
    output_dir: str | Path | None = None,
    check_results: list[dict[str, Any]] | None = None,
    runtime_smoke_summary_path: str | Path | None = None,
) -> dict[str, Any]:
    report = load_json_object(report_path)
    invariants = report.get("invariants") if isinstance(report.get("invariants"), dict) else {}
    verification = build_verification_summary(
        check_results=check_results,
        runtime_smoke_summary_path=runtime_smoke_summary_path,
        expected_dataset_version=invariants.get("expected_runtime_dataset_version"),
        expected_model_schema_version=invariants.get("expected_runtime_model_schema_version"),
    )
    updated_report = {**report, "verification": verification}
    report_paths = write_controlled_publish_report(updated_report, output_dir or Path(report_path).parent)
    return {**updated_report, "report_paths": report_paths}


def run_controlled_publish(
    *,
    shadow_report_path: str | Path = DEFAULT_D37_SHADOW_REPORT_PATH,
    candidate_model_path: str | Path = DEFAULT_D37_CATBOOST_CANDIDATE_PATH,
    production_model_path: str | Path = DEFAULT_MODEL_PATH,
    output_dir: str | Path = DEFAULT_D38_OUTPUT_DIR,
    selected_candidate_name: str = "pointwise_catboost",
    check_results: list[dict[str, Any]] | None = None,
    runtime_smoke_summary_path: str | Path | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    published_at = generated_at or datetime.now(UTC)
    shadow_report = load_json_object(shadow_report_path)
    shadow_selection = validate_publish_shadow_report(
        shadow_report,
        selected_candidate_name=selected_candidate_name,
    )
    production_before = build_production_artifact_state(production_model_path)
    rollback_reference = ensure_rollback_reference(production_before, model_path=production_model_path)
    publish_result = _publish_candidate_to_alias(
        candidate_model_path=candidate_model_path,
        production_model_path=production_model_path,
        shadow_report_path=shadow_report_path,
        shadow_selection=shadow_selection,
        rollback_reference=rollback_reference,
        published_at=published_at,
    )
    production_after = build_production_artifact_state(production_model_path)
    verification = build_verification_summary(
        check_results=check_results,
        runtime_smoke_summary_path=runtime_smoke_summary_path,
        expected_dataset_version=publish_result["model_info"].get("dataset_version"),
        expected_model_schema_version=publish_result["model_info"].get("model_schema_version"),
    )
    report = build_controlled_publish_report(
        shadow_report=shadow_report,
        shadow_report_path=shadow_report_path,
        shadow_selection=shadow_selection,
        production_before=production_before,
        production_after=production_after,
        rollback_reference=rollback_reference,
        publish_result=publish_result,
        verification=verification,
        generated_at=published_at,
    )
    report_paths = write_controlled_publish_report(report, output_dir)
    return {**report, "report_paths": report_paths}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shadow-report", default=str(DEFAULT_D37_SHADOW_REPORT_PATH))
    parser.add_argument("--candidate-model", default=str(DEFAULT_D37_CATBOOST_CANDIDATE_PATH))
    parser.add_argument("--production-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_D38_OUTPUT_DIR))
    parser.add_argument("--selected-candidate", default="pointwise_catboost")
    parser.add_argument("--runtime-smoke-summary", default=None)
    parser.add_argument("--update-report", default=None)
    args = parser.parse_args()
    if args.update_report:
        report = update_controlled_publish_verification(
            report_path=args.update_report,
            output_dir=args.output_dir,
            runtime_smoke_summary_path=args.runtime_smoke_summary,
        )
    else:
        report = run_controlled_publish(
            shadow_report_path=args.shadow_report,
            candidate_model_path=args.candidate_model,
            production_model_path=args.production_model,
            output_dir=args.output_dir,
            selected_candidate_name=args.selected_candidate,
            runtime_smoke_summary_path=args.runtime_smoke_summary,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
