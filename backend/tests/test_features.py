from app.features import build_features, build_technical_seo_features, merge_technical_seo_features


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
