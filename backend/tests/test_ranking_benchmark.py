import csv
import json
from pathlib import Path
import pytest
from app.ml.dataset_builder import DATASET_COLUMNS
from app.ml.candidate_artifacts import train_candidate_artifacts
from app.ml.model import load_saved_model, save_model, train_model
from app.ml.model_schema import get_model_feature_schema
from app.ml.ranking_benchmark import publish_best_ranking_model, run_ranking_benchmark
from app.ml.train import rows_to_matrix
V2_FEATURE_COLUMNS = get_model_feature_schema("v2").feature_columns
def _write_dataset(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
        query_specs = (
            ("╤А╨╡╨╝╨╛╨╜╤В ╨║╨▓╨░╤А╤В╨╕╤А ╨╝╨╛╤Б╨║╨▓╨░", "commercial"),
            ("╨┐╨╗╨░╤Б╤В╨╕╨║╨╛╨▓╤Л╨╡ ╨╛╨║╨╜╨░ ╨╝╨╛╤Б╨║╨▓╨░", "commercial"),
            ("╨║╨░╨║ ╨▓╤Л╨▒╤А╨░╤В╤М ╨┐╨╗╨░╤Б╤В╨╕╨║╨╛╨▓╤Л╨╡ ╨╛╨║╨╜╨░", "informational"),
            ("seo ╨░╤Г╨┤╨╕╤В ╤Б╨░╨╣╤В╨░", "informational"),
        )
        for query_index, (query, intent) in enumerate(query_specs, start=1):
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
                        "category": "services",
                        "intent": intent,
                        "city": "╨╝╨╛╤Б╨║╨▓╨░",
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
                        "page_indexable": 1,
                        "technical_seo_score": 0.85,
                    }
                )
                for feature_index, feature_name in enumerate(V2_FEATURE_COLUMNS, start=1):
                    row[feature_name] = float((feature_index + 1) * (query_index * 2 + (4 - rank)))
                writer.writerow(row)
def _write_ready_manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-24T10:00:00+00:00",
                "dataset": {
                    "version": "dataset-v2-test",
                    "baseline_version": "baseline-v1",
                    "feature_schema_versions": ["v2"],
                    "extraction_artifact_versions": ["extraction-v2"],
                    "label_schema_versions": ["hybrid-v1"],
                },
                "labeling": {
                    "label_source_distribution": {"weak_serp": 12},
                    "expert_rows_count": 0,
                    "hybrid_rows_count": 0,
                },
                "artifacts": {"artifact_coverage_ratio": 1.0},
                "coverage": {
                    "rows_count": 12,
                    "unique_queries": 4,
                    "unique_domains": 4,
                    "unique_categories": 1,
                    "unique_cities": 1,
                    "failure_rate": 0.0,
                    "query_coverage_ratio": 1.0,
                    "attempted_query_coverage_ratio": 1.0,
                },
                "split": {"split_mode": "group_by_query"},
                "quality_gates": {"ready_for_training": True, "unmet_requirements": []},
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
def _write_reference_model(path: Path) -> None:
    save_model(
        model=train_model(n_samples=60, seed=7),
        metrics={"rmse": 10.0, "ndcg_at_10": 0.7, "top_3_hit_rate": 0.75, "spearman_mean": 0.3},
        model_path=path,
        metadata={
            "source": "local_dataset",
            "dataset_version": "baseline-v1",
            "artifact_version": "baseline-v1-artifact",
        },
    )


def _write_v2_candidate_model(dataset_path: Path, model_path: Path) -> None:
    from sklearn.ensemble import RandomForestRegressor

    with dataset_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    x, y = rows_to_matrix(rows, feature_columns=V2_FEATURE_COLUMNS)
    model = RandomForestRegressor(n_estimators=8, random_state=13)
    model.fit(x, y)
    save_model(
        model=model,
        metrics={"rmse": 5.0, "ndcg_at_10": 0.9, "top_3_hit_rate": 1.0, "spearman_mean": 0.8},
        model_path=model_path,
        metadata={
            "source": "local_dataset",
            "dataset_version": "dataset-v2-test",
            "artifact_version": "dataset-v2-test-candidate",
            "model_schema_version": "v2",
            "feature_columns": list(V2_FEATURE_COLUMNS),
        },
    )


def test_run_ranking_benchmark_builds_report_and_reference_comparison(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    reference_model_path = tmp_path / "reference.pkl"
    candidate_model_path = tmp_path / "candidate.pkl"
    report_dir = tmp_path / "reports"
    _write_dataset(dataset_path)
    _write_reference_model(reference_model_path)
    _write_v2_candidate_model(dataset_path, candidate_model_path)
    report = run_ranking_benchmark(
        dataset_path=dataset_path,
        reference_model_path=reference_model_path,
        candidate_model_path=candidate_model_path,
        test_size=0.25,
        random_state=7,
        output_dir=report_dir,
    )
    candidate_map = {candidate["candidate_name"]: candidate for candidate in report["candidates"]}
    assert report["dataset_version"] == "dataset-v2-test"
    assert report["model_schema_version"] == "v2"
    assert report["feature_count"] == len(V2_FEATURE_COLUMNS)
    assert report["reference_model"] is not None
    assert report["reference_model"]["model_info"]["model_schema_version"] == "v1"
    assert report["candidate_model"]["candidate_name"] == "candidate_artifact"
    assert report["candidate_model"]["model_path"] == str(candidate_model_path)
    assert report["candidate_model"]["model_info"]["dataset_version"] == "dataset-v2-test"
    assert candidate_map["candidate_artifact"]["status"] == "available"
    assert candidate_map["candidate_artifact"]["model_schema_version"] == "v2"
    assert candidate_map["catboost_ranker"]["status"] == "available"
    assert candidate_map["catboost_ranker"]["feature_importance_summary"]["available"] is True
    assert candidate_map["lightgbm_ranker"]["status"] == "unavailable"
    assert candidate_map["xgboost_rank_pairwise"]["status"] == "unavailable"
    assert report["best_candidate"]["candidate_name"] in candidate_map
    assert report["comparison_to_reference"] is not None
    assert report["comparison_to_reference"]["publish_recommendation"] in {"publish_candidate", "keep_reference"}
    assert report["candidate_model_comparison_to_reference"] is not None
    assert report["candidate_model_comparison_to_reference"]["best_candidate"] == "candidate_artifact"
    assert Path(report["report_paths"]["json_path"]).exists()
    assert Path(report["report_paths"]["markdown_path"]).exists()


def test_train_candidate_artifacts_saves_models_without_rewriting_reference(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    reference_model_path = tmp_path / "reference.pkl"
    rf_model_path = tmp_path / "rf-candidate.pkl"
    catboost_model_path = tmp_path / "catboost-candidate.pkl"
    ranking_model_path = tmp_path / "ranking-candidate.pkl"
    report_dir = tmp_path / "reports"
    _write_dataset(dataset_path)
    _write_reference_model(reference_model_path)
    reference_bytes = reference_model_path.read_bytes()

    report = train_candidate_artifacts(
        dataset_path=dataset_path,
        dataset_version="dataset-v2-test",
        rf_model_path=rf_model_path,
        catboost_model_path=catboost_model_path,
        ranking_model_path=ranking_model_path,
        reference_model_path=reference_model_path,
        output_dir=report_dir,
        test_size=0.25,
        random_state=7,
    )

    assert reference_model_path.read_bytes() == reference_bytes
    assert rf_model_path.exists()
    assert catboost_model_path.exists()
    assert ranking_model_path.exists()
    assert report["reference_model"]["sha1"]
    assert report["split"]["split_mode"] == "group_by_query"
    assert report["split"]["query_overlap_count"] == 0
    assert report["saved_artifacts"]["pointwise_random_forest"] == str(rf_model_path)
    assert report["saved_artifacts"]["pointwise_catboost"] == str(catboost_model_path)
    assert report["best_ranking_candidate"]["candidate_family"] == "ranking"
    assert report["best_ranking_candidate"]["model_path"] == str(ranking_model_path)
    assert Path(report["report_paths"]["json_path"]).exists()
    assert Path(report["report_paths"]["markdown_path"]).exists()

    rf_payload = load_saved_model(rf_model_path)
    ranking_payload = load_saved_model(ranking_model_path)
    assert rf_payload is not None
    assert ranking_payload is not None
    assert rf_payload["candidate_name"] == "pointwise_random_forest"
    assert ranking_payload["candidate_family"] == "ranking"
    assert ranking_payload["model_schema_version"] == "v2"


def test_train_candidate_artifacts_rejects_production_output_path(tmp_path):
    reference_model_path = tmp_path / "page_quality_model.pkl"
    with pytest.raises(ValueError, match="must not overwrite"):
        train_candidate_artifacts(
            dataset_path=tmp_path / "dataset.csv",
            rf_model_path=reference_model_path,
            catboost_model_path=tmp_path / "catboost-candidate.pkl",
            ranking_model_path=tmp_path / "ranking-candidate.pkl",
            reference_model_path=reference_model_path,
            output_dir=None,
        )


def test_publish_best_ranking_model_writes_artifact_metadata_and_report(monkeypatch, tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    manifest_path = tmp_path / "manifest.json"
    model_path = tmp_path / "page_quality_model.pkl"
    reference_model_path = tmp_path / "reference.pkl"
    report_dir = tmp_path / "reports"
    _write_dataset(dataset_path)
    _write_ready_manifest(manifest_path)
    _write_reference_model(reference_model_path)
    monkeypatch.setattr("app.ml.publish.VERSIONED_ARTIFACTS_DIR", tmp_path / "versions")
    result = publish_best_ranking_model(
        dataset_path=dataset_path,
        manifest_path=manifest_path,
        model_path=model_path,
        reference_model_path=reference_model_path,
        test_size=0.25,
        random_state=7,
        report_output_dir=report_dir,
        force_publish=True,
    )
    saved_payload = load_saved_model(model_path)
    assert saved_payload is not None
    assert saved_payload["model_schema_version"] == "v2"
    assert saved_payload["candidate_name"] == "catboost_ranker"
    assert Path(result["published_model_path"]).exists()
    assert Path(result["versioned_model_path"]).exists()
    assert Path(result["published_metadata_path"]).exists()
    assert Path(result["versioned_metadata_path"]).exists()
    assert Path(result["report_paths"]["json_path"]).exists()
    assert Path(result["report_paths"]["markdown_path"]).exists()
    published_metadata = json.loads(Path(result["published_metadata_path"]).read_text(encoding="utf-8"))
    assert published_metadata["candidate_name"] == "catboost_ranker"
    assert published_metadata["feature_importance_summary"]["available"] is True


def test_publish_best_ranking_model_rejects_non_ranking_candidate(monkeypatch, tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    manifest_path = tmp_path / "manifest.json"
    model_path = tmp_path / "page_quality_model.pkl"
    report_dir = tmp_path / "reports"
    _write_dataset(dataset_path)
    _write_ready_manifest(manifest_path)

    monkeypatch.setattr(
        "app.ml.ranking_benchmark._run_ranking_benchmark_internal",
        lambda **kwargs: {
            "best_candidate": {
                "candidate_name": "candidate_artifact",
                "candidate_family": "pointwise_candidate",
                "status": "available",
                "model": train_model(n_samples=12, seed=9),
                "metrics": {
                    "rmse": 1.0,
                    "mae": 1.0,
                    "spearman_mean": 1.0,
                    "ndcg_at_10": 1.0,
                    "top_3_hit_rate": 1.0,
                },
            },
            "reference_candidate": None,
            "report": {"comparison_to_reference": None},
            "report_paths": {},
        },
    )

    with pytest.raises(ValueError, match="only publishes newly trained ranking candidates"):
        publish_best_ranking_model(
            dataset_path=dataset_path,
            manifest_path=manifest_path,
            model_path=model_path,
            report_output_dir=report_dir,
            force_publish=True,
        )

    assert not model_path.exists()
