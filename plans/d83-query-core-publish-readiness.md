# D83: Query-Core Controlled Publish

Status: completed locally.

## Goal

Prepare and execute the controlled publish of the D82 query-core candidate.

D82 fixed the D80 hard-negative blocker, but one deployment gap remained: the existing controlled publish path still targeted the old D80/D81 v3 candidate. It expected schema `v3` and read `D80_REPORT_JSON_PATH`, so it could not safely publish the D82 schema `v4` artifact.

## Gaps Found

- D82 decision said `publish_candidate`, but `--publish` still used the old D80/D81 route.
- `run_final_controlled_publish` was hard-coded to expect `MODEL_SCHEMA_VERSION_V3`.
- Release metadata was named around D80/D81, making D82 deployment ambiguous.
- There was no explicit readiness report checking that the current production SHA still matches the D82 reference SHA before publish.

## Fixes

- Generalized `run_final_controlled_publish` so it can publish either the old D81 v3 flow or the D83/D82 query-core v4 flow with explicit parameters.
- Added `build_query_core_publish_readiness_report`.
- Added CLI command:

```powershell
cd E:\codexPROJ\diplom
backend\.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --prepare-query-core-publish
```

- Added separate controlled publish command for the query-core candidate:

```powershell
cd E:\codexPROJ\diplom
backend\.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --publish-query-core
```

D83 originally added the explicit publish path; after user approval, `--publish-query-core` was executed and the query-core candidate became the active runtime artifact.

## Evidence

Readiness report:

- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d83/d83-query-core-publish-readiness-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d83/d83-query-core-publish-readiness-report.md`

Controlled release report:

- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d83/d83-query-core-controlled-release-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d83/d83-query-core-controlled-release-report.md`

Readiness result:

- `ready_for_controlled_publish=true`
- failed checks: `none`
- candidate SHA1: `2bbf84bfcc77662d66f62cfdafbb6ee4d8264e88`
- production SHA1: `5374ca30f48f70d8629e7d84ec3df0524ef35b52`
- schema: `v4`
- feature count: `156`
- candidate load smoke: passed
- production still matches the D82 reference SHA before publish.

Release result:

- `decision=published`
- publish action: `controlled_publish`
- production SHA1 before: `5374ca30f48f70d8629e7d84ec3df0524ef35b52`
- production SHA1 after: `da285ca34d8c19079373b1db86d818355c7b80e0`
- active dataset: `dataset-v7-final`
- active artifact: `dataset-v7-final-20260505125858`
- active model: `QueryCoreGuardrailCatBoostRegressor`
- schema: `v4`
- feature count: `156`
- rollback artifact: `backend/artifacts/versions/page_quality_model--dataset-v5-20260502151507.pkl`

## Verification

Passed:

```powershell
backend\.venv\Scripts\python.exe -m py_compile backend\app\ml\final_query_competitiveness.py backend\app\ml\model_schema.py backend\app\ml\query_core_model.py backend\app\features.py
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_final_query_competitiveness.py::test_d82_query_core_candidate_passes_hard_negative_guardrail backend\tests\test_final_query_competitiveness.py::test_d83_query_core_publish_readiness_is_green_without_runtime_mutation backend\tests\test_model_schema.py::test_model_schema_v4_extends_v3_with_query_core_features -q -p no:cacheprovider
```

Additional post-publish verification:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_competitors.py backend\tests\test_competitiveness_score.py backend\tests\test_query_relevance_runtime.py backend\tests\test_final_query_competitiveness.py backend\tests\test_model_schema.py -q -p no:cacheprovider
npm --prefix frontend run test -- --run
npm --prefix frontend run build
node scripts/d31-runtime-smoke.mjs
```

Runtime smoke evidence:

- `output/runtime-smoke/d83-query-core-smoke-final.json`
- audit `7a3a91ba-2279-4646-aa4e-88ea9b66e201`
- readiness `ready`, `4` workers, missing queues `[]`
- runtime model `dataset-v7-final` / schema `v4`
- `competitor_page` fan-out dispatch/terminal `2/2`
- completed with warnings because only `1/2` competitor pages was processed; UI shows competitor average/difference as `—`, not fake `0`.

## Current State

The D82 query-core candidate is now the active runtime model. The D58 `dataset-v5` artifact is preserved as rollback evidence.
