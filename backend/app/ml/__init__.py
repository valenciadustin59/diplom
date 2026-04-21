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
    load_saved_model,
    predict_score,
    save_model,
    score_pages,
    train_and_predict,
    train_model,
)


def __getattr__(name: str):
    if name in {
        "DATASET_COLUMNS",
        "DEFAULT_CHECKPOINT_PATH",
        "DEFAULT_DATASET_PATH",
        "DEFAULT_FAILURES_PATH",
        "DEFAULT_SEEDS_PATH",
        "build_dataset",
        "build_dataset_for_query",
        "infer_page_type",
        "load_seed_rows",
        "rank_to_score",
    }:
        module = importlib.import_module("app.ml.dataset_builder")
        return getattr(module, name)

    if name in {"load_dataset_rows", "prepare_training_data", "train_quality_model"}:
        module = importlib.import_module("app.ml.train")
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
    "load_saved_model",
    "predict_score",
    "save_model",
    "score_pages",
    "train_and_predict",
    "train_model",
    "DATASET_COLUMNS",
    "DEFAULT_CHECKPOINT_PATH",
    "DEFAULT_DATASET_PATH",
    "DEFAULT_FAILURES_PATH",
    "DEFAULT_SEEDS_PATH",
    "build_dataset",
    "build_dataset_for_query",
    "infer_page_type",
    "load_seed_rows",
    "rank_to_score",
    "load_dataset_rows",
    "prepare_training_data",
    "train_quality_model",
]
