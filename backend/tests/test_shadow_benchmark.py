import csv
import json
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor

from app.ml.dataset_builder import DATASET_COLUMNS
from app.ml.model import save_model
from app.ml.model_schema import get_model_feature_schema
from app.ml.shadow_benchmark import build_candidate_guardrails, run_shadow_benchmark
from app.ml.train import rows_to_matrix


V2_FEATURE_COLUMNS = get_model_feature_schema("v2").feature_columns
V1_FEATURE_COLUMNS = get_model_feature_schema("v1").feature_columns


def _write_shadow_dataset(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
        for query_index, query in enumerate(("query one", "query two", "query three", "query four"), start=1):
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
                    row[feature_name] = float((feature_index + 1) * (query_index + (4 - rank)))
                writer.writerow(row)


def _save_fitted_model(dataset_path: Path, model_path: Path, *, feature_columns, metadata: dict[str, object]) -> None:
    with dataset_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    x, y = rows_to_matrix(rows, feature_columns=feature_columns)
    model = RandomForestRegressor(n_estimators=8, random_state=13)
    model.fit(x, y)
    save_model(
        model=model,
        metrics={"rmse": 1.0},
        model_path=model_path,
        metadata={
            "source": "local_dataset",
            "dataset_version": "dataset-v2-test",
            "model_schema_version": "v2" if len(feature_columns) == len(V2_FEATURE_COLUMNS) else "v1",
            "feature_columns": list(feature_columns),
            **metadata,
        },
    )


def test_build_candidate_guardrails_rejects_top3_and_ranking_mae_regressions():
    candidate = {
        "status": "available",
        "candidate_family": "ranking",
        "metrics": {
            "rmse": 74.0,
            "mae": 72.0,
            "spearman_mean": 0.38,
            "ndcg_at_10": 0.94,
            "top_3_hit_rate": 0.8,
        },
        "feature_importance_summary": {"available": True, "top_features": [{"feature": "word_count"}]},
        "runtime_explanation_guardrail": {"passed": True},
    }
    reference = {
        "metrics": {
            "rmse": 28.0,
            "mae": 24.0,
            "spearman_mean": 0.15,
            "ndcg_at_10": 0.91,
            "top_3_hit_rate": 0.95,
        }
    }

    guardrails = build_candidate_guardrails(candidate, reference)

    assert guardrails["publish_gate_passed"] is False
    assert "top_3_hit_rate_regressed" in guardrails["rejection_reasons"]
    assert "mae_not_comparable" in guardrails["rejection_reasons"]
    assert "ranking_family_absolute_error_not_viable" in guardrails["rejection_reasons"]


def test_run_shadow_benchmark_writes_guardrail_report(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    reference_model_path = tmp_path / "reference.pkl"
    candidate_model_path = tmp_path / "candidate.pkl"
    output_dir = tmp_path / "shadow-report"
    _write_shadow_dataset(dataset_path)
    _save_fitted_model(
        dataset_path,
        reference_model_path,
        feature_columns=V1_FEATURE_COLUMNS,
        metadata={"artifact_version": "reference-v1"},
    )
    _save_fitted_model(
        dataset_path,
        candidate_model_path,
        feature_columns=V2_FEATURE_COLUMNS,
        metadata={
            "artifact_version": "candidate-v2",
            "candidate_name": "pointwise_test_candidate",
            "candidate_family": "pointwise",
        },
    )

    report = run_shadow_benchmark(
        dataset_path=dataset_path,
        reference_model_path=reference_model_path,
        candidate_model_paths=[candidate_model_path],
        output_dir=output_dir,
        smoke_queries=["query one"],
        test_size=0.25,
        random_state=7,
    )

    assert report["dataset_version"] == "dataset-v2-test"
    assert report["reference_model"]["status"] == "available"
    assert report["candidates"][0]["candidate_name"] == "pointwise_test_candidate"
    assert report["candidate_comparisons"][0]["guardrails"]["checks"]["candidate_available"] is True
    assert report["smoke_explainability"]["covered_queries_count"] == 1
    assert report["smoke_explainability"]["model_guardrails"]["pointwise_test_candidate"]["passed"] is True
    assert Path(report["report_paths"]["json_path"]).exists()
    assert Path(report["report_paths"]["markdown_path"]).exists()

    saved_report = json.loads(Path(report["report_paths"]["json_path"]).read_text(encoding="utf-8"))
    assert saved_report["decision"]["publish_recommendation"] in {"publish_candidate", "keep_reference"}
