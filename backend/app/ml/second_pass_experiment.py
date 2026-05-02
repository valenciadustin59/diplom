from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any

from app.features import SERP_RELATIVE_FEATURE_COLUMNS, merge_serp_relative_features
from app.ml.model import ARTIFACTS_DIR, DEFAULT_MODEL_PATH, clear_model_cache, load_model_artifact, save_model
from app.ml.model_schema import MODEL_SCHEMA_VERSION_V3
from app.ml.ranking_benchmark import build_feature_importance_summary, build_stability_summary
from app.ml.second_pass import (
    SECOND_PASS_CANDIDATE_FAMILY,
    SECOND_PASS_MIN_COMPETITORS,
    SECOND_PASS_MODEL_SCHEMA_VERSION,
    build_second_pass_score_result,
    get_second_pass_feature_columns,
)
from app.ml.train import (
    candidate_sort_key,
    evaluate_model_rows,
    load_dataset_rows,
    rows_to_matrix,
    split_dataset_rows,
    train_candidate_models,
)


BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
DEFAULT_D44_DATASET_PATH = DATA_DIR / "dataset_versions" / "dataset-v3-d37" / "dataset.csv"
DEFAULT_D44_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v3-d44"
DEFAULT_D44_CANDIDATE_MODEL_PATH = ARTIFACTS_DIR / "page_quality_model.dataset-v3-d44-second-pass-experiment.pkl"
DEFAULT_D44_ARTIFACT_VERSION = "dataset-v3-d37-d44-second-pass-experiment"
POINTWISE_RANDOM_FOREST_SECOND_PASS = "pointwise_random_forest_second_pass"
POINTWISE_CATBOOST_SECOND_PASS = "pointwise_catboost_second_pass"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _sha1_file(path: str | Path | None) -> str | None:
    if path is None:
        return None
    resolved_path = Path(path)
    if not resolved_path.exists():
        return None
    digest = hashlib.sha1()
    with resolved_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return round(sorted_values[0], 6)
    raw_index = (len(sorted_values) - 1) * percentile
    lower_index = int(raw_index)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    weight = raw_index - lower_index
    value = sorted_values[lower_index] * (1.0 - weight) + sorted_values[upper_index] * weight
    return round(value, 6)


def _dataset_version(dataset_path: str | Path, rows: list[dict[str, str]], explicit_version: str | None) -> str:
    if explicit_version:
        return explicit_version
    for row in rows:
        version = str(row.get("dataset_version") or "").strip()
        if version:
            return version
    return Path(dataset_path).stem


def _feature_map(row: dict[str, str], feature_columns: list[str] | tuple[str, ...]) -> dict[str, float | int]:
    return {feature_name: _safe_float(row.get(feature_name)) for feature_name in feature_columns}


def _group_rows_by_query(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped_rows[str(row.get("query") or "")].append(row)
    return dict(grouped_rows)


def enrich_rows_with_serp_relative_features(
    rows: list[dict[str, str]],
    *,
    primary_feature_columns: list[str] | tuple[str, ...] | None = None,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    feature_columns = primary_feature_columns or get_second_pass_feature_columns(MODEL_SCHEMA_VERSION_V3)[: -len(SERP_RELATIVE_FEATURE_COLUMNS)]
    enriched_rows: list[dict[str, str]] = []
    context_counts: list[int] = []
    rows_with_context = 0
    rows_with_min_context = 0
    grouped_rows = _group_rows_by_query(rows)

    for query_rows in grouped_rows.values():
        query_feature_maps = [_feature_map(row, feature_columns) for row in query_rows]
        for row_index, row in enumerate(query_rows):
            competitor_features = [
                features
                for competitor_index, features in enumerate(query_feature_maps)
                if competitor_index != row_index
            ]
            merged_features, _summary = merge_serp_relative_features(query_feature_maps[row_index], competitor_features)
            enriched_row = dict(row)
            for feature_name in SERP_RELATIVE_FEATURE_COLUMNS:
                enriched_row[feature_name] = str(_safe_float(merged_features.get(feature_name)))
            context_count = _safe_int(merged_features.get("serp_relative_context_count"))
            context_counts.append(context_count)
            if _safe_float(merged_features.get("serp_relative_context_available")) >= 1.0:
                rows_with_context += 1
            if context_count >= SECOND_PASS_MIN_COMPETITORS:
                rows_with_min_context += 1
            enriched_rows.append(enriched_row)

    return enriched_rows, {
        "rows_count": len(enriched_rows),
        "queries_count": len(grouped_rows),
        "rows_with_context": rows_with_context,
        "rows_with_min_context": rows_with_min_context,
        "weak_context_rows": len(enriched_rows) - rows_with_min_context,
        "min_context_count": min(context_counts) if context_counts else 0,
        "max_context_count": max(context_counts) if context_counts else 0,
        "avg_context_count": round(mean(context_counts), 6) if context_counts else 0.0,
        "serp_relative_feature_count": len(SERP_RELATIVE_FEATURE_COLUMNS),
        "min_competitors_required": SECOND_PASS_MIN_COMPETITORS,
    }


def _split_summary(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    split_metadata: dict[str, object],
) -> dict[str, Any]:
    train_queries = {str(row.get("query") or "") for row in train_rows if str(row.get("query") or "").strip()}
    validation_queries = {
        str(row.get("query") or "") for row in validation_rows if str(row.get("query") or "").strip()
    }
    return {
        "split_mode": str(split_metadata.get("split_mode") or "unknown"),
        "train_rows_count": len(train_rows),
        "validation_rows_count": len(validation_rows),
        "train_queries_count": len(train_queries),
        "validation_queries_count": len(validation_queries),
        "query_overlap_count": len(train_queries & validation_queries),
        "train_queries": sorted(train_queries),
        "validation_queries": sorted(validation_queries),
    }


def _evaluate_artifact_predictions(
    *,
    model_path: str | Path,
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    artifact = load_model_artifact(model_path)
    if artifact is None:
        raise FileNotFoundError(f"Model artifact is not available: {model_path}")
    feature_columns = artifact.get("feature_columns") if isinstance(artifact.get("feature_columns"), list) else []
    x_rows, _ = rows_to_matrix(rows, feature_columns=feature_columns)
    predictions = [float(value) for value in artifact["model"].predict(x_rows)]
    return {
        "model_path": str(Path(model_path)),
        "sha1": _sha1_file(model_path),
        "model_info": {
            "model_type": artifact.get("model_type"),
            "model_schema_version": artifact.get("model_schema_version"),
            "artifact_version": artifact.get("artifact_version"),
            "dataset_version": artifact.get("dataset_version"),
            "feature_count": len(feature_columns),
        },
        "metrics": evaluate_model_rows(artifact["model"], rows, feature_columns=feature_columns),
        "stability": build_stability_summary(rows, predictions),
        "predictions": predictions,
    }


def _candidate_name(model_type: object) -> str:
    normalized_model_type = str(model_type or "")
    if "CatBoost" in normalized_model_type:
        return POINTWISE_CATBOOST_SECOND_PASS
    return POINTWISE_RANDOM_FOREST_SECOND_PASS


def _serialize_candidate(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "candidate_name": candidate.get("candidate_name"),
        "candidate_family": candidate.get("candidate_family"),
        "status": candidate.get("status", "available"),
        "model_type": candidate.get("model_type"),
        "model_schema_version": candidate.get("model_schema_version"),
        "feature_count": candidate.get("feature_count"),
        "metrics": candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
        "stability": candidate.get("stability") if isinstance(candidate.get("stability"), dict) else {},
        "feature_importance_summary": candidate.get("feature_importance_summary")
        if isinstance(candidate.get("feature_importance_summary"), dict)
        else {"available": False, "top_features": []},
        "model_path": candidate.get("model_path"),
    }


def _train_second_pass_candidates(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    *,
    feature_columns: tuple[str, ...],
    random_state: int,
    force_catboost: bool,
) -> list[dict[str, Any]]:
    raw_candidates, benchmark = train_candidate_models(
        train_rows,
        validation_rows,
        random_state=random_state,
        feature_columns=feature_columns,
        force_catboost=force_catboost,
    )
    candidates: list[dict[str, Any]] = []
    for candidate in raw_candidates:
        x_validation, _ = rows_to_matrix(validation_rows, feature_columns=feature_columns)
        predictions = [float(value) for value in candidate["model"].predict(x_validation)]
        candidates.append(
            {
                **candidate,
                "candidate_name": _candidate_name(candidate.get("model_type")),
                "candidate_family": SECOND_PASS_CANDIDATE_FAMILY,
                "status": "available",
                "model_schema_version": SECOND_PASS_MODEL_SCHEMA_VERSION,
                "feature_count": len(feature_columns),
                "stability": build_stability_summary(validation_rows, predictions),
                "feature_importance_summary": build_feature_importance_summary(candidate["model"], feature_columns),
                "predictions": predictions,
            }
        )
    if force_catboost and POINTWISE_CATBOOST_SECOND_PASS not in {str(candidate["candidate_name"]) for candidate in candidates}:
        candidates.append(
            {
                "candidate_name": POINTWISE_CATBOOST_SECOND_PASS,
                "candidate_family": SECOND_PASS_CANDIDATE_FAMILY,
                "status": "unavailable",
                "model_type": "CatBoostRegressor",
                "model_schema_version": SECOND_PASS_MODEL_SCHEMA_VERSION,
                "feature_count": len(feature_columns),
                "metrics": {},
                "stability": {},
                "feature_importance_summary": {"available": False, "top_features": []},
                "reason": benchmark.get("catboost_error") or "catboost_not_available",
                "model": None,
                "predictions": [],
            }
        )
    return candidates


def _validate_candidate_path(candidate_model_path: str | Path, reference_model_path: str | Path | None) -> None:
    resolved_candidate_path = Path(candidate_model_path).resolve()
    if resolved_candidate_path == DEFAULT_MODEL_PATH.resolve():
        raise ValueError("D44 second-pass candidate must not overwrite backend/artifacts/page_quality_model.pkl")
    if reference_model_path is not None and resolved_candidate_path == Path(reference_model_path).resolve():
        raise ValueError("D44 second-pass candidate must not overwrite the reference model artifact")


def _save_candidate_metadata(
    *,
    candidate: dict[str, Any],
    candidate_model_path: str | Path,
    metadata: dict[str, Any],
) -> dict[str, str]:
    saved_path = save_model(
        model=candidate["model"],
        metrics=metadata["metrics"],
        model_path=candidate_model_path,
        metadata=metadata,
    )
    metadata_path = saved_path.with_suffix(".metadata.json")
    metadata_payload = {
        **metadata,
        "model_path": str(saved_path),
        "sha1": _sha1_file(saved_path),
        "metrics": metadata["metrics"],
    }
    metadata_path.write_text(json.dumps(metadata_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    clear_model_cache()
    candidate["model_path"] = str(saved_path)
    return {"model_path": str(saved_path), "metadata_path": str(metadata_path), "sha1": str(metadata_payload["sha1"])}


def _metric_delta(candidate_metrics: dict[str, Any], reference_metrics: dict[str, Any]) -> dict[str, float]:
    return {
        metric_name: round(_safe_float(candidate_metrics.get(metric_name)) - _safe_float(reference_metrics.get(metric_name)), 6)
        for metric_name in ("top_3_hit_rate", "ndcg_at_10", "spearman_mean", "mae", "rmse")
    }


def _prediction_delta_summary(primary_predictions: list[float], candidate_predictions: list[float]) -> dict[str, Any]:
    deltas = [
        float(candidate_prediction) - float(primary_prediction)
        for primary_prediction, candidate_prediction in zip(primary_predictions, candidate_predictions, strict=False)
    ]
    absolute_deltas = [abs(value) for value in deltas]
    return {
        "rows_count": len(deltas),
        "mean_delta": round(mean(deltas), 6) if deltas else 0.0,
        "mean_abs_delta": round(mean(absolute_deltas), 6) if absolute_deltas else 0.0,
        "p95_abs_delta": _percentile(absolute_deltas, 0.95),
        "max_abs_delta": round(max(absolute_deltas), 6) if absolute_deltas else 0.0,
        "candidate_scores_below_zero": sum(1 for value in candidate_predictions if value < 0.0),
        "candidate_scores_above_hundred": sum(1 for value in candidate_predictions if value > 100.0),
    }


def _recommendation_consistency_summary(
    validation_rows: list[dict[str, str]],
    primary_predictions: list[float],
    candidate_predictions: list[float],
) -> dict[str, Any]:
    low_relative_rows = 0
    high_relative_rows = 0
    low_relative_boost_violations = 0
    high_relative_drop_violations = 0

    for row, primary_prediction, candidate_prediction in zip(
        validation_rows,
        primary_predictions,
        candidate_predictions,
        strict=False,
    ):
        percentile = _safe_float(row.get("serp_relative_percentile"))
        gap_score = _safe_float(row.get("serp_relative_gap_score"))
        delta = float(candidate_prediction) - float(primary_prediction)
        if percentile < 0.35 or gap_score < 0.55:
            low_relative_rows += 1
            if delta > 5.0:
                low_relative_boost_violations += 1
        if percentile >= 0.65 and gap_score >= 0.75:
            high_relative_rows += 1
            if delta < -5.0:
                high_relative_drop_violations += 1

    low_violation_rate = (
        round(low_relative_boost_violations / low_relative_rows, 6) if low_relative_rows else 0.0
    )
    high_violation_rate = (
        round(high_relative_drop_violations / high_relative_rows, 6) if high_relative_rows else 0.0
    )
    return {
        "low_relative_rows": low_relative_rows,
        "high_relative_rows": high_relative_rows,
        "low_relative_boost_violations": low_relative_boost_violations,
        "high_relative_drop_violations": high_relative_drop_violations,
        "low_violation_rate": low_violation_rate,
        "high_violation_rate": high_violation_rate,
        "max_allowed_violation_rate": 0.2,
        "passed": low_violation_rate <= 0.2 and high_violation_rate <= 0.2,
    }


def _guardrail(
    name: str,
    passed: bool | None,
    message: str,
    *,
    severity: str = "critical",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status = "not_evaluated" if passed is None else ("passed" if passed else "failed")
    return {
        "name": name,
        "status": status,
        "severity": severity,
        "message": message,
        "details": details or {},
    }


def _build_guardrails(
    *,
    primary_model: dict[str, Any],
    candidate: dict[str, Any],
    metric_deltas: dict[str, float],
    prediction_deltas: dict[str, Any],
    recommendation_consistency: dict[str, Any],
    split: dict[str, Any],
    reference_sha_before: str | None,
    reference_sha_after: str | None,
    candidate_artifact: dict[str, str],
    weak_context_rows: int,
) -> list[dict[str, Any]]:
    primary_metrics = primary_model["metrics"]
    candidate_metrics = candidate["metrics"]
    weak_contract = build_second_pass_score_result(
        primary_score=72.5,
        enriched_features={"serp_relative_context_available": 0, "serp_relative_context_count": 0},
        candidate_model_path=candidate_artifact.get("model_path"),
    )
    return [
        _guardrail(
            "no_query_leakage",
            int(split["query_overlap_count"]) == 0,
            "Train and validation partitions must not share query groups.",
            details={"query_overlap_count": split["query_overlap_count"], "split_mode": split["split_mode"]},
        ),
        _guardrail(
            "top_3_no_regression",
            _safe_float(candidate_metrics.get("top_3_hit_rate")) >= _safe_float(primary_metrics.get("top_3_hit_rate")),
            "Second-pass candidate should not regress top-3 hit rate versus the active primary model.",
            details={"delta": metric_deltas["top_3_hit_rate"]},
        ),
        _guardrail(
            "ndcg_no_regression",
            _safe_float(candidate_metrics.get("ndcg_at_10")) >= _safe_float(primary_metrics.get("ndcg_at_10")),
            "Second-pass candidate should not regress NDCG@10 versus the active primary model.",
            details={"delta": metric_deltas["ndcg_at_10"]},
        ),
        _guardrail(
            "mae_no_regression",
            _safe_float(candidate_metrics.get("mae")) <= _safe_float(primary_metrics.get("mae")),
            "Second-pass candidate should not increase validation MAE versus the active primary model.",
            details={"delta": metric_deltas["mae"]},
        ),
        _guardrail(
            "score_stability",
            _safe_float(prediction_deltas.get("p95_abs_delta")) <= 25.0,
            "Second-pass predictions should not create large score jumps for most validation rows.",
            details=prediction_deltas,
            severity="warning",
        ),
        _guardrail(
            "score_boundedness",
            int(prediction_deltas.get("candidate_scores_below_zero") or 0) == 0
            and int(prediction_deltas.get("candidate_scores_above_hundred") or 0) == 0,
            "Second-pass raw predictions should stay inside the product 0-100 score range.",
            details=prediction_deltas,
        ),
        _guardrail(
            "recommendation_consistency",
            bool(recommendation_consistency.get("passed")),
            "Score movement should not contradict existing SERP-relative competitor-gap recommendation signals.",
            details=recommendation_consistency,
            severity="warning",
        ),
        _guardrail(
            "weak_competitor_coverage_fallback",
            weak_contract["status"] == "skipped" and weak_contract["effective_score"] == weak_contract["primary_score"],
            "Audits with weak competitor coverage must keep a valid primary score and skip the optional second pass.",
            details={"weak_context_rows": weak_context_rows, "contract_probe": weak_contract},
        ),
        _guardrail(
            "reference_artifact_unchanged",
            reference_sha_before is not None and reference_sha_before == reference_sha_after,
            "D44 must not mutate backend/artifacts/page_quality_model.pkl or the selected reference artifact.",
            details={"sha1_before": reference_sha_before, "sha1_after": reference_sha_after},
        ),
        _guardrail(
            "candidate_non_production",
            bool(candidate_artifact.get("model_path")) and "second-pass-experiment" in Path(candidate_artifact["model_path"]).stem,
            "Candidate artifact must be clearly separate from production and marked non-production.",
            details=candidate_artifact,
        ),
    ]


def _decision(metric_deltas: dict[str, float], guardrails: list[dict[str, Any]]) -> str:
    critical_failures = [
        guardrail
        for guardrail in guardrails
        if guardrail["severity"] == "critical" and guardrail["status"] == "failed"
    ]
    if critical_failures:
        return "do_not_continue_without_more_evidence"
    if (
        metric_deltas["top_3_hit_rate"] >= 0.0
        and metric_deltas["ndcg_at_10"] > 0.0
        and metric_deltas["mae"] <= 0.0
    ):
        return "continue_to_d45_candidate_review"
    return "needs_more_evidence_before_d45"


def render_second_pass_experiment_markdown(report: dict[str, Any]) -> str:
    candidate = report.get("candidate_model") if isinstance(report.get("candidate_model"), dict) else {}
    primary = report.get("primary_model") if isinstance(report.get("primary_model"), dict) else {}
    comparison = report.get("comparison") if isinstance(report.get("comparison"), dict) else {}
    lines = [
        "# D44 Second-Pass Competitor-Aware Score Experiment",
        "",
        f"- Decision: `{report.get('decision')}`",
        f"- Runtime impact: `{report.get('runtime_impact')}`",
        f"- Dataset: `{report.get('dataset_version')}`",
        f"- Feature schema: `{report.get('model_schema_version')}`",
        f"- Feature count: `{report.get('feature_count')}`",
        f"- Candidate artifact: `{candidate.get('model_path')}`",
        f"- Candidate non-production: `{candidate.get('non_production')}`",
        "",
        "## Two-Stage Contract",
        "",
        "- Primary score remains available before competitor aggregation.",
        "- Optional second-pass score is evaluated only after SERP-relative features exist.",
        f"- Minimum competitors for second pass: `{report.get('scoring_contract', {}).get('min_competitors_required')}`",
        "- Weak or missing competitor coverage keeps the primary score.",
        "",
        "## Primary Vs Candidate",
        "",
        f"- Primary model: `{primary.get('model_info', {}).get('model_type')}` / `{primary.get('model_info', {}).get('artifact_version')}`",
        f"- Candidate model: `{candidate.get('model_type')}` / `{candidate.get('artifact_version')}`",
        f"- Top-3 delta: `{comparison.get('metric_deltas', {}).get('top_3_hit_rate')}`",
        f"- NDCG@10 delta: `{comparison.get('metric_deltas', {}).get('ndcg_at_10')}`",
        f"- MAE delta: `{comparison.get('metric_deltas', {}).get('mae')}`",
        "",
        "## Guardrails",
        "",
    ]
    for guardrail in report.get("guardrails", []):
        lines.append(f"- `{guardrail.get('name')}`: `{guardrail.get('status')}` - {guardrail.get('message')}")
    lines.extend(
        [
            "",
            "## Non-Production Notes",
            "",
            "- D44 does not publish, roll back or replace `backend/artifacts/page_quality_model.pkl`.",
            "- Candidate artifact is for offline second-pass evidence only.",
            "- A later D45+ task would be required before any runtime scoring change.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def write_second_pass_experiment_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    json_path = resolved_output_dir / "second-pass-experiment-report.json"
    markdown_path = resolved_output_dir / "second-pass-experiment-report.md"
    report_paths = {"json_path": str(json_path), "markdown_path": str(markdown_path)}
    report_with_paths = {**report, "report_paths": report_paths}
    json_path.write_text(json.dumps(report_with_paths, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_second_pass_experiment_markdown(report_with_paths), encoding="utf-8")
    return report_paths


def run_second_pass_experiment(
    *,
    dataset_path: str | Path = DEFAULT_D44_DATASET_PATH,
    dataset_version: str | None = None,
    reference_model_path: str | Path | None = DEFAULT_MODEL_PATH,
    candidate_model_path: str | Path = DEFAULT_D44_CANDIDATE_MODEL_PATH,
    output_dir: str | Path | None = DEFAULT_D44_OUTPUT_DIR,
    test_size: float = 0.2,
    random_state: int = 42,
    force_catboost: bool = True,
) -> dict[str, Any]:
    if reference_model_path is None:
        raise ValueError("D44 requires an explicit primary/reference model for comparison")
    _validate_candidate_path(candidate_model_path, reference_model_path)
    reference_sha_before = _sha1_file(reference_model_path)
    generated_at = datetime.now(UTC).isoformat()
    rows = load_dataset_rows(dataset_path)
    if len(rows) < 4:
        raise ValueError("At least 4 rows are required for the D44 second-pass experiment")
    resolved_dataset_version = _dataset_version(dataset_path, rows, dataset_version)
    primary_feature_columns = get_second_pass_feature_columns(MODEL_SCHEMA_VERSION_V3)[: -len(SERP_RELATIVE_FEATURE_COLUMNS)]
    second_pass_feature_columns = get_second_pass_feature_columns(MODEL_SCHEMA_VERSION_V3)
    train_rows, validation_rows, split_metadata = split_dataset_rows(
        rows,
        test_size=test_size,
        random_state=random_state,
    )
    split = _split_summary(train_rows, validation_rows, split_metadata)
    train_enriched, train_enrichment = enrich_rows_with_serp_relative_features(
        train_rows,
        primary_feature_columns=primary_feature_columns,
    )
    validation_enriched, validation_enrichment = enrich_rows_with_serp_relative_features(
        validation_rows,
        primary_feature_columns=primary_feature_columns,
    )

    primary_model = _evaluate_artifact_predictions(model_path=reference_model_path, rows=validation_rows)
    candidates = _train_second_pass_candidates(
        train_enriched,
        validation_enriched,
        feature_columns=second_pass_feature_columns,
        random_state=random_state,
        force_catboost=force_catboost,
    )
    available_candidates = [
        candidate
        for candidate in candidates
        if candidate.get("status") == "available" and candidate.get("model") is not None
    ]
    if not available_candidates:
        raise ValueError("No D44 second-pass candidate was available for evaluation")
    best_candidate = max(available_candidates, key=candidate_sort_key)
    best_candidate["model_path"] = str(Path(candidate_model_path))

    candidate_metrics = {
        **best_candidate["metrics"],
        "train_rows": float(len(train_enriched)),
        "validation_rows": float(len(validation_enriched)),
        **split_metadata,
    }
    candidate_metadata = {
        "source": "local_dataset",
        "dataset_version": resolved_dataset_version,
        "artifact_version": DEFAULT_D44_ARTIFACT_VERSION,
        "artifact_family": "page_quality_model.second_pass_experiment",
        "model_schema_version": SECOND_PASS_MODEL_SCHEMA_VERSION,
        "feature_columns": list(second_pass_feature_columns),
        "model_type": best_candidate.get("model_type"),
        "candidate_name": best_candidate.get("candidate_name"),
        "candidate_family": SECOND_PASS_CANDIDATE_FAMILY,
        "trained_at": generated_at,
        "rows_count": len(rows),
        "queries_count": len({str(row.get("query") or "") for row in rows}),
        "domains_count": len({str(row.get("domain") or "") for row in rows}),
        "metrics": candidate_metrics,
        "non_production": True,
        "production_ready": False,
        "runtime_enabled": False,
        "usage_scope": "offline_second_pass_experiment_only",
        "does_not_replace": str(DEFAULT_MODEL_PATH),
        "d44_experiment": {
            "min_competitors_required": SECOND_PASS_MIN_COMPETITORS,
            "uses_serp_relative_features": True,
            "query_leakage_guard": "split_then_enrich_by_partition",
        },
    }
    candidate_artifact = _save_candidate_metadata(
        candidate=best_candidate,
        candidate_model_path=candidate_model_path,
        metadata=candidate_metadata,
    )
    reference_sha_after = _sha1_file(reference_model_path)
    metric_deltas = _metric_delta(best_candidate["metrics"], primary_model["metrics"])
    prediction_deltas = _prediction_delta_summary(primary_model["predictions"], best_candidate["predictions"])
    recommendation_consistency = _recommendation_consistency_summary(
        validation_enriched,
        primary_model["predictions"],
        best_candidate["predictions"],
    )
    guardrails = _build_guardrails(
        primary_model=primary_model,
        candidate=best_candidate,
        metric_deltas=metric_deltas,
        prediction_deltas=prediction_deltas,
        recommendation_consistency=recommendation_consistency,
        split=split,
        reference_sha_before=reference_sha_before,
        reference_sha_after=reference_sha_after,
        candidate_artifact=candidate_artifact,
        weak_context_rows=int(validation_enrichment["weak_context_rows"]),
    )
    report = {
        "generated_at": generated_at,
        "task": "D44",
        "runtime_impact": "none",
        "decision": _decision(metric_deltas, guardrails),
        "dataset_path": str(Path(dataset_path)),
        "dataset_version": resolved_dataset_version,
        "model_schema_version": SECOND_PASS_MODEL_SCHEMA_VERSION,
        "primary_model_schema_version": MODEL_SCHEMA_VERSION_V3,
        "feature_count": len(second_pass_feature_columns),
        "primary_feature_count": len(primary_feature_columns),
        "serp_relative_feature_count": len(SERP_RELATIVE_FEATURE_COLUMNS),
        "rows_count": len(rows),
        "queries_count": len({str(row.get("query") or "") for row in rows}),
        "split": split,
        "query_leakage_guard": {
            "strategy": "split_dataset_rows_before_serp_relative_enrichment",
            "query_overlap_count": split["query_overlap_count"],
            "target_score_in_feature_columns": "target_score" in second_pass_feature_columns,
            "passed": split["query_overlap_count"] == 0 and "target_score" not in second_pass_feature_columns,
        },
        "scoring_contract": {
            "primary_score_stage": "before_competitor_aggregation",
            "second_pass_stage": "after_competitor_aggregation",
            "min_competitors_required": SECOND_PASS_MIN_COMPETITORS,
            "missing_competitor_behavior": "skip_second_pass_keep_primary_score",
            "runtime_enabled": False,
        },
        "train_serp_relative_enrichment": train_enrichment,
        "validation_serp_relative_enrichment": validation_enrichment,
        "primary_model": {
            key: value
            for key, value in primary_model.items()
            if key != "predictions"
        },
        "candidate_model": {
            **(_serialize_candidate(best_candidate) or {}),
            **candidate_artifact,
            "artifact_version": DEFAULT_D44_ARTIFACT_VERSION,
            "non_production": True,
            "runtime_enabled": False,
        },
        "candidates": [_serialize_candidate(candidate) for candidate in candidates],
        "comparison": {
            "metric_deltas": metric_deltas,
            "prediction_deltas": prediction_deltas,
            "recommendation_consistency": recommendation_consistency,
        },
        "guardrails": guardrails,
    }
    report_paths: dict[str, str] | None = None
    if output_dir is not None:
        report_paths = write_second_pass_experiment_report(report, output_dir)
        report["report_paths"] = report_paths
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the D44 non-production second-pass scoring experiment.")
    parser.add_argument("--dataset", default=str(DEFAULT_D44_DATASET_PATH))
    parser.add_argument("--dataset-version", default="")
    parser.add_argument("--reference-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--candidate-model-output", default=str(DEFAULT_D44_CANDIDATE_MODEL_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_D44_OUTPUT_DIR))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--skip-catboost", action="store_true")
    args = parser.parse_args()
    report = run_second_pass_experiment(
        dataset_path=args.dataset,
        dataset_version=args.dataset_version or None,
        reference_model_path=args.reference_model,
        candidate_model_path=args.candidate_model_output,
        output_dir=args.output_dir or None,
        test_size=args.test_size,
        random_state=args.random_state,
        force_catboost=not args.skip_catboost,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
