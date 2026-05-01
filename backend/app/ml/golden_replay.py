from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.ml.model import ARTIFACTS_DIR
from app.ml.golden_replay_output import (
    render_golden_replay_markdown,
    write_golden_replay_report as _write_golden_replay_report,
)
from app.model_status import build_model_status_payload

DEFAULT_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v3-d41"
DEFAULT_GENERATED_AT = "2026-05-02T00:00:00+00:00"
SUCCESS_AUDIT_STATUSES = {"completed", "completed_with_warnings"}
DEFAULT_GUARDRAIL_THRESHOLDS = {
    "score_min": 0.0,
    "score_max": 100.0,
    "min_competitors_analyzed": 1,
    "min_competitor_coverage_ratio": 0.5,
    "min_recommendations": 1,
}
DEFAULT_RUNTIME_MODEL_INFO = {
    "source": "local_dataset",
    "model_type": "CatBoostRegressor",
    "model_schema_version": "v3",
    "artifact_version": "dataset-v3-d37-20260501200434",
    "artifact_family": "page_quality_model",
    "dataset_version": "dataset-v3-d37",
    "feature_count": 148,
}
DEFAULT_ROLLBACK_REFERENCE = {
    "label": "D38 rollback reference",
    "model_schema_version": "v1",
    "dataset_version": "ru_commercial_dataset-20260421-primary",
    "artifact_sha1": "5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9",
}


def _deepcopy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _safe_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if number == number and number not in (float("inf"), float("-inf")) else None
    return None


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _first_int(*values: Any) -> int | None:
    for value in values:
        number = _safe_int(value)
        if number is not None:
            return number
    return None


def _safe_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _round_metric(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def default_golden_query_catalog() -> list[dict[str, Any]]:
    return _deepcopy_json(
        [
            {
                "id": "renovation-moscow",
                "query": "ремонт квартир москва",
                "target_url": "https://smartremontmsk.ru/",
                "domain": "home_services",
                "description": "D38 post-publish smoke domain for commercial service pages.",
            },
            {
                "id": "plastic-windows-ekaterinburg",
                "query": "пластиковые окна екатеринбург",
                "target_url": "https://example.com/plastic-windows-ekaterinburg",
                "domain": "home_services",
                "description": "Commercial local-service query used throughout API and recommendation tests.",
            },
            {
                "id": "seo-audit",
                "query": "seo audit",
                "target_url": "https://example.com/seo-audit",
                "domain": "seo_services",
                "description": "Generic SEO-audit product query used in backend and frontend regression tests.",
            },
        ]
    )


def default_stored_replay_evidence() -> list[dict[str, Any]]:
    return _deepcopy_json(
        [
            {
                "id": "renovation-moscow",
                "evidence_source": "output/runtime-smoke/d38-smoke-summary.json",
                "audit_id": "690504f2-ca2f-42a6-a012-e622438437a7",
                "status": "completed",
                "score": 83.7366,
                "competitors_found": 2,
                "competitors_analyzed": 2,
                "competitors_failed": 0,
                "recommendations_count": 11,
                "warnings": [],
                "failure_context": None,
                "model_info": DEFAULT_RUNTIME_MODEL_INFO,
                "reference": {
                    **DEFAULT_ROLLBACK_REFERENCE,
                    "score": 69.5249,
                    "source": "D31 clean runtime smoke",
                },
            },
            {
                "id": "plastic-windows-ekaterinburg",
                "evidence_source": "app.ml.golden_replay.default_stored_replay_evidence",
                "audit_id": "stored-d41-plastic-windows-ekaterinburg",
                "status": "completed",
                "score": 78.4,
                "competitors_found": 3,
                "competitors_analyzed": 2,
                "competitors_failed": 1,
                "recommendations_count": 9,
                "warnings": [],
                "failure_context": None,
                "model_info": DEFAULT_RUNTIME_MODEL_INFO,
                "reference": {**DEFAULT_ROLLBACK_REFERENCE, "score": 71.0, "source": "stored rollback expectation"},
            },
            {
                "id": "seo-audit",
                "evidence_source": "app.ml.golden_replay.default_stored_replay_evidence",
                "audit_id": "stored-d41-seo-audit",
                "status": "completed",
                "score": 62.8,
                "competitors_found": 2,
                "competitors_analyzed": 1,
                "competitors_failed": 1,
                "recommendations_count": 7,
                "warnings": [],
                "failure_context": None,
                "model_info": DEFAULT_RUNTIME_MODEL_INFO,
                "reference": {**DEFAULT_ROLLBACK_REFERENCE, "score": 58.2, "source": "stored rollback expectation"},
            },
        ]
    )


def _extract_model_info(record: dict[str, Any]) -> dict[str, Any] | None:
    model_info = record.get("model_info")
    if isinstance(model_info, dict) and model_info:
        return model_info
    score_breakdown = record.get("score_breakdown") if isinstance(record.get("score_breakdown"), dict) else {}
    model_info = score_breakdown.get("model_info")
    return model_info if isinstance(model_info, dict) and model_info else None


def _extract_recommendation_count(record: dict[str, Any]) -> int:
    for key in ("recommendations_count", "recommendation_total"):
        explicit_count = _safe_int(record.get(key))
        if explicit_count is not None:
            return max(explicit_count, 0)

    recommendations = record.get("recommendations")
    if isinstance(recommendations, dict):
        summary = recommendations.get("summary") if isinstance(recommendations.get("summary"), dict) else {}
        summary_count = _safe_int(summary.get("total_recommendations"))
        if summary_count is not None:
            return max(summary_count, 0)
        groups = recommendations.get("groups")
        if isinstance(groups, list):
            return sum(len(group.get("items") or []) for group in groups if isinstance(group, dict))
    if isinstance(recommendations, list):
        return len(recommendations)
    return 0


def _extract_competitor_counts(record: dict[str, Any]) -> dict[str, int]:
    summary = record.get("comparison_summary") if isinstance(record.get("comparison_summary"), dict) else {}
    found = _first_int(record.get("competitors_found"), summary.get("competitors_found"))
    analyzed = _first_int(
        record.get("competitors_analyzed"),
        summary.get("competitors_analyzed"),
        summary.get("competitors_count"),
    )
    failed = _first_int(record.get("competitors_failed"), summary.get("competitors_failed"))

    competitors = record.get("competitor_results") if isinstance(record.get("competitor_results"), list) else []
    if found is None:
        found = len([item for item in competitors if isinstance(item, dict)])
    if analyzed is None:
        analyzed = len([item for item in competitors if isinstance(item, dict) and _safe_float(item.get("score")) is not None])
    if failed is None:
        failed = max(found - analyzed, 0)

    return {"found": max(found, 0), "analyzed": max(analyzed, 0), "failed": max(failed, 0)}


def _normalize_evidence_records(results: list[dict[str, Any]] | dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if results is None:
        return {}
    if isinstance(results, list):
        records = results
    elif isinstance(results.get("items"), list):
        records = results["items"]
    elif isinstance(results.get("evidence"), list):
        records = results["evidence"]
    else:
        records = [
            {**record, "id": record_id}
            for record_id, record in results.items()
            if isinstance(record_id, str) and isinstance(record, dict)
        ]
    return {
        str(record["id"]): dict(record)
        for record in records
        if isinstance(record, dict) and isinstance(record.get("id"), str)
    }


def _active_model_identity(model_status: dict[str, Any] | None) -> dict[str, Any]:
    model = model_status.get("model") if isinstance(model_status, dict) and isinstance(model_status.get("model"), dict) else {}
    dataset = (
        model_status.get("dataset")
        if isinstance(model_status, dict) and isinstance(model_status.get("dataset"), dict)
        else {}
    )
    return {
        "artifact_version": model.get("artifact_version"),
        "model_schema_version": model.get("model_schema_version"),
        "dataset_version": dataset.get("dataset_version") or model.get("dataset_version"),
        "model_type": model.get("model_type"),
    }


def _missing_model_metadata_fields(model_info: dict[str, Any] | None) -> list[str]:
    if not isinstance(model_info, dict):
        return ["model_info"]
    missing = [
        key
        for key in ("model_schema_version", "dataset_version", "model_type")
        if not _safe_str(model_info.get(key))
    ]
    if not (_safe_str(model_info.get("artifact_version")) or _safe_str(model_info.get("artifact_path"))):
        missing.append("artifact_version")
    return missing


def _model_matches_active(model_info: dict[str, Any] | None, active_identity: dict[str, Any]) -> bool | None:
    if not isinstance(model_info, dict) or not active_identity:
        return None
    comparable = {
        key: value
        for key, value in active_identity.items()
        if _safe_str(value) is not None
    }
    if not comparable:
        return None
    return all(model_info.get(key) == value for key, value in comparable.items())


def _guardrail(name: str, status: str, detail: str, observed: Any = None, threshold: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "observed": observed,
        "threshold": threshold,
    }


def _decision_from_guardrails(guardrails: list[dict[str, Any]]) -> dict[str, Any]:
    failed = [guardrail["name"] for guardrail in guardrails if guardrail.get("status") == "fail"]
    warned = [guardrail["name"] for guardrail in guardrails if guardrail.get("status") == "warn"]
    if failed:
        return {"status": "failed", "reasons": failed}
    if warned:
        return {"status": "warning", "reasons": warned}
    return {"status": "passed", "reasons": []}


def evaluate_replay_guardrails(
    item: dict[str, Any],
    *,
    thresholds: dict[str, Any] | None = None,
    active_model_identity: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    resolved_thresholds = {**DEFAULT_GUARDRAIL_THRESHOLDS, **(thresholds or {})}
    audit_status = _safe_str(item.get("audit_status") or item.get("status"))
    score = _safe_float(item.get("score"))
    model_info = item.get("model_info") if isinstance(item.get("model_info"), dict) else None
    competitor_counts = item.get("competitor_counts") if isinstance(item.get("competitor_counts"), dict) else _extract_competitor_counts(item)
    recommendations_count = _first_int(item.get("recommendations_count"))
    if recommendations_count is None:
        recommendations_count = _extract_recommendation_count(item)
    warnings = item.get("warnings") if isinstance(item.get("warnings"), list) else []

    analyzed = int(competitor_counts.get("analyzed") or 0)
    found = int(competitor_counts.get("found") or 0)
    coverage_ratio = analyzed / found if found else 0.0
    missing_metadata = _missing_model_metadata_fields(model_info)
    model_matches_active = _model_matches_active(model_info, active_model_identity or {})

    guardrails = [
        _guardrail(
            "audit_status",
            "pass" if audit_status in SUCCESS_AUDIT_STATUSES else "fail",
            "Audit reached a terminal successful status." if audit_status in SUCCESS_AUDIT_STATUSES else "Audit is missing or failed.",
            observed=audit_status,
            threshold=sorted(SUCCESS_AUDIT_STATUSES),
        ),
        _guardrail(
            "score_boundedness",
            "pass"
            if score is not None
            and resolved_thresholds["score_min"] <= score <= resolved_thresholds["score_max"]
            else "fail",
            "Score is inside the expected 0-100 range.",
            observed=score,
            threshold={"min": resolved_thresholds["score_min"], "max": resolved_thresholds["score_max"]},
        ),
        _guardrail(
            "competitor_coverage",
            "pass"
            if analyzed >= resolved_thresholds["min_competitors_analyzed"]
            and coverage_ratio >= resolved_thresholds["min_competitor_coverage_ratio"]
            else "fail",
            "Enough competitor pages were analyzed for a competitor-aware audit.",
            observed={"found": found, "analyzed": analyzed, "coverage_ratio": _round_metric(coverage_ratio)},
            threshold={
                "min_competitors_analyzed": resolved_thresholds["min_competitors_analyzed"],
                "min_competitor_coverage_ratio": resolved_thresholds["min_competitor_coverage_ratio"],
            },
        ),
        _guardrail(
            "recommendation_availability",
            "pass" if recommendations_count >= resolved_thresholds["min_recommendations"] else "fail",
            "Replay produced at least one recommendation.",
            observed=recommendations_count,
            threshold=resolved_thresholds["min_recommendations"],
        ),
        _guardrail(
            "model_metadata_presence",
            "pass" if not missing_metadata else "fail",
            "Runtime model metadata is present in score_breakdown.model_info.",
            observed={"missing_fields": missing_metadata},
            threshold=["artifact_version", "model_schema_version", "dataset_version", "model_type"],
        ),
        _guardrail(
            "runtime_warnings",
            "warn" if warnings else "pass",
            "Replay completed with runtime warnings." if warnings else "Replay completed without runtime warnings.",
            observed=warnings,
            threshold=[],
        ),
    ]
    if model_matches_active is not None:
        guardrails.append(
            _guardrail(
                "active_model_match",
                "pass" if model_matches_active else "fail",
                "Stored evidence model metadata matches the active /health/model metadata.",
                observed=model_info,
                threshold=active_model_identity,
            )
        )
    return guardrails


def _build_reference_comparison(score: float | None, reference: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(reference, dict) or not reference:
        return None
    reference_score = _safe_float(reference.get("score"))
    return {
        "available": True,
        "label": reference.get("label"),
        "source": reference.get("source"),
        "model_schema_version": reference.get("model_schema_version"),
        "dataset_version": reference.get("dataset_version"),
        "artifact_sha1": reference.get("artifact_sha1"),
        "reference_score": reference_score,
        "current_score": score,
        "score_delta": _round_metric(score - reference_score) if score is not None and reference_score is not None else None,
    }


def _build_replay_item(
    catalog_item: dict[str, Any],
    evidence: dict[str, Any] | None,
    *,
    thresholds: dict[str, Any],
    active_identity: dict[str, Any],
) -> dict[str, Any]:
    record = evidence or {}
    model_info = _extract_model_info(record)
    score = _safe_float(record.get("score"))
    competitor_counts = _extract_competitor_counts(record)
    recommendations_count = _extract_recommendation_count(record)
    warnings = [warning for warning in record.get("warnings", []) if isinstance(warning, str)] if isinstance(record.get("warnings"), list) else []
    item = {
        "id": catalog_item.get("id"),
        "query": catalog_item.get("query"),
        "target_url": catalog_item.get("target_url"),
        "domain": catalog_item.get("domain"),
        "description": catalog_item.get("description"),
        "evidence_source": record.get("evidence_source"),
        "audit_id": record.get("audit_id"),
        "audit_status": _safe_str(record.get("audit_status") or record.get("status")),
        "score": score,
        "model_info": model_info,
        "competitor_counts": competitor_counts,
        "recommendations_count": recommendations_count,
        "warnings": warnings,
        "failure_context": record.get("failure_context") if isinstance(record.get("failure_context"), dict) else None,
        "reference_comparison": _build_reference_comparison(score, record.get("reference") if isinstance(record.get("reference"), dict) else None),
    }
    guardrails = evaluate_replay_guardrails(
        item,
        thresholds=thresholds,
        active_model_identity=active_identity,
    )
    return {
        **item,
        "guardrails": guardrails,
        "decision": _decision_from_guardrails(guardrails),
    }


def _guardrail_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    guardrail_counts = {"pass": 0, "warn": 0, "fail": 0}
    for guardrail in [guardrail for item in items for guardrail in item.get("guardrails", [])]:
        status = guardrail.get("status")
        if status in guardrail_counts:
            guardrail_counts[status] += 1
    return {
        "item_count": len(items),
        "passed_items": sum(1 for item in items if item.get("decision", {}).get("status") == "passed"),
        "warning_items": sum(1 for item in items if item.get("decision", {}).get("status") == "warning"),
        "failed_items": sum(1 for item in items if item.get("decision", {}).get("status") == "failed"),
        "guardrail_counts": guardrail_counts,
    }


def _report_decision(summary: dict[str, Any]) -> dict[str, Any]:
    if summary.get("failed_items", 0) > 0:
        return {
            "status": "failed",
            "recommendation": "Investigate failed golden replay guardrails before any future publish.",
        }
    if summary.get("warning_items", 0) > 0 or summary.get("guardrail_counts", {}).get("warn", 0) > 0:
        return {
            "status": "warning",
            "recommendation": "Review replay warnings, but no automatic rollback is performed.",
        }
    return {
        "status": "passed",
        "recommendation": "Golden replay guardrails passed for the stored post-publish evidence.",
    }


def _model_status_section(model_status: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(model_status, dict):
        return {}
    return {
        "status": model_status.get("status"),
        "checked_at": model_status.get("checked_at"),
        "artifact_path": model_status.get("artifact_path"),
        "artifact_sha1": model_status.get("artifact_sha1"),
        "metadata_path": model_status.get("metadata_path"),
        "metadata_sha1": model_status.get("metadata_sha1"),
        "model": model_status.get("model") if isinstance(model_status.get("model"), dict) else None,
        "dataset": model_status.get("dataset") if isinstance(model_status.get("dataset"), dict) else None,
        "publish": model_status.get("publish") if isinstance(model_status.get("publish"), dict) else {},
        "rollback": model_status.get("rollback") if isinstance(model_status.get("rollback"), dict) else {"available": False},
    }


def build_golden_replay_report(
    catalog: list[dict[str, Any]] | None = None,
    results: list[dict[str, Any]] | dict[str, Any] | None = None,
    *,
    model_status: dict[str, Any] | None = None,
    rollback_reference: dict[str, Any] | None = None,
    generated_at: str | None = DEFAULT_GENERATED_AT,
    thresholds: dict[str, Any] | None = None,
    mode: str = "stored_evidence",
) -> dict[str, Any]:
    resolved_catalog = catalog or default_golden_query_catalog()
    resolved_results = _normalize_evidence_records(results if results is not None else default_stored_replay_evidence())
    resolved_thresholds = {**DEFAULT_GUARDRAIL_THRESHOLDS, **(thresholds or {})}
    resolved_model_status = model_status or {}
    active_identity = _active_model_identity(resolved_model_status)
    items = [
        _build_replay_item(
            catalog_item,
            resolved_results.get(str(catalog_item.get("id"))),
            thresholds=resolved_thresholds,
            active_identity=active_identity,
        )
        for catalog_item in resolved_catalog
    ]
    summary = _guardrail_summary(items)
    model_section = _model_status_section(resolved_model_status)
    rollback_section = rollback_reference or model_section.get("rollback") or {"available": False}
    return {
        "task": "D41",
        "mode": mode,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "catalog": {
            "item_count": len(resolved_catalog),
            "items": resolved_catalog,
        },
        "model_status": model_section,
        "rollback_reference": rollback_section,
        "guardrail_thresholds": resolved_thresholds,
        "items": items,
        "guardrail_summary": summary,
        "decision": _report_decision(summary),
        "invariants": {
            "mutates_production_artifact": False,
            "publishes_model": False,
            "rolls_back_model": False,
            "default_mode_requires_live_network": False,
        },
    }


def write_golden_replay_report(report: dict[str, Any], output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> dict[str, str]:
    return _write_golden_replay_report(report, output_dir)


def run_golden_replay_report(
    *,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    evidence_json: str | Path | None = None,
    model_status_json: str | Path | None = None,
    generated_at: str | None = DEFAULT_GENERATED_AT,
) -> dict[str, Any]:
    model_status = _read_json(model_status_json) if model_status_json else build_model_status_payload()
    evidence = _read_json(evidence_json) if evidence_json else default_stored_replay_evidence()
    mode = "stored_evidence_json" if evidence_json else "stored_evidence"
    report = build_golden_replay_report(
        model_status=model_status,
        results=evidence,
        generated_at=generated_at,
        mode=mode,
    )
    report_paths = write_golden_replay_report(report, output_dir)
    return {**report, "report_paths": report_paths}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build D41 deterministic golden query replay guardrail report.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--evidence-json", default=None, help="Optional stored replay evidence JSON.")
    parser.add_argument("--model-status-json", default=None, help="Optional /health/model payload JSON.")
    parser.add_argument(
        "--generated-at",
        default=DEFAULT_GENERATED_AT,
        help="Report timestamp. Keep the default for deterministic output; pass an ISO timestamp when needed.",
    )
    args = parser.parse_args(argv)
    report = run_golden_replay_report(
        output_dir=args.output_dir,
        evidence_json=args.evidence_json,
        model_status_json=args.model_status_json,
        generated_at=args.generated_at,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
