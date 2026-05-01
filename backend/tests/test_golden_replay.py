import json

from app.ml.golden_replay import (
    build_golden_replay_report,
    default_golden_query_catalog,
    evaluate_replay_guardrails,
    write_golden_replay_report,
)


MODEL_STATUS = {
    "status": "active",
    "checked_at": "2026-05-02T00:00:00+00:00",
    "artifact_path": "artifacts/page_quality_model.pkl",
    "artifact_sha1": "29c4b29455f795a535da94b2c6f36ef603d003eb",
    "model": {
        "model_type": "CatBoostRegressor",
        "model_schema_version": "v3",
        "artifact_version": "dataset-v3-d37-20260501200434",
        "feature_count": 148,
    },
    "dataset": {"dataset_version": "dataset-v3-d37"},
    "publish": {"selected_candidate": "pointwise_catboost"},
    "rollback": {
        "available": True,
        "model_sha1": "5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9",
    },
}
MODEL_INFO = {
    "model_type": "CatBoostRegressor",
    "model_schema_version": "v3",
    "artifact_version": "dataset-v3-d37-20260501200434",
    "dataset_version": "dataset-v3-d37",
    "source": "local_dataset",
}


def test_build_golden_replay_report_passes_with_complete_stored_evidence():
    catalog = [
        {
            "id": "golden-1",
            "query": "seo audit",
            "target_url": "https://example.com/seo-audit",
            "domain": "seo_services",
        }
    ]
    evidence = [
        {
            "id": "golden-1",
            "audit_id": "audit-1",
            "status": "completed",
            "score": 72.4,
            "model_info": MODEL_INFO,
            "competitors_found": 2,
            "competitors_analyzed": 2,
            "competitors_failed": 0,
            "recommendations_count": 4,
            "warnings": [],
            "reference": {"label": "rollback", "score": 68.0, "model_schema_version": "v1"},
        }
    ]

    report = build_golden_replay_report(
        catalog,
        evidence,
        model_status=MODEL_STATUS,
        generated_at="2026-05-02T00:00:00+00:00",
    )

    assert report["decision"]["status"] == "passed"
    assert report["guardrail_summary"]["passed_items"] == 1
    assert report["guardrail_summary"]["failed_items"] == 0
    item = report["items"][0]
    assert item["model_info"]["artifact_version"] == "dataset-v3-d37-20260501200434"
    assert item["reference_comparison"]["score_delta"] == 4.4
    assert {guardrail["status"] for guardrail in item["guardrails"]} == {"pass"}


def test_evaluate_replay_guardrails_reports_failures_for_bad_evidence():
    guardrails = evaluate_replay_guardrails(
        {
            "audit_status": "failed",
            "score": 120.0,
            "model_info": {},
            "competitor_counts": {"found": 2, "analyzed": 0, "failed": 2},
            "recommendations_count": 0,
            "warnings": [],
        },
        active_model_identity={
            "artifact_version": "dataset-v3-d37-20260501200434",
            "model_schema_version": "v3",
            "dataset_version": "dataset-v3-d37",
            "model_type": "CatBoostRegressor",
        },
    )
    failed = {guardrail["name"] for guardrail in guardrails if guardrail["status"] == "fail"}

    assert {
        "audit_status",
        "score_boundedness",
        "competitor_coverage",
        "recommendation_availability",
        "model_metadata_presence",
    }.issubset(failed)


def test_golden_replay_report_keeps_runtime_warnings_as_warning_not_publish_action():
    catalog = default_golden_query_catalog()[:1]
    evidence = [
        {
            "id": catalog[0]["id"],
            "status": "completed_with_warnings",
            "score": 81.0,
            "model_info": MODEL_INFO,
            "competitors_found": 2,
            "competitors_analyzed": 2,
            "competitors_failed": 0,
            "recommendations_count": 3,
            "warnings": ["One competitor blocked browser fetch."],
        }
    ]

    report = build_golden_replay_report(catalog, evidence, model_status=MODEL_STATUS)

    assert report["decision"]["status"] == "warning"
    assert report["guardrail_summary"]["warning_items"] == 1
    assert any(
        guardrail["name"] == "runtime_warnings" and guardrail["status"] == "warn"
        for guardrail in report["items"][0]["guardrails"]
    )
    assert report["invariants"]["publishes_model"] is False
    assert report["invariants"]["rolls_back_model"] is False


def test_write_golden_replay_report_creates_json_and_markdown(tmp_path):
    report = build_golden_replay_report(
        default_golden_query_catalog()[:1],
        [
            {
                "id": "renovation-moscow",
                "status": "completed",
                "score": 83.7,
                "model_info": MODEL_INFO,
                "competitors_found": 2,
                "competitors_analyzed": 2,
                "competitors_failed": 0,
                "recommendations_count": 11,
                "warnings": [],
            }
        ],
        model_status=MODEL_STATUS,
    )

    paths = write_golden_replay_report(report, tmp_path)

    json_path = tmp_path / "golden-replay-report.json"
    markdown_path = tmp_path / "golden-replay-report.md"
    assert paths == {"json_path": str(json_path), "markdown_path": str(markdown_path)}
    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["task"] == "D41"
    assert saved["report_paths"] == paths
    assert "# D41 Golden Query Replay Guardrails" in markdown_path.read_text(encoding="utf-8")
    assert not (tmp_path / "page_quality_model.pkl").exists()
