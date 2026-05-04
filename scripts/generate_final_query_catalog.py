from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Final


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_DIR = PROJECT_ROOT / "backend" / "data" / "query_relevance_v2"
CATALOG_PATH = CATALOG_DIR / "final_training_queries.csv"
MANIFEST_PATH = CATALOG_DIR / "manifest.json"
README_PATH = CATALOG_DIR / "README.md"
DATASET_DIR = PROJECT_ROOT / "backend" / "data" / "dataset_versions" / "dataset-v7-final"
SEEDS_PATH = DATASET_DIR / "seeds.csv"
DATASET_MANIFEST_PATH = DATASET_DIR / "manifest.json"

TOP_N: Final[int] = 10
PAGES_TO_SCAN: Final[int] = 1

FIELDS: Final[list[str]] = [
    "query",
    "category",
    "intent",
    "city",
    "region_code",
    "top_n",
    "pages_to_scan",
    "target_topic",
    "query_focus",
    "positive_page_pattern",
    "negative_page_traps",
]

CITIES: Final[list[tuple[str, int]]] = [
    ("Москва", 213),
    ("Санкт-Петербург", 2),
    ("Екатеринбург", 54),
    ("Казань", 43),
    ("Новосибирск", 65),
]

CATEGORY_SPECS: Final[list[dict[str, str]]] = [
    {"category": "veterinary_clinic", "entity": "ветеринарная клиника", "topic": "ветеринарные услуги для домашних животных", "negative": "зоомагазин без врачей; новости про животных; человеческая клиника"},
    {"category": "pet_grooming", "entity": "груминг собак", "topic": "груминг и уход за животными", "negative": "ветаптека; продажа кормов; статьи без записи к мастеру"},
    {"category": "private_school", "entity": "частная школа", "topic": "частное школьное образование", "negative": "курсы для взрослых; государственный портал; новости образования"},
    {"category": "kindergarten", "entity": "частный детский сад", "topic": "частные детские сады и дошкольное развитие", "negative": "игрушки; вакансии воспитателя; статья без сада"},
    {"category": "speech_therapy", "entity": "логопед для ребенка", "topic": "логопедические занятия для детей", "negative": "медицинский справочник; онлайн-курс для логопедов; детский магазин"},
    {"category": "psychologist", "entity": "психолог онлайн", "topic": "психологические консультации", "negative": "психологические тесты; книги; вакансии психолога"},
    {"category": "legal_translation", "entity": "юридический перевод документов", "topic": "перевод и заверение юридических документов", "negative": "бюро юристов без перевода; словарь терминов; курсы переводчиков"},
    {"category": "notary_services", "entity": "нотариус", "topic": "нотариальные услуги", "negative": "юридический блог; банковские услуги; вакансии нотариуса"},
    {"category": "migration_law", "entity": "миграционный юрист", "topic": "юридическая помощь по миграционным вопросам", "negative": "туристическое агентство; новости миграции; форум без услуги"},
    {"category": "tax_consulting", "entity": "налоговый консультант", "topic": "налоговые консультации для бизнеса и физлиц", "negative": "налоговый календарь; бухгалтерские курсы; новости ФНС"},
    {"category": "solar_panels", "entity": "солнечные панели для дома", "topic": "подбор и установка солнечных панелей", "negative": "научная статья; фонари на солнечных батареях; магазин кабеля"},
    {"category": "heat_pumps", "entity": "тепловой насос", "topic": "тепловые насосы для отопления", "negative": "насосы для воды; ремонт котлов; статья без оборудования"},
    {"category": "water_filters", "entity": "фильтр воды для дома", "topic": "фильтры и системы очистки воды", "negative": "доставка воды; анализ воды без фильтров; сантехника"},
    {"category": "smart_home", "entity": "умный дом", "topic": "проектирование и монтаж систем умного дома", "negative": "мобильные приложения; гаджеты без монтажа; новости технологий"},
    {"category": "security_systems", "entity": "охранная сигнализация", "topic": "охранные системы и сигнализация", "negative": "страхование; новости полиции; камеры для блогеров"},
    {"category": "video_surveillance", "entity": "видеонаблюдение для офиса", "topic": "системы видеонаблюдения", "negative": "экшн-камеры; видеомонтаж; статьи без установки"},
    {"category": "fire_safety", "entity": "пожарная сигнализация", "topic": "монтаж и обслуживание пожарной сигнализации", "negative": "огнетушители без проекта; новости МЧС; обучение пожарной безопасности"},
    {"category": "warehouse_racking", "entity": "стеллажи для склада", "topic": "складские стеллажи и хранение", "negative": "домашние полки; аренда склада; погрузчики"},
    {"category": "forklift_rental", "entity": "аренда вилочного погрузчика", "topic": "аренда складской техники", "negative": "продажа запчастей; обучение водителей; складская недвижимость"},
    {"category": "packaging_equipment", "entity": "упаковочное оборудование", "topic": "оборудование для упаковки продукции", "negative": "картонные коробки; дизайн упаковки; новости производства"},
    {"category": "coffee_machines", "entity": "кофемашина для офиса", "topic": "кофемашины и обслуживание для офиса", "negative": "кофейня; ремонт чайников; статьи о кофе"},
    {"category": "catering", "entity": "кейтеринг", "topic": "выездное питание и кейтеринг", "negative": "доставка еды на дом; рецепты; ресторан без выезда"},
    {"category": "banquet_hall", "entity": "банкетный зал", "topic": "аренда банкетных залов", "negative": "кейтеринг без площадки; мебель для ресторанов; афиша"},
    {"category": "event_agency", "entity": "организация мероприятий", "topic": "event-агентства и организация событий", "negative": "прокат оборудования только; блог идей; вакансии"},
    {"category": "photo_studio", "entity": "фотостудия", "topic": "аренда фотостудии и съемочные пространства", "negative": "фотограф без студии; магазин фотоаппаратов; обработка фото"},
    {"category": "wedding_photographer", "entity": "свадебный фотограф", "topic": "свадебная фотосъемка", "negative": "фотостудия без фотографа; свадебные платья; курсы фотографии"},
    {"category": "laser_cutting", "entity": "лазерная резка металла", "topic": "лазерная резка и обработка металла", "negative": "лазерная эпиляция; продажа лазеров; металлопрокат без резки"},
    {"category": "cnc_milling", "entity": "фрезеровка на чпу", "topic": "ЧПУ фрезеровка деталей", "negative": "продажа станков; обучение ЧПУ; 3D-печать без фрезеровки"},
    {"category": "metal_powder_coating", "entity": "порошковая покраска металла", "topic": "порошковая окраска изделий", "negative": "краска в банках; кузовной ремонт; статьи о покрытиях"},
    {"category": "industrial_flooring", "entity": "промышленные полы", "topic": "устройство промышленных полов", "negative": "ламинат для квартиры; уборка полов; наливные смеси без услуги"},
    {"category": "roof_repair", "entity": "ремонт кровли", "topic": "ремонт и монтаж кровли", "negative": "кровельные материалы без работ; ремонт квартир; новости ЖКХ"},
    {"category": "facade_insulation", "entity": "утепление фасада", "topic": "фасадные работы и утепление", "negative": "утеплитель оптом; интерьерная отделка; статья без подрядчика"},
    {"category": "landscape_design", "entity": "ландшафтный дизайн", "topic": "ландшафтное проектирование и благоустройство", "negative": "садовый магазин; дачные советы; продажа растений"},
    {"category": "tree_removal", "entity": "спил деревьев", "topic": "арбористика и удаление деревьев", "negative": "питомник растений; деревообработка; новости экологии"},
    {"category": "pool_installation", "entity": "строительство бассейна", "topic": "строительство и монтаж бассейнов", "negative": "абонемент в бассейн; надувные бассейны; очистка воды без строительства"},
    {"category": "sauna_construction", "entity": "строительство бани", "topic": "строительство бань и саун", "negative": "банный магазин; аренда сауны; статья о традициях"},
    {"category": "it_outsourcing", "entity": "ит аутсорсинг", "topic": "IT-аутсорсинг и поддержка бизнеса", "negative": "курсы IT; вакансии; магазин компьютеров"},
    {"category": "cybersecurity_audit", "entity": "аудит информационной безопасности", "topic": "кибербезопасность и аудит ИБ", "negative": "новости хакеров; антивирус для дома; курсы безопасности"},
    {"category": "crm_integration", "entity": "внедрение crm", "topic": "внедрение CRM-систем", "negative": "обзор CRM без внедрения; разработка сайта; обучение продажам"},
    {"category": "erp_consulting", "entity": "внедрение erp", "topic": "ERP-консалтинг и автоматизация", "negative": "бухгалтерская программа; вакансии консультанта; статьи без внедрения"},
    {"category": "hr_recruitment", "entity": "подбор персонала", "topic": "рекрутинг и подбор сотрудников", "negative": "доска вакансий; курсы HR; кадровый учет"},
    {"category": "corporate_training", "entity": "корпоративное обучение", "topic": "обучение сотрудников компаний", "negative": "школьные курсы; вакансии тренера; статьи без программы"},
    {"category": "medical_rehabilitation", "entity": "центр реабилитации", "topic": "медицинская реабилитация", "negative": "санаторий без реабилитации; фитнес-клуб; статья о здоровье"},
    {"category": "orthopedic_clinic", "entity": "ортопедическая клиника", "topic": "ортопедия и лечение суставов", "negative": "ортопедические товары; стоматология; форум пациентов"},
    {"category": "ophthalmology", "entity": "офтальмологическая клиника", "topic": "офтальмология и лечение зрения", "negative": "магазин очков; новости медицины; ветеринарный офтальмолог"},
    {"category": "dermatology", "entity": "дерматолог", "topic": "дерматологические услуги", "negative": "косметика; форум о коже; курсы косметолога"},
    {"category": "home_care", "entity": "сиделка для пожилого", "topic": "услуги сиделки и ухода", "negative": "дом престарелых без сиделок; медицинские статьи; вакансии сиделки"},
    {"category": "courier_service", "entity": "курьерская доставка", "topic": "курьерские службы для бизнеса", "negative": "доставка еды; вакансии курьера; почтовые новости"},
    {"category": "printing_house", "entity": "типография", "topic": "полиграфия и печать", "negative": "принтеры; дизайн-студия без печати; история печати"},
    {"category": "signage_production", "entity": "изготовление вывесок", "topic": "производство наружной рекламы и вывесок", "negative": "ремонт вывесок без изготовления; маркетинговый блог; LED-лампы"},
]

QUERY_TEMPLATES: Final[list[tuple[str, str, str]]] = [
    ("{entity} {city}", "commercial_local", "{entity} в городе {city}"),
    ("{entity} цена", "commercial", "стоимость: {entity}"),
    ("{entity} отзывы", "comparison", "отзывы и выбор: {entity}"),
    ("как выбрать {entity}", "informational", "выбор по критериям: {entity}"),
    ("{entity} с гарантией", "commercial", "гарантия и условия: {entity}"),
    ("{entity} для бизнеса", "commercial", "решение для бизнеса: {entity}"),
    ("{entity} под ключ", "commercial", "комплексная услуга: {entity}"),
    ("{entity} рядом", "commercial_local", "локальный поиск: {entity}"),
    ("{entity} консультация", "commercial", "консультация по теме: {entity}"),
    ("лучшие {entity}", "comparison", "сравнение вариантов: {entity}"),
]


def _city_for(index: int) -> tuple[str, int]:
    return CITIES[index % len(CITIES)]


def _build_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for category_index, spec in enumerate(CATEGORY_SPECS):
        city, region_code = _city_for(category_index)
        for template, intent, focus_template in QUERY_TEMPLATES:
            query = template.format(entity=spec["entity"], city=city).strip()
            query_focus = focus_template.format(entity=spec["entity"], city=city)
            row_city = city if intent.endswith("_local") else ""
            row_region_code: int | str = region_code if row_city else ""
            rows.append(
                {
                    "query": query,
                    "category": spec["category"],
                    "intent": intent.replace("_local", ""),
                    "city": row_city,
                    "region_code": row_region_code,
                    "top_n": TOP_N,
                    "pages_to_scan": PAGES_TO_SCAN,
                    "target_topic": spec["topic"],
                    "query_focus": query_focus,
                    "positive_page_pattern": (
                        f"страница именно про {spec['topic']} с понятным ответом на запрос, "
                        "условиями, доказательствами, контактами или подробным информационным раскрытием"
                    ),
                    "negative_page_traps": (
                        f"{spec['negative']}; страница с коммерческими словами без совпадения ядра запроса; "
                        "качественный сайт из другой тематики"
                    ),
                }
            )
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _manifest(rows: list[dict[str, object]]) -> dict[str, object]:
    cities = {str(row["city"]) for row in rows if str(row["city"]).strip()}
    categories = {str(row["category"]) for row in rows}
    return {
        "version": "query-relevance-v2-final",
        "dataset_version": "dataset-v7-final",
        "generated_at": datetime.now(UTC).isoformat(),
        "rows": len(rows),
        "unique_queries": len({str(row["query"]) for row in rows}),
        "categories": len(categories),
        "cities": sorted(cities),
        "city_count": len(cities),
        "top_n": TOP_N,
        "pages_to_scan": PAGES_TO_SCAN,
        "collection_policy": {
            "serp_depth": "top_10_full",
            "domain_dedupe": "domain_cap",
            "hard_negatives_required": True,
            "weak_serp_labels_allowed": False,
            "current_dataset_v6_is_draft_only": True,
        },
        "labeling_policy": {
            "label_source": "deterministic_expert_rubric",
            "target_formula": "query_relevance_multiplier * competitiveness_base_score",
            "full_mismatch_score_range": "0-15",
            "intent_modifiers_only_when_present_in_query": True,
        },
        "minimum_requirements": {
            "queries": 500,
            "categories": 50,
            "cities": 5,
            "top_n": 10,
        },
    }


def _write_readme(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Query relevance v2 final catalog",
                "",
                "This catalog is the seed source for `dataset-v7-final`.",
                "It intentionally supersedes the draft `query_relevance_v1` / `dataset-v6-query-relevance` evidence.",
                "",
                "- 500 unique queries.",
                "- 50 expanded categories.",
                "- Top-10 collection intent.",
                "- Multiple Russian cities.",
                "- Deterministic expert-rubric labels only; weak SERP labels are not final labels.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> None:
    rows = _build_rows()
    if len(rows) != 500:
        raise RuntimeError(f"Expected 500 final query rows, got {len(rows)}")
    if len({str(row["query"]) for row in rows}) != len(rows):
        raise RuntimeError("Final query catalog must contain unique queries")

    manifest = _manifest(rows)
    _write_csv(CATALOG_PATH, rows)
    _write_csv(SEEDS_PATH, rows)
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    DATASET_MANIFEST_PATH.write_text(
        json.dumps(
            {
                **manifest,
                "dataset_path": str(DATASET_DIR / "dataset.csv"),
                "seeds_path": str(SEEDS_PATH),
                "status": "ready_for_collection",
                "ready_for_training": False,
                "reason": "Final top-10 collection and expert labels must be generated before training.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_readme(README_PATH)
    print(json.dumps({"catalog": str(CATALOG_PATH), "rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
