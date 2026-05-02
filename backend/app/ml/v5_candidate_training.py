from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha1
import json
from math import sqrt
from pathlib import Path
from typing import Any, Mapping, Sequence

from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.ml.model import DEFAULT_MODEL_PATH, load_model_artifact, predict_score, save_model
from app.ml.model_schema import MODEL_SCHEMA_VERSION_V3, resolve_model_feature_schema
from app.ml.publish import ARTIFACTS_DIR, build_artifact_public_metadata, write_artifact_public_metadata
from app.ml.ranking_benchmark import build_feature_importance_summary, build_stability_summary
from app.ml.train import candidate_sort_key, load_dataset_rows, ranking_metrics, rows_to_matrix, split_dataset_rows
from app.ml.v3_dataset import DATASET_VERSIONS_DIR
from app.ml.v5_feature_policy import (
    DEFAULT_CONTROLLED_DATASET_PATH,
    DEFAULT_FEATURE_POLICY_PATH,
    FEATURE_POLICY_VERSION_V5,
    feature_dominance_guardrail,
    score_response_guardrail,
)
from app.ml.v5_preferences import DEFAULT_OUTPUT_PAGE_LABELS_PATH, DEFAULT_OUTPUT_PREFERENCE_LABELS_PATH


DEFAULT_DATASET_VERSION = "dataset-v5"
DEFAULT_D53_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v5-d53"
DEFAULT_D53_REPORT_JSON_PATH = DEFAULT_D53_OUTPUT_DIR / "d53-candidate-training-report.json"
DEFAULT_D53_REPORT_MD_PATH = DEFAULT_D53_OUTPUT_DIR / "d53-candidate-training-report.md"
DEFAULT_D53_POINTWISE_CANDIDATE_PATH = ARTIFACTS_DIR / "page_quality_model.dataset-v5-pointwise-catboost-candidate.pkl"
DEFAULT_D53_RANKING_CANDIDATE_PATH = ARTIFACTS_DIR / "page_quality_model.dataset-v5-ranking-aware-catboost-candidate.pkl"
DEFAULT_D53_HYBRID_CANDIDATE_PATH = ARTIFACTS_DIR / "page_quality_model.dataset-v5-hybrid-candidate.pkl"
DEFAULT_SPLIT_PATH = DATASET_VERSIONS_DIR / DEFAULT_DATASET_VERSION / "split.json"
POINTWISE_CANDIDATE_NAME = "pointwise_catboost_v5"
RANKING_CANDIDATE_NAME = "ranking_aware_catboost_v5"
HYBRID_CANDIDATE_NAME = "hybrid_catboost_ranker_v5"


@dataclass(frozen=True, slots=True)
class PreferencePair:
    query: str
    winner_url: str
    loser_url: str
    weight: float
    strength: str
    reason: str


class V5CalibratedRankerModel:
    def __init__(self, ranker_model: Any, *, raw_min: float, raw_max: float) -> None:
        self.ranker_model = ranker_model
        self.raw_min = float(raw_min)
        self.raw_max = float(raw_max)

    def _scale(self, value: float) -> float:
        if self.raw_max <= self.raw_min:
            return 50.0
        scaled = ((float(value) - self.raw_min) / (self.raw_max - self.raw_min)) * 100.0
        return max(0.0, min(100.0, scaled))

    def predict(self, rows: Sequence[Sequence[float]]) -> list[float]:
        raw_predictions = self.ranker_model.predict(rows)
        return [self._scale(float(value)) for value in raw_predictions]


class V5HybridRankerModel:
    def __init__(
        self,
        pointwise_model: Any,
        ranker_model: Any,
        *,
        raw_min: float,
        raw_max: float,
        ranking_weight: float = 0.18,
    ) -> None:
        self.pointwise_model = pointwise_model
        self.ranker_model = ranker_model
        self.raw_min = float(raw_min)
        self.raw_max = float(raw_max)
        self.ranking_weight = max(0.0, min(1.0, float(ranking_weight)))

    def _rank_score(self, value: float) -> float:
        if self.raw_max <= self.raw_min:
            return 50.0
        scaled = ((float(value) - self.raw_min) / (self.raw_max - self.raw_min)) * 100.0
        return max(0.0, min(100.0, scaled))

    def predict(self, rows: Sequence[Sequence[float]]) -> list[float]:
        pointwise_predictions = [max(0.0, min(100.0, float(value))) for value in self.pointwise_model.predict(rows)]
        ranking_predictions = [self._rank_score(float(value)) for value in self.ranker_model.predict(rows)]
        return [
            max(0.0, min(100.0, (1.0 - self.ranking_weight) * pointwise + self.ranking_weight * ranking))
            for pointwise, ranking in zip(pointwise_predictions, ranking_predictions, strict=False)
        ]


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sha1_file(path: str | Path | None) -> str | None:
    if path is None:
        return None
    resolved_path = Path(path)
    if not resolved_path.exists() or not resolved_path.is_file():
        return None
    digest = sha1()
    with resolved_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return {}
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return []
    with resolved_path.open("r", encoding="utf-8-sig", newline="") as file:
        return [dict(row) for row in csv.DictReader(file)]


def load_preference_pairs(path: str | Path = DEFAULT_OUTPUT_PREFERENCE_LABELS_PATH) -> list[PreferencePair]:
    pairs: list[PreferencePair] = []
    for row in _read_csv_rows(path):
        if str(row.get("usable_for_training") or "").strip().lower() not in {"true", "1", "yes"}:
            continue
        pairs.append(
            PreferencePair(
                query=str(row.get("query") or "").strip(),
                winner_url=str(row.get("winner_url") or "").strip(),
                loser_url=str(row.get("loser_url") or "").strip(),
                weight=max(0.0, _safe_float(row.get("weight"), 1.0)),
                strength=str(row.get("preference_strength") or "unknown"),
                reason=str(row.get("reason") or "unknown"),
            )
        )
    return pairs


def _page_label_targets(path: str | Path = DEFAULT_OUTPUT_PAGE_LABELS_PATH) -> dict[tuple[str, str], dict[str, float]]:
    targets: dict[tuple[str, str], dict[str, float]] = {}
    for row in _read_csv_rows(path):
        key = (str(row.get("query") or "").strip(), str(row.get("url") or "").strip())
        targets[key] = {
            "page_target_score": _safe_float(row.get("page_target_score"), _safe_float(row.get("target_score"))),
            "ranking_target_score": _safe_float(row.get("ranking_target_score"), _safe_float(row.get("target_score"))),
        }
    return targets


def attach_v5_targets(
    rows: Sequence[dict[str, str]],
    page_label_targets: Mapping[tuple[str, str], Mapping[str, float]],
) -> list[dict[str, str]]:
    enriched_rows: list[dict[str, str]] = []
    for row in rows:
        key = (str(row.get("query") or "").strip(), str(row.get("url") or "").strip())
        targets = page_label_targets.get(key, {})
        page_target = _safe_float(targets.get("page_target_score"), _safe_float(row.get("target_score")))
        ranking_target = _safe_float(targets.get("ranking_target_score"), page_target)
        enriched = dict(row)
        enriched["target_score"] = str(page_target)
        enriched["page_target_score"] = str(page_target)
        enriched["ranking_target_score"] = str(ranking_target)
        enriched_rows.append(enriched)
    return enriched_rows


def split_rows_from_manifest(
    rows: Sequence[dict[str, str]],
    split: Mapping[str, Any],
    *,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    train_queries = {str(query) for query in split.get("train_queries") or [] if str(query).strip()}
    validation_queries = {str(query) for query in split.get("validation_queries") or [] if str(query).strip()}
    if train_queries and validation_queries and not (train_queries & validation_queries):
        train_rows = [dict(row) for row in rows if str(row.get("query") or "") in train_queries]
        validation_rows = [dict(row) for row in rows if str(row.get("query") or "") in validation_queries]
        if train_rows and validation_rows:
            return (
                train_rows,
                validation_rows,
                {
                    "split_mode": str(split.get("split_mode") or "group_by_query"),
                    "source": "dataset-v5/split.json",
                    "train_rows_count": len(train_rows),
                    "validation_rows_count": len(validation_rows),
                    "train_queries_count": len(train_queries),
                    "validation_queries_count": len(validation_queries),
                    "query_overlap_count": 0,
                },
            )
    fallback_rows = [dict(row) for row in rows]
    train_rows, validation_rows, split_metadata = split_dataset_rows(
        fallback_rows,
        test_size=test_size,
        random_state=random_state,
    )
    return train_rows, validation_rows, {**split_metadata, "source": "fallback_group_split"}


def _rows_to_matrix_with_target(
    rows: Sequence[dict[str, str]],
    *,
    feature_columns: Sequence[str],
    target_key: str,
) -> tuple[list[list[float]], list[float]]:
    x = [[_safe_float(row.get(feature_name)) for feature_name in feature_columns] for row in rows]
    y = [_safe_float(row.get(target_key), _safe_float(row.get("target_score"))) for row in rows]
    return x, y


def _sorted_rows_by_query(rows: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        [dict(row) for row in rows],
        key=lambda row: (
            str(row.get("query") or ""),
            int(float(row.get("rank") or 0)),
            str(row.get("url") or ""),
        ),
    )


def _build_group_ids(rows: Sequence[dict[str, str]]) -> list[int]:
    group_ids: list[int] = []
    previous_query: str | None = None
    group_id = 0
    for row in rows:
        query = str(row.get("query") or "")
        if query != previous_query:
            group_id += 1
            previous_query = query
        group_ids.append(group_id)
    return group_ids


def build_catboost_pairs(
    sorted_rows: Sequence[dict[str, str]],
    preferences: Sequence[PreferencePair],
) -> tuple[list[tuple[int, int]], list[float], dict[str, Any]]:
    index_by_key = {
        (str(row.get("query") or "").strip(), str(row.get("url") or "").strip()): index
        for index, row in enumerate(sorted_rows)
    }
    pairs: list[tuple[int, int]] = []
    weights: list[float] = []
    strengths: dict[str, int] = {}
    reasons: dict[str, int] = {}
    skipped = 0
    for preference in preferences:
        winner_key = (preference.query, preference.winner_url)
        loser_key = (preference.query, preference.loser_url)
        if winner_key not in index_by_key or loser_key not in index_by_key:
            skipped += 1
            continue
        pairs.append((index_by_key[winner_key], index_by_key[loser_key]))
        weights.append(preference.weight or 1.0)
        strengths[preference.strength] = strengths.get(preference.strength, 0) + 1
        reasons[preference.reason] = reasons.get(preference.reason, 0) + 1
    return (
        pairs,
        weights,
        {
            "pairs_count": len(pairs),
            "skipped_preferences_count": skipped,
            "strength_distribution": dict(sorted(strengths.items())),
            "reason_distribution": dict(sorted(reasons.items())),
        },
    )


def _preference_accuracy(
    *,
    rows: Sequence[dict[str, str]],
    predictions: Sequence[float],
    preferences: Sequence[PreferencePair],
) -> dict[str, Any]:
    prediction_by_key = {
        (str(row.get("query") or "").strip(), str(row.get("url") or "").strip()): float(prediction)
        for row, prediction in zip(rows, predictions, strict=False)
    }
    total = 0
    correct = 0
    weighted_total = 0.0
    weighted_correct = 0.0
    for preference in preferences:
        winner_key = (preference.query, preference.winner_url)
        loser_key = (preference.query, preference.loser_url)
        if winner_key not in prediction_by_key or loser_key not in prediction_by_key:
            continue
        total += 1
        weight = preference.weight or 1.0
        weighted_total += weight
        if prediction_by_key[winner_key] > prediction_by_key[loser_key]:
            correct += 1
            weighted_correct += weight
    return {
        "evaluated_preferences_count": total,
        "accuracy": round(correct / total, 6) if total else 0.0,
        "weighted_accuracy": round(weighted_correct / weighted_total, 6) if weighted_total > 0.0 else 0.0,
    }


def _evaluate_predictions(
    rows: Sequence[dict[str, str]],
    predictions: Sequence[float],
    *,
    preferences: Sequence[PreferencePair],
) -> dict[str, Any]:
    y_true = [_safe_float(row.get("target_score")) for row in rows]
    y_pred = [float(value) for value in predictions]
    metrics = {
        "rmse": round(sqrt(float(mean_squared_error(y_true, y_pred))), 6),
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 6),
    }
    metrics.update(ranking_metrics([dict(row) for row in rows], y_pred))
    metrics["preference_accuracy"] = _preference_accuracy(rows=rows, predictions=y_pred, preferences=preferences)
    return metrics


def _train_pointwise_catboost(
    train_rows: Sequence[dict[str, str]],
    validation_rows: Sequence[dict[str, str]],
    *,
    feature_columns: Sequence[str],
    model_schema_version: str,
    random_state: int,
    validation_preferences: Sequence[PreferencePair],
) -> dict[str, Any]:
    try:
        from catboost import CatBoostError, CatBoostRegressor
    except ImportError:
        return _unavailable_candidate(POINTWISE_CANDIDATE_NAME, "catboost_not_installed", feature_columns, model_schema_version)
    x_train, y_train = _rows_to_matrix_with_target(train_rows, feature_columns=feature_columns, target_key="page_target_score")
    model = CatBoostRegressor(
        loss_function="RMSE",
        depth=6,
        learning_rate=0.045,
        iterations=550,
        random_seed=random_state,
        verbose=False,
        allow_writing_files=False,
    )
    try:
        model.fit(x_train, y_train)
        x_validation, _ = _rows_to_matrix_with_target(
            validation_rows,
            feature_columns=feature_columns,
            target_key="page_target_score",
        )
        predictions = [max(0.0, min(100.0, float(value))) for value in model.predict(x_validation)]
    except CatBoostError as error:
        return _unavailable_candidate(
            POINTWISE_CANDIDATE_NAME,
            f"catboost_training_failed: {error}",
            feature_columns,
            model_schema_version,
        )
    return _available_candidate(
        candidate_name=POINTWISE_CANDIDATE_NAME,
        candidate_family="pointwise",
        model=model,
        model_type="CatBoostRegressor",
        validation_rows=validation_rows,
        predictions=predictions,
        feature_columns=feature_columns,
        model_schema_version=model_schema_version,
        validation_preferences=validation_preferences,
        feature_importance_summary=build_feature_importance_summary(model, tuple(feature_columns)),
        training_target="page_target_score",
    )


def _train_ranking_catboost(
    train_rows: Sequence[dict[str, str]],
    validation_rows: Sequence[dict[str, str]],
    *,
    feature_columns: Sequence[str],
    model_schema_version: str,
    train_preferences: Sequence[PreferencePair],
    validation_preferences: Sequence[PreferencePair],
    random_state: int,
) -> dict[str, Any]:
    try:
        from catboost import CatBoostError, CatBoostRanker
    except ImportError:
        return _unavailable_candidate(RANKING_CANDIDATE_NAME, "catboost_not_installed", feature_columns, model_schema_version)
    sorted_train_rows = _sorted_rows_by_query(train_rows)
    x_train, y_train = _rows_to_matrix_with_target(
        sorted_train_rows,
        feature_columns=feature_columns,
        target_key="ranking_target_score",
    )
    group_id = _build_group_ids(sorted_train_rows)
    pairs, pairs_weight, pair_summary = build_catboost_pairs(sorted_train_rows, train_preferences)
    model = CatBoostRanker(
        loss_function="YetiRankPairwise",
        iterations=180,
        depth=6,
        learning_rate=0.05,
        random_seed=random_state,
        verbose=False,
        allow_writing_files=False,
    )
    fit_kwargs: dict[str, Any] = {"group_id": group_id}
    if pairs:
        fit_kwargs["pairs"] = pairs
        fit_kwargs["pairs_weight"] = pairs_weight
    try:
        model.fit(x_train, y_train, **fit_kwargs)
        x_train_raw, _ = _rows_to_matrix_with_target(
            sorted_train_rows,
            feature_columns=feature_columns,
            target_key="ranking_target_score",
        )
        train_raw_predictions = [float(value) for value in model.predict(x_train_raw)]
        calibrated_model = V5CalibratedRankerModel(
            model,
            raw_min=min(train_raw_predictions) if train_raw_predictions else 0.0,
            raw_max=max(train_raw_predictions) if train_raw_predictions else 1.0,
        )
        x_validation, _ = _rows_to_matrix_with_target(
            validation_rows,
            feature_columns=feature_columns,
            target_key="page_target_score",
        )
        predictions = [float(value) for value in calibrated_model.predict(x_validation)]
    except CatBoostError as error:
        return _unavailable_candidate(
            RANKING_CANDIDATE_NAME,
            f"catboost_ranker_training_failed: {error}",
            feature_columns,
            model_schema_version,
        )
    return _available_candidate(
        candidate_name=RANKING_CANDIDATE_NAME,
        candidate_family="ranking",
        model=calibrated_model,
        model_type="V5CalibratedRankerModel",
        validation_rows=validation_rows,
        predictions=predictions,
        feature_columns=feature_columns,
        model_schema_version=model_schema_version,
        validation_preferences=validation_preferences,
        feature_importance_summary=build_feature_importance_summary(model, tuple(feature_columns)),
        training_target="ranking_target_score_with_preference_pairs",
        extra={
            "raw_ranker_model_type": model.__class__.__name__,
            "ranker_calibration": {
                "raw_min": calibrated_model.raw_min,
                "raw_max": calibrated_model.raw_max,
                "method": "train_minmax_to_0_100",
            },
            "preference_pair_summary": pair_summary,
        },
    )


def _build_hybrid_candidate(
    *,
    pointwise_candidate: Mapping[str, Any],
    ranking_candidate: Mapping[str, Any],
    train_rows: Sequence[dict[str, str]],
    validation_rows: Sequence[dict[str, str]],
    feature_columns: Sequence[str],
    model_schema_version: str,
    validation_preferences: Sequence[PreferencePair],
    ranking_weight: float = 0.18,
) -> dict[str, Any]:
    if pointwise_candidate.get("status") != "available" or ranking_candidate.get("status") != "available":
        return _unavailable_candidate(
            HYBRID_CANDIDATE_NAME,
            "required_base_candidate_unavailable",
            feature_columns,
            model_schema_version,
        )
    ranking_model = ranking_candidate.get("model")
    pointwise_model = pointwise_candidate.get("model")
    raw_ranker = getattr(ranking_model, "ranker_model", None)
    if pointwise_model is None or raw_ranker is None:
        return _unavailable_candidate(
            HYBRID_CANDIDATE_NAME,
            "ranker_or_pointwise_model_missing",
            feature_columns,
            model_schema_version,
        )
    hybrid_model = V5HybridRankerModel(
        pointwise_model,
        raw_ranker,
        raw_min=float(getattr(ranking_model, "raw_min", 0.0)),
        raw_max=float(getattr(ranking_model, "raw_max", 1.0)),
        ranking_weight=ranking_weight,
    )
    x_validation, _ = _rows_to_matrix_with_target(validation_rows, feature_columns=feature_columns, target_key="page_target_score")
    predictions = [float(value) for value in hybrid_model.predict(x_validation)]
    feature_importance = pointwise_candidate.get("feature_importance_summary")
    return _available_candidate(
        candidate_name=HYBRID_CANDIDATE_NAME,
        candidate_family="hybrid",
        model=hybrid_model,
        model_type="V5HybridRankerModel",
        validation_rows=validation_rows,
        predictions=predictions,
        feature_columns=feature_columns,
        model_schema_version=model_schema_version,
        validation_preferences=validation_preferences,
        feature_importance_summary=feature_importance if isinstance(feature_importance, dict) else {"available": False, "top_features": []},
        training_target="page_score_plus_calibrated_ranker_signal",
        extra={
            "ranking_weight": ranking_weight,
            "pointwise_candidate": pointwise_candidate.get("candidate_name"),
            "ranking_candidate": ranking_candidate.get("candidate_name"),
            "calibration_rows_count": len(train_rows),
        },
    )


def _unavailable_candidate(
    candidate_name: str,
    reason: str,
    feature_columns: Sequence[str],
    model_schema_version: str,
) -> dict[str, Any]:
    return {
        "candidate_name": candidate_name,
        "candidate_family": "unknown",
        "status": "unavailable",
        "reason": reason,
        "model": None,
        "model_type": None,
        "model_schema_version": model_schema_version,
        "feature_count": len(feature_columns),
        "metrics": {},
        "feature_importance_summary": {"available": False, "top_features": []},
        "stability": {},
    }


def _available_candidate(
    *,
    candidate_name: str,
    candidate_family: str,
    model: Any,
    model_type: str,
    validation_rows: Sequence[dict[str, str]],
    predictions: Sequence[float],
    feature_columns: Sequence[str],
    model_schema_version: str,
    validation_preferences: Sequence[PreferencePair],
    feature_importance_summary: Mapping[str, Any],
    training_target: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = _evaluate_predictions(validation_rows, predictions, preferences=validation_preferences)
    return {
        "candidate_name": candidate_name,
        "candidate_family": candidate_family,
        "status": "available",
        "reason": None,
        "model": model,
        "model_type": model_type,
        "model_schema_version": model_schema_version,
        "feature_count": len(feature_columns),
        "metrics": metrics,
        "stability": build_stability_summary([dict(row) for row in validation_rows], [float(value) for value in predictions]),
        "feature_importance_summary": dict(feature_importance_summary),
        "training_target": training_target,
        **(dict(extra or {})),
    }


def _serialize_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    omitted = {"model"}
    return {key: value for key, value in candidate.items() if key not in omitted}


def _save_candidate_artifact(
    candidate: dict[str, Any],
    model_path: str | Path,
    *,
    dataset_path: str | Path,
    feature_columns: Sequence[str],
    generated_at: str,
    preference_summary: Mapping[str, Any],
    feature_policy_path: str | Path,
    report_json_path: str | Path,
) -> Path | None:
    if candidate.get("status") != "available" or candidate.get("model") is None:
        return None
    metadata = {
        "source": "local_dataset",
        "dataset_version": DEFAULT_DATASET_VERSION,
        "artifact_version": f"dataset-v5-d53-{candidate['candidate_name']}",
        "artifact_family": Path(model_path).stem,
        "model_schema_version": candidate.get("model_schema_version") or MODEL_SCHEMA_VERSION_V3,
        "feature_columns": list(feature_columns),
        "model_type": candidate.get("model_type"),
        "candidate_name": candidate.get("candidate_name"),
        "candidate_family": candidate.get("candidate_family"),
        "training_task": "D53",
        "trained_at": generated_at,
        "non_production": True,
        "runtime_enabled": False,
        "publish_decision_required": "D54",
        "dataset_path": str(Path(dataset_path)),
        "feature_policy_version": FEATURE_POLICY_VERSION_V5,
        "feature_policy_path": str(Path(feature_policy_path)),
        "preference_summary": dict(preference_summary),
        "training_target": candidate.get("training_target"),
        "feature_importance_summary": candidate.get("feature_importance_summary"),
        "training_report_path": str(Path(report_json_path)),
    }
    return save_model(candidate["model"], candidate["metrics"], model_path=model_path, metadata=metadata)


def _sample_features(row: Mapping[str, str], feature_columns: Sequence[str]) -> dict[str, float]:
    return {feature_name: _safe_float(row.get(feature_name)) for feature_name in feature_columns}


def _compatibility_check(
    model_path: str | Path,
    sample_row: Mapping[str, str],
    feature_columns: Sequence[str],
    *,
    expected_model_schema_version: str,
) -> dict[str, Any]:
    artifact = load_model_artifact(model_path)
    sample_score = predict_score(_sample_features(sample_row, feature_columns), model_path=model_path) if artifact else None
    return {
        "load_model_artifact": artifact is not None,
        "predict_score_bounded": sample_score is not None and 0.0 <= float(sample_score) <= 100.0,
        "sample_score": round(float(sample_score), 4) if sample_score is not None else None,
        "model_schema_version": artifact.get("model_schema_version") if artifact else None,
        "feature_count": len(artifact.get("feature_columns") or []) if artifact else 0,
        "dataset_version": artifact.get("dataset_version") if artifact else None,
        "passed": bool(
            artifact is not None
            and artifact.get("model_schema_version") == expected_model_schema_version
            and len(artifact.get("feature_columns") or []) == len(feature_columns)
            and artifact.get("dataset_version") == DEFAULT_DATASET_VERSION
            and sample_score is not None
            and 0.0 <= float(sample_score) <= 100.0
        ),
    }


def _write_candidate_metadata_sidecar(
    candidate: Mapping[str, Any],
    model_path: str | Path,
    *,
    compatibility: Mapping[str, Any],
    report_json_path: str | Path,
) -> dict[str, Any]:
    resolved_path = Path(model_path)
    artifact = load_model_artifact(resolved_path) or {}
    metadata = build_artifact_public_metadata(artifact, resolved_path)
    metadata.update(
        {
            "training_task": "D53",
            "candidate_name": candidate.get("candidate_name"),
            "candidate_family": candidate.get("candidate_family"),
            "candidate_status": candidate.get("status"),
            "non_production": True,
            "runtime_enabled": False,
            "publish_decision_required": "D54",
            "feature_policy_version": FEATURE_POLICY_VERSION_V5,
            "training_target": candidate.get("training_target"),
            "feature_importance_summary": candidate.get("feature_importance_summary"),
            "compatibility_check": dict(compatibility),
            "training_report_path": str(Path(report_json_path)),
            "sha1": _sha1_file(resolved_path),
        }
    )
    metadata_path = resolved_path.with_suffix(".metadata.json")
    write_artifact_public_metadata(metadata, metadata_path)
    return {
        "artifact_path": str(resolved_path),
        "metadata_path": str(metadata_path),
        "sha1": metadata["sha1"],
        "compatibility_check": dict(compatibility),
    }


def _guardrail_prechecks(
    candidates: Sequence[Mapping[str, Any]],
    *,
    validation_rows: Sequence[dict[str, str]],
    model_paths: Mapping[str, str],
) -> dict[str, Any]:
    prechecks: dict[str, Any] = {}
    for candidate in candidates:
        candidate_name = str(candidate.get("candidate_name") or "unknown")
        model_path = model_paths.get(candidate_name)
        if candidate.get("status") != "available" or model_path is None:
            continue
        feature_guardrail = feature_dominance_guardrail(candidate)
        response_guardrail = score_response_guardrail(model_path=model_path, rows=validation_rows)
        checks = {
            "feature_dominance_passed": bool(feature_guardrail.get("passed")),
            "score_response_passed": bool(response_guardrail.get("passed")),
        }
        prechecks[candidate_name] = {
            "passed": all(checks.values()),
            "checks": checks,
            "feature_dominance_guardrail": feature_guardrail,
            "score_response_guardrail": response_guardrail,
        }
    return prechecks


def _preference_summary(
    preferences: Sequence[PreferencePair],
    *,
    train_preferences: Sequence[PreferencePair],
    validation_preferences: Sequence[PreferencePair],
) -> dict[str, Any]:
    return {
        "usable_preferences_count": len(preferences),
        "train_preferences_count": len(train_preferences),
        "validation_preferences_count": len(validation_preferences),
        "strength_distribution": _count_by(preferences, lambda item: item.strength),
        "reason_distribution": _count_by(preferences, lambda item: item.reason),
    }


def _count_by(items: Sequence[PreferencePair], key_fn: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = str(key_fn(item))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# D53 Ranking-Aware v5 Candidate Training",
        "",
        f"- Dataset: `{report.get('dataset_path')}`",
        f"- Dataset version: `{report.get('dataset_version')}`",
        f"- Feature policy: `{report.get('feature_policy_version')}`",
        f"- Model schema: `{report.get('model_schema_version')}`",
        f"- Feature count: `{report.get('feature_count')}`",
        f"- Production artifact changed: `{report.get('production_artifact', {}).get('changed_by_d53')}`",
        "",
        "## Saved Non-Production Artifacts",
        "",
    ]
    for candidate_name, metadata in (report.get("candidate_metadata") or {}).items():
        lines.extend(
            [
                f"### {candidate_name}",
                f"- Artifact: `{metadata.get('artifact_path')}`",
                f"- Metadata: `{metadata.get('metadata_path')}`",
                f"- SHA1: `{metadata.get('sha1')}`",
                f"- Compatibility passed: `{metadata.get('compatibility_check', {}).get('passed')}`",
                "",
            ]
        )
    lines.extend(["## Candidates", ""])
    for candidate in report.get("candidates") or []:
        if not isinstance(candidate, dict):
            continue
        metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {}
        preference = metrics.get("preference_accuracy") if isinstance(metrics.get("preference_accuracy"), dict) else {}
        lines.extend(
            [
                f"### {candidate.get('candidate_name')}",
                f"- Status: `{candidate.get('status')}`",
                f"- Family: `{candidate.get('candidate_family')}`",
                f"- Model type: `{candidate.get('model_type')}`",
                f"- RMSE: `{metrics.get('rmse')}`",
                f"- MAE: `{metrics.get('mae')}`",
                f"- Spearman: `{metrics.get('spearman_mean')}`",
                f"- NDCG@10: `{metrics.get('ndcg_at_10')}`",
                f"- Top-3 hit rate: `{metrics.get('top_3_hit_rate')}`",
                f"- Preference accuracy: `{preference.get('weighted_accuracy')}`",
                f"- Reason: `{candidate.get('reason') or 'none'}`",
                "",
            ]
        )
    best = report.get("best_validation_candidate") if isinstance(report.get("best_validation_candidate"), dict) else {}
    lines.extend(
        [
            "## Best Validation Candidate",
            "",
            f"- Candidate: `{best.get('candidate_name')}`",
            f"- Family: `{best.get('candidate_family')}`",
            "",
            "D53 is not a publish decision. D54 must compare these artifacts against the current production model with release guardrails before any publish/no-publish decision.",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def run_d53_candidate_training(
    *,
    dataset_path: str | Path = DEFAULT_CONTROLLED_DATASET_PATH,
    split_path: str | Path = DEFAULT_SPLIT_PATH,
    page_labels_path: str | Path = DEFAULT_OUTPUT_PAGE_LABELS_PATH,
    preference_labels_path: str | Path = DEFAULT_OUTPUT_PREFERENCE_LABELS_PATH,
    feature_policy_path: str | Path = DEFAULT_FEATURE_POLICY_PATH,
    pointwise_model_path: str | Path = DEFAULT_D53_POINTWISE_CANDIDATE_PATH,
    ranking_model_path: str | Path = DEFAULT_D53_RANKING_CANDIDATE_PATH,
    hybrid_model_path: str | Path = DEFAULT_D53_HYBRID_CANDIDATE_PATH,
    reference_model_path: str | Path | None = DEFAULT_MODEL_PATH,
    output_dir: str | Path = DEFAULT_D53_OUTPUT_DIR,
    report_json_path: str | Path | None = None,
    report_markdown_path: str | Path | None = None,
    random_state: int = 42,
    model_schema_version: str = MODEL_SCHEMA_VERSION_V3,
    feature_columns: Sequence[str] | None = None,
) -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat()
    resolved_schema = resolve_model_feature_schema(
        model_schema_version=model_schema_version,
        feature_columns=feature_columns,
        default_version=MODEL_SCHEMA_VERSION_V3,
    )
    resolved_feature_columns = tuple(resolved_schema.feature_columns)
    production_before_sha1 = _sha1_file(reference_model_path)
    rows = attach_v5_targets(load_dataset_rows(dataset_path), _page_label_targets(page_labels_path))
    if len(rows) < 4:
        raise ValueError("D53 requires at least 4 dataset rows")
    train_rows, validation_rows, split_metadata = split_rows_from_manifest(rows, _read_json(split_path), random_state=random_state)
    preferences = load_preference_pairs(preference_labels_path)
    train_queries = {str(row.get("query") or "") for row in train_rows}
    validation_queries = {str(row.get("query") or "") for row in validation_rows}
    train_preferences = [preference for preference in preferences if preference.query in train_queries]
    validation_preferences = [preference for preference in preferences if preference.query in validation_queries]
    preference_summary = _preference_summary(
        preferences,
        train_preferences=train_preferences,
        validation_preferences=validation_preferences,
    )

    pointwise = _train_pointwise_catboost(
        train_rows,
        validation_rows,
        feature_columns=resolved_feature_columns,
        model_schema_version=resolved_schema.version,
        random_state=random_state,
        validation_preferences=validation_preferences,
    )
    ranking = _train_ranking_catboost(
        train_rows,
        validation_rows,
        feature_columns=resolved_feature_columns,
        model_schema_version=resolved_schema.version,
        train_preferences=train_preferences,
        validation_preferences=validation_preferences,
        random_state=random_state,
    )
    hybrid = _build_hybrid_candidate(
        pointwise_candidate=pointwise,
        ranking_candidate=ranking,
        train_rows=train_rows,
        validation_rows=validation_rows,
        feature_columns=resolved_feature_columns,
        model_schema_version=resolved_schema.version,
        validation_preferences=validation_preferences,
    )
    candidates = [pointwise, ranking, hybrid]
    resolved_output_dir = Path(output_dir)
    resolved_report_json_path = Path(report_json_path) if report_json_path is not None else resolved_output_dir / DEFAULT_D53_REPORT_JSON_PATH.name
    resolved_report_markdown_path = (
        Path(report_markdown_path) if report_markdown_path is not None else resolved_output_dir / DEFAULT_D53_REPORT_MD_PATH.name
    )
    output_paths = {
        POINTWISE_CANDIDATE_NAME: str(Path(pointwise_model_path)),
        RANKING_CANDIDATE_NAME: str(Path(ranking_model_path)),
        HYBRID_CANDIDATE_NAME: str(Path(hybrid_model_path)),
    }
    saved_artifacts: dict[str, str] = {}
    for candidate in candidates:
        candidate_name = str(candidate.get("candidate_name") or "")
        model_path = output_paths.get(candidate_name)
        if model_path is None:
            continue
        saved_path = _save_candidate_artifact(
            candidate,
            model_path,
            dataset_path=dataset_path,
            feature_columns=resolved_feature_columns,
            generated_at=generated_at,
            preference_summary=preference_summary,
            feature_policy_path=feature_policy_path,
            report_json_path=resolved_report_json_path,
        )
        if saved_path is not None:
            saved_artifacts[candidate_name] = str(saved_path)
            candidate["model_path"] = str(saved_path)

    sample_row = validation_rows[0] if validation_rows else rows[0]
    candidate_metadata: dict[str, Any] = {}
    for candidate_name, artifact_path in saved_artifacts.items():
        candidate = next(item for item in candidates if item.get("candidate_name") == candidate_name)
        compatibility = _compatibility_check(
            artifact_path,
            sample_row,
            resolved_feature_columns,
            expected_model_schema_version=resolved_schema.version,
        )
        candidate_metadata[candidate_name] = _write_candidate_metadata_sidecar(
            candidate,
            artifact_path,
            compatibility=compatibility,
            report_json_path=resolved_report_json_path,
        )

    guardrail_prechecks = _guardrail_prechecks(candidates, validation_rows=validation_rows, model_paths=saved_artifacts)
    available_candidates = [candidate for candidate in candidates if candidate.get("status") == "available"]
    best_candidate = max(available_candidates, key=candidate_sort_key) if available_candidates else None
    production_after_sha1 = _sha1_file(reference_model_path)
    report: dict[str, Any] = {
        "generated_at": generated_at,
        "task": "D53",
        "dataset_path": str(Path(dataset_path)),
        "dataset_version": DEFAULT_DATASET_VERSION,
        "split_path": str(Path(split_path)),
        "page_labels_path": str(Path(page_labels_path)),
        "preference_labels_path": str(Path(preference_labels_path)),
        "feature_policy_path": str(Path(feature_policy_path)),
        "feature_policy_version": FEATURE_POLICY_VERSION_V5,
        "model_schema_version": resolved_schema.version,
        "feature_count": len(resolved_feature_columns),
        "training_parameters": {
            "random_state": random_state,
            "candidate_families": ["pointwise_catboost", "catboost_ranker_with_preferences", "hybrid"],
            "ranker_loss": "YetiRankPairwise",
            "hybrid_ranking_weight": 0.18,
        },
        "split": split_metadata,
        "rows_count": len(rows),
        "train_rows_count": len(train_rows),
        "validation_rows_count": len(validation_rows),
        "preference_summary": preference_summary,
        "candidate_output_paths": output_paths,
        "saved_artifacts": saved_artifacts,
        "candidate_metadata": candidate_metadata,
        "candidates": [_serialize_candidate(candidate) for candidate in candidates],
        "best_validation_candidate": _serialize_candidate(best_candidate) if best_candidate is not None else None,
        "guardrail_prechecks": guardrail_prechecks,
        "production_artifact": {
            "path": str(Path(reference_model_path)) if reference_model_path is not None else None,
            "sha1_before": production_before_sha1,
            "sha1_after": production_after_sha1,
            "changed_by_d53": production_before_sha1 != production_after_sha1,
        },
        "next_step": "D54 shadow benchmark and controlled publish/no-publish decision. D53 artifacts are non-production.",
    }
    _write_json(resolved_report_json_path, report)
    resolved_report_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_report_markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    report["report_paths"] = {
        "json_path": str(resolved_report_json_path),
        "markdown_path": str(resolved_report_markdown_path),
    }
    _write_json(resolved_report_json_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train D53 non-production ranking-aware v5 candidates.")
    parser.add_argument("--dataset", default=str(DEFAULT_CONTROLLED_DATASET_PATH))
    parser.add_argument("--split", default=str(DEFAULT_SPLIT_PATH))
    parser.add_argument("--page-labels", default=str(DEFAULT_OUTPUT_PAGE_LABELS_PATH))
    parser.add_argument("--preference-labels", default=str(DEFAULT_OUTPUT_PREFERENCE_LABELS_PATH))
    parser.add_argument("--feature-policy", default=str(DEFAULT_FEATURE_POLICY_PATH))
    parser.add_argument("--pointwise-model-output", default=str(DEFAULT_D53_POINTWISE_CANDIDATE_PATH))
    parser.add_argument("--ranking-model-output", default=str(DEFAULT_D53_RANKING_CANDIDATE_PATH))
    parser.add_argument("--hybrid-model-output", default=str(DEFAULT_D53_HYBRID_CANDIDATE_PATH))
    parser.add_argument("--reference-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--without-reference-model", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_D53_OUTPUT_DIR))
    parser.add_argument("--report-json", default="")
    parser.add_argument("--report-md", default="")
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    report = run_d53_candidate_training(
        dataset_path=args.dataset,
        split_path=args.split,
        page_labels_path=args.page_labels,
        preference_labels_path=args.preference_labels,
        feature_policy_path=args.feature_policy,
        pointwise_model_path=args.pointwise_model_output,
        ranking_model_path=args.ranking_model_output,
        hybrid_model_path=args.hybrid_model_output,
        reference_model_path=None if args.without_reference_model else args.reference_model,
        output_dir=args.output_dir,
        report_json_path=args.report_json or None,
        report_markdown_path=args.report_md or None,
        random_state=args.random_state,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
