from __future__ import annotations

import csv
from pathlib import Path


CITIES = [
    {"city": "москва", "region_code": 213},
    {"city": "санкт-петербург", "region_code": 2},
    {"city": "екатеринбург", "region_code": 54},
    {"city": "новосибирск", "region_code": 65},
    {"city": "казань", "region_code": 43},
    {"city": "краснодар", "region_code": 35},
    {"city": "самара", "region_code": 51},
    {"city": "нижний новгород", "region_code": 47},
]

CATEGORIES = [
    "ремонт квартир",
    "ремонт кухни",
    "ремонт ванной",
    "натяжные потолки",
    "пластиковые окна",
    "установка входных дверей",
    "кухни на заказ",
    "шкафы-купе на заказ",
    "создание сайта",
    "разработка интернет-магазина",
    "seo продвижение",
    "контекстная реклама",
    "бухгалтерские услуги",
    "юридические услуги",
    "банкротство физических лиц",
    "грузоперевозки",
    "аренда спецтехники",
    "вывоз мусора",
    "клининг офиса",
    "химчистка мебели",
    "установка кондиционеров",
    "бурение скважин",
    "строительство домов",
    "утепление фасада",
    "ремонт офисов",
]


def build_seed_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for category in CATEGORIES:
        for city in CITIES:
            rows.append(
                {
                    "query": f"{category} {city['city']}",
                    "category": category,
                    "intent": "commercial",
                    "city": city["city"],
                    "region_code": city["region_code"],
                    "top_n": 10,
                    "pages_to_scan": 1,
                }
            )
    return rows


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    backend_data_dir = project_root / "backend" / "data"
    backend_data_dir.mkdir(parents=True, exist_ok=True)

    seeds_path = backend_data_dir / "training_query_seeds.csv"
    legacy_queries_path = backend_data_dir / "training_queries.txt"
    rows = build_seed_rows()

    with seeds_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["query", "category", "intent", "city", "region_code", "top_n", "pages_to_scan"],
        )
        writer.writeheader()
        writer.writerows(rows)

    unique_queries = sorted({str(row["query"]) for row in rows})
    legacy_queries_path.write_text("\n".join(unique_queries) + "\n", encoding="utf-8")

    print(
        {
            "seeds_output_path": str(seeds_path),
            "legacy_queries_output_path": str(legacy_queries_path),
            "seed_rows_count": len(rows),
            "queries_count": len(unique_queries),
            "categories_count": len(CATEGORIES),
            "cities_count": len(CITIES),
        }
    )


if __name__ == "__main__":
    main()
