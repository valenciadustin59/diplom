import importlib

from app.ml.model import (
    DEFAULT_MODEL_PATH,
    FEATURE_COLUMNS,
    average_score,
    clear_model_cache,
    compare_with_competitors,
    create_dataset,
    explain_score,
    get_model_artifact,
    load_model_artifact,
    load_saved_model,
    predict_score,
    save_model,
    score_pages,
    train_and_predict,
    train_model,
)


_DATASET_BUILDER_EXPORTS = {
    "DATASET_COLUMNS",
    "DEFAULT_CHECKPOINT_PATH",
    "DEFAULT_DATASET_PATH",
    "DEFAULT_FAILURES_PATH",
    "DEFAULT_QUERIES_PATH",
    "DEFAULT_SEEDS_PATH",
    "build_dataset",
    "build_dataset_for_query",
    "infer_page_type",
    "load_seed_rows",
    "rank_to_score",
}

_TRAIN_EXPORTS = {
    "evaluate_model_rows",
    "load_dataset_rows",
    "prepare_training_data",
    "rows_to_matrix",
    "select_best_candidate",
    "split_dataset_rows",
    "train_candidate_models",
    "train_quality_model",
}

_DATASET_QUALITY_EXPORTS = {
    "DatasetQualityThresholds",
    "PRODUCTION_LIKE_DATASET_THRESHOLDS",
    "build_dataset_manifest",
    "default_manifest_path",
    "evaluate_dataset_quality",
    "save_dataset_manifest",
}

_QUERY_SEED_EXPORTS = {
    "RU_COMMERCIAL_CATEGORIES",
    "RU_COMMERCIAL_CITIES",
    "TRAINING_SEED_FIELDS",
    "build_seed_catalog_summary",
    "build_training_queries",
    "build_training_seed_rows",
}

_PUBLISH_EXPORTS = {
    "ARTIFACTS_DIR",
    "DEFAULT_PRIMARY_DATASET_PATH",
    "DEFAULT_PRIMARY_MANIFEST_PATH",
    "VERSIONED_ARTIFACTS_DIR",
    "build_artifact_metadata_path",
    "build_artifact_public_metadata",
    "build_dataset_metadata",
    "build_primary_artifact_version",
    "build_primary_dataset_version",
    "build_versioned_artifact_path",
    "ensure_manifest_ready",
    "load_training_manifest",
    "publish_primary_model",
    "write_artifact_public_metadata",
}

_EVALUATE_EXPORTS = {"evaluate_candidate_models"}


def __getattr__(name: str):
    if name in _DATASET_BUILDER_EXPORTS:
        module = importlib.import_module("app.ml.dataset_builder")
        return getattr(module, name)

    if name in _TRAIN_EXPORTS:
        module = importlib.import_module("app.ml.train")
        return getattr(module, name)

    if name in _DATASET_QUALITY_EXPORTS:
        module = importlib.import_module("app.ml.dataset_quality")
        return getattr(module, name)

    if name in _QUERY_SEED_EXPORTS:
        module = importlib.import_module("app.ml.query_seeds")
        return getattr(module, name)

    if name in _PUBLISH_EXPORTS:
        module = importlib.import_module("app.ml.publish")
        return getattr(module, name)

    if name in _EVALUATE_EXPORTS:
        module = importlib.import_module("app.ml.evaluate")
        return getattr(module, name)

    raise AttributeError(name)


__all__ = [
    "DEFAULT_MODEL_PATH",
    "FEATURE_COLUMNS",
    "average_score",
    "clear_model_cache",
    "compare_with_competitors",
    "create_dataset",
    "explain_score",
    "get_model_artifact",
    "load_model_artifact",
    "load_saved_model",
    "predict_score",
    "save_model",
    "score_pages",
    "train_and_predict",
    "train_model",
    *_DATASET_BUILDER_EXPORTS,
    *_TRAIN_EXPORTS,
    *_DATASET_QUALITY_EXPORTS,
    *_QUERY_SEED_EXPORTS,
    *_PUBLISH_EXPORTS,
    *_EVALUATE_EXPORTS,
]
