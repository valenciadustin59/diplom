import csv
from pathlib import Path

from app.ml.dataset_quality import (
    DatasetQualityThresholds,
    build_dataset_manifest,
    default_manifest_path,
    save_dataset_manifest,
)


SUCCESS_FIELDS = ["query", "category", "city", "region_code", "domain", "rank", "page_type"]
FAILURE_FIELDS = ["query", "category", "city", "region_code", "fetch_error"]
SEED_FIELDS = ["query", "category", "intent", "city", "region_code", "top_n", "pages_to_scan"]


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _seed_rows() -> list[dict[str, object]]:
    return [
        {
            "query": "seo audit moscow",
            "category": "seo",
            "intent": "commercial",
            "city": "moscow",
            "region_code": 213,
            "top_n": 10,
            "pages_to_scan": 1,
        },
        {
            "query": "ppc agency spb",
            "category": "ppc",
            "intent": "commercial",
            "city": "spb",
            "region_code": 2,
            "top_n": 10,
            "pages_to_scan": 1,
        },
        {
            "query": "legal services moscow",
            "category": "legal",
            "intent": "commercial",
            "city": "moscow",
            "region_code": 213,
            "top_n": 10,
            "pages_to_scan": 1,
        },
    ]


def test_build_dataset_manifest_reports_coverage_and_quality_gates(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    failures_path = tmp_path / "failures.csv"
    manifest_path = tmp_path / "dataset.manifest.json"

    _write_csv(
        dataset_path,
        SUCCESS_FIELDS,
        [
            {
                "query": "seo audit moscow",
                "category": "seo",
                "city": "moscow",
                "region_code": 213,
                "domain": "example-1.com",
                "rank": 1,
                "page_type": "content",
            },
            {
                "query": "seo audit moscow",
                "category": "seo",
                "city": "moscow",
                "region_code": 213,
                "domain": "example-2.com",
                "rank": 2,
                "page_type": "homepage",
            },
            {
                "query": "ppc agency spb",
                "category": "ppc",
                "city": "spb",
                "region_code": 2,
                "domain": "example-3.com",
                "rank": 1,
                "page_type": "content",
            },
            {
                "query": "ppc agency spb",
                "category": "ppc",
                "city": "spb",
                "region_code": 2,
                "domain": "example-4.com",
                "rank": 2,
                "page_type": "category",
            },
        ],
    )
    _write_csv(
        failures_path,
        FAILURE_FIELDS,
        [
            {
                "query": "legal services moscow",
                "category": "legal",
                "city": "moscow",
                "region_code": 213,
                "fetch_error": "timeout",
            }
        ],
    )

    thresholds = DatasetQualityThresholds(
        min_rows=4,
        min_unique_queries=2,
        min_unique_domains=4,
        min_unique_categories=2,
        min_unique_cities=2,
        min_query_coverage_ratio=0.6,
        min_average_rows_per_query=2.0,
        max_failure_rate=0.25,
    )

    manifest = build_dataset_manifest(
        dataset_path=dataset_path,
        failures_path=failures_path,
        seed_rows=_seed_rows(),
        thresholds=thresholds,
    )

    assert manifest["coverage"]["rows_count"] == 4
    assert manifest["coverage"]["failures_count"] == 1
    assert manifest["coverage"]["unique_queries"] == 2
    assert manifest["coverage"]["attempted_queries"] == 3
    assert manifest["coverage"]["seed_queries_count"] == 3
    assert manifest["coverage"]["unique_domains"] == 4
    assert manifest["coverage"]["query_coverage_ratio"] == 0.666667
    assert manifest["coverage"]["attempted_query_coverage_ratio"] == 1.0
    assert manifest["coverage"]["average_rows_per_query"] == 2.0
    assert manifest["coverage"]["failure_rate"] == 0.2
    assert manifest["quality_gates"]["ready_for_training"] is True
    assert manifest["quality_gates"]["unmet_requirements"] == []

    saved_manifest = save_dataset_manifest(
        dataset_path=dataset_path,
        failures_path=failures_path,
        seed_rows=_seed_rows(),
        output_path=manifest_path,
        thresholds=thresholds,
    )
    assert Path(saved_manifest["manifest_path"]).exists()


def test_build_dataset_manifest_reports_unmet_requirements(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    failures_path = tmp_path / "failures.csv"

    _write_csv(
        dataset_path,
        SUCCESS_FIELDS,
        [
            {
                "query": "seo audit moscow",
                "category": "seo",
                "city": "moscow",
                "region_code": 213,
                "domain": "example-1.com",
                "rank": 1,
                "page_type": "content",
            }
        ],
    )
    _write_csv(
        failures_path,
        FAILURE_FIELDS,
        [
            {
                "query": "legal services moscow",
                "category": "legal",
                "city": "moscow",
                "region_code": 213,
                "fetch_error": "timeout",
            }
        ],
    )

    manifest = build_dataset_manifest(
        dataset_path=dataset_path,
        failures_path=failures_path,
        seed_rows=_seed_rows(),
        thresholds=DatasetQualityThresholds(
            min_rows=2,
            min_unique_queries=2,
            min_unique_domains=2,
            min_unique_categories=2,
            min_unique_cities=2,
            min_query_coverage_ratio=0.7,
            min_average_rows_per_query=1.0,
            max_failure_rate=0.1,
        ),
    )

    assert manifest["quality_gates"]["ready_for_training"] is False
    assert "min_rows" in manifest["quality_gates"]["unmet_requirements"]
    assert "min_unique_queries" in manifest["quality_gates"]["unmet_requirements"]
    assert "min_unique_domains" in manifest["quality_gates"]["unmet_requirements"]
    assert "min_unique_categories" in manifest["quality_gates"]["unmet_requirements"]
    assert "min_query_coverage_ratio" in manifest["quality_gates"]["unmet_requirements"]
    assert "max_failure_rate" in manifest["quality_gates"]["unmet_requirements"]
    assert default_manifest_path(dataset_path).name == "dataset.manifest.json"
