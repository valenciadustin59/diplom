from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from app.ml.candidate_artifacts import (
    DEFAULT_CATBOOST_CANDIDATE_PATH,
    DEFAULT_RANKING_CANDIDATE_PATH,
    DEFAULT_RF_CANDIDATE_PATH,
)
from app.ml.model import DEFAULT_MODEL_PATH, explain_score, load_model_artifact, load_saved_model
from app.ml.model_schema import MODEL_SCHEMA_VERSION_V2, get_model_feature_schema
from app.ml.publish import ARTIFACTS_DIR
from app.ml.ranking_benchmark import build_feature_importance_summary, build_stability_summary
from app.ml.shadow_explainability import build_explainability_sensibility_summary
from app.ml.shadow_report import write_shadow_benchmark_report
from app.ml.train import candidate_sort_key, evaluate_model_rows, load_dataset_rows, rows_to_matrix, split_dataset_rows


DEFAULT_D35_SHADOW_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v2-d35"
DEFAULT_D35_CANDIDATE_PATHS = (
    DEFAULT_RF_CANDIDATE_PATH,
    DEFAULT_CATBOOST_CANDIDATE_PATH,
    DEFAULT_RANKING_CANDIDATE_PATH,
)
DEFAULT_D35_SMOKE_QUERIES = (
    "ремонт квартир москва",
    "пластиковые окна казань",
    "кухни на заказ санкт-петербург",
    "натяжные потолки новосибирск",
)
ABSOLUTE_ERROR_TOLERANCE_RATIO = 0.05
RANKING_FAMILY_MAE_WARNING_THRESHOLD = 50.0


def _artifact_feature_columns(artifact: dict[str, Any]) -> list[str] | tuple[str, ...] | None:
    feature_columns = artifact.get("feature_columns")
    return feature_columns if isinstance(feature_columns, (list, tuple)) else None


def _artifact_model_info(artifact: dict[str, Any], raw_payload: dict[str, Any], model_path: str | Path) -> dict[str, Any]:
    feature_columns = _artifact_feature_columns(artifact) or []
    return {
        "model_path": str(Path(model_path)),
        "source": artifact.get("source", "unknown"),
        "model_type": artifact.get("model_type", artifact["model"].__class__.__name__),
        "trained_at": artifact.get("trained_at"),
        "published_at": artifact.get("published_at"),
        "artifact_version": artifact.get("artifact_version"),
        "dataset_version": artifact.get("dataset_version"),
        "model_schema_version": artifact.get("model_schema_version"),
        "candidate_name": raw_payload.get("candidate_name"),
        "candidate_family": raw_payload.get("candidate_family"),
        "feature_count": len(feature_columns),
        "rows_count": int(artifact.get("rows_count") or 0),
        "queries_count": int(artifact.get("queries_count") or 0),
        "domains_count": int(artifact.get("domains_count") or 0),
    }


def _artifact_feature_columns_for_path(model_path: str | Path) -> list[str] | tuple[str, ...]:
    artifact = load_model_artifact(model_path)
    if artifact is None:
        return get_model_feature_schema(MODEL_SCHEMA_VERSION_V2).feature_columns
    return _artifact_feature_columns(artifact) or get_model_feature_schema(MODEL_SCHEMA_VERSION_V2).feature_columns


def _candidate_name(raw_payload: dict[str, Any], model_path: str | Path, fallback: str) -> str:
    candidate_name = raw_payload.get("candidate_name")
    if isinstance(candidate_name, str) and candidate_name.strip():
        return candidate_name.strip()
    path_stem = Path(model_path).stem
    return path_stem or fallback


def _candidate_family(raw_payload: dict[str, Any], default: str) -> str:
    candidate_family = raw_payload.get("candidate_family")
    if isinstance(candidate_family, str) and candidate_family.strip():
        return candidate_family.strip()
    return default


def evaluate_shadow_artifact(
    *,
    candidate_name: str,
    candidate_family: str,
    model_path: str | Path,
    validation_rows: list[dict[str, str]],
) -> dict[str, Any]:
    artifact = load_model_artifact(model_path)
    raw_payload = load_saved_model(model_path) or {}
    if artifact is None:
        return {
            "candidate_name": candidate_name,
            "candidate_family": candidate_family,
            "status": "unavailable",
            "model_path": str(Path(model_path)),
            "model_info": None,
            "model_type": None,
            "model_schema_version": None,
            "feature_count": 0,
            "metrics": {},
            "stability": {},
            "feature_importance_summary": {"available": False, "top_features": []},
            "runtime_explanation_guardrail": {"passed": False, "reason": "artifact_not_available"},
            "reason": "artifact_not_available",
        }

    feature_columns = _artifact_feature_columns(artifact)
    x_validation, _ = rows_to_matrix(validation_rows, feature_columns=feature_columns)
    predictions = [float(value) for value in artifact["model"].predict(x_validation)]
    model_type = str(artifact.get("model_type", artifact["model"].__class__.__name__))
    return {
        "candidate_name": _candidate_name(raw_payload, model_path, candidate_name),
        "candidate_family": _candidate_family(raw_payload, candidate_family),
        "status": "available",
        "model_path": str(Path(model_path)),
        "model_info": _artifact_model_info(artifact, raw_payload, model_path),
        "model_type": model_type,
        "model_schema_version": artifact.get("model_schema_version"),
        "feature_count": len(feature_columns or []),
        "metrics": evaluate_model_rows(artifact["model"], validation_rows, feature_columns=feature_columns),
        "stability": build_stability_summary(validation_rows, predictions),
        "feature_importance_summary": build_feature_importance_summary(artifact["model"], feature_columns or []),
        "runtime_explanation_guardrail": {"passed": None, "reason": "not_evaluated"},
        "reason": None,
    }


def build_metric_deltas(candidate_metrics: dict[str, Any], reference_metrics: dict[str, Any]) -> dict[str, float]:
    return {
        metric_name: round(float(candidate_metrics.get(metric_name, 0.0)) - float(reference_metrics.get(metric_name, 0.0)), 6)
        for metric_name in ("spearman_mean", "ndcg_at_10", "top_3_hit_rate", "rmse", "mae")
        if metric_name in candidate_metrics or metric_name in reference_metrics
    }


def _absolute_error_threshold(reference_value: float, tolerance_ratio: float) -> float:
    return round(reference_value * (1.0 + tolerance_ratio), 6)


def build_candidate_guardrails(
    candidate: dict[str, Any],
    reference_model: dict[str, Any],
    *,
    absolute_error_tolerance_ratio: float = ABSOLUTE_ERROR_TOLERANCE_RATIO,
    ranking_family_mae_warning_threshold: float = RANKING_FAMILY_MAE_WARNING_THRESHOLD,
) -> dict[str, Any]:
    if candidate.get("status") != "available":
        return {
            "publish_gate_passed": False,
            "checks": {"candidate_available": False},
            "rejection_reasons": [str(candidate.get("reason") or "candidate_unavailable")],
            "thresholds": {},
        }

    candidate_metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {}
    reference_metrics = reference_model.get("metrics") if isinstance(reference_model.get("metrics"), dict) else {}
    reference_rmse = float(reference_metrics.get("rmse", 0.0))
    reference_mae = float(reference_metrics.get("mae", 0.0))
    rmse_threshold = _absolute_error_threshold(reference_rmse, absolute_error_tolerance_ratio)
    mae_threshold = _absolute_error_threshold(reference_mae, absolute_error_tolerance_ratio)
    feature_importance = candidate.get("feature_importance_summary")
    runtime_explanation = candidate.get("runtime_explanation_guardrail")
    sensibility = candidate.get("explainability_sensibility_guardrail")
    checks = {
        "candidate_available": True,
        "ndcg_at_10_not_worse": float(candidate_metrics.get("ndcg_at_10", 0.0)) >= float(reference_metrics.get("ndcg_at_10", 0.0)),
        "top_3_hit_rate_not_worse": float(candidate_metrics.get("top_3_hit_rate", 0.0)) >= float(reference_metrics.get("top_3_hit_rate", 0.0)),
        "spearman_mean_not_worse": float(candidate_metrics.get("spearman_mean", 0.0)) >= float(reference_metrics.get("spearman_mean", 0.0)),
        "rmse_comparable_or_better": float(candidate_metrics.get("rmse", 0.0)) <= rmse_threshold,
        "mae_comparable_or_better": float(candidate_metrics.get("mae", 0.0)) <= mae_threshold,
        "feature_importance_available": bool(isinstance(feature_importance, dict) and feature_importance.get("available")),
        "runtime_explanations_bounded": bool(isinstance(runtime_explanation, dict) and runtime_explanation.get("passed")),
        "explainability_sensible": bool(isinstance(sensibility, dict) and sensibility.get("passed")),
    }
    if str(candidate.get("candidate_family") or "") == "ranking":
        checks["ranking_family_absolute_error_viable"] = float(candidate_metrics.get("mae", 0.0)) <= ranking_family_mae_warning_threshold

    rejection_reason_by_check = {
        "candidate_available": "candidate_unavailable",
        "ndcg_at_10_not_worse": "ndcg_at_10_regressed",
        "top_3_hit_rate_not_worse": "top_3_hit_rate_regressed",
        "spearman_mean_not_worse": "spearman_mean_regressed",
        "rmse_comparable_or_better": "rmse_not_comparable",
        "mae_comparable_or_better": "mae_not_comparable",
        "feature_importance_available": "feature_importance_unavailable",
        "runtime_explanations_bounded": "runtime_explanations_not_bounded",
        "explainability_sensible": "explainability_sensibility_failed",
        "ranking_family_absolute_error_viable": "ranking_family_absolute_error_not_viable",
    }
    rejection_reasons = [
        rejection_reason_by_check[check_name]
        for check_name, passed in checks.items()
        if not bool(passed)
    ]
    return {
        "publish_gate_passed": not rejection_reasons,
        "checks": checks,
        "rejection_reasons": rejection_reasons,
        "thresholds": {
            "absolute_error_tolerance_ratio": absolute_error_tolerance_ratio,
            "rmse_comparable_threshold": rmse_threshold,
            "mae_comparable_threshold": mae_threshold,
            "ranking_family_mae_warning_threshold": ranking_family_mae_warning_threshold,
        },
    }


def _feature_row(row: dict[str, str], feature_columns: Iterable[str]) -> dict[str, float]:
    features: dict[str, float] = {}
    for feature_name in feature_columns:
        try:
            features[str(feature_name)] = float(row.get(str(feature_name), 0.0) or 0.0)
        except (TypeError, ValueError):
            features[str(feature_name)] = 0.0
    return features


def _sorted_query_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: (int(row.get("rank") or 0), str(row.get("url") or "")))


def _find_smoke_query_rows(rows: list[dict[str, str]], smoke_query: str) -> tuple[str, list[dict[str, str]], str]:
    normalized_query = smoke_query.casefold().strip()
    exact_rows = [row for row in rows if str(row.get("query") or "").casefold().strip() == normalized_query]
    if exact_rows:
        return str(exact_rows[0].get("query") or smoke_query), _sorted_query_rows(exact_rows), "exact_casefold"

    terms = [term for term in normalized_query.replace("-", " ").split() if term]
    fallback_rows = [
        row
        for row in rows
        if all(term in str(row.get("query") or "").casefold().replace("-", " ") for term in terms)
    ]
    if fallback_rows:
        matched_query = sorted({str(row.get("query") or "") for row in fallback_rows})[0]
        return matched_query, _sorted_query_rows([row for row in fallback_rows if str(row.get("query") or "") == matched_query]), "contains_all_terms"

    return smoke_query, [], "missing"


def _build_model_explanation_summary(
    *,
    model_name: str,
    model_path: str | Path,
    row: dict[str, str],
    feature_columns: Iterable[str],
) -> dict[str, Any]:
    explanation = explain_score(_feature_row(row, feature_columns), model_path=model_path)
    final_score = float(explanation.get("final_score", 0.0))
    ml_score = float(explanation.get("ml_score", 0.0))
    rule_score = float(explanation.get("rule_score", 0.0))
    return {
        "model_name": model_name,
        "model_path": str(Path(model_path)),
        "final_score": final_score,
        "ml_score": ml_score,
        "rule_score": rule_score,
        "bounded": all(0.0 <= score <= 100.0 for score in (final_score, ml_score, rule_score)),
        "model_info": explanation.get("model_info") if isinstance(explanation.get("model_info"), dict) else {},
        "top_positive_factor_keys": [
            str(factor.get("key"))
            for factor in explanation.get("top_positive_factors", [])
            if isinstance(factor, dict)
        ],
        "top_negative_factor_keys": [
            str(factor.get("key"))
            for factor in explanation.get("top_negative_factors", [])
            if isinstance(factor, dict)
        ],
        "serp_relative_factor_keys": [
            str(factor.get("key"))
            for factor in explanation.get("serp_relative_factors", [])
            if isinstance(factor, dict)
        ],
    }


def build_smoke_explainability_summary(
    *,
    rows: list[dict[str, str]],
    reference_model: dict[str, Any],
    candidates: list[dict[str, Any]],
    smoke_queries: Iterable[str],
) -> dict[str, Any]:
    smoke_query_list = tuple(smoke_queries)
    feature_columns = get_model_feature_schema(MODEL_SCHEMA_VERSION_V2).feature_columns
    model_entries = [
        {
            "model_name": "reference_artifact",
            "model_path": reference_model["model_path"],
            "feature_columns": _artifact_feature_columns_for_path(reference_model["model_path"]),
        },
        *[
            {
                "model_name": str(candidate.get("candidate_name") or Path(str(candidate.get("model_path"))).stem),
                "model_path": str(candidate.get("model_path")),
                "feature_columns": _artifact_feature_columns_for_path(str(candidate.get("model_path"))),
            }
            for candidate in candidates
            if candidate.get("status") == "available" and candidate.get("model_path")
        ],
    ]
    query_results: list[dict[str, Any]] = []
    for smoke_query in smoke_query_list:
        matched_query, query_rows, match_strategy = _find_smoke_query_rows(rows, smoke_query)
        if not query_rows:
            query_results.append(
                {
                    "requested_query": smoke_query,
                    "matched_query": matched_query,
                    "match_strategy": match_strategy,
                    "rows_count": 0,
                    "status": "missing",
                    "models": [],
                }
            )
            continue

        representative_row = query_rows[0]
        query_results.append(
            {
                "requested_query": smoke_query,
                "matched_query": matched_query,
                "match_strategy": match_strategy,
                "rows_count": len(query_rows),
                "status": "covered",
                "representative_url": str(representative_row.get("url") or ""),
                "representative_rank": int(representative_row.get("rank") or 0),
                "models": [
                    _build_model_explanation_summary(
                        model_name=str(model_entry["model_name"]),
                        model_path=str(model_entry["model_path"]),
                        row=representative_row,
                        feature_columns=model_entry.get("feature_columns") or feature_columns,
                    )
                    for model_entry in model_entries
                ],
            }
        )

    model_guardrails: dict[str, dict[str, Any]] = {}
    for model_entry in model_entries:
        model_name = str(model_entry["model_name"])
        model_summaries = [
            model
            for query_result in query_results
            for model in query_result.get("models", [])
            if isinstance(model, dict) and model.get("model_name") == model_name
        ]
        model_guardrails[model_name] = {
            "passed": bool(model_summaries) and all(bool(model.get("bounded")) for model in model_summaries),
            "covered_queries_count": len(model_summaries),
            "bounded_scores_count": sum(1 for model in model_summaries if bool(model.get("bounded"))),
        }

    return {
        "requested_queries_count": len(smoke_query_list),
        "covered_queries_count": sum(1 for item in query_results if item.get("status") == "covered"),
        "exact_match_queries_count": sum(1 for item in query_results if item.get("match_strategy") == "exact_casefold"),
        "fallback_match_queries_count": sum(1 for item in query_results if item.get("match_strategy") == "contains_all_terms"),
        "missing_queries_count": sum(1 for item in query_results if item.get("status") == "missing"),
        "query_results": query_results,
        "model_guardrails": model_guardrails,
    }


def _apply_runtime_explanation_guardrails(candidates: list[dict[str, Any]], smoke_summary: dict[str, Any]) -> None:
    model_guardrails = smoke_summary.get("model_guardrails") if isinstance(smoke_summary.get("model_guardrails"), dict) else {}
    for candidate in candidates:
        candidate_name = str(candidate.get("candidate_name") or "")
        guardrail = model_guardrails.get(candidate_name)
        if isinstance(guardrail, dict):
            candidate["runtime_explanation_guardrail"] = guardrail
        else:
            candidate["runtime_explanation_guardrail"] = {
                "passed": False,
                "covered_queries_count": 0,
                "bounded_scores_count": 0,
                "reason": "candidate_missing_from_smoke_summary",
            }


def _apply_explainability_sensibility_guardrails(
    candidates: list[dict[str, Any]],
    sensibility_summary: dict[str, Any],
) -> None:
    model_guardrails = sensibility_summary.get("model_guardrails")
    resolved_guardrails = model_guardrails if isinstance(model_guardrails, dict) else {}
    for candidate in candidates:
        candidate_name = str(candidate.get("candidate_name") or "")
        guardrail = resolved_guardrails.get(candidate_name)
        candidate["explainability_sensibility_guardrail"] = (
            guardrail
            if isinstance(guardrail, dict)
            else {"passed": False, "reason": "candidate_missing_from_sensibility_summary"}
        )


def build_shadow_decision(
    *,
    reference_model: dict[str, Any],
    candidates: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
) -> dict[str, Any]:
    eligible_candidate_names = {
        str(comparison.get("candidate_name"))
        for comparison in comparisons
        if isinstance(comparison.get("guardrails"), dict) and comparison["guardrails"].get("publish_gate_passed")
    }
    eligible_candidates = [
        candidate
        for candidate in candidates
        if str(candidate.get("candidate_name")) in eligible_candidate_names and candidate.get("status") == "available"
    ]
    if not eligible_candidates:
        return {
            "publish_recommendation": "keep_reference",
            "selected_candidate": None,
            "reason": "no_candidate_passed_all_publish_gates",
            "reference_model": reference_model.get("model_info"),
        }

    best_candidate = max(eligible_candidates, key=candidate_sort_key)
    if candidate_sort_key(best_candidate) <= candidate_sort_key(reference_model):
        return {
            "publish_recommendation": "keep_reference",
            "selected_candidate": str(best_candidate.get("candidate_name")),
            "reason": "best_gate_passing_candidate_does_not_outperform_reference_sort_key",
            "reference_model": reference_model.get("model_info"),
        }
    return {
        "publish_recommendation": "publish_candidate",
        "selected_candidate": str(best_candidate.get("candidate_name")),
        "reason": "candidate_passed_all_publish_gates_and_outperformed_reference",
        "reference_model": reference_model.get("model_info"),
    }


def _serialize_shadow_model(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_name": str(model.get("candidate_name") or "unknown"),
        "candidate_family": str(model.get("candidate_family") or "unknown"),
        "status": str(model.get("status") or "unknown"),
        "model_path": model.get("model_path"),
        "model_info": model.get("model_info") if isinstance(model.get("model_info"), dict) else None,
        "model_type": model.get("model_type"),
        "model_schema_version": model.get("model_schema_version"),
        "feature_count": model.get("feature_count"),
        "metrics": model.get("metrics") if isinstance(model.get("metrics"), dict) else {},
        "stability": model.get("stability") if isinstance(model.get("stability"), dict) else {},
        "feature_importance_summary": model.get("feature_importance_summary")
        if isinstance(model.get("feature_importance_summary"), dict)
        else {"available": False, "top_features": []},
        "runtime_explanation_guardrail": model.get("runtime_explanation_guardrail")
        if isinstance(model.get("runtime_explanation_guardrail"), dict)
        else {"passed": False},
        "explainability_sensibility_guardrail": model.get("explainability_sensibility_guardrail")
        if isinstance(model.get("explainability_sensibility_guardrail"), dict)
        else {"passed": False},
        "reason": model.get("reason"),
    }


def run_shadow_benchmark(
    *,
    dataset_path: str | Path,
    reference_model_path: str | Path = DEFAULT_MODEL_PATH,
    candidate_model_paths: Iterable[str | Path] = DEFAULT_D35_CANDIDATE_PATHS,
    output_dir: str | Path | None = DEFAULT_D35_SHADOW_OUTPUT_DIR,
    smoke_queries: Iterable[str] = DEFAULT_D35_SMOKE_QUERIES,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    rows = load_dataset_rows(dataset_path)
    if len(rows) < 4:
        raise ValueError("At least 4 dataset rows are required for D35 shadow benchmark")
    train_rows, validation_rows, split_metadata = split_dataset_rows(rows, test_size=test_size, random_state=random_state)
    if not train_rows or not validation_rows:
        raise ValueError("D35 shadow benchmark split produced an empty train or validation set")

    reference_model = evaluate_shadow_artifact(
        candidate_name="reference_artifact",
        candidate_family="baseline",
        model_path=reference_model_path,
        validation_rows=validation_rows,
    )
    if reference_model.get("status") != "available":
        raise ValueError(f"Reference model is not available: {reference_model_path}")

    candidates = [
        evaluate_shadow_artifact(
            candidate_name=Path(candidate_model_path).stem,
            candidate_family="candidate",
            model_path=candidate_model_path,
            validation_rows=validation_rows,
        )
        for candidate_model_path in candidate_model_paths
    ]
    smoke_query_list = tuple(smoke_queries)
    smoke_summary = build_smoke_explainability_summary(
        rows=rows,
        reference_model=reference_model,
        candidates=candidates,
        smoke_queries=smoke_query_list,
    )
    _apply_runtime_explanation_guardrails(candidates, smoke_summary)
    sensibility_summary = build_explainability_sensibility_summary(
        candidates=candidates,
        smoke_summary=smoke_summary,
    )
    _apply_explainability_sensibility_guardrails(candidates, sensibility_summary)
    comparisons = [
        {
            "candidate_name": str(candidate.get("candidate_name") or "unknown"),
            "candidate_family": str(candidate.get("candidate_family") or "unknown"),
            "model_path": candidate.get("model_path"),
            "candidate_metrics": candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
            "reference_metrics": reference_model.get("metrics") if isinstance(reference_model.get("metrics"), dict) else {},
            "metric_deltas": build_metric_deltas(
                candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
                reference_model.get("metrics") if isinstance(reference_model.get("metrics"), dict) else {},
            ),
            "guardrails": build_candidate_guardrails(candidate, reference_model),
        }
        for candidate in candidates
    ]
    available_candidates = [candidate for candidate in candidates if candidate.get("status") == "available"]
    best_candidate_by_ranking_metrics = max(available_candidates, key=candidate_sort_key) if available_candidates else None
    split_summary = {
        **split_metadata,
        "train_rows_count": len(train_rows),
        "validation_rows_count": len(validation_rows),
        "train_queries_count": len({str(row.get("query") or "") for row in train_rows}),
        "validation_queries_count": len({str(row.get("query") or "") for row in validation_rows}),
    }
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_path": str(Path(dataset_path)),
        "dataset_version": str(rows[0].get("dataset_version") or Path(dataset_path).stem),
        "rows_count": len(rows),
        "queries_count": len({str(row.get("query") or "") for row in rows}),
        "split": split_summary,
        "reference_model": _serialize_shadow_model(reference_model),
        "candidates": [_serialize_shadow_model(candidate) for candidate in candidates],
        "candidate_comparisons": comparisons,
        "best_candidate_by_ranking_metrics": _serialize_shadow_model(best_candidate_by_ranking_metrics)
        if best_candidate_by_ranking_metrics is not None
        else None,
        "smoke_explainability": smoke_summary,
        "explainability_sensibility": sensibility_summary,
        "decision": build_shadow_decision(
            reference_model=reference_model,
            candidates=candidates,
            comparisons=comparisons,
        ),
    }
    report_paths: dict[str, str] | None = None
    if output_dir is not None:
        report_paths = write_shadow_benchmark_report(report, output_dir)
        report["report_paths"] = report_paths
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--reference-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--candidate-model", action="append", default=[])
    parser.add_argument("--output-dir", default=str(DEFAULT_D35_SHADOW_OUTPUT_DIR))
    parser.add_argument("--smoke-query", action="append", default=[])
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    report = run_shadow_benchmark(
        dataset_path=args.dataset,
        reference_model_path=args.reference_model,
        candidate_model_paths=args.candidate_model or DEFAULT_D35_CANDIDATE_PATHS,
        output_dir=args.output_dir or None,
        smoke_queries=args.smoke_query or DEFAULT_D35_SMOKE_QUERIES,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
