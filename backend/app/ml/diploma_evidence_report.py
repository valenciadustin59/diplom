from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.ml.competitor_fetch_robustness import DEFAULT_REPORT_JSON_PATH as D85_REPORT_JSON_PATH
from app.ml.final_query_competitiveness import D83_RELEASE_JSON_PATH
from app.ml.live_relevance_regression import DEFAULT_REPORT_JSON_PATH as D84_REPORT_JSON_PATH
from app.ml.model import DEFAULT_MODEL_PATH, load_model_artifact
from app.ml.no_publish_decision import sha1_file


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "D87"
D87_REPORT_VERSION = "d87-diploma-evidence-v1"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "backend" / "artifacts" / "ranking-benchmarks" / "dataset-v7-final-d87"
DEFAULT_REPORT_JSON_PATH = DEFAULT_OUTPUT_DIR / "d87-diploma-evidence-report.json"
DEFAULT_REPORT_MD_PATH = DEFAULT_OUTPUT_DIR / "d87-diploma-evidence-report.md"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "missing", "path": str(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def run_d87_diploma_evidence_report(
    *,
    report_path: Path = DEFAULT_REPORT_JSON_PATH,
    markdown_path: Path = DEFAULT_REPORT_MD_PATH,
) -> dict[str, Any]:
    active_artifact = load_model_artifact(DEFAULT_MODEL_PATH)
    active_sha1 = sha1_file(DEFAULT_MODEL_PATH) if DEFAULT_MODEL_PATH.exists() else None
    d83 = _read_json(D83_RELEASE_JSON_PATH)
    d84 = _read_json(D84_REPORT_JSON_PATH)
    d85 = _read_json(D85_REPORT_JSON_PATH)
    checks = {
        "active_model_is_v7": bool(active_artifact and active_artifact.get("dataset_version") == "dataset-v7-final"),
        "active_schema_is_v4": bool(active_artifact and active_artifact.get("model_schema_version") == "v4"),
        "d83_controlled_publish_recorded": d83.get("decision") == "published",
        "d84_relevance_regression_passed": d84.get("status") == "passed" and int(d84.get("failed_cases_count") or 0) == 0,
        "d85_competitor_robustness_passed": d85.get("status") == "passed" and int(d85.get("failed_cases_count") or 0) == 0,
    }
    passed = all(checks.values())
    report: dict[str, Any] = {
        "task": TASK_ID,
        "version": D87_REPORT_VERSION,
        "status": "passed" if passed else "failed",
        "decision": "ready_for_diploma_evidence_pack" if passed else "evidence_pack_needs_review",
        "checks": checks,
        "active_model": {
            "path": _display_path(DEFAULT_MODEL_PATH),
            "sha1": active_sha1,
            "dataset_version": active_artifact.get("dataset_version") if active_artifact else None,
            "artifact_version": active_artifact.get("artifact_version") if active_artifact else None,
            "model_schema_version": active_artifact.get("model_schema_version") if active_artifact else None,
            "model_type": active_artifact.get("model_type") if active_artifact else None,
            "feature_count": len(active_artifact.get("feature_columns") or []) if active_artifact else 0,
        },
        "evidence": {
            "controlled_publish": {
                "path": _display_path(D83_RELEASE_JSON_PATH),
                "decision": d83.get("decision"),
                "production_sha1_after": d83.get("production_sha1_after"),
            },
            "query_relevance_regression": {
                "path": _display_path(D84_REPORT_JSON_PATH),
                "status": d84.get("status"),
                "cases_count": d84.get("cases_count"),
                "failed_cases_count": d84.get("failed_cases_count"),
            },
            "competitor_fetch_robustness": {
                "path": _display_path(D85_REPORT_JSON_PATH),
                "status": d85.get("status"),
                "cases_count": d85.get("cases_count"),
                "failed_cases_count": d85.get("failed_cases_count"),
            },
        },
        "product_definition": (
            "The product evaluates whether a chosen page can compete for a concrete search query: "
            "query relevance is checked first, then page quality and competitor context are used when enough SERP pages are processed."
        ),
        "verification_commands": [
            "cd backend && .venv\\Scripts\\python.exe -m pytest tests\\test_live_relevance_regression.py tests\\test_query_relevance_runtime.py tests\\test_final_query_competitiveness.py -q -p no:cacheprovider",
            "cd backend && .venv\\Scripts\\python.exe -m pytest tests\\test_competitiveness_score.py tests\\test_competitors.py tests\\test_competitor_fetch_robustness.py -q -p no:cacheprovider",
            "npm --prefix frontend run test -- --run src/lib/ui.test.tsx src/lib/auditReport.test.ts",
            "npm --prefix frontend run build",
        ],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown_report(report), encoding="utf-8")
    return report


def _render_markdown_report(report: dict[str, Any]) -> str:
    active = report["active_model"]
    evidence = report["evidence"]
    lines = [
        "# D87 Diploma Evidence Report",
        "",
        f"- Status: `{report['status']}`",
        f"- Decision: `{report['decision']}`",
        f"- Active model: `{active['dataset_version']}` / `{active['model_schema_version']}` / `{active['model_type']}`",
        f"- Active SHA1: `{active['sha1']}`",
        "",
        "## Evidence",
        "",
        f"- D83 controlled publish: `{evidence['controlled_publish']['decision']}` at `{evidence['controlled_publish']['path']}`",
        (
            "- D84 query relevance regression: "
            f"`{evidence['query_relevance_regression']['status']}`, "
            f"`{evidence['query_relevance_regression']['cases_count']}` cases, "
            f"`{evidence['query_relevance_regression']['failed_cases_count']}` failed"
        ),
        (
            "- D85 competitor fetch robustness: "
            f"`{evidence['competitor_fetch_robustness']['status']}`, "
            f"`{evidence['competitor_fetch_robustness']['cases_count']}` cases, "
            f"`{evidence['competitor_fetch_robustness']['failed_cases_count']}` failed"
        ),
        "",
        "## Product Definition",
        "",
        str(report["product_definition"]),
        "",
        "## Verification Commands",
        "",
    ]
    lines.extend(f"- `{command}`" for command in report["verification_commands"])
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build D87 diploma evidence report.")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_JSON_PATH)
    parser.add_argument("--markdown-path", type=Path, default=DEFAULT_REPORT_MD_PATH)
    args = parser.parse_args()
    report = run_d87_diploma_evidence_report(report_path=args.report_path, markdown_path=args.markdown_path)
    print(json.dumps({"status": report["status"], "decision": report["decision"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
