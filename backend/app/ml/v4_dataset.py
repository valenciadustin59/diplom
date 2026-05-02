from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha1
import json
from pathlib import Path
import shutil
from statistics import fmean
from typing import Any, Mapping, Sequence

from app.ml.dataset_quality import (
    PRODUCTION_LIKE_DATASET_THRESHOLDS,
    DatasetQualityThresholds,
    save_dataset_manifest,
)
from app.ml.dataset_versions import BASELINE_DATASET_VERSION
from app.ml.seo_weighted_labels import DEFAULT_OUTPUT_LABELS_PATH, DEFAULT_PRODUCTION_ARTIFACT_PATH
from app.ml.train import create_dataset_split
from app.ml.v3_dataset import DATASET_VERSIONS_DIR


DEFAULT_SOURCE_DATASET_DIR = DATASET_VERSIONS_DIR / "dataset-v3-d37"
DEFAULT_SOURCE_DATASET_PATH = DEFAULT_SOURCE_DATASET_DIR / "dataset.csv"
DEFAULT_SOURCE_FAILURES_PATH = DEFAULT_SOURCE_DATASET_DIR / "failures.csv"
DEFAULT_SOURCE_SEEDS_PATH = DEFAULT_SOURCE_DATASET_DIR / "seeds.csv"
DEFAULT_SOURCE_ARTIFACTS_DIR = DATASET_VERSIONS_DIR / "dataset-v2" / "artifacts"
DEFAULT_OUTPUT_DIR = DATASET_VERSIONS_DIR / "dataset-v4"
DEFAULT_OUTPUT_DATASET_PATH = DEFAULT_OUTPUT_DIR / "dataset.csv"
DEFAULT_OUTPUT_FAILURES_PATH = DEFAULT_OUTPUT_DIR / "failures.csv"
DEFAULT_OUTPUT_SEEDS_PATH = DEFAULT_OUTPUT_DIR / "seeds.csv"
DEFAULT_OUTPUT_SPLIT_PATH = DEFAULT_OUTPUT_DIR / "split.json"
DEFAULT_OUTPUT_MANIFEST_PATH = DEFAULT_OUTPUT_DIR / "manifest.json"
DEFAULT_OUTPUT_REPORT_JSON_PATH = DEFAULT_OUTPUT_DIR / "d46-dataset-v4-report.json"
DEFAULT_OUTPUT_REPORT_MD_PATH = DEFAULT_OUTPUT_DIR / "d46-dataset-v4-report.md"
DEFAULT_DATASET_VERSION = "dataset-v4"
LABEL_SCHEMA_VERSION_V4 = "seo-weighted-v4"


@dataclass(frozen=True, slots=True)
class SeoWeightedLabel:
    query: str
    url: str
    score: float
    label_source: str
    labeler: str
    critical_score: float
    important_score: float
    supporting_score: float
    rank_prior_score: float
    cap_reasons: str
    quality_band: str


def _row_key(query: str, url: str) -> str:
    return f"{query.strip().replace('\ufeff', '')}|{url.strip()}"


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_score(value: float) -> str:
    return str(round(float(value), 4))


def _read_csv_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return [], []
    with resolved_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv_rows(path: str | Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _sha1(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = sha1()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_seo_weighted_labels(labels_path: str | Path = DEFAULT_OUTPUT_LABELS_PATH) -> dict[str, SeoWeightedLabel]:
    resolved_labels_path = Path(labels_path)
    if not resolved_labels_path.exists():
        raise FileNotFoundError(f"D45 label sidecar not found: {resolved_labels_path}")

    labels: dict[str, SeoWeightedLabel] = {}
    with resolved_labels_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row_number, row in enumerate(reader, start=2):
            query = str(row.get("query") or "").strip().replace("\ufeff", "")
            url = str(row.get("url") or "").strip()
            score = _safe_float(row.get("expert_target_score"), default=-1.0)
            if not query or not url or score < 0.0:
                raise ValueError(f"Invalid D45 label at row {row_number}: query/url/score are required")
            labels[_row_key(query, url)] = SeoWeightedLabel(
                query=query,
                url=url,
                score=round(max(0.0, min(100.0, score)), 4),
                label_source=str(row.get("label_source") or "seo_weighted_rubric_v4").strip(),
                labeler=str(row.get("labeler") or "").strip(),
                critical_score=_safe_float(row.get("critical_score")),
                important_score=_safe_float(row.get("important_score")),
                supporting_score=_safe_float(row.get("supporting_score")),
                rank_prior_score=_safe_float(row.get("rank_prior_score")),
                cap_reasons=str(row.get("cap_reasons") or "").strip(),
                quality_band=str(row.get("quality_band") or "").strip(),
            )
    return labels


def _apply_labels_to_rows(
    rows: Sequence[Mapping[str, str]],
    labels: Mapping[str, SeoWeightedLabel],
    *,
    dataset_version: str,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    output_rows: list[dict[str, object]] = []
    seen_label_keys: set[str] = set()
    missing_labels: list[dict[str, str]] = []
    before_scores: list[float] = []
    after_scores: list[float] = []
    delta_scores: list[float] = []

    for row in rows:
        key = _row_key(str(row.get("query") or ""), str(row.get("url") or ""))
        label = labels.get(key)
        if label is None:
            missing_labels.append(
                {
                    "query": str(row.get("query") or ""),
                    "url": str(row.get("url") or ""),
                }
            )
            continue

        old_target = _safe_float(row.get("target_score"))
        new_target = float(label.score)
        before_scores.append(old_target)
        after_scores.append(new_target)
        delta_scores.append(new_target - old_target)
        seen_label_keys.add(key)

        output_row: dict[str, object] = dict(row)
        output_row["dataset_version"] = dataset_version
        output_row["label_schema_version"] = LABEL_SCHEMA_VERSION_V4
        output_row["label_source"] = label.label_source
        output_row["expert_target_score"] = _format_score(label.score)
        output_row["target_score"] = _format_score(label.score)
        output_rows.append(output_row)

    unmatched_label_keys = sorted(set(labels) - seen_label_keys)
    coverage = {
        "source_rows_count": len(rows),
        "output_rows_count": len(output_rows),
        "labels_loaded": len(labels),
        "labels_applied": len(seen_label_keys),
        "missing_labels_count": len(missing_labels),
        "missing_labels": missing_labels[:20],
        "unmatched_labels_count": len(unmatched_label_keys),
        "unmatched_labels": unmatched_label_keys[:20],
        "old_target_score_distribution": _score_stats(before_scores),
        "new_target_score_distribution": _score_stats(after_scores),
        "target_score_delta_distribution": _score_stats(delta_scores),
    }
    if missing_labels:
        examples = ", ".join(f"{item['query']} -> {item['url']}" for item in missing_labels[:5])
        raise ValueError(f"D46 requires every dataset row to have a D45 label. Missing: {examples}")
    return output_rows, coverage


def _update_versioned_rows(
    path: Path,
    output_path: Path,
    *,
    dataset_version: str,
    feature_schema_version: str | None = None,
) -> dict[str, object]:
    fieldnames, rows = _read_csv_rows(path)
    if not rows:
        return {"source_path": str(path), "output_path": str(output_path), "rows_count": 0, "copied": False}
    updated_rows: list[dict[str, object]] = []
    for row in rows:
        updated_row: dict[str, object] = dict(row)
        if "dataset_version" in updated_row:
            updated_row["dataset_version"] = dataset_version
        if feature_schema_version and "feature_schema_version" in updated_row:
            updated_row["feature_schema_version"] = feature_schema_version
        updated_rows.append(updated_row)
    _write_csv_rows(output_path, fieldnames, updated_rows)
    return {"source_path": str(path), "output_path": str(output_path), "rows_count": len(updated_rows), "copied": True}


def _copy_or_update_auxiliary_files(
    *,
    source_failures_path: Path,
    source_seeds_path: Path,
    output_failures_path: Path,
    output_seeds_path: Path,
    dataset_version: str,
) -> dict[str, object]:
    failures = _update_versioned_rows(
        source_failures_path,
        output_failures_path,
        dataset_version=dataset_version,
        feature_schema_version="v3",
    )
    seeds = {"source_path": str(source_seeds_path), "output_path": str(output_seeds_path), "copied": False}
    if source_seeds_path.exists():
        output_seeds_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_seeds_path, output_seeds_path)
        _, seed_rows = _read_csv_rows(output_seeds_path)
        seeds = {
            "source_path": str(source_seeds_path),
            "output_path": str(output_seeds_path),
            "rows_count": len(seed_rows),
            "copied": True,
        }
    return {"failures": failures, "seeds": seeds}


def _score_stats(scores: Sequence[float]) -> dict[str, float]:
    if not scores:
        return {"min": 0.0, "mean": 0.0, "max": 0.0}
    sorted_scores = sorted(float(score) for score in scores)

    def percentile(ratio: float) -> float:
        index = min(len(sorted_scores) - 1, max(0, round((len(sorted_scores) - 1) * ratio)))
        return round(sorted_scores[index], 4)

    return {
        "min": round(min(sorted_scores), 4),
        "p25": percentile(0.25),
        "mean": round(fmean(sorted_scores), 4),
        "p50": percentile(0.50),
        "p75": percentile(0.75),
        "max": round(max(sorted_scores), 4),
    }


def _counter(values: Sequence[str]) -> dict[str, int]:
    counter = Counter(values)
    return {key: counter[key] for key in sorted(counter)}


def _query_leakage_summary(split: Mapping[str, object]) -> dict[str, object]:
    train_queries = {str(query).strip() for query in split.get("train_queries") or [] if str(query).strip()}
    validation_queries = {
        str(query).strip() for query in split.get("validation_queries") or [] if str(query).strip()
    }
    overlap = sorted(train_queries & validation_queries)
    return {
        "split_mode": str(split.get("split_mode") or ""),
        "train_queries_count": len(train_queries),
        "validation_queries_count": len(validation_queries),
        "query_overlap_count": len(overlap),
        "query_overlap": overlap,
        "passed": str(split.get("split_mode") or "") == "group_by_query" and not overlap,
    }


def _label_evidence_summary(labels: Mapping[str, SeoWeightedLabel]) -> dict[str, object]:
    label_values = list(labels.values())
    return {
        "label_source_distribution": _counter([label.label_source for label in label_values]),
        "quality_band_distribution": _counter([label.quality_band or "unknown" for label in label_values]),
        "cap_reason_distribution": _counter(
            reason
            for label in label_values
            for reason in label.cap_reasons.split("|")
            if reason
        ),
        "critical_score_distribution": _score_stats([label.critical_score for label in label_values]),
        "important_score_distribution": _score_stats([label.important_score for label in label_values]),
        "supporting_score_distribution": _score_stats([label.supporting_score for label in label_values]),
        "rank_prior_score_distribution": _score_stats([label.rank_prior_score for label in label_values]),
    }


def _build_report(
    *,
    source_dataset_path: Path,
    output_dataset_path: Path,
    labels_path: Path,
    rows: Sequence[Mapping[str, object]],
    labels: Mapping[str, SeoWeightedLabel],
    label_application: Mapping[str, object],
    split: Mapping[str, object],
    manifest: Mapping[str, object],
    auxiliary_files: Mapping[str, object],
    production_artifact_path: Path,
) -> dict[str, object]:
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "task": "D46",
        "dataset_version": DEFAULT_DATASET_VERSION,
        "source_dataset_version": "dataset-v3-d37",
        "source_dataset_path": str(source_dataset_path),
        "output_dataset_path": str(output_dataset_path),
        "labels_path": str(labels_path),
        "rows_count": len(rows),
        "label_schema_version": LABEL_SCHEMA_VERSION_V4,
        "feature_schema_version": "v3",
        "target_score_policy": "target_score_equals_d45_seo_weighted_expert_label",
        "label_application": dict(label_application),
        "label_evidence": _label_evidence_summary(labels),
        "split": dict(split),
        "query_leakage": _query_leakage_summary(split),
        "manifest_ready_for_training": bool(manifest.get("quality_gates", {}).get("ready_for_training")),
        "manifest_quality_gates": manifest.get("quality_gates"),
        "manifest_path": manifest.get("manifest_path"),
        "auxiliary_files": dict(auxiliary_files),
        "production_artifact": {
            "path": str(production_artifact_path),
            "sha1": _sha1(production_artifact_path),
            "changed_by_d46": False,
        },
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, report: Mapping[str, object]) -> None:
    label_application = report.get("label_application") if isinstance(report.get("label_application"), dict) else {}
    query_leakage = report.get("query_leakage") if isinstance(report.get("query_leakage"), dict) else {}
    label_evidence = report.get("label_evidence") if isinstance(report.get("label_evidence"), dict) else {}
    new_distribution = (
        label_application.get("new_target_score_distribution")
        if isinstance(label_application.get("new_target_score_distribution"), dict)
        else {}
    )
    lines = [
        "# D46 Dataset v4 Build And Validation",
        "",
        f"- Source dataset: `{report.get('source_dataset_version')}`",
        f"- Output dataset: `{report.get('output_dataset_path')}`",
        f"- Labels: `{report.get('labels_path')}`",
        f"- Rows: `{report.get('rows_count')}`",
        f"- Label schema: `{report.get('label_schema_version')}`",
        f"- Target policy: `{report.get('target_score_policy')}`",
        f"- Manifest ready for training: `{report.get('manifest_ready_for_training')}`",
        f"- Split leakage check: `{'passed' if query_leakage.get('passed') else 'failed'}`",
        f"- Production artifact changed by D46: `{report.get('production_artifact', {}).get('changed_by_d46') if isinstance(report.get('production_artifact'), dict) else False}`",
        "",
        "## Label Application",
        "",
        f"- Labels loaded: `{label_application.get('labels_loaded')}`",
        f"- Labels applied: `{label_application.get('labels_applied')}`",
        f"- Missing labels: `{label_application.get('missing_labels_count')}`",
        f"- Unmatched labels: `{label_application.get('unmatched_labels_count')}`",
        "",
        "## New Target Score Distribution",
        "",
        *[f"- `{key}`: `{value}`" for key, value in new_distribution.items()],
        "",
        "## Label Evidence",
        "",
        f"- Label sources: `{label_evidence.get('label_source_distribution')}`",
        f"- Quality bands: `{label_evidence.get('quality_band_distribution')}`",
        "",
        "## Split",
        "",
        f"- Mode: `{query_leakage.get('split_mode')}`",
        f"- Train queries: `{query_leakage.get('train_queries_count')}`",
        f"- Validation queries: `{query_leakage.get('validation_queries_count')}`",
        f"- Query overlap: `{query_leakage.get('query_overlap_count')}`",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_v4_dataset(
    *,
    source_dataset_path: str | Path = DEFAULT_SOURCE_DATASET_PATH,
    source_failures_path: str | Path = DEFAULT_SOURCE_FAILURES_PATH,
    source_seeds_path: str | Path = DEFAULT_SOURCE_SEEDS_PATH,
    source_artifacts_dir: str | Path = DEFAULT_SOURCE_ARTIFACTS_DIR,
    labels_path: str | Path = DEFAULT_OUTPUT_LABELS_PATH,
    output_dataset_path: str | Path = DEFAULT_OUTPUT_DATASET_PATH,
    output_failures_path: str | Path = DEFAULT_OUTPUT_FAILURES_PATH,
    output_seeds_path: str | Path = DEFAULT_OUTPUT_SEEDS_PATH,
    output_split_path: str | Path = DEFAULT_OUTPUT_SPLIT_PATH,
    output_manifest_path: str | Path = DEFAULT_OUTPUT_MANIFEST_PATH,
    output_report_json_path: str | Path = DEFAULT_OUTPUT_REPORT_JSON_PATH,
    output_report_markdown_path: str | Path = DEFAULT_OUTPUT_REPORT_MD_PATH,
    production_artifact_path: str | Path = DEFAULT_PRODUCTION_ARTIFACT_PATH,
    dataset_version: str = DEFAULT_DATASET_VERSION,
    thresholds: DatasetQualityThresholds = PRODUCTION_LIKE_DATASET_THRESHOLDS,
) -> dict[str, object]:
    resolved_source_dataset_path = Path(source_dataset_path)
    resolved_source_failures_path = Path(source_failures_path)
    resolved_source_seeds_path = Path(source_seeds_path)
    resolved_source_artifacts_dir = Path(source_artifacts_dir)
    resolved_labels_path = Path(labels_path)
    resolved_output_dataset_path = Path(output_dataset_path)
    resolved_output_failures_path = Path(output_failures_path)
    resolved_output_seeds_path = Path(output_seeds_path)
    resolved_output_split_path = Path(output_split_path)
    resolved_output_manifest_path = Path(output_manifest_path)
    resolved_output_report_json_path = Path(output_report_json_path)
    resolved_output_report_markdown_path = Path(output_report_markdown_path)
    resolved_production_artifact_path = Path(production_artifact_path)

    fieldnames, source_rows = _read_csv_rows(resolved_source_dataset_path)
    if not fieldnames or not source_rows:
        raise ValueError(f"Source dataset is empty or missing: {resolved_source_dataset_path}")

    labels = load_seo_weighted_labels(resolved_labels_path)
    output_rows, label_application = _apply_labels_to_rows(
        source_rows,
        labels,
        dataset_version=dataset_version,
    )
    _write_csv_rows(resolved_output_dataset_path, fieldnames, output_rows)
    auxiliary_files = _copy_or_update_auxiliary_files(
        source_failures_path=resolved_source_failures_path,
        source_seeds_path=resolved_source_seeds_path,
        output_failures_path=resolved_output_failures_path,
        output_seeds_path=resolved_output_seeds_path,
        dataset_version=dataset_version,
    )

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
        thresholds=thresholds,
        dataset_version=dataset_version,
        baseline_version=BASELINE_DATASET_VERSION,
        artifacts_dir=resolved_source_artifacts_dir,
        split_path=resolved_output_split_path,
    )

    report = _build_report(
        source_dataset_path=resolved_source_dataset_path,
        output_dataset_path=resolved_output_dataset_path,
        labels_path=resolved_labels_path,
        rows=output_rows,
        labels=labels,
        label_application=label_application,
        split=split,
        manifest=manifest,
        auxiliary_files=auxiliary_files,
        production_artifact_path=resolved_production_artifact_path,
    )
    _write_json(resolved_output_report_json_path, report)
    _write_markdown(resolved_output_report_markdown_path, report)
    return {
        **report,
        "report_json_path": str(resolved_output_report_json_path),
        "report_markdown_path": str(resolved_output_report_markdown_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build D46 dataset-v4 from D37 rows and D45 labels.")
    parser.add_argument("--source-dataset", default=str(DEFAULT_SOURCE_DATASET_PATH))
    parser.add_argument("--source-failures", default=str(DEFAULT_SOURCE_FAILURES_PATH))
    parser.add_argument("--source-seeds", default=str(DEFAULT_SOURCE_SEEDS_PATH))
    parser.add_argument("--source-artifacts-dir", default=str(DEFAULT_SOURCE_ARTIFACTS_DIR))
    parser.add_argument("--labels", default=str(DEFAULT_OUTPUT_LABELS_PATH))
    parser.add_argument("--output-dataset", default=str(DEFAULT_OUTPUT_DATASET_PATH))
    parser.add_argument("--output-failures", default=str(DEFAULT_OUTPUT_FAILURES_PATH))
    parser.add_argument("--output-seeds", default=str(DEFAULT_OUTPUT_SEEDS_PATH))
    parser.add_argument("--output-split", default=str(DEFAULT_OUTPUT_SPLIT_PATH))
    parser.add_argument("--output-manifest", default=str(DEFAULT_OUTPUT_MANIFEST_PATH))
    parser.add_argument("--output-report-json", default=str(DEFAULT_OUTPUT_REPORT_JSON_PATH))
    parser.add_argument("--output-report-md", default=str(DEFAULT_OUTPUT_REPORT_MD_PATH))
    parser.add_argument("--production-artifact", default=str(DEFAULT_PRODUCTION_ARTIFACT_PATH))
    args = parser.parse_args()
    report = build_v4_dataset(
        source_dataset_path=args.source_dataset,
        source_failures_path=args.source_failures,
        source_seeds_path=args.source_seeds,
        source_artifacts_dir=args.source_artifacts_dir,
        labels_path=args.labels,
        output_dataset_path=args.output_dataset,
        output_failures_path=args.output_failures,
        output_seeds_path=args.output_seeds,
        output_split_path=args.output_split,
        output_manifest_path=args.output_manifest,
        output_report_json_path=args.output_report_json,
        output_report_markdown_path=args.output_report_md,
        production_artifact_path=args.production_artifact,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
