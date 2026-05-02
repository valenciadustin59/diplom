from app.recommendations import generate_recommendations, normalize_recommendations_payload


def flatten_codes(payload: dict[str, object]) -> set[str]:
    return {
        str(item["code"])
        for group in payload["groups"]
        for item in group["items"]
    }


def get_group(payload: dict[str, object], key: str) -> dict[str, object]:
    return next(group for group in payload["groups"] if group["key"] == key)


def test_generate_recommendations_returns_grouped_payload():
    page_features = {
        "title_present": 0,
        "meta_description_present": 0,
        "h1_count": 0,
        "query_in_title": 0,
        "query_in_text": 0,
        "keyword_coverage_ratio": 0.2,
        "semantic_similarity": 0.21,
        "text_length_chars": 650,
        "text_to_html_ratio": 0.07,
        "link_count": 2,
        "image_count": 0,
        "form_count": 0,
        "serp_relative_context_available": 1,
        "serp_relative_percentile": 0.22,
        "serp_relative_gap_score": 0.44,
        "relative_gap_to_top_semantic_relevance": -0.17,
        "relative_gap_to_top_technical_seo": -0.12,
        "relative_gap_to_top_commercial_trust": -0.15,
        "relative_gap_to_top_intent_alignment": -0.19,
    }
    competitor_pages_features = [
        {
            "text_length_chars": 2400,
            "link_count": 12,
            "image_count": 4,
            "form_count": 1,
            "semantic_similarity": 0.78,
            "keyword_coverage_ratio": 0.74,
            "intent_alignment_score": 0.71,
        },
        {
            "text_length_chars": 2600,
            "link_count": 10,
            "image_count": 3,
            "form_count": 1,
            "semantic_similarity": 0.81,
            "keyword_coverage_ratio": 0.77,
            "intent_alignment_score": 0.75,
        },
    ]

    recommendations = generate_recommendations(
        page_features=page_features,
        page_score=38.0,
        competitor_pages_features=competitor_pages_features,
    )

    assert recommendations["schema_version"] == "recommendations-v2"
    assert recommendations["summary"]["total_recommendations"] > 0
    assert recommendations["summary"]["competitor_context"] is True
    assert [group["key"] for group in recommendations["groups"]] == [
        "technical_seo",
        "commercial_trust",
        "semantic_intent",
        "competitor_gap",
    ]
    assert any(group["deviations"] for group in recommendations["groups"])

    semantic_group = get_group(recommendations, "semantic_intent")
    competitor_gap_group = get_group(recommendations, "competitor_gap")

    assert any(item["code"] == "LOW_PAGE_SCORE" for item in competitor_gap_group["items"])
    assert any(item["code"] == "MISSING_TITLE" for item in semantic_group["items"])
    assert any(item["code"] == "LOW_SEMANTIC_RELEVANCE" for item in semantic_group["items"])
    assert any(item["evidence"] for item in semantic_group["items"])
    assert any(deviation["trend"] == "behind" for deviation in competitor_gap_group["deviations"])


def test_generate_recommendations_skips_competitor_rules_with_single_competitor():
    page_features = {
        "title_present": 1,
        "query_in_title": 1,
        "meta_description_present": 1,
        "h1_count": 1,
        "query_in_text": 1,
        "keyword_coverage_ratio": 1.0,
        "semantic_similarity": 0.8,
        "text_length_chars": 2200,
        "text_to_html_ratio": 0.2,
        "link_count": 10,
        "image_count": 2,
        "form_count": 1,
    }
    competitor_pages_features = [
        {
            "text_length_chars": 2500,
            "link_count": 12,
            "image_count": 3,
            "form_count": 1,
        }
    ]

    recommendations = generate_recommendations(
        page_features=page_features,
        page_score=60.0,
        competitor_pages_features=competitor_pages_features,
    )

    codes = flatten_codes(recommendations)

    assert recommendations["summary"]["competitor_context"] is False
    assert "BELOW_COMPETITORS" not in codes
    assert "SLIGHTLY_BELOW_COMPETITORS" not in codes


def test_generate_recommendations_adds_technical_seo_recommendations():
    page_features = {
        "title_present": 1,
        "query_in_title": 1,
        "meta_description_present": 1,
        "h1_count": 1,
        "query_in_text": 1,
        "keyword_coverage_ratio": 1.0,
        "semantic_similarity": 0.82,
        "text_length_chars": 2200,
        "text_to_html_ratio": 0.22,
        "link_count": 12,
        "image_count": 2,
        "form_count": 1,
        "page_indexable": 0,
        "robots_noindex": 1,
        "canonical_present": 1,
        "canonical_matches_final_url": 0,
        "redirect_count": 2,
        "has_redirect": 1,
        "viewport_present": 0,
        "lang_present": 0,
        "url_has_query_parameters": 1,
        "url_parameter_count": 2,
        "url_depth": 5,
        "hreflang_present": 0,
    }
    competitor_pages_features = [
        {
            "text_length_chars": 2400,
            "link_count": 14,
            "image_count": 2,
            "form_count": 1,
            "canonical_present": 1,
            "hreflang_present": 1,
            "page_indexable": 1,
            "redirect_count": 0,
            "viewport_present": 1,
            "url_depth": 2,
        },
        {
            "text_length_chars": 2600,
            "link_count": 11,
            "image_count": 3,
            "form_count": 1,
            "canonical_present": 1,
            "hreflang_present": 1,
            "page_indexable": 1,
            "redirect_count": 0,
            "viewport_present": 1,
            "url_depth": 2,
        },
    ]

    recommendations = generate_recommendations(
        page_features=page_features,
        page_score=58.0,
        competitor_pages_features=competitor_pages_features,
    )
    technical_group = get_group(recommendations, "technical_seo")
    codes = {item["code"] for item in technical_group["items"]}

    assert technical_group["status"] == "critical"
    assert "TECHNICAL_INDEXING_BLOCK" in codes
    assert "TECHNICAL_CANONICAL_MISMATCH" in codes
    assert "TECHNICAL_REDIRECT_CHAIN" in codes
    assert "TECHNICAL_MISSING_VIEWPORT" in codes
    assert "TECHNICAL_MISSING_LANG" in codes
    assert "TECHNICAL_QUERY_PARAMETERS_IN_URL" in codes
    assert "TECHNICAL_DEEP_URL" in codes
    assert "TECHNICAL_MISSING_HREFLANG" in codes
    assert any(deviation["code"] == "page_indexable" for deviation in technical_group["deviations"])


def test_generate_recommendations_adds_commercial_and_trust_recommendations():
    page_features = {
        "title_present": 1,
        "query_in_title": 1,
        "meta_description_present": 1,
        "h1_count": 1,
        "query_in_text": 1,
        "keyword_coverage_ratio": 1.0,
        "semantic_similarity": 0.85,
        "text_length_chars": 2600,
        "text_to_html_ratio": 0.2,
        "link_count": 10,
        "image_count": 2,
        "form_count": 1,
        "phone_present": 0,
        "address_present": 0,
        "business_hours_present": 0,
        "price_present": 0,
        "delivery_info_present": 0,
        "payment_info_present": 0,
        "cta_present": 0,
        "messenger_present": 0,
        "value_proposition_present": 0,
        "reviews_present": 0,
        "rating_present": 0,
        "warranty_info_present": 0,
        "returns_info_present": 0,
        "legal_requisites_present": 0,
        "company_identity_present": 0,
        "contact_options_score": 0.0,
        "commercial_signals_score": 0.1,
        "trust_signals_score": 0.1,
    }
    competitor_pages_features = [
        {
            "phone_present": 1,
            "address_present": 1,
            "business_hours_present": 1,
            "price_present": 1,
            "delivery_info_present": 1,
            "payment_info_present": 1,
            "cta_present": 1,
            "messenger_present": 1,
            "value_proposition_present": 1,
            "reviews_present": 1,
            "rating_present": 1,
            "warranty_info_present": 1,
            "returns_info_present": 1,
            "legal_requisites_present": 1,
            "company_identity_present": 1,
            "contact_options_score": 0.84,
            "commercial_signals_score": 0.82,
            "trust_signals_score": 0.8,
            "price_present": 1,
        },
        {
            "phone_present": 1,
            "address_present": 1,
            "business_hours_present": 1,
            "price_present": 1,
            "delivery_info_present": 1,
            "payment_info_present": 1,
            "cta_present": 1,
            "messenger_present": 1,
            "value_proposition_present": 1,
            "reviews_present": 1,
            "rating_present": 1,
            "warranty_info_present": 1,
            "returns_info_present": 1,
            "legal_requisites_present": 1,
            "company_identity_present": 1,
            "contact_options_score": 0.78,
            "commercial_signals_score": 0.79,
            "trust_signals_score": 0.77,
            "price_present": 1,
        },
    ]

    recommendations = generate_recommendations(
        page_features=page_features,
        page_score=61.0,
        competitor_pages_features=competitor_pages_features,
    )
    commercial_group = get_group(recommendations, "commercial_trust")
    codes = {item["code"] for item in commercial_group["items"]}

    assert commercial_group["status"] == "critical"
    assert "COMMERCIAL_MISSING_PHONE" in codes
    assert "COMMERCIAL_MISSING_ADDRESS" in codes
    assert "COMMERCIAL_MISSING_BUSINESS_HOURS" in codes
    assert "COMMERCIAL_MISSING_PRICE_SIGNAL" in codes
    assert "COMMERCIAL_MISSING_DELIVERY_INFO" in codes
    assert "COMMERCIAL_MISSING_PAYMENT_INFO" in codes
    assert "COMMERCIAL_WEAK_CTA" in codes
    assert "COMMERCIAL_NO_MESSENGERS" in codes
    assert "COMMERCIAL_WEAK_VALUE_PROPOSITION" in codes
    assert "TRUST_WEAK_CONTACT_BLOCK" in codes
    assert "TRUST_MISSING_BUSINESS_ID" in codes
    assert "TRUST_MISSING_SOCIAL_PROOF" in codes
    assert "TRUST_MISSING_POST_SALE_INFO" in codes
    assert any(deviation["code"] == "contact_options_score" for deviation in commercial_group["deviations"])


def test_generate_recommendations_adds_intent_and_serp_relative_guidance():
    recommendations = generate_recommendations(
        page_features={
            "title_present": 1,
            "query_in_title": 1,
            "meta_description_present": 1,
            "h1_count": 1,
            "query_in_text": 1,
            "keyword_coverage_ratio": 0.72,
            "semantic_similarity": 0.74,
            "text_length_chars": 2200,
            "text_to_html_ratio": 0.2,
            "link_count": 8,
            "image_count": 2,
            "form_count": 1,
            "intent_alignment_score": 0.49,
            "intent_is_local_commercial": 1,
            "intent_is_commercial": 0,
            "intent_is_informational": 0,
            "local_intent_alignment": 0.42,
            "commercial_intent_alignment": 0.46,
            "serp_relative_context_available": 1,
            "serp_relative_percentile": 0.21,
            "serp_relative_gap_score": 0.41,
            "relative_gap_to_top_semantic_relevance": -0.18,
            "relative_gap_to_top_technical_seo": -0.14,
            "relative_gap_to_top_commercial_trust": -0.19,
            "relative_gap_to_top_intent_alignment": -0.23,
        },
        page_score=63.0,
        competitor_pages_features=[
            {
                "text_length_chars": 2400,
                "link_count": 11,
                "image_count": 3,
                "form_count": 1,
                "semantic_similarity": 0.81,
                "keyword_coverage_ratio": 0.77,
                "intent_alignment_score": 0.72,
            },
            {
                "text_length_chars": 2500,
                "link_count": 10,
                "image_count": 3,
                "form_count": 1,
                "semantic_similarity": 0.79,
                "keyword_coverage_ratio": 0.75,
                "intent_alignment_score": 0.7,
            },
        ],
    )
    codes = flatten_codes(recommendations)
    semantic_group = get_group(recommendations, "semantic_intent")
    competitor_gap_group = get_group(recommendations, "competitor_gap")

    assert "INTENT_WEAK_LOCAL_ALIGNMENT" in codes
    assert "RELATIVE_SERP_GAP" in codes
    assert "RELATIVE_SEMANTIC_GAP" in codes
    assert "RELATIVE_TECHNICAL_GAP" in codes
    assert "RELATIVE_COMMERCIAL_TRUST_GAP" in codes
    assert "RELATIVE_INTENT_ALIGNMENT_GAP" in codes
    assert semantic_group["status"] in {"attention", "critical"}
    assert competitor_gap_group["status"] == "critical"
    assert any(deviation["code"] == "serp_relative_gap_score" for deviation in competitor_gap_group["deviations"])


def test_competitor_deviation_priority_uses_metric_importance():
    recommendations = generate_recommendations(
        page_features={
            "title_present": 1,
            "query_in_title": 1,
            "h1_count": 1,
            "query_in_text": 1,
            "keyword_coverage_ratio": 0.78,
            "semantic_similarity": 0.42,
            "intent_alignment_score": 0.7,
            "text_length_chars": 2600,
            "text_to_html_ratio": 0.2,
            "link_count": 1,
            "image_count": 0,
        },
        page_score=70.0,
        competitor_pages_features=[
            {
                "semantic_similarity": 0.88,
                "keyword_coverage_ratio": 0.82,
                "intent_alignment_score": 0.75,
                "text_to_html_ratio": 0.22,
                "link_count": 12,
                "image_count": 6,
            },
            {
                "semantic_similarity": 0.86,
                "keyword_coverage_ratio": 0.8,
                "intent_alignment_score": 0.74,
                "text_to_html_ratio": 0.2,
                "link_count": 10,
                "image_count": 4,
            },
        ],
    )

    semantic_group = get_group(recommendations, "semantic_intent")
    deviations_by_code = {deviation["code"]: deviation for deviation in semantic_group["deviations"]}

    assert deviations_by_code["semantic_similarity"]["priority"] == "high"
    assert deviations_by_code["image_count"]["priority"] == "low"


def test_normalize_recommendations_payload_converts_legacy_list():
    legacy_payload = [
        {
            "code": "TECHNICAL_REDIRECT_CHAIN",
            "priority": "high",
            "message": "Legacy message",
        }
    ]

    normalized = normalize_recommendations_payload(legacy_payload)

    assert normalized is not None
    assert normalized["schema_version"] == "recommendations-v2"
    assert normalized["summary"]["total_recommendations"] == 1
    technical_group = get_group(normalized, "technical_seo")
    assert technical_group["items"][0]["code"] == "TECHNICAL_REDIRECT_CHAIN"
    assert technical_group["items"][0]["message"] == "Legacy message"
