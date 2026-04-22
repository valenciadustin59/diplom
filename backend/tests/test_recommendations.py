from app.recommendations import generate_recommendations


def test_generate_recommendations_returns_structured_list():
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
    }
    competitor_pages_features = [
        {
            "text_length_chars": 2400,
            "link_count": 12,
            "image_count": 4,
            "form_count": 1,
        },
        {
            "text_length_chars": 2600,
            "link_count": 10,
            "image_count": 3,
            "form_count": 1,
        },
    ]

    recommendations = generate_recommendations(
        page_features=page_features,
        page_score=38.0,
        competitor_pages_features=competitor_pages_features,
    )

    assert isinstance(recommendations, list)
    assert recommendations
    assert all(set(item.keys()) == {"code", "priority", "message"} for item in recommendations)
    assert any(item["code"] == "LOW_PAGE_SCORE" for item in recommendations)
    assert any(item["code"] == "MISSING_TITLE" for item in recommendations)
    assert any(item["code"] == "LOW_SEMANTIC_RELEVANCE" for item in recommendations)
    assert recommendations[0]["priority"] == "high"


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

    assert all(item["code"] not in {"BELOW_COMPETITORS", "SLIGHTLY_BELOW_COMPETITORS"} for item in recommendations)


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
        },
        {
            "text_length_chars": 2600,
            "link_count": 11,
            "image_count": 3,
            "form_count": 1,
            "canonical_present": 1,
            "hreflang_present": 1,
        },
    ]

    recommendations = generate_recommendations(
        page_features=page_features,
        page_score=58.0,
        competitor_pages_features=competitor_pages_features,
    )
    codes = {item["code"] for item in recommendations}

    assert "TECHNICAL_INDEXING_BLOCK" in codes
    assert "TECHNICAL_CANONICAL_MISMATCH" in codes
    assert "TECHNICAL_REDIRECT_CHAIN" in codes
    assert "TECHNICAL_MISSING_VIEWPORT" in codes
    assert "TECHNICAL_MISSING_LANG" in codes
    assert "TECHNICAL_QUERY_PARAMETERS_IN_URL" in codes
    assert "TECHNICAL_DEEP_URL" in codes
    assert "TECHNICAL_MISSING_HREFLANG" in codes
