from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from app.ml.candidate_artifacts import train_candidate_artifacts
from app.ml.model import DEFAULT_MODEL_PATH, load_model_artifact, load_saved_model, predict_score
from app.ml.model_schema import MODEL_SCHEMA_VERSION_V3, get_model_feature_schema
from app.ml.publish import ARTIFACTS_DIR, build_artifact_public_metadata, write_artifact_public_metadata
from app.ml.train import load_dataset_rows
from app.ml.v3_dataset import DATASET_VERSIONS_DIR
from app.ml.v4_dataset import LABEL_SCHEMA_VERSION_V4


DEFAULT_D47_DATASET_PATH = DATASET_VERSIONS_DIR / "dataset-v4" / "dataset.csv"
DEFAULT_D47_MANIFEST_PATH = DATASET_VERSIONS_DIR / "dataset-v4" / "manifest.json"
DEFAULT_D47_LABEL_REPORT_PATH = DATASET_VERSIONS_DIR / "dataset-v4" / "d45-seo-weighted-label-report.json"
DEFAULT_D47_DATASET_REPORT_PATH = DATASET_VERSIONS_DIR / "dataset-v4" / "d46-dataset-v4-report.json"
DEFAULT_D47_RF_CANDIDATE_PATH = ARTIFACTS_DIR / "page_quality_model.dataset-v4-seo-weighted-rf-candidate.pkl"
DEFAULT_D47_CATBOOST_CANDIDATE_PATH = ARTIFACTS_DIR / "page_quality_model.dataset-v4-seo-weighted-catboost-candidate.pkl"
DEFAULT_D47_RANKING_CANDIDATE_PATH = ARTIFACTS_DIR / "page_quality_model.dataset-v4-seo-weighted-ranking-candidate.pkl"
DEFAULT_D47_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v4-d47"
DEFAULT_D47_REPORT_JSON_PATH = DEFAULT_D47_OUTPUT_DIR / "d47-candidate-training-report.json"
DEFAULT_D47_REPORT_MD_PATH = DEFAULT_D47_OUTPUT_DIR / "d47-candidate-training-report.md"


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


def _read_json(path: str | Path) -> dict[str, Any]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return {}
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _sample_features(dataset_path: str | Path) -> dict[str, float]:
    rows = load_dataset_rows(dataset_path)
    if not rows:
        raise ValueError(f"D47 dataset is empty: {dataset_path}")
    feature_columns = get_model_feature_schema(MODEL_SCHEMA_VERSION_V3).feature_columns
    first_row = rows[0]
    return {feature_name: _safe_float(first_row.get(feature_name)) for feature_name in feature_columns}


def _candidate_lookup(training_report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    candidates = training_report.get("candidates") if isinstance(training_report.get("candidates"), list) else []
    return {
        str(candidate.get("candidate_name")): candidate
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("candidate_name")
    }


def _write_candidate_metadata_sidecars(
    *,
    training_report: Mapping[str, Any],
    dataset_path: str | Path,
    output_dir: str | Path,
    target_policy: str,
    manifest_path: str | Path,
    label_report_path: str | Path,
    dataset_report_path: str | Path,
) -> dict[str, dict[str, Any]]:
    sample_features = _sample_features(dataset_path)
    candidate_by_name = _candidate_lookup(training_report)
    saved_artifacts = (
        training_report.get("saved_artifacts") if isinstance(training_report.get("saved_artifacts"), dict) else {}
    )
    metadata_by_candidate: dict[str, dict[str, Any]] = {}

    for candidate_name, artifact_path in saved_artifacts.items():
        resolved_artifact_path = Path(str(artifact_path))
        artifact = load_model_artifact(resolved_artifact_path)
        raw_payload = load_saved_model(resolved_artifact_path) or {}
        score = predict_score(sample_features, model_path=resolved_artifact_path)
        candidate = candidate_by_name.get(str(candidate_name), {})
        compatibility = {
            "load_model_artifact": artifact is not None,
            "predict_score_bounded": 0.0 <= float(score) <= 100.0,
            "sample_score": round(float(score), 4),
            "model_schema_version": artifact.get("model_schema_version") if artifact else None,
            "feature_count": len(artifact.get("feature_columns") or []) if artifact else 0,
            "dataset_version": artifact.get("dataset_version") if artifact else None,
            "passed": bool(
                artifact is not None
                and artifact.get("model_schema_version") == MODEL_SCHEMA_VERSION_V3
                and len(artifact.get("feature_columns") or []) == len(get_model_feature_schema(MODEL_SCHEMA_VERSION_V3).feature_columns)
                and artifact.get("dataset_version") == "dataset-v4"
                and 0.0 <= float(score) <= 100.0
            ),
        }
        public_metadata = build_artifact_public_metadata(artifact or raw_payload, resolved_artifact_path)
        public_metadata.update(
            {
                "training_task": "D47",
                "non_production": True,
                "runtime_enabled": False,
                "publish_decision_required": "D48/D49",
                "candidate_name": candidate_name,
                "candidate_family": candidate.get("candidate_family") or raw_payload.get("candidate_family"),
                "candidate_status": candidate.get("status"),
                "target_policy": target_policy,
                "label_schema_version": LABEL_SCHEMA_VERSION_V4,
                "manifest_path": str(Path(manifest_path)),
                "label_report_path": str(Path(label_report_path)),
                "dataset_report_path": str(Path(dataset_report_path)),
                "training_report_dir": str(Path(output_dir)),
                "compatibility_check": compatibility,
                "sha1": _sha1_file(resolved_artifact_path),
            }
        )
        metadata_path = resolved_artifact_path.with_suffix(".metadata.json")
        write_artifact_public_metadata(public_metadata, metadata_path)
        metadata_by_candidate[str(candidate_name)] = {
            "artifact_path": str(resolved_artifact_path),
            "metadata_path": str(metadata_path),
            "sha1": public_metadata["sha1"],
            "compatibility_check": compatibility,
        }
    return metadata_by_candidate


def _build_training_decisions(training_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    candidates = training_report.get("candidates") if isinstance(training_report.get("candidates"), list) else []
    saved_artifacts = (
        training_report.get("saved_artifacts") if isinstance(training_report.get("saved_artifacts"), dict) else {}
    )
    saved_names = {str(name) for name in saved_artifacts}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        candidate_name = str(candidate.get("candidate_name") or "unknown")
        status = str(candidate.get("status") or "unknown")
        if status != "available":
            decision = "not_trained"
            reason = candidate.get("reason") or "candidate_family_unavailable_in_local_environment"
        elif candidate_name in saved_names:
            decision = "trained_for_d48_shadow_benchmark"
            reason = "artifact_saved_as_non_production_candidate"
        else:
            decision = "evaluated_but_not_saved"
            reason = "only best ranking candidate is saved for ranking families"
        decisions.append(
            {
                "candidate_name": candidate_name,
                "candidate_family": candidate.get("candidate_family"),
                "model_type": candidate.get("model_type"),
                "status": status,
                "decision": decision,
                "reason": reason,
                "metrics": candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
                "model_path": candidate.get("model_path"),
            }
        )
    return decisions


def _render_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# D47 SEO-Weighted Candidate Training",
        "",
        f"- Dataset: `{report.get('dataset_path')}`",
        f"- Dataset version: `{report.get('dataset_version')}`",
        f"- Label schema: `{report.get('label_schema_version')}`",
        f"- Target policy: `{report.get('target_policy')}`",
        f"- Model schema: `{report.get('model_schema_version')}`",
        f"- Feature count: `{report.get('feature_count')}`",
        f"- Production artifact changed: `{report.get('production_artifact', {}).get('changed_by_d47')}`",
        "",
        "## Saved Non-Production Artifacts",
        "",
    ]
    metadata = report.get("candidate_metadata") if isinstance(report.get("candidate_metadata"), dict) else {}
    for candidate_name, item in metadata.items():
        lines.extend(
            [
                f"### {candidate_name}",
                f"- Artifact: `{item.get('artifact_path')}`",
                f"- Metadata: `{item.get('metadata_path')}`",
                f"- SHA1: `{item.get('sha1')}`",
                f"- Compatibility passed: `{item.get('compatibility_check', {}).get('passed')}`",
                "",
            ]
        )
    lines.extend(["## Candidate Decisions", ""])
    for decision in report.get("candidate_training_decisions") or []:
        if not isinstance(decision, dict):
            continue
        metrics = decision.get("metrics") if isinstance(decision.get("metrics"), dict) else {}
        lines.extend(
            [
                f"### {decision.get('candidate_name')}",
                f"- Decision: `{decision.get('decision')}`",
                f"- Reason: `{decision.get('reason')}`",
                f"- RMSE: `{metrics.get('rmse')}`",
                f"- MAE: `{metrics.get('mae')}`",
                f"- NDCG@10: `{metrics.get('ndcg_at_10')}`",
                f"- Top-3 hit rate: `{metrics.get('top_3_hit_rate')}`",
                f"- Spearman mean: `{metrics.get('spearman_mean')}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Next Step",
            "",
            "D47 is not a publish decision. D48 must compare these candidates against the current production artifact with product-critical guardrails before D49 can publish or explicitly keep the current model.",
            "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _write_report(path: str | Path, report: Mapping[str, Any]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def run_d47_candidate_training(
    *,
    dataset_path: str | Path = DEFAULT_D47_DATASET_PATH,
    manifest_path: str | Path = DEFAULT_D47_MANIFEST_PATH,
    label_report_path: str | Path = DEFAULT_D47_LABEL_REPORT_PATH,
    dataset_report_path: str | Path = DEFAULT_D47_DATASET_REPORT_PATH,
    rf_model_path: str | Path = DEFAULT_D47_RF_CANDIDATE_PATH,
    catboost_model_path: str | Path = DEFAULT_D47_CATBOOST_CANDIDATE_PATH,
    ranking_model_path: str | Path = DEFAULT_D47_RANKING_CANDIDATE_PATH,
    reference_model_path: str | Path | None = DEFAULT_MODEL_PATH,
    output_dir: str | Path = DEFAULT_D47_OUTPUT_DIR,
    report_json_path: str | Path = DEFAULT_D47_REPORT_JSON_PATH,
    report_markdown_path: str | Path = DEFAULT_D47_REPORT_MD_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    manifest = _read_json(manifest_path)
    dataset_report = _read_json(dataset_report_path)
    target_policy = str(dataset_report.get("target_score_policy") or "target_score_equals_d45_seo_weighted_expert_label")
    production_before_sha1 = _sha1_file(reference_model_path)
    training_metadata = {
        "training_task": "D47",
        "non_production": True,
        "runtime_enabled": False,
        "publish_decision_required": "D48/D49",
        "target_policy": target_policy,
        "label_schema_version": LABEL_SCHEMA_VERSION_V4,
    }
    training_report = train_candidate_artifacts(
        dataset_path=dataset_path,
        dataset_version="dataset-v4",
        rf_model_path=rf_model_path,
        catboost_model_path=catboost_model_path,
        ranking_model_path=ranking_model_path,
        reference_model_path=reference_model_path,
        output_dir=output_dir,
        test_size=test_size,
        random_state=random_state,
        model_schema_version=MODEL_SCHEMA_VERSION_V3,
        artifact_metadata=training_metadata,
    )
    candidate_metadata = _write_candidate_metadata_sidecars(
        training_report=training_report,
        dataset_path=dataset_path,
        output_dir=output_dir,
        target_policy=target_policy,
        manifest_path=manifest_path,
        label_report_path=label_report_path,
        dataset_report_path=dataset_report_path,
    )
    production_after_sha1 = _sha1_file(reference_model_path)
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "task": "D47",
        "dataset_path": str(Path(dataset_path)),
        "dataset_version": "dataset-v4",
        "manifest_path": str(Path(manifest_path)),
        "manifest_ready_for_training": bool(manifest.get("quality_gates", {}).get("ready_for_training")),
        "label_schema_version": LABEL_SCHEMA_VERSION_V4,
        "target_policy": target_policy,
        "model_schema_version": MODEL_SCHEMA_VERSION_V3,
        "feature_count": len(get_model_feature_schema(MODEL_SCHEMA_VERSION_V3).feature_columns),
        "training_parameters": {
            "test_size": float(test_size),
            "random_state": int(random_state),
            "force_catboost": True,
            "candidate_families": ["RandomForestRegressor", "CatBoostRegressor", "best_available_ranker"],
        },
        "candidate_artifact_training_report": training_report,
        "candidate_training_decisions": _build_training_decisions(training_report),
        "candidate_metadata": candidate_metadata,
        "production_artifact": {
            "path": str(Path(reference_model_path)) if reference_model_path is not None else None,
            "sha1_before": production_before_sha1,
            "sha1_after": production_after_sha1,
            "changed_by_d47": production_before_sha1 != production_after_sha1,
        },
        "next_step": "D48 shadow benchmark and product-critical guardrails before any D49 publish/no-publish decision.",
    }
    _write_report(report_json_path, report)
    Path(report_markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_markdown_path).write_text(_render_markdown(report), encoding="utf-8")
    report["report_paths"] = {
        "json_path": str(Path(report_json_path)),
        "markdown_path": str(Path(report_markdown_path)),
    }
    _write_report(report_json_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Train D47 SEO-weighted non-production candidates.")
    parser.add_argument("--dataset", default=str(DEFAULT_D47_DATASET_PATH))
    parser.add_argument("--manifest", default=str(DEFAULT_D47_MANIFEST_PATH))
    parser.add_argument("--label-report", default=str(DEFAULT_D47_LABEL_REPORT_PATH))
    parser.add_argument("--dataset-report", default=str(DEFAULT_D47_DATASET_REPORT_PATH))
    parser.add_argument("--rf-model-output", default=str(DEFAULT_D47_RF_CANDIDATE_PATH))
    parser.add_argument("--catboost-model-output", default=str(DEFAULT_D47_CATBOOST_CANDIDATE_PATH))
    parser.add_argument("--ranking-model-output", default=str(DEFAULT_D47_RANKING_CANDIDATE_PATH))
    parser.add_argument("--reference-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--without-reference-model", action="store_true")
    parser.add_argument("--output-dir", default=str(DEFAULT_D47_OUTPUT_DIR))
    parser.add_argument("--report-json", default=str(DEFAULT_D47_REPORT_JSON_PATH))
    parser.add_argument("--report-md", default=str(DEFAULT_D47_REPORT_MD_PATH))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()
    report = run_d47_candidate_training(
        dataset_path=args.dataset,
        manifest_path=args.manifest,
        label_report_path=args.label_report,
        dataset_report_path=args.dataset_report,
        rf_model_path=args.rf_model_output,
        catboost_model_path=args.catboost_model_output,
        ranking_model_path=args.ranking_model_output,
        reference_model_path=None if args.without_reference_model else args.reference_model,
        output_dir=args.output_dir,
        report_json_path=args.report_json,
        report_markdown_path=args.report_md,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
