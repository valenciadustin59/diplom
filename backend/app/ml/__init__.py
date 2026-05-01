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
    "DEFAULT_EXPERT_LABELS_PATH",
    "DEFAULT_FAILURES_PATH",
    "DEFAULT_QUERIES_PATH",
    "DEFAULT_SEEDS_PATH",
    "build_dataset",
    "build_dataset_for_query",
    "infer_page_type",
    "load_expert_labels",
    "load_seed_rows",
    "rank_to_score",
    "resolve_target_label",
}
_TRAIN_EXPORTS = {
    "build_dataset_split_manifest",
    "create_dataset_split",
    "evaluate_model_rows",
    "load_dataset_rows",
    "prepare_training_data",
    "rows_to_matrix",
    "save_dataset_split_manifest",
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
    "DATASET_V2_QUERY_PATTERNS",
    "RU_COMMERCIAL_CATEGORIES",
    "RU_COMMERCIAL_CITIES",
    "TRAINING_SEED_FIELDS",
    "build_dataset_v2_seed_rows",
    "build_dataset_v2_seed_summary",
    "build_seed_catalog_summary",
    "build_training_queries",
    "build_training_seed_rows",
    "save_seed_rows",
}
_DATASET_VERSION_EXPORTS = {
    "BASELINE_DATASET_VERSION",
    "DATASET_VERSIONS_DIR",
    "DEFAULT_DATASET_VERSION",
    "LABEL_SCHEMA_VERSION",
    "build_dataset_bundle_paths",
    "freeze_primary_dataset_as_baseline",
    "infer_dataset_version",
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
_CANDIDATE_ARTIFACT_EXPORTS = {
    "DEFAULT_CATBOOST_CANDIDATE_PATH",
    "DEFAULT_D34_CANDIDATE_REPORTS_DIR",
    "DEFAULT_RANKING_CANDIDATE_PATH",
    "DEFAULT_RF_CANDIDATE_PATH",
    "POINTWISE_CATBOOST_CANDIDATE",
    "POINTWISE_RANDOM_FOREST_CANDIDATE",
    "train_candidate_artifacts",
    "write_candidate_artifact_report",
}
_RANKING_BENCHMARK_EXPORTS = {
    "CATBOOST_RANKER_CANDIDATE",
    "DEFAULT_RANKING_DATASET_PATH",
    "DEFAULT_RANKING_MANIFEST_PATH",
    "DEFAULT_RANKING_REPORTS_DIR",
    "LIGHTGBM_RANKER_CANDIDATE",
    "RANKING_CANDIDATE_NAMES",
    "XGBOOST_RANKER_CANDIDATE",
    "build_feature_importance_summary",
    "build_intent_breakdown",
    "build_query_group_breakdown",
    "build_ranking_benchmark_comparison",
    "build_stability_summary",
    "publish_best_ranking_model",
    "render_ranking_benchmark_markdown",
    "run_ranking_benchmark",
    "write_ranking_benchmark_report",
}
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
    if name in _DATASET_VERSION_EXPORTS:
        module = importlib.import_module("app.ml.dataset_versions")
        return getattr(module, name)
    if name in _PUBLISH_EXPORTS:
        module = importlib.import_module("app.ml.publish")
        return getattr(module, name)
    if name in _EVALUATE_EXPORTS:
        module = importlib.import_module("app.ml.evaluate")
        return getattr(module, name)
    if name in _CANDIDATE_ARTIFACT_EXPORTS:
        module = importlib.import_module("app.ml.candidate_artifacts")
        return getattr(module, name)
    if name in _RANKING_BENCHMARK_EXPORTS:
        module = importlib.import_module("app.ml.ranking_benchmark")
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
    *_DATASET_VERSION_EXPORTS,
    *_PUBLISH_EXPORTS,
    *_EVALUATE_EXPORTS,
    *_CANDIDATE_ARTIFACT_EXPORTS,
    *_RANKING_BENCHMARK_EXPORTS,
]
