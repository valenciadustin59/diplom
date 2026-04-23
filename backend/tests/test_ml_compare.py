from app.ml import compare_with_competitors, explain_score


def test_compare_with_competitors_returns_score_difference():
    user_pages_features = [
        {
            "text_length_chars": 5000,
            "html_length_chars": 9000,
            "word_count": 800,
            "unique_word_count": 500,
            "unique_word_ratio": 0.625,
            "avg_word_length": 5.5,
            "sentence_count": 35,
            "avg_sentence_length": 22.8,
            "paragraph_count": 12,
            "h1_count": 1,
            "h2_count": 6,
            "h3_count": 3,
            "title_present": 1,
            "title_length": 55,
            "meta_description_present": 1,
            "meta_description_length": 150,
            "query_in_title": 1,
            "query_in_text": 1,
            "exact_query_count": 3,
            "query_term_count": 10,
            "query_density": 0.03,
            "keyword_coverage_ratio": 0.9,
            "link_count": 18,
            "image_count": 8,
            "list_item_count": 6,
            "strong_tag_count": 5,
            "form_count": 1,
            "input_count": 3,
            "text_to_html_ratio": 0.55,
        }
    ]

    competitor_pages_features = [
        {
            "text_length_chars": 3000,
            "html_length_chars": 8500,
            "word_count": 500,
            "unique_word_count": 260,
            "unique_word_ratio": 0.52,
            "avg_word_length": 5.1,
            "sentence_count": 28,
            "avg_sentence_length": 17.8,
            "paragraph_count": 9,
            "h1_count": 1,
            "h2_count": 3,
            "h3_count": 2,
            "title_present": 1,
            "title_length": 48,
            "meta_description_present": 1,
            "meta_description_length": 120,
            "query_in_title": 0,
            "query_in_text": 1,
            "exact_query_count": 1,
            "query_term_count": 4,
            "query_density": 0.01,
            "keyword_coverage_ratio": 0.5,
            "link_count": 10,
            "image_count": 4,
            "list_item_count": 2,
            "strong_tag_count": 1,
            "form_count": 0,
            "input_count": 0,
            "text_to_html_ratio": 0.35,
        },
        {
            "text_length_chars": 3200,
            "html_length_chars": 8700,
            "word_count": 540,
            "unique_word_count": 290,
            "unique_word_ratio": 0.537,
            "avg_word_length": 5.0,
            "sentence_count": 29,
            "avg_sentence_length": 18.6,
            "paragraph_count": 10,
            "h1_count": 1,
            "h2_count": 4,
            "h3_count": 2,
            "title_present": 1,
            "title_length": 50,
            "meta_description_present": 1,
            "meta_description_length": 125,
            "query_in_title": 0,
            "query_in_text": 1,
            "exact_query_count": 1,
            "query_term_count": 5,
            "query_density": 0.012,
            "keyword_coverage_ratio": 0.55,
            "link_count": 12,
            "image_count": 5,
            "list_item_count": 3,
            "strong_tag_count": 2,
            "form_count": 0,
            "input_count": 1,
            "text_to_html_ratio": 0.37,
        },
    ]

    result = compare_with_competitors(user_pages_features, competitor_pages_features)

    assert len(result["user_scores"]) == 1
    assert len(result["competitor_scores"]) == 2
    assert isinstance(result["user_average_score"], float)
    assert isinstance(result["competitors_average_score"], float)
    assert result["score_difference"] == round(
        result["user_average_score"] - result["competitors_average_score"],
        4,
    )


def test_explain_score_includes_serp_relative_factors_when_context_is_available():
    explanation = explain_score(
        {
            "word_count": 900,
            "title_present": 1,
            "title_length_quality": 0.9,
            "meta_description_present": 1,
            "meta_length_quality": 0.85,
            "heading_count": 6,
            "semantic_similarity": 0.81,
            "keyword_coverage_ratio": 0.78,
            "title_semantic_alignment": 0.72,
            "heading_semantic_alignment": 0.69,
            "content_depth_semantic_score": 0.74,
            "semantic_content_richness": 0.71,
            "keyword_balance_score": 0.65,
            "conversion_signal_score": 0.5,
            "query_prominence_score": 0.7,
            "text_to_html_ratio": 0.22,
            "unique_word_ratio": 0.66,
            "serp_relative_context_available": 1,
            "relative_gap_to_top_semantic_relevance": -0.18,
            "relative_percentile_semantic_relevance": 0.2,
            "relative_gap_to_top_commercial_trust": -0.11,
            "relative_percentile_commercial_trust": 0.3,
        }
    )

    assert any(item["key"] == "relative_semantic_relevance" for item in explanation["serp_relative_factors"])
