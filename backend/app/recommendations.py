from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.ml import average_score


RecommendationPriority = Literal["high", "medium", "low"]
RecommendationGroupKey = Literal[
    "technical_seo",
    "commercial_trust",
    "semantic_intent",
    "competitor_gap",
]
DeviationTrend = Literal["behind", "ahead", "aligned"]


PRIORITY_ORDER: dict[RecommendationPriority, int] = {"high": 0, "medium": 1, "low": 2}
MIN_COMPETITORS_FOR_RECOMMENDATIONS = 2
RECOMMENDATIONS_SCHEMA_VERSION = "recommendations-v2"

TECHNICAL_FEATURE_KEYS = {
    "page_indexable",
    "canonical_present",
    "canonical_matches_final_url",
    "redirect_count",
    "viewport_present",
    "lang_present",
    "hreflang_present",
    "url_has_query_parameters",
    "url_depth",
}
COMMERCIAL_TRUST_FEATURE_KEYS = {
    "phone_present",
    "email_present",
    "address_present",
    "business_hours_present",
    "price_present",
    "delivery_info_present",
    "payment_info_present",
    "reviews_present",
    "rating_present",
    "faq_present",
    "cta_present",
    "messenger_present",
    "value_proposition_present",
    "legal_requisites_present",
    "company_identity_present",
    "contact_options_score",
    "commercial_signals_score",
    "trust_signals_score",
}
INTENT_ALIGNMENT_FEATURE_KEYS = {
    "intent_is_commercial",
    "intent_is_local_commercial",
    "intent_is_informational",
    "intent_is_navigational",
    "intent_alignment_score",
    "commercial_intent_alignment",
    "local_intent_alignment",
    "informational_intent_alignment",
    "navigational_intent_alignment",
}
SERP_RELATIVE_FEATURE_KEYS = {
    "serp_relative_context_available",
    "serp_relative_percentile",
    "serp_relative_gap_score",
    "relative_gap_to_top_semantic_relevance",
    "relative_gap_to_top_technical_seo",
    "relative_gap_to_top_commercial_trust",
    "relative_gap_to_top_intent_alignment",
}


@dataclass(frozen=True)
class RecommendationTemplate:
    group: RecommendationGroupKey
    title: str
    metrics: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecommendationDraft:
    code: str
    priority: RecommendationPriority
    message: str


@dataclass(frozen=True)
class MetricSpec:
    label: str
    unit: str
    direction: Literal["higher_is_better", "lower_is_better"]
    tolerance: float = 0.05
    minimum_scale: float = 1.0
    target_value: float | None = None
    benchmark_label: str | None = None


GROUP_ORDER: tuple[RecommendationGroupKey, ...] = (
    "technical_seo",
    "commercial_trust",
    "semantic_intent",
    "competitor_gap",
)
GROUP_METADATA: dict[RecommendationGroupKey, dict[str, str]] = {
    "technical_seo": {
        "label": "Technical SEO",
        "description": "Индексация, canonical, URL hygiene и другие технические сигналы ранжируемой страницы.",
    },
    "commercial_trust": {
        "label": "Commercial and Trust",
        "description": "Контакты, офферы, CTA, социальное доказательство и сигналы доверия к бизнесу.",
    },
    "semantic_intent": {
        "label": "Semantic and Intent",
        "description": "Насколько структура и контент страницы совпадают с запросом и поисковым интентом.",
    },
    "competitor_gap": {
        "label": "Competitor Gap",
        "description": "Где страница уступает конкурентам и лидерам SERP по совокупности ключевых факторов.",
    },
}
GROUP_EMPTY_MESSAGES: dict[RecommendationGroupKey, str] = {
    "technical_seo": "Критичных технических просадок в этом блоке не обнаружено.",
    "commercial_trust": "Коммерческий и trust-профиль выглядит достаточно конкурентным.",
    "semantic_intent": "Семантический и интентный профиль не показывает явных слабых мест.",
    "competitor_gap": "Существенных отставаний от SERP-лидеров по главным группам сигналов не выявлено.",
}
IMPACT_LABELS: dict[RecommendationPriority, str] = {
    "high": "Исправление может заметно поднять итоговый score и сократить отставание от SERP-лидеров.",
    "medium": "Исправление даст ощутимое улучшение релевантности и конкурентоспособности страницы.",
    "low": "Исправление носит точечный характер, но помогает дожать качество страницы относительно выдачи.",
}

RECOMMENDATION_TEMPLATES: dict[str, RecommendationTemplate] = {
    "LOW_PAGE_SCORE": RecommendationTemplate("competitor_gap", "Низкий общий score", ("page_score",)),
    "BELOW_COMPETITORS": RecommendationTemplate(
        "competitor_gap",
        "Страница заметно слабее конкурентов",
        ("page_score", "competitors_average_score"),
    ),
    "SLIGHTLY_BELOW_COMPETITORS": RecommendationTemplate(
        "competitor_gap",
        "Страница немного уступает конкурентам",
        ("page_score", "competitors_average_score"),
    ),
    "MISSING_TITLE": RecommendationTemplate("semantic_intent", "Отсутствует title", ("title_present",)),
    "QUERY_NOT_IN_TITLE": RecommendationTemplate(
        "semantic_intent",
        "Запрос не отражён в title",
        ("query_in_title",),
    ),
    "MISSING_META_DESCRIPTION": RecommendationTemplate(
        "technical_seo",
        "Отсутствует meta description",
        ("meta_description_present",),
    ),
    "MISSING_H1": RecommendationTemplate("semantic_intent", "Отсутствует H1", ("h1_count",)),
    "MULTIPLE_H1": RecommendationTemplate("semantic_intent", "На странице несколько H1", ("h1_count",)),
    "QUERY_NOT_IN_TEXT": RecommendationTemplate(
        "semantic_intent",
        "Запрос не покрыт в основном тексте",
        ("query_in_text",),
    ),
    "LOW_KEYWORD_COVERAGE": RecommendationTemplate(
        "semantic_intent",
        "Тема запроса раскрыта неполно",
        ("keyword_coverage_ratio",),
    ),
    "LOW_SEMANTIC_RELEVANCE": RecommendationTemplate(
        "semantic_intent",
        "Низкая семантическая релевантность",
        ("semantic_similarity",),
    ),
    "THIN_CONTENT": RecommendationTemplate(
        "semantic_intent",
        "Недостаточный объём основного контента",
        ("text_length_chars",),
    ),
    "CONTENT_SHORTER_THAN_COMPETITORS": RecommendationTemplate(
        "semantic_intent",
        "Контент короче, чем у конкурентов",
        ("text_length_chars",),
    ),
    "LOW_TEXT_TO_HTML_RATIO": RecommendationTemplate(
        "semantic_intent",
        "Мало полезного текста относительно HTML",
        ("text_to_html_ratio",),
    ),
    "FEW_LINKS": RecommendationTemplate("semantic_intent", "Мало полезных ссылок", ("link_count",)),
    "NO_IMAGES": RecommendationTemplate("semantic_intent", "Не хватает визуальных элементов", ("image_count",)),
    "NO_CONVERSION_ELEMENT": RecommendationTemplate(
        "commercial_trust",
        "Нет явного конверсионного элемента",
        ("form_count", "cta_present"),
    ),
    "TECHNICAL_INDEXING_BLOCK": RecommendationTemplate(
        "technical_seo",
        "Есть блокирующая проблема индексации",
        ("page_indexable", "robots_noindex", "http_status_ok"),
    ),
    "TECHNICAL_CANONICAL_MISMATCH": RecommendationTemplate(
        "technical_seo",
        "Canonical указывает не на ранжируемый URL",
        ("canonical_present", "canonical_matches_final_url"),
    ),
    "TECHNICAL_MISSING_CANONICAL": RecommendationTemplate(
        "technical_seo",
        "Не задан canonical",
        ("canonical_present", "url_has_query_parameters"),
    ),
    "TECHNICAL_REDIRECT_CHAIN": RecommendationTemplate(
        "technical_seo",
        "Слишком длинная redirect chain",
        ("redirect_count",),
    ),
    "TECHNICAL_REDIRECTED_TARGET": RecommendationTemplate(
        "technical_seo",
        "Продвигаемый URL редиректит",
        ("redirect_count",),
    ),
    "TECHNICAL_MISSING_VIEWPORT": RecommendationTemplate(
        "technical_seo",
        "Нет mobile viewport",
        ("viewport_present",),
    ),
    "TECHNICAL_MISSING_LANG": RecommendationTemplate(
        "technical_seo",
        "Не указан язык документа",
        ("lang_present",),
    ),
    "TECHNICAL_QUERY_PARAMETERS_IN_URL": RecommendationTemplate(
        "technical_seo",
        "Продвигаемый URL содержит query-параметры",
        ("url_has_query_parameters", "url_parameter_count"),
    ),
    "TECHNICAL_DEEP_URL": RecommendationTemplate(
        "technical_seo",
        "URL слишком глубоко вложен",
        ("url_depth",),
    ),
    "TECHNICAL_MISSING_HREFLANG": RecommendationTemplate(
        "technical_seo",
        "Не хватает hreflang-разметки",
        ("hreflang_present",),
    ),
    "COMMERCIAL_MISSING_PHONE": RecommendationTemplate(
        "commercial_trust",
        "Нет прямого контактного канала",
        ("phone_present", "contact_options_score"),
    ),
    "COMMERCIAL_MISSING_ADDRESS": RecommendationTemplate(
        "commercial_trust",
        "Не показан адрес или геопривязка",
        ("address_present", "trust_signals_score"),
    ),
    "COMMERCIAL_MISSING_BUSINESS_HOURS": RecommendationTemplate(
        "commercial_trust",
        "Не указан режим работы",
        ("business_hours_present",),
    ),
    "COMMERCIAL_MISSING_PRICE_SIGNAL": RecommendationTemplate(
        "commercial_trust",
        "Нет ценового ориентира",
        ("price_present",),
    ),
    "COMMERCIAL_MISSING_DELIVERY_INFO": RecommendationTemplate(
        "commercial_trust",
        "Не раскрыты условия доставки или оказания услуги",
        ("delivery_info_present",),
    ),
    "COMMERCIAL_MISSING_PAYMENT_INFO": RecommendationTemplate(
        "commercial_trust",
        "Не раскрыты способы оплаты",
        ("payment_info_present",),
    ),
    "COMMERCIAL_WEAK_CTA": RecommendationTemplate(
        "commercial_trust",
        "CTA-блок недостаточно выражен",
        ("cta_present", "form_count"),
    ),
    "COMMERCIAL_NO_MESSENGERS": RecommendationTemplate(
        "commercial_trust",
        "Не хватает мессенджеров как канала связи",
        ("messenger_present",),
    ),
    "COMMERCIAL_WEAK_VALUE_PROPOSITION": RecommendationTemplate(
        "commercial_trust",
        "Слабо сформулировано ценностное предложение",
        ("value_proposition_present",),
    ),
    "TRUST_WEAK_CONTACT_BLOCK": RecommendationTemplate(
        "commercial_trust",
        "Слабый contact-блок",
        ("contact_options_score", "trust_signals_score"),
    ),
    "TRUST_MISSING_BUSINESS_ID": RecommendationTemplate(
        "commercial_trust",
        "Не хватает business identity signals",
        ("legal_requisites_present", "company_identity_present"),
    ),
    "TRUST_MISSING_SOCIAL_PROOF": RecommendationTemplate(
        "commercial_trust",
        "Нет social proof на странице",
        ("reviews_present", "rating_present"),
    ),
    "TRUST_MISSING_POST_SALE_INFO": RecommendationTemplate(
        "commercial_trust",
        "Нет постпродажных гарантий",
        ("warranty_info_present", "returns_info_present"),
    ),
    "INTENT_WEAK_LOCAL_ALIGNMENT": RecommendationTemplate(
        "semantic_intent",
        "Слабое соответствие локально-коммерческому интенту",
        ("local_intent_alignment",),
    ),
    "INTENT_WEAK_COMMERCIAL_ALIGNMENT": RecommendationTemplate(
        "semantic_intent",
        "Слабое соответствие коммерческому интенту",
        ("commercial_intent_alignment",),
    ),
    "INTENT_WEAK_INFORMATIONAL_ALIGNMENT": RecommendationTemplate(
        "semantic_intent",
        "Слабое соответствие информационному интенту",
        ("informational_intent_alignment",),
    ),
    "RELATIVE_SERP_GAP": RecommendationTemplate(
        "competitor_gap",
        "Есть заметный интегральный разрыв с SERP",
        ("serp_relative_gap_score", "serp_relative_percentile"),
    ),
    "RELATIVE_SEMANTIC_GAP": RecommendationTemplate(
        "competitor_gap",
        "Семантическая релевантность слабее топа",
        ("relative_gap_to_top_semantic_relevance",),
    ),
    "RELATIVE_TECHNICAL_GAP": RecommendationTemplate(
        "competitor_gap",
        "Технический профиль слабее топа",
        ("relative_gap_to_top_technical_seo",),
    ),
    "RELATIVE_COMMERCIAL_TRUST_GAP": RecommendationTemplate(
        "competitor_gap",
        "Коммерческий и trust-профиль слабее топа",
        ("relative_gap_to_top_commercial_trust",),
    ),
    "RELATIVE_INTENT_ALIGNMENT_GAP": RecommendationTemplate(
        "competitor_gap",
        "Совпадение с интентом слабее топа",
        ("relative_gap_to_top_intent_alignment",),
    ),
    "NO_CRITICAL_ISSUES": RecommendationTemplate("competitor_gap", "Критичных проблем не найдено", ("page_score",)),
}

METRIC_SPECS: dict[str, MetricSpec] = {
    "title_present": MetricSpec("Title", "binary", "higher_is_better"),
    "query_in_title": MetricSpec("Запрос в title", "binary", "higher_is_better"),
    "meta_description_present": MetricSpec("Meta description", "binary", "higher_is_better"),
    "h1_count": MetricSpec("Количество H1", "count", "lower_is_better", tolerance=0.2),
    "query_in_text": MetricSpec("Запрос в тексте", "binary", "higher_is_better"),
    "keyword_coverage_ratio": MetricSpec("Покрытие слов запроса", "ratio", "higher_is_better", tolerance=0.08),
    "semantic_similarity": MetricSpec("Семантическая релевантность", "score", "higher_is_better", tolerance=0.08),
    "text_length_chars": MetricSpec("Объём текста", "chars", "higher_is_better", tolerance=120.0, minimum_scale=500.0),
    "text_to_html_ratio": MetricSpec("Доля текста в HTML", "ratio", "higher_is_better", tolerance=0.03),
    "link_count": MetricSpec("Количество ссылок", "count", "higher_is_better", tolerance=1.0),
    "image_count": MetricSpec("Количество изображений", "count", "higher_is_better", tolerance=1.0),
    "form_count": MetricSpec("Формы и конверсионные элементы", "count", "higher_is_better", tolerance=0.5),
    "page_indexable": MetricSpec("Индексируемость страницы", "binary", "higher_is_better", tolerance=0.1),
    "robots_noindex": MetricSpec("Директива noindex", "binary", "lower_is_better", tolerance=0.1),
    "http_status_ok": MetricSpec("Корректный HTTP-статус", "binary", "higher_is_better", tolerance=0.1),
    "canonical_present": MetricSpec("Canonical", "binary", "higher_is_better"),
    "canonical_matches_final_url": MetricSpec("Canonical совпадает с URL", "binary", "higher_is_better"),
    "redirect_count": MetricSpec("Количество редиректов", "count", "lower_is_better", tolerance=0.3),
    "viewport_present": MetricSpec("Meta viewport", "binary", "higher_is_better"),
    "lang_present": MetricSpec("Атрибут lang", "binary", "higher_is_better"),
    "url_has_query_parameters": MetricSpec("Query-параметры в URL", "binary", "lower_is_better", tolerance=0.1),
    "url_parameter_count": MetricSpec("Количество query-параметров", "count", "lower_is_better", tolerance=1.0),
    "url_depth": MetricSpec("Глубина URL", "count", "lower_is_better", tolerance=1.0),
    "hreflang_present": MetricSpec("Hreflang", "binary", "higher_is_better"),
    "phone_present": MetricSpec("Телефон", "binary", "higher_is_better"),
    "address_present": MetricSpec("Адрес", "binary", "higher_is_better"),
    "business_hours_present": MetricSpec("Режим работы", "binary", "higher_is_better"),
    "price_present": MetricSpec("Ценовой сигнал", "binary", "higher_is_better"),
    "delivery_info_present": MetricSpec("Информация о доставке", "binary", "higher_is_better"),
    "payment_info_present": MetricSpec("Информация об оплате", "binary", "higher_is_better"),
    "cta_present": MetricSpec("CTA", "binary", "higher_is_better"),
    "messenger_present": MetricSpec("Мессенджеры", "binary", "higher_is_better"),
    "value_proposition_present": MetricSpec("Ценностное предложение", "binary", "higher_is_better"),
    "reviews_present": MetricSpec("Отзывы", "binary", "higher_is_better"),
    "rating_present": MetricSpec("Рейтинг", "binary", "higher_is_better"),
    "warranty_info_present": MetricSpec("Гарантии", "binary", "higher_is_better"),
    "returns_info_present": MetricSpec("Условия возврата", "binary", "higher_is_better"),
    "legal_requisites_present": MetricSpec("Юридические реквизиты", "binary", "higher_is_better"),
    "company_identity_present": MetricSpec("Сведения о компании", "binary", "higher_is_better"),
    "contact_options_score": MetricSpec("Контактная полнота", "score", "higher_is_better", tolerance=0.08),
    "commercial_signals_score": MetricSpec("Коммерческие сигналы", "score", "higher_is_better", tolerance=0.08),
    "trust_signals_score": MetricSpec("Trust-сигналы", "score", "higher_is_better", tolerance=0.08),
    "intent_alignment_score": MetricSpec("Общее совпадение с интентом", "score", "higher_is_better", tolerance=0.08),
    "local_intent_alignment": MetricSpec("Локальный интент", "score", "higher_is_better", tolerance=0.08),
    "commercial_intent_alignment": MetricSpec("Коммерческий интент", "score", "higher_is_better", tolerance=0.08),
    "informational_intent_alignment": MetricSpec("Информационный интент", "score", "higher_is_better", tolerance=0.08),
    "serp_relative_gap_score": MetricSpec(
        "SERP gap score",
        "score",
        "higher_is_better",
        tolerance=0.05,
        target_value=1.0,
        benchmark_label="Цель: паритет с SERP-лидерами",
    ),
    "serp_relative_percentile": MetricSpec(
        "SERP percentile",
        "percentile",
        "higher_is_better",
        tolerance=0.05,
        target_value=0.65,
        benchmark_label="Цель: конкурентный диапазон SERP",
    ),
    "relative_gap_to_top_semantic_relevance": MetricSpec(
        "Gap до топа: семантика",
        "gap",
        "higher_is_better",
        tolerance=0.03,
        target_value=0.0,
        benchmark_label="Цель: без разрыва с лидером",
    ),
    "relative_gap_to_top_technical_seo": MetricSpec(
        "Gap до топа: technical SEO",
        "gap",
        "higher_is_better",
        tolerance=0.03,
        target_value=0.0,
        benchmark_label="Цель: без разрыва с лидером",
    ),
    "relative_gap_to_top_commercial_trust": MetricSpec(
        "Gap до топа: commercial/trust",
        "gap",
        "higher_is_better",
        tolerance=0.03,
        target_value=0.0,
        benchmark_label="Цель: без разрыва с лидером",
    ),
    "relative_gap_to_top_intent_alignment": MetricSpec(
        "Gap до топа: intent alignment",
        "gap",
        "higher_is_better",
        tolerance=0.03,
        target_value=0.0,
        benchmark_label="Цель: без разрыва с лидером",
    ),
}

GROUP_DEVIATION_METRICS: dict[RecommendationGroupKey, tuple[str, ...]] = {
    "technical_seo": (
        "page_indexable",
        "canonical_present",
        "redirect_count",
        "viewport_present",
        "url_depth",
    ),
    "commercial_trust": (
        "contact_options_score",
        "commercial_signals_score",
        "trust_signals_score",
        "cta_present",
        "price_present",
    ),
    "semantic_intent": (
        "semantic_similarity",
        "keyword_coverage_ratio",
        "intent_alignment_score",
        "query_in_title",
        "text_length_chars",
    ),
    "competitor_gap": (
        "serp_relative_gap_score",
        "serp_relative_percentile",
        "relative_gap_to_top_semantic_relevance",
        "relative_gap_to_top_technical_seo",
        "relative_gap_to_top_commercial_trust",
        "relative_gap_to_top_intent_alignment",
    ),
}


def average_competitor_features(
    competitor_pages_features: list[dict[str, float | int]],
) -> dict[str, float]:
    if not competitor_pages_features:
        return {}

    totals: dict[str, float] = {}
    for features in competitor_pages_features:
        for key, value in features.items():
            totals[key] = totals.get(key, 0.0) + float(value)

    count = float(len(competitor_pages_features))
    return {key: value / count for key, value in totals.items()}


def _has_feature(features: dict[str, float | int], key: str) -> bool:
    return key in features


def _float_feature(features: dict[str, float | int], key: str) -> float:
    return float(features.get(key, 0.0))


def _int_feature(features: dict[str, float | int], key: str) -> int:
    return int(features.get(key, 0))


def _normalize_priority(value: object) -> RecommendationPriority:
    if value in PRIORITY_ORDER:
        return value  # type: ignore[return-value]
    return "low"


def _humanize_code(code: str) -> str:
    return code.replace("_", " ").strip().capitalize() or "Recommendation"


def _format_metric_value(value: float, unit: str) -> str:
    if unit == "binary":
        return "Да" if value >= 0.5 else "Нет"
    if unit == "chars":
        return f"{int(round(value))} симв."
    if unit == "count":
        return str(int(round(value)))
    if unit == "percentile":
        return f"{round(value * 100.0, 1)} перцентиль"
    if unit in {"score", "ratio", "gap"}:
        return f"{round(value, 2)}"
    return str(round(value, 2))


def _resolve_metric_values(
    metric_code: str,
    *,
    page_features: dict[str, float | int],
    competitor_avg_features: dict[str, float],
    page_score: float | None,
    competitors_average_score: float | None,
) -> tuple[float | None, float | None, MetricSpec | None]:
    if metric_code == "page_score":
        return page_score, competitors_average_score, MetricSpec("Текущий score", "score", "higher_is_better")
    if metric_code == "competitors_average_score":
        return competitors_average_score, None, MetricSpec("Средний score конкурентов", "score", "higher_is_better")

    spec = METRIC_SPECS.get(metric_code)
    if spec is None or metric_code not in page_features:
        return None, None, None

    current_value = float(page_features[metric_code])
    benchmark_value = (
        spec.target_value
        if spec.target_value is not None
        else float(competitor_avg_features[metric_code])
        if metric_code in competitor_avg_features
        else None
    )
    return current_value, benchmark_value, spec


def _build_item_evidence(
    metric_codes: tuple[str, ...],
    *,
    page_features: dict[str, float | int],
    competitor_avg_features: dict[str, float],
    page_score: float | None,
    competitors_average_score: float | None,
) -> list[dict[str, str | None]]:
    evidence: list[dict[str, str | None]] = []
    for metric_code in dict.fromkeys(metric_codes):
        current_value, benchmark_value, spec = _resolve_metric_values(
            metric_code,
            page_features=page_features,
            competitor_avg_features=competitor_avg_features,
            page_score=page_score,
            competitors_average_score=competitors_average_score,
        )
        if current_value is None or spec is None:
            continue

        benchmark_label = spec.benchmark_label or "Среднее по конкурентам"
        evidence.append(
            {
                "label": spec.label,
                "value": _format_metric_value(current_value, spec.unit),
                "benchmark": _format_metric_value(benchmark_value, spec.unit)
                if benchmark_value is not None
                else None,
                "benchmark_label": benchmark_label if benchmark_value is not None else None,
            }
        )
    return evidence


def _gap_ratio(gap: float, benchmark_value: float, spec: MetricSpec) -> float:
    scale = max(abs(benchmark_value), spec.minimum_scale)
    return gap / scale if scale else gap


def _priority_from_gap(gap: float, benchmark_value: float, spec: MetricSpec) -> RecommendationPriority:
    ratio = _gap_ratio(gap, benchmark_value, spec)
    if ratio >= 0.4:
        return "high"
    if ratio >= 0.18:
        return "medium"
    return "low"


def _build_deviation_summary(
    *,
    spec: MetricSpec,
    current_value: float,
    benchmark_value: float,
    trend: DeviationTrend,
) -> str:
    benchmark_label = spec.benchmark_label or "среднего по конкурентам"
    if trend == "aligned":
        return f"Метрика близка к {benchmark_label.lower()}."

    difference_label = _format_metric_value(abs(current_value - benchmark_value), spec.unit)
    if spec.direction == "higher_is_better":
        return f"Страница {'отстаёт' if trend == 'behind' else 'опережает'} {benchmark_label.lower()} на {difference_label}."
    return f"Значение {'хуже' if trend == 'behind' else 'лучше'} {benchmark_label.lower()} на {difference_label}."


def _build_group_deviation(
    metric_code: str,
    *,
    page_features: dict[str, float | int],
    competitor_avg_features: dict[str, float],
) -> dict[str, object] | None:
    spec = METRIC_SPECS.get(metric_code)
    if spec is None or metric_code not in page_features:
        return None

    benchmark_value = (
        spec.target_value
        if spec.target_value is not None
        else float(competitor_avg_features[metric_code])
        if metric_code in competitor_avg_features
        else None
    )
    if benchmark_value is None:
        return None

    current_value = float(page_features[metric_code])
    delta = round(current_value - benchmark_value, 4)
    performance_gap = benchmark_value - current_value if spec.direction == "higher_is_better" else current_value - benchmark_value
    if performance_gap > spec.tolerance:
        trend: DeviationTrend = "behind"
    elif performance_gap < -spec.tolerance:
        trend = "ahead"
    else:
        trend = "aligned"

    gap = round(max(performance_gap, 0.0), 4)
    priority = "low" if trend == "aligned" else _priority_from_gap(gap, benchmark_value, spec)
    return {
        "code": metric_code,
        "label": spec.label,
        "unit": spec.unit,
        "current_value": round(current_value, 4),
        "benchmark_value": round(benchmark_value, 4),
        "benchmark_label": spec.benchmark_label or "Среднее по конкурентам",
        "delta": delta,
        "gap": gap,
        "trend": trend,
        "priority": priority,
        "summary": _build_deviation_summary(
            spec=spec,
            current_value=current_value,
            benchmark_value=benchmark_value,
            trend=trend,
        ),
    }


def _build_group_status(
    items: list[dict[str, object]],
    deviations: list[dict[str, object]],
    *,
    has_context: bool,
) -> str:
    if items:
        top_priority = min((str(item.get("priority") or "low") for item in items), key=lambda priority: PRIORITY_ORDER[_normalize_priority(priority)])
        return {"high": "critical", "medium": "attention", "low": "monitor"}[top_priority]

    behind_deviations = [deviation for deviation in deviations if deviation.get("trend") == "behind"]
    if behind_deviations:
        top_priority = min(
            (str(deviation.get("priority") or "low") for deviation in behind_deviations),
            key=lambda priority: PRIORITY_ORDER[_normalize_priority(priority)],
        )
        return {"high": "critical", "medium": "attention", "low": "monitor"}[top_priority]

    if has_context or deviations:
        return "competitive"
    return "not_enough_data"


def _build_groups_payload(
    drafts: list[RecommendationDraft],
    *,
    page_features: dict[str, float | int],
    competitor_avg_features: dict[str, float],
    has_competitor_context: bool,
    page_score: float | None,
    competitors_average_score: float | None,
    include_deviations: bool,
) -> list[dict[str, object]]:
    groups: dict[RecommendationGroupKey, dict[str, object]] = {
        key: {
            "key": key,
            "label": GROUP_METADATA[key]["label"],
            "description": GROUP_METADATA[key]["description"],
            "status": "not_enough_data",
            "items": [],
            "deviations": [],
        }
        for key in GROUP_ORDER
    }

    for draft in drafts:
        template = RECOMMENDATION_TEMPLATES.get(draft.code)
        group_key = template.group if template is not None else "competitor_gap"
        metrics = template.metrics if template is not None else ()
        title = template.title if template is not None else _humanize_code(draft.code)
        item = {
            "code": draft.code,
            "priority": draft.priority,
            "impact": draft.priority,
            "title": title,
            "message": draft.message,
            "expected_outcome": IMPACT_LABELS[draft.priority],
            "evidence": _build_item_evidence(
                metrics,
                page_features=page_features,
                competitor_avg_features=competitor_avg_features,
                page_score=page_score,
                competitors_average_score=competitors_average_score,
            ),
            "related_metrics": list(metrics),
        }
        items = groups[group_key]["items"]
        if isinstance(items, list):
            items.append(item)

    for group_key in GROUP_ORDER:
        group = groups[group_key]
        items = group["items"]
        if isinstance(items, list):
            items.sort(key=lambda item: (PRIORITY_ORDER[_normalize_priority(item.get("priority"))], str(item.get("code") or "")))

        deviations: list[dict[str, object]] = []
        if include_deviations:
            for metric_code in GROUP_DEVIATION_METRICS[group_key]:
                deviation = _build_group_deviation(
                    metric_code,
                    page_features=page_features,
                    competitor_avg_features=competitor_avg_features,
                )
                if deviation is not None:
                    deviations.append(deviation)
            deviations.sort(
                key=lambda deviation: (
                    0 if deviation.get("trend") == "behind" else 1 if deviation.get("trend") == "aligned" else 2,
                    PRIORITY_ORDER[_normalize_priority(deviation.get("priority"))],
                    -float(deviation.get("gap") or 0.0),
                    str(deviation.get("code") or ""),
                )
            )

        group["deviations"] = deviations
        group["status"] = _build_group_status(
            items if isinstance(items, list) else [],
            deviations,
            has_context=has_competitor_context or any(metric in page_features for metric in GROUP_DEVIATION_METRICS[group_key]),
        )
        group["empty_state"] = GROUP_EMPTY_MESSAGES[group_key]

    return [groups[key] for key in GROUP_ORDER]


def _build_recommendations_payload(
    drafts: list[RecommendationDraft],
    *,
    page_features: dict[str, float | int],
    competitor_avg_features: dict[str, float],
    has_competitor_context: bool,
    page_score: float | None,
    competitors_average_score: float | None,
    include_deviations: bool,
) -> dict[str, object]:
    groups = _build_groups_payload(
        drafts,
        page_features=page_features,
        competitor_avg_features=competitor_avg_features,
        has_competitor_context=has_competitor_context,
        page_score=page_score,
        competitors_average_score=competitors_average_score,
        include_deviations=include_deviations,
    )
    total_recommendations = sum(len(group["items"]) for group in groups if isinstance(group.get("items"), list))
    by_priority = {priority: 0 for priority in PRIORITY_ORDER}
    for group in groups:
        for item in group.get("items", []):
            priority = _normalize_priority(item.get("priority"))
            by_priority[priority] += 1

    return {
        "schema_version": RECOMMENDATIONS_SCHEMA_VERSION,
        "summary": {
            "total_recommendations": total_recommendations,
            "high_priority_count": by_priority["high"],
            "medium_priority_count": by_priority["medium"],
            "low_priority_count": by_priority["low"],
            "groups_with_issues": sum(1 for group in groups if group.get("items")),
            "competitor_context": has_competitor_context,
            "score_gap_vs_competitors": round(page_score - competitors_average_score, 4)
            if has_competitor_context and page_score is not None and competitors_average_score is not None
            else None,
        },
        "groups": groups,
    }


def get_recommendation_count(recommendations: object) -> int:
    if isinstance(recommendations, list):
        return len([item for item in recommendations if isinstance(item, dict)])
    if isinstance(recommendations, dict):
        summary = recommendations.get("summary")
        if isinstance(summary, dict) and isinstance(summary.get("total_recommendations"), int):
            return int(summary["total_recommendations"])
        groups = recommendations.get("groups")
        if isinstance(groups, list):
            return sum(
                len(group.get("items", []))
                for group in groups
                if isinstance(group, dict) and isinstance(group.get("items"), list)
            )
    return 0


def normalize_recommendations_payload(recommendations: object) -> dict[str, object] | None:
    if recommendations is None:
        return None
    if isinstance(recommendations, dict) and isinstance(recommendations.get("groups"), list):
        return recommendations
    if not isinstance(recommendations, list):
        return None

    drafts = [
        RecommendationDraft(
            code=str(item.get("code") or "LEGACY_RECOMMENDATION"),
            priority=_normalize_priority(item.get("priority")),
            message=str(item.get("message") or item.get("title") or "Рекомендация без описания"),
        )
        for item in recommendations
        if isinstance(item, dict)
    ]
    return _build_recommendations_payload(
        drafts,
        page_features={},
        competitor_avg_features={},
        has_competitor_context=False,
        page_score=None,
        competitors_average_score=None,
        include_deviations=False,
    )


def generate_recommendations(
    page_features: dict[str, float | int],
    page_score: float,
    competitor_pages_features: list[dict[str, float | int]] | None = None,
) -> dict[str, object]:
    drafts: list[RecommendationDraft] = []
    competitor_pages_features = competitor_pages_features or []
    has_competitor_context = len(competitor_pages_features) >= MIN_COMPETITORS_FOR_RECOMMENDATIONS
    competitor_avg_features = average_competitor_features(competitor_pages_features) if has_competitor_context else {}
    competitors_average_score = average_score(competitor_pages_features) if has_competitor_context else None
    has_technical_context = any(_has_feature(page_features, key) for key in TECHNICAL_FEATURE_KEYS)
    has_commercial_trust_context = any(_has_feature(page_features, key) for key in COMMERCIAL_TRUST_FEATURE_KEYS)
    has_intent_context = any(_has_feature(page_features, key) for key in INTENT_ALIGNMENT_FEATURE_KEYS)
    has_relative_context = (
        any(_has_feature(page_features, key) for key in SERP_RELATIVE_FEATURE_KEYS)
        and _int_feature(page_features, "serp_relative_context_available") == 1
    )

    def add_recommendation(code: str, priority: RecommendationPriority, message: str) -> None:
        drafts.append(RecommendationDraft(code=code, priority=priority, message=message))

    if page_score < 45:
        add_recommendation(
            "LOW_PAGE_SCORE",
            "high",
            "Существенно улучшите структуру, релевантность, коммерческую полноту и техническое качество страницы: текущий score слишком низкий.",
        )
    elif competitors_average_score and page_score < competitors_average_score - 7:
        add_recommendation(
            "BELOW_COMPETITORS",
            "high",
            "Страница заметно уступает конкурентам по качеству. Усильте контент, коммерческие блоки, trust-сигналы и техническую базу.",
        )
    elif competitors_average_score and page_score < competitors_average_score:
        add_recommendation(
            "SLIGHTLY_BELOW_COMPETITORS",
            "medium",
            "Страница немного уступает конкурентам. Стоит доработать ключевые блоки и итоговую релевантность.",
        )

    if _int_feature(page_features, "title_present") == 0:
        add_recommendation(
            "MISSING_TITLE",
            "high",
            "Добавьте title для страницы, чтобы улучшить поисковую релевантность и CTR сниппета.",
        )
    elif _int_feature(page_features, "query_in_title") == 0:
        add_recommendation(
            "QUERY_NOT_IN_TITLE",
            "high",
            "Добавьте основной запрос в title страницы, сохранив естественную формулировку.",
        )

    if _int_feature(page_features, "meta_description_present") == 0:
        add_recommendation(
            "MISSING_META_DESCRIPTION",
            "medium",
            "Добавьте meta description с кратким описанием страницы и основной темой запроса.",
        )

    h1_count = _int_feature(page_features, "h1_count")
    if h1_count == 0:
        add_recommendation(
            "MISSING_H1",
            "high",
            "Добавьте один понятный H1 с основной темой страницы.",
        )
    elif h1_count > 1:
        add_recommendation(
            "MULTIPLE_H1",
            "medium",
            "Оставьте один основной H1, чтобы структура страницы была чище и однозначнее.",
        )

    if _int_feature(page_features, "query_in_text") == 0:
        add_recommendation(
            "QUERY_NOT_IN_TEXT",
            "high",
            "Добавьте ключевой запрос в основной текст страницы естественным образом.",
        )
    elif _float_feature(page_features, "keyword_coverage_ratio") < 0.5:
        add_recommendation(
            "LOW_KEYWORD_COVERAGE",
            "medium",
            "Раскройте тему полнее: сейчас текст покрывает слишком мало слов из поискового запроса.",
        )

    if _float_feature(page_features, "semantic_similarity") < 0.45:
        add_recommendation(
            "LOW_SEMANTIC_RELEVANCE",
            "high",
            "Перепишите текст так, чтобы он точнее отвечал на поисковый запрос и интент пользователя.",
        )

    text_length_chars = _float_feature(page_features, "text_length_chars")
    competitor_text_length = float(competitor_avg_features.get("text_length_chars", 0.0))
    if text_length_chars < 1200:
        add_recommendation(
            "THIN_CONTENT",
            "medium",
            "Увеличьте объём полезного основного текста: текущего контента недостаточно для уверенного сравнения с выдачей.",
        )
    elif competitor_text_length and text_length_chars < competitor_text_length * 0.75:
        add_recommendation(
            "CONTENT_SHORTER_THAN_COMPETITORS",
            "medium",
            "Расширьте страницу: у конкурентов в среднем контент заметно полнее.",
        )

    if _float_feature(page_features, "text_to_html_ratio") < 0.12:
        add_recommendation(
            "LOW_TEXT_TO_HTML_RATIO",
            "medium",
            "Увеличьте долю полезного текста относительно служебной HTML-разметки.",
        )

    link_count = _float_feature(page_features, "link_count")
    competitor_link_count = float(competitor_avg_features.get("link_count", 0.0))
    if competitor_link_count and link_count < competitor_link_count * 0.6:
        add_recommendation(
            "FEW_LINKS",
            "low",
            "Добавьте больше полезных ссылок на связанные разделы и ключевые страницы сайта.",
        )

    image_count = _float_feature(page_features, "image_count")
    competitor_image_count = float(competitor_avg_features.get("image_count", 0.0))
    if image_count == 0 and competitor_image_count >= 1:
        add_recommendation(
            "NO_IMAGES",
            "low",
            "Добавьте изображения или иллюстрации, чтобы страница выглядела информативнее и конкурентоспособнее.",
        )

    form_count = _float_feature(page_features, "form_count")
    competitor_form_count = float(competitor_avg_features.get("form_count", 0.0))
    if form_count == 0 and competitor_form_count >= 0.5:
        add_recommendation(
            "NO_CONVERSION_ELEMENT",
            "medium",
            "Добавьте форму заявки или другой явный CTA-элемент для конверсии.",
        )

    if has_technical_context:
        if _has_feature(page_features, "page_indexable") and _int_feature(page_features, "page_indexable") == 0:
            if _int_feature(page_features, "robots_noindex") == 1:
                message = "Страница закрыта от индексации директивой noindex. Снимите запрет, если страница должна ранжироваться."
            elif _has_feature(page_features, "http_status_ok") and _int_feature(page_features, "http_status_ok") == 0:
                message = "Страница возвращает нецелевой HTTP-статус. Для ранжируемой посадочной страницы нужен корректный индексируемый ответ сервера."
            else:
                message = "Страница не выглядит индексируемой. Проверьте robots-директивы и технический ответ сервера."
            add_recommendation("TECHNICAL_INDEXING_BLOCK", "high", message)

        if (
            _has_feature(page_features, "canonical_present")
            and _int_feature(page_features, "canonical_present") == 1
            and _has_feature(page_features, "canonical_matches_final_url")
            and _int_feature(page_features, "canonical_matches_final_url") == 0
        ):
            add_recommendation(
                "TECHNICAL_CANONICAL_MISMATCH",
                "high",
                "Canonical указывает на другой URL. Согласуйте canonical с финальной ранжируемой страницей.",
            )
        elif _has_feature(page_features, "canonical_present") and _int_feature(page_features, "canonical_present") == 0:
            is_complex_url = _int_feature(page_features, "has_redirect") == 1 or _int_feature(page_features, "url_has_query_parameters") == 1
            competitor_canonical = float(competitor_avg_features.get("canonical_present", 0.0)) if has_competitor_context else 0.0
            if is_complex_url or competitor_canonical >= 0.7:
                add_recommendation(
                    "TECHNICAL_MISSING_CANONICAL",
                    "medium" if not is_complex_url else "high",
                    "Добавьте canonical, чтобы закрепить основную версию URL и уменьшить риск размывания сигналов между вариантами страницы.",
                )

        redirect_count = _int_feature(page_features, "redirect_count")
        if _has_feature(page_features, "redirect_count") and redirect_count >= 2:
            add_recommendation(
                "TECHNICAL_REDIRECT_CHAIN",
                "high",
                "Сократите redirect chain: несколько последовательных редиректов ухудшают crawl efficiency и техническое качество посадочной страницы.",
            )
        elif _has_feature(page_features, "redirect_count") and redirect_count == 1:
            add_recommendation(
                "TECHNICAL_REDIRECTED_TARGET",
                "medium",
                "Используйте в продвижении сразу финальный URL без промежуточного редиректа.",
            )

        if _has_feature(page_features, "viewport_present") and _int_feature(page_features, "viewport_present") == 0:
            add_recommendation(
                "TECHNICAL_MISSING_VIEWPORT",
                "medium",
                "Добавьте meta viewport, чтобы страница корректно адаптировалась на мобильных устройствах.",
            )

        if _has_feature(page_features, "lang_present") and _int_feature(page_features, "lang_present") == 0:
            add_recommendation(
                "TECHNICAL_MISSING_LANG",
                "medium",
                "Укажите атрибут lang у HTML-документа, чтобы поисковые системы и браузеры точнее интерпретировали язык страницы.",
            )

        if _has_feature(page_features, "url_has_query_parameters") and _int_feature(page_features, "url_has_query_parameters") == 1:
            add_recommendation(
                "TECHNICAL_QUERY_PARAMETERS_IN_URL",
                "medium" if _int_feature(page_features, "url_parameter_count") > 1 else "low",
                "Сведите к минимуму query-параметры в продвигаемом URL или зафиксируйте основную версию через canonical.",
            )

        if _has_feature(page_features, "url_depth") and _int_feature(page_features, "url_depth") >= 4:
            add_recommendation(
                "TECHNICAL_DEEP_URL",
                "low",
                "Сократите глубину URL, если это возможно: слишком вложенные адреса хуже читаются и усложняют информационную архитектуру.",
            )

        competitor_hreflang = float(competitor_avg_features.get("hreflang_present", 0.0)) if has_competitor_context else 0.0
        if (
            _has_feature(page_features, "hreflang_present")
            and _int_feature(page_features, "hreflang_present") == 0
            and competitor_hreflang >= 0.4
        ):
            add_recommendation(
                "TECHNICAL_MISSING_HREFLANG",
                "low",
                "Конкуренты используют hreflang. Если страница участвует в мультирегиональной или мультиязычной выдаче, добавьте hreflang-разметку.",
            )

    if has_commercial_trust_context:
        competitor_phone = float(competitor_avg_features.get("phone_present", 0.0)) if has_competitor_context else 0.0
        competitor_address = float(competitor_avg_features.get("address_present", 0.0)) if has_competitor_context else 0.0
        competitor_hours = float(competitor_avg_features.get("business_hours_present", 0.0)) if has_competitor_context else 0.0
        competitor_price = float(competitor_avg_features.get("price_present", 0.0)) if has_competitor_context else 0.0
        competitor_delivery = float(competitor_avg_features.get("delivery_info_present", 0.0)) if has_competitor_context else 0.0
        competitor_payment = float(competitor_avg_features.get("payment_info_present", 0.0)) if has_competitor_context else 0.0
        competitor_cta = float(competitor_avg_features.get("cta_present", 0.0)) if has_competitor_context else 0.0
        competitor_messenger = float(competitor_avg_features.get("messenger_present", 0.0)) if has_competitor_context else 0.0
        competitor_value = float(competitor_avg_features.get("value_proposition_present", 0.0)) if has_competitor_context else 0.0
        competitor_reviews = float(competitor_avg_features.get("reviews_present", 0.0)) if has_competitor_context else 0.0
        competitor_rating = float(competitor_avg_features.get("rating_present", 0.0)) if has_competitor_context else 0.0
        competitor_legal = float(competitor_avg_features.get("legal_requisites_present", 0.0)) if has_competitor_context else 0.0
        competitor_warranty = float(competitor_avg_features.get("warranty_info_present", 0.0)) if has_competitor_context else 0.0
        competitor_returns = float(competitor_avg_features.get("returns_info_present", 0.0)) if has_competitor_context else 0.0

        if _has_feature(page_features, "phone_present") and _int_feature(page_features, "phone_present") == 0:
            if has_competitor_context or _float_feature(page_features, "contact_options_score") < 0.4:
                add_recommendation(
                    "COMMERCIAL_MISSING_PHONE",
                    "high" if competitor_phone >= 0.4 else "medium",
                    "Добавьте заметный телефон или другой прямой контакт в первый экран и основные коммерческие блоки страницы.",
                )

        if _has_feature(page_features, "address_present") and _int_feature(page_features, "address_present") == 0:
            if competitor_address >= 0.3 or _float_feature(page_features, "trust_signals_score") < 0.45:
                add_recommendation(
                    "COMMERCIAL_MISSING_ADDRESS",
                    "medium",
                    "Добавьте адрес или понятную географическую привязку бизнеса, чтобы усилить локальное доверие и коммерческую полноту страницы.",
                )

        if _has_feature(page_features, "business_hours_present") and _int_feature(page_features, "business_hours_present") == 0:
            if competitor_hours >= 0.3:
                add_recommendation(
                    "COMMERCIAL_MISSING_BUSINESS_HOURS",
                    "medium",
                    "Укажите режим работы или время ответа, чтобы снизить неопределённость для пользователя.",
                )

        if _has_feature(page_features, "price_present") and _int_feature(page_features, "price_present") == 0:
            if competitor_price >= 0.4:
                add_recommendation(
                    "COMMERCIAL_MISSING_PRICE_SIGNAL",
                    "medium",
                    "Добавьте ценовой ориентир, диапазон цен или понятный оффер, если конкуренты уже дают пользователю ценовой сигнал.",
                )

        if (
            _has_feature(page_features, "delivery_info_present")
            and _int_feature(page_features, "delivery_info_present") == 0
            and competitor_delivery >= 0.4
        ):
            add_recommendation(
                "COMMERCIAL_MISSING_DELIVERY_INFO",
                "medium",
                "Добавьте блок с условиями доставки или получения услуги, если это важно в конкурентной выдаче.",
            )

        if (
            _has_feature(page_features, "payment_info_present")
            and _int_feature(page_features, "payment_info_present") == 0
            and competitor_payment >= 0.4
        ):
            add_recommendation(
                "COMMERCIAL_MISSING_PAYMENT_INFO",
                "medium",
                "Укажите способы оплаты или условия расчёта, если конкуренты уже дают этот сигнал доверия.",
            )

        if _has_feature(page_features, "cta_present") and _int_feature(page_features, "cta_present") == 0:
            if competitor_cta >= 0.5 or form_count == 0:
                add_recommendation(
                    "COMMERCIAL_WEAK_CTA",
                    "medium",
                    "Сделайте CTA-блок явнее: добавьте кнопки действия, заявку, звонок или консультацию в ключевые зоны страницы.",
                )

        if (
            _has_feature(page_features, "messenger_present")
            and _int_feature(page_features, "messenger_present") == 0
            and competitor_messenger >= 0.5
        ):
            add_recommendation(
                "COMMERCIAL_NO_MESSENGERS",
                "low",
                "Добавьте мессенджеры как дополнительный канал связи, если это уже стало нормой в выдаче по вашему запросу.",
            )

        if (
            _has_feature(page_features, "value_proposition_present")
            and _int_feature(page_features, "value_proposition_present") == 0
            and competitor_value >= 0.4
        ):
            add_recommendation(
                "COMMERCIAL_WEAK_VALUE_PROPOSITION",
                "medium",
                "Сформулируйте ценностное предложение страницы: почему пользователь должен выбрать именно вас, а не конкурента.",
            )

        if _float_feature(page_features, "contact_options_score") < 0.4:
            add_recommendation(
                "TRUST_WEAK_CONTACT_BLOCK",
                "high",
                "Усильте contact-блок: добавьте больше прозрачных способов связи, адрес, график работы и понятную контактную зону.",
            )

        if (
            _has_feature(page_features, "legal_requisites_present")
            and _int_feature(page_features, "legal_requisites_present") == 0
            and (_int_feature(page_features, "company_identity_present") == 0 or competitor_legal >= 0.3)
        ):
            add_recommendation(
                "TRUST_MISSING_BUSINESS_ID",
                "medium",
                "Добавьте юридические реквизиты, сведения о компании или другой явный business identity block, чтобы усилить доверие.",
            )

        if (
            _int_feature(page_features, "reviews_present") == 0
            and _int_feature(page_features, "rating_present") == 0
            and (competitor_reviews >= 0.4 or competitor_rating >= 0.4)
        ):
            add_recommendation(
                "TRUST_MISSING_SOCIAL_PROOF",
                "medium",
                "Добавьте отзывы, кейсы или рейтинговые сигналы, если конкуренты уже показывают социальное доказательство на посадочной странице.",
            )

        if (
            _int_feature(page_features, "warranty_info_present") == 0
            and _int_feature(page_features, "returns_info_present") == 0
            and (competitor_warranty >= 0.4 or competitor_returns >= 0.4)
        ):
            add_recommendation(
                "TRUST_MISSING_POST_SALE_INFO",
                "low",
                "Добавьте гарантию, условия возврата или постпродажные обязательства, если это используется конкурентами как trust-сигнал.",
            )

    if has_intent_context:
        if _int_feature(page_features, "intent_is_local_commercial") == 1 and _float_feature(page_features, "local_intent_alignment") < 0.55:
            add_recommendation(
                "INTENT_WEAK_LOCAL_ALIGNMENT",
                "high",
                "Запрос выглядит локально-коммерческим. Усильте адрес, телефон, режим работы и локальные коммерческие сигналы на странице.",
            )

        if _int_feature(page_features, "intent_is_commercial") == 1 and _float_feature(page_features, "commercial_intent_alignment") < 0.55:
            add_recommendation(
                "INTENT_WEAK_COMMERCIAL_ALIGNMENT",
                "high",
                "Страница недостаточно соответствует коммерческому интенту: добавьте явные офферы, CTA, цены и блоки доверия.",
            )

        if _int_feature(page_features, "intent_is_informational") == 1 and _float_feature(page_features, "informational_intent_alignment") < 0.55:
            add_recommendation(
                "INTENT_WEAK_INFORMATIONAL_ALIGNMENT",
                "medium",
                "Для информационного запроса не хватает глубины ответа: расширьте объяснения, структуру и FAQ-блоки.",
            )

    if has_relative_context:
        relative_percentile = _float_feature(page_features, "serp_relative_percentile")
        relative_gap_score = _float_feature(page_features, "serp_relative_gap_score")

        if relative_percentile < 0.35 or relative_gap_score < 0.55:
            add_recommendation(
                "RELATIVE_SERP_GAP",
                "high",
                "Страница заметно отстаёт от SERP-лидеров по совокупности ключевых групп сигналов. Приоритетно закрывайте разрывы относительно топа, а не только общие SEO-ошибки.",
            )

        if _float_feature(page_features, "relative_gap_to_top_semantic_relevance") < -0.12:
            add_recommendation(
                "RELATIVE_SEMANTIC_GAP",
                "high",
                "Семантическая релевантность ниже лидеров выдачи. Усильте соответствие интенту в title, заголовках и основном тексте.",
            )

        if _float_feature(page_features, "relative_gap_to_top_technical_seo") < -0.12:
            add_recommendation(
                "RELATIVE_TECHNICAL_GAP",
                "medium",
                "Технический профиль страницы слабее конкурентов из топа. Проверьте indexability, canonical, URL hygiene и meta-signals.",
            )

        if _float_feature(page_features, "relative_gap_to_top_commercial_trust") < -0.12:
            add_recommendation(
                "RELATIVE_COMMERCIAL_TRUST_GAP",
                "high",
                "Коммерческие и trust-сигналы отстают от топа. Усильте контакты, офферы, цены, условия покупки и блоки доверия.",
            )

        if _float_feature(page_features, "relative_gap_to_top_intent_alignment") < -0.12:
            add_recommendation(
                "RELATIVE_INTENT_ALIGNMENT_GAP",
                "high",
                "Даже при наличии базовых SEO-сигналов страница хуже конкурентов совпадает с интентом запроса. Пересоберите структуру страницы под сценарий пользователя.",
            )

    if not drafts:
        add_recommendation(
            "NO_CRITICAL_ISSUES",
            "low",
            "Критичных проблем не найдено. Можно точечно усиливать контент, коммерческие блоки, trust-сигналы и техническую базу.",
        )

    drafts.sort(key=lambda item: (PRIORITY_ORDER[item.priority], item.code))
    return _build_recommendations_payload(
        drafts,
        page_features=page_features,
        competitor_avg_features=competitor_avg_features,
        has_competitor_context=has_competitor_context,
        page_score=page_score,
        competitors_average_score=competitors_average_score,
        include_deviations=True,
    )
