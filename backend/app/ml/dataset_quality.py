from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
import json
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class DatasetQualityThresholds:
    min_rows: int = 400
    min_unique_queries: int = 40
    min_unique_domains: int = 250
    min_unique_categories: int = 6
    min_unique_cities: int = 6
    min_query_coverage_ratio: float = 0.2
    min_average_rows_per_query: float = 5.0
    max_failure_rate: float = 0.2

    def with_overrides(self, **kwargs: int | float | None) -> DatasetQualityThresholds:
        normalized_kwargs = {key: value for key, value in kwargs.items() if value is not None}
        return replace(self, **normalized_kwargs)


PRODUCTION_LIKE_DATASET_THRESHOLDS = DatasetQualityThresholds()


def default_manifest_path(dataset_path: str | Path) -> Path:
    resolved_path = Path(dataset_path)
    return resolved_path.with_name(f"{resolved_path.stem}.manifest.json")


def _load_csv_rows(csv_path: Path | None) -> list[dict[str, str]]:
    if csv_path is None or not csv_path.exists():
        return []

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader]


def _normalize_seed_rows(seed_rows: Sequence[Mapping[str, object]] | None) -> list[dict[str, str]]:
    if not seed_rows:
        return []

    normalized_rows: list[dict[str, str]] = []
    for row in seed_rows:
        normalized_rows.append({key: str(value or "") for key, value in row.items()})
    return normalized_rows


def _load_seed_rows(seed_rows: Sequence[Mapping[str, object]] | None, seeds_path: Path | None) -> list[dict[str, str]]:
    normalized_rows = _normalize_seed_rows(seed_rows)
    if normalized_rows:
        return normalized_rows
    return _load_csv_rows(seeds_path)


def _counter_to_sorted_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _safe_float(value: object) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _round_metric(value: float) -> float:
    return round(float(value), 6)


def _unique_query_values(rows: Sequence[Mapping[str, str]], value_key: str) -> Counter[str]:
    query_to_value: dict[str, str] = {}
    for row in rows:
        query = str(row.get("query") or "").strip()
        value = str(row.get(value_key) or "").strip()
        if query and value:
            query_to_value.setdefault(query, value)
    return Counter(query_to_value.values())


def _coverage_breakdown(
    seed_rows: Sequence[Mapping[str, str]],
    success_rows: Sequence[Mapping[str, str]],
    key: str,
) -> list[dict[str, object]]:
    seed_distribution = _unique_query_values(seed_rows, key)
    success_distribution = _unique_query_values(success_rows, key)
    values = sorted(seed_distribution.keys() | success_distribution.keys())

    breakdown: list[dict[str, object]] = []
    for value in values:
        seed_queries = int(seed_distribution.get(value, 0))
        success_queries = int(success_distribution.get(value, 0))
        coverage_ratio = _round_metric(success_queries / seed_queries) if seed_queries else 0.0
        breakdown.append(
            {
                "value": value,
                "seed_queries": seed_queries,
                "success_queries": success_queries,
                "coverage_ratio": coverage_ratio,
            }
        )
    return breakdown


def _evaluate_quality_gate(
    name: str,
    actual: float,
    expected: float,
    comparator: str,
) -> dict[str, object]:
    if comparator == "min":
        passed = actual >= expected
    elif comparator == "max":
        passed = actual <= expected
    else:
        raise ValueError(f"Unsupported comparator: {comparator}")

    return {
        "name": name,
        "passed": passed,
        "actual": _round_metric(actual),
        "expected": _round_metric(expected),
        "comparator": comparator,
    }


def evaluate_dataset_quality(
    coverage: Mapping[str, object],
    thresholds: DatasetQualityThresholds = PRODUCTION_LIKE_DATASET_THRESHOLDS,
) -> dict[str, object]:
    checks = [
        _evaluate_quality_gate("min_rows", _safe_float(coverage.get("rows_count")), thresholds.min_rows, "min"),
        _evaluate_quality_gate(
            "min_unique_queries",
            _safe_float(coverage.get("unique_queries")),
            thresholds.min_unique_queries,
            "min",
        ),
        _evaluate_quality_gate(
            "min_unique_domains",
            _safe_float(coverage.get("unique_domains")),
            thresholds.min_unique_domains,
            "min",
        ),
        _evaluate_quality_gate(
            "min_unique_categories",
            _safe_float(coverage.get("unique_categories")),
            thresholds.min_unique_categories,
            "min",
        ),
        _evaluate_quality_gate(
            "min_unique_cities",
            _safe_float(coverage.get("unique_cities")),
            thresholds.min_unique_cities,
            "min",
        ),
        _evaluate_quality_gate(
            "min_query_coverage_ratio",
            _safe_float(coverage.get("query_coverage_ratio")),
            thresholds.min_query_coverage_ratio,
            "min",
        ),
        _evaluate_quality_gate(
            "min_average_rows_per_query",
            _safe_float(coverage.get("average_rows_per_query")),
            thresholds.min_average_rows_per_query,
            "min",
        ),
        _evaluate_quality_gate(
            "max_failure_rate",
            _safe_float(coverage.get("failure_rate")),
            thresholds.max_failure_rate,
            "max",
        ),
    ]

    return {
        "ready_for_training": all(check["passed"] for check in checks),
        "thresholds": asdict(thresholds),
        "checks": checks,
        "unmet_requirements": [check["name"] for check in checks if not check["passed"]],
    }


def build_dataset_manifest(
    dataset_path: str | Path,
    failures_path: str | Path | None = None,
    *,
    seed_rows: Sequence[Mapping[str, object]] | None = None,
    seeds_path: str | Path | None = None,
    thresholds: DatasetQualityThresholds = PRODUCTION_LIKE_DATASET_THRESHOLDS,
) -> dict[str, object]:
    resolved_dataset_path = Path(dataset_path)
    resolved_failures_path = Path(failures_path) if failures_path is not None else None
    resolved_seeds_path = Path(seeds_path) if seeds_path is not None else None

    success_rows = _load_csv_rows(resolved_dataset_path)
    failure_rows = _load_csv_rows(resolved_failures_path)
    normalized_seed_rows = _load_seed_rows(seed_rows=seed_rows, seeds_path=resolved_seeds_path)

    success_queries = {str(row.get("query") or "").strip() for row in success_rows if row.get("query")}
    failure_queries = {str(row.get("query") or "").strip() for row in failure_rows if row.get("query")}
    seed_queries = {str(row.get("query") or "").strip() for row in normalized_seed_rows if row.get("query")}

    success_domains = {str(row.get("domain") or "").strip() for row in success_rows if row.get("domain")}
    success_categories = {str(row.get("category") or "").strip() for row in success_rows if row.get("category")}
    success_cities = {str(row.get("city") or "").strip() for row in success_rows if row.get("city")}
    page_type_distribution = Counter(str(row.get("page_type") or "unknown").strip() or "unknown" for row in success_rows)
    region_distribution = Counter(str(row.get("region_code") or "").strip() for row in success_rows if row.get("region_code"))
    failure_messages = Counter(str(row.get("fetch_error") or "unknown_failure").strip() or "unknown_failure" for row in failure_rows)
    rank_values = [_safe_int(row.get("rank")) for row in success_rows if row.get("rank")]

    rows_count = len(success_rows)
    failures_count = len(failure_rows)
    attempts_count = rows_count + failures_count
    query_coverage_ratio = _round_metric(len(success_queries) / len(seed_queries)) if seed_queries else 1.0
    attempted_query_coverage_ratio = _round_metric(len(success_queries | failure_queries) / len(seed_queries)) if seed_queries else 1.0
    failure_rate = _round_metric(failures_count / attempts_count) if attempts_count else 0.0
    average_rows_per_query = _round_metric(rows_count / len(success_queries)) if success_queries else 0.0
    average_rank = _round_metric(fmean(rank_values)) if rank_values else 0.0

    coverage = {
        "rows_count": rows_count,
        "failures_count": failures_count,
        "attempts_count": attempts_count,
        "unique_queries": len(success_queries),
        "attempted_queries": len(success_queries | failure_queries),
        "seed_queries_count": len(seed_queries),
        "unique_domains": len(success_domains),
        "unique_categories": len(success_categories),
        "unique_cities": len(success_cities),
        "query_coverage_ratio": query_coverage_ratio,
        "attempted_query_coverage_ratio": attempted_query_coverage_ratio,
        "average_rows_per_query": average_rows_per_query,
        "failure_rate": failure_rate,
        "average_rank": average_rank,
        "best_rank": min(rank_values) if rank_values else 0,
        "worst_rank": max(rank_values) if rank_values else 0,
        "page_type_distribution": _counter_to_sorted_dict(page_type_distribution),
        "region_distribution": _counter_to_sorted_dict(region_distribution),
        "top_failure_messages": [
            {"message": message, "count": count}
            for message, count in failure_messages.most_common(5)
        ],
    }
    coverage["category_coverage"] = _coverage_breakdown(normalized_seed_rows, success_rows, "category")
    coverage["city_coverage"] = _coverage_breakdown(normalized_seed_rows, success_rows, "city")

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_path": str(resolved_dataset_path),
        "failures_path": str(resolved_failures_path) if resolved_failures_path is not None else None,
        "seeds_path": str(resolved_seeds_path) if resolved_seeds_path is not None else None,
        "coverage": coverage,
        "quality_gates": evaluate_dataset_quality(coverage, thresholds=thresholds),
    }


def save_dataset_manifest(
    dataset_path: str | Path,
    failures_path: str | Path | None = None,
    *,
    seed_rows: Sequence[Mapping[str, object]] | None = None,
    seeds_path: str | Path | None = None,
    output_path: str | Path | None = None,
    thresholds: DatasetQualityThresholds = PRODUCTION_LIKE_DATASET_THRESHOLDS,
) -> dict[str, object]:
    manifest = build_dataset_manifest(
        dataset_path=dataset_path,
        failures_path=failures_path,
        seed_rows=seed_rows,
        seeds_path=seeds_path,
        thresholds=thresholds,
    )
    resolved_output_path = Path(output_path) if output_path is not None else default_manifest_path(dataset_path)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        **manifest,
        "manifest_path": str(resolved_output_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--failures", default="")
    parser.add_argument("--seeds", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--min-rows", type=int, default=PRODUCTION_LIKE_DATASET_THRESHOLDS.min_rows)
    parser.add_argument(
        "--min-unique-queries",
        type=int,
        default=PRODUCTION_LIKE_DATASET_THRESHOLDS.min_unique_queries,
    )
    parser.add_argument(
        "--min-unique-domains",
        type=int,
        default=PRODUCTION_LIKE_DATASET_THRESHOLDS.min_unique_domains,
    )
    parser.add_argument(
        "--min-unique-categories",
        type=int,
        default=PRODUCTION_LIKE_DATASET_THRESHOLDS.min_unique_categories,
    )
    parser.add_argument(
        "--min-unique-cities",
        type=int,
        default=PRODUCTION_LIKE_DATASET_THRESHOLDS.min_unique_cities,
    )
    parser.add_argument(
        "--min-query-coverage-ratio",
        type=float,
        default=PRODUCTION_LIKE_DATASET_THRESHOLDS.min_query_coverage_ratio,
    )
    parser.add_argument(
        "--min-average-rows-per-query",
        type=float,
        default=PRODUCTION_LIKE_DATASET_THRESHOLDS.min_average_rows_per_query,
    )
    parser.add_argument(
        "--max-failure-rate",
        type=float,
        default=PRODUCTION_LIKE_DATASET_THRESHOLDS.max_failure_rate,
    )
    args = parser.parse_args()

    thresholds = DatasetQualityThresholds(
        min_rows=args.min_rows,
        min_unique_queries=args.min_unique_queries,
        min_unique_domains=args.min_unique_domains,
        min_unique_categories=args.min_unique_categories,
        min_unique_cities=args.min_unique_cities,
        min_query_coverage_ratio=args.min_query_coverage_ratio,
        min_average_rows_per_query=args.min_average_rows_per_query,
        max_failure_rate=args.max_failure_rate,
    )
    manifest = save_dataset_manifest(
        dataset_path=args.dataset,
        failures_path=args.failures or None,
        seeds_path=args.seeds or None,
        output_path=args.output or None,
        thresholds=thresholds,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
