# D75 Dataset-v7 Controlled Collection

## Goal

Start the real `dataset-v7-final` collection for the final query-competitiveness model. The purpose is to gather fresh top-10 page evidence for the new relevance-first scoring direction without training or publishing a model from incomplete data.

## Current Status

Status: `collection_started`.

D75 has started with a controlled first batch:

- `10/500` seed queries collected.
- `80` successful rows.
- `6` failures.
- `64` unique domains.
- `80` extraction snapshot artifacts.
- `0` domain-cap skips.
- Highest domain repeat count so far: `7`, below the D69 cap of `12`.

Evidence:

- `backend/data/dataset_versions/dataset-v7-final/dataset.csv`
- `backend/data/dataset_versions/dataset-v7-final/failures.csv`
- `backend/data/dataset_versions/dataset-v7-final/checkpoint.json`
- `backend/data/dataset_versions/dataset-v7-final/dataset.dataset.json`
- `backend/data/dataset_versions/dataset-v7-final/artifacts/`
- `backend/data/dataset_versions/dataset-v7-final/d75-collection-progress.json`
- `backend/data/dataset_versions/dataset-v7-final/d75-collection-progress.md`

## Commands Used

```powershell
backend\.venv\Scripts\python.exe -m app.ml.dataset_builder --versioned-layout --dataset-version dataset-v7-final --max-domain-rows-per-domain 12 --max-workers 3 --query-delay 0.2 --seed-offset 0 --seed-limit 3
backend\.venv\Scripts\python.exe -m app.ml.dataset_builder --versioned-layout --dataset-version dataset-v7-final --max-domain-rows-per-domain 12 --max-workers 3 --query-delay 0.2 --seed-offset 3 --seed-limit 7
```

## Policy

- Keep `manifest.json` as `ready_for_training=false` until collection and labels are complete.
- Treat the current `target_score`/weak-label columns in `dataset.csv` as placeholders only.
- Do not train, publish, roll back or mutate `backend/artifacts/page_quality_model.pkl` during collection.
- Continue collection with checkpoint/resume and the same `--max-domain-rows-per-domain 12` cap.

## Next Steps

1. Continue collection in resumable batches from `--seed-offset 10`.
2. Watch failure rate, empty text rate and domain repeat count after each batch.
3. After all seeds are collected, materialize hard negatives from saved snapshots.
4. Replace placeholder labels with deterministic expert-rubric labels.
5. Validate no query leakage and no harmful domain concentration.
6. Only then run final training/benchmark/publish decision.
