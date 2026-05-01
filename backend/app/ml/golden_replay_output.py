from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GOLDEN_REPLAY_JSON_NAME = "golden-replay-report.json"
GOLDEN_REPLAY_MARKDOWN_NAME = "golden-replay-report.md"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def render_golden_replay_markdown(report: dict[str, Any]) -> str:
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    model_status = report.get("model_status") if isinstance(report.get("model_status"), dict) else {}
    model = model_status.get("model") if isinstance(model_status.get("model"), dict) else {}
    dataset = model_status.get("dataset") if isinstance(model_status.get("dataset"), dict) else {}
    rollback = report.get("rollback_reference") if isinstance(report.get("rollback_reference"), dict) else {}
    summary = report.get("guardrail_summary") if isinstance(report.get("guardrail_summary"), dict) else {}
    evidence_summary = report.get("evidence_summary") if isinstance(report.get("evidence_summary"), dict) else {}

    lines = [
        "# D41 Golden Query Replay Guardrails",
        "",
        "## Summary",
        "",
        f"- Mode: `{report.get('mode')}`",
        f"- Generated at: `{report.get('generated_at')}`",
        f"- Decision: `{decision.get('status')}`",
        f"- Recommendation: {decision.get('recommendation')}",
        f"- Active model: `{model.get('model_type')}` / schema `{model.get('model_schema_version')}`",
        f"- Dataset: `{dataset.get('dataset_version')}`",
        f"- Artifact: `{model.get('artifact_version')}`",
        f"- Artifact SHA1: `{model_status.get('artifact_sha1')}`",
        f"- Rollback available: `{rollback.get('available')}`",
        f"- Rollback SHA1: `{rollback.get('model_sha1') or rollback.get('artifact_sha1')}`",
        f"- Evidence kinds: `{json.dumps(evidence_summary.get('kind_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Guardrail Summary",
        "",
        f"- Items: `{summary.get('item_count')}`",
        f"- Passed items: `{summary.get('passed_items')}`",
        f"- Warning items: `{summary.get('warning_items')}`",
        f"- Failed items: `{summary.get('failed_items')}`",
        f"- Guardrail counts: `{json.dumps(summary.get('guardrail_counts', {}), ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Replay Items",
        "",
        "| ID | Query | Status | Score | Competitors | Recommendations | Decision |",
        "| --- | --- | --- | ---: | --- | ---: | --- |",
    ]
    for item in report.get("items", []):
        if not isinstance(item, dict):
            continue
        counts = item.get("competitor_counts") if isinstance(item.get("competitor_counts"), dict) else {}
        lines.append(
            "| {id} | {query} | {status} | {score} | {analyzed}/{found} analyzed, {failed} failed | {recommendations} | {decision} |".format(
                id=item.get("id"),
                query=item.get("query"),
                status=item.get("audit_status"),
                score=item.get("score"),
                analyzed=counts.get("analyzed"),
                found=counts.get("found"),
                failed=counts.get("failed"),
                recommendations=item.get("recommendations_count"),
                decision=item.get("decision", {}).get("status") if isinstance(item.get("decision"), dict) else None,
            )
        )

    lines.extend(["", "## Item Guardrails", ""])
    for item in report.get("items", []):
        if not isinstance(item, dict):
            continue
        lines.extend([f"### {item.get('id')}", ""])
        lines.append(f"- Evidence kind: `{item.get('evidence_kind')}`")
        if item.get("fixture_note"):
            lines.append(f"- Fixture note: {item.get('fixture_note')}")
        for guardrail in item.get("guardrails", []):
            if not isinstance(guardrail, dict):
                continue
            lines.append(f"- `{guardrail.get('name')}`: `{guardrail.get('status')}` - {guardrail.get('detail')}")
        reference = item.get("reference_comparison") if isinstance(item.get("reference_comparison"), dict) else None
        if reference:
            lines.append(
                f"- Reference comparison: `{reference.get('label')}`, score delta `{reference.get('score_delta')}`"
            )
        lines.append("")

    lines.extend(
        [
            "## Invariants",
            "",
            "- This workflow does not publish a model.",
            "- This workflow does not roll back a model.",
            "- This workflow does not mutate `backend/artifacts/page_quality_model.pkl`.",
            "- Default mode evaluates stored deterministic evidence and does not require live network.",
            "",
        ]
    )
    return "\n".join(lines)


def write_golden_replay_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    json_path = resolved_output_dir / GOLDEN_REPLAY_JSON_NAME
    markdown_path = resolved_output_dir / GOLDEN_REPLAY_MARKDOWN_NAME
    report_paths = {"json_path": str(json_path), "markdown_path": str(markdown_path)}
    report_with_paths = {**report, "report_paths": report_paths}
    _write_json(json_path, report_with_paths)
    markdown_path.write_text(render_golden_replay_markdown(report_with_paths), encoding="utf-8")
    return report_paths
