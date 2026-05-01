import csv
import json
from pathlib import Path

from app.ml import (
    FEATURE_COLUMNS,
    build_dataset,
    explain_score,
    load_saved_model,
    predict_score,
    train_quality_model,
)
from app.ml.dataset_builder import DATASET_COLUMNS
from app.ml.dataset_versions import build_dataset_bundle_paths, freeze_primary_dataset_as_baseline


def _feature_row(multiplier: float) -> dict[str, float]:
    return {
        feature_name: float((index + 1) * multiplier)
        for index, feature_name in enumerate(FEATURE_COLUMNS)
    }


def test_build_dataset_from_seed_csv_writes_dataset_failures_artifacts_and_hybrid_labels(monkeypatch, tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    failures_path = tmp_path / "failures.csv"
    checkpoint_path = tmp_path / "checkpoint.json"
    seeds_path = tmp_path / "seeds.csv"
    expert_labels_path = tmp_path / "expert_labels.csv"
    artifacts_dir = tmp_path / "artifacts"

    with seeds_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["query", "category", "intent", "city", "region_code", "top_n", "pages_to_scan"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query": "ремонт квартир москва",
                "category": "ремонт квартир",
                "intent": "commercial",
                "city": "москва",
                "region_code": 213,
                "top_n": 2,
                "pages_to_scan": 1,
            }
        )

    with expert_labels_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["query", "url", "expert_target_score", "label_source", "labeler"])
        writer.writeheader()
        writer.writerow(
            {
                "query": "ремонт квартир москва",
                "url": "https://example.com/page-1",
                "expert_target_score": 80,
                "label_source": "expert",
                "labeler": "qa",
            }
        )

    monkeypatch.setattr(
        "app.ml.dataset_builder.search_serp",
        lambda query, top_n, region_code=None, page=0: [
            {
                "url": "https://example.com/page-1",
                "title": "Page 1",
                "snippet": "Snippet 1",
                "rank": 1,
                "serp_page": page,
            },
            {
                "url": "https://example.com/page-2",
                "title": "Page 2",
                "snippet": "Snippet 2",
                "rank": 2,
                "serp_page": page,
            },
        ],
    )

    def fake_fetch(url: str, use_browser: bool = True):
        if url.endswith("page-2"):
            return {
                "status": "failed",
                "fetch_method": "http",
                "fetch_error_code": "unknown_fetch_error",
                "fetch_error_message": "boom",
                "final_url": url,
                "http_status": None,
                "html": None,
                "text": None,
            }
        return {
            "status": "success",
            "fetch_method": "http",
            "fetch_error_code": None,
            "fetch_error_message": None,
            "final_url": url,
            "http_status": 200,
            "html": "<html><head><title>Example</title></head><body><h1>Header</h1><p>Body</p></body></html>",
            "text": "Header Body",
        }

    monkeypatch.setattr("app.ml.dataset_builder.fetch_page", fake_fetch)
    monkeypatch.setattr("app.ml.dataset_builder.build_features", lambda html, text, query: _feature_row(1.0))

    result = build_dataset(
        seeds_file=seeds_path,
        output_path=dataset_path,
        failures_path=failures_path,
        checkpoint_path=checkpoint_path,
        artifacts_dir=artifacts_dir,
        expert_labels_path=expert_labels_path,
        dataset_version="dataset-v2-test",
        overwrite=True,
        max_workers=2,
        query_delay_seconds=0.0,
    )

    assert result["rows_count"] == 1
    assert result["failures_count"] == 1
    assert Path(result["metadata_path"]).exists()
    assert dataset_path.exists()
    assert failures_path.exists()
    assert checkpoint_path.exists()

    with dataset_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    with failures_path.open("r", encoding="utf-8", newline="") as file:
        failures = list(csv.DictReader(file))

    assert len(rows) == 1
    assert rows[0]["dataset_version"] == "dataset-v2-test"
    assert rows[0]["query"] == "ремонт квартир москва"
    assert rows[0]["category"] == "ремонт квартир"
    assert rows[0]["rank"] == "1"
    assert rows[0]["title"] == "Page 1"
    assert rows[0]["fetch_status"] == "ok"
    assert rows[0]["page_type"] == "content"
    assert rows[0]["label_source"] == "hybrid"
    assert rows[0]["weak_target_score"] == "100.0"
    assert rows[0]["expert_target_score"] == "80.0"
    assert rows[0]["target_score"] == "86.0"
    assert rows[0]["artifact_path"]
    assert (dataset_path.parent / rows[0]["artifact_path"]).exists()
    assert "phone_present" in rows[0]
    assert "commercial_signals_score" in rows[0]
    assert rows[0]["phone_present"] == "0.0"

    assert len(failures) == 1
    assert failures[0]["url"] == "https://example.com/page-2"
    assert failures[0]["fetch_status"] == "failed"
    assert failures[0]["dataset_version"] == "dataset-v2-test"

    second_run = build_dataset(
        seeds_file=seeds_path,
        output_path=dataset_path,
        failures_path=failures_path,
        checkpoint_path=checkpoint_path,
        artifacts_dir=artifacts_dir,
        expert_labels_path=expert_labels_path,
        dataset_version="dataset-v2-test",
        overwrite=False,
        max_workers=2,
        query_delay_seconds=0.0,
    )
    assert second_run["processed_seed_pages"] == 0

    with dataset_path.open("r", encoding="utf-8", newline="") as file:
        rows_after_resume = list(csv.DictReader(file))
    assert len(rows_after_resume) == 1


def test_build_dataset_deduplicates_search_results_before_parallel_fetch(monkeypatch, tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    failures_path = tmp_path / "failures.csv"
    checkpoint_path = tmp_path / "checkpoint.json"
    seeds_path = tmp_path / "seeds.csv"

    with seeds_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["query", "category", "intent", "city", "region_code", "top_n", "pages_to_scan"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "query": "ремонт квартир москва",
                "category": "ремонт квартир",
                "intent": "commercial",
                "city": "москва",
                "region_code": 213,
                "top_n": 3,
                "pages_to_scan": 1,
            }
        )

    monkeypatch.setattr(
        "app.ml.dataset_builder.search_serp",
        lambda query, top_n, region_code=None, page=0: [
            {
                "url": "https://example.com/page-1",
                "title": "Page 1",
                "snippet": "Snippet 1",
                "rank": 1,
                "serp_page": page,
            },
            {
                "url": "https://example.com/page-1",
                "title": "Page 1 duplicate",
                "snippet": "Snippet duplicate",
                "rank": 2,
                "serp_page": page,
            },
            {
                "url": "https://example.com/page-2",
                "title": "Page 2",
                "snippet": "Snippet 2",
                "rank": 3,
                "serp_page": page,
            },
        ],
    )
    monkeypatch.setattr(
        "app.ml.dataset_builder.fetch_page",
        lambda url, use_browser=True: {
            "status": "success",
            "fetch_method": "http",
            "fetch_error_code": None,
            "fetch_error_message": None,
            "final_url": url,
            "http_status": 200,
            "html": "<html><head><title>Example</title></head><body><h1>Header</h1><p>Body</p></body></html>",
            "text": "Header Body",
        },
    )
    monkeypatch.setattr("app.ml.dataset_builder.build_features", lambda html, text, query: _feature_row(1.0))

    result = build_dataset(
        seeds_file=seeds_path,
        output_path=dataset_path,
        failures_path=failures_path,
        checkpoint_path=checkpoint_path,
        dataset_version="dataset-v2-test",
        overwrite=True,
        max_workers=2,
        query_delay_seconds=0.0,
    )

    with dataset_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

    assert result["rows_count"] == 2
    assert [row["url"] for row in rows] == ["https://example.com/page-1", "https://example.com/page-2"]
    assert len(checkpoint["written_keys"]) == 2


def test_freeze_primary_dataset_as_baseline_copies_bundle(monkeypatch, tmp_path):
    dataset_path = tmp_path / "ru_commercial_dataset.csv"
    failures_path = tmp_path / "ru_commercial_dataset_failures.csv"
    manifest_path = tmp_path / "ru_commercial_dataset.manifest.json"
    checkpoint_path = tmp_path / "ru_commercial_dataset.checkpoint.json"
    seeds_path = tmp_path / "training_query_seeds.csv"
    dataset_versions_dir = tmp_path / "dataset_versions"

    dataset_path.write_text("query,target_score\nq,100\n", encoding="utf-8")
    failures_path.write_text("query,fetch_error\nq,boom\n", encoding="utf-8")
    manifest_path.write_text(json.dumps({"quality_gates": {"ready_for_training": True}}), encoding="utf-8")
    checkpoint_path.write_text(json.dumps({"completed_pages": [], "written_keys": []}), encoding="utf-8")
    seeds_path.write_text("query\nq\n", encoding="utf-8")

    monkeypatch.setattr("app.ml.dataset_versions.DATASET_VERSIONS_DIR", dataset_versions_dir)

    result = freeze_primary_dataset_as_baseline(
        dataset_path=dataset_path,
        failures_path=failures_path,
        manifest_path=manifest_path,
        checkpoint_path=checkpoint_path,
        seeds_path=seeds_path,
    )

    bundle = build_dataset_bundle_paths("baseline-v1")
    assert result["frozen"] is True
    assert bundle.dataset_path.exists()
    assert bundle.failures_path.exists()
    assert bundle.manifest_path.exists()
    assert bundle.checkpoint_path.exists()
    assert bundle.seeds_path.exists()
    assert Path(result["metadata_path"]).exists()


def test_train_quality_model_saves_model_and_exposes_model_info_with_split_manifest(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    model_path = tmp_path / "model.pkl"
    split_path = tmp_path / "split.json"

    with dataset_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
        queries = ["ремонт квартир москва", "пластиковые окна москва", "seo продвижение москва"]
        for query_index, query in enumerate(queries, start=1):
            for rank in range(1, 4):
                row = {column: "" for column in DATASET_COLUMNS}
                row.update(
                    {
                        "dataset_version": "dataset-v2-test",
                        "feature_schema_version": "v2",
                        "extraction_artifact_version": "extraction-v2",
                        "label_schema_version": "hybrid-v1",
                        "label_source": "weak_serp",
                        "weak_target_score": round(((3 - rank) / 2) * 100.0, 4),
                        "expert_target_score": "",
                        "query": query,
                        "category": "category",
                        "intent": "commercial",
                        "city": "москва",
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
                        "target_score": round(((3 - rank) / 2) * 100.0, 4),
                        "phone_present": 1,
                        "address_present": 1,
                        "price_present": 1,
                        "commercial_signals_score": 0.8,
                        "trust_signals_score": 0.7,
                        "commercial_trust_score": 0.75,
                    }
                )
                for index, feature_name in enumerate(FEATURE_COLUMNS, start=1):
                    row[feature_name] = float(index * (query_index * 2 + rank))
                writer.writerow(row)

    result = train_quality_model(
        dataset_path=dataset_path,
        model_path=model_path,
        test_size=0.34,
        split_output_path=split_path,
    )

    assert model_path.exists()
    assert split_path.exists()
    assert result["rows_count"] == 9
    assert result["queries_count"] == 3
    assert result["domains_count"] == 3
    assert result["metrics"]["split_mode"] == "group_by_query"
    assert "rmse" in result["metrics"]
    assert "mae" in result["metrics"]
    assert "spearman_mean" in result["metrics"]
    assert "ndcg_at_10" in result["metrics"]
    assert "top_3_hit_rate" in result["metrics"]
    assert result["dataset_version"] == "dataset-v2-test"
    assert result["split"]["split_mode"] == "group_by_query"
    assert result["split"]["split_path"] == str(split_path)

    saved_model = load_saved_model(model_path)
    assert saved_model is not None
    assert saved_model["source"] == "local_dataset"
    assert saved_model["model_type"] in {"RandomForestRegressor", "CatBoostRegressor"}
    assert saved_model["dataset_version"] == "dataset-v2-test"

    features = {feature_name: float(index * 2) for index, feature_name in enumerate(FEATURE_COLUMNS, start=1)}
    score = predict_score(features, model_path=model_path)
    explanation = explain_score(features, model_path=model_path)

    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0
    assert explanation["model_info"]["source"] == "local_dataset"
    assert explanation["model_info"]["dataset_rows"] == 9


def test_predict_score_falls_back_to_bootstrap_model(tmp_path):
    missing_model_path = tmp_path / "missing.pkl"
    features = {feature_name: float(index + 1) for index, feature_name in enumerate(FEATURE_COLUMNS)}

    score = predict_score(features, model_path=missing_model_path)
    explanation = explain_score(features, model_path=missing_model_path)

    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0
    assert explanation["model_info"]["source"] == "bootstrap"


def test_train_quality_model_accepts_dataset_with_auxiliary_snapshot_columns(tmp_path):
    dataset_path = tmp_path / "dataset-with-auxiliary-columns.csv"
    model_path = tmp_path / "model-with-auxiliary-columns.pkl"

    with dataset_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
        for query_index, query in enumerate(["ремонт квартир москва", "пластиковые окна москва"], start=1):
            for rank in range(1, 4):
                row = {column: "" for column in DATASET_COLUMNS}
                row.update(
                    {
                        "dataset_version": "dataset-v2-aux",
                        "feature_schema_version": "v2",
                        "extraction_artifact_version": "extraction-v2",
                        "label_schema_version": "hybrid-v1",
                        "label_source": "weak_serp",
                        "weak_target_score": round(((3 - rank) / 2) * 100.0, 4),
                        "expert_target_score": "",
                        "query": query,
                        "category": "category",
                        "intent": "commercial",
                        "city": "москва",
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
                        "target_score": round(((3 - rank) / 2) * 100.0, 4),
                        "phone_present": 1,
                        "address_present": 1,
                        "price_present": 1,
                        "commercial_signals_score": 0.8,
                        "trust_signals_score": 0.7,
                        "commercial_trust_score": 0.75,
                    }
                )
                for index, feature_name in enumerate(FEATURE_COLUMNS, start=1):
                    row[feature_name] = float(index * (query_index * 2 + rank))
                writer.writerow(row)

    result = train_quality_model(dataset_path=dataset_path, model_path=model_path, test_size=0.34)
    explanation = explain_score(
        {feature_name: float(index * 2) for index, feature_name in enumerate(FEATURE_COLUMNS, start=1)},
        model_path=model_path,
    )

    assert model_path.exists()
    assert result["rows_count"] == 6
    assert result["queries_count"] == 2
    assert result["dataset_version"] == "dataset-v2-aux"
    assert explanation["model_info"]["source"] == "local_dataset"
import csv
from pathlib import Path

import pytest

from app.ml import FEATURE_COLUMNS, load_saved_model, train_quality_model


def _write_small_constant_dataset(path: Path) -> None:
    fieldnames = [
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
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for query_index, query in enumerate(("q1", "q2"), start=1):
            for rank in range(1, 3):
                row = {
                    "query": query,
                    "category": "category",
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
                    "target_score": round(((2 - rank) / 1) * 100.0, 4),
                }
                for feature_name in FEATURE_COLUMNS:
                    row[feature_name] = 1.0
                writer.writerow(row)


def test_train_quality_model_survives_catboost_benchmark_failure(tmp_path):
    dataset_path = tmp_path / "constant-dataset.csv"
    model_path = tmp_path / "constant-model.pkl"
    _write_small_constant_dataset(dataset_path)

    result = train_quality_model(dataset_path=dataset_path, model_path=model_path, test_size=0.5, random_state=7)

    assert model_path.exists()
    assert load_saved_model(model_path) is not None
    assert result["model_type"] == "RandomForestRegressor"
    benchmark = result["benchmark"]
    if benchmark.get("enabled"):
        assert "catboost_error" in benchmark
        assert str(benchmark["catboost_error"]).startswith("catboost_training_failed:")
