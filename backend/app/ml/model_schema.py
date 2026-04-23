from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.features import SNAPSHOT_AUXILIARY_FEATURE_COLUMNS


MODEL_SCHEMA_VERSION_V1 = "v1"
MODEL_SCHEMA_VERSION_V2 = "v2"
CUSTOM_MODEL_SCHEMA_VERSION = "custom"
DEFAULT_TRAINING_MODEL_SCHEMA_VERSION = MODEL_SCHEMA_VERSION_V2
DEFAULT_RUNTIME_MODEL_SCHEMA_VERSION = MODEL_SCHEMA_VERSION_V1

BASELINE_FEATURE_COLUMNS = (
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
)

MODEL_FEATURE_COLUMNS_BY_VERSION: dict[str, tuple[str, ...]] = {
    MODEL_SCHEMA_VERSION_V1: BASELINE_FEATURE_COLUMNS,
    MODEL_SCHEMA_VERSION_V2: BASELINE_FEATURE_COLUMNS + tuple(SNAPSHOT_AUXILIARY_FEATURE_COLUMNS),
}


@dataclass(frozen=True)
class ModelFeatureSchema:
    version: str
    feature_columns: tuple[str, ...]


def normalize_feature_columns(feature_columns: Sequence[str]) -> tuple[str, ...]:
    normalized = tuple(str(feature_name).strip() for feature_name in feature_columns if str(feature_name).strip())
    if not normalized:
        raise ValueError("Model feature schema must contain at least one feature column.")
    if len(set(normalized)) != len(normalized):
        raise ValueError("Model feature schema contains duplicate feature columns.")
    return normalized


def infer_model_schema_version(feature_columns: Sequence[str]) -> str | None:
    normalized = normalize_feature_columns(feature_columns)
    for version, expected_columns in MODEL_FEATURE_COLUMNS_BY_VERSION.items():
        if normalized == expected_columns:
            return version
    return None


def get_model_feature_schema(model_schema_version: str) -> ModelFeatureSchema:
    try:
        feature_columns = MODEL_FEATURE_COLUMNS_BY_VERSION[model_schema_version]
    except KeyError as error:
        supported_versions = ", ".join(sorted(MODEL_FEATURE_COLUMNS_BY_VERSION))
        raise ValueError(
            f"Unknown model schema version '{model_schema_version}'. Supported versions: {supported_versions}."
        ) from error
    return ModelFeatureSchema(version=model_schema_version, feature_columns=feature_columns)


def resolve_model_feature_schema(
    *,
    model_schema_version: str | None = None,
    feature_columns: Sequence[str] | None = None,
    default_version: str = DEFAULT_RUNTIME_MODEL_SCHEMA_VERSION,
) -> ModelFeatureSchema:
    if feature_columns is not None:
        normalized_feature_columns = normalize_feature_columns(feature_columns)
        inferred_version = infer_model_schema_version(normalized_feature_columns)
        resolved_version = model_schema_version or inferred_version or CUSTOM_MODEL_SCHEMA_VERSION
        return ModelFeatureSchema(version=resolved_version, feature_columns=normalized_feature_columns)

    resolved_version = model_schema_version or default_version
    return get_model_feature_schema(resolved_version)
