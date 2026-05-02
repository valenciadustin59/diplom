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
_CONTROLLED_PUBLISH_EXPORTS = {
    "run_controlled_publish",
    "update_controlled_publish_verification",
    "validate_publish_shadow_report",
}
_SECOND_PASS_EXPORTS = {
    "SECOND_PASS_CANDIDATE_FAMILY",
    "SECOND_PASS_CONTRACT_VERSION",
    "SECOND_PASS_MIN_COMPETITORS",
    "SECOND_PASS_MODEL_SCHEMA_VERSION",
    "build_second_pass_context",
    "build_second_pass_score_result",
    "get_second_pass_feature_columns",
}
_SECOND_PASS_EXPERIMENT_EXPORTS = {
    "DEFAULT_D44_CANDIDATE_MODEL_PATH",
    "DEFAULT_D44_DATASET_PATH",
    "DEFAULT_D44_OUTPUT_DIR",
    "enrich_rows_with_serp_relative_features",
    "render_second_pass_experiment_markdown",
    "run_second_pass_experiment",
    "write_second_pass_experiment_report",
}
_V4_DATASET_EXPORTS = {
    "LABEL_SCHEMA_VERSION_V4",
    "build_v4_dataset",
    "load_seo_weighted_labels",
}
_SEO_WEIGHTED_CANDIDATE_TRAINING_EXPORTS = {
    "DEFAULT_D47_CATBOOST_CANDIDATE_PATH",
    "DEFAULT_D47_OUTPUT_DIR",
    "DEFAULT_D47_RANKING_CANDIDATE_PATH",
    "DEFAULT_D47_RF_CANDIDATE_PATH",
    "run_d47_candidate_training",
}
_SEO_WEIGHTED_SHADOW_BENCHMARK_EXPORTS = {
    "DEFAULT_D48_OUTPUT_DIR",
    "build_d48_decision",
    "build_product_guardrails",
    "run_d48_product_shadow_benchmark",
}
_SEO_WEIGHTED_NO_PUBLISH_DECISION_EXPORTS = {
    "DEFAULT_D49_OUTPUT_DIR",
    "build_d49_no_publish_report",
    "run_d49_no_publish_decision",
    "validate_d48_keep_current_report",
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
    if name in _RANKING_BENCHMARK_EXPORTS:
        module = importlib.import_module("app.ml.ranking_benchmark")
        return getattr(module, name)
    if name in _CONTROLLED_PUBLISH_EXPORTS:
        module = importlib.import_module("app.ml.controlled_publish")
        return getattr(module, name)
    if name in _SECOND_PASS_EXPORTS:
        module = importlib.import_module("app.ml.second_pass")
        return getattr(module, name)
    if name in _SECOND_PASS_EXPERIMENT_EXPORTS:
        module = importlib.import_module("app.ml.second_pass_experiment")
        return getattr(module, name)
    if name in _V4_DATASET_EXPORTS:
        module = importlib.import_module("app.ml.v4_dataset")
        return getattr(module, name)
    if name in _SEO_WEIGHTED_CANDIDATE_TRAINING_EXPORTS:
        module = importlib.import_module("app.ml.seo_weighted_candidate_training")
        return getattr(module, name)
    if name in _SEO_WEIGHTED_SHADOW_BENCHMARK_EXPORTS:
        module = importlib.import_module("app.ml.seo_weighted_shadow_benchmark")
        return getattr(module, name)
    if name in _SEO_WEIGHTED_NO_PUBLISH_DECISION_EXPORTS:
        module = importlib.import_module("app.ml.seo_weighted_no_publish_decision")
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
    *_RANKING_BENCHMARK_EXPORTS,
    *_CONTROLLED_PUBLISH_EXPORTS,
    *_SECOND_PASS_EXPORTS,
    *_SECOND_PASS_EXPERIMENT_EXPORTS,
    *_V4_DATASET_EXPORTS,
    *_SEO_WEIGHTED_CANDIDATE_TRAINING_EXPORTS,
    *_SEO_WEIGHTED_SHADOW_BENCHMARK_EXPORTS,
    *_SEO_WEIGHTED_NO_PUBLISH_DECISION_EXPORTS,
]
