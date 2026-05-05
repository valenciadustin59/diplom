from app.competitors import _build_competitor_analysis_text
from app.features import build_features
from app.query_relevance import has_strong_query_topic_fit


def test_competitor_serp_context_protects_relevant_page_with_thin_fetch_text(monkeypatch):
    monkeypatch.setattr(
        "app.features.build_semantic_features",
        lambda text, query: {"semantic_similarity": 0.2},
    )
    query = "\u043a\u043e\u0437\u043b\u043e\u0432\u043e\u0439 \u043a\u0440\u0430\u043d \u043a\u0443\u043f\u0438\u0442\u044c"
    result = {
        "url": "https://example.com/category/krany-kozlovye/",
        "title": "\u041a\u0440\u0430\u043d \u043a\u043e\u0437\u043b\u043e\u0432\u043e\u0439 \u043a\u0443\u043f\u0438\u0442\u044c",
        "snippet": (
            "\u041a\u043e\u0437\u043b\u043e\u0432\u043e\u0439 \u043a\u0440\u0430\u043d "
            "\u0434\u043b\u044f \u0441\u043a\u043b\u0430\u0434\u0430, "
            "\u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434\u0441\u0442\u0432\u0430 "
            "\u0438 \u043c\u043e\u043d\u0442\u0430\u0436\u043d\u044b\u0445 "
            "\u0440\u0430\u0431\u043e\u0442."
        ),
    }
    analysis_text = _build_competitor_analysis_text(
        "\u0417\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u043a\u0430\u0442\u0430\u043b\u043e\u0433\u0430",
        result,
    )

    features = build_features(
        html="<html><body>Loading catalog</body></html>",
        text=analysis_text,
        query=query,
    )

    assert features["query_core_keyword_coverage_ratio"] == 1.0
    assert features["query_intent_modifier_coverage_ratio"] == 1.0
    assert has_strong_query_topic_fit(features) is True
