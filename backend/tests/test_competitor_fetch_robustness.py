from __future__ import annotations

from pathlib import Path

from app.ml.competitor_fetch_robustness import (
    build_d85_competitor_fetch_cases,
    run_d85_competitor_fetch_robustness,
)


def test_d85_competitor_fetch_cases_cover_blocked_and_partial_contexts() -> None:
    cases = build_d85_competitor_fetch_cases()
    statuses = {case["expected"]["competitor_context_status"] for case in cases}

    assert len(cases) == 5
    assert statuses == {
        "insufficient_processed_competitors",
        "no_serp_results",
        "partial_but_usable",
        "ready",
    }


def test_d85_competitor_fetch_robustness_report_passes(tmp_path: Path) -> None:
    report = run_d85_competitor_fetch_robustness(
        report_path=tmp_path / "d85.json",
        markdown_path=tmp_path / "d85.md",
    )

    assert report["status"] == "passed"
    assert report["failed_cases_count"] == 0
    assert report["decision"] == "competitor_context_is_explicit_and_no_fake_market_average"
