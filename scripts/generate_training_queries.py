from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.query_seeds import (  # noqa: E402
    TRAINING_SEED_FIELDS,
    build_seed_catalog_summary,
    build_training_queries,
    build_training_seed_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--pages-to-scan", type=int, default=1)
    args = parser.parse_args()

    backend_data_dir = BACKEND_DIR / "data"
    backend_data_dir.mkdir(parents=True, exist_ok=True)

    seeds_path = backend_data_dir / "training_query_seeds.csv"
    legacy_queries_path = backend_data_dir / "training_queries.txt"
    seed_rows = build_training_seed_rows(top_n=args.top_n, pages_to_scan=args.pages_to_scan)
    training_queries = build_training_queries(seed_rows)

    with seeds_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=TRAINING_SEED_FIELDS)
        writer.writeheader()
        writer.writerows(seed_rows)

    legacy_queries_path.write_text("\n".join(training_queries) + "\n", encoding="utf-8")

    print(
        {
            "seeds_output_path": str(seeds_path),
            "legacy_queries_output_path": str(legacy_queries_path),
            **build_seed_catalog_summary(seed_rows),
        }
    )


if __name__ == "__main__":
    main()
