from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def render_shadow_benchmark_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# D35 Shadow Benchmark And Guardrails",
        "",
        f"- Dataset path: `{report.get('dataset_path')}`",
        f"- Dataset version: `{report.get('dataset_version')}`",
        f"- Split mode: `{report.get('split', {}).get('split_mode')}`",
        f"- Validation rows: `{report.get('split', {}).get('validation_rows_count')}`",
        f"- Publish recommendation: `{report.get('decision', {}).get('publish_recommendation')}`",
        f"- Decision reason: `{report.get('decision', {}).get('reason')}`",
        "",
        "## Reference",
        "",
    ]
    reference_model = report.get("reference_model") if isinstance(report.get("reference_model"), dict) else {}
    reference_metrics = reference_model.get("metrics") if isinstance(reference_model.get("metrics"), dict) else {}
    lines.extend(
        [
            f"- Path: `{reference_model.get('model_path')}`",
            f"- Model type: `{reference_model.get('model_type')}`",
            f"- Spearman mean: `{reference_metrics.get('spearman_mean')}`",
            f"- NDCG@10: `{reference_metrics.get('ndcg_at_10')}`",
            f"- Top-3 hit rate: `{reference_metrics.get('top_3_hit_rate')}`",
            f"- MAE: `{reference_metrics.get('mae')}`",
            "",
            "## Candidate Gate Results",
            "",
        ]
    )
    for comparison in report.get("candidate_comparisons", []):
        if not isinstance(comparison, dict):
            continue
        candidate_metrics = comparison.get("candidate_metrics") if isinstance(comparison.get("candidate_metrics"), dict) else {}
        guardrails = comparison.get("guardrails") if isinstance(comparison.get("guardrails"), dict) else {}
        lines.extend(
            [
                f"### {comparison.get('candidate_name')}",
                f"- Publish gate passed: `{guardrails.get('publish_gate_passed')}`",
                f"- Rejection reasons: `{', '.join(guardrails.get('rejection_reasons') or []) or 'none'}`",
                f"- Spearman mean: `{candidate_metrics.get('spearman_mean')}`",
                f"- NDCG@10: `{candidate_metrics.get('ndcg_at_10')}`",
                f"- Top-3 hit rate: `{candidate_metrics.get('top_3_hit_rate')}`",
                f"- MAE: `{candidate_metrics.get('mae')}`",
            ]
        )
        for metric_name, delta in (comparison.get("metric_deltas") or {}).items():
            lines.append(f"- Delta `{metric_name}`: `{delta}`")
        lines.append("")

    smoke_summary = report.get("smoke_explainability") if isinstance(report.get("smoke_explainability"), dict) else {}
    lines.extend(
        [
            "## Smoke Explainability",
            "",
            f"- Requested queries: `{smoke_summary.get('requested_queries_count')}`",
            f"- Covered queries: `{smoke_summary.get('covered_queries_count')}`",
            f"- Exact query matches: `{smoke_summary.get('exact_match_queries_count')}`",
            f"- Fallback query matches: `{smoke_summary.get('fallback_match_queries_count')}`",
            f"- Missing queries: `{smoke_summary.get('missing_queries_count')}`",
            "",
        ]
    )
    for query_result in smoke_summary.get("query_results", []):
        if isinstance(query_result, dict):
            lines.append(
                f"- `{query_result.get('requested_query')}` -> `{query_result.get('matched_query')}` "
                f"({query_result.get('match_strategy')}, `{query_result.get('status')}`)"
            )
    sensibility = report.get("explainability_sensibility") if isinstance(report.get("explainability_sensibility"), dict) else {}
    lines.extend(["", "## Explainability Sensibility", "", f"- Passed: `{sensibility.get('passed')}`"])
    if sensibility.get("heuristic"):
        lines.append(f"- Heuristic: {sensibility.get('heuristic')}")
    model_guardrails = sensibility.get("model_guardrails") if isinstance(sensibility.get("model_guardrails"), dict) else {}
    for model_name, guardrail in model_guardrails.items():
        if isinstance(guardrail, dict):
            failed_checks = [
                check_name
                for check_name, passed in (guardrail.get("checks") or {}).items()
                if isinstance(passed, bool) and not passed
            ]
            lines.append(f"- `{model_name}`: passed `{guardrail.get('passed')}`, failed checks `{failed_checks or 'none'}`")
    return "\n".join(lines).strip() + "\n"


def write_shadow_benchmark_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    json_path = resolved_output_dir / "shadow-benchmark-guardrails-report.json"
    markdown_path = resolved_output_dir / "shadow-benchmark-guardrails-report.md"
    report_paths = {"json_path": str(json_path), "markdown_path": str(markdown_path)}
    report_with_paths = {**report, "report_paths": report_paths}
    json_path.write_text(json.dumps(report_with_paths, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_shadow_benchmark_markdown(report_with_paths), encoding="utf-8")
    return report_paths
