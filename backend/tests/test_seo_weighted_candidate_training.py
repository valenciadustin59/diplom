from __future__ import annotations

import csv
import json
from pathlib import Path

from app.ml.model import load_saved_model
from app.ml.model_schema import MODEL_SCHEMA_VERSION_V3, get_model_feature_schema
from app.ml.seo_weighted_candidate_training import run_d47_candidate_training
from app.ml.v4_dataset import LABEL_SCHEMA_VERSION_V4


V3_FEATURE_COLUMNS = get_model_feature_schema(MODEL_SCHEMA_VERSION_V3).feature_columns
BASE_FIELDS = [
    "dataset_version",
    "feature_schema_version",
    "extraction_artifact_version",
    "label_schema_version",
    "label_source",
    "weak_target_score",
    "expert_target_score",
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
    "artifact_path",
    "artifact_sha1",
    "artifact_size_bytes",
    "target_score",
]
DATASET_FIELDS = list(dict.fromkeys([*BASE_FIELDS, *V3_FEATURE_COLUMNS]))


def _write_dataset(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DATASET_FIELDS)
        writer.writeheader()
        for query_index in range(1, 5):
            query = f"seo query {query_index}"
            for rank in range(1, 4):
                row: dict[str, object] = {field: "" for field in DATASET_FIELDS}
                row.update(
                    {
                        "dataset_version": "dataset-v4",
                        "feature_schema_version": "v3",
                        "extraction_artifact_version": "extraction-v2",
                        "label_schema_version": LABEL_SCHEMA_VERSION_V4,
                        "label_source": "seo_weighted_rubric_v4",
                        "weak_target_score": 100.0 - rank * 10.0,
                        "expert_target_score": 72.0 - rank * 4.0 + query_index,
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
                        "page_type": "service",
                        "fetch_status": "ok",
                        "fetch_error": "",
                        "artifact_path": f"artifact-{query_index}-{rank}.json",
                        "artifact_sha1": f"sha-{query_index}-{rank}",
                        "artifact_size_bytes": 20,
                        "target_score": 72.0 - rank * 4.0 + query_index,
                    }
                )
                for feature_index, feature_name in enumerate(V3_FEATURE_COLUMNS, start=1):
                    row[feature_name] = round((feature_index % 13 + 1) * (query_index + 1) / (rank + 2), 6)
                writer.writerow(row)


def _write_manifest(path: Path) -> None:
    path.write_text(
        json.dumps({"quality_gates": {"ready_for_training": True}}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_dataset_report(path: Path) -> None:
    path.write_text(
        json.dumps(
            {"target_score_policy": "target_score_equals_d45_seo_weighted_expert_label"},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_run_d47_candidate_training_writes_non_production_artifacts(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset-v4" / "dataset.csv"
    manifest_path = tmp_path / "dataset-v4" / "manifest.json"
    label_report_path = tmp_path / "dataset-v4" / "d45-report.json"
    dataset_report_path = tmp_path / "dataset-v4" / "d46-report.json"
    output_dir = tmp_path / "reports"
    reference_model_path = tmp_path / "page_quality_model.pkl"
    rf_model_path = tmp_path / "page_quality_model.dataset-v4-seo-weighted-rf-candidate.pkl"
    catboost_model_path = tmp_path / "page_quality_model.dataset-v4-seo-weighted-catboost-candidate.pkl"
    ranking_model_path = tmp_path / "page_quality_model.dataset-v4-seo-weighted-ranking-candidate.pkl"
    reference_model_path.write_bytes(b"current-production")
    reference_before = reference_model_path.read_bytes()
    _write_dataset(dataset_path)
    _write_manifest(manifest_path)
    label_report_path.write_text("{}", encoding="utf-8")
    _write_dataset_report(dataset_report_path)

    report = run_d47_candidate_training(
        dataset_path=dataset_path,
        manifest_path=manifest_path,
        label_report_path=label_report_path,
        dataset_report_path=dataset_report_path,
        rf_model_path=rf_model_path,
        catboost_model_path=catboost_model_path,
        ranking_model_path=ranking_model_path,
        reference_model_path=reference_model_path,
        output_dir=output_dir,
        report_json_path=output_dir / "d47-report.json",
        report_markdown_path=output_dir / "d47-report.md",
        test_size=0.25,
        random_state=7,
    )

    assert reference_model_path.read_bytes() == reference_before
    assert report["production_artifact"]["changed_by_d47"] is False
    assert report["model_schema_version"] == MODEL_SCHEMA_VERSION_V3
    assert report["label_schema_version"] == LABEL_SCHEMA_VERSION_V4
    assert report["manifest_ready_for_training"] is True
    assert report["report_paths"]["json_path"].endswith("d47-report.json")
    assert report["report_paths"]["markdown_path"].endswith("d47-report.md")
    for model_path in (rf_model_path, catboost_model_path, ranking_model_path):
        assert model_path.exists()
        metadata = json.loads(model_path.with_suffix(".metadata.json").read_text(encoding="utf-8"))
        payload = load_saved_model(model_path)
        assert metadata["training_task"] == "D47"
        assert metadata["non_production"] is True
        assert metadata["runtime_enabled"] is False
        assert metadata["compatibility_check"]["passed"] is True
        assert payload is not None
        assert payload["training_task"] == "D47"
        assert payload["non_production"] is True
        assert payload["runtime_enabled"] is False
