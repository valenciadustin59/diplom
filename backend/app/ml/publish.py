from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any

from app.ml.dataset_quality import default_manifest_path
from app.ml.model import DEFAULT_MODEL_PATH
from app.ml.train import train_quality_model


BACKEND_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BACKEND_DIR / "data"
DEFAULT_PRIMARY_DATASET_PATH = DATA_DIR / "ru_commercial_dataset.csv"
DEFAULT_PRIMARY_MANIFEST_PATH = DATA_DIR / "ru_commercial_dataset.manifest.json"


def load_training_manifest(manifest_path: str | Path = DEFAULT_PRIMARY_MANIFEST_PATH) -> dict[str, Any]:
    resolved_path = Path(manifest_path)
    if not resolved_path.exists():
        raise FileNotFoundError(f"Training manifest not found: {resolved_path}")
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Training manifest must be a JSON object")
    return payload


def ensure_manifest_ready(manifest: dict[str, Any]) -> None:
    quality_gates = manifest.get("quality_gates")
    if not isinstance(quality_gates, dict):
        raise ValueError("Training manifest does not contain quality_gates")
    if bool(quality_gates.get("ready_for_training")):
        return

    unmet = quality_gates.get("unmet_requirements")
    if isinstance(unmet, list) and unmet:
        requirements = ", ".join(str(item) for item in unmet)
        raise ValueError(f"Dataset is not ready for training: {requirements}")
    raise ValueError("Dataset is not ready for training")


def build_primary_dataset_version(dataset_path: str | Path, manifest: dict[str, Any]) -> str:
    resolved_dataset_path = Path(dataset_path)
    generated_at_raw = str(manifest.get("generated_at") or "")
    generated_at = datetime.fromisoformat(generated_at_raw) if generated_at_raw else None
    version_suffix = generated_at.strftime("%Y%m%d") if generated_at is not None else "undated"
    return f"{resolved_dataset_path.stem}-{version_suffix}-primary"


def publish_primary_model(
    dataset_path: str | Path = DEFAULT_PRIMARY_DATASET_PATH,
    manifest_path: str | Path | None = None,
    model_path: str | Path = DEFAULT_MODEL_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    resolved_dataset_path = Path(dataset_path)
    resolved_manifest_path = Path(manifest_path) if manifest_path is not None else default_manifest_path(resolved_dataset_path)
    manifest = load_training_manifest(resolved_manifest_path)
    ensure_manifest_ready(manifest)

    dataset_version = build_primary_dataset_version(resolved_dataset_path, manifest)
    training_result = train_quality_model(
        dataset_path=resolved_dataset_path,
        model_path=model_path,
        test_size=test_size,
        random_state=random_state,
        dataset_version=dataset_version,
    )
    return {
        **training_result,
        "manifest_path": str(resolved_manifest_path),
        "published_model_path": str(Path(model_path)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DEFAULT_PRIMARY_DATASET_PATH))
    parser.add_argument("--manifest", default=str(DEFAULT_PRIMARY_MANIFEST_PATH))
    parser.add_argument("--model-output", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    result = publish_primary_model(
        dataset_path=args.dataset,
        manifest_path=args.manifest,
        model_path=args.model_output,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
