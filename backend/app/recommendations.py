from __future__ import annotations

from typing import Any

from app.ml import average_score


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
MIN_COMPETITORS_FOR_RECOMMENDATIONS = 2


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


def generate_recommendations(
    page_features: dict[str, float | int],
    page_score: float,
    competitor_pages_features: list[dict[str, float | int]] | None = None,
) -> list[dict[str, str]]:
    recommendations: list[dict[str, str]] = []
    competitor_pages_features = competitor_pages_features or []
    has_competitor_context = len(competitor_pages_features) >= MIN_COMPETITORS_FOR_RECOMMENDATIONS
    competitor_avg_features = average_competitor_features(competitor_pages_features) if has_competitor_context else {}
    competitors_average_score = average_score(competitor_pages_features) if has_competitor_context else 0.0

    def add_recommendation(code: str, priority: str, message: str) -> None:
        recommendations.append(
            {
                "code": code,
                "priority": priority,
                "message": message,
            }
        )

    if page_score < 45:
        add_recommendation(
            "LOW_PAGE_SCORE",
            "high",
            "Существенно улучшите структуру и релевантность страницы: текущий score слишком низкий.",
        )
    elif competitors_average_score and page_score < competitors_average_score - 7:
        add_recommendation(
            "BELOW_COMPETITORS",
            "high",
            "Страница заметно уступает конкурентам по качеству, нужно усилить контент и коммерческие элементы.",
        )
    elif competitors_average_score and page_score < competitors_average_score:
        add_recommendation(
            "SLIGHTLY_BELOW_COMPETITORS",
            "medium",
            "Страница немного уступает конкурентам, стоит доработать ключевые блоки и релевантность.",
        )

    if int(page_features.get("title_present", 0)) == 0:
        add_recommendation(
            "MISSING_TITLE",
            "high",
            "Добавьте title для страницы, чтобы улучшить поисковую релевантность и CTR.",
        )
    elif int(page_features.get("query_in_title", 0)) == 0:
        add_recommendation(
            "QUERY_NOT_IN_TITLE",
            "high",
            "Добавьте основной запрос в title страницы.",
        )

    if int(page_features.get("meta_description_present", 0)) == 0:
        add_recommendation(
            "MISSING_META_DESCRIPTION",
            "medium",
            "Добавьте meta description с кратким описанием страницы и ключевой темой.",
        )

    h1_count = int(page_features.get("h1_count", 0))
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
            "Оставьте один основной H1, чтобы структура страницы была чище.",
        )

    if int(page_features.get("query_in_text", 0)) == 0:
        add_recommendation(
            "QUERY_NOT_IN_TEXT",
            "high",
            "Добавьте ключевой запрос в основной текст страницы естественным образом.",
        )
    elif float(page_features.get("keyword_coverage_ratio", 0.0)) < 0.5:
        add_recommendation(
            "LOW_KEYWORD_COVERAGE",
            "medium",
            "Раскройте тему полнее: сейчас текст покрывает мало слов из поискового запроса.",
        )

    if float(page_features.get("semantic_similarity", 0.0)) < 0.45:
        add_recommendation(
            "LOW_SEMANTIC_RELEVANCE",
            "high",
            "Перепишите текст так, чтобы он точнее отвечал на поисковый запрос по смыслу.",
        )

    text_length_chars = float(page_features.get("text_length_chars", 0))
    competitor_text_length = float(competitor_avg_features.get("text_length_chars", 0.0))
    if text_length_chars < 1200:
        add_recommendation(
            "THIN_CONTENT",
            "medium",
            "Увеличьте объём полезного основного текста: текущего контента недостаточно.",
        )
    elif competitor_text_length and text_length_chars < competitor_text_length * 0.75:
        add_recommendation(
            "CONTENT_SHORTER_THAN_COMPETITORS",
            "medium",
            "Расширьте страницу: у конкурентов в среднем контент заметно полнее.",
        )

    if float(page_features.get("text_to_html_ratio", 0.0)) < 0.12:
        add_recommendation(
            "LOW_TEXT_TO_HTML_RATIO",
            "medium",
            "Увеличьте долю полезного текста относительно служебной HTML-разметки.",
        )

    link_count = float(page_features.get("link_count", 0))
    competitor_link_count = float(competitor_avg_features.get("link_count", 0.0))
    if competitor_link_count and link_count < competitor_link_count * 0.6:
        add_recommendation(
            "FEW_LINKS",
            "low",
            "Добавьте больше полезных ссылок на связанные разделы и ключевые страницы сайта.",
        )

    image_count = float(page_features.get("image_count", 0))
    competitor_image_count = float(competitor_avg_features.get("image_count", 0.0))
    if image_count == 0 and competitor_image_count >= 1:
        add_recommendation(
            "NO_IMAGES",
            "low",
            "Добавьте изображения или иллюстрации, чтобы страница выглядела информативнее.",
        )

    form_count = float(page_features.get("form_count", 0))
    competitor_form_count = float(competitor_avg_features.get("form_count", 0.0))
    if form_count == 0 and competitor_form_count >= 0.5:
        add_recommendation(
            "NO_CONVERSION_ELEMENT",
            "medium",
            "Добавьте форму заявки или другой явный CTA-элемент для конверсии.",
        )

    if not recommendations:
        add_recommendation(
            "NO_CRITICAL_ISSUES",
            "low",
            "Критичных проблем не найдено, можно точечно улучшать контент и конверсионные элементы.",
        )

    recommendations.sort(key=lambda item: (PRIORITY_ORDER[item["priority"]], item["code"]))
    return recommendations
