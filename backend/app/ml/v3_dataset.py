from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
from typing import Any

from app.features import detect_query_intent, merge_intent_alignment_features
from app.heavy_analysis import HEAVY_ANALYSIS_FEATURE_COLUMNS, build_heavy_analysis_payload
from app.ml.dataset_quality import save_dataset_manifest
from app.ml.dataset_versions import BASELINE_DATASET_VERSION
from app.ml.model_schema import MODEL_SCHEMA_VERSION_V3, get_model_feature_schema
from app.ml.train import create_dataset_split


BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
DATASET_VERSIONS_DIR = DATA_DIR / "dataset_versions"
DEFAULT_SOURCE_DATASET_DIR = DATASET_VERSIONS_DIR / "dataset-v2"
DEFAULT_SOURCE_DATASET_PATH = DEFAULT_SOURCE_DATASET_DIR / "dataset.csv"
DEFAULT_SOURCE_FAILURES_PATH = DEFAULT_SOURCE_DATASET_DIR / "failures.csv"
DEFAULT_SOURCE_SEEDS_PATH = DEFAULT_SOURCE_DATASET_DIR / "seeds.csv"
DEFAULT_SOURCE_ARTIFACTS_DIR = DEFAULT_SOURCE_DATASET_DIR / "artifacts"
DEFAULT_OUTPUT_DIR = DATASET_VERSIONS_DIR / "dataset-v3-d37"
DEFAULT_OUTPUT_DATASET_PATH = DEFAULT_OUTPUT_DIR / "dataset.csv"
DEFAULT_OUTPUT_FAILURES_PATH = DEFAULT_OUTPUT_DIR / "failures.csv"
DEFAULT_OUTPUT_SEEDS_PATH = DEFAULT_OUTPUT_DIR / "seeds.csv"
DEFAULT_OUTPUT_SPLIT_PATH = DEFAULT_OUTPUT_DIR / "split.json"
DEFAULT_OUTPUT_MANIFEST_PATH = DEFAULT_OUTPUT_DIR / "manifest.json"
DEFAULT_OUTPUT_REPORT_PATH = DEFAULT_OUTPUT_DIR / "d37-v3-dataset-report.json"
DEFAULT_DATASET_VERSION = "dataset-v3-d37"
METADATA_COLUMNS = [
    "dataset_version",
    "feature_schema_version",
    "extraction_artifact_version",
    "label_schema_version",
    "label_source",
    "weak_target_score",
    "expert_target_score",
    "query",
    "category",
    "intent",
    "city",
    "region_code",
    "url",
    "domain",
    "rank",
    "serp_page",
    "title",
    "snippet",
    "page_type",
    "fetch_status",
    "fetch_error",
    "artifact_path",
    "artifact_sha1",
    "artifact_size_bytes",
    "target_score",
]


def _safe_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _load_csv_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    resolved_path = Path(path)
    with resolved_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv_rows(path: str | Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _source_artifact_path(source_dataset_path: Path, source_artifacts_dir: Path, artifact_path: str) -> Path | None:
    if not artifact_path.strip():
        return None
    raw_path = Path(artifact_path)
    candidates = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.extend(
            [
                source_dataset_path.parent / raw_path,
                source_artifacts_dir / raw_path,
                source_artifacts_dir / raw_path.name,
            ]
        )
        if raw_path.parts and raw_path.parts[0] == source_artifacts_dir.name:
            candidates.append(source_artifacts_dir.joinpath(*raw_path.parts[1:]))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _artifact_path_for_output(source_artifact_path: Path, output_dataset_path: Path) -> str:
    return str(Path(os.path.relpath(source_artifact_path, output_dataset_path.parent)))


def _load_artifact_payload(artifact_path: Path | None) -> dict[str, object] | None:
    if artifact_path is None:
        return None
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _heavy_features(snapshot: dict[str, object] | None) -> dict[str, float | int]:
    if not isinstance(snapshot, dict):
        return {feature_name: 0.0 for feature_name in HEAVY_ANALYSIS_FEATURE_COLUMNS}
    try:
        payload = build_heavy_analysis_payload(snapshot)
        features = payload.get("features") if isinstance(payload.get("features"), dict) else {}
    except Exception:
        features = {}
    return {
        feature_name: _safe_float(features.get(feature_name))
        for feature_name in HEAVY_ANALYSIS_FEATURE_COLUMNS
    }


def _feature_map(row: dict[str, str], feature_columns: tuple[str, ...]) -> dict[str, float | int]:
    return {feature_name: _safe_float(row.get(feature_name)) for feature_name in feature_columns}


def _enrich_row(
    row: dict[str, str],
    *,
    source_dataset_path: Path,
    source_artifacts_dir: Path,
    output_dataset_path: Path,
    dataset_version: str,
    feature_columns: tuple[str, ...],
) -> tuple[dict[str, object], dict[str, object]]:
    source_artifact = _source_artifact_path(
        source_dataset_path,
        source_artifacts_dir,
        str(row.get("artifact_path") or ""),
    )
    snapshot = _load_artifact_payload(source_artifact)
    features = _feature_map(row, feature_columns)
    heavy_features = _heavy_features(snapshot)
    features.update(heavy_features)
    intent_features = merge_intent_alignment_features(features, detect_query_intent(str(row.get("query") or "")))
    features.update(intent_features)

    enriched_row: dict[str, object] = {column: row.get(column, "") for column in METADATA_COLUMNS}
    enriched_row.update(
        {
            "dataset_version": dataset_version,
            "feature_schema_version": MODEL_SCHEMA_VERSION_V3,
            "artifact_path": _artifact_path_for_output(source_artifact, output_dataset_path)
            if source_artifact is not None
            else str(row.get("artifact_path") or ""),
        }
    )
    for feature_name in feature_columns:
        enriched_row[feature_name] = _safe_float(features.get(feature_name))

    row_report = {
        "source_artifact_found": source_artifact is not None,
        "heavy_features_non_zero": sum(1 for value in heavy_features.values() if _safe_float(value) != 0.0),
        "intent_alignment_score": _safe_float(features.get("intent_alignment_score")),
    }
    return enriched_row, row_report


def build_v3_dataset(
    *,
    source_dataset_path: str | Path = DEFAULT_SOURCE_DATASET_PATH,
    source_failures_path: str | Path = DEFAULT_SOURCE_FAILURES_PATH,
    source_seeds_path: str | Path = DEFAULT_SOURCE_SEEDS_PATH,
    source_artifacts_dir: str | Path = DEFAULT_SOURCE_ARTIFACTS_DIR,
    output_dataset_path: str | Path = DEFAULT_OUTPUT_DATASET_PATH,
    output_failures_path: str | Path = DEFAULT_OUTPUT_FAILURES_PATH,
    output_seeds_path: str | Path = DEFAULT_OUTPUT_SEEDS_PATH,
    output_split_path: str | Path = DEFAULT_OUTPUT_SPLIT_PATH,
    output_manifest_path: str | Path = DEFAULT_OUTPUT_MANIFEST_PATH,
    output_report_path: str | Path = DEFAULT_OUTPUT_REPORT_PATH,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    overwrite: bool = True,
) -> dict[str, Any]:
    resolved_source_dataset_path = Path(source_dataset_path)
    resolved_source_failures_path = Path(source_failures_path)
    resolved_source_seeds_path = Path(source_seeds_path)
    resolved_source_artifacts_dir = Path(source_artifacts_dir)
    resolved_output_dataset_path = Path(output_dataset_path)
    resolved_output_failures_path = Path(output_failures_path)
    resolved_output_seeds_path = Path(output_seeds_path)
    resolved_output_split_path = Path(output_split_path)
    resolved_output_manifest_path = Path(output_manifest_path)
    resolved_output_report_path = Path(output_report_path)

    if not overwrite and resolved_output_dataset_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing dataset: {resolved_output_dataset_path}")

    _, rows = _load_csv_rows(resolved_source_dataset_path)
    if not rows:
        raise ValueError(f"Source dataset is empty: {resolved_source_dataset_path}")

    schema = get_model_feature_schema(MODEL_SCHEMA_VERSION_V3)
    output_columns = [*METADATA_COLUMNS, *schema.feature_columns]
    enriched_rows: list[dict[str, object]] = []
    row_reports: list[dict[str, object]] = []
    for row in rows:
        enriched_row, row_report = _enrich_row(
            row,
            source_dataset_path=resolved_source_dataset_path,
            source_artifacts_dir=resolved_source_artifacts_dir,
            output_dataset_path=resolved_output_dataset_path,
            dataset_version=dataset_version,
            feature_columns=schema.feature_columns,
        )
        enriched_rows.append(enriched_row)
        row_reports.append(row_report)

    _write_csv_rows(resolved_output_dataset_path, output_columns, enriched_rows)

    resolved_output_failures_path.parent.mkdir(parents=True, exist_ok=True)
    if resolved_source_failures_path.exists():
        failure_columns, failure_rows = _load_csv_rows(resolved_source_failures_path)
        for failure_row in failure_rows:
            failure_row["dataset_version"] = dataset_version
            failure_row["feature_schema_version"] = MODEL_SCHEMA_VERSION_V3
        if failure_columns:
            _write_csv_rows(resolved_output_failures_path, failure_columns, failure_rows)
        else:
            shutil.copy2(resolved_source_failures_path, resolved_output_failures_path)

    if resolved_source_seeds_path.exists():
        resolved_output_seeds_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved_source_seeds_path, resolved_output_seeds_path)

    split = create_dataset_split(
        resolved_output_dataset_path,
        resolved_output_split_path,
        dataset_version=dataset_version,
    )
    manifest = save_dataset_manifest(
        dataset_path=resolved_output_dataset_path,
        failures_path=resolved_output_failures_path if resolved_output_failures_path.exists() else None,
        seeds_path=resolved_output_seeds_path if resolved_output_seeds_path.exists() else None,
        output_path=resolved_output_manifest_path,
        dataset_version=dataset_version,
        baseline_version=BASELINE_DATASET_VERSION,
        artifacts_dir=resolved_source_artifacts_dir,
        split_path=resolved_output_split_path,
    )

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "task": "D37",
        "dataset_version": dataset_version,
        "source_dataset_path": str(resolved_source_dataset_path),
        "output_dataset_path": str(resolved_output_dataset_path),
        "model_schema_version": schema.version,
        "feature_count": len(schema.feature_columns),
        "rows_count": len(enriched_rows),
        "source_artifacts_found": sum(1 for item in row_reports if item["source_artifact_found"]),
        "source_artifacts_missing": sum(1 for item in row_reports if not item["source_artifact_found"]),
        "rows_with_heavy_features": sum(1 for item in row_reports if int(item["heavy_features_non_zero"]) > 0),
        "rows_with_intent_alignment": sum(1 for item in row_reports if float(item["intent_alignment_score"]) > 0.0),
        "split_path": str(resolved_output_split_path),
        "manifest_path": str(resolved_output_manifest_path),
        "split_summary": split,
        "manifest_ready_for_training": bool(manifest.get("quality_gates", {}).get("ready_for_training")),
    }
    resolved_output_report_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dataset", default=str(DEFAULT_SOURCE_DATASET_PATH))
    parser.add_argument("--source-failures", default=str(DEFAULT_SOURCE_FAILURES_PATH))
    parser.add_argument("--source-seeds", default=str(DEFAULT_SOURCE_SEEDS_PATH))
    parser.add_argument("--source-artifacts-dir", default=str(DEFAULT_SOURCE_ARTIFACTS_DIR))
    parser.add_argument("--output-dataset", default=str(DEFAULT_OUTPUT_DATASET_PATH))
    parser.add_argument("--output-failures", default=str(DEFAULT_OUTPUT_FAILURES_PATH))
    parser.add_argument("--output-seeds", default=str(DEFAULT_OUTPUT_SEEDS_PATH))
    parser.add_argument("--output-split", default=str(DEFAULT_OUTPUT_SPLIT_PATH))
    parser.add_argument("--output-manifest", default=str(DEFAULT_OUTPUT_MANIFEST_PATH))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT_PATH))
    parser.add_argument("--dataset-version", default=DEFAULT_DATASET_VERSION)
    parser.add_argument("--no-overwrite", action="store_true")
    args = parser.parse_args()
    report = build_v3_dataset(
        source_dataset_path=args.source_dataset,
        source_failures_path=args.source_failures,
        source_seeds_path=args.source_seeds,
        source_artifacts_dir=args.source_artifacts_dir,
        output_dataset_path=args.output_dataset,
        output_failures_path=args.output_failures,
        output_seeds_path=args.output_seeds,
        output_split_path=args.output_split,
        output_manifest_path=args.output_manifest,
        output_report_path=args.output_report,
        dataset_version=args.dataset_version,
        overwrite=not args.no_overwrite,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
