from __future__ import annotations

import csv
import json
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor

from app.features import SERP_RELATIVE_FEATURE_COLUMNS
from app.ml.model import load_saved_model, save_model
from app.ml.model_schema import MODEL_SCHEMA_VERSION_V3, get_model_feature_schema
from app.ml.second_pass import (
    SECOND_PASS_MODEL_SCHEMA_VERSION,
    build_second_pass_score_result,
    get_second_pass_feature_columns,
)
from app.ml.second_pass_experiment import (
    enrich_rows_with_serp_relative_features,
    run_second_pass_experiment,
)
from app.ml.train import rows_to_matrix


V3_FEATURE_COLUMNS = get_model_feature_schema(MODEL_SCHEMA_VERSION_V3).feature_columns
SECOND_PASS_FEATURE_COLUMNS = get_second_pass_feature_columns(MODEL_SCHEMA_VERSION_V3)


def _write_second_pass_dataset(path: Path) -> list[dict[str, str]]:
    fieldnames = [
        "dataset_version",
        "query",
        "url",
        "domain",
        "rank",
        "target_score",
        "fetch_status",
        *V3_FEATURE_COLUMNS,
    ]
    rows: list[dict[str, str]] = []
    query_specs = ("repair moscow", "windows kazan", "seo audit", "delivery flowers")
    for query_index, query in enumerate(query_specs, start=1):
        for rank in range(1, 5):
            target_score = float((4 - rank) * 30 + query_index)
            row = {
                "dataset_version": "dataset-v3-d44-test",
                "query": query,
                "url": f"https://example{query_index}.test/page-{rank}",
                "domain": f"example{query_index}.test",
                "rank": str(rank),
                "target_score": str(target_score),
                "fetch_status": "ok",
            }
            for feature_index, feature_name in enumerate(V3_FEATURE_COLUMNS, start=1):
                row[feature_name] = str(float((feature_index % 7) + target_score / 100.0 + (4 - rank) * 0.15))
            row["semantic_similarity"] = str(0.9 - rank * 0.08)
            row["technical_seo_score"] = str(0.85 - rank * 0.04)
            row["commercial_trust_score"] = str(0.8 - rank * 0.05)
            row["intent_alignment_score"] = str(0.82 - rank * 0.04)
            row["word_count"] = str(900 - rank * 80)
            rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def _write_reference_model(dataset_path: Path, model_path: Path) -> None:
    with dataset_path.open("r", encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    x_rows, y_rows = rows_to_matrix(rows, feature_columns=V3_FEATURE_COLUMNS)
    model = RandomForestRegressor(n_estimators=24, random_state=11)
    model.fit(x_rows, y_rows)
    save_model(
        model=model,
        metrics={"mae": 3.0, "ndcg_at_10": 0.9, "top_3_hit_rate": 1.0, "spearman_mean": 0.8},
        model_path=model_path,
        metadata={
            "source": "local_dataset",
            "dataset_version": "dataset-v3-d44-test",
            "artifact_version": "dataset-v3-d44-test-reference",
            "model_schema_version": MODEL_SCHEMA_VERSION_V3,
            "feature_columns": list(V3_FEATURE_COLUMNS),
        },
    )


def test_enrich_rows_with_serp_relative_features_uses_query_local_competitor_context(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    rows = _write_second_pass_dataset(dataset_path)

    enriched_rows, summary = enrich_rows_with_serp_relative_features(
        rows,
        primary_feature_columns=V3_FEATURE_COLUMNS,
    )

    assert len(enriched_rows) == len(rows)
    assert summary["rows_with_min_context"] == len(rows)
    assert summary["min_context_count"] == 3
    assert set(SERP_RELATIVE_FEATURE_COLUMNS).issubset(enriched_rows[0].keys())
    assert float(enriched_rows[0]["serp_relative_context_available"]) == 1.0
    assert "target_score" not in SECOND_PASS_FEATURE_COLUMNS


def test_second_pass_score_contract_skips_weak_context_and_reports_candidate(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    reference_model_path = tmp_path / "reference.pkl"
    candidate_model_path = tmp_path / "second-pass-experiment.pkl"
    report_dir = tmp_path / "reports"
    _write_second_pass_dataset(dataset_path)
    _write_reference_model(dataset_path, reference_model_path)

    report = run_second_pass_experiment(
        dataset_path=dataset_path,
        reference_model_path=reference_model_path,
        candidate_model_path=candidate_model_path,
        output_dir=report_dir,
        test_size=0.25,
        random_state=7,
        force_catboost=False,
    )
    saved_candidate = load_saved_model(candidate_model_path)
    metadata = json.loads(candidate_model_path.with_suffix(".metadata.json").read_text(encoding="utf-8"))

    assert reference_model_path.exists()
    assert candidate_model_path.exists()
    assert saved_candidate is not None
    assert saved_candidate["model_schema_version"] == SECOND_PASS_MODEL_SCHEMA_VERSION
    assert saved_candidate["candidate_family"] == "second_pass_experiment"
    assert saved_candidate["non_production"] is True
    assert metadata["runtime_enabled"] is False
    assert report["runtime_impact"] == "none"
    assert report["query_leakage_guard"]["passed"] is True
    assert report["candidate_model"]["non_production"] is True
    assert report["candidate_model"]["model_path"] == str(candidate_model_path)
    assert Path(report["report_paths"]["json_path"]).exists()
    assert Path(report["report_paths"]["markdown_path"]).exists()
    guardrail_names = {guardrail["name"] for guardrail in report["guardrails"]}
    assert {
        "no_query_leakage",
        "weak_competitor_coverage_fallback",
        "reference_artifact_unchanged",
        "candidate_non_production",
    }.issubset(guardrail_names)

    weak_result = build_second_pass_score_result(
        primary_score=64.0,
        enriched_features={"serp_relative_context_available": 0, "serp_relative_context_count": 0},
        candidate_model_path=candidate_model_path,
    )
    assert weak_result["status"] == "skipped"
    assert weak_result["effective_score"] == 64.0

    ready_features = {
        feature_name: 0.5
        for feature_name in SECOND_PASS_FEATURE_COLUMNS
    }
    ready_features["serp_relative_context_available"] = 1
    ready_features["serp_relative_context_count"] = 3
    ready_result = build_second_pass_score_result(
        primary_score=64.0,
        enriched_features=ready_features,
        candidate_model_path=candidate_model_path,
    )
    assert ready_result["status"] == "available"
    assert ready_result["runtime_effect"] == "candidate_score_reported_only"
    assert ready_result["effective_score"] == 64.0


def test_d44_generated_evidence_is_non_production_and_not_a_publish_decision():
    backend_dir = Path(__file__).resolve().parents[1]
    report_path = backend_dir / "artifacts" / "ranking-benchmarks" / "dataset-v3-d44" / "second-pass-experiment-report.json"
    metadata_path = backend_dir / "artifacts" / "page_quality_model.dataset-v3-d44-second-pass-experiment.metadata.json"

    report = json.loads(report_path.read_text(encoding="utf-8"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert report["decision"] == "do_not_continue_without_more_evidence"
    assert report["runtime_impact"] == "none"
    assert report["candidate_model"]["non_production"] is True
    assert report["candidate_model"]["runtime_enabled"] is False
    assert report["candidate_model"]["model_path"].endswith(
        "page_quality_model.dataset-v3-d44-second-pass-experiment.pkl"
    )
    assert metadata["non_production"] is True
    assert metadata["runtime_enabled"] is False
    assert metadata["usage_scope"] == "offline_second_pass_experiment_only"
