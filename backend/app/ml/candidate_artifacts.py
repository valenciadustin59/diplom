from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from app.ml.model import DEFAULT_MODEL_PATH, save_model
from app.ml.model_schema import DEFAULT_TRAINING_MODEL_SCHEMA_VERSION, resolve_model_feature_schema
from app.ml.publish import ARTIFACTS_DIR
from app.ml.ranking_benchmark import (
    DEFAULT_RANKING_DATASET_PATH,
    build_feature_importance_summary,
    build_stability_summary,
    train_catboost_ranker_candidate,
    train_lightgbm_ranker_candidate,
    train_xgboost_ranker_candidate,
)
from app.ml.train import (
    candidate_sort_key,
    load_dataset_rows,
    rows_to_matrix,
    split_dataset_rows,
    train_candidate_models,
)


POINTWISE_RANDOM_FOREST_CANDIDATE = "pointwise_random_forest"
POINTWISE_CATBOOST_CANDIDATE = "pointwise_catboost"
DEFAULT_RF_CANDIDATE_PATH = ARTIFACTS_DIR / "page_quality_model.dataset-v2-expert-rf-candidate.pkl"
DEFAULT_CATBOOST_CANDIDATE_PATH = ARTIFACTS_DIR / "page_quality_model.dataset-v2-expert-catboost-candidate.pkl"
DEFAULT_RANKING_CANDIDATE_PATH = ARTIFACTS_DIR / "page_quality_model.dataset-v2-ranking-candidate.pkl"
DEFAULT_D34_CANDIDATE_REPORTS_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v2-d34"


def _sha1_file(path: str | Path | None) -> str | None:
    if path is None:
        return None
    resolved_path = Path(path)
    if not resolved_path.exists() or not resolved_path.is_file():
        return None
    digest = hashlib.sha1()
    with resolved_path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dataset_version(dataset_path: str | Path, rows: list[dict[str, str]], explicit_version: str | None) -> str:
    if explicit_version:
        return explicit_version
    return str(rows[0].get("dataset_version") or Path(dataset_path).stem)


def _normalized_path(path: str | Path) -> Path:
    return Path(path).resolve()


def _validate_candidate_output_paths(
    candidate_output_paths: list[str | Path],
    *,
    reference_model_path: str | Path | None,
) -> None:
    protected_paths = {_normalized_path(DEFAULT_MODEL_PATH)}
    if reference_model_path is not None:
        protected_paths.add(_normalized_path(reference_model_path))
    normalized_outputs = [_normalized_path(path) for path in candidate_output_paths]
    duplicate_outputs = {
        str(output_path)
        for output_path in normalized_outputs
        if normalized_outputs.count(output_path) > 1
    }
    if duplicate_outputs:
        raise ValueError(f"Candidate artifact output paths must be unique: {sorted(duplicate_outputs)}")
    protected_overwrites = sorted(str(output_path) for output_path in normalized_outputs if output_path in protected_paths)
    if protected_overwrites:
        raise ValueError(
            "Candidate artifact output paths must not overwrite the production/reference artifact: "
            f"{protected_overwrites}"
        )


def _split_summary(
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    split_metadata: dict[str, object],
) -> dict[str, object]:
    train_queries = {str(row.get("query") or "") for row in train_rows if str(row.get("query") or "").strip()}
    validation_queries = {
        str(row.get("query") or "") for row in validation_rows if str(row.get("query") or "").strip()
    }
    return {
        **split_metadata,
        "train_rows_count": len(train_rows),
        "validation_rows_count": len(validation_rows),
        "train_queries_count": len(train_queries),
        "validation_queries_count": len(validation_queries),
        "query_overlap_count": len(train_queries & validation_queries),
    }


def _unavailable_candidate(
    candidate_name: str,
    candidate_family: str,
    reason: str,
    *,
    model_schema_version: str,
    feature_count: int,
) -> dict[str, Any]:
    return {
        "candidate_name": candidate_name,
        "candidate_family": candidate_family,
        "status": "unavailable",
        "model_type": None,
        "model_schema_version": model_schema_version,
        "feature_count": feature_count,
        "metrics": {},
        "stability": {},
        "feature_importance_summary": {"available": False, "top_features": []},
        "reason": reason,
        "model": None,
    }


def _pointwise_candidate_name(model_type: str) -> str:
    if model_type == "RandomForestRegressor":
        return POINTWISE_RANDOM_FOREST_CANDIDATE
    if model_type == "CatBoostRegressor":
        return POINTWISE_CATBOOST_CANDIDATE
    return f"pointwise_{model_type.lower()}"


def _build_pointwise_candidate(
    candidate: dict[str, Any],
    validation_rows: list[dict[str, str]],
    *,
    feature_columns: list[str] | tuple[str, ...],
    model_schema_version: str,
) -> dict[str, Any]:
    model = candidate["model"]
    model_type = str(candidate["model_type"])
    x_validation, _ = rows_to_matrix(validation_rows, feature_columns=feature_columns)
    predictions = [float(value) for value in model.predict(x_validation)]
    return {
        "candidate_name": _pointwise_candidate_name(model_type),
        "candidate_family": "pointwise",
        "status": "available",
        "model_type": model_type,
        "model_schema_version": model_schema_version,
        "feature_count": len(feature_columns),
        "metrics": candidate["metrics"],
        "stability": build_stability_summary(validation_rows, predictions),
        "feature_importance_summary": build_feature_importance_summary(model, feature_columns),
        "reason": None,
        "model": model,
    }


def _serialize_candidate(candidate: dict[str, Any] | None) -> dict[str, Any] | None:
    if candidate is None:
        return None
    return {
        "candidate_name": str(candidate.get("candidate_name") or "unknown"),
        "candidate_family": str(candidate.get("candidate_family") or "unknown"),
        "status": str(candidate.get("status") or "unknown"),
        "model_path": candidate.get("model_path"),
        "model_type": candidate.get("model_type"),
        "model_schema_version": candidate.get("model_schema_version"),
        "feature_count": candidate.get("feature_count"),
        "metrics": candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
        "stability": candidate.get("stability") if isinstance(candidate.get("stability"), dict) else {},
        "feature_importance_summary": (
            candidate.get("feature_importance_summary")
            if isinstance(candidate.get("feature_importance_summary"), dict)
            else {"available": False, "top_features": []}
        ),
        "reason": candidate.get("reason"),
    }


def _model_metrics(
    candidate: dict[str, Any],
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    split_metadata: dict[str, object],
) -> dict[str, Any]:
    return {
        **candidate["metrics"],
        "train_rows": float(len(train_rows)),
        "validation_rows": float(len(validation_rows)),
        **split_metadata,
    }


def _model_metadata(
    candidate: dict[str, Any],
    *,
    model_path: str | Path,
    dataset_version: str,
    rows: list[dict[str, str]],
    feature_columns: list[str] | tuple[str, ...],
    model_schema_version: str,
    trained_at: str,
    artifact_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "source": "local_dataset",
        "dataset_version": dataset_version,
        "artifact_version": f"{dataset_version}-{candidate['candidate_name']}",
        "artifact_family": Path(model_path).stem,
        "model_schema_version": model_schema_version,
        "feature_columns": list(feature_columns),
        "model_type": candidate.get("model_type"),
        "candidate_name": candidate.get("candidate_name"),
        "candidate_family": candidate.get("candidate_family"),
        "rows_count": len(rows),
        "queries_count": len({str(row.get("query") or "") for row in rows}),
        "domains_count": len({str(row.get("domain") or "") for row in rows}),
        "trained_at": trained_at,
        **(artifact_metadata or {}),
    }


def _save_candidate_model(
    candidate: dict[str, Any],
    model_path: str | Path,
    *,
    rows: list[dict[str, str]],
    train_rows: list[dict[str, str]],
    validation_rows: list[dict[str, str]],
    split_metadata: dict[str, object],
    dataset_version: str,
    feature_columns: list[str] | tuple[str, ...],
    model_schema_version: str,
    trained_at: str,
    artifact_metadata: dict[str, Any] | None = None,
) -> Path:
    saved_path = save_model(
        model=candidate["model"],
        metrics=_model_metrics(candidate, train_rows, validation_rows, split_metadata),
        model_path=model_path,
        metadata=_model_metadata(
            candidate,
            model_path=model_path,
            dataset_version=dataset_version,
            rows=rows,
            feature_columns=feature_columns,
            model_schema_version=model_schema_version,
            trained_at=trained_at,
            artifact_metadata=artifact_metadata,
        ),
    )
    candidate["model_path"] = str(saved_path)
    return saved_path


def _render_candidate_artifact_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Candidate Artifact Training Report",
        "",
        f"- Dataset path: `{report.get('dataset_path')}`",
        f"- Dataset version: `{report.get('dataset_version')}`",
        f"- Model schema version: `{report.get('model_schema_version')}`",
        f"- Feature count: `{report.get('feature_count')}`",
        f"- Rows: `{report.get('rows_count')}`",
        f"- Queries: `{report.get('queries_count')}`",
        f"- Split mode: `{report.get('split', {}).get('split_mode')}`",
        f"- Validation rows: `{report.get('split', {}).get('validation_rows_count')}`",
        "",
        "## Reference Artifact",
        "",
    ]
    reference_model = report.get("reference_model") if isinstance(report.get("reference_model"), dict) else None
    if reference_model is None:
        lines.append("Reference artifact was not provided.")
    else:
        lines.extend(
            [
                f"- Path: `{reference_model.get('model_path')}`",
                f"- SHA1: `{reference_model.get('sha1')}`",
            ]
        )
    lines.extend(["", "## Saved Artifacts", ""])
    for candidate_name, model_path in (report.get("saved_artifacts") or {}).items():
        lines.append(f"- `{candidate_name}`: `{model_path}`")
    lines.extend(["", "## Candidates", ""])
    candidates = report.get("candidates") if isinstance(report.get("candidates"), list) else []
    for candidate in candidates:
        lines.extend(
            [
                f"### {candidate.get('candidate_name')}",
                f"- Family: `{candidate.get('candidate_family')}`",
                f"- Status: `{candidate.get('status')}`",
                f"- Model path: `{candidate.get('model_path')}`",
                f"- Model type: `{candidate.get('model_type')}`",
                f"- RMSE: `{candidate.get('metrics', {}).get('rmse')}`",
                f"- MAE: `{candidate.get('metrics', {}).get('mae')}`",
                f"- NDCG@10: `{candidate.get('metrics', {}).get('ndcg_at_10')}`",
                f"- Top-3 hit rate: `{candidate.get('metrics', {}).get('top_3_hit_rate')}`",
                f"- Spearman mean: `{candidate.get('metrics', {}).get('spearman_mean')}`",
            ]
        )
        reason = candidate.get("reason")
        if reason:
            lines.append(f"- Reason: `{reason}`")
        lines.append("")
    for section_key, section_title in (
        ("best_pointwise_candidate", "Best Pointwise Candidate"),
        ("best_ranking_candidate", "Best Ranking Candidate"),
        ("best_overall_candidate", "Best Overall Candidate"),
    ):
        candidate = report.get(section_key) if isinstance(report.get(section_key), dict) else None
        if candidate is None:
            continue
        lines.extend(
            [
                f"## {section_title}",
                "",
                f"- Candidate: `{candidate.get('candidate_name')}`",
                f"- Family: `{candidate.get('candidate_family')}`",
                f"- Model path: `{candidate.get('model_path')}`",
                f"- NDCG@10: `{candidate.get('metrics', {}).get('ndcg_at_10')}`",
                f"- Top-3 hit rate: `{candidate.get('metrics', {}).get('top_3_hit_rate')}`",
                f"- Spearman mean: `{candidate.get('metrics', {}).get('spearman_mean')}`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def write_candidate_artifact_report(report: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    resolved_output_dir = Path(output_dir)
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    json_path = resolved_output_dir / "candidate-artifact-training-report.json"
    markdown_path = resolved_output_dir / "candidate-artifact-training-report.md"
    report_paths = {"json_path": str(json_path), "markdown_path": str(markdown_path)}
    report_with_paths = {**report, "report_paths": report_paths}
    json_path.write_text(json.dumps(report_with_paths, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_candidate_artifact_report_markdown(report_with_paths), encoding="utf-8")
    return report_paths


def train_candidate_artifacts(
    dataset_path: str | Path = DEFAULT_RANKING_DATASET_PATH,
    *,
    dataset_version: str | None = None,
    rf_model_path: str | Path = DEFAULT_RF_CANDIDATE_PATH,
    catboost_model_path: str | Path = DEFAULT_CATBOOST_CANDIDATE_PATH,
    ranking_model_path: str | Path = DEFAULT_RANKING_CANDIDATE_PATH,
    reference_model_path: str | Path | None = DEFAULT_MODEL_PATH,
    output_dir: str | Path | None = DEFAULT_D34_CANDIDATE_REPORTS_DIR,
    test_size: float = 0.2,
    random_state: int = 42,
    model_schema_version: str = DEFAULT_TRAINING_MODEL_SCHEMA_VERSION,
    artifact_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _validate_candidate_output_paths(
        [rf_model_path, catboost_model_path, ranking_model_path],
        reference_model_path=reference_model_path,
    )
    resolved_schema = resolve_model_feature_schema(
        model_schema_version=model_schema_version,
        default_version=DEFAULT_TRAINING_MODEL_SCHEMA_VERSION,
    )
    rows = load_dataset_rows(dataset_path)
    if len(rows) < 4:
        raise ValueError("At least 4 dataset rows are required to train candidate artifacts")
    train_rows, validation_rows, split_metadata = split_dataset_rows(
        rows,
        test_size=test_size,
        random_state=random_state,
    )
    if not train_rows or not validation_rows:
        raise ValueError("Candidate artifact training split produced an empty train or validation set")

    trained_at = datetime.now(UTC).isoformat()
    resolved_dataset_version = _dataset_version(dataset_path, rows, dataset_version)
    feature_columns = resolved_schema.feature_columns
    pointwise_raw_candidates, pointwise_benchmark = train_candidate_models(
        train_rows,
        validation_rows,
        random_state=random_state,
        feature_columns=feature_columns,
        force_catboost=True,
    )
    pointwise_candidates = [
        _build_pointwise_candidate(
            candidate,
            validation_rows,
            feature_columns=feature_columns,
            model_schema_version=resolved_schema.version,
        )
        for candidate in pointwise_raw_candidates
    ]
    available_pointwise_names = {str(candidate.get("candidate_name")) for candidate in pointwise_candidates}
    if POINTWISE_CATBOOST_CANDIDATE not in available_pointwise_names:
        pointwise_candidates.append(
            _unavailable_candidate(
                POINTWISE_CATBOOST_CANDIDATE,
                "pointwise",
                str(pointwise_benchmark.get("catboost_error") or "catboost_not_available"),
                model_schema_version=resolved_schema.version,
                feature_count=len(feature_columns),
            )
        )

    ranking_candidates = [
        train_catboost_ranker_candidate(
            train_rows,
            validation_rows,
            feature_columns=feature_columns,
            model_schema_version=resolved_schema.version,
            random_state=random_state,
        ),
        train_lightgbm_ranker_candidate(
            train_rows,
            validation_rows,
            feature_columns=feature_columns,
            model_schema_version=resolved_schema.version,
            random_state=random_state,
        ),
        train_xgboost_ranker_candidate(
            train_rows,
            validation_rows,
            feature_columns=feature_columns,
            model_schema_version=resolved_schema.version,
            random_state=random_state,
        ),
    ]

    saved_artifacts: dict[str, str] = {}
    pointwise_output_paths = {
        POINTWISE_RANDOM_FOREST_CANDIDATE: rf_model_path,
        POINTWISE_CATBOOST_CANDIDATE: catboost_model_path,
    }
    for candidate in pointwise_candidates:
        if candidate.get("status") != "available":
            continue
        model_path = pointwise_output_paths.get(str(candidate.get("candidate_name")))
        if model_path is None:
            continue
        saved_path = _save_candidate_model(
            candidate,
            model_path,
            rows=rows,
            train_rows=train_rows,
            validation_rows=validation_rows,
            split_metadata=split_metadata,
            dataset_version=resolved_dataset_version,
            feature_columns=feature_columns,
            model_schema_version=resolved_schema.version,
            trained_at=trained_at,
            artifact_metadata=artifact_metadata,
        )
        saved_artifacts[str(candidate["candidate_name"])] = str(saved_path)

    available_ranking_candidates = [
        candidate
        for candidate in ranking_candidates
        if candidate.get("status") == "available" and candidate.get("model") is not None
    ]
    best_ranking_candidate = max(available_ranking_candidates, key=candidate_sort_key) if available_ranking_candidates else None
    if best_ranking_candidate is not None:
        saved_path = _save_candidate_model(
            best_ranking_candidate,
            ranking_model_path,
            rows=rows,
            train_rows=train_rows,
            validation_rows=validation_rows,
            split_metadata=split_metadata,
            dataset_version=resolved_dataset_version,
            feature_columns=feature_columns,
            model_schema_version=resolved_schema.version,
            trained_at=trained_at,
            artifact_metadata=artifact_metadata,
        )
        saved_artifacts[str(best_ranking_candidate["candidate_name"])] = str(saved_path)

    available_pointwise_candidates = [candidate for candidate in pointwise_candidates if candidate.get("status") == "available"]
    available_candidates = [*available_pointwise_candidates, *available_ranking_candidates]
    best_pointwise_candidate = max(available_pointwise_candidates, key=candidate_sort_key) if available_pointwise_candidates else None
    best_overall_candidate = max(available_candidates, key=candidate_sort_key) if available_candidates else None
    report = {
        "generated_at": trained_at,
        "dataset_path": str(Path(dataset_path)),
        "dataset_version": resolved_dataset_version,
        "model_schema_version": resolved_schema.version,
        "feature_count": len(feature_columns),
        "rows_count": len(rows),
        "queries_count": len({str(row.get("query") or "") for row in rows}),
        "domains_count": len({str(row.get("domain") or "") for row in rows}),
        "training_parameters": {
            "test_size": float(test_size),
            "random_state": int(random_state),
            "force_catboost": True,
            "model_schema_version": resolved_schema.version,
        },
        "split": _split_summary(train_rows, validation_rows, split_metadata),
        "reference_model": {
            "model_path": str(Path(reference_model_path)),
            "sha1": _sha1_file(reference_model_path),
        }
        if reference_model_path is not None
        else None,
        "candidate_output_paths": {
            POINTWISE_RANDOM_FOREST_CANDIDATE: str(Path(rf_model_path)),
            POINTWISE_CATBOOST_CANDIDATE: str(Path(catboost_model_path)),
            "best_ranking_candidate": str(Path(ranking_model_path)),
        },
        "saved_artifacts": saved_artifacts,
        "pointwise_benchmark": pointwise_benchmark,
        "candidates": [_serialize_candidate(candidate) for candidate in [*pointwise_candidates, *ranking_candidates]],
        "best_pointwise_candidate": _serialize_candidate(best_pointwise_candidate),
        "best_ranking_candidate": _serialize_candidate(best_ranking_candidate),
        "best_overall_candidate": _serialize_candidate(best_overall_candidate),
    }
    report_paths: dict[str, str] | None = None
    if output_dir is not None:
        report_paths = write_candidate_artifact_report(report, output_dir)
        report["report_paths"] = report_paths
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_RANKING_DATASET_PATH))
    parser.add_argument("--dataset-version", default="")
    parser.add_argument("--rf-model-output", default=str(DEFAULT_RF_CANDIDATE_PATH))
    parser.add_argument("--catboost-model-output", default=str(DEFAULT_CATBOOST_CANDIDATE_PATH))
    parser.add_argument("--ranking-model-output", default=str(DEFAULT_RANKING_CANDIDATE_PATH))
    parser.add_argument("--reference-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--without-reference-model", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_D34_CANDIDATE_REPORTS_DIR))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--model-schema-version", default=DEFAULT_TRAINING_MODEL_SCHEMA_VERSION)
    args = parser.parse_args()
    report = train_candidate_artifacts(
        dataset_path=args.dataset,
        dataset_version=args.dataset_version or None,
        rf_model_path=args.rf_model_output,
        catboost_model_path=args.catboost_model_output,
        ranking_model_path=args.ranking_model_output,
        reference_model_path=None if args.without_reference_model else args.reference_model,
        output_dir=args.output_dir or None,
        test_size=args.test_size,
        random_state=args.random_state,
        model_schema_version=args.model_schema_version,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
