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
