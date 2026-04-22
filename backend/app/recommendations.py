from __future__ import annotations

from app.ml import average_score


PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
MIN_COMPETITORS_FOR_RECOMMENDATIONS = 2
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
    has_technical_context = any(_has_feature(page_features, key) for key in TECHNICAL_FEATURE_KEYS)
    has_commercial_trust_context = any(_has_feature(page_features, key) for key in COMMERCIAL_TRUST_FEATURE_KEYS)

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

    if not recommendations:
        add_recommendation(
            "NO_CRITICAL_ISSUES",
            "low",
            "Критичных проблем не найдено. Можно точечно усиливать контент, коммерческие блоки, trust-сигналы и техническую базу.",
        )

    recommendations.sort(key=lambda item: (PRIORITY_ORDER[item["priority"]], item["code"]))
    return recommendations
