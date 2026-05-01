# D37 Unified V3 Feature Model And Hybrid Guardrail Plan

This plan is the local source of truth for GitHub issue `#56`: `D37: Unified v3 feature model with hybrid ensemble and top-3 guardrail`.

It exists so future Codex dialogs can continue even when GitHub Issues for the private repository are unavailable and return `404 Not Found`.

## Current Context

`D27-D31` built and validated `dataset-v2`, trained a candidate artifact, and kept the existing production model because the ranking benchmark recommended `keep_reference`.

`D32-D36` improved the model evidence path with expert-rubric labels, refreshed dataset metadata, trained RF/CatBoost/CatBoostRanker candidates, ran shadow guardrails, and finalized a controlled no-publish decision. D36 left the production artifact unchanged:

- production artifact: `backend/artifacts/page_quality_model.pkl`
- runtime dataset version: `ru_commercial_dataset-20260421-primary`
- runtime model schema: `v1`
- production SHA1: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`

D35 rejected all D34 candidates for publish because product-critical `top_3_hit_rate` regressed from reference `0.95` to candidate `0.8`, even though RF/CatBoost improved absolute error and some ranking metrics.

## Purpose

D37 should create the next candidate as a real unified feature model, not merely as an average of old model predictions.

The product already extracts more features at runtime than the production model uses. The goal is to train a candidate that can use the strongest available pre-competitor signals together, then compare it honestly against the current production reference. If the candidate fails the release guardrails, the correct D37 result is another explicit `keep_reference` decision.

## Feature Scope

Current feature groups:

- `v1` baseline features: `59`
- snapshot auxiliary technical/commercial features: `49`
- current `v2` model schema: `108` features
- heavy-analysis runtime features: `25`
- intent-alignment runtime features: `15`
- SERP-relative competitor-aware features: `29`

The fully known runtime feature space is therefore up to `177` features. However, `dataset-v2` currently contains only the `108` `v2` features. It does not contain heavy-analysis, intent-alignment, or SERP-relative columns.

D37 should implement a safer pre-competitor `v3` first:

```text
MODEL_SCHEMA_VERSION_V3 =
  59 baseline features
  + 49 snapshot auxiliary technical/commercial features
  + 25 heavy-analysis features
  + 15 intent-alignment features
  = 148 features
```

This keeps D37 compatible with the current scoring lifecycle because these signals are available before the initial target score is calculated.

Do not include `serp_relative` in the primary D37 runtime model unless the implementation explicitly adds a second post-competitor scoring pass. `serp_relative` features are created only after competitor analysis, while the current `scoring` stage happens before full competitor aggregation.

A future follow-up can explore the full `177`-feature competitor-aware model:

```text
preliminary score -> competitor analysis -> serp_relative features -> final competitor-aware ML score
```

## Active Task

- [x] `D37` / GitHub `#56`: add unified `v3` feature schema, build dataset evidence with `148` pre-competitor features, train non-production candidates, run hybrid/shadow benchmark, and keep production unchanged unless all top-3 guardrails pass.

## Progress

- [x] (2026-05-02) D37 GitHub issue `#56` created with the unified v3/hybrid/top-3 guardrail scope.
- [x] (2026-05-02) Local D37 plan created in `plans/d37-unified-v3-hybrid-ensemble-top3-guardrail.md`.
- [x] (2026-05-02) Added `MODEL_SCHEMA_VERSION_V3` and the `148`-feature pre-competitor schema.
- [x] (2026-05-02) Created D37 dataset bundle `backend/data/dataset_versions/dataset-v3-d37/` with actual v3 columns.
- [x] (2026-05-02) Trained RF v3, CatBoost v3 and CatBoostRanker v3 candidate artifacts without replacing production.
- [x] (2026-05-02) Ran D37 shadow benchmark against the current production reference.
- [x] (2026-05-02) Documented D37 decision evidence: `pointwise_catboost` is publish-recommended by guardrails, while production artifact stayed unchanged during D37.

## D37 Evidence

Dataset evidence:

- bundle: `backend/data/dataset_versions/dataset-v3-d37/`
- dataset: `backend/data/dataset_versions/dataset-v3-d37/dataset.csv`
- manifest: `backend/data/dataset_versions/dataset-v3-d37/manifest.json`
- split: `backend/data/dataset_versions/dataset-v3-d37/split.json`
- report: `backend/data/dataset_versions/dataset-v3-d37/d37-v3-dataset-report.json`
- rows: `885`
- queries: `99`
- model schema: `v3`
- feature count: `148`
- source raw artifacts: `885/885` found
- split: `group_by_query`, `695` train rows, `190` validation rows, `0` query leakage

Candidate artifacts:

- RF v3: `backend/artifacts/page_quality_model.dataset-v3-d37-rf-candidate.pkl`
- CatBoost v3: `backend/artifacts/page_quality_model.dataset-v3-d37-catboost-candidate.pkl`
- CatBoostRanker v3: `backend/artifacts/page_quality_model.dataset-v3-d37-ranking-candidate.pkl`
- training report: `backend/artifacts/ranking-benchmarks/dataset-v3-d37/candidate-artifact-training-report.json`

Shadow benchmark evidence:

- report: `backend/artifacts/ranking-benchmarks/dataset-v3-d37-shadow/shadow-benchmark-guardrails-report.json`
- markdown: `backend/artifacts/ranking-benchmarks/dataset-v3-d37-shadow/shadow-benchmark-guardrails-report.md`
- reference: `top_3_hit_rate=0.95`, `ndcg_at_10=0.909302`, `spearman_mean=0.153604`, `MAE=23.858757`
- selected candidate: `pointwise_catboost`
- selected candidate metrics: `top_3_hit_rate=0.95`, `ndcg_at_10=0.945929`, `spearman_mean=0.421894`, `MAE=11.774165`
- decision: `publish_candidate`
- reason: `candidate_passed_all_publish_gates_and_outperformed_reference`
- rejected candidates: RF v3 failed `top_3_hit_rate`; CatBoostRanker v3 failed `top_3_hit_rate`, RMSE/MAE comparability and absolute-error viability.
- smoke explainability: `4/4` queries covered, bounded scores, explainability sensibility passed.

Production state:

- `backend/artifacts/page_quality_model.pkl` was not overwritten during D37 candidate training or benchmarking.
- production SHA1 after D37 benchmark: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`
- D37 therefore proved a publishable candidate, while actual product rollout was handled later by D38.

Post-D37 rollout note:

- D38 / GitHub `#57` later performed that controlled publish step.
- Current production artifact is CatBoost v3: `backend/artifacts/page_quality_model.pkl`, SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`, dataset `dataset-v3-d37`, schema `v3`, artifact version `dataset-v3-d37-20260501200434`.
- Rollback artifact for the old v1 model remains `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl`.

Checks:

- `cd E:\codexPROJ\diplom\backend; .venv\Scripts\python.exe -m pytest tests\test_model_schema.py tests\test_v3_dataset.py tests\test_training_pipeline.py tests\test_training_dataset_quality.py tests\test_ranking_benchmark.py tests\test_shadow_benchmark.py -q` -> `27 passed`
- `cd E:\codexPROJ\diplom; npm run test:scripts` -> `13 passed`

## Work Items

1. Add schema support.

   Update `backend/app/ml/model_schema.py` with `MODEL_SCHEMA_VERSION_V3`. Its columns should be:

   - `BASELINE_FEATURE_COLUMNS`
   - `SNAPSHOT_AUXILIARY_FEATURE_COLUMNS`
   - `HEAVY_ANALYSIS_FEATURE_COLUMNS`
   - `INTENT_ALIGNMENT_FEATURE_COLUMNS`

   Keep `DEFAULT_RUNTIME_MODEL_SCHEMA_VERSION` unchanged until a publish decision. D37 must not accidentally switch runtime scoring to v3 before benchmark evidence exists.

2. Build v3 dataset evidence.

   Create a versioned dataset bundle such as `backend/data/dataset_versions/dataset-v3-d37/` or another explicit D37 path. The bundle must include a `dataset.csv` with all `148` v3 feature columns, a `manifest.json`, and a `split.json` with `group_by_query` and no query leakage.

   The dataset refresh should derive values deterministically from existing row data and raw snapshot artifacts. Missing feature values must be explicit and repeatable, normally `0` for absent binary/count/score features, not random or implicit.

3. Train non-production candidates.

   Save candidate artifacts under unique D37 names, for example:

   - `backend/artifacts/page_quality_model.dataset-v3-d37-rf-candidate.pkl`
   - `backend/artifacts/page_quality_model.dataset-v3-d37-catboost-candidate.pkl`
   - `backend/artifacts/page_quality_model.dataset-v3-d37-ranking-candidate.pkl`

   Candidate training must not overwrite `backend/artifacts/page_quality_model.pkl`.

4. Evaluate candidates against the current reference.

   The D37 benchmark should compare each candidate to the current production artifact and write JSON/Markdown evidence under an explicit D37 directory, for example:

   - `backend/artifacts/ranking-benchmarks/dataset-v3-d37/hybrid-ensemble-report.json`
   - `backend/artifacts/ranking-benchmarks/dataset-v3-d37/hybrid-ensemble-report.md`

5. Consider hybrid ensemble only after v3 candidates exist.

   A hybrid candidate may combine:

   - production reference stability;
   - RF v3;
   - CatBoost v3;
   - calibrated ranker signal if it does not break absolute-error viability.

   The hybrid must be evaluated as product behavior, not as a benchmark-only trick.

## Guardrails

D37 may recommend publish only if the selected candidate is at least as good as the reference on product-critical ranking and not worse on basic score quality:

- `top_3_hit_rate >= reference_top_3_hit_rate`
- `ndcg_at_10 >= reference_ndcg_at_10`
- `spearman_mean >= reference_spearman_mean`
- `mae <= reference_mae`
- scores are bounded to `0..100`
- runtime explanations remain finite and sensible
- production artifact SHA1 stays unchanged during candidate training and benchmarking

`top_3_hit_rate` is a release gate, not a cosmetic metric. Do not hard-code a top-3 boost only to pass the benchmark. If calibration or a top-3 protection strategy is used, it must be documented as real model/product behavior and validated honestly.

## Suggested Checks

Backend ML checks:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest tests\test_training_pipeline.py tests\test_training_dataset_quality.py tests\test_ranking_benchmark.py tests\test_shadow_benchmark.py
```

Script checks:

```powershell
cd E:\codexPROJ\diplom
npm run test:scripts
```

If D37 touches runtime scoring or publish logic, also run the full backend suite and a product smoke before any publish decision.

## Acceptance Criteria

- D37 is implemented as a unified feature-model experiment, not only as an averaged old-model ensemble.
- `MODEL_SCHEMA_VERSION_V3` exists and represents the `148` pre-competitor feature schema.
- Dataset evidence includes actual v3 feature columns and no train/validation query leakage.
- Candidate artifacts are saved with D37 names and do not overwrite production.
- D37 benchmark compares candidates against the current production reference.
- If guardrails fail, the report clearly recommends `keep_reference`.
- `backend/artifacts/page_quality_model.pkl` remains unchanged unless a later controlled publish task explicitly passes all guardrails.

## Notes For Future Follow-Up

The 177-feature competitor-aware model is intentionally not the default D37 implementation. It requires a second score pass after competitor aggregation because `SERP_RELATIVE_FEATURE_COLUMNS` are unavailable at the first scoring stage. That design can be valuable, but it should be planned as a separate pipeline change after D37 proves the safer `v3` path.
