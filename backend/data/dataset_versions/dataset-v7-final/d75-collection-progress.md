# D75 Dataset-v7 Controlled Collection

Status: `raw_collection_completed`.

D75 completed the real `dataset-v7-final` top-10 raw collection path with the D69 domain cap enabled. This is raw collection evidence, not a final labeled training dataset and not a model publish.

## Commands

```powershell
backend\.venv\Scripts\python.exe -m app.ml.dataset_builder --versioned-layout --dataset-version dataset-v7-final --max-domain-rows-per-domain 12 --max-workers 3 --query-delay 0.2 --seed-offset 0 --seed-limit 3
backend\.venv\Scripts\python.exe -m app.ml.dataset_builder --versioned-layout --dataset-version dataset-v7-final --max-domain-rows-per-domain 12 --max-workers 3 --query-delay 0.2 --seed-offset 3 --seed-limit 7
scripts\run_d75_collection.ps1 -StartOffset 135 -EndOffset 500 -BatchSize 25 -MaxWorkers 4 -QueryDelay 0.2 -DomainCap 12
backend\.venv\Scripts\python.exe -m app.ml.dataset_builder --dataset-version dataset-v7-final --seeds-file backend\data\dataset_versions\dataset-v7-final\d75-repair-seeds.csv --output backend\data\dataset_versions\dataset-v7-final\dataset.csv --failures-output backend\data\dataset_versions\dataset-v7-final\failures.csv --checkpoint backend\data\dataset_versions\dataset-v7-final\d75-repair.checkpoint.json --artifacts-dir backend\data\dataset_versions\dataset-v7-final\artifacts --max-domain-rows-per-domain 12 --max-workers 4 --query-delay 0.2
```

## Final Raw Coverage

- Seed queries: `500`.
- Queries with successful rows: `500`.
- Successful rows: `3876`.
- Failures: `367`.
- Unique domains: `2253`.
- Categories: `50`.
- Cities: `5`.
- Saved extraction snapshots: `3876`.
- Failure rate: `0.086495`.
- Empty text rate: `0.0`.
- Domain cap: `12`.
- Max rows for a single domain: `12`.
- Main checkpoint completed pages: `500`.
- Repair checkpoint completed pages: `61`.

## Important Notes

- `dataset.csv` is a raw collection surface. Its weak label columns are collection-time placeholders from the generic builder and must not be used as final `dataset-v7-final` labels.
- `manifest.json` remains `ready_for_training=false`.
- Final training still requires deterministic expert-rubric labels, hard-negative materialization, split validation and controlled publish decision.
- No runtime model artifact was replaced, no rollback was executed and product scoring was not changed.
