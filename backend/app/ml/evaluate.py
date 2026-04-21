from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.ml.dataset_builder import DEFAULT_DATASET_PATH
from app.ml.model import DEFAULT_MODEL_PATH, load_model_artifact
from app.ml.train import (
    load_dataset_rows,
    select_best_candidate,
    split_dataset_rows,
    train_candidate_models,
    evaluate_model_rows,
)


def evaluate_candidate_models(
    dataset_path: str | Path = DEFAULT_DATASET_PATH,
    reference_model_path: str | Path | None = DEFAULT_MODEL_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    rows = load_dataset_rows(dataset_path)
    if len(rows) < 4:
        raise ValueError("At least 4 dataset rows are required for offline evaluation")

    train_rows, validation_rows, split_metadata = split_dataset_rows(
        rows,
        test_size=test_size,
        random_state=random_state,
    )
    if not train_rows or not validation_rows:
        raise ValueError("Offline evaluation split produced an empty train or validation set")

    candidates, benchmark = train_candidate_models(
        train_rows,
        validation_rows,
        random_state=random_state,
    )
    best_candidate = select_best_candidate(candidates)

    reference: dict[str, Any] | None = None
    if reference_model_path is not None:
        artifact = load_model_artifact(reference_model_path)
        if artifact is not None:
            reference = {
                "model_path": str(Path(reference_model_path)),
                "model_info": {
                    "source": artifact.get("source", "unknown"),
                    "model_type": artifact.get("model_type", artifact["model"].__class__.__name__),
                    "trained_at": artifact.get("trained_at"),
                    "dataset_rows": int(artifact.get("rows_count") or 0),
                    "dataset_version": artifact.get("dataset_version"),
                },
                "metrics": {
                    **evaluate_model_rows(artifact["model"], validation_rows),
                    **split_metadata,
                },
            }

    return {
        "dataset_path": str(Path(dataset_path)),
        "rows_count": len(rows),
        "queries_count": len({str(row.get("query") or "") for row in rows}),
        "domains_count": len({str(row.get("domain") or "") for row in rows}),
        "train_rows": len(train_rows),
        "validation_rows": len(validation_rows),
        "split": split_metadata,
        "candidates": [
            {
                "model_type": str(candidate["model_type"]),
                "metrics": {
                    **candidate["metrics"],
                    **split_metadata,
                },
            }
            for candidate in candidates
        ],
        "best_candidate": {
            "model_type": str(best_candidate["model_type"]),
            "metrics": {
                **best_candidate["metrics"],
                **split_metadata,
            },
        },
        "benchmark": benchmark,
        "reference_model": reference,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET_PATH))
    parser.add_argument("--reference-model", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--without-reference-model", action="store_true")
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = evaluate_candidate_models(
        dataset_path=args.dataset,
        reference_model_path=None if args.without_reference_model else args.reference_model,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
