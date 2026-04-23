from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path
from typing import Final


TRAINING_SEED_FIELDS: Final[list[str]] = [
    "query",
    "category",
    "intent",
    "city",
    "region_code",
    "top_n",
    "pages_to_scan",
]


@dataclass(frozen=True, slots=True)
class QueryCity:
    name: str
    region_code: int


@dataclass(frozen=True, slots=True)
class QueryCategory:
    phrase: str


@dataclass(frozen=True, slots=True)
class QueryPattern:
    template: str
    intent: str
    uses_city: bool = True


RU_COMMERCIAL_CITIES: Final[tuple[QueryCity, ...]] = (
    QueryCity(name="Москва", region_code=213),
    QueryCity(name="Санкт-Петербург", region_code=2),
    QueryCity(name="Екатеринбург", region_code=54),
    QueryCity(name="Новосибирск", region_code=65),
    QueryCity(name="Казань", region_code=43),
    QueryCity(name="Краснодар", region_code=35),
    QueryCity(name="Самара", region_code=51),
    QueryCity(name="Нижний Новгород", region_code=47),
)


RU_COMMERCIAL_CATEGORIES: Final[tuple[QueryCategory, ...]] = (
    QueryCategory(phrase="натяжные потолки"),
    QueryCategory(phrase="пластиковые окна"),
    QueryCategory(phrase="входные двери"),
    QueryCategory(phrase="кухни на заказ"),
    QueryCategory(phrase="шкафы-купе"),
    QueryCategory(phrase="ремонт квартир"),
    QueryCategory(phrase="дизайн интерьера"),
    QueryCategory(phrase="стоматология имплантация"),
    QueryCategory(phrase="стоматология брекеты"),
    QueryCategory(phrase="банкротство физических лиц"),
    QueryCategory(phrase="юридические услуги"),
    QueryCategory(phrase="бухгалтерские услуги"),
    QueryCategory(phrase="ведение бухгалтерии"),
    QueryCategory(phrase="грузоперевозки"),
    QueryCategory(phrase="эвакуатор"),
    QueryCategory(phrase="уборка квартир"),
    QueryCategory(phrase="химчистка диванов"),
    QueryCategory(phrase="установка кондиционеров"),
    QueryCategory(phrase="ремонт ноутбуков"),
    QueryCategory(phrase="создание сайтов"),
    QueryCategory(phrase="разработка интернет-магазина"),
    QueryCategory(phrase="seo продвижение"),
    QueryCategory(phrase="контекстная реклама"),
    QueryCategory(phrase="лазерная эпиляция"),
    QueryCategory(phrase="автосервис"),
)


DATASET_V2_QUERY_PATTERNS: Final[tuple[QueryPattern, ...]] = (
    QueryPattern(template="{category} {city}", intent="commercial", uses_city=True),
    QueryPattern(template="{category} цена {city}", intent="commercial", uses_city=True),
    QueryPattern(template="как выбрать {category}", intent="informational", uses_city=False),
    QueryPattern(template="{category} отзывы", intent="informational", uses_city=False),
)


def build_training_seed_rows(
    top_n: int = 10,
    pages_to_scan: int = 1,
) -> list[dict[str, object]]:
    normalized_top_n = max(1, top_n)
    normalized_pages_to_scan = max(1, pages_to_scan)
    return [
        {
            "query": f"{category.phrase} {city.name}",
            "category": category.phrase,
            "intent": "commercial",
            "city": city.name,
            "region_code": city.region_code,
            "top_n": normalized_top_n,
            "pages_to_scan": normalized_pages_to_scan,
        }
        for category in RU_COMMERCIAL_CATEGORIES
        for city in RU_COMMERCIAL_CITIES
    ]


def build_dataset_v2_seed_rows(
    top_n: int = 10,
    pages_to_scan: int = 2,
) -> list[dict[str, object]]:
    normalized_top_n = max(1, top_n)
    normalized_pages_to_scan = max(1, pages_to_scan)
    rows: list[dict[str, object]] = []
    for category in RU_COMMERCIAL_CATEGORIES:
        for pattern in DATASET_V2_QUERY_PATTERNS:
            if pattern.uses_city:
                for city in RU_COMMERCIAL_CITIES:
                    rows.append(
                        {
                            "query": pattern.template.format(category=category.phrase, city=city.name),
                            "category": category.phrase,
                            "intent": pattern.intent,
                            "city": city.name,
                            "region_code": city.region_code,
                            "top_n": normalized_top_n,
                            "pages_to_scan": normalized_pages_to_scan,
                        }
                    )
            else:
                rows.append(
                    {
                        "query": pattern.template.format(category=category.phrase, city=""),
                        "category": category.phrase,
                        "intent": pattern.intent,
                        "city": "",
                        "region_code": "",
                        "top_n": normalized_top_n,
                        "pages_to_scan": normalized_pages_to_scan,
                    }
                )
    return rows


def build_training_queries(seed_rows: list[dict[str, object]] | None = None) -> list[str]:
    rows = seed_rows or build_training_seed_rows()
    return list(dict.fromkeys(str(row["query"]) for row in rows))


def build_seed_catalog_summary(seed_rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    rows = seed_rows or build_training_seed_rows()
    return {
        "seed_rows_count": len(rows),
        "queries_count": len(build_training_queries(rows)),
        "categories_count": len(RU_COMMERCIAL_CATEGORIES),
        "cities_count": len(RU_COMMERCIAL_CITIES),
        "categories": [category.phrase for category in RU_COMMERCIAL_CATEGORIES],
        "cities": [city.name for city in RU_COMMERCIAL_CITIES],
    }


def build_dataset_v2_seed_summary(seed_rows: list[dict[str, object]] | None = None) -> dict[str, object]:
    rows = seed_rows or build_dataset_v2_seed_rows()
    return {
        "seed_rows_count": len(rows),
        "queries_count": len(build_training_queries(rows)),
        "categories_count": len(RU_COMMERCIAL_CATEGORIES),
        "cities_count": len(RU_COMMERCIAL_CITIES),
        "intent_count": len({str(row["intent"]) for row in rows}),
        "intents": sorted({str(row["intent"]) for row in rows}),
        "query_patterns_count": len(DATASET_V2_QUERY_PATTERNS),
        "target_query_range": "300-500",
    }


def save_seed_rows(path: str | Path, rows: list[dict[str, object]]) -> Path:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=TRAINING_SEED_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return resolved_path
