from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app.ml.dataset_quality import DatasetQualityThresholds
from app.ml.v4_dataset import LABEL_SCHEMA_VERSION_V4, build_v4_dataset, load_seo_weighted_labels


SOURCE_FIELDS = [
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
    "semantic_similarity",
    "keyword_coverage_ratio",
    "technical_seo_score",
    "commercial_trust_score",
]


LABEL_FIELDS = [
    "query",
    "url",
    "expert_target_score",
    "label_source",
    "labeler",
    "notes",
    "critical_score",
    "important_score",
    "supporting_score",
    "rank_prior_score",
    "cap_applied",
    "cap_reasons",
    "quality_band",
    "top_positive_factors",
    "top_negative_factors",
]


SEED_FIELDS = ["query", "category", "intent", "city", "region_code", "top_n", "pages_to_scan"]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _source_row(query: str, index: int, *, weak: float = 100.0, old_target: float = 90.0) -> dict[str, object]:
    return {
        "dataset_version": "dataset-v3-d37",
        "feature_schema_version": "v3",
        "extraction_artifact_version": "extraction-v2",
        "label_schema_version": "hybrid-v1",
        "label_source": "weak_serp",
        "weak_target_score": weak,
        "expert_target_score": "",
        "query": query,
        "category": "seo",
        "intent": "commercial",
        "city": "moscow" if query == "seo audit moscow" else "spb",
        "region_code": 213 if query == "seo audit moscow" else 2,
        "url": f"https://example-{index}.com/",
        "domain": f"example-{index}.com",
        "rank": index,
        "serp_page": 0,
        "title": f"Title {index}",
        "snippet": f"Snippet {index}",
        "page_type": "category",
        "fetch_status": "ok",
        "fetch_error": "",
        "artifact_path": f"row-{index}.json",
        "artifact_sha1": f"sha-{index}",
        "artifact_size_bytes": 12,
        "target_score": old_target,
        "semantic_similarity": 0.5,
        "keyword_coverage_ratio": 0.6,
        "technical_seo_score": 0.8,
        "commercial_trust_score": 0.7,
    }


def _label_for(row: dict[str, object], score: float, *, band: str = "medium") -> dict[str, object]:
    return {
        "query": row["query"],
        "url": row["url"],
        "expert_target_score": score,
        "label_source": "seo_weighted_rubric_v4",
        "labeler": "d45_seo_weighted_rubric_v1",
        "notes": "deterministic_expert_rubric=true; human_label=false",
        "critical_score": 0.7,
        "important_score": 0.6,
        "supporting_score": 0.3,
        "rank_prior_score": 0.8,
        "cap_applied": 100,
        "cap_reasons": "",
        "quality_band": band,
        "top_positive_factors": "semantic_query_fit:0.700",
        "top_negative_factors": "structured_support:0.300",
    }


def _low_thresholds() -> DatasetQualityThresholds:
    return DatasetQualityThresholds(
        min_rows=4,
        min_unique_queries=2,
        min_unique_domains=4,
        min_unique_categories=1,
        min_unique_cities=2,
        min_query_coverage_ratio=1.0,
        min_average_rows_per_query=2.0,
        max_failure_rate=0.2,
    )


def test_build_v4_dataset_applies_d45_labels_without_extra_serp_hybrid(tmp_path: Path) -> None:
    source_dir = tmp_path / "dataset-v3-d37"
    output_dir = tmp_path / "dataset-v4"
    artifacts_dir = tmp_path / "dataset-v2" / "artifacts"
    artifacts_dir.mkdir(parents=True)
    source_dataset = source_dir / "dataset.csv"
    source_seeds = source_dir / "seeds.csv"
    labels_path = output_dir / "expert_labels.csv"
    artifact_path = tmp_path / "page_quality_model.pkl"
    artifact_path.write_bytes(b"production-model")

    rows = [
        _source_row("seo audit moscow", 1, weak=100.0, old_target=100.0),
        _source_row("seo audit moscow", 2, weak=50.0, old_target=50.0),
        _source_row("ppc agency spb", 3, weak=100.0, old_target=100.0),
        _source_row("ppc agency spb", 4, weak=50.0, old_target=50.0),
    ]
    _write_csv(source_dataset, SOURCE_FIELDS, rows)
    _write_csv(
        source_seeds,
        SEED_FIELDS,
        [
            {
                "query": "seo audit moscow",
                "category": "seo",
                "intent": "commercial",
                "city": "moscow",
                "region_code": 213,
                "top_n": 2,
                "pages_to_scan": 1,
            },
            {
                "query": "ppc agency spb",
                "category": "seo",
                "intent": "commercial",
                "city": "spb",
                "region_code": 2,
                "top_n": 2,
                "pages_to_scan": 1,
            },
        ],
    )
    for row in rows:
        (artifacts_dir / str(row["artifact_path"])).write_text("{}", encoding="utf-8")
    _write_csv(
        labels_path,
        LABEL_FIELDS,
        [_label_for(row, 61.5 + index, band="medium") for index, row in enumerate(rows)],
    )

    report = build_v4_dataset(
        source_dataset_path=source_dataset,
        source_failures_path=source_dir / "missing-failures.csv",
        source_seeds_path=source_seeds,
        source_artifacts_dir=artifacts_dir,
        labels_path=labels_path,
        output_dataset_path=output_dir / "dataset.csv",
        output_failures_path=output_dir / "failures.csv",
        output_seeds_path=output_dir / "seeds.csv",
        output_split_path=output_dir / "split.json",
        output_manifest_path=output_dir / "manifest.json",
        output_report_json_path=output_dir / "d46-report.json",
        output_report_markdown_path=output_dir / "d46-report.md",
        production_artifact_path=artifact_path,
        thresholds=_low_thresholds(),
    )

    with (output_dir / "dataset.csv").open("r", encoding="utf-8", newline="") as file:
        output_rows = list(csv.DictReader(file))

    assert output_rows[0]["dataset_version"] == "dataset-v4"
    assert output_rows[0]["label_schema_version"] == LABEL_SCHEMA_VERSION_V4
    assert output_rows[0]["label_source"] == "seo_weighted_rubric_v4"
    assert float(output_rows[0]["expert_target_score"]) == 61.5
    assert float(output_rows[0]["target_score"]) == 61.5
    assert float(output_rows[0]["weak_target_score"]) == 100.0
    assert report["target_score_policy"] == "target_score_equals_d45_seo_weighted_expert_label"
    assert report["label_application"]["labels_loaded"] == 4
    assert report["label_application"]["labels_applied"] == 4
    assert report["label_application"]["missing_labels_count"] == 0
    assert report["query_leakage"]["passed"] is True
    assert report["manifest_ready_for_training"] is True
    assert report["production_artifact"]["changed_by_d46"] is False
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "split.json").exists()
    assert (output_dir / "d46-report.md").exists()


def test_load_seo_weighted_labels_rejects_invalid_rows(tmp_path: Path) -> None:
    labels_path = tmp_path / "expert_labels.csv"
    _write_csv(
        labels_path,
        LABEL_FIELDS,
        [
            {
                "query": "seo audit",
                "url": "",
                "expert_target_score": 70,
                "label_source": "seo_weighted_rubric_v4",
                "labeler": "d45",
            }
        ],
    )

    with pytest.raises(ValueError, match="Invalid D45 label"):
        load_seo_weighted_labels(labels_path)


def test_build_v4_dataset_requires_labels_for_every_source_row(tmp_path: Path) -> None:
    source_dir = tmp_path / "dataset-v3-d37"
    output_dir = tmp_path / "dataset-v4"
    source_dataset = source_dir / "dataset.csv"
    labels_path = output_dir / "expert_labels.csv"
    rows = [
        _source_row("seo audit moscow", 1),
        _source_row("seo audit moscow", 2),
    ]
    _write_csv(source_dataset, SOURCE_FIELDS, rows)
    _write_csv(labels_path, LABEL_FIELDS, [_label_for(rows[0], 70.0)])

    with pytest.raises(ValueError, match="every dataset row"):
        build_v4_dataset(
            source_dataset_path=source_dataset,
            source_failures_path=source_dir / "missing-failures.csv",
            source_seeds_path=source_dir / "missing-seeds.csv",
            labels_path=labels_path,
            output_dataset_path=output_dir / "dataset.csv",
            output_failures_path=output_dir / "failures.csv",
            output_seeds_path=output_dir / "seeds.csv",
            output_split_path=output_dir / "split.json",
            output_manifest_path=output_dir / "manifest.json",
            output_report_json_path=output_dir / "d46-report.json",
            output_report_markdown_path=output_dir / "d46-report.md",
        )
