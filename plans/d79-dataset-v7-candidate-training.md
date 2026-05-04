# D79 Dataset-v7 Candidate Training

## Goal

Train the final query-competitiveness candidate from the D77 labels and D78 leakage-safe split. D79 is training only: it must not publish, roll back or replace the runtime model.

## Inputs

- `backend/data/dataset_versions/dataset-v7-final/dataset.labeled.csv`
- `backend/data/dataset_versions/dataset-v7-final/split.json`
- `query-competitiveness-final-v2`
- `query-competitiveness-rubric-v1`
- model schema `v3` with `148` features

## Output Evidence

D79 generated:

- `backend/artifacts/page_quality_model.dataset-v7-final-candidate.pkl`
- `backend/artifacts/page_quality_model.dataset-v7-final-candidate.pkl.metadata.json`
- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d79/d79-candidate-training-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d79/d79-candidate-training-report.md`

## Candidate

- candidate name: `final_query_competitiveness_catboost_v7`
- model type: `CatBoostRegressor`
- artifact SHA1: `65c30b2611e6cde393fae52d1f820a00e7d42681`
- schema: `v3`
- feature count: `148`
- non-production: `true`
- runtime enabled: `false`

## Validation Metrics

On the D78 validation split:

- MAE: `1.699042`
- RMSE: `2.584978`
- Spearman: `0.929238`
- NDCG@10: `0.996686`
- Top-3 diagnostic: `0.91`
- validation queries: `100`

The RandomForest baseline was also trained for comparison and had `MAE=1.755365`, `Spearman=0.918959`, `NDCG@10=0.996646`, `top_3_hit_rate=0.9`.

## Feature Importance

Top features for the selected CatBoost candidate:

- `keyword_coverage_ratio`
- `query_prominence_score`
- `page_indexable`
- `keyword_balance_score`
- `early_query_coverage_ratio`
- `query_term_count`
- `query_density`
- `semantic_content_richness`
- `heading_semantic_alignment`
- `query_semantic_alignment`

This is directionally consistent with the final product goal: query fit and page availability dominate generic page-size signals.

## Runtime Status

D79 did not change `backend/artifacts/page_quality_model.pkl`.

Current production SHA1 remains `5374ca30f48f70d8629e7d84ec3df0524ef35b52`.

## Verification

```powershell
backend\.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --train
backend\.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --validate
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_final_query_competitiveness.py backend/tests/test_final_hard_negatives.py backend/tests/test_final_query_catalog.py backend/tests/test_training_pipeline.py::test_build_dataset_enforces_domain_cap_before_parallel_fetch -q
backend\.venv\Scripts\python.exe -m py_compile backend\app\ml\final_query_competitiveness.py
```

D80 must run product guardrails / controlled decision before any publish.
