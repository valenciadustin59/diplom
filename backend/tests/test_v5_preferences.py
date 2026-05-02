from __future__ import annotations

import csv
from pathlib import Path

from app.ml.dataset_quality import DatasetQualityThresholds
from app.ml.v5_preferences import (
    LABEL_SCHEMA_VERSION_V5,
    build_preference_labels,
    build_v5_query_preference_dataset,
    validate_preference_split,
)


FIELDS = [
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
    "http_status_ok",
    "page_indexable",
    "canonical_signal_score",
    "technical_seo_score",
    "title_keyword_coverage_ratio",
    "heading_query_coverage_ratio",
    "semantic_similarity",
    "query_semantic_alignment",
    "keyword_coverage_ratio",
    "intent_alignment_score",
    "word_count",
]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _row(query: str, index: int, *, score: float, rank: int | None = None, semantic: float = 0.8) -> dict[str, object]:
    resolved_rank = rank or index
    return {
        "dataset_version": "dataset-v4",
        "feature_schema_version": "v3",
        "extraction_artifact_version": "extraction-v2",
        "label_schema_version": "seo-weighted-v4",
        "label_source": "seo_weighted_rubric_v4",
        "weak_target_score": 100 - index,
        "expert_target_score": score,
        "query": query,
        "category": "seo",
        "intent": "commercial",
        "city": "moscow",
        "region_code": 213,
        "url": f"https://example-{query}-{index}.com/",
        "domain": f"example-{query}-{index}.com",
        "rank": resolved_rank,
        "serp_page": 0,
        "title": f"Title {index}",
        "snippet": f"Snippet {index}",
        "page_type": "category",
        "fetch_status": "ok",
        "fetch_error": "",
        "artifact_path": f"row-{query}-{index}.json",
        "artifact_sha1": f"sha-{query}-{index}",
        "artifact_size_bytes": 10,
        "target_score": score,
        "http_status_ok": 1,
        "page_indexable": 1,
        "canonical_signal_score": 1,
        "technical_seo_score": 1,
        "title_keyword_coverage_ratio": semantic,
        "heading_query_coverage_ratio": semantic,
        "semantic_similarity": semantic,
        "query_semantic_alignment": semantic,
        "keyword_coverage_ratio": semantic,
        "intent_alignment_score": semantic,
        "word_count": 700 + index,
    }


def _low_thresholds() -> DatasetQualityThresholds:
    return DatasetQualityThresholds(
        min_rows=4,
        min_unique_queries=2,
        min_unique_domains=4,
        min_unique_categories=1,
        min_unique_cities=1,
        min_query_coverage_ratio=1.0,
        min_average_rows_per_query=2.0,
        max_failure_rate=0.3,
    )


def test_build_preference_labels_uses_margin_strengths_and_uncertain_zero_weight() -> None:
    rows = [
        _row("q", 1, score=90, rank=1),
        _row("q", 2, score=82, rank=2),
        _row("q", 3, score=78, rank=3),
        _row("q", 4, score=76.5, rank=4),
    ]

    preferences = build_preference_labels(rows, strong_margin=8.0, weak_margin=4.0, uncertain_margin=1.0)

    strengths = {preference.preference_strength for preference in preferences}
    assert "strong" in strengths
    assert "weak" in strengths
    assert "uncertain" in strengths
    assert any(preference.weight == 0.0 and not preference.usable_for_training for preference in preferences)


def test_d50_recovery_does_not_blindly_force_bad_serp_row_as_winner() -> None:
    rows = [
        _row("q", 1, score=20, rank=1, semantic=0.1),
        _row("q", 2, score=82, rank=8, semantic=0.9),
    ]
    d50_report = {
        "suggested_d51_focus": [{"area": "query_level_preference_labels", "queries": ["q"]}],
        "query_diagnostics": [
            {
                "query": "q",
                "lost_actual_top3": [{"url": rows[0]["url"]}],
                "promoted_non_top3": [{"url": rows[1]["url"]}],
                "patterns": ["rank_prior_disagreement"],
            }
        ],
    }

    preferences = build_preference_labels(rows, d50_report=d50_report, uncertain_margin=1.0)
    recovery_preferences = [preference for preference in preferences if preference.reason.startswith("d50")]

    assert recovery_preferences
    assert all(preference.preference_strength == "uncertain" for preference in recovery_preferences)
    assert all(preference.usable_for_training is False for preference in recovery_preferences)
    assert all(preference.winner_url == rows[1]["url"] for preference in recovery_preferences)


def test_validate_preference_split_tracks_focus_query_coverage() -> None:
    rows = [
        _row("train-q", 1, score=90),
        _row("train-q", 2, score=70),
        _row("validation-q", 3, score=88),
        _row("validation-q", 4, score=60),
    ]
    preferences = build_preference_labels(rows)
    split = {
        "split_mode": "group_by_query",
        "train_queries": ["train-q"],
        "validation_queries": ["validation-q"],
    }

    validation = validate_preference_split(preferences, split, d50_focus_queries={"validation-q"})

    assert validation["passed"] is True
    assert validation["train_preferences_count"] > 0
    assert validation["validation_preferences_count"] > 0
    assert validation["d50_focus_queries_represented_count"] == 1


def test_build_v5_query_preference_dataset_writes_sidecars(tmp_path: Path) -> None:
    source_dir = tmp_path / "dataset-v4"
    output_dir = tmp_path / "dataset-v5"
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    production_artifact = tmp_path / "page_quality_model.pkl"
    production_artifact.write_bytes(b"production")
    rows = [
        _row("train-q", 1, score=91, rank=1),
        _row("train-q", 2, score=70, rank=2),
        _row("validation-q", 3, score=89, rank=1),
        _row("validation-q", 4, score=62, rank=5),
    ]
    source_dataset = source_dir / "dataset.csv"
    _write_csv(source_dataset, FIELDS, rows)
    _write_csv(source_dir / "failures.csv", FIELDS[:5], [])
    _write_csv(
        source_dir / "seeds.csv",
        ["query", "category", "intent", "city", "region_code", "top_n", "pages_to_scan"],
        [
            {"query": "train-q", "category": "seo", "intent": "commercial", "city": "moscow", "region_code": 213, "top_n": 2, "pages_to_scan": 1},
            {"query": "validation-q", "category": "seo", "intent": "commercial", "city": "moscow", "region_code": 213, "top_n": 2, "pages_to_scan": 1},
        ],
    )
    for row in rows:
        (artifacts_dir / str(row["artifact_path"])).write_text("{}", encoding="utf-8")
    d50_report = tmp_path / "d50.json"
    d50_report.write_text(
        """
        {
          "suggested_d51_focus": [{"area": "query_level_preference_labels", "queries": ["validation-q"]}],
          "query_diagnostics": []
        }
        """,
        encoding="utf-8",
    )

    report = build_v5_query_preference_dataset(
        source_dataset_path=source_dataset,
        source_failures_path=source_dir / "failures.csv",
        source_seeds_path=source_dir / "seeds.csv",
        source_artifacts_dir=artifacts_dir,
        d50_report_path=d50_report,
        output_dataset_path=output_dir / "dataset.csv",
        output_failures_path=output_dir / "failures.csv",
        output_seeds_path=output_dir / "seeds.csv",
        output_split_path=output_dir / "split.json",
        output_manifest_path=output_dir / "manifest.json",
        output_page_labels_path=output_dir / "page_labels.csv",
        output_preference_labels_path=output_dir / "preference_labels.csv",
        output_split_validation_path=output_dir / "split-validation.json",
        output_report_json_path=output_dir / "d51-report.json",
        output_report_markdown_path=output_dir / "d51-report.md",
        production_artifact_path=production_artifact,
        thresholds=_low_thresholds(),
    )

    with (output_dir / "dataset.csv").open("r", encoding="utf-8", newline="") as file:
        output_rows = list(csv.DictReader(file))

    assert output_rows[0]["dataset_version"] == "dataset-v5"
    assert output_rows[0]["label_schema_version"] == LABEL_SCHEMA_VERSION_V5
    assert (output_dir / "page_labels.csv").exists()
    assert (output_dir / "preference_labels.csv").exists()
    assert (output_dir / "manifest.json").exists()
    assert report["preference_labels_count"] > 0
    assert report["split_validation"]["passed"] is True
    assert report["production_artifact"]["changed_by_d51"] is False
