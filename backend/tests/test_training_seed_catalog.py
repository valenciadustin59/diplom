from pathlib import Path

from app.ml.query_seeds import (
    DATASET_V2_QUERY_PATTERNS,
    RU_COMMERCIAL_CATEGORIES,
    RU_COMMERCIAL_CITIES,
    TRAINING_SEED_FIELDS,
    build_dataset_v2_seed_rows,
    build_dataset_v2_seed_summary,
    build_seed_catalog_summary,
    build_training_queries,
    build_training_seed_rows,
    save_seed_rows,
)


def test_build_training_seed_rows_are_unique_and_cover_ru_taxonomy():
    rows = build_training_seed_rows(top_n=12, pages_to_scan=2)

    assert len(rows) == len(RU_COMMERCIAL_CATEGORIES) * len(RU_COMMERCIAL_CITIES)
    assert len({str(row["query"]) for row in rows}) == len(rows)
    assert {str(row["intent"]) for row in rows} == {"commercial"}
    assert {int(row["top_n"]) for row in rows} == {12}
    assert {int(row["pages_to_scan"]) for row in rows} == {2}
    assert "Москва" in {str(row["city"]) for row in rows}
    assert "seo продвижение" in {str(row["category"]) for row in rows}

    queries = build_training_queries(rows)
    assert len(queries) == len(rows)

    summary = build_seed_catalog_summary(rows)
    assert summary["seed_rows_count"] == len(rows)
    assert summary["queries_count"] == len(rows)
    assert summary["categories_count"] == len(RU_COMMERCIAL_CATEGORIES)
    assert summary["cities_count"] == len(RU_COMMERCIAL_CITIES)


def test_build_dataset_v2_seed_rows_expands_catalog_with_multiple_intents_and_patterns():
    rows = build_dataset_v2_seed_rows(top_n=11, pages_to_scan=3)
    city_patterns_count = sum(1 for pattern in DATASET_V2_QUERY_PATTERNS if pattern.uses_city)
    non_city_patterns_count = sum(1 for pattern in DATASET_V2_QUERY_PATTERNS if not pattern.uses_city)
    expected_count = len(RU_COMMERCIAL_CATEGORIES) * (
        city_patterns_count * len(RU_COMMERCIAL_CITIES) + non_city_patterns_count
    )

    assert len(rows) == expected_count
    assert len(build_training_queries(rows)) == expected_count
    assert {str(row["intent"]) for row in rows} == {"commercial", "informational"}
    assert {int(row["top_n"]) for row in rows} == {11}
    assert {int(row["pages_to_scan"]) for row in rows} == {3}
    assert any(str(row["query"]).startswith("как выбрать ") for row in rows)
    assert any(str(row["query"]).endswith(" отзывы") for row in rows)
    assert any(str(row["query"]).endswith(" Москва") for row in rows)
    assert any(str(row["city"]) == "" for row in rows)
    assert any(str(row["city"]) == "Москва" for row in rows)

    summary = build_dataset_v2_seed_summary(rows)
    assert summary["seed_rows_count"] == expected_count
    assert summary["queries_count"] == expected_count
    assert summary["intent_count"] == 2
    assert summary["intents"] == ["commercial", "informational"]
    assert summary["query_patterns_count"] == len(DATASET_V2_QUERY_PATTERNS)
    assert summary["target_query_range"] == "300-500"


def test_save_seed_rows_persists_v2_catalog_with_compatible_headers(tmp_path):
    rows = build_dataset_v2_seed_rows(top_n=10, pages_to_scan=2)
    output_path = tmp_path / "dataset-v2-seeds.csv"

    saved_path = save_seed_rows(output_path, rows)

    assert saved_path == output_path
    assert output_path.exists()

    content = output_path.read_text(encoding="utf-8")
    header = content.splitlines()[0]
    assert header.split(",") == TRAINING_SEED_FIELDS
    assert "как выбрать" in content
    assert "отзывы" in content
