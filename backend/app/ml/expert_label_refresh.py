from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.ml.dataset_builder import DATA_DIR, load_expert_labels, resolve_target_label


DEFAULT_DATASET_V2_DIR = DATA_DIR / "dataset_versions" / "dataset-v2"
DEFAULT_DATASET_PATH = DEFAULT_DATASET_V2_DIR / "dataset.csv"
DEFAULT_EXPERT_LABELS_PATH = DEFAULT_DATASET_V2_DIR / "expert_labels.csv"
REQUIRED_DATASET_COLUMNS = {"query", "url", "weak_target_score", "expert_target_score", "label_source", "target_score"}


@dataclass(frozen=True, slots=True)
class ExpertLabelRefreshResult:
    dataset_path: str
    output_path: str
    rows_count: int
    expert_labels_loaded: int
    updated_rows_count: int
    weak_only_rows_count: int
    unmatched_expert_labels_count: int
    label_source_distribution: dict[str, int]


def _row_key(query: str, url: str) -> str:
    return f"{query.strip().replace('\ufeff', '')}|{url.strip()}"


def _safe_float(value: object, *, field_name: str, row_number: int) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid {field_name!r} value at dataset row {row_number}: {value!r}") from error


def _format_score(value: float) -> str:
    return str(round(float(value), 4))


def _validate_fieldnames(fieldnames: list[str] | None) -> list[str]:
    if not fieldnames:
        raise ValueError("Dataset CSV has no header.")
    missing_columns = sorted(REQUIRED_DATASET_COLUMNS - set(fieldnames))
    if missing_columns:
        raise ValueError(f"Dataset CSV is missing required columns: {', '.join(missing_columns)}")
    return fieldnames


def _write_rows_atomically(output_path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=output_path.parent) as temp_file:
        temp_path = Path(temp_file.name)
        writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    temp_path.replace(output_path)


def refresh_dataset_expert_labels(
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    expert_labels_path: str | Path = DEFAULT_EXPERT_LABELS_PATH,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    resolved_dataset_path = Path(dataset_path)
    resolved_output_path = Path(output_path) if output_path is not None else resolved_dataset_path
    expert_labels = load_expert_labels(expert_labels_path)

    if not resolved_dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {resolved_dataset_path}")

    with resolved_dataset_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = _validate_fieldnames(reader.fieldnames)
        rows = [dict(row) for row in reader]

    updated_rows_count = 0
    label_source_distribution: dict[str, int] = {}
    seen_expert_label_keys: set[str] = set()
    refreshed_rows: list[dict[str, str]] = []

    for row_number, row in enumerate(rows, start=2):
        key = _row_key(str(row.get("query") or ""), str(row.get("url") or ""))
        expert_label = expert_labels.get(key)
        if expert_label is None:
            row["label_source"] = "weak_serp"
            row["expert_target_score"] = ""
            row["target_score"] = _format_score(
                _safe_float(row.get("weak_target_score"), field_name="weak_target_score", row_number=row_number)
            )
        else:
            weak_target_score = _safe_float(
                row.get("weak_target_score"),
                field_name="weak_target_score",
                row_number=row_number,
            )
            target_score, expert_target_score, label_source = resolve_target_label(weak_target_score, expert_label)
            row["label_source"] = label_source
            row["expert_target_score"] = _format_score(float(expert_target_score or 0.0))
            row["target_score"] = _format_score(target_score)
            updated_rows_count += 1
            seen_expert_label_keys.add(key)

        label_source = str(row.get("label_source") or "weak_serp")
        label_source_distribution[label_source] = label_source_distribution.get(label_source, 0) + 1
        refreshed_rows.append(row)

    _write_rows_atomically(resolved_output_path, fieldnames, refreshed_rows)

    result = ExpertLabelRefreshResult(
        dataset_path=str(resolved_dataset_path),
        output_path=str(resolved_output_path),
        rows_count=len(refreshed_rows),
        expert_labels_loaded=len(expert_labels),
        updated_rows_count=updated_rows_count,
        weak_only_rows_count=len(refreshed_rows) - updated_rows_count,
        unmatched_expert_labels_count=len(set(expert_labels) - seen_expert_label_keys),
        label_source_distribution=dict(sorted(label_source_distribution.items())),
    )
    return asdict(result)


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply expert labels to an existing dataset CSV.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--expert-labels", default=str(DEFAULT_EXPERT_LABELS_PATH))
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = refresh_dataset_expert_labels(
        dataset_path=args.dataset,
        expert_labels_path=args.expert_labels,
        output_path=args.output or None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
