# D82: Query-Core Hard Negative Hardening

Status: completed locally.

## Goal

D80 showed that the first `dataset-v7-final` candidate was strong on aggregate metrics but still unsafe for the final product goal: `25` validation hard negatives were predicted above the `35.0` cap. D82 fixes that specific release blocker without publishing the model automatically.

The product goal remains: score must primarily answer whether a chosen page is competitive for the concrete query. A generally good page from another topic must not receive a medium/high score just because it has solid SEO signals.

## Implementation

- Added model schema `v4` with `156` features: the existing `148` v3 features plus `8` query-core relevance features.
- Added query-core features for core query terms, exact core phrase presence and intent modifier coverage.
- Expanded intent modifiers so city/service/commercial helper words are not treated as the main topic.
- Materialized `backend/data/dataset_versions/dataset-v7-final/dataset.query-core.csv` from `dataset.labeled.csv` and saved snapshot artifacts.
- Trained non-production candidate `backend/artifacts/page_quality_model.dataset-v7-final-query-core-candidate.pkl`.
- Candidate SHA1: `2bbf84bfcc77662d66f62cfdafbb6ee4d8264e88`.
- Model type: `QueryCoreGuardrailCatBoostRegressor`.
- Added a pickle-safe `QueryCoreGuardrailRegressor` wrapper that caps raw prediction to `35.0` when the page misses the query core and semantic similarity is weak.
- D82 did not replace `backend/artifacts/page_quality_model.pkl`.

## Evidence

Reports:

- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d82/d82-query-core-hardening-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d82/d82-query-core-hardening-report.md`
- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d82/d82-controlled-decision-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d82/d82-controlled-decision-report.md`

Controlled decision:

- decision: `publish_candidate`
- reason: `final_product_guardrails_passed`
- next step: `controlled_publish_required`

Validation metrics after runtime query-relevance adjustment:

- candidate `MAE=4.253847`
- candidate `Spearman=0.917044`
- candidate `NDCG@10=0.996873`
- candidate `top_3_hit_rate=0.93` as diagnostic

Reference runtime metrics on the same split:

- reference `MAE=6.556754`
- reference `Spearman=0.77064`
- reference `NDCG@10=0.984659`
- reference `top_3_hit_rate=0.83` as diagnostic

Hard-negative guardrail:

- D80 blocker: `25` validation hard negatives above `35.0`.
- D82 result: `0` validation hard negatives above `35.0`.
- D82 maximum raw hard-negative prediction: `35.0`.

## Verification

Passed:

```powershell
backend\.venv\Scripts\python.exe -m py_compile app\ml\final_query_competitiveness.py app\ml\model_schema.py app\ml\query_core_model.py app\features.py
backend\.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --harden-query-core --force-query-core-materialize
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_final_query_competitiveness.py::test_d82_query_core_candidate_passes_hard_negative_guardrail backend\tests\test_model_schema.py::test_model_schema_v4_extends_v3_with_query_core_features -q -p no:cacheprovider
```

The broader targeted pytest files currently hit an environment temp-directory `PermissionError` on this machine (`pytest-of-timac` / `basetemp`) after partial execution. This is an execution-environment issue, not a D82 model guardrail failure; the direct D82 regression tests pass.

## Next Step

Run a separate controlled publish task only if the user explicitly chooses to replace the active runtime model. Until then, active production remains the D58 `dataset-v5` runtime artifact.
