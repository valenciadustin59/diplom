from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import json
from pathlib import Path
import re
import shutil
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
DATASET_VERSIONS_DIR = DATA_DIR / "dataset_versions"

BASELINE_DATASET_VERSION = "baseline-v1"
DEFAULT_DATASET_VERSION = "dataset-v7-final"
LABEL_SCHEMA_VERSION = "hybrid-v1"

PRIMARY_DATASET_PATH = DATASET_VERSIONS_DIR / "dataset-v7-final" / "dataset.csv"
PRIMARY_FAILURES_PATH = DATASET_VERSIONS_DIR / "dataset-v7-final" / "failures.csv"
PRIMARY_MANIFEST_PATH = DATASET_VERSIONS_DIR / "dataset-v7-final" / "manifest.json"
PRIMARY_CHECKPOINT_PATH = DATASET_VERSIONS_DIR / "dataset-v7-final" / "checkpoint.json"
PRIMARY_SEEDS_PATH = DATASET_VERSIONS_DIR / "dataset-v7-final" / "seeds.csv"


@dataclass(frozen=True, slots=True)
class DatasetBundlePaths:
    version: str
    root_dir: Path
    dataset_path: Path
    failures_path: Path
    checkpoint_path: Path
    manifest_path: Path
    split_path: Path
    metadata_path: Path
    seeds_path: Path
    artifacts_dir: Path


def normalize_dataset_version(version: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(version or "").strip())
    normalized = normalized.strip("-._")
    if not normalized:
        raise ValueError("Dataset version must not be empty")
    return normalized


def build_dataset_bundle_paths(version: str) -> DatasetBundlePaths:
    normalized_version = normalize_dataset_version(version)
    root_dir = DATASET_VERSIONS_DIR / normalized_version
    return DatasetBundlePaths(
        version=normalized_version,
        root_dir=root_dir,
        dataset_path=root_dir / "dataset.csv",
        failures_path=root_dir / "failures.csv",
        checkpoint_path=root_dir / "checkpoint.json",
        manifest_path=root_dir / "manifest.json",
        split_path=root_dir / "split.json",
        metadata_path=root_dir / "dataset.json",
        seeds_path=root_dir / "seeds.csv",
        artifacts_dir=root_dir / "artifacts",
    )


def build_dataset_row_artifact_path(artifacts_dir: str | Path, *, query: str, url: str) -> Path:
    resolved_artifacts_dir = Path(artifacts_dir)
    query_slug = re.sub(r"[^a-zA-Z0-9]+", "-", query.lower()).strip("-") or "query"
    key = sha1(f"{query}\n{url}".encode("utf-8")).hexdigest()[:16]
    return resolved_artifacts_dir / f"{query_slug}--{key}.json"


def infer_dataset_version(
    dataset_path: str | Path,
    rows: list[dict[str, str]] | None = None,
    manifest: dict[str, Any] | None = None,
) -> str:
    if isinstance(manifest, dict):
        dataset_metadata = manifest.get("dataset")
        if isinstance(dataset_metadata, dict) and dataset_metadata.get("version"):
            return str(dataset_metadata["version"])

    for row in rows or []:
        version = str(row.get("dataset_version") or "").strip()
        if version:
            return version

    resolved_dataset_path = Path(dataset_path)
    try:
        relative_parts = resolved_dataset_path.relative_to(DATASET_VERSIONS_DIR).parts
    except ValueError:
        relative_parts = ()
    if relative_parts:
        return str(relative_parts[0])
    return resolved_dataset_path.stem


def write_dataset_metadata(output_path: str | Path, payload: dict[str, Any]) -> Path:
    resolved_output_path = Path(output_path)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return resolved_output_path


def freeze_primary_dataset_as_baseline(
    version: str = BASELINE_DATASET_VERSION,
    *,
    dataset_path: str | Path = PRIMARY_DATASET_PATH,
    failures_path: str | Path = PRIMARY_FAILURES_PATH,
    manifest_path: str | Path = PRIMARY_MANIFEST_PATH,
    checkpoint_path: str | Path = PRIMARY_CHECKPOINT_PATH,
    seeds_path: str | Path = PRIMARY_SEEDS_PATH,
) -> dict[str, object]:
    bundle = build_dataset_bundle_paths(version)
    bundle.root_dir.mkdir(parents=True, exist_ok=True)

    source_to_target = {
        Path(dataset_path): bundle.dataset_path,
        Path(failures_path): bundle.failures_path,
        Path(manifest_path): bundle.manifest_path,
        Path(checkpoint_path): bundle.checkpoint_path,
        Path(seeds_path): bundle.seeds_path,
    }

    copied_files: list[str] = []
    for source_path, target_path in source_to_target.items():
        if not source_path.exists() or target_path.exists():
            continue
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        copied_files.append(str(target_path))

    metadata = {
        "version": bundle.version,
        "kind": "baseline",
        "source_aliases": {
            "dataset_path": str(Path(dataset_path)),
            "failures_path": str(Path(failures_path)),
            "manifest_path": str(Path(manifest_path)),
            "checkpoint_path": str(Path(checkpoint_path)),
            "seeds_path": str(Path(seeds_path)),
        },
        "paths": {
            "dataset_path": str(bundle.dataset_path),
            "failures_path": str(bundle.failures_path),
            "manifest_path": str(bundle.manifest_path),
            "checkpoint_path": str(bundle.checkpoint_path),
            "seeds_path": str(bundle.seeds_path),
            "artifacts_dir": str(bundle.artifacts_dir),
            "split_path": str(bundle.split_path),
        },
        "copied_files": copied_files,
        "frozen": bundle.dataset_path.exists(),
    }
    write_dataset_metadata(bundle.metadata_path, metadata)
    return {
        **metadata,
        "metadata_path": str(bundle.metadata_path),
    }
