from __future__ import annotations

from collections.abc import Mapping


QUERY_RELEVANCE_GUARDRAIL_VERSION = "query-relevance-contract-v2"
QUERY_RELEVANCE_EARLY_STOP_VERSION = "query-relevance-early-stop-v1"
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


def _has_numeric_feature(features: Mapping[str, object], key: str) -> bool:
    return isinstance(features.get(key), (int, float))


def _page_unusable_reasons(features: Mapping[str, object]) -> list[str]:
    reasons: list[str] = []
    http_status_code = _feature_value(features, "http_status_code")
    if http_status_code >= 100.0 and _feature_value(features, "http_status_ok") < 0.5:
        reasons.append("http_status_not_ok")
    if _has_numeric_feature(features, "page_indexable") and _feature_value(features, "page_indexable") < 0.5:
        reasons.append("page_not_indexable")
    if _has_numeric_feature(features, "robots_noindex") and _feature_value(features, "robots_noindex") > 0.5:
        reasons.append("robots_noindex")
    if (
        _has_numeric_feature(features, "word_count")
        and _has_numeric_feature(features, "text_length_chars")
        and _feature_value(features, "word_count") < 20.0
        and _feature_value(features, "text_length_chars") < 200.0
    ):
        reasons.append("empty_or_too_thin_content")
    return reasons


def _multiplied_score(score: float, multiplier: float) -> float:
    return round(max(0.0, min(100.0, score * _bounded_signal(multiplier))), 4)


def _banded_score(score: float, multiplier: float, band_max: float | None) -> float:
    adjusted_score = _multiplied_score(score, multiplier)
    if band_max is None:
        return adjusted_score
    return round(max(0.0, min(float(band_max), adjusted_score)), 4)


def build_query_topic_metrics(features: Mapping[str, object]) -> dict[str, float]:
    semantic_similarity = _bounded_signal(_feature_value(features, "semantic_similarity"))
    keyword_coverage = _bounded_signal(_feature_value(features, "keyword_coverage_ratio"))
    core_keyword_coverage = _bounded_signal(
        _feature_value(features, "query_core_keyword_coverage_ratio")
        if "query_core_keyword_coverage_ratio" in features
        else keyword_coverage
    )
    intent_modifier_coverage = _bounded_signal(_feature_value(features, "query_intent_modifier_coverage_ratio"))
    query_density = max(0.0, _feature_value(features, "query_density"))
    word_count = max(0.0, _feature_value(features, "word_count"))
    core_query_density = (
        max(0.0, _feature_value(features, "query_core_term_count")) / word_count
        if word_count > 0.0 and "query_core_term_count" in features
        else query_density
    )
    query_in_title = _bounded_signal(_feature_value(features, "query_in_title"))
    query_in_text = _bounded_signal(_feature_value(features, "query_in_text"))
    exact_query_count = max(0.0, _feature_value(features, "exact_query_count"))
    title_semantic_alignment = _bounded_signal(_feature_value(features, "title_semantic_alignment"))
    heading_semantic_alignment = _bounded_signal(_feature_value(features, "heading_semantic_alignment"))
    query_prominence = _bounded_signal(_feature_value(features, "query_prominence_score"))
    title_heading_signal = max(query_in_title, title_semantic_alignment, heading_semantic_alignment)

    density_signal = _bounded_signal(query_density / 0.01)
    core_density_signal = _bounded_signal(core_query_density / 0.008)
    exact_or_structural_signal = max(
        _bounded_signal(exact_query_count),
        query_in_title,
        query_in_text,
        title_semantic_alignment,
        heading_semantic_alignment,
    )
    relevance_score = _bounded_signal(
        (core_keyword_coverage * 0.38)
        + (semantic_similarity * 0.22)
        + (keyword_coverage * 0.10)
        + (core_density_signal * 0.15)
        + (max(exact_or_structural_signal, query_prominence) * 0.15)
    )

    return {
        "relevance_score": round(relevance_score, 4),
        "semantic_similarity": round(semantic_similarity, 4),
        "keyword_coverage_ratio": round(keyword_coverage, 4),
        "query_core_keyword_coverage_ratio": round(core_keyword_coverage, 4),
        "query_intent_modifier_coverage_ratio": round(intent_modifier_coverage, 4),
        "query_density": round(query_density, 6),
        "query_core_density": round(core_query_density, 6),
        "exact_query_count": round(exact_query_count, 4),
        "query_in_title": round(query_in_title, 4),
        "query_in_text": round(query_in_text, 4),
        "title_semantic_alignment": round(title_semantic_alignment, 4),
        "heading_semantic_alignment": round(heading_semantic_alignment, 4),
        "title_heading_signal": round(title_heading_signal, 4),
        "density_signal": round(density_signal, 4),
        "core_density_signal": round(core_density_signal, 4),
        "exact_or_structural_signal": round(exact_or_structural_signal, 4),
        "query_prominence_score": round(query_prominence, 4),
    }


def has_strong_query_topic_fit(features: Mapping[str, object]) -> bool:
    metrics = build_query_topic_metrics(features)
    return (
        metrics["relevance_score"] >= 0.58
        and metrics["query_core_keyword_coverage_ratio"] >= 0.75
        and (
            metrics["core_density_signal"] >= 0.5
            or metrics["query_prominence_score"] >= 0.45
            or metrics["exact_or_structural_signal"] >= 0.65
        )
    )


def _content_evaluable_for_query(features: Mapping[str, object]) -> bool:
    if _has_numeric_feature(features, "http_status_ok") and _feature_value(features, "http_status_ok") < 0.5:
        return False
    word_count = _feature_value(features, "word_count")
    text_length_chars = _feature_value(features, "text_length_chars")
    return word_count >= 80.0 or text_length_chars >= 500.0


def build_query_relevance_preflight_decision(features: Mapping[str, object]) -> dict[str, object]:
    metrics = build_query_topic_metrics(features)
    strong_topic_fit = has_strong_query_topic_fit(features)
    content_evaluable = _content_evaluable_for_query(features)
    unusable_reasons = _page_unusable_reasons(features)
    confident_full_mismatch = (
        content_evaluable
        and not unusable_reasons
        and not strong_topic_fit
        and metrics["relevance_score"] <= 0.15
        and metrics["semantic_similarity"] <= 0.22
        and metrics["query_core_keyword_coverage_ratio"] <= 0.05
        and metrics["query_core_density"] <= 0.0008
        and metrics["exact_query_count"] <= 0.0
        and metrics["title_heading_signal"] <= 0.05
        and metrics["query_prominence_score"] <= 0.08
    )
    if confident_full_mismatch:
        return {
            "schema_version": QUERY_RELEVANCE_EARLY_STOP_VERSION,
            "decision": "stop",
            "should_stop": True,
            "confidence": "high",
            "reason": "confident_full_query_mismatch",
            "score_floor": 0.0,
            "score_ceiling": 5.0,
            "safe_to_skip_competitors": True,
            "content_evaluable": content_evaluable,
            "metrics": metrics,
        }
    return {
        "schema_version": QUERY_RELEVANCE_EARLY_STOP_VERSION,
        "decision": "continue",
        "should_stop": False,
        "confidence": "low" if content_evaluable else "insufficient_content",
        "reason": "not_confident_enough_for_early_stop",
        "score_floor": None,
        "score_ceiling": None,
        "safe_to_skip_competitors": False,
        "content_evaluable": content_evaluable,
        "metrics": metrics,
    }


def build_query_relevance_guardrail(features: Mapping[str, object], score: float) -> dict[str, object]:
    metrics = build_query_topic_metrics(features)
    semantic_similarity = metrics["semantic_similarity"]
    core_keyword_coverage = metrics["query_core_keyword_coverage_ratio"]
    core_query_density = metrics["query_core_density"]
    exact_or_structural_signal = metrics["exact_or_structural_signal"]
    query_prominence = metrics["query_prominence_score"]
    relevance_score = metrics["relevance_score"]
    strong_topic_fit = has_strong_query_topic_fit(features)
    unusable_reasons = _page_unusable_reasons(features)
    early_stop_decision = build_query_relevance_preflight_decision(features)

    reason: str | None = None
    band: str | None = None
    band_min: float | None = None
    band_max: float | None = None
    relevance_multiplier = 1.0
    if unusable_reasons:
        reason = "page_unusable"
        band = "unusable"
        band_min = 0.0
        band_max = 10.0
        relevance_multiplier = 0.10
    elif early_stop_decision["should_stop"]:
        reason = "confident_full_query_mismatch"
        band = "full_mismatch"
        band_min = 0.0
        band_max = 5.0
        relevance_multiplier = 0.05
    elif (
        not strong_topic_fit
        and relevance_score < 0.35
        and core_keyword_coverage < 0.34
        and semantic_similarity < 0.38
        and core_query_density < 0.002
    ):
        reason = "probable_query_topic_mismatch"
        band = "probable_mismatch"
        band_min = 6.0
        band_max = 25.0
        relevance_multiplier = 0.25
    elif (
        not strong_topic_fit
        and relevance_score < 0.48
        and core_keyword_coverage < 0.5
        and semantic_similarity < 0.45
        and core_query_density < 0.004
    ):
        reason = "weak_query_topic_match"
        band = "weak_match"
        band_min = 25.0
        band_max = 55.0
        relevance_multiplier = 0.55
    elif (
        not strong_topic_fit
        and relevance_score < 0.58
        and core_keyword_coverage < 0.75
        and exact_or_structural_signal < 0.35
        and query_prominence < 0.35
    ):
        reason = "partial_query_topic_match"
        band = "partial_match"
        band_min = 55.0
        band_max = 80.0
        relevance_multiplier = 0.80

    adjusted_score = _banded_score(score, relevance_multiplier, band_max)
    dynamic_cap = adjusted_score if adjusted_score < score else None
    return {
        "schema_version": QUERY_RELEVANCE_GUARDRAIL_VERSION,
        "active": adjusted_score < score,
        "reason": reason,
        "band": band,
        "band_min": band_min,
        "band_max": band_max,
        "cap": dynamic_cap,
        "query_relevance_multiplier": round(relevance_multiplier, 4),
        "original_score": score,
        "adjusted_score": adjusted_score,
        "score_delta": round(adjusted_score - score, 4),
        "metrics": metrics,
        "unusable_reasons": unusable_reasons,
        "early_stop_decision": early_stop_decision,
        "early_stop": bool(early_stop_decision["should_stop"]),
    }
