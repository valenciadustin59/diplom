import csv
from pathlib import Path

from app.ml import FEATURE_COLUMNS
from app.ml.evaluate import evaluate_candidate_models
from app.ml.model import save_model, train_model


DATASET_FIELDS = [
    "query",
    "category",
    "intent",
    "city",
    "region_code",
    "url",
    "domain",
    "rank",
    "serp_page",
    "title",
    "snippet",
    "page_type",
    "fetch_status",
    "fetch_error",
    "target_score",
] + FEATURE_COLUMNS


def _write_dataset(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DATASET_FIELDS)
        writer.writeheader()
        for query_index, query in enumerate(("seo audit", "ppc agency", "legal services", "design studio"), start=1):
            for rank in range(1, 5):
                row = {
                    "query": query,
                    "category": "services",
                    "intent": "commercial",
                    "city": "moscow",
                    "region_code": 213,
                    "url": f"https://example{query_index}.com/page-{rank}",
                    "domain": f"example{query_index}.com",
                    "rank": rank,
                    "serp_page": 0,
                    "title": f"Title {rank}",
                    "snippet": f"Snippet {rank}",
                    "page_type": "content",
                    "fetch_status": "ok",
                    "fetch_error": "",
                    "target_score": round(((4 - rank) / 3) * 100.0, 4),
                }
                for index, feature_name in enumerate(FEATURE_COLUMNS, start=1):
                    row[feature_name] = float(index * (query_index + rank))
                writer.writerow(row)


def test_evaluate_candidate_models_returns_candidate_and_reference_metrics(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    model_path = tmp_path / "reference.pkl"
    _write_dataset(dataset_path)
    save_model(
        model=train_model(n_samples=50, seed=7),
        metrics={"rmse": 10.0},
        model_path=model_path,
        metadata={
            "source": "local_dataset",
            "dataset_version": "reference-v1",
            "rows_count": 16,
            "queries_count": 4,
            "domains_count": 4,
        },
    )

    result = evaluate_candidate_models(
        dataset_path=dataset_path,
        reference_model_path=model_path,
        test_size=0.25,
        random_state=42,
    )

    assert result["rows_count"] == 16
    assert result["queries_count"] == 4
    assert result["domains_count"] == 4
    assert result["train_rows"] > 0
    assert result["validation_rows"] > 0
    assert result["split"]["split_mode"] == "group_by_query"
    assert result["best_candidate"]["model_type"] in {"RandomForestRegressor", "CatBoostRegressor"}
    assert result["best_candidate"]["model_schema_version"] == "v2"
    assert result["best_candidate"]["feature_count"] > len(FEATURE_COLUMNS)
    assert "ndcg_at_10" in result["best_candidate"]["metrics"]
    assert "top_3_hit_rate" in result["best_candidate"]["metrics"]
    assert result["reference_model"] is not None
    assert result["reference_model"]["model_info"]["dataset_version"] == "reference-v1"
    assert result["reference_model"]["model_info"]["model_schema_version"] == "v1"
    assert result["reference_model"]["metrics"]["split_mode"] == "group_by_query"


def test_evaluate_candidate_models_without_reference_model(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    _write_dataset(dataset_path)

    result = evaluate_candidate_models(
        dataset_path=dataset_path,
        reference_model_path=None,
        test_size=0.25,
        random_state=42,
    )

    assert result["reference_model"] is None
    assert len(result["candidates"]) >= 1
