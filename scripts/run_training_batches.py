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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds-file", default=str(DEFAULT_SEEDS_PATH))
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--failures", default=str(DEFAULT_FAILURES_PATH))
    parser.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT_PATH))
    parser.add_argument("--model-output", default=str(BACKEND_DIR / "artifacts" / "page_quality_model.pkl"))
    parser.add_argument("--batch-size", type=int, default=60)
    parser.add_argument("--target-rows", type=int, default=1800)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--query-delay", type=float, default=1.0)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        seeds = load_seed_rows(args.seeds_file)
        dataset_path = Path(args.dataset)

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
            stats = _dataset_stats(dataset_path)
            print(
                {
                    "batch": batch_number,
                    "result": result,
                    "stats": stats,
                }
            )
            if stats["rows_count"] >= args.target_rows:
                break

        final_stats = _dataset_stats(dataset_path)
        if final_stats["rows_count"] >= args.target_rows:
            training_result = train_quality_model(
                dataset_path=args.dataset,
                model_path=args.model_output,
            )
            print({"training_result": training_result})
        else:
            print(
                {
                    "status": "dataset_incomplete",
                    "rows_count": final_stats["rows_count"],
                    "target_rows": args.target_rows,
                }
            )
    except SerpConfigurationError as error:
        print({"error": str(error)})
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
