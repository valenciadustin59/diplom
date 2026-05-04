# D75 Dataset-v7 Controlled Collection Start

Status: `collection_started`.

D75 started the real `dataset-v7-final` top-10 collection path with the D69 domain cap enabled. This is a controlled first batch, not a completed dataset and not a model publish.

## Commands

```powershell
backend\.venv\Scripts\python.exe -m app.ml.dataset_builder --versioned-layout --dataset-version dataset-v7-final --max-domain-rows-per-domain 12 --max-workers 3 --query-delay 0.2 --seed-offset 0 --seed-limit 3
backend\.venv\Scripts\python.exe -m app.ml.dataset_builder --versioned-layout --dataset-version dataset-v7-final --max-domain-rows-per-domain 12 --max-workers 3 --query-delay 0.2 --seed-offset 3 --seed-limit 7
```

## Current Coverage

- Seed queries: `500`.
- Collected queries: `10`.
- Successful rows: `80`.
- Failures: `6`.
- Unique domains: `64`.
- Saved extraction snapshots: `80`.
- Failure rate: `0.069767`.
- Empty text rate: `0.0`.
- Domain cap: `12`.
- Domain cap skipped rows: `0`.
- Max rows for a single domain so far: `7`.

## Important Notes

- `dataset.csv` is currently a raw collection surface. Its weak label columns are collection-time placeholders from the generic builder and must not be used as final `dataset-v7-final` labels.
- `manifest.json` remains `ready_for_training=false`.
- Final training still requires the remaining seed collection, deterministic expert-rubric labels, hard-negative materialization, split validation and controlled publish decision.
- No runtime model artifact was replaced, no rollback was executed and product scoring was not changed.

## Continue Command

For the next batch, continue with a later offset and the same cap:

```powershell
backend\.venv\Scripts\python.exe -m app.ml.dataset_builder --versioned-layout --dataset-version dataset-v7-final --max-domain-rows-per-domain 12 --max-workers 3 --query-delay 0.2 --seed-offset 10 --seed-limit 20
```
