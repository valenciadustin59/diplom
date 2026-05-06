from __future__ import annotations
import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
from typing import Any
from app.ml.dataset_quality import default_manifest_path
from app.ml.model import DEFAULT_MODEL_PATH, FEATURE_COLUMNS, load_model_artifact
from app.ml.model_schema import DEFAULT_TRAINING_MODEL_SCHEMA_VERSION
from app.ml.train import train_quality_model
BACKEND_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = BACKEND_DIR / "artifacts"
VERSIONED_ARTIFACTS_DIR = ARTIFACTS_DIR / "versions"
DATA_DIR = BACKEND_DIR / "data"
DEFAULT_PRIMARY_DATASET_PATH = DATA_DIR / "dataset_versions" / "dataset-v7-final" / "dataset.csv"
DEFAULT_PRIMARY_MANIFEST_PATH = DATA_DIR / "dataset_versions" / "dataset-v7-final" / "manifest.json"
def load_training_manifest(manifest_path: str | Path = DEFAULT_PRIMARY_MANIFEST_PATH) -> dict[str, Any]:
    resolved_path = Path(manifest_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Training manifest not found: {resolved_path}")
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Training manifest must be a JSON object")
    return payload
def ensure_manifest_ready(manifest: dict[str, Any]) -> None:
    quality_gates = manifest.get("quality_gates")
    if not isinstance(quality_gates, dict):
        raise ValueError("Training manifest does not contain quality_gates")
    if bool(quality_gates.get("ready_for_training")):
        return
    unmet = quality_gates.get("unmet_requirements")
    if isinstance(unmet, list) and unmet:
        requirements = ", ".join(str(item) for item in unmet)
        raise ValueError(f"Dataset is not ready for training: {requirements}")
    raise ValueError("Dataset is not ready for training")
def build_primary_dataset_version(dataset_path: str | Path, manifest: dict[str, Any]) -> str:
    dataset_metadata = manifest.get("dataset") if isinstance(manifest.get("dataset"), dict) else {}
    explicit_version = dataset_metadata.get("version") if isinstance(dataset_metadata, dict) else None
    if explicit_version:
        return str(explicit_version)
    resolved_dataset_path = Path(dataset_path)
    generated_at_raw = str(manifest.get("generated_at") or "")
    generated_at = datetime.fromisoformat(generated_at_raw) if generated_at_raw else None
    version_suffix = generated_at.strftime("%Y%m%d") if generated_at is not None else "undated"
    return f"{resolved_dataset_path.stem}-{version_suffix}-primary"
def build_primary_artifact_version(dataset_version: str, published_at: datetime) -> str:
    return f"{dataset_version}-{published_at.strftime('%Y%m%d%H%M%S')}"
def build_dataset_metadata(manifest: dict[str, Any], dataset_version: str) -> dict[str, object]:
    coverage = manifest.get("coverage") if isinstance(manifest.get("coverage"), dict) else {}
    dataset = manifest.get("dataset") if isinstance(manifest.get("dataset"), dict) else {}
    labeling = manifest.get("labeling") if isinstance(manifest.get("labeling"), dict) else {}
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    split = manifest.get("split") if isinstance(manifest.get("split"), dict) else {}
    return {
        "dataset_version": dataset_version,
        "baseline_version": dataset.get("baseline_version"),
        "rows_count": int(coverage.get("rows_count") or 0),
        "queries_count": int(coverage.get("unique_queries") or 0),
        "domains_count": int(coverage.get("unique_domains") or 0),
        "categories_count": int(coverage.get("unique_categories") or 0),
        "cities_count": int(coverage.get("unique_cities") or 0),
        "failure_rate": float(coverage.get("failure_rate") or 0.0),
        "query_coverage_ratio": float(coverage.get("query_coverage_ratio") or 0.0),
        "attempted_query_coverage_ratio": float(coverage.get("attempted_query_coverage_ratio") or 0.0),
        "feature_schema_versions": list(dataset.get("feature_schema_versions") or []),
        "extraction_artifact_versions": list(dataset.get("extraction_artifact_versions") or []),
        "label_schema_versions": list(dataset.get("label_schema_versions") or []),
        "label_source_distribution": dict(labeling.get("label_source_distribution") or {}),
        "expert_rows_count": int(labeling.get("expert_rows_count") or 0),
        "hybrid_rows_count": int(labeling.get("hybrid_rows_count") or 0),
        "artifact_coverage_ratio": float(artifacts.get("artifact_coverage_ratio") or 0.0),
        "split_mode": split.get("split_mode"),
        "split_path": dataset.get("split_path"),
        "manifest_generated_at": manifest.get("generated_at"),
    }
def build_versioned_artifact_path(model_path: str | Path, artifact_version: str) -> Path:
    resolved_model_path = Path(model_path)
    return VERSIONED_ARTIFACTS_DIR / f"{resolved_model_path.stem}--{artifact_version}{resolved_model_path.suffix}"
def build_artifact_metadata_path(model_path: str | Path) -> Path:
    resolved_model_path = Path(model_path)
    return resolved_model_path.with_suffix(".metadata.json")
def build_artifact_public_metadata(artifact: dict[str, object], artifact_path: str | Path) -> dict[str, object]:
    dataset_metadata = artifact.get("dataset_metadata") if isinstance(artifact.get("dataset_metadata"), dict) else {}
    metrics_summary = artifact.get("metrics_summary") if isinstance(artifact.get("metrics_summary"), dict) else {}
    feature_columns = artifact.get("feature_columns") if isinstance(artifact.get("feature_columns"), (list, tuple)) else FEATURE_COLUMNS
    return {
        "artifact_version": artifact.get("artifact_version"),
        "artifact_family": artifact.get("artifact_family"),
        "artifact_path": str(Path(artifact_path)),
        "model_type": artifact.get("model_type"),
        "model_schema_version": artifact.get("model_schema_version"),
        "source": artifact.get("source"),
        "trained_at": artifact.get("trained_at"),
        "published_at": artifact.get("published_at"),
        "feature_count": len(feature_columns),
        "dataset_metadata": dataset_metadata,
        "metrics_summary": metrics_summary,
    }
def write_artifact_public_metadata(metadata: dict[str, object], output_path: str | Path) -> Path:
    resolved_output_path = Path(output_path)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return resolved_output_path
def publish_primary_model(
    dataset_path: str | Path = DEFAULT_PRIMARY_DATASET_PATH,
    manifest_path: str | Path | None = None,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
    model_schema_version: str = DEFAULT_TRAINING_MODEL_SCHEMA_VERSION,
) -> dict[str, Any]:
    resolved_dataset_path = Path(dataset_path)
    resolved_model_path = Path(model_path)
    resolved_manifest_path = Path(manifest_path) if manifest_path is not None else default_manifest_path(resolved_dataset_path)
    manifest = load_training_manifest(resolved_manifest_path)
    ensure_manifest_ready(manifest)
    dataset_version = build_primary_dataset_version(resolved_dataset_path, manifest)
    published_at = datetime.now(UTC)
    artifact_version = build_primary_artifact_version(dataset_version, published_at)
    dataset_metadata = build_dataset_metadata(manifest, dataset_version=dataset_version)
    split_output_path = str(dataset_metadata.get("split_path") or "") or None
    training_result = train_quality_model(
        dataset_path=resolved_dataset_path,
        model_path=resolved_model_path,
        test_size=test_size,
        random_state=random_state,
        dataset_version=dataset_version,
        split_output_path=split_output_path,
        model_schema_version=model_schema_version,
        artifact_metadata={
            "artifact_version": artifact_version,
            "artifact_family": resolved_model_path.stem,
            "published_at": published_at.isoformat(),
            "dataset_metadata": dataset_metadata,
        },
    )
    artifact = load_model_artifact(resolved_model_path)
    if artifact is None:
        raise RuntimeError(f"Published artifact was not created: {resolved_model_path}")
    versioned_artifact_path = build_versioned_artifact_path(resolved_model_path, artifact_version)
    versioned_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(resolved_model_path, versioned_artifact_path)
    alias_metadata = build_artifact_public_metadata(artifact, resolved_model_path)
    alias_metadata_path = write_artifact_public_metadata(alias_metadata, build_artifact_metadata_path(resolved_model_path))
    versioned_metadata_path = write_artifact_public_metadata(
        {**alias_metadata, "artifact_path": str(versioned_artifact_path)},
        build_artifact_metadata_path(versioned_artifact_path),
    )
    return {
        **training_result,
        "artifact_version": artifact_version,
        "manifest_path": str(resolved_manifest_path),
        "published_model_path": str(resolved_model_path),
        "published_metadata_path": str(alias_metadata_path),
        "versioned_model_path": str(versioned_artifact_path),
        "versioned_metadata_path": str(versioned_metadata_path),
        "dataset_metadata": dataset_metadata,
        "model_schema_version": training_result.get("model_schema_version", model_schema_version),
    }
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_PRIMARY_DATASET_PATH))
    parser.add_argument("--manifest", default=str(DEFAULT_PRIMARY_MANIFEST_PATH))
    parser.add_argument("--model-output", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--model-schema-version", default=DEFAULT_TRAINING_MODEL_SCHEMA_VERSION)
    args = parser.parse_args()
    result = publish_primary_model(
        dataset_path=args.dataset,
        manifest_path=args.manifest,
        model_path=args.model_output,
        test_size=args.test_size,
        random_state=args.random_state,
        model_schema_version=args.model_schema_version,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
if __name__ == "__main__":
    main()
