from __future__ import annotations

from collections.abc import Iterable
from math import isfinite
from typing import Any


SENSIBLE_FEATURE_KEYWORDS = (
    "word",
    "text",
    "content",
    "semantic",
    "query",
    "keyword",
    "title",
    "heading",
    "meta",
    "link",
    "image",
    "technical",
    "commercial",
    "trust",
    "intent",
    "faq",
    "url",
    "canonical",
)
SENSIBLE_FACTOR_KEYS = (
    "content_depth",
    "semantic_relevance",
    "keyword_coverage",
    "title_signal",
    "meta_signal",
    "heading_structure",
    "commercial_completeness",
    "trust_signals",
    "intent_alignment",
    "relative_query_match",
    "relative_semantic_relevance",
    "relative_content_depth",
    "relative_technical_seo",
    "relative_commercial_trust",
    "relative_intent_alignment",
)


def _contains_known_signal(value: str, known_signals: Iterable[str]) -> bool:
    normalized_value = value.casefold()
    return any(signal.casefold() in normalized_value for signal in known_signals)


def _top_feature_checks(candidate: dict[str, Any]) -> dict[str, Any]:
    feature_importance = candidate.get("feature_importance_summary")
    top_features = feature_importance.get("top_features", []) if isinstance(feature_importance, dict) else []
    feature_names = [str(feature.get("feature") or "") for feature in top_features if isinstance(feature, dict)]
    importances = [
        float(feature.get("importance"))
        for feature in top_features
        if isinstance(feature, dict) and feature.get("importance") is not None
    ]
    return {
        "top_features_non_empty": bool(feature_names),
        "top_feature_importances_finite": bool(importances) and all(isfinite(value) for value in importances),
        "known_seo_signal_in_top_features": any(
            _contains_known_signal(feature_name, SENSIBLE_FEATURE_KEYWORDS)
            for feature_name in feature_names[:10]
        ),
        "top_feature_names": feature_names[:10],
    }


def _smoke_factor_checks(candidate_name: str, smoke_summary: dict[str, Any]) -> dict[str, Any]:
    model_summaries = [
        model
        for query_result in smoke_summary.get("query_results", [])
        for model in query_result.get("models", [])
        if isinstance(query_result, dict)
        and isinstance(model, dict)
        and model.get("model_name") == candidate_name
    ]
    factor_keys = [
        str(factor_key)
        for model in model_summaries
        for factor_key in [
            *model.get("top_positive_factor_keys", []),
            *model.get("top_negative_factor_keys", []),
            *model.get("serp_relative_factor_keys", []),
        ]
    ]
    return {
        "smoke_explanations_present": bool(model_summaries),
        "smoke_explanations_bounded": bool(model_summaries) and all(bool(model.get("bounded")) for model in model_summaries),
        "known_factor_key_present": any(_contains_known_signal(factor_key, SENSIBLE_FACTOR_KEYS) for factor_key in factor_keys),
        "factor_keys_sample": factor_keys[:12],
    }


def build_explainability_sensibility_summary(
    *,
    candidates: list[dict[str, Any]],
    smoke_summary: dict[str, Any],
) -> dict[str, Any]:
    model_guardrails: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        if candidate.get("status") != "available":
            continue
        candidate_name = str(candidate.get("candidate_name") or "unknown")
        checks = {
            **_top_feature_checks(candidate),
            **_smoke_factor_checks(candidate_name, smoke_summary),
        }
        passed = all(
            bool(checks[check_name])
            for check_name in (
                "top_features_non_empty",
                "top_feature_importances_finite",
                "known_seo_signal_in_top_features",
                "smoke_explanations_present",
                "smoke_explanations_bounded",
                "known_factor_key_present",
            )
        )
        model_guardrails[candidate_name] = {"passed": passed, "checks": checks}
    return {
        "passed": bool(model_guardrails) and all(item["passed"] for item in model_guardrails.values()),
        "heuristic": (
            "Top features must be non-empty, finite and include at least one known SEO signal; "
            "smoke explanations must be present, bounded and include known explanation factor keys."
        ),
        "model_guardrails": model_guardrails,
    }
