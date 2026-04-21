from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
import logging
from pathlib import Path
import pickle
import random
from typing import Any

from sklearn.ensemble import RandomForestRegressor


logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "text_length_chars",
    "html_length_chars",
    "word_count",
    "unique_word_count",
    "unique_word_ratio",
    "avg_word_length",
    "sentence_count",
    "avg_sentence_length",
    "paragraph_count",
    "h1_count",
    "h2_count",
    "h3_count",
    "heading_count",
    "title_present",
    "title_length",
    "meta_description_present",
    "meta_description_length",
    "query_in_title",
    "query_in_text",
    "exact_query_count",
    "query_term_count",
    "title_query_term_count",
    "meta_query_term_count",
    "title_keyword_coverage_ratio",
    "meta_keyword_coverage_ratio",
    "query_terms_in_headings",
    "heading_query_coverage_ratio",
    "first_200_words_query_term_count",
    "query_density",
    "keyword_coverage_ratio",
    "link_count",
    "image_count",
    "list_item_count",
    "strong_tag_count",
    "form_count",
    "input_count",
    "inputs_per_form_ratio",
    "avg_paragraph_length",
    "link_density_per_1000_words",
    "image_density_per_1000_words",
    "list_density_per_1000_words",
    "strong_density_per_1000_words",
    "text_to_html_ratio",
    "semantic_similarity",
    "early_query_coverage_ratio",
    "conversion_signal_score",
    "content_link_ratio",
    "heading_paragraph_balance",
    "query_semantic_alignment",
    "title_semantic_alignment",
    "heading_semantic_alignment",
    "title_heading_keyword_alignment",
    "content_depth_semantic_score",
    "query_prominence_score",
    "title_length_quality",
    "meta_length_quality",
    "keyword_balance_score",
    "semantic_content_richness",
    "cta_semantic_score",
]

BACKEND_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = BACKEND_DIR / "artifacts"
DEFAULT_MODEL_PATH = ARTIFACTS_DIR / "page_quality_model.pkl"


def _resolve_model_path(model_path: str | Path | None = None) -> Path:
    return Path(model_path) if model_path is not None else DEFAULT_MODEL_PATH


def _rounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 4)


def _bounded_quality(value: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return max(0.0, 1.0 - (abs(value - target) / target))


def _vectorize_features(features: dict[str, float | int]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in FEATURE_COLUMNS]


def _feature_value(features: dict[str, float | int], key: str) -> float:
    return float(features.get(key, 0.0))


def create_dataset(n_samples: int = 500, seed: int = 42) -> tuple[list[list[float]], list[float]]:
    rng = random.Random(seed)
    rows: list[list[float]] = []
    targets: list[float] = []

    for _ in range(n_samples):
        word_count = rng.randint(80, 3500)
        unique_word_ratio = rng.uniform(0.25, 0.95)
        unique_word_count = int(word_count * unique_word_ratio)
        sentence_count = max(1, word_count // rng.randint(8, 24))
        avg_sentence_length = word_count / sentence_count
        text_length_chars = word_count * rng.randint(4, 8)
        html_length_chars = text_length_chars + rng.randint(500, 12000)
        paragraph_count = max(1, word_count // rng.randint(40, 160))
        h1_count = rng.randint(0, 3)
        h2_count = rng.randint(0, 12)
        h3_count = rng.randint(0, 16)
        heading_count = h1_count + h2_count + h3_count
        title_present = rng.randint(0, 1)
        title_length = rng.randint(0, 80) if title_present else 0
        meta_description_present = rng.randint(0, 1)
        meta_description_length = rng.randint(0, 180) if meta_description_present else 0
        query_in_title = rng.randint(0, 1)
        query_in_text = rng.randint(0, 1)
        exact_query_count = rng.randint(0, 8)
        query_term_count = rng.randint(0, 30)
        title_query_term_count = rng.randint(0, 4)
        meta_query_term_count = rng.randint(0, 4)
        query_terms_in_headings = rng.randint(0, 6)
        first_200_words_query_term_count = rng.randint(0, 12)
        query_density = rng.uniform(0.0, 0.2)
        keyword_coverage_ratio = rng.uniform(0.0, 1.0)
        title_keyword_coverage_ratio = rng.uniform(0.0, 1.0)
        meta_keyword_coverage_ratio = rng.uniform(0.0, 1.0)
        heading_query_coverage_ratio = rng.uniform(0.0, 1.0)
        link_count = rng.randint(0, 150)
        image_count = rng.randint(0, 60)
        list_item_count = rng.randint(0, 80)
        strong_tag_count = rng.randint(0, 40)
        form_count = rng.randint(0, 5)
        input_count = rng.randint(0, 20)
        inputs_per_form_ratio = (input_count / form_count) if form_count else 0.0
        avg_paragraph_length = word_count / paragraph_count if paragraph_count else 0.0
        avg_word_length = rng.uniform(3.5, 8.0)
        text_to_html_ratio = rng.uniform(0.01, 0.9)
        semantic_similarity = rng.uniform(0.0, 1.0)

        early_query_coverage_ratio = min(first_200_words_query_term_count / 3.0, 1.0)
        conversion_signal_score = (
            int(form_count > 0)
            + int(input_count > 0)
            + int(image_count > 0)
            + int(list_item_count > 0)
        ) / 4.0
        content_link_ratio = (word_count / max(link_count, 1)) if word_count else 0.0
        heading_paragraph_balance = heading_count / paragraph_count if paragraph_count else 0.0
        query_semantic_alignment = semantic_similarity * keyword_coverage_ratio
        title_semantic_alignment = semantic_similarity * title_keyword_coverage_ratio
        heading_semantic_alignment = semantic_similarity * heading_query_coverage_ratio
        title_heading_keyword_alignment = title_keyword_coverage_ratio * heading_query_coverage_ratio
        content_depth_semantic_score = semantic_similarity * min(word_count / 1500.0, 1.0)
        query_prominence_score = (
            title_keyword_coverage_ratio * 0.35
            + heading_query_coverage_ratio * 0.25
            + early_query_coverage_ratio * 0.25
            + keyword_coverage_ratio * 0.15
        )
        title_length_quality = _bounded_quality(float(title_length), 55.0) if title_present else 0.0
        meta_length_quality = (
            _bounded_quality(float(meta_description_length), 145.0) if meta_description_present else 0.0
        )
        keyword_balance_score = keyword_coverage_ratio * max(
            0.0,
            1.0 - min(abs(query_density - 0.03) / 0.03, 1.0),
        )
        semantic_content_richness = semantic_similarity * min(word_count / 1800.0, 1.0) * min(
            unique_word_ratio,
            1.0,
        )
        cta_semantic_score = conversion_signal_score * semantic_similarity

        row_features = {
            "text_length_chars": float(text_length_chars),
            "html_length_chars": float(html_length_chars),
            "word_count": float(word_count),
            "unique_word_count": float(unique_word_count),
            "unique_word_ratio": float(unique_word_ratio),
            "avg_word_length": float(avg_word_length),
            "sentence_count": float(sentence_count),
            "avg_sentence_length": float(avg_sentence_length),
            "paragraph_count": float(paragraph_count),
            "h1_count": float(h1_count),
            "h2_count": float(h2_count),
            "h3_count": float(h3_count),
            "heading_count": float(heading_count),
            "title_present": float(title_present),
            "title_length": float(title_length),
            "meta_description_present": float(meta_description_present),
            "meta_description_length": float(meta_description_length),
            "query_in_title": float(query_in_title),
            "query_in_text": float(query_in_text),
            "exact_query_count": float(exact_query_count),
            "query_term_count": float(query_term_count),
            "title_query_term_count": float(title_query_term_count),
            "meta_query_term_count": float(meta_query_term_count),
            "title_keyword_coverage_ratio": float(title_keyword_coverage_ratio),
            "meta_keyword_coverage_ratio": float(meta_keyword_coverage_ratio),
            "query_terms_in_headings": float(query_terms_in_headings),
            "heading_query_coverage_ratio": float(heading_query_coverage_ratio),
            "first_200_words_query_term_count": float(first_200_words_query_term_count),
            "query_density": float(query_density),
            "keyword_coverage_ratio": float(keyword_coverage_ratio),
            "link_count": float(link_count),
            "image_count": float(image_count),
            "list_item_count": float(list_item_count),
            "strong_tag_count": float(strong_tag_count),
            "form_count": float(form_count),
            "input_count": float(input_count),
            "inputs_per_form_ratio": float(inputs_per_form_ratio),
            "avg_paragraph_length": float(avg_paragraph_length),
            "link_density_per_1000_words": float((link_count * 1000.0 / word_count) if word_count else 0.0),
            "image_density_per_1000_words": float((image_count * 1000.0 / word_count) if word_count else 0.0),
            "list_density_per_1000_words": float((list_item_count * 1000.0 / word_count) if word_count else 0.0),
            "strong_density_per_1000_words": float((strong_tag_count * 1000.0 / word_count) if word_count else 0.0),
            "text_to_html_ratio": float(text_to_html_ratio),
            "semantic_similarity": float(semantic_similarity),
            "early_query_coverage_ratio": float(early_query_coverage_ratio),
            "conversion_signal_score": float(conversion_signal_score),
            "content_link_ratio": float(content_link_ratio),
            "heading_paragraph_balance": float(heading_paragraph_balance),
            "query_semantic_alignment": float(query_semantic_alignment),
            "title_semantic_alignment": float(title_semantic_alignment),
            "heading_semantic_alignment": float(heading_semantic_alignment),
            "title_heading_keyword_alignment": float(title_heading_keyword_alignment),
            "content_depth_semantic_score": float(content_depth_semantic_score),
            "query_prominence_score": float(query_prominence_score),
            "title_length_quality": float(title_length_quality),
            "meta_length_quality": float(meta_length_quality),
            "keyword_balance_score": float(keyword_balance_score),
            "semantic_content_richness": float(semantic_content_richness),
            "cta_semantic_score": float(cta_semantic_score),
        }
        rows.append(_vectorize_features(row_features))

        score = 18.0
        score += min(word_count / 100.0, 18.0)
        score += keyword_coverage_ratio * 12.0
        score += semantic_similarity * 18.0
        score += query_semantic_alignment * 10.0
        score += title_semantic_alignment * 6.0
        score += heading_semantic_alignment * 5.0
        score += query_prominence_score * 6.0
        score += min(content_depth_semantic_score * 8.0, 8.0)
        score += semantic_content_richness * 9.0
        score += keyword_balance_score * 7.0
        score += cta_semantic_score * 4.0

        if not title_present:
            score -= 8.0
        if not meta_description_present:
            score -= 4.0
        if query_in_title:
            score += 3.0
        if query_in_text:
            score += 2.0
        if form_count == 0 and input_count == 0:
            score -= 3.0
        if keyword_coverage_ratio < 0.2:
            score -= 8.0
        if query_density > 0.09:
            score -= 7.0
        if heading_count == 0:
            score -= 3.0
        if text_to_html_ratio < 0.05:
            score -= 3.0
        if word_count < 250:
            score -= 8.0
        if unique_word_ratio < 0.35:
            score -= 6.0
        if content_link_ratio < 10.0:
            score -= 4.0

        targets.append(_rounded_score(score))

    return rows, targets


def train_model(n_samples: int = 500, seed: int = 42) -> RandomForestRegressor:
    x_train, y_train = create_dataset(n_samples=n_samples, seed=seed)
    model = RandomForestRegressor(
        n_estimators=250,
        max_depth=12,
        min_samples_split=4,
        min_samples_leaf=2,
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    return model


def save_model(
    model: Any,
    metrics: dict[str, Any],
    model_path: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    output_path = _resolve_model_path(model_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload_metadata = dict(metadata or {})
    payload = {
        "model": model,
        "metrics": dict(metrics),
        "feature_columns": payload_metadata.pop("feature_columns", FEATURE_COLUMNS),
        "trained_at": payload_metadata.pop("trained_at", datetime.now(UTC).isoformat()),
        "source": payload_metadata.pop("source", "local_dataset"),
        "model_type": payload_metadata.pop("model_type", model.__class__.__name__),
        **payload_metadata,
    }
    with output_path.open("wb") as file:
        pickle.dump(payload, file)
    return output_path


def load_saved_model(model_path: str | Path | None = None) -> dict[str, object] | None:
    resolved_path = _resolve_model_path(model_path)
    if not resolved_path.exists():
        return None
    with resolved_path.open("rb") as file:
        payload = pickle.load(file)
    if not isinstance(payload, dict):
        raise TypeError(f"Saved model payload at {resolved_path} must be a dict.")
    return payload


def _bootstrap_artifact() -> dict[str, object]:
    bootstrap_model = train_model()
    return {
        "model": bootstrap_model,
        "metrics": {},
        "feature_columns": FEATURE_COLUMNS,
        "trained_at": None,
        "source": "bootstrap",
        "model_type": bootstrap_model.__class__.__name__,
        "rows_count": 0,
        "queries_count": 0,
        "domains_count": 0,
        "dataset_version": None,
    }


def _ensure_artifact_compatibility(payload: dict[str, object]) -> dict[str, object]:
    model = payload.get("model")
    if model is None or not hasattr(model, "predict"):
        raise TypeError("Saved artifact does not contain a compatible model with predict().")
    feature_columns = payload.get("feature_columns")
    if feature_columns != FEATURE_COLUMNS:
        raise ValueError("Saved artifact feature schema does not match current FEATURE_COLUMNS.")

    metrics = payload.get("metrics")
    normalized_metrics = metrics if isinstance(metrics, dict) else {}
    return {
        "model": model,
        "metrics": normalized_metrics,
        "feature_columns": FEATURE_COLUMNS,
        "trained_at": payload.get("trained_at"),
        "source": payload.get("source", "local_dataset"),
        "model_type": payload.get("model_type", model.__class__.__name__),
        "rows_count": int(payload.get("rows_count") or normalized_metrics.get("rows_count") or 0),
        "queries_count": int(payload.get("queries_count") or 0),
        "domains_count": int(payload.get("domains_count") or 0),
        "dataset_version": payload.get("dataset_version"),
    }


def load_model_artifact(model_path: str | Path | None = None) -> dict[str, object] | None:
    saved_payload = load_saved_model(model_path)
    if saved_payload is None:
        return None
    return _ensure_artifact_compatibility(saved_payload)


@lru_cache(maxsize=4)
def _get_cached_model_artifact(model_path_str: str) -> dict[str, object]:
    saved_payload = load_saved_model(model_path_str)
    if saved_payload is not None:
        try:
            return _ensure_artifact_compatibility(saved_payload)
        except Exception as error:
            logger.warning("Falling back to bootstrap model due to artifact incompatibility: %s", error)
    return _bootstrap_artifact()


def clear_model_cache() -> None:
    _get_cached_model_artifact.cache_clear()


def get_model_artifact(model_path: str | Path | None = None) -> dict[str, object]:
    return _get_cached_model_artifact(str(_resolve_model_path(model_path)))


def _build_model_info(artifact: dict[str, object]) -> dict[str, object]:
    return {
        "source": artifact.get("source", "unknown"),
        "model_type": artifact.get("model_type", artifact["model"].__class__.__name__),
        "trained_at": artifact.get("trained_at"),
        "dataset_rows": int(artifact.get("rows_count") or 0),
        "dataset_version": artifact.get("dataset_version"),
    }


def calculate_rule_score(features: dict[str, float | int]) -> tuple[float, list[dict[str, object]]]:
    word_count = _feature_value(features, "word_count")
    title_present = _feature_value(features, "title_present")
    title_length_quality = _feature_value(features, "title_length_quality")
    meta_present = _feature_value(features, "meta_description_present")
    meta_length_quality = _feature_value(features, "meta_length_quality")
    heading_count = _feature_value(features, "heading_count")
    semantic_similarity = _feature_value(features, "semantic_similarity")
    keyword_coverage_ratio = _feature_value(features, "keyword_coverage_ratio")
    title_semantic_alignment = _feature_value(features, "title_semantic_alignment")
    heading_semantic_alignment = _feature_value(features, "heading_semantic_alignment")
    content_depth_semantic_score = _feature_value(features, "content_depth_semantic_score")
    semantic_content_richness = _feature_value(features, "semantic_content_richness")
    keyword_balance_score = _feature_value(features, "keyword_balance_score")
    conversion_signal_score = _feature_value(features, "conversion_signal_score")
    query_prominence_score = _feature_value(features, "query_prominence_score")
    text_to_html_ratio = _feature_value(features, "text_to_html_ratio")
    unique_word_ratio = _feature_value(features, "unique_word_ratio")

    factors = [
        {
            "key": "content_depth",
            "label": "Content depth",
            "impact": round(min(word_count / 1200.0, 1.0) * 18.0, 4),
            "value": round(word_count, 4),
        },
        {
            "key": "semantic_relevance",
            "label": "Semantic relevance",
            "impact": round(semantic_similarity * 20.0, 4),
            "value": round(semantic_similarity, 4),
        },
        {
            "key": "keyword_coverage",
            "label": "Keyword coverage",
            "impact": round(keyword_coverage_ratio * 10.0, 4),
            "value": round(keyword_coverage_ratio, 4),
        },
        {
            "key": "title_signal",
            "label": "Title quality",
            "impact": round((title_present * 0.5 + title_length_quality * 0.5) * 8.0, 4),
            "value": round(title_length_quality, 4),
        },
        {
            "key": "meta_signal",
            "label": "Meta description quality",
            "impact": round((meta_present * 0.5 + meta_length_quality * 0.5) * 5.0, 4),
            "value": round(meta_length_quality, 4),
        },
        {
            "key": "heading_structure",
            "label": "Heading structure",
            "impact": round(min(heading_count / 6.0, 1.0) * 6.0, 4),
            "value": round(heading_count, 4),
        },
        {
            "key": "title_semantic_alignment",
            "label": "Title-query alignment",
            "impact": round(title_semantic_alignment * 6.0, 4),
            "value": round(title_semantic_alignment, 4),
        },
        {
            "key": "heading_semantic_alignment",
            "label": "Heading-query alignment",
            "impact": round(heading_semantic_alignment * 5.0, 4),
            "value": round(heading_semantic_alignment, 4),
        },
        {
            "key": "content_depth_semantic_score",
            "label": "Depth and semantic match",
            "impact": round(content_depth_semantic_score * 8.0, 4),
            "value": round(content_depth_semantic_score, 4),
        },
        {
            "key": "semantic_content_richness",
            "label": "Content richness",
            "impact": round(semantic_content_richness * 8.0, 4),
            "value": round(semantic_content_richness, 4),
        },
        {
            "key": "keyword_balance",
            "label": "Keyword balance",
            "impact": round(keyword_balance_score * 7.0, 4),
            "value": round(keyword_balance_score, 4),
        },
        {
            "key": "conversion_signal",
            "label": "Commercial signals",
            "impact": round(conversion_signal_score * 4.0, 4),
            "value": round(conversion_signal_score, 4),
        },
        {
            "key": "query_prominence",
            "label": "Query prominence",
            "impact": round(query_prominence_score * 8.0, 4),
            "value": round(query_prominence_score, 4),
        },
        {
            "key": "text_to_html_ratio",
            "label": "Text-to-HTML ratio",
            "impact": round(min(text_to_html_ratio / 0.25, 1.0) * 4.0, 4),
            "value": round(text_to_html_ratio, 4),
        },
        {
            "key": "uniqueness",
            "label": "Lexical uniqueness",
            "impact": round(unique_word_ratio * 5.0, 4),
            "value": round(unique_word_ratio, 4),
        },
    ]

    rule_score = _rounded_score(sum(float(item["impact"]) for item in factors))
    return rule_score, factors


def _predict_model_score(features: dict[str, float | int], model_path: str | Path | None = None) -> float:
    artifact = get_model_artifact(model_path)
    model = artifact["model"]
    vector = _vectorize_features(features)
    return _rounded_score(float(model.predict([vector])[0]))


def explain_score(
    features: dict[str, float | int],
    model_path: str | Path | None = None,
) -> dict[str, object]:
    artifact = get_model_artifact(model_path)
    ml_score = _predict_model_score(features, model_path=model_path)
    rule_score, factors = calculate_rule_score(features)

    rule_weight = 0.65 if artifact.get("source") == "bootstrap" else 0.45
    ml_weight = 1.0 - rule_weight
    final_score = _rounded_score(rule_score * rule_weight + ml_score * ml_weight)

    positives = sorted(
        [factor for factor in factors if float(factor["impact"]) > 0],
        key=lambda item: float(item["impact"]),
        reverse=True,
    )[:5]
    negatives = sorted(
        [factor for factor in factors if float(factor["impact"]) <= 0],
        key=lambda item: float(item["impact"]),
    )[:5]

    return {
        "final_score": final_score,
        "rule_score": rule_score,
        "ml_score": ml_score,
        "model_info": _build_model_info(artifact),
        "weights": {
            "rule_weight": round(rule_weight, 4),
            "ml_weight": round(ml_weight, 4),
        },
        "top_positive_factors": positives,
        "top_negative_factors": negatives,
    }


def predict_score(features: dict[str, float | int], model_path: str | Path | None = None) -> float:
    explanation = explain_score(features, model_path=model_path)
    return float(explanation["final_score"])


def score_pages(
    pages_features: list[dict[str, float | int]],
    model_path: str | Path | None = None,
) -> list[float]:
    return [predict_score(features, model_path=model_path) for features in pages_features]


def average_score(
    pages_features: list[dict[str, float | int]],
    model_path: str | Path | None = None,
) -> float:
    scores = score_pages(pages_features, model_path=model_path)
    if not scores:
        return 0.0
    return _rounded_score(sum(scores) / len(scores))


def compare_with_competitors(
    user_pages_features: list[dict[str, float | int]],
    competitor_pages_features: list[dict[str, float | int]],
    model_path: str | Path | None = None,
) -> dict[str, object]:
    user_scores = score_pages(user_pages_features, model_path=model_path)
    competitor_scores = score_pages(competitor_pages_features, model_path=model_path)
    user_average = _rounded_score(sum(user_scores) / len(user_scores)) if user_scores else 0.0
    competitors_average = _rounded_score(sum(competitor_scores) / len(competitor_scores)) if competitor_scores else 0.0
    return {
        "user_scores": user_scores,
        "competitor_scores": competitor_scores,
        "user_average_score": user_average,
        "competitors_average_score": competitors_average,
        "score_difference": _rounded_score(user_average - competitors_average),
    }


def train_and_predict(
    features: dict[str, float | int],
    model_path: str | Path | None = None,
) -> dict[str, object]:
    explanation = explain_score(features, model_path=model_path)
    artifact = get_model_artifact(model_path)
    metrics = artifact.get("metrics", {})
    model_info = _build_model_info(artifact)
    return {
        "model_type": str(model_info["model_type"]),
        "feature_count": len(FEATURE_COLUMNS),
        "rule_score": float(explanation["rule_score"]),
        "ml_score": float(explanation["ml_score"]),
        "final_score": float(explanation["final_score"]),
        "metrics": metrics if isinstance(metrics, dict) else {},
        "source": str(model_info["source"]),
        "model_info": model_info,
    }

