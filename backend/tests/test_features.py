from app.features import (
    build_commercial_trust_features,
    build_features,
    build_technical_seo_features,
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
