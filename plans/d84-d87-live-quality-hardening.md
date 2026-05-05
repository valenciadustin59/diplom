# D84-D87: Live Quality Hardening After Query-Core Publish

Status: completed locally.

## Goal

After D83 made the `dataset-v7-final` query-core artifact active, this wave adds product-quality guardrails around the two practical risks that remain in live use:

- relevance mistakes for fresh queries that were not part of the training discussion;
- misleading competitor comparison when pages from the search results are blocked or only partially processed.

No retraining, rollback or publish was performed in this wave.

## D84: Live Relevance Regression Pack

Added a deterministic regression pack for the active query relevance contract.

Evidence:

- cases: `backend/data/query_relevance_regression/d84-live-regression-cases.json`
- report: `backend/artifacts/ranking-benchmarks/dataset-v7-final-d84/d84-live-relevance-regression-report.json`
- markdown: `backend/artifacts/ranking-benchmarks/dataset-v7-final-d84/d84-live-relevance-regression-report.md`

Result:

- `40` fresh cases
- `6` risk groups
- `0` failed cases
- groups: strong match, commercial modifier not required when core matches, full mismatch, near-topic wrong object, partial match, unusable page

## D85: Competitor Fetch Robustness

Added explicit competitor context quality to the backend comparison summary.

New summary fields:

- `competitor_context_status`
- `competitor_context_quality`

Statuses:

- `ready`
- `partial_but_usable`
- `insufficient_processed_competitors`
- `no_serp_results`

The system no longer exposes a fake competitor average or market difference when fewer than two competitors are processed.

Evidence:

- report: `backend/artifacts/ranking-benchmarks/dataset-v7-final-d85/d85-competitor-fetch-robustness-report.json`
- markdown: `backend/artifacts/ranking-benchmarks/dataset-v7-final-d85/d85-competitor-fetch-robustness-report.md`

Result:

- `5` robustness scenarios
- `0` failed cases

## D86: UX Score Contract Polish

Updated the audit overview copy so the product explains the score without ML/debug wording:

1. first, the page must match the query;
2. then the page quality and completeness matter;
3. for commercial queries, action/trust signals matter;
4. competitor context is used only when enough search-result pages were processed.

The UI now tells the user when market comparison is unavailable because competitor context is insufficient.

## D87: Diploma Evidence Report

Added a single report that links active runtime, controlled publish evidence and the new post-publish guardrails.

Evidence:

- report: `backend/artifacts/ranking-benchmarks/dataset-v7-final-d87/d87-diploma-evidence-report.json`
- markdown: `backend/artifacts/ranking-benchmarks/dataset-v7-final-d87/d87-diploma-evidence-report.md`

Result:

- decision: `ready_for_diploma_evidence_pack`
- active runtime: `dataset-v7-final` / schema `v4` / `QueryCoreGuardrailCatBoostRegressor`
- active SHA1: `da285ca34d8c19079373b1db86d818355c7b80e0`

## Verification

Passed:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.live_relevance_regression
.venv\Scripts\python.exe -m app.ml.competitor_fetch_robustness
.venv\Scripts\python.exe -m app.ml.diploma_evidence_report
.venv\Scripts\python.exe -m pytest tests\test_live_relevance_regression.py tests\test_query_relevance_runtime.py tests\test_final_query_competitiveness.py -q -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests\test_competitiveness_score.py tests\test_competitors.py tests\test_competitor_fetch_robustness.py -q -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests\test_diploma_evidence_report.py tests\test_live_relevance_regression.py tests\test_competitor_fetch_robustness.py -q -p no:cacheprovider
```

```powershell
npm --prefix frontend run test -- --run src/lib/ui.test.tsx src/lib/auditReport.test.ts
npm --prefix frontend run build
```
