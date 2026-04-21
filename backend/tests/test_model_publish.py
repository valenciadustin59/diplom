import json
from pathlib import Path

import pytest

from app.ml.publish import (
    build_primary_dataset_version,
    ensure_manifest_ready,
    load_training_manifest,
    publish_primary_model,
)


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


def test_build_primary_dataset_version_uses_manifest_timestamp():
    version = build_primary_dataset_version(
        dataset_path=Path("backend/data/ru_commercial_dataset.csv"),
        manifest={"generated_at": "2026-04-21T17:23:49.060829+00:00"},
    )

    assert version == "ru_commercial_dataset-20260421-primary"


def test_publish_primary_model_trains_default_artifact_from_ready_manifest(monkeypatch, tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    manifest_path = tmp_path / "dataset.manifest.json"
    model_path = tmp_path / "page_quality_model.pkl"
    dataset_path.write_text("query,target_score\n", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at": "2026-04-21T17:23:49.060829+00:00",
                "quality_gates": {"ready_for_training": True, "unmet_requirements": []},
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_train_quality_model(*, dataset_path, model_path, test_size, random_state, dataset_version):
        captured.update(
            {
                "dataset_path": dataset_path,
                "model_path": model_path,
                "test_size": test_size,
                "random_state": random_state,
                "dataset_version": dataset_version,
            }
        )
        return {
            "dataset_path": str(dataset_path),
            "model_path": str(model_path),
            "dataset_version": dataset_version,
            "rows_count": 436,
            "queries_count": 47,
            "domains_count": 385,
            "model_type": "RandomForestRegressor",
            "metrics": {"ndcg_at_10": 0.84},
        }

    monkeypatch.setattr("app.ml.publish.train_quality_model", fake_train_quality_model)

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
    assert captured["dataset_version"] == "dataset-20260421-primary"
    assert result["published_model_path"] == str(model_path)
    assert result["manifest_path"] == str(manifest_path)
