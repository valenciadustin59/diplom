from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.query_relevance import (
    QUERY_RELEVANCE_GUARDRAIL_VERSION,
    build_query_relevance_guardrail,
    build_query_relevance_preflight_decision,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TASK_ID = "D84"
D84_REGRESSION_VERSION = "d84-live-relevance-regression-v1"
DEFAULT_CASES_PATH = PROJECT_ROOT / "backend" / "data" / "query_relevance_regression" / "d84-live-regression-cases.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "backend" / "artifacts" / "ranking-benchmarks" / "dataset-v7-final-d84"
DEFAULT_REPORT_JSON_PATH = DEFAULT_OUTPUT_DIR / "d84-live-relevance-regression-report.json"
DEFAULT_REPORT_MD_PATH = DEFAULT_OUTPUT_DIR / "d84-live-relevance-regression-report.md"


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _base_features(**overrides: float | int) -> dict[str, float | int]:
    features: dict[str, float | int] = {
        "http_status_code": 200,
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "word_count": 900,
        "text_length_chars": 5600,
        "semantic_similarity": 0.32,
        "keyword_coverage_ratio": 0.8,
        "query_core_keyword_coverage_ratio": 1.0,
        "query_intent_modifier_coverage_ratio": 0.0,
        "query_density": 0.006,
        "query_core_term_count": 8,
        "exact_query_count": 0,
        "query_in_title": 0,
        "query_in_text": 1,
        "title_semantic_alignment": 0.62,
        "heading_semantic_alignment": 0.68,
        "query_prominence_score": 0.58,
    }
    features.update(overrides)
    return features


def _case(
    *,
    case_id: str,
    group: str,
    query: str,
    page_hint: str,
    base_score: float,
    features: dict[str, float | int],
    expectation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": case_id,
        "group": group,
        "query": query,
        "page_hint": page_hint,
        "base_score": base_score,
        "features": features,
        "expectation": expectation,
    }


def build_d84_relevance_regression_cases() -> list[dict[str, Any]]:
    strong_topics = [
        ("d84-strong-01", "аренда фотостудии екатеринбург", "лендинг фотостудии с залами, адресом и примерами"),
        ("d84-strong-02", "ремонт электросамокатов казань", "страница сервиса по диагностике и ремонту самокатов"),
        ("d84-strong-03", "мрт коленного сустава спб", "страница клиники про МРТ колена и запись на исследование"),
        ("d84-strong-04", "муфельная печь лабораторная", "категория лабораторных муфельных печей"),
        ("d84-strong-05", "семена газонной травы для тени", "каталог семян газона для теневых участков"),
        ("d84-strong-06", "техосмотр грузовых автомобилей", "услуга техосмотра грузовиков"),
        ("d84-strong-07", "замена стеклопакета в окне", "страница мастера по замене стеклопакетов"),
        ("d84-strong-08", "наливной пол для гаража", "материал и услуга по наливным полам в гараже"),
        ("d84-strong-09", "обслуживание кофемашин офис", "сервисное обслуживание офисных кофемашин"),
        ("d84-strong-10", "ветеринарная клиника для кошек", "ветклиника с услугами для кошек"),
    ]
    strong_commercial_without_modifier = [
        (
            "d84-commercial-01",
            "купить компрессор для аквариума",
            "категория аквариумных компрессоров без слова купить в тексте",
        ),
        ("d84-commercial-02", "цена химчистки дивана", "страница услуги химчистки диванов без явного прайса"),
        ("d84-commercial-03", "заказать поверку счетчиков воды", "услуга поверки счетчиков без слова заказать"),
        ("d84-commercial-04", "купить термопанели фасадные", "каталог фасадных термопанелей без buy-CTA"),
        ("d84-commercial-05", "стоимость бурения скважины", "страница бурения скважин с описанием этапов"),
    ]
    full_mismatches = [
        ("d84-mismatch-01", "монтаж солнечных панелей", "курсы японского языка для взрослых"),
        ("d84-mismatch-02", "купить детский батут", "магазин крафтового шоколада"),
        ("d84-mismatch-03", "доставка бетона миксером", "афиша джазовых концертов"),
        ("d84-mismatch-04", "как выбрать ирригатор", "блог о выращивании базилика"),
        ("d84-mismatch-05", "аренда катка для мероприятия", "страница аренды катеров"),
        ("d84-mismatch-06", "лечение варикоза лазером", "подбор онлайн-курсов дизайна"),
        ("d84-mismatch-07", "купить офисное кресло", "каталог свадебных платьев"),
        ("d84-mismatch-08", "ремонт холодильников на дому", "магазин туристических палаток"),
        ("d84-mismatch-09", "детский логопед новосибирск", "расписание йога-студии"),
        ("d84-mismatch-10", "штукатурка стен механизированная", "страница доставки роллов"),
    ]
    near_topic_wrong = [
        ("d84-near-01", "аренда фотостудии екатеринбург", "аренда конференц-зала без фотозон и света"),
        ("d84-near-02", "ремонт электросамокатов казань", "магазин велосипедов без ремонта самокатов"),
        ("d84-near-03", "мрт коленного сустава спб", "общая статья про боль в колене без МРТ"),
        ("d84-near-04", "муфельная печь лабораторная", "каталог кухонных духовых шкафов"),
        ("d84-near-05", "семена газонной травы для тени", "ландшафтный дизайн без семян"),
        ("d84-near-06", "техосмотр грузовых автомобилей", "страхование легковых автомобилей"),
        ("d84-near-07", "замена стеклопакета в окне", "установка межкомнатных дверей"),
        ("d84-near-08", "обслуживание кофемашин офис", "продажа кофе в зернах без сервиса"),
    ]
    partial_matches = [
        ("d84-partial-01", "ветеринарная клиника для кошек", "общая ветклиника без отдельного кошачьего направления"),
        ("d84-partial-02", "наливной пол для гаража", "страница наливных полов без гаражного применения"),
        ("d84-partial-03", "семена газонной травы для тени", "каталог газонной травы без теневых смесей"),
        ("d84-partial-04", "мрт коленного сустава спб", "страница МРТ без привязки к коленному суставу и городу"),
        ("d84-partial-05", "замена стеклопакета в окне", "ремонт окон без отдельной услуги стеклопакета"),
    ]
    unusable_pages = [
        ("d84-unusable-01", "ремонт электросамокатов казань", "404 страница сервиса"),
        ("d84-unusable-02", "аренда фотостудии екатеринбург", "noindex страница с пустым контентом"),
    ]

    cases: list[dict[str, Any]] = []
    for case_id, query, page_hint in strong_topics:
        cases.append(
            _case(
                case_id=case_id,
                group="strong_match",
                query=query,
                page_hint=page_hint,
                base_score=82.0,
                features=_base_features(),
                expectation={"active": False, "early_stop": False, "score_min": 82.0, "score_max": 82.0, "bands": [None]},
            )
        )

    for case_id, query, page_hint in strong_commercial_without_modifier:
        cases.append(
            _case(
                case_id=case_id,
                group="commercial_modifier_not_required_when_core_matches",
                query=query,
                page_hint=page_hint,
                base_score=84.0,
                features=_base_features(keyword_coverage_ratio=0.75, query_intent_modifier_coverage_ratio=0.0),
                expectation={"active": False, "early_stop": False, "score_min": 84.0, "score_max": 84.0, "bands": [None]},
            )
        )

    for case_id, query, page_hint in full_mismatches:
        cases.append(
            _case(
                case_id=case_id,
                group="full_mismatch",
                query=query,
                page_hint=page_hint,
                base_score=91.0,
                features=_base_features(
                    semantic_similarity=0.08,
                    keyword_coverage_ratio=0.0,
                    query_core_keyword_coverage_ratio=0.0,
                    query_intent_modifier_coverage_ratio=1.0 if any(word in query for word in ("купить", "цена", "стоимость", "заказать")) else 0.0,
                    query_density=0.0,
                    query_core_term_count=0,
                    exact_query_count=0,
                    query_in_title=0,
                    query_in_text=0,
                    title_semantic_alignment=0.0,
                    heading_semantic_alignment=0.0,
                    query_prominence_score=0.0,
                ),
                expectation={"active": True, "early_stop": True, "score_min": 0.0, "score_max": 5.0, "bands": ["full_mismatch"]},
            )
        )

    for case_id, query, page_hint in near_topic_wrong:
        cases.append(
            _case(
                case_id=case_id,
                group="near_topic_wrong_object",
                query=query,
                page_hint=page_hint,
                base_score=86.0,
                features=_base_features(
                    semantic_similarity=0.31,
                    keyword_coverage_ratio=0.333333,
                    query_core_keyword_coverage_ratio=0.25,
                    query_density=0.001,
                    query_core_term_count=1,
                    exact_query_count=0,
                    query_in_title=0,
                    query_in_text=1,
                    title_semantic_alignment=0.0,
                    heading_semantic_alignment=0.0,
                    query_prominence_score=0.12,
                ),
                expectation={"active": True, "early_stop": False, "score_min": 0.0, "score_max": 55.0, "bands": ["probable_mismatch", "weak_match"]},
            )
        )

    for case_id, query, page_hint in partial_matches:
        cases.append(
            _case(
                case_id=case_id,
                group="partial_match",
                query=query,
                page_hint=page_hint,
                base_score=88.0,
                features=_base_features(
                    semantic_similarity=0.5,
                    keyword_coverage_ratio=0.65,
                    query_core_keyword_coverage_ratio=0.65,
                    query_density=0.0033,
                    query_core_term_count=3,
                    exact_query_count=0,
                    query_in_title=0,
                    query_in_text=0,
                    title_semantic_alignment=0.18,
                    heading_semantic_alignment=0.2,
                    query_prominence_score=0.28,
                ),
                expectation={"active": True, "early_stop": False, "score_min": 55.0, "score_max": 80.0, "bands": ["partial_match"]},
            )
        )

    for case_id, query, page_hint in unusable_pages:
        cases.append(
            _case(
                case_id=case_id,
                group="unusable",
                query=query,
                page_hint=page_hint,
                base_score=79.0,
                features=_base_features(
                    http_status_code=404,
                    http_status_ok=0,
                    page_indexable=0,
                    robots_noindex=1,
                    word_count=0,
                    text_length_chars=0,
                    semantic_similarity=0.0,
                    keyword_coverage_ratio=0.0,
                    query_core_keyword_coverage_ratio=0.0,
                    query_density=0.0,
                    query_core_term_count=0,
                    query_in_text=0,
                    title_semantic_alignment=0.0,
                    heading_semantic_alignment=0.0,
                    query_prominence_score=0.0,
                ),
                expectation={"active": True, "early_stop": False, "score_min": 0.0, "score_max": 10.0, "bands": ["unusable"]},
            )
        )

    return cases


def _check_case(case: dict[str, Any]) -> dict[str, Any]:
    base_score = float(case["base_score"])
    features = case["features"]
    expectation = case["expectation"]
    preflight = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, base_score)
    adjusted_score = float(guardrail["adjusted_score"])
    failures: list[str] = []

    if bool(guardrail["active"]) != bool(expectation["active"]):
        failures.append("active_state")
    if bool(guardrail["early_stop"]) != bool(expectation["early_stop"]):
        failures.append("early_stop_state")
    if adjusted_score < float(expectation["score_min"]) or adjusted_score > float(expectation["score_max"]):
        failures.append("score_band")
    expected_bands = expectation.get("bands")
    if isinstance(expected_bands, list) and guardrail.get("band") not in expected_bands:
        failures.append("relevance_band")

    return {
        "id": case["id"],
        "group": case["group"],
        "query": case["query"],
        "page_hint": case["page_hint"],
        "status": "pass" if not failures else "fail",
        "failed_checks": failures,
        "base_score": base_score,
        "adjusted_score": adjusted_score,
        "guardrail_band": guardrail.get("band"),
        "guardrail_reason": guardrail.get("reason"),
        "guardrail_active": guardrail.get("active"),
        "early_stop": guardrail.get("early_stop"),
        "preflight_decision": preflight.get("decision"),
        "preflight_reason": preflight.get("reason"),
        "metrics": guardrail.get("metrics"),
    }


def run_d84_live_relevance_regression(
    *,
    cases_path: Path = DEFAULT_CASES_PATH,
    report_path: Path = DEFAULT_REPORT_JSON_PATH,
    markdown_path: Path = DEFAULT_REPORT_MD_PATH,
) -> dict[str, Any]:
    cases = build_d84_relevance_regression_cases()
    results = [_check_case(case) for case in cases]
    failed_cases = [result for result in results if result["status"] != "pass"]
    groups = sorted({case["group"] for case in cases})
    group_counts = {
        group: {
            "total": sum(1 for result in results if result["group"] == group),
            "failed": sum(1 for result in results if result["group"] == group and result["status"] != "pass"),
        }
        for group in groups
    }
    report: dict[str, Any] = {
        "task": TASK_ID,
        "version": D84_REGRESSION_VERSION,
        "query_relevance_guardrail_version": QUERY_RELEVANCE_GUARDRAIL_VERSION,
        "status": "passed" if not failed_cases else "failed",
        "cases_count": len(cases),
        "groups_count": len(groups),
        "group_counts": group_counts,
        "failed_cases_count": len(failed_cases),
        "failed_cases": failed_cases,
        "results": results,
        "cases_path": _display_path(cases_path),
        "recommendation": (
            "D84 regression pack passed; keep adding live bug cases here before changing relevance thresholds."
            if not failed_cases
            else "Review failed cases before changing runtime thresholds or publishing a new model."
        ),
    }

    cases_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    cases_path.write_text(
        json.dumps(
            {
                "task": TASK_ID,
                "version": D84_REGRESSION_VERSION,
                "cases_count": len(cases),
                "cases": cases,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_render_markdown_report(report), encoding="utf-8")
    return report


def _render_markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# D84 Live Relevance Regression Pack",
        "",
        f"- Status: `{report['status']}`",
        f"- Cases: `{report['cases_count']}`",
        f"- Guardrail: `{report['query_relevance_guardrail_version']}`",
        f"- Failed cases: `{report['failed_cases_count']}`",
        "",
        "## Groups",
        "",
    ]
    for group, counts in report["group_counts"].items():
        lines.append(f"- `{group}`: `{counts['total']}` cases, `{counts['failed']}` failed")
    lines.extend(["", "## Decision", "", str(report["recommendation"]), ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run D84 query relevance regression pack.")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_JSON_PATH)
    parser.add_argument("--markdown-path", type=Path, default=DEFAULT_REPORT_MD_PATH)
    args = parser.parse_args()
    report = run_d84_live_relevance_regression(
        cases_path=args.cases_path,
        report_path=args.report_path,
        markdown_path=args.markdown_path,
    )
    print(json.dumps({"status": report["status"], "cases_count": report["cases_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
