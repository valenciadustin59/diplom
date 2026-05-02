from __future__ import annotations

import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = PROJECT_ROOT / "backend" / "data" / "query_relevance_v1"
CATALOG_PATH = CATALOG_DIR / "relevance_training_queries.csv"
MANIFEST_PATH = CATALOG_DIR / "manifest.json"


def _load_rows() -> list[dict[str, str]]:
    with CATALOG_PATH.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def test_query_relevance_catalog_has_200_unique_queries() -> None:
    rows = _load_rows()

    assert len(rows) == 200
    assert len({row["query"] for row in rows}) == 200
    assert all(row["target_topic"] for row in rows)
    assert all(row["positive_page_pattern"] for row in rows)
    assert all(row["negative_page_traps"] for row in rows)


def test_query_relevance_catalog_is_balanced_by_category() -> None:
    rows = _load_rows()
    categories = sorted({row["category"] for row in rows})

    assert len(categories) == 20
    assert all(sum(1 for row in rows if row["category"] == category) == 10 for category in categories)


def test_query_relevance_manifest_matches_catalog() -> None:
    rows = _load_rows()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["version"] == "query-relevance-v1"
    assert manifest["rows"] == len(rows)
    assert manifest["unique_queries"] == len({row["query"] for row in rows})
    assert manifest["categories"] == len({row["category"] for row in rows})
