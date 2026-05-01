# D38 Controlled Publish CatBoost V3 Candidate

This plan is the local source of truth for GitHub issue `#57`: `D38: Controlled publish CatBoost v3 candidate`.

It exists so future Codex dialogs can continue even when GitHub Issues for the private repository are unavailable and return `404 Not Found`.

## Purpose

D37 proved that the unified `v3` CatBoost candidate passes the product guardrails, but it intentionally left the production artifact unchanged. D38 turns that evidence into product behavior: the runtime `backend/artifacts/page_quality_model.pkl` alias now points to the D37 CatBoost v3 candidate, with a rollback reference and smoke evidence.

## Progress

- [x] (2026-05-02) GitHub issue `#57` created for D38 controlled publish.
- [x] (2026-05-02) Added `app.ml.controlled_publish` with shadow-report validation, rollback preservation, production alias publish, evidence report writing and post-publish verification update.
- [x] (2026-05-02) Added regression coverage in `backend/tests/test_controlled_publish.py`.
- [x] (2026-05-02) Published `backend/artifacts/page_quality_model.dataset-v3-d37-catboost-candidate.pkl` to `backend/artifacts/page_quality_model.pkl`.
- [x] (2026-05-02) Preserved rollback reference for the previous production model under `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl`.
- [x] (2026-05-02) Wrote D38 evidence to `backend/artifacts/ranking-benchmarks/dataset-v3-d37-d38/`.
- [x] (2026-05-02) Ran post-publish backend/script checks and runtime smoke.

## Evidence

Published runtime artifact:

- path: `backend/artifacts/page_quality_model.pkl`
- SHA1 before publish: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`
- SHA1 after publish: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- artifact version: `dataset-v3-d37-20260501200434`
- model type: `CatBoostRegressor`
- dataset version: `dataset-v3-d37`
- model schema version: `v3`
- feature count: `148`

Rollback reference:

- model: `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl`
- SHA1: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`
- metadata: `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.metadata.json`

D38 reports:

- JSON: `backend/artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.json`
- Markdown: `backend/artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.md`

Runtime smoke:

- summary: `output/runtime-smoke/d38-smoke-summary.json`
- audit: `690504f2-ca2f-42a6-a012-e622438437a7`
- status: `completed`
- readiness: `ready`
- workers: `4`
- missing queues: `[]`
- competitors: `2 found / 2 analyzed / 0 failed`
- recommendations: `11`
- runtime model: `dataset-v3-d37` / schema `v3` / `CatBoostRegressor`
- fan-out: `competitor_page` dispatch/terminal `2/2`

Checks:

- `cd E:\codexPROJ\diplom\backend; .venv\Scripts\python.exe -m pytest tests\test_model_schema.py tests\test_v3_dataset.py tests\test_controlled_publish.py tests\test_model_publish.py tests\test_no_publish_decision.py tests\test_training_pipeline.py tests\test_training_dataset_quality.py tests\test_ranking_benchmark.py tests\test_shadow_benchmark.py -q` -> `41 passed`
- `cd E:\codexPROJ\diplom; npm run test:scripts` -> `13 passed`

## Decision

D38 publishes the D37 `pointwise_catboost` candidate because D37 shadow guardrails selected it with:

- `top_3_hit_rate=0.95`, equal to reference;
- `ndcg_at_10=0.945929`, above reference `0.909302`;
- `spearman_mean=0.421894`, above reference `0.153604`;
- `MAE=11.774165`, below reference `23.858757`.

The previous RandomForest v1 artifact remains available for rollback, but it is no longer the selected runtime model.

## Next Step

The next product task should expose active model metadata in the UI/report layer, so users can see that audits are running on `dataset-v3-d37`, schema `v3`, `CatBoostRegressor`, `148` features.
