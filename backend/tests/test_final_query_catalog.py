from __future__ import annotations

import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = PROJECT_ROOT / "backend" / "data" / "query_relevance_v2"
CATALOG_PATH = CATALOG_DIR / "final_training_queries.csv"
MANIFEST_PATH = CATALOG_DIR / "manifest.json"
DATASET_DIR = PROJECT_ROOT / "backend" / "data" / "dataset_versions" / "dataset-v7-final"
SEEDS_PATH = DATASET_DIR / "seeds.csv"
DATASET_MANIFEST_PATH = DATASET_DIR / "manifest.json"


def _load_rows(path: Path = CATALOG_PATH) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def test_final_query_catalog_has_500_unique_top10_queries() -> None:
    rows = _load_rows()

    assert len(rows) == 500
    assert len({row["query"] for row in rows}) == 500
    assert {row["top_n"] for row in rows} == {"10"}
    assert {row["pages_to_scan"] for row in rows} == {"1"}
    assert all(row["target_topic"] for row in rows)
    assert all(row["positive_page_pattern"] for row in rows)
    assert all("качественный сайт из другой тематики" in row["negative_page_traps"] for row in rows)


def test_final_query_catalog_expands_categories_and_cities() -> None:
    rows = _load_rows()
    categories = {row["category"] for row in rows}
    cities = {row["city"] for row in rows if row["city"]}

    assert len(categories) == 50
    assert all(sum(1 for row in rows if row["category"] == category) == 10 for category in categories)
    assert cities == {"Москва", "Санкт-Петербург", "Екатеринбург", "Казань", "Новосибирск"}


def test_dataset_v7_manifest_preserves_seed_policy_after_candidate_training() -> None:
    catalog_rows = _load_rows(CATALOG_PATH)
    seed_rows = _load_rows(SEEDS_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    dataset_manifest = json.loads(DATASET_MANIFEST_PATH.read_text(encoding="utf-8"))

    assert seed_rows == catalog_rows
    assert manifest["version"] == "query-relevance-v2-final"
    assert manifest["dataset_version"] == "dataset-v7-final"
    assert manifest["collection_policy"]["weak_serp_labels_allowed"] is False
    assert manifest["collection_policy"]["current_dataset_v6_is_draft_only"] is True
    assert dataset_manifest["collection_policy"]["weak_serp_labels_allowed"] is False
    assert dataset_manifest["collection_policy"]["current_dataset_v6_is_draft_only"] is True
    assert dataset_manifest["status"] == "candidate_trained"
    assert dataset_manifest["ready_for_training"] is True
    assert dataset_manifest["split_progress"]["query_overlap_count"] == 0
    assert dataset_manifest["training_progress"]["runtime_enabled"] is False
