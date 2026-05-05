from __future__ import annotations

import json
from pathlib import Path

from app.ml.live_relevance_regression import (
    D84_REGRESSION_VERSION,
    build_d84_relevance_regression_cases,
    run_d84_live_relevance_regression,
)


def test_d84_regression_pack_covers_query_relevance_risk_groups() -> None:
    cases = build_d84_relevance_regression_cases()
    groups = {case["group"] for case in cases}

    assert len(cases) == 40
    assert groups == {
        "commercial_modifier_not_required_when_core_matches",
        "full_mismatch",
        "near_topic_wrong_object",
        "partial_match",
        "strong_match",
        "unusable",
    }
    assert len({case["query"] for case in cases}) >= 20
    assert not any("pzpo" in case["page_hint"].lower() or "winemore" in case["page_hint"].lower() for case in cases)


def test_d84_regression_pack_passes_current_runtime_contract(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.json"
    report_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"

    report = run_d84_live_relevance_regression(
        cases_path=cases_path,
        report_path=report_path,
        markdown_path=markdown_path,
    )
    stored_report = json.loads(report_path.read_text(encoding="utf-8"))
    stored_cases = json.loads(cases_path.read_text(encoding="utf-8"))

    assert report["version"] == D84_REGRESSION_VERSION
    assert report["status"] == "passed"
    assert report["failed_cases_count"] == 0
    assert stored_report["status"] == "passed"
    assert stored_cases["cases_count"] == report["cases_count"]
    assert markdown_path.read_text(encoding="utf-8").startswith("# D84")
