# D88-D96: RoSBERTa Semantic Runtime And Competitor Context Quality

Status: D88-D96 implemented locally.

## Goal

Improve query relevance for the Russian segment and make the distributed runtime clearly carry the heavier semantic workload. The active page-quality artifact is not retrained or replaced in this wave. The change affects semantic feature extraction, relevance calibration, competitor selection quality and worker topology.

## D88: RoSBERTa Semantic Provider

Implemented:

- added provider abstraction in `backend/app/semantic_providers.py`;
- added config settings in `backend/app/config.py`;
- default provider can use `ai-forever/ru-en-RoSBERTa`;
- fallback remains available through the previous MiniLM multilingual model;
- `backend/app/semantic.py` records provider/model metadata and keeps the existing feature contract compatible.

Important env knobs:

- `SEMANTIC_PROVIDER`;
- `SEMANTIC_MODEL_NAME`;
- `SEMANTIC_FALLBACK_MODEL_NAME`;
- `SEMANTIC_MAX_TEXT_CHARS`;
- `SEMANTIC_BATCH_SIZE`.

## D89: Query Relevance Strictness Calibration

Implemented:

- query relevance thresholds now account for the selected semantic provider;
- RoSBERTa similarities are calibrated so approximate but truly relevant pages are not punished too aggressively;
- commercial modifiers such as buy/price/order still influence relevance only when the query contains them.

## D90-D91: Competitor Replacement And Suspicious Candidate Filtering

Implemented:

- competitor search now collects reserve candidates beyond requested `top_n`;
- the comparison context selects accepted competitors first and excludes failed, blocked, suspiciously thin or very low-score candidates;
- pages with `score < 10` are treated as unusable competitor context, commonly caused by blocking or irrelevant snapshots;
- each competitor result receives `competitor_context_status`: `accepted`, `discarded` or `unused`;
- comparison summary exposes `competitor-context-quality-v2`.

Key fields:

- `requested_top_n`;
- `collected_candidates`;
- `accepted_competitors`;
- `discarded_competitors`;
- `unused_candidates`;
- `replacement_attempts`;
- `replacements_used`;
- `discard_reasons`.

## D92-D93: Semantic Queue And Autoscaling

Implemented:

- added required queue `audits.semantic`;
- added worker profile `semantic_cpu`;
- routed target feature extraction and competitor semantic/ML analysis to the semantic queue;
- kept pipeline simple: no new mini-orchestration tasks were introduced;
- reused saved target semantic features on the second feature pass after heavy analysis;
- `scripts/dev.mjs` starts at least one semantic worker and supports opt-in autoscaling.

Autoscaling knobs:

- `--semantic-autoscale=auto`;
- `SEMANTIC_WORKER_MIN`;
- `SEMANTIC_WORKER_MAX`;
- `SEMANTIC_WORKER_SCALE_UP_DEPTH`;
- `SEMANTIC_WORKER_SCALE_UP_WAIT_MS`;
- `SEMANTIC_WORKER_SCALE_DOWN_IDLE_MS`;
- `SEMANTIC_WORKER_POLL_INTERVAL_MS`.

## D94: Competitor Context Quality In Product UI

Implemented:

- frontend uses only accepted competitors in the chart, tables and report exports;
- discarded and unused candidates are separated under a non-scoring section;
- UI summary explains how many valid competitors entered the calculation and how many were replaced or excluded;
- report/export no longer presents discarded candidates as real competitors.

## D95: Focused Product Benchmark

Evidence:

- script: `backend/app/ml/d95_focused_product_benchmark.py`;
- catalog: `backend/artifacts/ranking-benchmarks/d95-rosberta-competitor-replacement/d95-focused-catalog.json`;
- report: `backend/artifacts/ranking-benchmarks/d95-rosberta-competitor-replacement/d95-focused-product-benchmark-report.json`;
- markdown: `backend/artifacts/ranking-benchmarks/d95-rosberta-competitor-replacement/d95-focused-product-benchmark-report.md`.

Result:

- decision: `passed`;
- cases: `6`;
- failed cases: `0`;
- full mismatch example: `94.0 -> 4.7`;
- approximate relevant example: `86.0 -> 47.3`;
- no buy/price modifier example: `82.0 -> 82.0`;
- competitor replacement example: `3` accepted, `3` discarded, `2/3` replacements used.

## Verification

Passed locally:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m app.ml.d95_focused_product_benchmark
.venv\Scripts\python.exe -m pytest tests/test_semantic_provider.py tests/test_query_relevance_runtime.py tests/test_features.py tests/test_competitiveness_score.py tests/test_competitor_fetch_robustness.py tests/test_competitors.py tests/test_worker_topology.py tests/test_health_api.py tests/test_audit_pipeline.py -q -p no:cacheprovider
```

```powershell
cd E:\codexPROJ\diplom
npm --prefix frontend run test
npm --prefix frontend run build
node --test scripts/dev.test.mjs scripts/d31-runtime-smoke.test.mjs
```

Observed results:

- backend targeted suite: `101 passed`;
- D95 benchmark: `passed`;
- frontend tests: `68 passed`;
- frontend production build: passed;
- dev/smoke script tests: `13 passed`.

## D96: Live RoSBERTa Smoke

Implemented:

- added `scripts/d96-rosberta-live-smoke.mjs`;
- started a fresh dev runtime with the new topology;
- verified readiness with `5` workers, including `site-audit.semantic_cpu.1@Qonwick`;
- verified expected queue coverage includes `audits.semantic`;
- ran `3` real live audits through API, frontend shell, SearXNG, Redis and Celery workers.

Evidence:

- summary: `output/runtime-smoke/d96-rosberta-live-smoke-summary.json`;
- API base used by the smoke: `http://127.0.0.1:8001`;
- frontend base: `http://127.0.0.1:5173`;
- active runtime: `dataset-v7-final`, schema `v4`, `QueryCoreGuardrailCatBoostRegressor`, SHA1 `da285ca34d8c19079373b1db86d818355c7b80e0`.

Live smoke result:

- decision: `passed`;
- `козловой кран купить` / `https://pzpo.ru/crane/cat-krany-kozlovye/`: score `68.3102`, no early stop, RoSBERTa provider code `2`, `3` accepted competitors, `1` discarded low-score competitor replaced.
- `купить козловой кран` / `https://winemore.ru/`: score `7.1563`, RoSBERTa provider code `2`, unrelated page kept below mismatch cap, `3` accepted competitors after `2` low-score replacements.
- `занятия пилатес москва` / `https://pilatesmed.ru/`: score `64.1375`, no early stop, RoSBERTa provider code `2`, no commercial modifier penalty, `3` accepted competitors.

Final notes:

- This wave does not mutate `backend/artifacts/page_quality_model.pkl`.
- D96 is a real live SERP/runtime smoke, while D95 remains the controlled focused benchmark.
- If backend later adds more exclusion statuses beyond `discarded` and `unused`, update `frontend/src/lib/competitorContext.ts`.
