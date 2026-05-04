# D77 Dataset-v7 Deterministic Labels

## Goal

Materialize final deterministic expert-rubric labels for `dataset-v7-final` before split validation and training. D77 labels the hard-negative training surface, not the raw collection-only `dataset.csv`.

## Inputs

- `backend/data/dataset_versions/dataset-v7-final/dataset.with-hard-negatives.csv`
- D75 raw snapshots and D76 hard-negative rows
- `query-competitiveness-final-v2` score contract
- `query-competitiveness-rubric-v1` label schema

## Output Evidence

D77 generated:

- `backend/data/dataset_versions/dataset-v7-final/dataset.labeled.csv`
- `backend/data/dataset_versions/dataset-v7-final/d77-final-label-report.json`
- `backend/data/dataset_versions/dataset-v7-final/d77-final-label-report.md`

Final counts:

- rows: `4876`
- regular rows: `3876`
- hard negatives: `1000`
- label source: `deterministic_expert_rubric_v7`
- score contract: `query-competitiveness-final-v2`
- label schema: `query-competitiveness-rubric-v1`

## Hard-Negative Cap

D77 adds a deterministic hard-negative score cap to prevent a technically polished page from a different topic from receiving a convincing score for the wrong query.

- hard-negative cap: `35.0`
- cap applications: `192`
- hard negatives above cap: `0`

Hard-negative score distribution after labeling:

- min: `0.4081`
- p25: `2.9563`
- p50: `17.4971`
- p75: `32.4512`
- p90: `35.0`
- max: `35.0`

## Dataset Status

`manifest.json` status is now `deterministic_labels_materialized`.

`ready_for_training=false` remains intentional. D78 must create and validate the leakage-safe train/validation split before any training task can proceed.

## Verification

Targeted checks:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_final_query_competitiveness.py backend/tests/test_final_hard_negatives.py backend/tests/test_training_pipeline.py::test_build_dataset_enforces_domain_cap_before_parallel_fetch -q
backend\.venv\Scripts\python.exe -m py_compile backend\app\ml\final_query_competitiveness.py
backend\.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --validate
```

D77 does not train, publish, roll back or replace `backend/artifacts/page_quality_model.pkl`.
