from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
from statistics import pstdev
from typing import Any
from app.ml.dataset_quality import default_manifest_path
from app.ml.model import DEFAULT_MODEL_PATH, clear_model_cache, load_model_artifact, save_model
from app.ml.model_schema import DEFAULT_TRAINING_MODEL_SCHEMA_VERSION, resolve_model_feature_schema
from app.ml.publish import (
    ARTIFACTS_DIR,
    build_artifact_metadata_path,
    build_artifact_public_metadata,
    build_dataset_metadata,
    build_primary_artifact_version,
    build_primary_dataset_version,
    build_versioned_artifact_path,
    ensure_manifest_ready,
    load_training_manifest,
    write_artifact_public_metadata,
)
from app.ml.train import (
    candidate_sort_key,
    evaluate_model_rows,
    load_dataset_rows,
    ranking_metrics,
    rows_to_matrix,
    split_dataset_rows,
)
BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
DEFAULT_RANKING_DATASET_PATH = DATA_DIR / "dataset_versions" / "dataset-v2" / "dataset.csv"
DEFAULT_RANKING_MANIFEST_PATH = DATA_DIR / "dataset_versions" / "dataset-v2" / "manifest.json"
DEFAULT_RANKING_REPORTS_DIR = ARTIFACTS_DIR / "ranking_reports"
CATBOOST_RANKER_CANDIDATE = "catboost_ranker"
LIGHTGBM_RANKER_CANDIDATE = "lightgbm_ranker"
XGBOOST_RANKER_CANDIDATE = "xgboost_rank_pairwise"
RANKING_CANDIDATE_NAMES = (
    CATBOOST_RANKER_CANDIDATE,
    LIGHTGBM_RANKER_CANDIDATE,
    XGBOOST_RANKER_CANDIDATE,
)
def _safe_stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return round(float(pstdev(values)), 6)
def _sorted_rows_by_query(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("query") or ""),
            int(row.get("rank") or 0),
            str(row.get("url") or ""),
        ),
    )
def _build_group_ids(rows: list[dict[str, str]]) -> list[int]:
    group_ids: list[int] = []
    current_group = 0
    previous_query: str | None = None
    for row in rows:
        query = str(row.get("query") or "")
        if query != previous_query:
            current_group += 1
            previous_query = query
        group_ids.append(current_group)
    return group_ids
def _build_group_sizes(rows: list[dict[str, str]]) -> list[int]:
    group_sizes: list[int] = []
    current_query: str | None = None
    current_count = 0
    for row in rows:
        query = str(row.get("query") or "")
        if query != current_query:
            if current_count > 0:
                group_sizes.append(current_count)
            current_query = query
            current_count = 1
        else:
            current_count += 1
    if current_count > 0:
        group_sizes.append(current_count)
    return group_sizes
def _enrich_rows_with_predictions(rows: list[dict[str, str]], predictions: list[float]) -> list[dict[str, Any]]:
    enriched_rows: list[dict[str, Any]] = []
    for row, prediction in zip(rows, predictions, strict=False):
        enriched_row: dict[str, Any] = dict(row)
        enriched_row["predicted_score"] = float(prediction)
        enriched_rows.append(enriched_row)
    return enriched_rows
def build_query_group_breakdown(rows: list[dict[str, str]], predictions: list[float]) -> list[dict[str, Any]]:
    grouped_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _enrich_rows_with_predictions(rows, predictions):
        grouped_rows[str(row.get("query") or "")].append(row)
    breakdown: list[dict[str, Any]] = []
    for query, query_rows in sorted(grouped_rows.items()):
        query_predictions = [float(row["predicted_score"]) for row in query_rows]
        metrics = ranking_metrics(query_rows, query_predictions)
        intents = sorted({str(row.get("intent") or "unknown") for row in query_rows})
        breakdown.append(
            {
                "query": query,
                "intent": intents[0] if len(intents) == 1 else "mixed",
                "rows_count": len(query_rows),
                "metrics": metrics,
            }
        )
    return breakdown
def build_intent_breakdown(rows: list[dict[str, str]], predictions: list[float]) -> list[dict[str, Any]]:
    rows_by_intent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in _enrich_rows_with_predictions(rows, predictions):
        rows_by_intent[str(row.get("intent") or "unknown")].append(row)
    breakdown: list[dict[str, Any]] = []
    for intent, intent_rows in sorted(rows_by_intent.items()):
        intent_predictions = [float(row["predicted_score"]) for row in intent_rows]
        metrics = ranking_metrics(intent_rows, intent_predictions)
        breakdown.append(
            {
                "intent": intent,
                "rows_count": len(intent_rows),
                "queries_count": len({str(row.get("query") or "") for row in intent_rows}),
                "metrics": metrics,
            }
        )
    return breakdown
def build_stability_summary(rows: list[dict[str, str]], predictions: list[float]) -> dict[str, Any]:
    query_group_breakdown = build_query_group_breakdown(rows, predictions)
    intent_breakdown = build_intent_breakdown(rows, predictions)
    return {
        "query_groups_count": len(query_group_breakdown),
        "intents_count": len(intent_breakdown),
        "query_group_breakdown": query_group_breakdown,
        "intent_breakdown": intent_breakdown,
        "query_group_metric_stddev": {
            "spearman_mean": _safe_stddev([float(item["metrics"].get("spearman_mean", 0.0)) for item in query_group_breakdown]),
            "ndcg_at_10": _safe_stddev([float(item["metrics"].get("ndcg_at_10", 0.0)) for item in query_group_breakdown]),
            "top_3_hit_rate": _safe_stddev([float(item["metrics"].get("top_3_hit_rate", 0.0)) for item in query_group_breakdown]),
        },
        "intent_metric_stddev": {
            "spearman_mean": _safe_stddev([float(item["metrics"].get("spearman_mean", 0.0)) for item in intent_breakdown]),
            "ndcg_at_10": _safe_stddev([float(item["metrics"].get("ndcg_at_10", 0.0)) for item in intent_breakdown]),
            "top_3_hit_rate": _safe_stddev([float(item["metrics"].get("top_3_hit_rate", 0.0)) for item in intent_breakdown]),
        },
    }
def build_feature_importance_summary(
    model: Any,
    feature_columns: list[str] | tuple[str, ...],
    top_n: int = 10,
) -> dict[str, Any]:
    importances: list[float] | None = None
    if hasattr(model, "get_feature_importance"):
        for importance_type in (None, "PredictionValuesChange", "FeatureImportance"):
            try:
                raw_values = model.get_feature_importance() if importance_type is None else model.get_feature_importance(type=importance_type)
                importances = [float(value) for value in raw_values]
                break
            except Exception:
                importances = None
    elif hasattr(model, "feature_importances_"):
        try:
            importances = [float(value) for value in model.feature_importances_]
        except Exception:
            importances = None
    if importances is None or len(importances) != len(feature_columns):
        return {"available": False, "top_features": []}
    ranked_features = sorted(
        [
            {"feature": feature_name, "importance": round(float(importance), 6)}
            for feature_name, importance in zip(feature_columns, importances, strict=False)
        ],
        key=lambda item: float(item["importance"]),
        reverse=True,
    )
    top_features = [item for item in ranked_features if float(item["importance"]) > 0][:top_n]
    return {
        "available": bool(top_features),
        "top_features": top_features,
        "feature_count": len(feature_columns),
    }
def _serialize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_name": str(candidate["candidate_name"]),
        "candidate_family": str(candidate["candidate_family"]),
        "status": str(candidate["status"]),
        "model_path": candidate.get("model_path"),
        "model_info": candidate.get("model_info") if isinstance(candidate.get("model_info"), dict) else None,
        "model_type": candidate.get("model_type"),
        "model_schema_version": candidate.get("model_schema_version"),
        "feature_count": candidate.get("feature_count"),
        "metrics": candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
        "stability": candidate.get("stability") if isinstance(candidate.get("stability"), dict) else {},
        "feature_importance_summary": candidate.get("feature_importance_summary") if isinstance(candidate.get("feature_importance_summary"), dict) else {"available": False, "top_features": []},
        "reason": candidate.get("reason"),
    }
def _unavailable_candidate(
    candidate_name: str,
    reason: str,
    *,
    model_schema_version: str,
    feature_count: int,
) -> dict[str, Any]:
    return {
        "candidate_name": candidate_name,
        "candidate_family": "ranking",
        "status": "unavailable",
        "model_type": None,
        "model_schema_version": model_schema_version,
        "feature_count": feature_count,
        "metrics": {},
        "stability": {},
        "feature_importance_summary": {"available": False, "top_features": []},
        "reason": reason,
        "model": None,
    }
def _available_candidate(
    candidate_name: str,
    model: Any,
    predictions: list[float],
    validation_rows: list[dict[str, str]],
    *,
    model_schema_version: str,
    feature_columns: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    metrics = evaluate_model_rows(model, validation_rows, feature_columns=feature_columns)
    return {
        "candidate_name": candidate_name,
        "candidate_family": "ranking",
        "status": "available",
        "model_type": model.__class__.__name__,
        "model_schema_version": model_schema_version,
        "feature_count": len(feature_columns),
        "metrics": metrics,
        "stability": build_stability_summary(validation_rows, predictions),
        "feature_importance_summary": build_feature_importance_summary(model, feature_columns),
        "reason": None,
        "model": model,
    }


def evaluate_candidate_model_artifact(
    validation_rows: list[dict[str, str]],
    candidate_model_path: str | Path | None,
) -> dict[str, Any] | None:
    if candidate_model_path is None:
        return None
    artifact = load_model_artifact(candidate_model_path)
    if artifact is None:
        return _unavailable_candidate(
            "candidate_artifact",
            "candidate_artifact_not_found_or_invalid",
            model_schema_version="unknown",
            feature_count=0,
        )
    feature_columns = artifact.get("feature_columns") if isinstance(artifact.get("feature_columns"), (list, tuple)) else None
    metrics = evaluate_model_rows(artifact["model"], validation_rows, feature_columns=feature_columns)
    x_validation, _ = rows_to_matrix(validation_rows, feature_columns=feature_columns)
    predictions = [float(value) for value in artifact["model"].predict(x_validation)]
    return {
        "candidate_name": "candidate_artifact",
        "candidate_family": "pointwise_candidate",
        "status": "available",
        "model_type": artifact.get("model_type", artifact["model"].__class__.__name__),
        "model_schema_version": artifact.get("model_schema_version"),
        "feature_count": len(feature_columns or []),
        "metrics": metrics,
        "stability": build_stability_summary(validation_rows, predictions),
        "feature_importance_summary": build_feature_importance_summary(artifact["model"], feature_columns or []),
        "reason": None,
        "model": artifact["model"],
        "model_path": str(Path(candidate_model_path)),
        "model_info": {
            "source": artifact.get("source", "unknown"),
            "model_type": artifact.get("model_type", artifact["model"].__class__.__name__),
            "trained_at": artifact.get("trained_at"),
            "published_at": artifact.get("published_at"),
            "artifact_version": artifact.get("artifact_version"),
            "dataset_version": artifact.get("dataset_version"),
            "model_schema_version": artifact.get("model_schema_version"),
            "feature_count": len(feature_columns or []),
        },
    }
def train_catboost_ranker_candidate(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    *,
    feature_columns: list[str] | tuple[str, ...],
    model_schema_version: str,
    random_state: int,
    iterations: int = 120,
) -> dict[str, Any]:
    try:
        from catboost import CatBoostError, CatBoostRanker
    except ImportError:
        return _unavailable_candidate(
            CATBOOST_RANKER_CANDIDATE,
            "catboost_not_installed",
            model_schema_version=model_schema_version,
            feature_count=len(feature_columns),
        )
    sorted_train_rows = _sorted_rows_by_query(train_rows)
    x_train, y_train = rows_to_matrix(sorted_train_rows, feature_columns=feature_columns)
    group_id = _build_group_ids(sorted_train_rows)
    model = CatBoostRanker(
        loss_function="YetiRankPairwise",
        iterations=iterations,
        depth=6,
        learning_rate=0.05,
        random_seed=random_state,
        verbose=False,
    )
    try:
        model.fit(x_train, y_train, group_id=group_id)
        x_validation, _ = rows_to_matrix(validation_rows, feature_columns=feature_columns)
        predictions = [float(value) for value in model.predict(x_validation)]
    except CatBoostError as error:
        return _unavailable_candidate(
            CATBOOST_RANKER_CANDIDATE,
            f"catboost_ranker_training_failed: {error}",
            model_schema_version=model_schema_version,
            feature_count=len(feature_columns),
        )
    return _available_candidate(
        CATBOOST_RANKER_CANDIDATE,
        model,
        predictions,
        validation_rows,
        model_schema_version=model_schema_version,
        feature_columns=feature_columns,
    )
def train_lightgbm_ranker_candidate(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    *,
    feature_columns: list[str] | tuple[str, ...],
    model_schema_version: str,
    random_state: int,
    estimators: int = 150,
) -> dict[str, Any]:
    try:
        from lightgbm import LGBMRanker
    except ImportError:
        return _unavailable_candidate(
            LIGHTGBM_RANKER_CANDIDATE,
            "lightgbm_not_installed",
            model_schema_version=model_schema_version,
            feature_count=len(feature_columns),
        )
    sorted_train_rows = _sorted_rows_by_query(train_rows)
    x_train, y_train = rows_to_matrix(sorted_train_rows, feature_columns=feature_columns)
    group_sizes = _build_group_sizes(sorted_train_rows)
    model = LGBMRanker(
        objective="lambdarank",
        n_estimators=estimators,
        learning_rate=0.05,
        num_leaves=31,
        random_state=random_state,
    )
    model.fit(x_train, y_train, group=group_sizes)
    x_validation, _ = rows_to_matrix(validation_rows, feature_columns=feature_columns)
    predictions = [float(value) for value in model.predict(x_validation)]
    return _available_candidate(
        LIGHTGBM_RANKER_CANDIDATE,
        model,
        predictions,
        validation_rows,
        model_schema_version=model_schema_version,
        feature_columns=feature_columns,
    )
def train_xgboost_ranker_candidate(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    *,
    feature_columns: list[str] | tuple[str, ...],
    model_schema_version: str,
    random_state: int,
    estimators: int = 150,
) -> dict[str, Any]:
    try:
        from xgboost import XGBRanker
    except ImportError:
        return _unavailable_candidate(
            XGBOOST_RANKER_CANDIDATE,
            "xgboost_not_installed",
            model_schema_version=model_schema_version,
            feature_count=len(feature_columns),
        )
    sorted_train_rows = _sorted_rows_by_query(train_rows)
    x_train, y_train = rows_to_matrix(sorted_train_rows, feature_columns=feature_columns)
    qid = _build_group_ids(sorted_train_rows)
    model = XGBRanker(
        objective="rank:pairwise",
        n_estimators=estimators,
        learning_rate=0.05,
        max_depth=6,
        random_state=random_state,
    )
    model.fit(x_train, y_train, qid=qid)
    x_validation, _ = rows_to_matrix(validation_rows, feature_columns=feature_columns)
    predictions = [float(value) for value in model.predict(x_validation)]
    return _available_candidate(
        XGBOOST_RANKER_CANDIDATE,
        model,
        predictions,
        validation_rows,
        model_schema_version=model_schema_version,
        feature_columns=feature_columns,
    )
def evaluate_reference_model(
    validation_rows: list[dict[str, str]],
    reference_model_path: str | Path | None,
) -> dict[str, Any] | None:
    if reference_model_path is None:
        return None
    artifact = load_model_artifact(reference_model_path)
    if artifact is None:
        return None
    feature_columns = artifact.get("feature_columns") if isinstance(artifact.get("feature_columns"), (list, tuple)) else None
    metrics = evaluate_model_rows(artifact["model"], validation_rows, feature_columns=feature_columns)
    x_validation, _ = rows_to_matrix(validation_rows, feature_columns=feature_columns)
    predictions = [float(value) for value in artifact["model"].predict(x_validation)]
    return {
        "candidate_name": "reference_artifact",
        "candidate_family": "baseline",
        "status": "available",
        "model_type": artifact.get("model_type", artifact["model"].__class__.__name__),
        "model_schema_version": artifact.get("model_schema_version"),
        "feature_count": len(feature_columns or []),
        "metrics": metrics,
        "stability": build_stability_summary(validation_rows, predictions),
        "reason": None,
        "model": artifact["model"],
        "model_info": {
            "source": artifact.get("source", "unknown"),
            "model_type": artifact.get("model_type", artifact["model"].__class__.__name__),
            "trained_at": artifact.get("trained_at"),
            "published_at": artifact.get("published_at"),
            "artifact_version": artifact.get("artifact_version"),
            "dataset_version": artifact.get("dataset_version"),
            "model_schema_version": artifact.get("model_schema_version"),
            "feature_count": len(feature_columns or []),
        },
    }
def build_ranking_benchmark_comparison(
    best_candidate: dict[str, Any] | None,
    reference_candidate: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if best_candidate is None or reference_candidate is None:
        return None
    best_metrics = best_candidate.get("metrics") if isinstance(best_candidate.get("metrics"), dict) else {}
    reference_metrics = reference_candidate.get("metrics") if isinstance(reference_candidate.get("metrics"), dict) else {}
    deltas = {
        metric_name: round(float(best_metrics.get(metric_name, 0.0)) - float(reference_metrics.get(metric_name, 0.0)), 6)
        for metric_name in ("spearman_mean", "ndcg_at_10", "top_3_hit_rate", "rmse", "mae")
        if metric_name in best_metrics or metric_name in reference_metrics
    }
    candidate_wins = candidate_sort_key(best_candidate) > candidate_sort_key(reference_candidate)
    return {
        "best_candidate": str(best_candidate.get("candidate_name") or "unknown"),
        "reference_candidate": str(reference_candidate.get("candidate_name") or "reference_artifact"),
        "metric_deltas": deltas,
        "publish_recommendation": "publish_candidate" if candidate_wins else "keep_reference",
        "candidate_outperforms_reference": candidate_wins,
    }
def build_default_ranking_report_output_dir(dataset_version: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    dataset_slug = dataset_version.strip().replace(" ", "-") or "dataset"
    return DEFAULT_RANKING_REPORTS_DIR / f"{dataset_slug}-{timestamp}"
def render_ranking_benchmark_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Ranking Benchmark Report",
        "",
        f"- Dataset path: `{report.get('dataset_path')}`",
        f"- Dataset version: `{report.get('dataset_version')}`",
        f"- Model schema version: `{report.get('model_schema_version')}`",
        f"- Feature count: `{report.get('feature_count')}`",
        f"- Split mode: `{report.get('split', {}).get('split_mode')}`",
        f"- Validation rows: `{report.get('validation_rows')}`",
        "",
        "## Reference Baseline",
        "",
    ]
    reference_model = report.get("reference_model") if isinstance(report.get("reference_model"), dict) else None
    if reference_model is None:
        lines.append("Reference model is not available.")
    else:
        lines.extend(
            [
                f"- Artifact version: `{reference_model.get('model_info', {}).get('artifact_version')}`",
                f"- Model type: `{reference_model.get('model_info', {}).get('model_type')}`",
                f"- Dataset version: `{reference_model.get('model_info', {}).get('dataset_version')}`",
                f"- NDCG@10: `{reference_model.get('metrics', {}).get('ndcg_at_10')}`",
                f"- Top-3 hit rate: `{reference_model.get('metrics', {}).get('top_3_hit_rate')}`",
                f"- Spearman mean: `{reference_model.get('metrics', {}).get('spearman_mean')}`",
                "",
            ]
        )
    lines.extend(["## Ranking Candidates", ""])
    candidates = report.get("candidates") if isinstance(report.get("candidates"), list) else []
    for candidate in candidates:
        lines.extend(
            [
                f"### {candidate.get('candidate_name')}",
                f"- Status: `{candidate.get('status')}`",
                f"- Model type: `{candidate.get('model_type')}`",
                f"- NDCG@10: `{candidate.get('metrics', {}).get('ndcg_at_10')}`",
                f"- Top-3 hit rate: `{candidate.get('metrics', {}).get('top_3_hit_rate')}`",
                f"- Spearman mean: `{candidate.get('metrics', {}).get('spearman_mean')}`",
                f"- Query-group NDCG stddev: `{candidate.get('stability', {}).get('query_group_metric_stddev', {}).get('ndcg_at_10')}`",
                f"- Intent NDCG stddev: `{candidate.get('stability', {}).get('intent_metric_stddev', {}).get('ndcg_at_10')}`",
            ]
        )
        top_features = candidate.get("feature_importance_summary", {}).get("top_features") if isinstance(candidate.get("feature_importance_summary"), dict) else []
        if top_features:
            lines.append("- Top features:")
            for feature in top_features[:5]:
                lines.append(f"  - `{feature.get('feature')}`: `{feature.get('importance')}`")
        reason = candidate.get("reason")
        if reason:
            lines.append(f"- Reason: `{reason}`")
        lines.append("")
    best_candidate = report.get("best_candidate") if isinstance(report.get("best_candidate"), dict) else None
    if best_candidate is not None:
        lines.extend(
            [
                "## Selected Candidate",
                "",
                f"- Candidate: `{best_candidate.get('candidate_name')}`",
                f"- Model type: `{best_candidate.get('model_type')}`",
                f"- NDCG@10: `{best_candidate.get('metrics', {}).get('ndcg_at_10')}`",
                f"- Top-3 hit rate: `{best_candidate.get('metrics', {}).get('top_3_hit_rate')}`",
                f"- Spearman mean: `{best_candidate.get('metrics', {}).get('spearman_mean')}`",
                "",
            ]
        )
    comparison = report.get("comparison_to_reference") if isinstance(report.get("comparison_to_reference"), dict) else None
    if comparison is not None:
        lines.extend(["## Comparison To Reference", ""])
        lines.append(f"- Publish recommendation: `{comparison.get('publish_recommendation')}`")
        lines.append(f"- Candidate outperforms reference: `{comparison.get('candidate_outperforms_reference')}`")
        for metric_name, delta in (comparison.get("metric_deltas") or {}).items():
            lines.append(f"- `{metric_name}`: `{delta}`")
        lines.append("")
    candidate_model_comparison = report.get("candidate_model_comparison_to_reference")
    if isinstance(candidate_model_comparison, dict):
        lines.extend(["## Candidate Artifact Comparison To Reference", ""])
        lines.append(f"- Publish recommendation: `{candidate_model_comparison.get('publish_recommendation')}`")
        lines.append(
            f"- Candidate outperforms reference: `{candidate_model_comparison.get('candidate_outperforms_reference')}`"
        )
        for metric_name, delta in (candidate_model_comparison.get("metric_deltas") or {}).items():
            lines.append(f"- `{metric_name}`: `{delta}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"

def write_ranking_benchmark_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    json_path = resolved_output_dir / "ranking-benchmark-report.json"
    markdown_path = resolved_output_dir / "ranking-benchmark-report.md"
    report_paths = {"json_path": str(json_path), "markdown_path": str(markdown_path)}
    report_with_paths = {**report, "report_paths": report_paths}
    json_path.write_text(json.dumps(report_with_paths, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_ranking_benchmark_markdown(report_with_paths), encoding="utf-8")
    return report_paths
def _run_ranking_benchmark_internal(
    dataset_path: str | Path = DEFAULT_RANKING_DATASET_PATH,
    reference_model_path: str | Path | None = DEFAULT_MODEL_PATH,
    candidate_model_path: str | Path | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
    model_schema_version: str = DEFAULT_TRAINING_MODEL_SCHEMA_VERSION,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    resolved_schema = resolve_model_feature_schema(
        model_schema_version=model_schema_version,
        default_version=DEFAULT_TRAINING_MODEL_SCHEMA_VERSION,
    )
    rows = load_dataset_rows(dataset_path)
    if len(rows) < 4:
        raise ValueError("At least 4 dataset rows are required for ranking benchmark")
    train_rows, validation_rows, split_metadata = split_dataset_rows(rows, test_size=test_size, random_state=random_state)
    if not train_rows or not validation_rows:
        raise ValueError("Ranking benchmark split produced an empty train or validation set")
    ranking_candidates = [
        train_catboost_ranker_candidate(
            train_rows,
            validation_rows,
            feature_columns=resolved_schema.feature_columns,
            model_schema_version=resolved_schema.version,
            random_state=random_state,
        ),
        train_lightgbm_ranker_candidate(
            train_rows,
            validation_rows,
            feature_columns=resolved_schema.feature_columns,
            model_schema_version=resolved_schema.version,
            random_state=random_state,
        ),
        train_xgboost_ranker_candidate(
            train_rows,
            validation_rows,
            feature_columns=resolved_schema.feature_columns,
            model_schema_version=resolved_schema.version,
            random_state=random_state,
        ),
    ]
    candidate_model = evaluate_candidate_model_artifact(validation_rows, candidate_model_path)
    candidates = [candidate for candidate in [candidate_model, *ranking_candidates] if candidate is not None]
    available_candidates = [candidate for candidate in candidates if candidate.get("status") == "available"]
    best_candidate = max(available_candidates, key=candidate_sort_key) if available_candidates else None
    reference_candidate = evaluate_reference_model(validation_rows, reference_model_path)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_path": str(Path(dataset_path)),
        "dataset_version": str(rows[0].get("dataset_version") or Path(dataset_path).stem),
        "model_schema_version": resolved_schema.version,
        "feature_count": len(resolved_schema.feature_columns),
        "rows_count": len(rows),
        "queries_count": len({str(row.get("query") or "") for row in rows}),
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "split": split_metadata,
        "reference_model": None,
        "candidate_model_path": str(Path(candidate_model_path)) if candidate_model_path is not None else None,
        "candidate_model": _serialize_candidate(candidate_model) if candidate_model is not None else None,
        "candidates": [_serialize_candidate(candidate) for candidate in candidates],
        "best_candidate": _serialize_candidate(best_candidate) if best_candidate is not None else None,
        "comparison_to_reference": None,
        "candidate_model_comparison_to_reference": None,
    }
    if reference_candidate is not None:
        report["reference_model"] = {
            "model_path": str(Path(reference_model_path)) if reference_model_path is not None else None,
            "model_info": reference_candidate.get("model_info"),
            "metrics": reference_candidate.get("metrics"),
            "stability": reference_candidate.get("stability"),
        }
        report["comparison_to_reference"] = build_ranking_benchmark_comparison(best_candidate, reference_candidate)
        if candidate_model is not None and candidate_model.get("status") == "available":
            report["candidate_model_comparison_to_reference"] = build_ranking_benchmark_comparison(
                candidate_model,
                reference_candidate,
            )
    report_paths: dict[str, str] | None = None
    if output_dir is not None:
        report_paths = write_ranking_benchmark_report(report, output_dir)
        report["report_paths"] = report_paths
    return {
        "report": report,
        "report_paths": report_paths,
        "best_candidate": best_candidate,
        "reference_candidate": reference_candidate,
    }
def run_ranking_benchmark(
    dataset_path: str | Path = DEFAULT_RANKING_DATASET_PATH,
    reference_model_path: str | Path | None = DEFAULT_MODEL_PATH,
    candidate_model_path: str | Path | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
    model_schema_version: str = DEFAULT_TRAINING_MODEL_SCHEMA_VERSION,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    internal_result = _run_ranking_benchmark_internal(
        dataset_path=dataset_path,
        reference_model_path=reference_model_path,
        candidate_model_path=candidate_model_path,
        test_size=test_size,
        random_state=random_state,
        model_schema_version=model_schema_version,
        output_dir=output_dir,
    )
    return internal_result["report"]
def publish_best_ranking_model(
    dataset_path: str | Path = DEFAULT_RANKING_DATASET_PATH,
    manifest_path: str | Path | None = None,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    reference_model_path: str | Path | None = DEFAULT_MODEL_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
    model_schema_version: str = DEFAULT_TRAINING_MODEL_SCHEMA_VERSION,
    report_output_dir: str | Path | None = None,
    force_publish: bool = False,
) -> dict[str, Any]:
    resolved_dataset_path = Path(dataset_path)
    resolved_model_path = Path(model_path)
    resolved_manifest_path = Path(manifest_path) if manifest_path is not None else default_manifest_path(resolved_dataset_path)
    manifest = load_training_manifest(resolved_manifest_path)
    ensure_manifest_ready(manifest)
    dataset_version = build_primary_dataset_version(resolved_dataset_path, manifest)
    resolved_report_output_dir = Path(report_output_dir) if report_output_dir is not None else build_default_ranking_report_output_dir(dataset_version)
    benchmark_result = _run_ranking_benchmark_internal(
        dataset_path=resolved_dataset_path,
        reference_model_path=reference_model_path,
        test_size=test_size,
        random_state=random_state,
        model_schema_version=model_schema_version,
        output_dir=resolved_report_output_dir,
    )
    best_candidate = benchmark_result["best_candidate"]
    if best_candidate is None or best_candidate.get("status") != "available" or best_candidate.get("model") is None:
        raise ValueError("No ranking candidate is available for publication.")
    reference_candidate = benchmark_result["reference_candidate"]
    if not force_publish and reference_candidate is not None:
        if candidate_sort_key(best_candidate) <= candidate_sort_key(reference_candidate):
            raise ValueError("Best ranking candidate does not outperform the current reference artifact. Use force_publish=True to override.")
    published_at = datetime.now(UTC)
    artifact_version = build_primary_artifact_version(dataset_version, published_at)
    dataset_metadata = build_dataset_metadata(manifest, dataset_version=dataset_version)
    resolved_schema = resolve_model_feature_schema(
        model_schema_version=model_schema_version,
        default_version=DEFAULT_TRAINING_MODEL_SCHEMA_VERSION,
    )
    metadata = {
        "artifact_version": artifact_version,
        "artifact_family": resolved_model_path.stem,
        "published_at": published_at.isoformat(),
        "dataset_metadata": dataset_metadata,
        "source": "local_dataset",
        "dataset_version": dataset_version,
        "model_schema_version": best_candidate.get("model_schema_version"),
        "feature_columns": list(resolved_schema.feature_columns),
        "candidate_name": best_candidate.get("candidate_name"),
        "candidate_family": best_candidate.get("candidate_family"),
        "feature_importance_summary": best_candidate.get("feature_importance_summary"),
        "benchmark_report_paths": benchmark_result.get("report_paths") or {},
    }
    save_model(
        model=best_candidate["model"],
        metrics=best_candidate["metrics"],
        model_path=resolved_model_path,
        metadata=metadata,
    )
    clear_model_cache()
    artifact = load_model_artifact(resolved_model_path)
    if artifact is None:
        raise RuntimeError(f"Published artifact was not created: {resolved_model_path}")
    versioned_artifact_path = build_versioned_artifact_path(resolved_model_path, artifact_version)
    versioned_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved_model_path, versioned_artifact_path)
    alias_metadata = {
        **build_artifact_public_metadata(artifact, resolved_model_path),
        "candidate_name": best_candidate.get("candidate_name"),
        "candidate_family": best_candidate.get("candidate_family"),
        "feature_importance_summary": best_candidate.get("feature_importance_summary"),
        "benchmark_report_paths": benchmark_result.get("report_paths") or {},
        "comparison_to_reference": benchmark_result["report"].get("comparison_to_reference"),
    }
    alias_metadata_path = write_artifact_public_metadata(alias_metadata, build_artifact_metadata_path(resolved_model_path))
    versioned_metadata_path = write_artifact_public_metadata(
        {**alias_metadata, "artifact_path": str(versioned_artifact_path)},
        build_artifact_metadata_path(versioned_artifact_path),
    )
    return {
        "dataset_path": str(resolved_dataset_path),
        "dataset_version": dataset_version,
        "manifest_path": str(resolved_manifest_path),
        "artifact_version": artifact_version,
        "published_model_path": str(resolved_model_path),
        "published_metadata_path": str(alias_metadata_path),
        "versioned_model_path": str(versioned_artifact_path),
        "versioned_metadata_path": str(versioned_metadata_path),
        "best_candidate": _serialize_candidate(best_candidate),
        "reference_model": benchmark_result["report"].get("reference_model"),
        "comparison_to_reference": benchmark_result["report"].get("comparison_to_reference"),
        "report_paths": benchmark_result.get("report_paths") or {},
        "force_publish": bool(force_publish),
    }
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_RANKING_DATASET_PATH))
    parser.add_argument("--manifest", default=str(DEFAULT_RANKING_MANIFEST_PATH))
    parser.add_argument("--reference-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--candidate-model", default="")
    parser.add_argument("--without-reference-model", action="store_true")
    parser.add_argument("--model-output", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--model-schema-version", default=DEFAULT_TRAINING_MODEL_SCHEMA_VERSION)
    parser.add_argument("--publish-best", action="store_true")
    parser.add_argument("--force-publish", action="store_true")
    args = parser.parse_args()
    reference_model_path = None if args.without_reference_model else args.reference_model
    output_dir = args.output_dir or None
    if args.publish_best:
        result = publish_best_ranking_model(
            dataset_path=args.dataset,
            manifest_path=args.manifest,
            model_path=args.model_output,
            reference_model_path=reference_model_path,
            test_size=args.test_size,
            random_state=args.random_state,
            model_schema_version=args.model_schema_version,
            report_output_dir=output_dir,
            force_publish=args.force_publish,
        )
    else:
        result = run_ranking_benchmark(
            dataset_path=args.dataset,
            reference_model_path=reference_model_path,
            candidate_model_path=args.candidate_model or None,
            test_size=args.test_size,
            random_state=args.random_state,
            model_schema_version=args.model_schema_version,
            output_dir=output_dir,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
if __name__ == "__main__":
    main()
