import json
from datetime import datetime
from pathlib import Path

import pytest

from app.ml.publish import (
    build_artifact_metadata_path,
    build_primary_artifact_version,
    build_primary_dataset_version,
    build_versioned_artifact_path,
    ensure_manifest_ready,
    load_training_manifest,
    publish_primary_model,
)
from app.ml.model import save_model, train_model
from app.ml.model_schema import get_model_feature_schema


def test_load_training_manifest_reads_json_payload(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    payload = {"quality_gates": {"ready_for_training": True}}
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded_manifest = load_training_manifest(manifest_path)

    assert loaded_manifest == payload


def test_ensure_manifest_ready_rejects_not_ready_manifest():
    with pytest.raises(ValueError, match="min_rows"):
        ensure_manifest_ready(
            {
                "quality_gates": {
                    "ready_for_training": False,
                    "unmet_requirements": ["min_rows"],
                }
            }
        )


def test_build_primary_dataset_version_prefers_manifest_dataset_version():
    version = build_primary_dataset_version(
        dataset_path=Path("backend/data/dataset_versions/dataset-v2/dataset.csv"),
        manifest={"dataset": {"version": "dataset-v2"}},
    )

    assert version == "dataset-v2"


def test_build_primary_dataset_version_uses_manifest_timestamp_when_explicit_version_is_missing():
    version = build_primary_dataset_version(
        dataset_path=Path("backend/data/ru_commercial_dataset.csv"),
        manifest={"generated_at": "2026-04-21T17:23:49.060829+00:00"},
    )

    assert version == "ru_commercial_dataset-20260421-primary"


def test_build_primary_artifact_version_and_paths_are_versioned():
    artifact_version = build_primary_artifact_version(
        dataset_version="ru_commercial_dataset-20260421-primary",
        published_at=datetime.fromisoformat("2026-04-21T17:32:48+00:00"),
    )
    versioned_path = build_versioned_artifact_path(Path("backend/artifacts/page_quality_model.pkl"), artifact_version)
    metadata_path = build_artifact_metadata_path(versioned_path)

    assert artifact_version == "ru_commercial_dataset-20260421-primary-20260421173248"
    assert versioned_path.name == "page_quality_model--ru_commercial_dataset-20260421-primary-20260421173248.pkl"
    assert metadata_path.name == "page_quality_model--ru_commercial_dataset-20260421-primary-20260421173248.metadata.json"


def test_publish_primary_model_trains_default_artifact_from_ready_manifest(monkeypatch, tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    manifest_path = tmp_path / "dataset.manifest.json"
    model_path = tmp_path / "page_quality_model.pkl"
    split_path = tmp_path / "split.json"
    dataset_path.write_text("query,target_score\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-21T17:23:49.060829+00:00",
                "dataset": {
                    "version": "dataset-v2-test",
                    "baseline_version": "baseline-v1",
                    "feature_schema_versions": ["v2"],
                    "extraction_artifact_versions": ["extraction-v2"],
                    "label_schema_versions": ["hybrid-v1"],
                    "split_path": str(split_path),
                },
                "labeling": {
                    "label_source_distribution": {"hybrid": 112, "weak_serp": 324},
                    "expert_rows_count": 112,
                    "hybrid_rows_count": 112,
                },
                "artifacts": {
                    "artifact_coverage_ratio": 1.0,
                },
                "coverage": {
                    "rows_count": 436,
                    "unique_queries": 47,
                    "unique_domains": 385,
                    "unique_categories": 6,
                    "unique_cities": 8,
                    "failure_rate": 0.07234,
                    "query_coverage_ratio": 0.235,
                    "attempted_query_coverage_ratio": 0.235,
                },
                "split": {"split_mode": "group_by_query"},
                "quality_gates": {"ready_for_training": True, "unmet_requirements": []},
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_train_quality_model(*, dataset_path, model_path, test_size, random_state, dataset_version, artifact_metadata, split_output_path=None, model_schema_version="v2"):
        captured.update(
            {
                "dataset_path": dataset_path,
                "model_path": model_path,
                "test_size": test_size,
                "random_state": random_state,
                "dataset_version": dataset_version,
                "artifact_metadata": artifact_metadata,
                "split_output_path": split_output_path,
                "model_schema_version": model_schema_version,
            }
        )
        save_model(
            model=train_model(n_samples=50, seed=7),
            metrics={"ndcg_at_10": 0.84, "top_3_hit_rate": 0.9, "split_mode": "group_by_query"},
            model_path=model_path,
            metadata={
                "model_type": "RandomForestRegressor",
                "source": "local_dataset",
                "dataset_version": dataset_version,
                "model_schema_version": model_schema_version,
                **artifact_metadata,
            },
        )
        return {
            "dataset_path": str(dataset_path),
            "model_path": str(model_path),
            "dataset_version": dataset_version,
            "artifact_version": str(artifact_metadata["artifact_version"]),
            "rows_count": 436,
            "queries_count": 47,
            "domains_count": 385,
            "model_type": "RandomForestRegressor",
            "metrics": {"ndcg_at_10": 0.84},
            "split": {"split_path": split_output_path, "split_mode": "group_by_query"},
        }

    monkeypatch.setattr("app.ml.publish.train_quality_model", fake_train_quality_model)
    monkeypatch.setattr("app.ml.publish.VERSIONED_ARTIFACTS_DIR", tmp_path / "versions")

    result = publish_primary_model(
        dataset_path=dataset_path,
        manifest_path=manifest_path,
        model_path=model_path,
        test_size=0.3,
        random_state=7,
    )

    assert captured["dataset_path"] == dataset_path
    assert captured["model_path"] == model_path
    assert captured["test_size"] == 0.3
    assert captured["random_state"] == 7
    assert captured["dataset_version"] == "dataset-v2-test"
    assert captured["model_schema_version"] == "v2"
    assert captured["split_output_path"] == str(split_path)
    assert captured["artifact_metadata"]["dataset_metadata"]["queries_count"] == 47
    assert captured["artifact_metadata"]["dataset_metadata"]["expert_rows_count"] == 112
    assert result["published_model_path"] == str(model_path)
    assert result["manifest_path"] == str(manifest_path)
    assert Path(result["published_metadata_path"]).exists()
    assert Path(result["versioned_model_path"]).exists()
    assert Path(result["versioned_metadata_path"]).exists()
    assert result["artifact_version"].startswith("dataset-v2-test-")
    assert result["model_schema_version"] == "v2"

    published_metadata = json.loads(Path(result["published_metadata_path"]).read_text(encoding="utf-8"))
    assert published_metadata["model_schema_version"] == "v2"
    assert published_metadata["feature_count"] == len(get_model_feature_schema("v2").feature_columns)
