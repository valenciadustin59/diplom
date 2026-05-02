from __future__ import annotations

import csv
from pathlib import Path

from app.ml.model import save_model
from app.ml.v5_feature_policy import (
    DEFAULT_DATASET_VERSION,
    FEATURE_POLICY_VERSION_V5,
    apply_feature_policy_to_features,
    build_controlled_dataset,
    classify_feature_group,
    control_feature_value,
    feature_dominance_guardrail,
    run_d52_shortcut_feature_control,
    score_response_guardrail,
)


class _ScoreResponseModel:
    def predict(self, rows: list[list[float]]) -> list[float]:
        output: list[float] = []
        for page_indexable, semantic_similarity, word_count, image_count in rows:
            output.append(
                20.0
                + 55.0 * float(page_indexable)
                + 20.0 * float(semantic_similarity)
                + 0.001 * float(word_count)
                + 0.05 * float(image_count)
            )
        return output


def test_shortcut_policy_caps_raw_counts_but_preserves_thin_signal() -> None:
    assert control_feature_value("word_count", 3500) == 1600
    assert control_feature_value("word_count", 120) == 120
    assert control_feature_value("image_count", 80) == 24
    assert control_feature_value("link_count", 999) == 80
    assert control_feature_value("semantic_similarity", 1.7) == 1.0

    features = apply_feature_policy_to_features(
        {
            "word_count": 2400,
            "text_length_chars": 16000,
            "page_indexable": 2,
            "semantic_similarity": 0.72,
        }
    )

    assert features["word_count"] == 1600
    assert features["text_length_chars"] == 9600
    assert features["page_indexable"] == 1.0
    assert features["semantic_similarity"] == 0.72


def test_feature_groups_and_dominance_guardrail_reject_supporting_shortcut_top_feature() -> None:
    assert classify_feature_group("semantic_similarity") == "critical"
    assert classify_feature_group("commercial_trust_score") == "important"
    assert classify_feature_group("word_count") == "supporting"

    guardrail = feature_dominance_guardrail(
        {
            "feature_importance_summary": {
                "top_features": [
                    {"feature": "word_count", "importance": 12.0},
                    {"feature": "unique_word_count", "importance": 8.0},
                    {"feature": "semantic_similarity", "importance": 4.0},
                    {"feature": "page_indexable", "importance": 3.0},
                ]
            }
        }
    )

    assert guardrail["passed"] is False
    assert guardrail["top_feature"] == "word_count"
    assert guardrail["top_feature_group"] == "supporting"
    assert "top_feature_not_supporting" in guardrail["failed_checks"]


def test_score_response_guardrail_runs_against_saved_artifact(tmp_path: Path) -> None:
    feature_columns = ("page_indexable", "semantic_similarity", "word_count", "image_count")
    model = _ScoreResponseModel()
    model_path = tmp_path / "candidate.pkl"
    save_model(
        model,
        metrics={"mae": 1.0},
        model_path=model_path,
        metadata={
            "model_schema_version": "custom",
            "feature_columns": list(feature_columns),
            "dataset_version": "unit-test",
        },
    )
    rows = [
        {
            "query": "q",
            "url": "https://a.example/",
            "target_score": "90",
            "page_indexable": "1",
            "semantic_similarity": "0.9",
            "word_count": "3600",
            "image_count": "50",
        },
        {
            "query": "q",
            "url": "https://b.example/",
            "target_score": "75",
            "page_indexable": "1",
            "semantic_similarity": "0.7",
            "word_count": "650",
            "image_count": "3",
        },
    ]

    guardrail = score_response_guardrail(model_path=model_path, rows=rows, feature_columns=feature_columns)

    assert guardrail["rows_count"] == 2
    assert guardrail["passed"] is True
    assert guardrail["average_critical_drop"] > guardrail["average_supporting_drop"]
    assert guardrail["feature_policy_version"] == FEATURE_POLICY_VERSION_V5


def test_build_controlled_dataset_writes_policy_version_and_change_summary(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    controlled_path = tmp_path / "dataset.controlled.csv"
    fieldnames = ["dataset_version", "query", "url", "fetch_status", "target_score", "word_count", "image_count"]
    with dataset_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(
            {
                "dataset_version": "dataset-v5",
                "query": "q",
                "url": "https://a.example/",
                "fetch_status": "ok",
                "target_score": "80",
                "word_count": "3000",
                "image_count": "80",
            }
        )

    summary = build_controlled_dataset(
        dataset_path,
        controlled_path,
        feature_columns=("word_count", "image_count"),
    )

    with controlled_path.open("r", encoding="utf-8", newline="") as file:
        row = next(csv.DictReader(file))
    assert row["dataset_version"] == DEFAULT_DATASET_VERSION
    assert row["feature_policy_version"] == FEATURE_POLICY_VERSION_V5
    assert row["word_count"] == "1600"
    assert row["image_count"] == "24"
    assert summary["changed_shortcut_features_count"] == 2
    assert summary["changed_shortcut_rows_total"] == 2


def test_run_d52_report_can_build_without_candidate_artifacts(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    split_path = tmp_path / "split.json"
    candidate_report_path = tmp_path / "missing-candidates.json"
    controlled_path = tmp_path / "dataset.controlled.csv"
    feature_policy_path = tmp_path / "feature_policy.json"
    output_dir = tmp_path / "reports"
    fieldnames = ["dataset_version", "query", "url", "fetch_status", "target_score", "word_count", "image_count"]
    with dataset_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for index in range(2):
            writer.writerow(
                {
                    "dataset_version": "dataset-v5",
                    "query": "q",
                    "url": f"https://a.example/{index}",
                    "fetch_status": "ok",
                    "target_score": "80",
                    "word_count": "3000",
                    "image_count": "80",
                }
            )
    split_path.write_text('{"validation_queries": ["q"]}', encoding="utf-8")

    report = run_d52_shortcut_feature_control(
        dataset_path=dataset_path,
        controlled_dataset_path=controlled_path,
        feature_policy_path=feature_policy_path,
        split_path=split_path,
        candidate_report_path=candidate_report_path,
        output_dir=output_dir,
    )

    assert report["decision"] == "ready_for_d53"
    assert report["acceptance"]["feature_policy_implemented"] is True
    assert report["acceptance"]["controlled_dataset_written"] is True
    assert report["candidate_guardrail_evidence"]["candidates_count"] == 0
    assert Path(report["report_paths"]["json_path"]).exists()
    assert Path(report["report_paths"]["markdown_path"]).exists()
