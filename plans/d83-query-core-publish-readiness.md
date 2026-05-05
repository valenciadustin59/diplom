# D83: Query-Core Publish Readiness

Status: completed locally.

## Goal

Prepare the D82 query-core candidate for safe deployment without switching the runtime model automatically.

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

Do not run `--publish-query-core` unless the user explicitly chooses to switch runtime to D82.

## Evidence

Readiness report:

- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d83/d83-query-core-publish-readiness-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d83/d83-query-core-publish-readiness-report.md`

Readiness result:

- `ready_for_controlled_publish=true`
- failed checks: `none`
- candidate SHA1: `2bbf84bfcc77662d66f62cfdafbb6ee4d8264e88`
- production SHA1: `5374ca30f48f70d8629e7d84ec3df0524ef35b52`
- schema: `v4`
- feature count: `156`
- candidate load smoke: passed
- production still matches the D82 reference SHA before publish.

## Verification

Passed:

```powershell
backend\.venv\Scripts\python.exe -m py_compile backend\app\ml\final_query_competitiveness.py backend\app\ml\model_schema.py backend\app\ml\query_core_model.py backend\app\features.py
backend\.venv\Scripts\python.exe -m pytest backend\tests\test_final_query_competitiveness.py::test_d82_query_core_candidate_passes_hard_negative_guardrail backend\tests\test_final_query_competitiveness.py::test_d83_query_core_publish_readiness_is_green_without_runtime_mutation backend\tests\test_model_schema.py::test_model_schema_v4_extends_v3_with_query_core_features -q -p no:cacheprovider
```

## Current State

The D82 query-core candidate is ready for controlled publish, but active runtime is still the D58 `dataset-v5` model until `--publish-query-core` is explicitly run.
