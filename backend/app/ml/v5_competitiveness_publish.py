from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
from typing import Any, Mapping, Sequence

from app.ml.competitiveness_release_policy import COMPETITIVENESS_RELEASE_POLICY_VERSION
from app.ml.controlled_publish import (
    build_controlled_versioned_artifact_path,
    ensure_rollback_reference,
)
from app.ml.model import DEFAULT_MODEL_PATH, clear_model_cache, load_model_artifact, load_saved_model, save_model
from app.ml.no_publish_decision import build_production_artifact_state, sha1_file
from app.ml.publish import build_artifact_metadata_path, build_artifact_public_metadata, build_primary_artifact_version, write_artifact_public_metadata
from app.ml.v5_candidate_training import (
    DEFAULT_DATASET_VERSION,
    V5CalibratedRankerModel,
    V5HybridRankerModel,
)
from app.ml.v5_shadow_decision import (
    DEFAULT_D54_CANDIDATE_PATHS,
    DEFAULT_D54_REPORT_JSON_PATH,
    build_d54_decision,
    build_d54_product_guardrails,
    build_d54_shadow_benchmark,
    build_d54_validation_rows,
    _selected_metrics,
)


DEFAULT_D58_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "ranking-benchmarks" / "dataset-v5-d58"
DEFAULT_D58_REPORT_JSON_PATH = DEFAULT_D58_OUTPUT_DIR / "d58-competitiveness-publish-report.json"
DEFAULT_D58_REPORT_MD_PATH = DEFAULT_D58_OUTPUT_DIR / "d58-competitiveness-publish-report.md"


def _read_json(path: str | Path) -> dict[str, Any]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return {}
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _candidate_by_name(shadow_report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = shadow_report.get("candidates")
    result: dict[str, dict[str, Any]] = {}
    for candidate in candidates if isinstance(candidates, list) else []:
        if not isinstance(candidate, dict) or candidate.get("status") != "available":
            continue
        name = str(candidate.get("candidate_name") or Path(str(candidate.get("model_path") or "model")).stem)
        result[name] = candidate
    return result


def _comparison_by_name(shadow_report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    comparisons = shadow_report.get("candidate_comparisons")
    result: dict[str, dict[str, Any]] = {}
    for comparison in comparisons if isinstance(comparisons, list) else []:
        if not isinstance(comparison, dict):
            continue
        result[str(comparison.get("candidate_name") or "unknown")] = comparison
    return result


def _verification_summary(check_results: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    checks = [dict(check) for check in (check_results or [])]
    if not checks:
        return {"status": "pending", "checks": [], "reason": "checks_not_recorded"}
    failed = [check for check in checks if check.get("status") != "passed"]
    return {"status": "passed" if not failed else "failed", "checks": checks}


def _artifact_model_info(artifact: Mapping[str, Any]) -> dict[str, Any]:
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
        "dataset_version": artifact.get("dataset_version"),
        "rows_count": artifact.get("rows_count"),
        "queries_count": artifact.get("queries_count"),
        "domains_count": artifact.get("domains_count"),
        "metrics_summary": artifact.get("metrics_summary") if isinstance(artifact.get("metrics_summary"), dict) else {},
    }


def _candidate_dataset_metadata(candidate_artifact: Mapping[str, Any], candidate_raw: Mapping[str, Any]) -> dict[str, Any]:
    raw_dataset_metadata = candidate_raw.get("dataset_metadata")
    if isinstance(raw_dataset_metadata, dict):
        return dict(raw_dataset_metadata)
    artifact_dataset_metadata = candidate_artifact.get("dataset_metadata")
    if isinstance(artifact_dataset_metadata, dict):
        return dict(artifact_dataset_metadata)
    return {
        "dataset_version": candidate_artifact.get("dataset_version"),
        "rows_count": candidate_artifact.get("rows_count"),
        "queries_count": candidate_artifact.get("queries_count"),
        "domains_count": candidate_artifact.get("domains_count"),
        "split_mode": candidate_artifact.get("metrics_summary", {}).get("split_mode")
        if isinstance(candidate_artifact.get("metrics_summary"), dict)
        else None,
    }


def _runtime_dataset_metadata(
    *,
    rows: Sequence[Mapping[str, Any]],
    train_rows: Sequence[Mapping[str, Any]],
    validation_rows: Sequence[Mapping[str, Any]],
    split_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    queries = {str(row.get("query") or "").strip() for row in rows if str(row.get("query") or "").strip()}
    domains = {str(row.get("domain") or "").strip() for row in rows if str(row.get("domain") or "").strip()}
    return {
        "dataset_version": DEFAULT_DATASET_VERSION,
        "rows_count": len(rows),
        "queries_count": len(queries),
        "domains_count": len(domains),
        "split_mode": split_metadata.get("split_mode") or "group_by_query",
        "train_rows_count": len(train_rows),
        "validation_rows_count": len(validation_rows),
        "train_queries_count": len({str(row.get("query") or "") for row in train_rows}),
        "validation_queries_count": len({str(row.get("query") or "") for row in validation_rows}),
        "query_overlap_count": split_metadata.get("query_overlap_count", 0),
    }


def _selected_candidate_path(
    *,
    selected_candidate: str,
    shadow_report: Mapping[str, Any],
    fallback_candidate_paths: Sequence[str | Path],
) -> Path:
    candidates = _candidate_by_name(shadow_report)
    candidate = candidates.get(selected_candidate)
    if isinstance(candidate, dict) and candidate.get("model_path"):
        return Path(str(candidate["model_path"]))
    for candidate_path in fallback_candidate_paths:
        raw = load_saved_model(candidate_path)
        if isinstance(raw, dict) and raw.get("candidate_name") == selected_candidate:
            return Path(candidate_path)
    raise ValueError(f"Selected candidate artifact is not available: {selected_candidate}")


def _publish_v5_candidate_to_alias(
    *,
    candidate_model_path: str | Path,
    production_model_path: str | Path,
    d58_report_path: str | Path,
    decision: Mapping[str, Any],
    rollback_reference: Mapping[str, Any],
    product_guardrail: Mapping[str, Any],
    dataset_metadata: Mapping[str, Any] | None,
    published_at: datetime,
) -> dict[str, Any]:
    resolved_candidate_model_path = Path(candidate_model_path)
    resolved_production_model_path = Path(production_model_path)
    candidate_raw = load_saved_model(resolved_candidate_model_path)
    candidate_artifact = load_model_artifact(resolved_candidate_model_path)
    if not isinstance(candidate_raw, dict) or candidate_artifact is None:
        raise ValueError(f"Candidate artifact is not loadable: {resolved_candidate_model_path}")
    if candidate_artifact.get("model_schema_version") != "v3":
        raise ValueError(f"D58 expects a v3-compatible candidate, got {candidate_artifact.get('model_schema_version')!r}")
    if candidate_raw.get("candidate_name") != decision.get("selected_candidate"):
        raise ValueError(
            "Candidate artifact name does not match D58 decision: "
            f"{candidate_raw.get('candidate_name')!r} vs {decision.get('selected_candidate')!r}"
        )

    dataset_version = str(candidate_artifact.get("dataset_version") or candidate_raw.get("dataset_version") or DEFAULT_DATASET_VERSION)
    artifact_version = build_primary_artifact_version(dataset_version, published_at)
    resolved_dataset_metadata = dict(dataset_metadata or _candidate_dataset_metadata(candidate_artifact, candidate_raw))
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
        "dataset_metadata": resolved_dataset_metadata,
        "model_schema_version": candidate_artifact.get("model_schema_version"),
        "feature_columns": candidate_artifact.get("feature_columns"),
        "candidate_name": candidate_raw.get("candidate_name"),
        "candidate_family": candidate_raw.get("candidate_family"),
        "feature_importance_summary": candidate_raw.get("feature_importance_summary"),
        "non_production": False,
        "runtime_enabled": True,
        "publish_decision_required": "completed_d58",
        "d58_publish": {
            "source_candidate_path": str(resolved_candidate_model_path),
            "source_candidate_sha1": sha1_file(resolved_candidate_model_path),
            "d58_report_path": str(Path(d58_report_path)),
            "decision": dict(decision),
            "release_policy_version": COMPETITIVENESS_RELEASE_POLICY_VERSION,
            "product_guardrail": dict(product_guardrail),
            "rollback_reference": dict(rollback_reference),
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
        "release_policy_version": COMPETITIVENESS_RELEASE_POLICY_VERSION,
        "d58_report_path": str(Path(d58_report_path)),
        "d58_decision": dict(decision),
        "rollback_reference": dict(rollback_reference),
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


def _candidate_decision_summaries(
    *,
    shadow_report: Mapping[str, Any],
    product_guardrails: Mapping[str, Any],
) -> list[dict[str, Any]]:
    comparisons = _comparison_by_name(shadow_report)
    summaries: list[dict[str, Any]] = []
    for candidate_name, guardrail in product_guardrails.items():
        if not isinstance(guardrail, dict):
            continue
        comparison = comparisons.get(str(candidate_name), {})
        summaries.append(
            {
                "candidate_name": str(candidate_name),
                "publish_allowed": bool(guardrail.get("passed")),
                "failed_checks": list(guardrail.get("failed_checks") or []),
                "candidate_metrics": _selected_metrics(
                    comparison.get("candidate_metrics") if isinstance(comparison.get("candidate_metrics"), dict) else {}
                ),
                "reference_metrics": _selected_metrics(
                    comparison.get("reference_metrics") if isinstance(comparison.get("reference_metrics"), dict) else {}
                ),
                "metric_deltas": _selected_metrics(
                    comparison.get("metric_deltas") if isinstance(comparison.get("metric_deltas"), dict) else {}
                ),
                "serp_alignment_diagnostics": guardrail.get("serp_alignment_diagnostics"),
                "page_quality_checks": guardrail.get("page_quality_checks"),
                "product_guardrail_checks": guardrail.get("product_guardrail_checks"),
                "recommendation_consistency": guardrail.get("recommendation_consistency"),
            }
        )
    return summaries


def render_d58_markdown(report: Mapping[str, Any]) -> str:
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    production = report.get("production_artifact") if isinstance(report.get("production_artifact"), dict) else {}
    publish_result = report.get("publish_result") if isinstance(report.get("publish_result"), dict) else {}
    verification = report.get("verification") if isinstance(report.get("verification"), dict) else {}
    lines = [
        "# D58 Competitiveness Scorecard Re-Evaluation And Publish",
        "",
        f"- Decision: `{decision.get('decision')}`",
        f"- Publish action: `{decision.get('publish_action')}`",
        f"- Selected candidate: `{decision.get('selected_candidate')}`",
        f"- Reason: `{decision.get('reason')}`",
        f"- Release policy: `{report.get('release_policy_version')}`",
        f"- Production SHA1 before: `{production.get('sha1_before')}`",
        f"- Production SHA1 after: `{production.get('sha1_after')}`",
        f"- Production changed by D58: `{production.get('changed_by_d58')}`",
        "",
        "## Published Artifact",
        "",
        f"- Artifact version: `{publish_result.get('artifact_version')}`",
        f"- Dataset: `{publish_result.get('model_info', {}).get('dataset_version') if isinstance(publish_result.get('model_info'), dict) else None}`",
        f"- Model type: `{publish_result.get('model_info', {}).get('model_type') if isinstance(publish_result.get('model_info'), dict) else None}`",
        f"- Feature count: `{publish_result.get('model_info', {}).get('feature_count') if isinstance(publish_result.get('model_info'), dict) else None}`",
        "",
        "## Candidate Decisions",
        "",
    ]
    for candidate in report.get("candidate_decisions", []):
        if not isinstance(candidate, dict):
            continue
        lines.extend(
            [
                f"### {candidate.get('candidate_name')}",
                f"- Publish allowed: `{candidate.get('publish_allowed')}`",
                f"- Failed checks: `{', '.join(candidate.get('failed_checks') or []) or 'none'}`",
                f"- Candidate metrics: `{json.dumps(candidate.get('candidate_metrics'), ensure_ascii=False, sort_keys=True)}`",
                f"- Metric deltas: `{json.dumps(candidate.get('metric_deltas'), ensure_ascii=False, sort_keys=True)}`",
                f"- SERP diagnostics: `{json.dumps(candidate.get('serp_alignment_diagnostics'), ensure_ascii=False, sort_keys=True)}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Verification",
            "",
            f"- Overall status: `{verification.get('status')}`",
        ]
    )
    for check in verification.get("checks", []):
        if isinstance(check, dict):
            lines.append(f"- `{check.get('name')}`: `{check.get('status')}`")
    return "\n".join(lines).strip() + "\n"


def run_d58_competitiveness_publish(
    *,
    reference_model_path: str | Path = DEFAULT_MODEL_PATH,
    candidate_model_paths: Sequence[str | Path] = DEFAULT_D54_CANDIDATE_PATHS,
    output_dir: str | Path = DEFAULT_D58_OUTPUT_DIR,
    report_json_path: str | Path = DEFAULT_D58_REPORT_JSON_PATH,
    report_markdown_path: str | Path = DEFAULT_D58_REPORT_MD_PATH,
    check_results: Sequence[Mapping[str, Any]] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    published_at = generated_at or datetime.now(UTC)
    resolved_output_dir = Path(output_dir)
    production_sha1_before = sha1_file(reference_model_path)
    train_rows, validation_rows, split_metadata = build_d54_validation_rows()
    rows = train_rows + validation_rows
    shadow_report = build_d54_shadow_benchmark(
        rows=rows,
        train_rows=train_rows,
        validation_rows=validation_rows,
        split_metadata=split_metadata,
        reference_model_path=reference_model_path,
        candidate_model_paths=candidate_model_paths,
        output_dir=resolved_output_dir,
    )
    product_guardrails = build_d54_product_guardrails(
        shadow_report=shadow_report,
        validation_rows=validation_rows,
    )
    decision = build_d54_decision(shadow_report=shadow_report, product_guardrails=product_guardrails)
    production_before = build_production_artifact_state(reference_model_path)
    rollback_reference: dict[str, Any] | None = None
    publish_result: dict[str, Any] | None = None
    if decision.get("publish_action") == "controlled_publish_required":
        selected_candidate = str(decision.get("selected_candidate") or "")
        selected_guardrail = product_guardrails.get(selected_candidate)
        if not isinstance(selected_guardrail, dict) or selected_guardrail.get("passed") is not True:
            raise ValueError(f"D58 selected candidate did not pass product guardrails: {selected_candidate}")
        selected_candidate_path = _selected_candidate_path(
            selected_candidate=selected_candidate,
            shadow_report=shadow_report,
            fallback_candidate_paths=candidate_model_paths,
        )
        rollback_reference = ensure_rollback_reference(production_before, model_path=reference_model_path)
        publish_result = _publish_v5_candidate_to_alias(
            candidate_model_path=selected_candidate_path,
            production_model_path=reference_model_path,
            d58_report_path=report_json_path,
            decision=decision,
            rollback_reference=rollback_reference,
            product_guardrail=selected_guardrail,
            dataset_metadata=_runtime_dataset_metadata(
                rows=rows,
                train_rows=train_rows,
                validation_rows=validation_rows,
                split_metadata=split_metadata,
            ),
            published_at=published_at,
        )
    production_after = build_production_artifact_state(reference_model_path)
    production_sha1_after = sha1_file(reference_model_path)
    if decision.get("publish_action") != "controlled_publish_required" and production_sha1_before != production_sha1_after:
        raise RuntimeError(
            f"Production artifact changed despite no-publish D58 decision: {production_sha1_before} -> {production_sha1_after}"
        )
    verification = _verification_summary(check_results)
    report: dict[str, Any] = {
        "generated_at": published_at.isoformat(),
        "task": "D58",
        "release_policy_version": COMPETITIVENESS_RELEASE_POLICY_VERSION,
        "re_evaluated_from": {
            "previous_d54_report": str(DEFAULT_D54_REPORT_JSON_PATH),
            "previous_d54_decision": _read_json(DEFAULT_D54_REPORT_JSON_PATH).get("decision"),
        },
        "dependencies": {
            "D55": "top_3_hit_rate is SERP-alignment diagnostic, not release blocker",
            "D56": "runtime competitiveness score wraps page quality with competitor context",
            "D57": "recommendation priority now follows competitor gap and controllability",
        },
        "candidate_model_paths": [str(Path(path)) for path in candidate_model_paths],
        "shadow_benchmark": shadow_report,
        "product_guardrails": product_guardrails,
        "decision": decision,
        "candidate_decisions": _candidate_decision_summaries(
            shadow_report=shadow_report,
            product_guardrails=product_guardrails,
        ),
        "production_artifact": {
            "path": str(Path(reference_model_path)),
            "sha1_before": production_sha1_before,
            "sha1_after": production_sha1_after,
            "changed_by_d58": production_sha1_before != production_sha1_after,
            "before": production_before,
            "after": production_after,
        },
        "rollback_reference": rollback_reference,
        "publish_result": publish_result,
        "verification": verification,
        "invariants": {
            "production_changed_only_for_controlled_publish": (
                decision.get("publish_action") == "controlled_publish_required"
            )
            == (production_sha1_before != production_sha1_after),
            "runtime_dataset_version": production_after.get("model_info", {}).get("dataset_version")
            if isinstance(production_after.get("model_info"), dict)
            else None,
            "runtime_model_schema_version": production_after.get("model_info", {}).get("model_schema_version")
            if isinstance(production_after.get("model_info"), dict)
            else None,
            "runtime_model_type": production_after.get("model_info", {}).get("model_type")
            if isinstance(production_after.get("model_info"), dict)
            else None,
        },
        "report_paths": {
            "json_path": str(Path(report_json_path)),
            "markdown_path": str(Path(report_markdown_path)),
        },
    }
    _write_json(report_json_path, report)
    Path(report_markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_markdown_path).write_text(render_d58_markdown(report), encoding="utf-8")
    return report


def update_d58_verification(
    *,
    report_json_path: str | Path = DEFAULT_D58_REPORT_JSON_PATH,
    report_markdown_path: str | Path = DEFAULT_D58_REPORT_MD_PATH,
    check_results: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    report = _read_json(report_json_path)
    if not report:
        raise FileNotFoundError(f"D58 report not found: {report_json_path}")
    updated_report = {**report, "verification": _verification_summary(check_results)}
    _write_json(report_json_path, updated_report)
    Path(report_markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_markdown_path).write_text(render_d58_markdown(updated_report), encoding="utf-8")
    return updated_report


def _parse_check_result(value: str) -> dict[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Check result must use NAME=STATUS format.")
    name, status = value.split("=", 1)
    if not name.strip() or not status.strip():
        raise argparse.ArgumentTypeError("Check result must use non-empty NAME=STATUS format.")
    return {"name": name.strip(), "status": status.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run D58 v5 competitiveness re-evaluation and controlled publish.")
    parser.add_argument("--reference-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--candidate-model", action="append", default=[])
    parser.add_argument("--output-dir", default=str(DEFAULT_D58_OUTPUT_DIR))
    parser.add_argument("--report-json", default=str(DEFAULT_D58_REPORT_JSON_PATH))
    parser.add_argument("--report-md", default=str(DEFAULT_D58_REPORT_MD_PATH))
    parser.add_argument("--check", action="append", type=_parse_check_result, default=[])
    parser.add_argument("--update-report", action="store_true")
    args = parser.parse_args()
    if args.update_report:
        report = update_d58_verification(
            report_json_path=args.report_json,
            report_markdown_path=args.report_md,
            check_results=args.check,
        )
    else:
        report = run_d58_competitiveness_publish(
            reference_model_path=args.reference_model,
            candidate_model_paths=tuple(args.candidate_model or [str(path) for path in DEFAULT_D54_CANDIDATE_PATHS]),
            output_dir=args.output_dir,
            report_json_path=args.report_json,
            report_markdown_path=args.report_md,
            check_results=args.check,
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
