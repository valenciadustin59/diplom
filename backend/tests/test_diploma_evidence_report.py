from __future__ import annotations

from pathlib import Path

from app.ml.diploma_evidence_report import run_d87_diploma_evidence_report


def test_d87_diploma_evidence_report_links_current_runtime_and_guardrails(tmp_path: Path) -> None:
    report = run_d87_diploma_evidence_report(
        report_path=tmp_path / "d87.json",
        markdown_path=tmp_path / "d87.md",
    )

    assert report["status"] == "passed"
    assert report["decision"] == "ready_for_diploma_evidence_pack"
    assert report["active_model"]["dataset_version"] == "dataset-v7-final"
    assert report["active_model"]["model_schema_version"] == "v4"
    assert report["checks"]["d84_relevance_regression_passed"] is True
    assert report["checks"]["d85_competitor_robustness_passed"] is True
    assert report["evidence"]["query_relevance_regression"]["failed_cases_count"] == 0
