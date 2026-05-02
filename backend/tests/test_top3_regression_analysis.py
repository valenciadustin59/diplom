from __future__ import annotations

from datetime import UTC, datetime

from app.ml.top3_regression_analysis import (
    build_top3_regression_report_from_predictions,
    classify_failure_patterns,
)


def _row(query: str, url: str, rank: int, *, word_count: int, semantic: float, technical: float = 1.0) -> dict[str, str]:
    return {
        "query": query,
        "url": url,
        "domain": url.split("//", 1)[-1].split("/", 1)[0],
        "rank": str(rank),
        "target_score": str(90 - rank),
        "intent": "commercial",
        "label_source": "seo_weighted_rubric_v4",
        "word_count": str(word_count),
        "text_length_chars": str(word_count * 6),
        "paragraph_count": str(max(1, word_count // 120)),
        "sentence_count": str(max(1, word_count // 30)),
        "semantic_similarity": str(semantic),
        "query_semantic_alignment": str(semantic),
        "keyword_coverage_ratio": str(semantic),
        "intent_alignment_score": str(semantic),
        "technical_seo_score": str(technical),
        "canonical_signal_score": str(technical),
        "page_indexable": str(technical),
        "commercial_signal_score": "0.4",
    }


def test_classify_failure_patterns_detects_text_volume_and_semantic_mismatch() -> None:
    lost_rows = [
        _row("q", "https://good.example/a", 1, word_count=600, semantic=0.9),
        _row("q", "https://good.example/b", 2, word_count=700, semantic=0.85),
    ]
    promoted_rows = [
        _row("q", "https://thin-but-long.example/a", 8, word_count=2400, semantic=0.2),
    ]

    patterns = classify_failure_patterns(
        lost_rows=lost_rows,
        promoted_rows=promoted_rows,
        candidate_top_feature="word_count",
        candidate_top_feature_group="supporting",
    )

    assert "shortcut_text_volume" in patterns
    assert "semantic_or_intent_mismatch" in patterns
    assert "rank_prior_disagreement" in patterns


def test_build_top3_regression_report_identifies_candidate_query_loss() -> None:
    rows = [
        _row("query-a", "https://a.example/1", 1, word_count=600, semantic=0.9),
        _row("query-a", "https://a.example/2", 2, word_count=650, semantic=0.85),
        _row("query-a", "https://a.example/3", 3, word_count=700, semantic=0.8),
        _row("query-a", "https://market.example/4", 4, word_count=2500, semantic=0.3),
        _row("query-a", "https://market.example/5", 5, word_count=2600, semantic=0.25),
        _row("query-a", "https://market.example/6", 6, word_count=2700, semantic=0.2),
        _row("query-b", "https://b.example/1", 1, word_count=900, semantic=0.75),
        _row("query-b", "https://b.example/2", 2, word_count=800, semantic=0.74),
        _row("query-b", "https://b.example/3", 3, word_count=700, semantic=0.73),
        _row("query-b", "https://b.example/4", 4, word_count=600, semantic=0.72),
    ]
    predictions_by_model = {
        "reference": [99, 10, 9, 8, 7, 6, 80, 79, 78, 1],
        "candidate": [1, 2, 3, 99, 98, 97, 80, 79, 78, 1],
    }
    d48_report = {
        "product_guardrails": {
            "candidate": {
                "feature_importance_guardrail": {
                    "top_feature": "word_count",
                    "top_feature_group": "supporting",
                }
            }
        }
    }

    report = build_top3_regression_report_from_predictions(
        validation_rows=rows,
        predictions_by_model=predictions_by_model,
        reference_model_name="reference",
        candidate_model_names=["candidate"],
        d48_report=d48_report,
        production_sha1="prod-sha",
        generated_at=datetime(2026, 5, 2, 12, 0, tzinfo=UTC),
    )

    candidate_summary = report["candidate_summaries"]["candidate"]
    assert report["summary"]["total_candidate_query_regressions"] == 1
    assert candidate_summary["regressed_queries_count"] == 1
    assert candidate_summary["same_hit_queries_count"] == 1
    assert candidate_summary["patterns"]["shortcut_text_volume"] == 1
    assert report["query_diagnostics"][0]["query"] == "query-a"
    assert report["query_diagnostics"][0]["candidate_top3_hit"] is False
    assert report["production_artifact"]["unchanged_by_d50"] is True
