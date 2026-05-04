# D69 Dataset-v7 Final Collection Readiness

## Goal

Prepare the real `dataset-v7-final` collection path so the final query-competitiveness model is trained on fresh top-10 evidence, not on repeated domains or synthetic-only examples.

## Implemented

- `app.ml.dataset_builder` now supports `--max-domain-rows-per-domain`.
- The domain cap is enforced before parallel page fetch, so repeated domains are not over-scheduled during the same SERP page batch.
- Existing collected rows are counted on resume, so interrupted collection continues respecting the same cap.
- Dataset metadata now records `collection_policy.max_domain_rows_per_domain` and `domain_cap_skipped_count`.
- `app.ml.final_hard_negatives` materializes hard negatives from saved snapshot artifacts:
  - keeps original collected rows;
  - clones pages from other categories under a target query;
  - recomputes query-dependent features against the new query;
  - writes `dataset.with-hard-negatives.csv`;
  - writes `d69-hard-negatives-report.json`.
- `app.ml.final_query_competitiveness` now blocks final training until hard negatives are materialized when the manifest requires them.

## Collection Commands

From repo root:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.dataset_builder --versioned-layout --dataset-version dataset-v7-final --max-domain-rows-per-domain 12 --max-workers 6 --query-delay 1.0
```

After collection completes and `manifest.json` is marked `ready_for_training=true`:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.final_hard_negatives --max-negatives-per-query 2
.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --validate
.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --train
.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --decide
```

Publish remains controlled and must only run after the decision report says `publish_candidate`:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --publish
```

## Verification

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_training_pipeline.py::test_build_dataset_enforces_domain_cap_before_parallel_fetch backend/tests/test_final_hard_negatives.py backend/tests/test_final_query_competitiveness.py -q
```

Current targeted result: `6 passed`.

## Notes

- `dataset-v7-final/dataset.csv` is still not collected in this task.
- Full collection is intentionally a long live-network job: around `500` queries times `top-10` pages before failures and hard negatives.
- `dataset-v6-query-relevance` remains draft evidence only.
