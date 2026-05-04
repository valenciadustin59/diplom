# D75 Dataset-v7 Controlled Collection

## Goal

Collect the real `dataset-v7-final` raw evidence for the final query-competitiveness model. The purpose is to gather fresh top-10 page evidence for the new relevance-first scoring direction without training or publishing a model from incomplete data.

## Current Status

Status: `raw_collection_completed`.

D75 completed the raw collection pass:

- `500/500` seed queries have at least one successful row after the repair pass.
- `3876` successful rows.
- `367` failures.
- `2253` unique domains.
- `50` categories.
- `5` cities.
- `3876` extraction snapshot artifacts.
- Highest domain repeat count: `12`, matching the D69 cap.

Evidence:

- `backend/data/dataset_versions/dataset-v7-final/dataset.csv`
- `backend/data/dataset_versions/dataset-v7-final/failures.csv`
- `backend/data/dataset_versions/dataset-v7-final/checkpoint.json`
- `backend/data/dataset_versions/dataset-v7-final/dataset.dataset.json`
- `backend/data/dataset_versions/dataset-v7-final/artifacts/`
- `backend/data/dataset_versions/dataset-v7-final/d75-collection-progress.json`
- `backend/data/dataset_versions/dataset-v7-final/d75-collection-progress.md`
- `backend/data/dataset_versions/dataset-v7-final/d75-repair-seeds.csv`
- `backend/data/dataset_versions/dataset-v7-final/d75-repair.checkpoint.json`

## Commands Used

```powershell
backend\.venv\Scripts\python.exe -m app.ml.dataset_builder --versioned-layout --dataset-version dataset-v7-final --max-domain-rows-per-domain 12 --max-workers 3 --query-delay 0.2 --seed-offset 0 --seed-limit 3
backend\.venv\Scripts\python.exe -m app.ml.dataset_builder --versioned-layout --dataset-version dataset-v7-final --max-domain-rows-per-domain 12 --max-workers 3 --query-delay 0.2 --seed-offset 3 --seed-limit 7
scripts\run_d75_collection.ps1 -StartOffset 135 -EndOffset 500 -BatchSize 25 -MaxWorkers 4 -QueryDelay 0.2 -DomainCap 12
backend\.venv\Scripts\python.exe -m app.ml.dataset_builder --dataset-version dataset-v7-final --seeds-file backend\data\dataset_versions\dataset-v7-final\d75-repair-seeds.csv --output backend\data\dataset_versions\dataset-v7-final\dataset.csv --failures-output backend\data\dataset_versions\dataset-v7-final\failures.csv --checkpoint backend\data\dataset_versions\dataset-v7-final\d75-repair.checkpoint.json --artifacts-dir backend\data\dataset_versions\dataset-v7-final\artifacts --max-domain-rows-per-domain 12 --max-workers 4 --query-delay 0.2
```

## Policy

- Keep `manifest.json` as `ready_for_training=false` until deterministic labels, hard negatives and split validation are complete.
- Treat the current `target_score`/weak-label columns in `dataset.csv` as placeholders only.
- Do not train, publish, roll back or mutate `backend/artifacts/page_quality_model.pkl` during collection.
- Keep snapshot artifacts local/generated; they are large raw evidence and are not part of the user-facing product UI.

## Next Steps

1. Materialize hard negatives from saved snapshots.
2. Replace placeholder labels with deterministic expert-rubric labels.
3. Validate no query leakage and no harmful domain concentration.
4. Only then run final training/benchmark/publish decision.
