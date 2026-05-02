from __future__ import annotations

import csv
from pathlib import Path

from app.ml.v5_candidate_training import (
    HYBRID_CANDIDATE_NAME,
    POINTWISE_CANDIDATE_NAME,
    RANKING_CANDIDATE_NAME,
    V5HybridRankerModel,
    attach_v5_targets,
    build_catboost_pairs,
    load_preference_pairs,
    run_d53_candidate_training,
    split_rows_from_manifest,
)


class _LinearModel:
    def __init__(self, weight: float) -> None:
        self.weight = weight

    def predict(self, rows: list[list[float]]) -> list[float]:
        return [self.weight * float(row[0]) for row in rows]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_preference_pairs_are_filtered_and_mapped_to_catboost_indices(tmp_path: Path) -> None:
    preferences_path = tmp_path / "preference_labels.csv"
    _write_csv(
        preferences_path,
        ["query", "winner_url", "loser_url", "usable_for_training", "weight", "preference_strength", "reason"],
        [
            {
                "query": "q",
                "winner_url": "https://a.example/",
                "loser_url": "https://b.example/",
                "usable_for_training": "True",
                "weight": "1.5",
                "preference_strength": "strong",
                "reason": "ranking_target_margin",
            },
            {
                "query": "q",
                "winner_url": "https://a.example/",
                "loser_url": "https://c.example/",
                "usable_for_training": "False",
                "weight": "0",
                "preference_strength": "uncertain",
                "reason": "manual_review",
            },
        ],
    )

    preferences = load_preference_pairs(preferences_path)
    pairs, weights, summary = build_catboost_pairs(
        [
            {"query": "q", "url": "https://b.example/"},
            {"query": "q", "url": "https://a.example/"},
        ],
        preferences,
    )

    assert len(preferences) == 1
    assert pairs == [(1, 0)]
    assert weights == [1.5]
    assert summary["pairs_count"] == 1
    assert summary["strength_distribution"] == {"strong": 1}


def test_split_rows_from_manifest_preserves_query_leakage_boundary() -> None:
    rows = [
        {"query": "train-q", "url": "https://a.example/"},
        {"query": "validation-q", "url": "https://b.example/"},
    ]
    train_rows, validation_rows, split = split_rows_from_manifest(
        rows,
        {"split_mode": "group_by_query", "train_queries": ["train-q"], "validation_queries": ["validation-q"]},
    )

    assert [row["query"] for row in train_rows] == ["train-q"]
    assert [row["query"] for row in validation_rows] == ["validation-q"]
    assert split["query_overlap_count"] == 0


def test_hybrid_ranker_model_keeps_predictions_bounded() -> None:
    model = V5HybridRankerModel(
        _LinearModel(10.0),
        _LinearModel(1.0),
        raw_min=0.0,
        raw_max=10.0,
        ranking_weight=0.2,
    )

    predictions = model.predict([[5.0], [20.0]])

    assert predictions[0] == 50.0
    assert predictions[1] == 100.0


def test_run_d53_candidate_training_writes_non_production_artifacts(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.controlled.csv"
    page_labels_path = tmp_path / "page_labels.csv"
    preference_labels_path = tmp_path / "preference_labels.csv"
    split_path = tmp_path / "split.json"
    feature_policy_path = tmp_path / "feature_policy.json"
    report_json_path = tmp_path / "report.json"
    report_md_path = tmp_path / "report.md"
    output_dir = tmp_path / "reports"
    feature_columns = ("page_indexable", "semantic_similarity", "word_count", "image_count")
    rows = [
        ("train-a", "https://a.example/1", 1, 1, 0.92, 900, 6, 90),
        ("train-a", "https://a.example/2", 2, 1, 0.78, 650, 3, 78),
        ("train-a", "https://a.example/3", 4, 1, 0.34, 1600, 24, 42),
        ("train-b", "https://b.example/1", 1, 1, 0.88, 850, 5, 88),
        ("train-b", "https://b.example/2", 3, 1, 0.55, 600, 2, 66),
        ("train-b", "https://b.example/3", 5, 0, 0.22, 1600, 24, 30),
        ("validation-q", "https://v.example/1", 1, 1, 0.86, 800, 5, 86),
        ("validation-q", "https://v.example/2", 4, 1, 0.44, 1600, 24, 48),
    ]
    fieldnames = [
        "dataset_version",
        "query",
        "url",
        "rank",
        "fetch_status",
        "target_score",
        *feature_columns,
    ]
    _write_csv(
        dataset_path,
        fieldnames,
        [
            {
                "dataset_version": "dataset-v5",
                "query": query,
                "url": url,
                "rank": rank,
                "fetch_status": "ok",
                "target_score": target,
                "page_indexable": page_indexable,
                "semantic_similarity": semantic,
                "word_count": word_count,
                "image_count": image_count,
            }
            for query, url, rank, page_indexable, semantic, word_count, image_count, target in rows
        ],
    )
    _write_csv(
        page_labels_path,
        ["query", "url", "page_target_score", "ranking_target_score"],
        [
            {
                "query": query,
                "url": url,
                "page_target_score": target,
                "ranking_target_score": max(0, min(100, target + (6 - rank))),
            }
            for query, url, rank, _page_indexable, _semantic, _word_count, _image_count, target in rows
        ],
    )
    _write_csv(
        preference_labels_path,
        ["query", "winner_url", "loser_url", "usable_for_training", "weight", "preference_strength", "reason"],
        [
            {
                "query": "train-a",
                "winner_url": "https://a.example/1",
                "loser_url": "https://a.example/3",
                "usable_for_training": "True",
                "weight": "1.5",
                "preference_strength": "strong",
                "reason": "ranking_target_margin",
            },
            {
                "query": "train-b",
                "winner_url": "https://b.example/1",
                "loser_url": "https://b.example/3",
                "usable_for_training": "True",
                "weight": "1.5",
                "preference_strength": "strong",
                "reason": "ranking_target_margin",
            },
            {
                "query": "validation-q",
                "winner_url": "https://v.example/1",
                "loser_url": "https://v.example/2",
                "usable_for_training": "True",
                "weight": "1.0",
                "preference_strength": "strong",
                "reason": "ranking_target_margin",
            },
        ],
    )
    split_path.write_text(
        '{"split_mode":"group_by_query","train_queries":["train-a","train-b"],"validation_queries":["validation-q"]}',
        encoding="utf-8",
    )
    feature_policy_path.write_text("{}", encoding="utf-8")

    report = run_d53_candidate_training(
        dataset_path=dataset_path,
        split_path=split_path,
        page_labels_path=page_labels_path,
        preference_labels_path=preference_labels_path,
        feature_policy_path=feature_policy_path,
        pointwise_model_path=tmp_path / "pointwise.pkl",
        ranking_model_path=tmp_path / "ranking.pkl",
        hybrid_model_path=tmp_path / "hybrid.pkl",
        reference_model_path=None,
        output_dir=output_dir,
        report_json_path=report_json_path,
        report_markdown_path=report_md_path,
        random_state=7,
        model_schema_version="custom",
        feature_columns=feature_columns,
    )

    assert report["production_artifact"]["changed_by_d53"] is False
    assert set(report["saved_artifacts"]) == {
        POINTWISE_CANDIDATE_NAME,
        RANKING_CANDIDATE_NAME,
        HYBRID_CANDIDATE_NAME,
    }
    assert all(item["compatibility_check"]["passed"] for item in report["candidate_metadata"].values())
    assert report_json_path.exists()
    assert report_md_path.exists()
