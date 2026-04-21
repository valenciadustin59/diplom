from app.ml.query_seeds import (
    RU_COMMERCIAL_CATEGORIES,
    RU_COMMERCIAL_CITIES,
    build_seed_catalog_summary,
    build_training_queries,
    build_training_seed_rows,
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
