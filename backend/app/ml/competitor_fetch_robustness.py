from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.competitors import build_comparison_summary


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "D85"
D85_REPORT_VERSION = "d85-competitor-fetch-robustness-v1"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "backend" / "artifacts" / "ranking-benchmarks" / "dataset-v7-final-d85"
DEFAULT_REPORT_JSON_PATH = DEFAULT_OUTPUT_DIR / "d85-competitor-fetch-robustness-report.json"
DEFAULT_REPORT_MD_PATH = DEFAULT_OUTPUT_DIR / "d85-competitor-fetch-robustness-report.md"


def _competitor(score: float) -> dict[str, object]:
    return {
        "url": f"https://competitor-{int(score)}.example/",
        "domain": f"competitor-{int(score)}.example",
        "fetch_status": "success",
        "score": score,
        "features": {
            "semantic_similarity": 0.82,
            "query_core_keyword_coverage_ratio": 1.0,
        },
    }


def _failed(code: str) -> dict[str, object]:
    return {
        "url": f"https://blocked-{code}.example/",
        "domain": f"blocked-{code}.example",
        "fetch_status": "failed",
        "fetch_error_code": code,
        "fetch_error_message": code,
        "score": None,
        "features": None,
    }


def _case(
    *,
    case_id: str,
    competitor_results: list[dict[str, object]],
    expected_status: str,
    expected_average_available: bool,
    requested_top_n: int = 5,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "requested_top_n": requested_top_n,
        "competitor_results": competitor_results,
        "expected": {
            "competitor_context_status": expected_status,
            "average_available": expected_average_available,
        },
    }


def build_d85_competitor_fetch_cases() -> list[dict[str, Any]]:
    return [
        _case(
            case_id="d85-ready-all-processed",
            competitor_results=[_competitor(82.0), _competitor(87.0), _competitor(79.0)],
            expected_status="ready",
            expected_average_available=True,
        ),
        _case(
            case_id="d85-partial-but-usable",
            competitor_results=[_competitor(82.0), _competitor(87.0), _failed("http_403")],
            expected_status="partial_but_usable",
            expected_average_available=True,
        ),
        _case(
            case_id="d85-insufficient-one-processed",
            competitor_results=[_competitor(82.0), _failed("browser_blocked"), _failed("timeout")],
            expected_status="insufficient_processed_competitors",
            expected_average_available=False,
        ),
        _case(
            case_id="d85-all-blocked",
            competitor_results=[_failed("http_403"), _failed("browser_blocked"), _failed("timeout")],
            expected_status="insufficient_processed_competitors",
            expected_average_available=False,
        ),
        _case(
            case_id="d85-no-serp-results",
            competitor_results=[],
            expected_status="no_serp_results",
            expected_average_available=False,
        ),
    ]


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    summary = build_comparison_summary(
        user_features={"semantic_similarity": 0.74},
        user_score=76.0,
        competitor_results=list(case["competitor_results"]),
        requested_top_n=int(case["requested_top_n"]),
    )
    expected = case["expected"]
    failures: list[str] = []
    if summary["competitor_context_status"] != expected["competitor_context_status"]:
        failures.append("competitor_context_status")
    average_available = summary["competitors_average_score"] is not None
    if average_available != expected["average_available"]:
        failures.append("average_available")
    if summary["score_difference"] is not None and not average_available:
        failures.append("fake_score_difference")

    return {
        "id": case["id"],
        "status": "pass" if not failures else "fail",
        "failed_checks": failures,
        "competitor_context_status": summary["competitor_context_status"],
        "score_basis": summary["score_basis"],
        "competitors_average_score": summary["competitors_average_score"],
        "score_difference": summary["score_difference"],
        "competitor_context_quality": summary["competitor_context_quality"],
    }


def run_d85_competitor_fetch_robustness(
    *,
    report_path: Path = DEFAULT_REPORT_JSON_PATH,
    markdown_path: Path = DEFAULT_REPORT_MD_PATH,
) -> dict[str, Any]:
    cases = build_d85_competitor_fetch_cases()
    results = [_evaluate_case(case) for case in cases]
    failed = [result for result in results if result["status"] != "pass"]
    report: dict[str, Any] = {
        "task": TASK_ID,
        "version": D85_REPORT_VERSION,
        "status": "passed" if not failed else "failed",
        "cases_count": len(cases),
        "failed_cases_count": len(failed),
        "failed_cases": failed,
        "results": results,
        "decision": (
            "competitor_context_is_explicit_and_no_fake_market_average"
            if not failed
            else "review_competitor_context_quality_failures"
        ),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown_report(report), encoding="utf-8")
    return report


def _render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# D85 Competitor Fetch Robustness",
        "",
        f"- Status: `{report['status']}`",
        f"- Cases: `{report['cases_count']}`",
        f"- Failed cases: `{report['failed_cases_count']}`",
        f"- Decision: `{report['decision']}`",
        "",
        "## Case Results",
        "",
    ]
    for result in report["results"]:
        lines.append(
            f"- `{result['id']}`: `{result['status']}`, "
            f"context `{result['competitor_context_status']}`, score basis `{result['score_basis']}`"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run D85 competitor fetch robustness checks.")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_JSON_PATH)
    parser.add_argument("--markdown-path", type=Path, default=DEFAULT_REPORT_MD_PATH)
    args = parser.parse_args()
    report = run_d85_competitor_fetch_robustness(report_path=args.report_path, markdown_path=args.markdown_path)
    print(json.dumps({"status": report["status"], "cases_count": report["cases_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
