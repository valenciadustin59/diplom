from __future__ import annotations

from pathlib import Path
from typing import Any

from app.features import SERP_RELATIVE_FEATURE_COLUMNS
from app.ml.model import load_model_artifact
from app.ml.model_schema import MODEL_SCHEMA_VERSION_V3, get_model_feature_schema


SECOND_PASS_CONTRACT_VERSION = "d44-second-pass-v1"
SECOND_PASS_MODEL_SCHEMA_VERSION = "v3-serp-relative-experiment"
SECOND_PASS_CANDIDATE_FAMILY = "second_pass_experiment"
SECOND_PASS_MIN_COMPETITORS = 2


def get_second_pass_feature_columns(
    primary_model_schema_version: str = MODEL_SCHEMA_VERSION_V3,
) -> tuple[str, ...]:
    primary_columns = get_model_feature_schema(primary_model_schema_version).feature_columns
    return primary_columns + tuple(SERP_RELATIVE_FEATURE_COLUMNS)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _bounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 4)


def _feature_vector(features: dict[str, float | int], feature_columns: list[str] | tuple[str, ...]) -> list[float]:
    return [_safe_float(features.get(feature_name)) for feature_name in feature_columns]


def build_second_pass_context(
    features: dict[str, float | int] | None,
    *,
    min_competitors: int = SECOND_PASS_MIN_COMPETITORS,
) -> dict[str, Any]:
    resolved_features = features if isinstance(features, dict) else {}
    context_count = _safe_int(resolved_features.get("serp_relative_context_count"))
    context_available = _safe_float(resolved_features.get("serp_relative_context_available")) >= 1.0
    relative_feature_count = sum(1 for feature_name in SERP_RELATIVE_FEATURE_COLUMNS if feature_name in resolved_features)
    return {
        "context_available": bool(context_available),
        "context_count": context_count,
        "min_competitors_required": int(min_competitors),
        "relative_feature_count": relative_feature_count,
        "ready": bool(context_available and context_count >= min_competitors),
    }


def build_second_pass_score_result(
    *,
    primary_score: float,
    enriched_features: dict[str, float | int] | None,
    candidate_model_path: str | Path | None = None,
    min_competitors: int = SECOND_PASS_MIN_COMPETITORS,
) -> dict[str, Any]:
    context = build_second_pass_context(enriched_features, min_competitors=min_competitors)
    primary_score_value = _bounded_score(float(primary_score))
    base_payload: dict[str, Any] = {
        "contract_version": SECOND_PASS_CONTRACT_VERSION,
        "stage": "post_competitor_aggregation",
        "status": "skipped",
        "reason": None,
        "primary_score": primary_score_value,
        "second_pass_score": None,
        "effective_score": primary_score_value,
        "runtime_effect": "primary_score_preserved",
        "context": context,
        "candidate_model": None,
    }

    if not context["ready"]:
        base_payload["reason"] = "insufficient_competitor_context"
        return base_payload
    if candidate_model_path is None:
        base_payload["reason"] = "candidate_model_not_configured"
        return base_payload

    artifact = load_model_artifact(candidate_model_path)
    if artifact is None:
        base_payload["reason"] = "candidate_model_unavailable"
        base_payload["candidate_model"] = {"model_path": str(Path(candidate_model_path))}
        return base_payload

    feature_columns = artifact.get("feature_columns") if isinstance(artifact.get("feature_columns"), list) else []
    model = artifact["model"]
    prediction = float(model.predict([_feature_vector(enriched_features or {}, feature_columns)])[0])
    second_pass_score = _bounded_score(prediction)
    return {
        **base_payload,
        "status": "available",
        "reason": None,
        "second_pass_score": second_pass_score,
        "effective_score": primary_score_value,
        "runtime_effect": "candidate_score_reported_only",
        "candidate_model": {
            "model_path": str(Path(candidate_model_path)),
            "artifact_version": artifact.get("artifact_version"),
            "model_type": artifact.get("model_type"),
            "model_schema_version": artifact.get("model_schema_version"),
            "feature_count": len(feature_columns),
        },
    }
