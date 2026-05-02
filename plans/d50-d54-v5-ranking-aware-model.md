# D50-D54: Ranking-Aware v5 Model Plan

GitHub issues: `D50` #69, `D51` #70, `D52` #71, `D53` #72, `D54` #73.

This wave exists because `dataset-v4` improved absolute score fit but failed the product-critical top-3 release gate. The next model should not simply be "v4 trained again"; it should become ranking-aware while keeping the current production model safe until a candidate proves it is better for SEO ranking.

## D50 / GitHub #69: Top-3 Regression Analysis

Goal: identify why D47/D48 candidates lost top-3 behavior against the current production CatBoost v3 model.

Scope:

- Compare production v3 and all D47 candidates inside the same validation query groups.
- Identify queries where production hits SERP top-3 and a candidate misses it.
- Record actual SERP top-3, production predicted top-3, candidate predicted top-3, lost rows, promoted rows and feature context.
- Classify failure patterns into actionable buckets for D51/D52.
- Do not train, publish or mutate `backend/artifacts/page_quality_model.pkl`.

Evidence:

- Runner: `backend/app/ml/top3_regression_analysis.py`.
- Report: `backend/artifacts/ranking-benchmarks/dataset-v5-d50/top3-regression-analysis.json` and `.md`.
- Validation scope: `190` validation rows, `20` validation queries, group-by-query split.
- Production artifact SHA1 stayed `29c4b29455f795a535da94b2c6f36ef603d003eb`.
- Total candidate/query regressions: `20`.
- Queries requiring D51 focus: `9`.
- Pattern counts: `rank_prior_disagreement=20`, `shortcut_text_volume=16`, `aggregator_or_marketplace_distortion=7`.
- Candidate regression counts: RF `8`, CatBoostRegressor `6`, CatBoostRanker `6`.
- Verification: `tests/test_top3_regression_analysis.py`, `tests/test_seo_weighted_shadow_benchmark.py`, `tests/test_seo_weighted_no_publish_decision.py`, `tests/test_training_pipeline.py`, and `tests/test_model_schema.py` passed together as `25 passed`.

## D51 / GitHub #70: Query-Level Preference Labels

Goal: build `dataset-v5` labeling evidence that teaches the model which pages should outrank others inside the same query.

Scope:

- Use D50 query diagnostics as input.
- Preserve page-quality labels on a bounded `0..100` scale.
- Add pairwise/listwise preference labels inside query groups.
- Use weak/uncertain margins where pages are close.
- Avoid blindly treating SERP rank as absolute truth.
- Keep labels explicitly deterministic expert-rubric labels, not human labels.

Acceptance:

- Completed: `dataset-v5` bundle includes `dataset.csv`, `page_labels.csv`, `preference_labels.csv`, `split.json` and `manifest.json`.
- Completed: split validation shows `0` query overlap.
- Completed: all `9/9` D50 failure-focus queries are represented in usable preference evidence.

Evidence:

- Runner: `backend/app/ml/v5_preferences.py`.
- Dataset bundle: `backend/data/dataset_versions/dataset-v5/dataset.csv`, `failures.csv`, `seeds.csv`, `split.json`, `manifest.json`.
- Page labels: `backend/data/dataset_versions/dataset-v5/page_labels.csv`.
- Preference labels: `backend/data/dataset_versions/dataset-v5/preference_labels.csv`.
- Reports: `backend/data/dataset_versions/dataset-v5/d51-query-preference-label-report.json` and `.md`.
- Split validation: `backend/data/dataset_versions/dataset-v5/d51-preference-split-validation.json`.
- Rows/page labels: `885`.
- Preference labels: `3351` total, `2863` usable for training.
- Strength distribution: `strong=2047`, `weak=816`, `uncertain=488`.
- Reason distribution: `ranking_target_margin=3258`, `d50_top3_recovery=74`, `d50_top3_conflict_manual_review=19`.
- D50 focus coverage: `9/9` focus queries represented.
- Split: `79` train queries, `20` validation queries, `0` query overlap.
- Manifest is `ready_for_training=true`.
- Verification: `tests/test_v5_preferences.py`, `tests/test_top3_regression_analysis.py`, `tests/test_v4_dataset.py`, `tests/test_seo_weighted_labels.py`, `tests/test_training_dataset_quality.py`, `tests/test_training_pipeline.py`, and `tests/test_model_schema.py` passed together as `35 passed`.
- Production artifact SHA1 remains `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D52 / GitHub #71: Shortcut Feature Control

Goal: prevent weak shortcut features from dominating the next publish candidate.

Scope:

- Define feature groups: critical, important and supporting.
- Cap or bucket raw quantitative features such as `word_count`, image count and link count.
- Keep thin-page penalties without unlimited upside for longer text.
- Reuse feature-dominance and score-response guardrails in D53/D54.

Acceptance:

- Feature policy and tests exist.
- Supporting features cannot dominate a publishable candidate.

## D53 / GitHub #72: Non-Production v5 Candidate Training

Goal: train v5 candidates that combine page-quality scoring and query-level ranking awareness.

Scope:

- Train pointwise CatBoostRegressor v5.
- Train ranking-aware candidate with query groups/preference labels.
- Optionally train a hybrid candidate with bounded `0..100` score.
- Save all candidates as non-production artifacts.

Acceptance:

- Artifacts and metadata sidecars exist.
- Compatibility smoke passes.
- No production artifact is changed.

## D54 / GitHub #73: Shadow Benchmark And Controlled Decision

Goal: decide whether v5 can replace the current production CatBoost v3 model.

Publish requirements:

- `top_3_hit_rate >= 0.95`.
- No meaningful `NDCG@10` regression.
- Absolute error remains viable.
- Scores stay bounded in `0..100`.
- Supporting features do not dominate explanations.
- Critical degradation reduces score more than supporting degradation.

If a candidate passes, D54 performs controlled publish with rollback and smoke evidence. If no candidate passes, D54 writes a no-publish report and keeps production.
