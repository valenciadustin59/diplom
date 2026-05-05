# D87 Diploma Evidence Report

- Status: `passed`
- Decision: `ready_for_diploma_evidence_pack`
- Active model: `dataset-v7-final` / `v4` / `QueryCoreGuardrailCatBoostRegressor`
- Active SHA1: `da285ca34d8c19079373b1db86d818355c7b80e0`

## Evidence

- D83 controlled publish: `published` at `backend\artifacts\ranking-benchmarks\dataset-v7-final-d83\d83-query-core-controlled-release-report.json`
- D84 query relevance regression: `passed`, `40` cases, `0` failed
- D85 competitor fetch robustness: `passed`, `5` cases, `0` failed

## Product Definition

The product evaluates whether a chosen page can compete for a concrete search query: query relevance is checked first, then page quality and competitor context are used when enough SERP pages are processed.

## Verification Commands

- `cd backend && .venv\Scripts\python.exe -m pytest tests\test_live_relevance_regression.py tests\test_query_relevance_runtime.py tests\test_final_query_competitiveness.py -q -p no:cacheprovider`
- `cd backend && .venv\Scripts\python.exe -m pytest tests\test_competitiveness_score.py tests\test_competitors.py tests\test_competitor_fetch_robustness.py -q -p no:cacheprovider`
- `npm --prefix frontend run test -- --run src/lib/ui.test.tsx src/lib/auditReport.test.ts`
- `npm --prefix frontend run build`
