# D40-D44 Post-Publish Model Operations Backlog

This file is the local source of truth for the post-D39 backlog. GitHub issues may be inaccessible to other Codex chats without authenticated access, so the tasks are mirrored here.

## Context

D38 published the D37 `pointwise_catboost` candidate as the active runtime artifact at `backend/artifacts/page_quality_model.pkl`. D39 added `GET /health/model` and product UI visibility for the active model in the stack page, score explanation and audit report/export. The next wave should not repeat the CatBoost rollout. It should make the published model observable, safer to operate, and easier to validate in the product.

## Active Issues

- `D40` / GitHub `#59` — completed locally: post-publish model monitoring dashboard.
- `D41` / GitHub `#60` — completed locally: golden query replay guardrails after publish.
- `D42` / GitHub `#61` — completed locally: score confidence and data-quality warnings in audit UX.
- `D43` / GitHub `#62` — completed locally: model registry and rollback evidence UI.
- `D44` / GitHub `#63` — completed locally: second-pass competitor-aware score experiment with SERP-relative features.

## D40: Post-Publish Model Monitoring Dashboard

Goal: add post-publish monitoring for the active CatBoost v3 runtime model so the product can answer which model is serving audits, how many audits it handled, whether scores look stable, and whether runtime quality is drifting after D38/D39.

Scope:

- Build a backend view/model that aggregates recent audits by runtime model metadata from `score_breakdown.model_info`.
- Add model usage counters: audits by model artifact, schema version, status, date window and failure/warning count.
- Add score distribution metrics: average, min/max, p25/p50/p75, low-score count and high-score count for the active model.
- Add competitor coverage metrics: competitors found/analyzed/failed, grouped by model artifact where possible.
- Add a frontend monitoring card or section in the existing `Стек`/runtime area, reusing the D39 model status card rather than creating a separate admin app.
- Keep this informational only: no automatic rollback and no scoring behavior changes.

Acceptance:

- Product UI shows active model usage over recent audits, not only static artifact metadata.
- Empty state is clear when no completed audits have model metadata.
- Old audits without `model_info` do not break the dashboard and are counted separately as legacy/unknown.
- Tests cover aggregation logic and UI rendering.
- Helper docs are updated with D40 evidence after implementation.

## D41: Golden Query Replay Guardrails After Publish

Goal: create a reproducible post-publish replay workflow that reruns a fixed golden query set against the current runtime model and compares evidence with rollback/reference expectations.

Scope:

- Define a small golden query catalog that represents product domains already used in project evidence.
- Add a script that can run replay audits or evaluate stored snapshots without mutating production artifacts.
- Record for each replay item: query, target URL, selected model metadata, score, competitor counts, recommendations count, runtime status and failure context.
- Compare current model evidence against rollback/reference metadata where available.
- Produce JSON and Markdown reports under `backend/artifacts/ranking-benchmarks/` or `output/runtime-smoke/` with clear pass/warn/fail guardrails.
- Do not publish or roll back a model in this task.

Acceptance:

- A single command produces a deterministic replay report from the configured golden set.
- The report includes model artifact/schema/dataset metadata from D39.
- Guardrails include at least: no audit failures, competitor coverage threshold, score boundedness, recommendation availability and model metadata presence.
- The workflow is documented in helper files so another Codex chat can rerun it.
- Tests cover report building and guardrail decision logic without requiring live network by default.

## D42: Score Confidence And Data-Quality Warnings In Audit UX

Goal: make the audit result easier to trust by showing confidence/data-quality context for the score: whether the score is based on complete enough data, whether competitor coverage is sufficient, and whether fetch/model metadata is reliable.

Scope:

- Build a confidence view model from existing data: fetch status, feature schema, heavy analysis presence, competitor coverage, recommendation availability, model metadata presence and warnings/failure context.
- Add backend or frontend pure helpers to classify confidence as high/medium/low/unknown.
- Show confidence in overview/report without overwhelming the score card.
- Add clear warning copy for cases such as: no competitors analyzed, target fetch fallback, missing model metadata, incomplete recommendations and legacy audit.
- Include confidence in report/export where useful.
- No changes to the numeric score formula in this task.

Acceptance:

- Completed audits show a compact score confidence label and reason list.
- Failed/processing/legacy audits degrade gracefully.
- Long warning text does not break layout on narrow resolutions.
- Tests cover confidence classification and key UI states.
- Helper docs explain that D42 is a UX/reliability layer, not retraining.

## D43: Model Registry And Rollback Evidence UI

Goal: turn D38/D39 model metadata into a small product-facing model registry/history view: current model, previous rollback artifact, publish decision and evidence links/metadata in one place.

Scope:

- Extend model status payload or add a registry endpoint that lists current and known versioned artifacts from `backend/artifacts/versions/` plus public metadata sidecars.
- Surface current artifact, rollback artifact, dataset, schema, SHA1, publish decision, smoke evidence path and report path where available.
- Add a UI section under `Стек` for model release history / rollback evidence.
- Provide a rollback dry-run/checklist view only; do not execute rollback from UI.
- Include guardrails that warn if rollback metadata file or SHA1 is missing.

Acceptance:

- UI shows current CatBoost v3 and previous v1 RandomForest rollback artifact as separate records when metadata is present.
- Missing metadata is represented as a warning, not a crash.
- Backend tests cover artifact discovery and metadata normalization.
- Frontend tests cover rendering current/rollback records and narrow-layout behavior.
- Docs clarify that actual rollback remains a controlled engineering operation.

## D44: Second-Pass Competitor-Aware Score Experiment With SERP-Relative Features

Goal: prototype a controlled second-pass scoring experiment that can use the existing `serp_relative` features after competitor aggregation, without replacing the D38 production score by default.

Scope:

- Design a two-stage scoring contract: primary score remains available early; optional second-pass score is computed after competitor aggregation.
- Build dataset/evaluation evidence for using `serp_relative` features without query leakage.
- Train or simulate a non-production second-pass candidate and compare it against the current CatBoost v3 primary model.
- Add guardrails focused on product behavior: top-3, NDCG, MAE, score stability, recommendation consistency and no regression in audits with weak competitor coverage.
- Store candidate/report artifacts separately; do not replace `backend/artifacts/page_quality_model.pkl` in D44.
- Decide at the end whether second-pass scoring is worth a later D45+ publish task.

Acceptance:

- D44 produces a report explaining whether competitor-aware second-pass scoring helps enough to continue.
- Existing primary score path remains unchanged and tested.
- Audits with missing/failed competitors still have a valid primary score.
- Candidate artifacts are clearly marked non-production.
- Docs state that D44 is an experiment/evidence task, not a production rollout.

## Implementation Order

Implement D40 first because monitoring gives the product a baseline after D38/D39. D41 should follow because replay guardrails make future model changes reproducible. D42 then improves user trust in individual audit results. D43 makes release/rollback evidence visible. D44 is deliberately last because it is a modeling experiment and should benefit from the monitoring/replay/confidence context created by D40-D43.

## Current Status

- [x] (2026-05-02) GitHub issues `#59-#63` created for D40-D44.
- [x] (2026-05-02) Local backlog mirror created in this file.
- [x] (2026-05-02) D40 implementation.
- [x] (2026-05-02) D41 implementation.
- [x] (2026-05-02) D42 implementation.
- [x] (2026-05-02) D43 implementation.
- [x] (2026-05-02) D44 implementation.

## D40-D44 Implementation Notes

- `D40` adds `GET /health/model/monitoring` and `backend/app/model_monitoring.py`. The payload aggregates recent `Audit` rows by `score_breakdown.model_info`, exposes model usage, status/warning/failure counts, active-model score percentiles, competitor coverage, and counts legacy/unknown audits without `model_info` separately. The `Стек` runtime page now shows the monitoring section next to the D39 active model card.
- `D41` adds deterministic offline golden replay evidence in `backend/app/ml/golden_replay.py`. The default command is `cd backend && .venv\Scripts\python.exe -m app.ml.golden_replay --output-dir artifacts/ranking-benchmarks/dataset-v3-d41`. It evaluates stored evidence for the fixed golden catalog, normalizes volatile `/health/model.checked_at` to the fixed report timestamp, includes rollback reference, and does not publish, roll back, or mutate `backend/artifacts/page_quality_model.pkl`. Default evidence uses one D38 smoke artifact plus explicit synthetic stored fixtures for the remaining catalog items; pass `--evidence-json` to evaluate externally captured snapshots.
- D41 generated evidence: `backend/artifacts/ranking-benchmarks/dataset-v3-d41/golden-replay-report.json` and `backend/artifacts/ranking-benchmarks/dataset-v3-d41/golden-replay-report.md`; current decision is `passed` for `3/3` golden items and `21/21` guardrails.
- `D42` adds frontend-only score confidence/data-quality view-model logic in `frontend/src/lib/auditConfidence.ts`. It classifies score confidence as `high`, `medium`, `low`, or `unknown` from existing audit/result payloads: fetch status/method, feature schema, heavy-analysis payload, competitor coverage, recommendations, `score_breakdown.model_info`, warnings, and failure context.
- D42 UI surfaces are the audit overview card and the audit report tab/export. The overview shows a compact confidence badge plus a reason list; report UI, Markdown export, and printable HTML export include the same confidence metrics and reasons.
- D42 intentionally does not change the numeric score formula, model artifact, backend scoring pipeline, publish flow, rollback flow, or `backend/artifacts/page_quality_model.pkl`.
- D42 verification: `npm --prefix frontend run test -- src/lib/auditConfidence.test.ts src/lib/auditReport.test.ts src/lib/ui.test.tsx` passed with `23` tests; `npm --prefix frontend run build` passed.
- `D43` adds read-only model registry discovery in `backend/app/model_registry.py` and exposes it as `GET /health/model/registry`. The payload lists the active alias, known versioned artifacts from `backend/artifacts/versions/`, public metadata sidecars, publish report paths, smoke evidence paths, SHA1 values, and rollback guardrails.
- D43 registry discovery deliberately does not execute rollback and does not mutate `backend/artifacts/page_quality_model.pkl`. Rollback remains a controlled engineering operation; the UI shows only evidence and a dry-run/checklist state.
- D43 UI surfaces are the existing `Стек` runtime page via `frontend/src/lib/runtimeModelRegistry.ts` and the new `Model registry и rollback evidence` section in `frontend/src/pages/RuntimeStatusPage.tsx`. Current CatBoost v3 and previous v1 RandomForest rollback artifacts render as separate records when metadata is present.
- D43 missing rollback metadata/SHA1 conditions are warnings, not crashes. Backend tests cover artifact discovery and metadata normalization; frontend tests cover current/rollback rendering and long warning text in the registry card.
- D43 verification: `backend\.venv\Scripts\python.exe -m pytest backend/tests/test_model_registry.py backend/tests/test_health_api.py::test_model_registry_endpoint_returns_release_history_payload` passed with D43-targeted backend tests; `npm --prefix frontend run test` passed; `npm --prefix frontend run build`, `npm run site:check`, `npm run test:scripts`, and `git diff --check` passed. A full backend `pytest` attempt still fails in `backend/tests/test_audit_pipeline.py` and `backend/tests/test_audits_api.py` where those lifecycle tests expect inline terminal processing from `process_audit.run()` rather than the queued stage handoff; D43 did not modify the audit task pipeline.
- `D44` adds a non-production second-pass scoring contract in `backend/app/ml/second_pass.py` and an offline experiment runner in `backend/app/ml/second_pass_experiment.py`. The primary score remains the runtime score before competitor aggregation; the optional second-pass candidate is evaluated only after `serp_relative` features exist and skips back to the primary score when competitor coverage is weak.
- D44 generated a separate candidate artifact at `backend/artifacts/page_quality_model.dataset-v3-d44-second-pass-experiment.pkl` plus sidecar metadata at `backend/artifacts/page_quality_model.dataset-v3-d44-second-pass-experiment.metadata.json`. Both are marked `non_production=true`, `runtime_enabled=false`, and do not replace `backend/artifacts/page_quality_model.pkl`.
- D44 evidence is stored in `backend/artifacts/ranking-benchmarks/dataset-v3-d44/second-pass-experiment-report.json` and `.md`. The experiment uses `177` features (`148` v3 pre-competitor + `29` SERP-relative), split-then-enrich query isolation, and compares the second-pass CatBoost candidate against the active CatBoost v3 primary model.
- D44 decision is `do_not_continue_without_more_evidence`: MAE improved slightly (`-0.002376`), but top-3 hit rate regressed by `-0.1`, NDCG@10 regressed by `-0.000398`, and recommendation-consistency warning failed. This is evidence against a D45 publish path unless more data or a different second-pass design is requested.
- D44 verification: `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_second_pass_experiment.py backend\tests\test_features.py::test_merge_serp_relative_features_builds_gaps_and_fallbacks_with_single_competitor backend\tests\test_model_schema.py::test_model_schema_v3_combines_pre_competitor_feature_groups -q` passed with `4` tests; `certutil -hashfile backend\artifacts\page_quality_model.pkl SHA1` stayed `29c4b29455f795a535da94b2c6f36ef603d003eb`.
