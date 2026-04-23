from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
from math import log2, sqrt
import json
from pathlib import Path
from typing import Any

from scipy.stats import spearmanr
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupShuffleSplit, train_test_split

from app.ml.dataset_builder import DEFAULT_DATASET_PATH
from app.ml.dataset_versions import infer_dataset_version
from app.ml.model import DEFAULT_MODEL_PATH, FEATURE_COLUMNS, clear_model_cache, save_model


def load_dataset_rows(dataset_path: str | Path = DEFAULT_DATASET_PATH) -> list[dict[str, str]]:
    resolved_path = Path(dataset_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Dataset not found: {resolved_path}")
    with resolved_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader if str(row.get("fetch_status") or "ok") != "failed"]


def prepare_training_data(
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
) -> tuple[list[list[float]], list[float], list[dict[str, str]]]:
    rows = load_dataset_rows(dataset_path)
    if not rows:
        raise ValueError("Dataset is empty")

    x: list[list[float]] = []
    y: list[float] = []
    for row in rows:
        x.append([float(row.get(feature_name, 0.0) or 0.0) for feature_name in FEATURE_COLUMNS])
        y.append(float(row["target_score"]))
    return x, y, rows


def rows_to_matrix(rows: list[dict[str, str]]) -> tuple[list[list[float]], list[float]]:
    x = [[float(row.get(feature_name, 0.0) or 0.0) for feature_name in FEATURE_COLUMNS] for row in rows]
    y = [float(row["target_score"]) for row in rows]
    return x, y


def split_dataset_rows(
    rows: list[dict[str, str]],
    test_size: float,
    random_state: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    unique_queries = {str(row.get("query") or "") for row in rows}
    if len(unique_queries) < 2:
        validation_count = max(1, int(round(len(rows) * test_size)))
        if validation_count >= len(rows):
            validation_count = 1
        train_rows, validation_rows = train_test_split(
            rows,
            test_size=validation_count,
            random_state=random_state,
        )
        return train_rows, validation_rows, {"split_mode": "row_fallback"}

    groups = [str(row.get("query") or "") for row in rows]
    splitter = GroupShuffleSplit(n_splits=1, test_size=test_size, random_state=random_state)
    train_indices, validation_indices = next(splitter.split(rows, groups=groups))
    train_rows = [rows[index] for index in train_indices]
    validation_rows = [rows[index] for index in validation_indices]
    return train_rows, validation_rows, {"split_mode": "group_by_query"}


def build_dataset_split_manifest(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    *,
    dataset_path: str | Path,
    dataset_version: str,
    test_size: float,
    random_state: int,
    split_metadata: dict[str, object],
) -> dict[str, object]:
    train_queries = {str(row.get("query") or "") for row in train_rows if str(row.get("query") or "").strip()}
    validation_queries = {str(row.get("query") or "") for row in validation_rows if str(row.get("query") or "").strip()}
    partition_map: dict[str, str] = {}
    for query in sorted(train_queries | validation_queries):
        in_train = query in train_queries
        in_validation = query in validation_queries
        if in_train and in_validation:
            partition_map[query] = "both"
        elif in_train:
            partition_map[query] = "train"
        else:
            partition_map[query] = "validation"

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_path": str(Path(dataset_path)),
        "dataset_version": dataset_version,
        "split_mode": str(split_metadata.get("split_mode") or "unknown"),
        "test_size": float(test_size),
        "random_state": int(random_state),
        "train_rows_count": len(train_rows),
        "validation_rows_count": len(validation_rows),
        "train_queries_count": len(train_queries),
        "validation_queries_count": len(validation_queries),
        "train_queries": sorted(train_queries),
        "validation_queries": sorted(validation_queries),
        "query_assignments": [
            {"query": query, "partition": partition_map[query]}
            for query in sorted(partition_map)
        ],
    }


def save_dataset_split_manifest(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    *,
    dataset_path: str | Path,
    dataset_version: str,
    test_size: float,
    random_state: int,
    split_metadata: dict[str, object],
    output_path: str | Path,
) -> dict[str, object]:
    manifest = build_dataset_split_manifest(
        train_rows,
        validation_rows,
        dataset_path=dataset_path,
        dataset_version=dataset_version,
        test_size=test_size,
        random_state=random_state,
        split_metadata=split_metadata,
    )
    resolved_output_path = Path(output_path)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**manifest, "split_path": str(resolved_output_path)}


def _rmse(y_true: list[float], y_pred: list[float]) -> float:
    return sqrt(float(mean_squared_error(y_true, y_pred)))


def _dcg(relevances: list[float]) -> float:
    total = 0.0
    for index, relevance in enumerate(relevances, start=1):
        total += (2.0**float(relevance) - 1.0) / log2(index + 1)
    return total


def _ndcg_at_k(query_rows: list[dict[str, Any]], k: int = 10) -> float:
    ranked_rows = sorted(query_rows, key=lambda item: float(item["predicted_score"]), reverse=True)[:k]
    actual_relevances = [float(row["target_score"]) / 100.0 for row in ranked_rows]
    ideal_rows = sorted(query_rows, key=lambda item: float(item["target_score"]), reverse=True)[:k]
    ideal_relevances = [float(row["target_score"]) / 100.0 for row in ideal_rows]
    ideal_dcg = _dcg(ideal_relevances)
    if ideal_dcg <= 0:
        return 0.0
    return _dcg(actual_relevances) / ideal_dcg


def _top_3_hit_rate(query_rows: list[dict[str, Any]]) -> float:
    predicted_top = sorted(query_rows, key=lambda item: float(item["predicted_score"]), reverse=True)[:3]
    actual_top = sorted(query_rows, key=lambda item: int(item["rank"]))[:3]
    predicted_urls = {str(row["url"]) for row in predicted_top}
    actual_urls = {str(row["url"]) for row in actual_top}
    return 1.0 if predicted_urls & actual_urls else 0.0


def ranking_metrics(validation_rows: list[dict[str, str]], predictions: list[float]) -> dict[str, float]:
    grouped_rows: dict[str, list[dict[str, Any]]] = {}
    for row, prediction in zip(validation_rows, predictions, strict=False):
        enriched_row: dict[str, Any] = dict(row)
        enriched_row["predicted_score"] = float(prediction)
        grouped_rows.setdefault(str(row.get("query") or ""), []).append(enriched_row)

    spearman_values: list[float] = []
    ndcg_values: list[float] = []
    top_3_values: list[float] = []

    for query_rows in grouped_rows.values():
        if len(query_rows) >= 2:
            actual = [float(row["target_score"]) for row in query_rows]
            predicted = [float(row["predicted_score"]) for row in query_rows]
            if len(set(actual)) > 1 and len(set(predicted)) > 1:
                correlation = spearmanr(actual, predicted).correlation
                if correlation is not None and correlation == correlation:
                    spearman_values.append(float(correlation))
        ndcg_values.append(float(_ndcg_at_k(query_rows, k=10)))
        top_3_values.append(float(_top_3_hit_rate(query_rows)))

    return {
        "spearman_mean": round(sum(spearman_values) / len(spearman_values), 6) if spearman_values else 0.0,
        "ndcg_at_10": round(sum(ndcg_values) / len(ndcg_values), 6) if ndcg_values else 0.0,
        "top_3_hit_rate": round(sum(top_3_values) / len(top_3_values), 6) if top_3_values else 0.0,
        "validation_queries": float(len(grouped_rows)),
    }


def evaluate_model_rows(model: Any, validation_rows: list[dict[str, str]]) -> dict[str, float]:
    x_validation, y_validation = rows_to_matrix(validation_rows)
    predictions = [float(value) for value in model.predict(x_validation)]
    metrics = {
        "rmse": round(_rmse(y_validation, predictions), 6),
        "mae": round(float(mean_absolute_error(y_validation, predictions)), 6),
    }
    metrics.update(ranking_metrics(validation_rows, predictions))
    return metrics


def _train_random_forest(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    random_state: int,
) -> tuple[Any, dict[str, float]]:
    x_train, y_train = rows_to_matrix(train_rows)
    model = RandomForestRegressor(
        n_estimators=400,
        max_depth=14,
        min_samples_split=3,
        min_samples_leaf=1,
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    return model, evaluate_model_rows(model, validation_rows)


def _train_catboost(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    random_state: int,
) -> tuple[Any | None, dict[str, float], str | None]:
    try:
        from catboost import CatBoostError, CatBoostRegressor
    except ImportError:
        return None, {}, "catboost_not_installed"

    x_train, y_train = rows_to_matrix(train_rows)
    model = CatBoostRegressor(
        loss_function="RMSE",
        depth=6,
        learning_rate=0.05,
        iterations=500,
        random_seed=random_state,
        verbose=False,
    )
    try:
        model.fit(x_train, y_train)
    except CatBoostError as error:
        return None, {}, f"catboost_training_failed: {error}"
    return model, evaluate_model_rows(model, validation_rows), None


def should_benchmark_catboost(metrics: dict[str, float]) -> bool:
    return float(metrics.get("mae", 0.0)) > 12.0 or float(metrics.get("spearman_mean", 0.0)) < 0.45


def candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, float, float, float]:
    metrics = candidate["metrics"]
    return (
        float(metrics.get("spearman_mean", 0.0)),
        float(metrics.get("ndcg_at_10", 0.0)),
        float(metrics.get("top_3_hit_rate", 0.0)),
        -float(metrics.get("mae", 0.0)),
    )


def train_candidate_models(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    random_state: int,
) -> tuple[list[dict[str, Any]], dict[str, object]]:
    candidates: list[dict[str, Any]] = []
    rf_model, rf_metrics = _train_random_forest(train_rows, validation_rows, random_state=random_state)
    candidates.append({"model": rf_model, "model_type": "RandomForestRegressor", "metrics": rf_metrics})

    benchmark: dict[str, object] = {"enabled": False}
    if should_benchmark_catboost(rf_metrics):
        benchmark["enabled"] = True
        catboost_model, catboost_metrics, catboost_error = _train_catboost(
            train_rows,
            validation_rows,
            random_state=random_state,
        )
        if catboost_model is not None:
            candidates.append(
                {
                    "model": catboost_model,
                    "model_type": "CatBoostRegressor",
                    "metrics": catboost_metrics,
                }
            )
            benchmark["catboost_metrics"] = catboost_metrics
        else:
            benchmark["catboost_error"] = catboost_error
    return candidates, benchmark


def select_best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return max(candidates, key=candidate_sort_key)


def train_quality_model(
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
    dataset_version: str | None = None,
    artifact_metadata: dict[str, Any] | None = None,
    split_output_path: str | Path | None = None,
) -> dict[str, object]:
    _x, _y, rows = prepare_training_data(dataset_path)
    if len(rows) < 4:
        raise ValueError("At least 4 dataset rows are required for training")

    train_rows, validation_rows, split_metadata = split_dataset_rows(rows, test_size=test_size, random_state=random_state)
    if not train_rows or not validation_rows:
        raise ValueError("Training split produced an empty train or validation set")

    candidates, benchmark = train_candidate_models(
        train_rows,
        validation_rows,
        random_state=random_state,
    )

    best_candidate = select_best_candidate(candidates)
    rows_count = len(rows)
    queries_count = len({str(row.get("query") or "") for row in rows})
    domains_count = len({str(row.get("domain") or "") for row in rows})
    resolved_dataset_version = dataset_version or infer_dataset_version(dataset_path, rows=rows)

    split_manifest: dict[str, object] | None = None
    if split_output_path is not None:
        split_manifest = save_dataset_split_manifest(
            train_rows,
            validation_rows,
            dataset_path=dataset_path,
            dataset_version=resolved_dataset_version,
            test_size=test_size,
            random_state=random_state,
            split_metadata=split_metadata,
            output_path=split_output_path,
        )

    model_metadata = {
        "model_type": best_candidate["model_type"],
        "rows_count": rows_count,
        "queries_count": queries_count,
        "domains_count": domains_count,
        "source": "local_dataset",
        "dataset_version": resolved_dataset_version,
        "artifact_version": resolved_dataset_version,
        **(artifact_metadata or {}),
    }
    metrics = {
        **best_candidate["metrics"],
        "train_rows": float(len(train_rows)),
        "validation_rows": float(len(validation_rows)),
        **split_metadata,
    }

    saved_model_path = save_model(
        model=best_candidate["model"],
        metrics=metrics,
        model_path=model_path,
        metadata=model_metadata,
    )
    clear_model_cache()

    return {
        "dataset_path": str(Path(dataset_path)),
        "model_path": str(saved_model_path),
        "rows_count": rows_count,
        "queries_count": queries_count,
        "domains_count": domains_count,
        "model_type": best_candidate["model_type"],
        "metrics": metrics,
        "benchmark": benchmark,
        "dataset_version": resolved_dataset_version,
        "artifact_version": str(model_metadata["artifact_version"]),
        "split": split_manifest,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--model-output", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--dataset-version", default="")
    parser.add_argument("--split-output", default="")
    args = parser.parse_args()

    result = train_quality_model(
        dataset_path=args.dataset,
        model_path=args.model_output,
        test_size=args.test_size,
        random_state=args.random_state,
        dataset_version=args.dataset_version or None,
        split_output_path=args.split_output or None,
    )
    print(result)


if __name__ == "__main__":
    main()

