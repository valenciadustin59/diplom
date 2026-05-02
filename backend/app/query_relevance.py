from __future__ import annotations

from collections.abc import Mapping


QUERY_RELEVANCE_GUARDRAIL_VERSION = "query-relevance-guardrail-v1"
SEMANTIC_LIMITING_FACTOR_KEYS = frozenset(
    {
        "semantic_relevance",
        "content_depth_semantic_score",
        "semantic_content_richness",
    }
)


def _bounded_signal(value: float) -> float:
    return max(0.0, min(1.0, value))


def _feature_value(features: Mapping[str, object], key: str) -> float:
    value = features.get(key, 0.0)
    return float(value) if isinstance(value, (int, float)) else 0.0


def build_query_topic_metrics(features: Mapping[str, object]) -> dict[str, float]:
    semantic_similarity = _bounded_signal(_feature_value(features, "semantic_similarity"))
    keyword_coverage = _bounded_signal(_feature_value(features, "keyword_coverage_ratio"))
    query_density = max(0.0, _feature_value(features, "query_density"))
    query_in_title = _bounded_signal(_feature_value(features, "query_in_title"))
    query_in_text = _bounded_signal(_feature_value(features, "query_in_text"))
    exact_query_count = max(0.0, _feature_value(features, "exact_query_count"))
    title_semantic_alignment = _bounded_signal(_feature_value(features, "title_semantic_alignment"))
    heading_semantic_alignment = _bounded_signal(_feature_value(features, "heading_semantic_alignment"))
    query_prominence = _bounded_signal(_feature_value(features, "query_prominence_score"))

    density_signal = _bounded_signal(query_density / 0.01)
    exact_or_structural_signal = max(
        _bounded_signal(exact_query_count),
        query_in_title,
        query_in_text,
        title_semantic_alignment,
        heading_semantic_alignment,
    )
    relevance_score = _bounded_signal(
        (keyword_coverage * 0.35)
        + (semantic_similarity * 0.25)
        + (density_signal * 0.20)
        + (max(exact_or_structural_signal, query_prominence) * 0.20)
    )

    return {
        "relevance_score": round(relevance_score, 4),
        "semantic_similarity": round(semantic_similarity, 4),
        "keyword_coverage_ratio": round(keyword_coverage, 4),
        "query_density": round(query_density, 6),
        "density_signal": round(density_signal, 4),
        "exact_or_structural_signal": round(exact_or_structural_signal, 4),
        "query_prominence_score": round(query_prominence, 4),
    }


def has_strong_query_topic_fit(features: Mapping[str, object]) -> bool:
    metrics = build_query_topic_metrics(features)
    return (
        metrics["relevance_score"] >= 0.58
        and metrics["keyword_coverage_ratio"] >= 0.8
        and (metrics["density_signal"] >= 0.75 or metrics["query_prominence_score"] >= 0.45)
    )


def build_query_relevance_guardrail(features: Mapping[str, object], score: float) -> dict[str, object]:
    metrics = build_query_topic_metrics(features)
    semantic_similarity = metrics["semantic_similarity"]
    keyword_coverage = metrics["keyword_coverage_ratio"]
    query_density = metrics["query_density"]
    exact_or_structural_signal = metrics["exact_or_structural_signal"]
    relevance_score = metrics["relevance_score"]

    reason: str | None = None
    cap: float | None = None
    if (
        relevance_score < 0.28
        and keyword_coverage < 0.5
        and semantic_similarity < 0.38
        and exact_or_structural_signal < 0.15
        and query_density < 0.002
    ):
        reason = "severe_query_topic_mismatch"
        cap = 42.0
    elif (
        relevance_score < 0.42
        and keyword_coverage < 0.67
        and semantic_similarity < 0.45
        and exact_or_structural_signal < 0.2
        and query_density < 0.004
    ):
        reason = "weak_query_topic_match"
        cap = 58.0

    adjusted_score = round(max(0.0, min(100.0, min(score, cap))), 4) if cap is not None else score
    return {
        "schema_version": QUERY_RELEVANCE_GUARDRAIL_VERSION,
        "active": cap is not None and adjusted_score < score,
        "reason": reason,
        "cap": cap,
        "original_score": score,
        "adjusted_score": adjusted_score,
        "score_delta": round(adjusted_score - score, 4),
        "metrics": metrics,
    }
