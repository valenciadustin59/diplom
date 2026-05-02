from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.ml.model import DEFAULT_MODEL_PATH
from app.ml.no_publish_decision import (
    build_production_artifact_state,
    build_versioned_reference_state,
    load_json_object,
    sha1_file,
)
from app.ml.publish import ARTIFACTS_DIR
from app.ml.seo_weighted_shadow_benchmark import DEFAULT_D48_REPORT_JSON_PATH


DEFAULT_D49_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v4-d49"
DEFAULT_D49_REPORT_JSON_PATH = DEFAULT_D49_OUTPUT_DIR / "d49-no-publish-decision-report.json"
DEFAULT_D49_REPORT_MD_PATH = DEFAULT_D49_OUTPUT_DIR / "d49-no-publish-decision-report.md"
KEEP_CURRENT_RECOMMENDATIONS = {"keep_current", "keep_reference"}


def _selected_metrics(metrics: Mapping[str, Any]) -> dict[str, Any]:
    keys = ("rmse", "mae", "spearman_mean", "ndcg_at_10", "top_3_hit_rate", "validation_queries")
    return {key: metrics[key] for key in keys if key in metrics}


def _find_comparison(d48_report: Mapping[str, Any], candidate_name: str) -> dict[str, Any]:
    shadow = d48_report.get("shadow_benchmark") if isinstance(d48_report.get("shadow_benchmark"), dict) else {}
    comparisons = shadow.get("candidate_comparisons") if isinstance(shadow.get("candidate_comparisons"), list) else []
    for comparison in comparisons:
        if isinstance(comparison, dict) and str(comparison.get("candidate_name")) == candidate_name:
            return comparison
    return {}


def _summarize_candidate_decisions(d48_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    product_guardrails = (
        d48_report.get("product_guardrails") if isinstance(d48_report.get("product_guardrails"), dict) else {}
    )
    summaries: list[dict[str, Any]] = []
    for candidate_name, guardrail in product_guardrails.items():
        if not isinstance(guardrail, dict):
            continue
        comparison = _find_comparison(d48_report, str(candidate_name))
        candidate_metrics = (
            comparison.get("candidate_metrics") if isinstance(comparison.get("candidate_metrics"), dict) else {}
        )
        reference_metrics = (
            comparison.get("reference_metrics") if isinstance(comparison.get("reference_metrics"), dict) else {}
        )
        base_guardrails = comparison.get("guardrails") if isinstance(comparison.get("guardrails"), dict) else {}
        feature_guardrail = (
            guardrail.get("feature_importance_guardrail")
            if isinstance(guardrail.get("feature_importance_guardrail"), dict)
            else {}
        )
        score_response = (
            guardrail.get("score_response_guardrail")
            if isinstance(guardrail.get("score_response_guardrail"), dict)
            else {}
        )
        summaries.append(
            {
                "candidate_name": str(candidate_name),
                "model_path": comparison.get("model_path"),
                "publish_allowed": False,
                "shadow_gate_passed": bool(base_guardrails.get("publish_gate_passed")),
                "product_gate_passed": bool(guardrail.get("passed")),
                "base_rejection_reasons": list(base_guardrails.get("rejection_reasons") or []),
                "product_failed_checks": list(guardrail.get("failed_checks") or []),
                "candidate_metrics": _selected_metrics(candidate_metrics),
                "reference_metrics": _selected_metrics(reference_metrics),
                "metric_deltas": _selected_metrics(
                    comparison.get("metric_deltas") if isinstance(comparison.get("metric_deltas"), dict) else {}
                ),
                "top_feature": feature_guardrail.get("top_feature"),
                "top_feature_group": feature_guardrail.get("top_feature_group"),
                "feature_guardrail_passed": bool(feature_guardrail.get("passed")),
                "score_response_guardrail_passed": bool(score_response.get("passed")),
                "average_critical_drop": score_response.get("average_critical_drop"),
                "average_supporting_drop": score_response.get("average_supporting_drop"),
            }
        )
    return summaries


def validate_d48_keep_current_report(d48_report: Mapping[str, Any]) -> None:
    decision = d48_report.get("decision") if isinstance(d48_report.get("decision"), dict) else {}
    recommendation = decision.get("publish_recommendation")
    if recommendation not in KEEP_CURRENT_RECOMMENDATIONS:
        raise ValueError(
            "D49 no-publish path requires D48 keep-current recommendation, "
            f"got {recommendation!r}."
        )
    product_guardrails = (
        d48_report.get("product_guardrails") if isinstance(d48_report.get("product_guardrails"), dict) else {}
    )
    passing_candidates = [
        str(candidate_name)
        for candidate_name, guardrail in product_guardrails.items()
        if isinstance(guardrail, dict) and guardrail.get("passed") is True
    ]
    if passing_candidates:
        raise ValueError(
            "D49 no-publish path expects no candidate to pass product-critical guardrails: "
            + ", ".join(passing_candidates)
        )
    production = d48_report.get("production_artifact") if isinstance(d48_report.get("production_artifact"), dict) else {}
    if production.get("changed_by_d48") is True:
        raise ValueError("D49 no-publish path requires D48 to leave production artifact unchanged.")


def _verification_summary(check_results: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    checks = [dict(check) for check in (check_results or [])]
    if not checks:
        return {"status": "pending", "checks": [], "reason": "checks_not_recorded"}
    failed = [check for check in checks if check.get("status") != "passed"]
    return {"status": "passed" if not failed else "failed", "checks": checks}


def _build_d49_rollback_reference(production_state: Mapping[str, Any]) -> dict[str, Any]:
    rollback_reference = build_versioned_reference_state(dict(production_state))
    rollback_reference["rollback_reason"] = (
        "D49 did not publish a dataset-v4 candidate; the current production alias remains selected."
    )
    return rollback_reference


def build_d49_no_publish_report(
    *,
    d48_report: Mapping[str, Any],
    d48_report_path: str | Path,
    production_state: Mapping[str, Any],
    production_sha1_before: str,
    production_sha1_after: str,
    verification: Mapping[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    validate_d48_keep_current_report(d48_report)
    d48_decision = d48_report.get("decision") if isinstance(d48_report.get("decision"), dict) else {}
    shadow = d48_report.get("shadow_benchmark") if isinstance(d48_report.get("shadow_benchmark"), dict) else {}
    reference = shadow.get("reference_model") if isinstance(shadow.get("reference_model"), dict) else {}
    reference_metrics = reference.get("metrics") if isinstance(reference.get("metrics"), dict) else {}
    production_model_info = (
        production_state.get("model_info") if isinstance(production_state.get("model_info"), dict) else {}
    )
    return {
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "task": "D49",
        "decision": {
            "decision": "keep_current",
            "publish_action": "no_publish",
            "reason": "d48_no_candidate_passed_product_critical_guardrails",
            "d48_publish_recommendation": d48_decision.get("publish_recommendation"),
            "d48_reason": d48_decision.get("reason"),
            "selected_candidate": None,
            "selected_runtime_artifact": dict(production_state),
            "production_artifact_sha1_before": production_sha1_before,
            "production_artifact_sha1_after": production_sha1_after,
            "production_artifact_unchanged": production_sha1_before == production_sha1_after,
        },
        "d48_evidence": {
            "d48_report_path": str(Path(d48_report_path)),
            "dataset_version": d48_report.get("dataset_version"),
            "reference_metrics": _selected_metrics(reference_metrics),
            "metric_deltas_by_candidate": d48_report.get("metric_deltas_by_candidate"),
            "decision": dict(d48_decision),
        },
        "candidate_decisions": _summarize_candidate_decisions(d48_report),
        "rollback_reference": _build_d49_rollback_reference(production_state),
        "verification": dict(verification),
        "invariants": {
            "production_model_path": production_state["model_path"],
            "production_model_sha1": production_state["model_sha1"],
            "runtime_dataset_version": production_model_info.get("dataset_version"),
            "runtime_model_schema_version": production_model_info.get("model_schema_version"),
            "candidate_artifacts_are_not_runtime_selected": True,
            "next_modeling_step_requires_new_task": True,
        },
    }


def _inline_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_d49_no_publish_markdown(report: Mapping[str, Any]) -> str:
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    selected_artifact = (
        decision.get("selected_runtime_artifact") if isinstance(decision.get("selected_runtime_artifact"), dict) else {}
    )
    model_info = selected_artifact.get("model_info") if isinstance(selected_artifact.get("model_info"), dict) else {}
    d48 = report.get("d48_evidence") if isinstance(report.get("d48_evidence"), dict) else {}
    rollback = report.get("rollback_reference") if isinstance(report.get("rollback_reference"), dict) else {}
    verification = report.get("verification") if isinstance(report.get("verification"), dict) else {}
    lines = [
        "# D49 No-Publish Decision",
        "",
        f"- Decision: `{decision.get('decision')}`",
        f"- Publish action: `{decision.get('publish_action')}`",
        f"- Reason: `{decision.get('reason')}`",
        f"- D48 recommendation: `{decision.get('d48_publish_recommendation')}`",
        f"- D48 reason: `{decision.get('d48_reason')}`",
        f"- Production SHA1 before: `{decision.get('production_artifact_sha1_before')}`",
        f"- Production SHA1 after: `{decision.get('production_artifact_sha1_after')}`",
        f"- Production artifact unchanged: `{decision.get('production_artifact_unchanged')}`",
        "",
        "## Selected Runtime Artifact",
        "",
        f"- Path: `{selected_artifact.get('model_path')}`",
        f"- SHA1: `{selected_artifact.get('model_sha1')}`",
        f"- Artifact version: `{model_info.get('artifact_version')}`",
        f"- Dataset version: `{model_info.get('dataset_version')}`",
        f"- Model schema version: `{model_info.get('model_schema_version')}`",
        f"- Model type: `{model_info.get('model_type')}`",
        f"- Feature count: `{model_info.get('feature_count')}`",
        "",
        "## D48 Evidence",
        "",
        f"- D48 report: `{d48.get('d48_report_path')}`",
        f"- Dataset version: `{d48.get('dataset_version')}`",
        f"- Reference metrics: `{_inline_json(d48.get('reference_metrics'))}`",
        f"- D48 decision: `{_inline_json(d48.get('decision'))}`",
        "",
        "## Candidate Decisions",
        "",
    ]
    for candidate in report.get("candidate_decisions", []):
        if not isinstance(candidate, dict):
            continue
        failed_checks = ", ".join(str(item) for item in candidate.get("product_failed_checks", [])) or "none"
        rejection_reasons = ", ".join(str(item) for item in candidate.get("base_rejection_reasons", [])) or "none"
        lines.extend(
            [
                f"### {candidate.get('candidate_name')}",
                f"- Publish allowed: `{candidate.get('publish_allowed')}`",
                f"- Shadow gate passed: `{candidate.get('shadow_gate_passed')}`",
                f"- Product gate passed: `{candidate.get('product_gate_passed')}`",
                f"- Base rejection reasons: `{rejection_reasons}`",
                f"- Product failed checks: `{failed_checks}`",
                f"- Candidate metrics: `{_inline_json(candidate.get('candidate_metrics'))}`",
                f"- Metric deltas: `{_inline_json(candidate.get('metric_deltas'))}`",
                f"- Top feature: `{candidate.get('top_feature')}` (`{candidate.get('top_feature_group')}`)",
                f"- Critical/supporting drop: `{candidate.get('average_critical_drop')}` / `{candidate.get('average_supporting_drop')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Rollback Reference",
            "",
            f"- Rollback required: `{rollback.get('rollback_required')}`",
            f"- Reason: {rollback.get('rollback_reason')}",
            f"- Current alias path: `{rollback.get('current_alias_model_path')}`",
            f"- Current alias SHA1: `{rollback.get('current_alias_model_sha1')}`",
            f"- Versioned reference path: `{rollback.get('versioned_reference_model_path')}`",
            f"- Versioned reference available: `{rollback.get('versioned_reference_model_available')}`",
            "",
            "## Verification",
            "",
            f"- Overall status: `{verification.get('status')}`",
        ]
    )
    for check in verification.get("checks", []):
        if isinstance(check, dict):
            lines.append(f"- `{check.get('name')}`: `{check.get('status')}`")
    return "\n".join(lines).strip() + "\n"


def write_d49_no_publish_report(
    report: Mapping[str, Any],
    *,
    json_path: str | Path = DEFAULT_D49_REPORT_JSON_PATH,
    markdown_path: str | Path = DEFAULT_D49_REPORT_MD_PATH,
) -> dict[str, str]:
    resolved_json_path = Path(json_path)
    resolved_markdown_path = Path(markdown_path)
    resolved_json_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    paths = {"json_path": str(resolved_json_path), "markdown_path": str(resolved_markdown_path)}
    report_with_paths = {**dict(report), "report_paths": paths}
    resolved_json_path.write_text(json.dumps(report_with_paths, ensure_ascii=False, indent=2), encoding="utf-8")
    resolved_markdown_path.write_text(render_d49_no_publish_markdown(report_with_paths), encoding="utf-8")
    return paths


def run_d49_no_publish_decision(
    *,
    d48_report_path: str | Path = DEFAULT_D48_REPORT_JSON_PATH,
    production_model_path: str | Path = DEFAULT_MODEL_PATH,
    report_json_path: str | Path = DEFAULT_D49_REPORT_JSON_PATH,
    report_markdown_path: str | Path = DEFAULT_D49_REPORT_MD_PATH,
    check_results: Sequence[Mapping[str, Any]] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    production_sha1_before = sha1_file(production_model_path)
    d48_report = load_json_object(d48_report_path)
    production_state = build_production_artifact_state(production_model_path)
    verification = _verification_summary(check_results)
    production_sha1_after = sha1_file(production_model_path)
    if production_sha1_before != production_sha1_after:
        raise RuntimeError(
            f"Production artifact changed while generating D49 evidence: "
            f"{production_sha1_before} -> {production_sha1_after}"
        )
    report = build_d49_no_publish_report(
        d48_report=d48_report,
        d48_report_path=d48_report_path,
        production_state=production_state,
        production_sha1_before=production_sha1_before,
        production_sha1_after=production_sha1_after,
        verification=verification,
        generated_at=generated_at,
    )
    report_paths = write_d49_no_publish_report(
        report,
        json_path=report_json_path,
        markdown_path=report_markdown_path,
    )
    return {**report, "report_paths": report_paths}


def _parse_check_result(value: str) -> dict[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("Check result must use NAME=STATUS format.")
    name, status = value.split("=", 1)
    if not name.strip() or not status.strip():
        raise argparse.ArgumentTypeError("Check result must use non-empty NAME=STATUS format.")
    return {"name": name.strip(), "status": status.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Record D49 no-publish decision from D48 evidence.")
    parser.add_argument("--d48-report", default=str(DEFAULT_D48_REPORT_JSON_PATH))
    parser.add_argument("--production-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--report-json", default=str(DEFAULT_D49_REPORT_JSON_PATH))
    parser.add_argument("--report-md", default=str(DEFAULT_D49_REPORT_MD_PATH))
    parser.add_argument("--check", action="append", type=_parse_check_result, default=[])
    args = parser.parse_args()
    report = run_d49_no_publish_decision(
        d48_report_path=args.d48_report,
        production_model_path=args.production_model,
        report_json_path=args.report_json,
        report_markdown_path=args.report_md,
        check_results=args.check,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
