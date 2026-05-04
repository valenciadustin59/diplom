# D78 Dataset-v7 Split Validation

## Goal

Create the final leakage-safe train/validation split for `dataset-v7-final` after D77 deterministic labels. D78 must make the dataset ready for D79 training without training or publishing a model.

## Input

- `backend/data/dataset_versions/dataset-v7-final/dataset.labeled.csv`
- `query-competitiveness-rubric-v1` labels from D77
- `query-competitiveness-final-v2` score contract

## Output Evidence

D78 generated:

- `backend/data/dataset_versions/dataset-v7-final/split.json`
- `backend/data/dataset_versions/dataset-v7-final/d78-split-validation-report.json`
- `backend/data/dataset_versions/dataset-v7-final/d78-split-validation-report.md`

## Split Policy

The split mode is `group_by_query_category_stratified`.

This keeps all rows for the same query in one partition and samples validation queries per category. The purpose is to avoid query leakage while keeping all major categories represented in validation.

Final split:

- train rows: `3898`
- validation rows: `978`
- train queries: `400`
- validation queries: `100`
- query overlap: `0`
- categories in validation: `50/50`
- non-empty cities in validation: `5/5`
- hard negatives in train: `800`
- hard negatives in validation: `200`
- hard negatives above cap: `0`

## Manifest Status

`manifest.json` is now:

- `status=split_validated`
- `ready_for_training=true`

This means the dataset can move to D79 candidate training. It does not mean a model has been trained or published.

## Verification

Targeted checks:

```powershell
backend\.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --split
backend\.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --validate
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_final_query_competitiveness.py backend/tests/test_final_hard_negatives.py backend/tests/test_training_pipeline.py::test_build_dataset_enforces_domain_cap_before_parallel_fetch -q
backend\.venv\Scripts\python.exe -m py_compile backend\app\ml\final_query_competitiveness.py
```

D78 does not train, publish, roll back or replace `backend/artifacts/page_quality_model.pkl`.
