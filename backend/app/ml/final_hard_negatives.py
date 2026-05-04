from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.features import SNAPSHOT_AUXILIARY_FEATURE_COLUMNS, build_features, merge_snapshot_auxiliary_features
from app.ml.dataset_builder import DATASET_COLUMNS, load_seed_rows
from app.ml.final_query_competitiveness import FINAL_DATASET_DIR, FINAL_DATASET_PATH
from app.ml.model import FEATURE_COLUMNS
from app.parser import ensure_extraction_artifact, extraction_artifact_html, extraction_artifact_text


HARD_NEGATIVE_POLICY_VERSION = "dataset-v7-hard-negatives-v1"
DEFAULT_OUTPUT_PATH = FINAL_DATASET_DIR / "dataset.with-hard-negatives.csv"
DEFAULT_REPORT_PATH = FINAL_DATASET_DIR / "d69-hard-negatives-report.json"

HARD_NEGATIVE_EXTRA_COLUMNS = [
    "hard_negative",
    "hard_negative_policy_version",
    "hard_negative_source_query",
    "hard_negative_source_category",
    "hard_negative_source_url",
]


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return []
    with resolved_path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, object]]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for column in [*DATASET_COLUMNS, *HARD_NEGATIVE_EXTRA_COLUMNS]:
        if column not in seen:
            seen.add(column)
            fieldnames.append(column)
    for row in rows:
        for column in row.keys():
            if column not in seen:
                seen.add(column)
                fieldnames.append(str(column))

    with resolved_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in fieldnames})


def _artifact_path(dataset_path: Path, artifact_value: object) -> Path | None:
    raw = str(artifact_value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    return dataset_path.parent / path


def _load_snapshot(dataset_path: Path, row: Mapping[str, object]) -> dict[str, object] | None:
    artifact_path = _artifact_path(dataset_path, row.get("artifact_path"))
    if artifact_path is None or not artifact_path.exists():
        return None
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return ensure_extraction_artifact(
        requested_url=str(payload.get("requested_url") or row.get("url") or ""),
        artifact=payload,
    )


def _clone_as_hard_negative(
    *,
    dataset_path: Path,
    source_row: Mapping[str, object],
    target_seed: Mapping[str, object],
) -> dict[str, object] | None:
    snapshot = _load_snapshot(dataset_path, source_row)
    if snapshot is None:
        return None
    query = str(target_seed.get("query") or "").strip()
    if not query:
        return None
    html = extraction_artifact_html(snapshot)
    text = extraction_artifact_text(snapshot)
    features = merge_snapshot_auxiliary_features(build_features(html=html, text=text, query=query), snapshot)

    row: dict[str, object] = dict(source_row)
    row.update(
        {
            "query": query,
            "category": str(target_seed.get("category") or ""),
            "intent": str(target_seed.get("intent") or ""),
            "city": str(target_seed.get("city") or ""),
            "region_code": str(target_seed.get("region_code") or ""),
            "rank": 999,
            "serp_page": -1,
            "label_source": "hard_negative_v7",
            "weak_target_score": "",
            "expert_target_score": "",
            "target_score": "",
            "hard_negative": 1,
            "hard_negative_policy_version": HARD_NEGATIVE_POLICY_VERSION,
            "hard_negative_source_query": str(source_row.get("query") or ""),
            "hard_negative_source_category": str(source_row.get("category") or ""),
            "hard_negative_source_url": str(source_row.get("url") or ""),
        }
    )
    for feature_name in FEATURE_COLUMNS:
        row[feature_name] = float(features.get(feature_name, 0.0))
    for feature_name in SNAPSHOT_AUXILIARY_FEATURE_COLUMNS:
        row[feature_name] = float(features.get(feature_name, 0.0))
    return row


def _seed_payloads(seeds_path: str | Path) -> list[dict[str, object]]:
    seeds = load_seed_rows(seeds_path)
    return [
        {
            "query": seed.query,
            "category": seed.category,
            "intent": seed.intent,
            "city": seed.city,
            "region_code": seed.region_code or "",
        }
        for seed in seeds
    ]


def materialize_hard_negatives(
    *,
    dataset_path: str | Path = FINAL_DATASET_PATH,
    seeds_path: str | Path = FINAL_DATASET_DIR / "seeds.csv",
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    report_path: str | Path = DEFAULT_REPORT_PATH,
    max_negatives_per_query: int = 2,
) -> dict[str, Any]:
    resolved_dataset_path = Path(dataset_path)
    source_rows = _read_csv(resolved_dataset_path)
    if not source_rows:
        raise ValueError(f"Dataset is empty or missing: {resolved_dataset_path}")
    seeds = _seed_payloads(seeds_path)
    if not seeds:
        raise ValueError(f"Seed file is empty or missing: {seeds_path}")

    rows_by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in source_rows:
        category = str(row.get("category") or "").strip()
        if category:
            rows_by_category[category].append(row)

    hard_negative_rows: list[dict[str, object]] = []
    missing_artifact_count = 0
    duplicate_keys: set[tuple[str, str, str]] = set()

    for seed_index, seed in enumerate(seeds):
        target_category = str(seed.get("category") or "").strip()
        source_pool = [
            row
            for category, category_rows in sorted(rows_by_category.items())
            if category and category != target_category
            for row in category_rows
        ]
        if not source_pool:
            continue
        accepted_for_query = 0
        cursor = seed_index % len(source_pool)
        for offset in range(len(source_pool)):
            if accepted_for_query >= max_negatives_per_query:
                break
            source_row = source_pool[(cursor + offset) % len(source_pool)]
            key = (
                str(seed.get("query") or ""),
                str(source_row.get("url") or ""),
                str(source_row.get("query") or ""),
            )
            if key in duplicate_keys:
                continue
            duplicate_keys.add(key)
            cloned_row = _clone_as_hard_negative(
                dataset_path=resolved_dataset_path,
                source_row=source_row,
                target_seed=seed,
            )
            if cloned_row is None:
                missing_artifact_count += 1
                continue
            hard_negative_rows.append(cloned_row)
            accepted_for_query += 1

    original_rows: list[dict[str, object]] = []
    for row in source_rows:
        enriched = dict(row)
        enriched.setdefault("hard_negative", 0)
        enriched.setdefault("hard_negative_policy_version", "")
        enriched.setdefault("hard_negative_source_query", "")
        enriched.setdefault("hard_negative_source_category", "")
        enriched.setdefault("hard_negative_source_url", "")
        original_rows.append(enriched)

    output_rows = [*original_rows, *hard_negative_rows]
    _write_csv(output_path, output_rows)
    report = {
        "task": "D69",
        "generated_at": datetime.now(UTC).isoformat(),
        "hard_negative_policy_version": HARD_NEGATIVE_POLICY_VERSION,
        "dataset_path": str(resolved_dataset_path),
        "seeds_path": str(Path(seeds_path)),
        "output_path": str(Path(output_path)),
        "source_rows_count": len(source_rows),
        "seeds_count": len(seeds),
        "hard_negative_rows_count": len(hard_negative_rows),
        "output_rows_count": len(output_rows),
        "max_negatives_per_query": max_negatives_per_query,
        "missing_artifact_count": missing_artifact_count,
    }
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize dataset-v7 hard negatives from saved page snapshots.")
    parser.add_argument("--dataset", default=str(FINAL_DATASET_PATH))
    parser.add_argument("--seeds", default=str(FINAL_DATASET_DIR / "seeds.csv"))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--max-negatives-per-query", type=int, default=2)
    args = parser.parse_args()
    report = materialize_hard_negatives(
        dataset_path=args.dataset,
        seeds_path=args.seeds,
        output_path=args.output,
        report_path=args.report,
        max_negatives_per_query=args.max_negatives_per_query,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
