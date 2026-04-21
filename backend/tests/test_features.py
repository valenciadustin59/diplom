from app.features import build_features


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
