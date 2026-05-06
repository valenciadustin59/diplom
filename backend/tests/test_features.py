from app.features import (
    build_intent_alignment_features,
    build_commercial_trust_features,
    build_features,
    detect_query_intent,
    build_technical_seo_features,
    merge_serp_relative_features,
    merge_technical_seo_features,
)


def test_build_features_includes_semantic_fields(monkeypatch):
    def fake_semantic_features(text: str, query: str) -> dict[str, float | int]:
        assert text == "Main page text"
        assert query == "plastic windows"
        return {
            "semantic_similarity": 0.812345,
        }

    monkeypatch.setattr("app.features.build_semantic_features", fake_semantic_features)

    features = build_features(
        html="<html><head><title>Test</title></head><body><h1>Hello</h1><a href='/'>link</a></body></html>",
        text="Main page text",
        query="plastic windows",
    )

    assert features["semantic_similarity"] == 0.812345
    assert "heading_count" in features
    assert "title_query_term_count" in features
    assert "title_keyword_coverage_ratio" in features
    assert "meta_keyword_coverage_ratio" in features
    assert "heading_query_coverage_ratio" in features
    assert "first_200_words_query_term_count" in features
    assert "inputs_per_form_ratio" in features
    assert "avg_paragraph_length" in features
    assert "link_density_per_1000_words" in features
    assert "query_semantic_alignment" in features
    assert "title_semantic_alignment" in features
    assert "heading_semantic_alignment" in features
    assert "query_prominence_score" in features
    assert "keyword_balance_score" in features
    assert "semantic_content_richness" in features
    assert "cta_semantic_score" in features


def test_build_features_reuses_valid_semantic_features(monkeypatch):
    def fail_semantic_features(text: str, query: str) -> dict[str, float | int]:
        raise AssertionError("semantic features should be reused from the semantic queue payload")

    monkeypatch.setattr("app.features.build_semantic_features", fail_semantic_features)

    features = build_features(
        html="<html><head><title>Plastic windows</title></head><body><h1>Plastic windows</h1></body></html>",
        text="Plastic windows installation and service",
        query="plastic windows",
        semantic_features={
            "semantic_similarity": 0.72,
            "semantic_similarity_raw": 0.66,
            "semantic_provider_code": 2,
            "semantic_model_code": 2,
            "semantic_fallback_used": 0,
            "semantic_embedding_failure": 0,
        },
    )

    assert features["semantic_similarity"] == 0.72
    assert features["semantic_similarity_raw"] == 0.66
    assert features["semantic_provider_code"] == 2
    assert features["query_semantic_alignment"] > 0
    assert features["title_semantic_alignment"] > 0


def test_build_features_treats_informational_phrase_as_modifier(monkeypatch):
    monkeypatch.setattr(
        "app.features.build_semantic_features",
        lambda text, query: {
            "semantic_similarity": 0.74,
            "semantic_similarity_raw": 0.71,
            "semantic_provider_code": 2,
            "semantic_model_code": 2,
            "semantic_fallback_used": 0,
            "semantic_embedding_failure": 0,
        },
    )

    features = build_features(
        html="<html><head><title>Фотосинтез</title></head><body><h1>Фотосинтез</h1></body></html>",
        text="Фотосинтез - процесс образования органических веществ растениями на свету.",
        query="что такое фотосинтез",
    )

    assert features["query_core_keyword_coverage_ratio"] == 1.0
    assert features["query_primary_core_term_present"] == 1
    assert features["query_core_term_matches"] == 1
    assert features["query_intent_modifier_coverage_ratio"] == 0.0
    assert features["modifier_or_geo_only_match"] == 0


def test_build_technical_seo_features_from_snapshot():
    snapshot = {
        "requested_url": "https://example.com/catalog?utm_source=ads",
        "final_url": "https://example.com/catalog?utm_source=ads",
        "status_code": 200,
        "response_headers": {"X-Robots-Tag": "googlebot: nofollow"},
        "redirect_chain": [{"url": "https://example.com/catalog", "status_code": 301}],
        "html": (
            "<html lang='ru'><head>"
            "<link rel='canonical' href='https://example.com/catalog'>"
            "<meta name='robots' content='index,follow'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            "<link rel='alternate' hreflang='ru' href='https://example.com/ru/catalog'>"
            "</head><body><p>Каталог</p></body></html>"
        ),
        "text": "Каталог",
        "json_ld": [],
    }

    features = build_technical_seo_features(snapshot)
    merged = merge_technical_seo_features({"semantic_similarity": 0.82}, snapshot)

    assert features["http_status_code"] == 200
    assert features["http_status_ok"] == 1
    assert features["redirect_count"] == 1
    assert features["has_redirect"] == 1
    assert features["canonical_present"] == 1
    assert features["canonical_matches_final_url"] == 1
    assert features["x_robots_tag_present"] == 1
    assert features["robots_nofollow"] == 1
    assert features["page_indexable"] == 1
    assert features["viewport_present"] == 1
    assert features["lang_present"] == 1
    assert features["hreflang_count"] == 1
    assert features["hreflang_present"] == 1
    assert features["url_parameter_count"] == 1
    assert features["url_has_query_parameters"] == 1
    assert 0.0 < float(features["technical_seo_score"]) <= 1.0
    assert merged["semantic_similarity"] == 0.82
    assert merged["technical_seo_score"] == features["technical_seo_score"]


def test_build_commercial_trust_features_from_snapshot():
    snapshot = {
        "requested_url": "https://example.com/services/windows",
        "final_url": "https://example.com/services/windows",
        "status_code": 200,
        "response_headers": {},
        "redirect_chain": [],
        "html": (
            "<html lang='ru'><head>"
            "<script type='application/ld+json'>"
            '{"@context":"https://schema.org","@type":"Organization","telephone":"+7 (999) 000-00-00","address":{"@type":"PostalAddress","streetAddress":"ул. Ленина, 10"}}'
            "</script>"
            "<script type='application/ld+json'>"
            '{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[]}'
            "</script>"
            "</head><body>"
            "<section class='hero'>"
            "<p>Телефон: +7 (999) 000-00-00</p>"
            "<p>Адрес: г. Москва, ул. Ленина, 10</p>"
            "<p>Режим работы: пн-пт 09:00-18:00</p>"
            "<p>Цена от 9 900 ₽</p>"
            "<p>Доставка и оплата по договору</p>"
            "<p>Гарантия 2 года, возврат в течение 14 дней</p>"
            "<p>Отзывы клиентов и рейтинг 4.9</p>"
            "<p>Скидка и бесплатный замер от производителя</p>"
            "<a href='https://t.me/example'>Telegram</a>"
            "<a href='mailto:info@example.com'>info@example.com</a>"
            "<button>Оставить заявку</button>"
            "<div>ИНН 7701234567, ОГРН 1027700123456</div>"
            "</section>"
            "</body></html>"
        ),
        "text": (
            "Телефон +7 (999) 000-00-00 Адрес Москва улица Ленина 10 Режим работы пн-пт 09:00-18:00 "
            "Цена от 9 900 ₽ Доставка и оплата Гарантия 2 года Возврат 14 дней Отзывы клиентов Рейтинг 4.9 "
            "Скидка бесплатный замер ИНН 7701234567"
        ),
        "json_ld": [],
    }

    features = build_commercial_trust_features(snapshot)

    assert features["phone_present"] == 1
    assert features["phone_count"] >= 1
    assert features["email_present"] == 1
    assert features["address_present"] == 1
    assert features["business_hours_present"] == 1
    assert features["price_present"] == 1
    assert features["currency_present"] == 1
    assert features["delivery_info_present"] == 1
    assert features["payment_info_present"] == 1
    assert features["warranty_info_present"] == 1
    assert features["returns_info_present"] == 1
    assert features["reviews_present"] == 1
    assert features["rating_present"] == 1
    assert features["faq_present"] == 1
    assert features["cta_present"] == 1
    assert features["cta_count"] >= 1
    assert features["messenger_present"] == 1
    assert features["value_proposition_present"] == 1
    assert features["legal_requisites_present"] == 1
    assert features["company_identity_present"] == 1
    assert float(features["contact_options_score"]) > 0.5
    assert float(features["commercial_signals_score"]) > 0.6
    assert float(features["trust_signals_score"]) > 0.6
    assert float(features["commercial_trust_score"]) > 0.6


def test_detect_query_intent_and_build_alignment_features_for_local_commercial_query():
    query_intent = detect_query_intent("купить пластиковые окна москва")

    features = build_intent_alignment_features(
        {
            "semantic_similarity": 0.83,
            "query_semantic_alignment": 0.78,
            "query_prominence_score": 0.74,
            "keyword_coverage_ratio": 0.8,
            "commercial_signals_score": 0.82,
            "contact_options_score": 0.75,
            "conversion_signal_score": 0.65,
            "cta_semantic_score": 0.72,
            "address_present": 1,
            "business_hours_present": 1,
            "phone_present": 1,
            "content_depth_semantic_score": 0.66,
            "semantic_content_richness": 0.61,
            "heading_count": 6,
            "faq_present": 1,
            "technical_seo_score": 0.88,
            "title_semantic_alignment": 0.79,
            "heading_semantic_alignment": 0.74,
        },
        query_intent,
    )

    assert query_intent["label"] == "local_commercial"
    assert features["intent_is_local_commercial"] == 1
    assert float(features["local_intent_alignment"]) > 0.7
    assert float(features["intent_alignment_score"]) > 0.7


def test_detect_query_intent_does_not_mark_plain_commercial_query_as_local():
    query_intent = detect_query_intent("купить пластиковые окна")

    assert query_intent["label"] == "commercial"
    assert float(query_intent["scores"]["local"]) < 0.2


def test_detect_query_intent_marks_informational_query_without_local_false_positive():
    query_intent = detect_query_intent("как выбрать пластиковые окна")

    assert query_intent["label"] == "informational"
    assert float(query_intent["scores"]["local"]) < 0.2


def test_detect_query_intent_marks_navigational_query_without_local_false_positive():
    query_intent = detect_query_intent("официальный сайт rehau")

    assert query_intent["label"] == "navigational"
    assert float(query_intent["scores"]["local"]) < 0.2


def test_merge_serp_relative_features_builds_gaps_and_fallbacks_with_single_competitor():
    merged, summary = merge_serp_relative_features(
        {
            "semantic_similarity": 0.62,
            "query_semantic_alignment": 0.54,
            "title_semantic_alignment": 0.51,
            "heading_semantic_alignment": 0.48,
            "keyword_coverage_ratio": 0.58,
            "query_prominence_score": 0.56,
            "title_heading_keyword_alignment": 0.5,
            "early_query_coverage_ratio": 0.55,
            "content_depth_semantic_score": 0.52,
            "semantic_content_richness": 0.5,
            "conversion_signal_score": 0.45,
            "technical_seo_score": 0.63,
            "technical_metadata_score": 0.58,
            "canonical_signal_score": 0.61,
            "url_hygiene_score": 0.57,
            "commercial_trust_score": 0.44,
            "commercial_signals_score": 0.4,
            "trust_signals_score": 0.42,
            "contact_options_score": 0.39,
            "intent_alignment_score": 0.5,
            "commercial_intent_alignment": 0.52,
            "local_intent_alignment": 0.46,
            "informational_intent_alignment": 0.44,
            "navigational_intent_alignment": 0.41,
        },
        [
            {
                "semantic_similarity": 0.8,
                "query_semantic_alignment": 0.74,
                "title_semantic_alignment": 0.69,
                "heading_semantic_alignment": 0.67,
                "keyword_coverage_ratio": 0.76,
                "query_prominence_score": 0.71,
                "title_heading_keyword_alignment": 0.7,
                "early_query_coverage_ratio": 0.68,
                "content_depth_semantic_score": 0.73,
                "semantic_content_richness": 0.75,
                "conversion_signal_score": 0.64,
                "technical_seo_score": 0.8,
                "technical_metadata_score": 0.76,
                "canonical_signal_score": 0.74,
                "url_hygiene_score": 0.72,
                "commercial_trust_score": 0.78,
                "commercial_signals_score": 0.74,
                "trust_signals_score": 0.76,
                "contact_options_score": 0.7,
                "intent_alignment_score": 0.79,
                "commercial_intent_alignment": 0.77,
                "local_intent_alignment": 0.75,
                "informational_intent_alignment": 0.65,
                "navigational_intent_alignment": 0.58,
            }
        ],
    )

    assert merged["serp_relative_context_available"] == 1
    assert merged["serp_relative_context_count"] == 1
    assert merged["serp_relative_group_count"] >= 4
    assert float(merged["relative_gap_to_top_semantic_relevance"]) < 0.0
    assert float(merged["relative_z_score_semantic_relevance"]) == 0.0
    assert summary["context_count"] == 1
    assert "semantic_relevance" in summary["groups"]

    empty_merged, empty_summary = merge_serp_relative_features({"semantic_similarity": 0.5}, [])

    assert empty_merged["serp_relative_context_available"] == 0
    assert empty_merged["serp_relative_group_count"] == 0
    assert empty_summary["context_available"] == 0
