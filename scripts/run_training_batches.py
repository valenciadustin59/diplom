from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.dataset_builder import (  # noqa: E402
    DEFAULT_CHECKPOINT_PATH,
    DEFAULT_DATASET_PATH,
    DEFAULT_FAILURES_PATH,
    DEFAULT_SEEDS_PATH,
    build_dataset,
    load_seed_rows,
)
from app.ml.dataset_quality import (  # noqa: E402
    PRODUCTION_LIKE_DATASET_THRESHOLDS,
    DatasetQualityThresholds,
    default_manifest_path,
    save_dataset_manifest,
)
from app.ml.train import train_quality_model  # noqa: E402
from app.serp import SerpConfigurationError  # noqa: E402


def _dataset_stats(dataset_path: Path) -> dict[str, int]:
    if not dataset_path.exists():
        return {"rows_count": 0, "unique_queries": 0, "unique_domains": 0}

    with dataset_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    return {
        "rows_count": len(rows),
        "unique_queries": len({str(row.get("query") or "") for row in rows}),
        "unique_domains": len({str(row.get("domain") or "") for row in rows}),
    }


def _resolve_thresholds(args: argparse.Namespace) -> DatasetQualityThresholds:
    return PRODUCTION_LIKE_DATASET_THRESHOLDS.with_overrides(
        min_rows=args.target_rows,
        min_unique_queries=args.min_unique_queries,
        min_unique_domains=args.min_unique_domains,
        min_unique_categories=args.min_unique_categories,
        min_unique_cities=args.min_unique_cities,
        min_query_coverage_ratio=args.min_query_coverage_ratio,
        min_average_rows_per_query=args.min_average_rows_per_query,
        max_failure_rate=args.max_failure_rate,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds-file", default=str(DEFAULT_SEEDS_PATH))
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--failures", default=str(DEFAULT_FAILURES_PATH))
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT_PATH))
    parser.add_argument("--manifest", default="")
    parser.add_argument("--model-output", default=str(BACKEND_DIR / "artifacts" / "page_quality_model.pkl"))
    parser.add_argument("--batch-size", type=int, default=60)
    parser.add_argument("--target-rows", type=int, default=1800)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--query-delay", type=float, default=1.0)
    parser.add_argument("--overwrite", action="store_true")
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

    quality_thresholds = _resolve_thresholds(args)
    manifest_path = Path(args.manifest) if args.manifest else default_manifest_path(args.dataset)

    try:
        dataset_path = Path(args.dataset)
        seeds = load_seed_rows(args.seeds_file)
        for batch_start in range(0, len(seeds), args.batch_size):
            batch_number = (batch_start // args.batch_size) + 1
            result = build_dataset(
                output_path=args.dataset,
                failures_path=args.failures,
                checkpoint_path=args.checkpoint,
                seeds_file=args.seeds_file,
                overwrite=args.overwrite and batch_start == 0,
                max_workers=args.max_workers,
                query_delay_seconds=args.query_delay,
                seed_offset=batch_start,
                seed_limit=args.batch_size,
            )
            manifest = save_dataset_manifest(
                dataset_path=args.dataset,
                failures_path=args.failures,
                seeds_path=args.seeds_file,
                output_path=manifest_path,
                thresholds=quality_thresholds,
            )
            stats = _dataset_stats(dataset_path)
            print(
                {
                    "batch": batch_number,
                    "result": result,
                    "stats": stats,
                    "quality": manifest["quality_gates"],
                    "manifest_path": str(manifest_path),
                }
            )
            if manifest["quality_gates"]["ready_for_training"]:
                break

        final_stats = _dataset_stats(dataset_path)
        final_manifest = save_dataset_manifest(
            dataset_path=args.dataset,
            failures_path=args.failures,
            seeds_path=args.seeds_file,
            output_path=manifest_path,
            thresholds=quality_thresholds,
        )
        if final_manifest["quality_gates"]["ready_for_training"]:
            training_result = train_quality_model(
                dataset_path=args.dataset,
                model_path=args.model_output,
            )
            print({"training_result": training_result, "manifest_path": str(manifest_path)})
        else:
            print(
                {
                    "status": "dataset_incomplete",
                    "rows_count": final_stats["rows_count"],
                    "quality": final_manifest["quality_gates"],
                    "manifest_path": str(manifest_path),
                }
            )
    except SerpConfigurationError as error:
        print({"error": str(error)})
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
