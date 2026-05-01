# D32-D36 Model Productization Plan

This plan is the local source of truth for the next model-deployment wave after `D27-D31`.
It mirrors GitHub issues `#51-#55` so future Codex dialogs can continue even when GitHub
Issues are private or unavailable.

## Current Context

`D27-D31` are complete. `dataset-v2` was built and validated, the D29 candidate model was
trained, and D30 benchmarked it against the current production artifact. The correct D31
decision was `keep_reference`: the candidate improved absolute error (`RMSE/MAE`) but
lost product-critical ranking metrics (`spearman_mean`, `ndcg_at_10`, `top_3_hit_rate`).

The product currently still serves:

- production model: `backend/artifacts/page_quality_model.pkl`
- runtime dataset version: `ru_commercial_dataset-20260421-primary`
- runtime model schema: `v1`
- candidate evidence: `backend/artifacts/page_quality_model.dataset-v2-candidate.pkl`
- benchmark evidence: `backend/artifacts/ranking-benchmarks/dataset-v2/`

The next wave should not blindly replace the model. It should make the candidate good enough
to publish, or explicitly keep the current production model with evidence.

## Active Tasks

- [x] `D32` / GitHub `#51`: add expert labels for `dataset-v2` model productization.
- [x] `D33` / GitHub `#52`: refresh `dataset-v2` manifest and group split after expert labels.
- [x] `D34` / GitHub `#53`: train ranking-aware candidate models for product deployment.
- [x] `D35` / GitHub `#54`: run shadow benchmark and explainability guardrails before publish.
- [ ] `D36` / GitHub `#55`: controlled model publish, rollback path and product smoke verification.

## Progress

- [x] (2026-05-01) D32: Filled `backend/data/dataset_versions/dataset-v2/expert_labels.csv` with `197` expert-rubric labels covering `99` queries, `6` categories, `9` city buckets, and all `5` observed page types. Labels use `label_source=expert_rubric_v1`, `labeler=builder_d32_rubric_v1`, and a landing-page quality rubric where the weak SERP-rank prior is capped at `5%` of the score. Score bands: `19` strong (`90-100`), `101` usable (`70-89`), `19` partial (`50-69`), `4` weak (`20-49`), and `54` irrelevant/broken/thin (`0-19`). `dataset.csv` and production artifacts remain unchanged; D33 must refresh dataset rows/manifest/split so these labels affect `target_score` and `hybrid` row counts.
- [x] (2026-05-01) D33: Applied D32 expert labels to `dataset.csv` through `app.ml.expert_label_refresh`, regenerated `split.json` with `group_by_query`, and regenerated `manifest.json`. Dataset evidence now has `197` `hybrid` rows and `688` `weak_serp` rows, `expert_rows_count=197`, `hybrid_rows_count=197`, `unmatched_expert_labels_count=0`, artifact coverage `1.0`, and `ready_for_training=true`. Split stayed `695` train / `190` validation rows with `79` train queries / `20` validation queries and no query overlap. Production artifact hash remains unchanged.
- [x] (2026-05-01) D34: Added `app.ml.candidate_artifacts` and trained three non-production candidate artifacts from the D33 `dataset-v2` evidence: `page_quality_model.dataset-v2-expert-rf-candidate.pkl`, `page_quality_model.dataset-v2-expert-catboost-candidate.pkl`, and `page_quality_model.dataset-v2-ranking-candidate.pkl`. Training used schema `v2`, `108` features, `group_by_query` split, `695` train rows / `190` validation rows, and `0` query overlap. D34 validation metrics selected `pointwise_catboost` as best overall (`spearman_mean=0.404524`, `ndcg_at_10=0.947887`, `top_3_hit_rate=0.8`, `MAE=12.003497`); the best ranking-aware available model is `catboost_ranker` (`spearman_mean=0.379091`, `ndcg_at_10=0.938496`, `top_3_hit_rate=0.8`, `MAE=72.250466`). LightGBM and XGBoost rankers are unavailable in the local environment. Production artifact `backend/artifacts/page_quality_model.pkl` remains unchanged at SHA1 `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`.
- [x] (2026-05-01) D35: Added `app.ml.shadow_benchmark` and ran a no-publish shadow benchmark/guardrail report for the three D34 artifacts against the current reference artifact. The report recommends `keep_reference` because no candidate passed all publish gates. RF and CatBoost improve Spearman/NDCG/RMSE/MAE but fail `top_3_hit_rate` (`0.8` vs reference `0.95`). `CatBoostRanker` also fails absolute-error viability (`MAE=72.250466` vs reference `23.858757`). Smoke explainability found rows for `4/4` D35 smoke queries, with `3` exact query matches and `1` documented fallback (`ремонт квартир москва` -> `ремонт квартир цена Москва`). Bounded explanation checks and the explicit explainability sensibility heuristic passed for all three candidates. Production artifact hash remains unchanged at SHA1 `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`.

## D32: Expert Labels

Goal: improve label quality before training another publish candidate.

Work:

- Fill `backend/data/dataset_versions/dataset-v2/expert_labels.csv`.
- Label at least `100-200` rows across different queries, categories, cities and page types.
- Score landing-page quality for the audit product, not just SERP rank.
- Preserve `query`, `url`, `expert_target_score`, `label_source`, `labeler`.
- Keep production model artifacts unchanged.

Suggested scoring rubric:

- `90-100`: strong relevant commercial landing page with good content, trust, contacts and CTA.
- `70-89`: usable relevant page with minor gaps.
- `50-69`: partially relevant or weak page.
- `20-49`: poor, thin or weakly relevant page.
- `0-19`: irrelevant, empty, broken or not a landing page.

D32 output:

- `backend/data/dataset_versions/dataset-v2/expert_labels.csv` now contains `197` labels.
- `scripts/generate_d32_expert_labels.py` records the deterministic rubric and selection logic.
- `backend/data/dataset_versions/dataset-v2/dataset.json` records the D32 label subset metadata.
- `backend/data/dataset_versions/dataset-v2/dataset.csv` is intentionally not refreshed until D33.

Checks:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest tests\test_training_pipeline.py tests\test_training_dataset_quality.py
```

## D33: Manifest And Split Refresh

Goal: make dataset evidence reflect the new expert/hybrid labels.

Work:

- Refresh dataset rows if required so expert labels affect `target_score`.
- Regenerate `manifest.json`.
- Regenerate or validate `split.json` with `group_by_query`.
- Verify no query leakage between train and validation.
- Verify `label_source_distribution`, `expert_rows_count`, `hybrid_rows_count`.
- Verify artifact coverage.

D33 output:

- `backend/data/dataset_versions/dataset-v2/dataset.csv` now applies expert labels to `target_score` using the existing `0.7 * expert + 0.3 * weak` hybrid formula.
- `backend/data/dataset_versions/dataset-v2/manifest.json` reports `label_source_distribution={"hybrid": 197, "weak_serp": 688}`, `expert_rows_count=197`, `hybrid_rows_count=197`, `ready_for_training=true`.
- `backend/data/dataset_versions/dataset-v2/split.json` remains `group_by_query` with no train/validation query leakage.
- `backend/app/ml/expert_label_refresh.py` records the reusable in-place refresh command used for D33.

Checks:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest tests\test_training_dataset_quality.py tests\test_training_pipeline.py
```

## D34: Ranking-Aware Candidates

Goal: train candidates that can actually beat production on ranking quality.

Work:

- Train candidates without replacing `backend/artifacts/page_quality_model.pkl`.
- Compare pointwise baseline, CatBoost candidate and ranking-aware candidate where available.
- Save candidates under unique artifact names.
- Record model metadata: dataset version, model type, feature count, rows/query counts and split mode.

Candidate examples:

```text
backend/artifacts/page_quality_model.dataset-v2-expert-rf-candidate.pkl
backend/artifacts/page_quality_model.dataset-v2-expert-catboost-candidate.pkl
backend/artifacts/page_quality_model.dataset-v2-ranking-candidate.pkl
```

D34 output:

- `backend/app/ml/candidate_artifacts.py` adds a reusable train/save path for candidate artifacts without invoking publish.
- `backend/artifacts/page_quality_model.dataset-v2-expert-rf-candidate.pkl`: `RandomForestRegressor`, schema `v2`, `108` features, `spearman_mean=0.398474`, `ndcg_at_10=0.942676`, `top_3_hit_rate=0.8`, `MAE=12.380441`.
- `backend/artifacts/page_quality_model.dataset-v2-expert-catboost-candidate.pkl`: `CatBoostRegressor`, schema `v2`, `108` features, `spearman_mean=0.404524`, `ndcg_at_10=0.947887`, `top_3_hit_rate=0.8`, `MAE=12.003497`.
- `backend/artifacts/page_quality_model.dataset-v2-ranking-candidate.pkl`: best available ranking model, `CatBoostRanker`, schema `v2`, `108` features, `spearman_mean=0.379091`, `ndcg_at_10=0.938496`, `top_3_hit_rate=0.8`, `MAE=72.250466`.
- D34 evidence report: `backend/artifacts/ranking-benchmarks/dataset-v2-d34/candidate-artifact-training-report.json` and `.md`.
- Post-training compatibility check: all three D34 artifacts load through the existing `load_model_artifact` path and produce bounded `predict_score` output, including the saved `CatBoostRanker`.
- D34 is not a publish decision. D35 must compare candidates against the current reference with shadow benchmark and guardrails before D36 can publish or explicitly keep the reference.

Checks:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest tests\test_training_pipeline.py tests\test_model_evaluate.py tests\test_ranking_benchmark.py
```

## D35: Shadow Benchmark And Guardrails

Goal: decide whether a candidate is safe to publish.

Minimum publish gate:

- `ndcg_at_10` is not worse than reference.
- `top_3_hit_rate` is not worse than reference.
- `spearman_mean` is not worse, unless there is a documented product rationale.
- `RMSE/MAE` improve or stay comparable.
- D34's saved `CatBoostRanker` must be evaluated explicitly against the reference, not treated as publishable only because it is ranking-aware; its D34 validation `MAE=72.250466` is a viability concern unless D35 evidence and product rationale justify it.
- Score explanations and top features look sensible.
- Smoke audits show no recommendation regressions.

Smoke query set:

- `ремонт квартир москва`
- `пластиковые окна казань`
- `кухни на заказ санкт-петербург`
- `натяжные потолки новосибирск`

Checks:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest tests\test_shadow_benchmark.py tests\test_ranking_benchmark.py tests\test_model_evaluate.py tests\test_model_publish.py

cd E:\codexPROJ\diplom
npm run test:scripts
```

D35 output:

- `backend/app/ml/shadow_benchmark.py` evaluates saved candidate artifacts against the current reference without training or publishing.
- `backend/artifacts/ranking-benchmarks/dataset-v2-d35/shadow-benchmark-guardrails-report.json` and `.md` record the D35 shadow benchmark.
- Reference validation metrics: `spearman_mean=0.153604`, `ndcg_at_10=0.909302`, `top_3_hit_rate=0.95`, `MAE=23.858757`.
- `pointwise_random_forest`: gate failed on `top_3_hit_rate_regressed`; deltas vs reference are `spearman_mean=+0.24487`, `ndcg_at_10=+0.033374`, `top_3_hit_rate=-0.15`, `MAE=-11.478316`.
- `pointwise_catboost`: gate failed on `top_3_hit_rate_regressed`; deltas vs reference are `spearman_mean=+0.25092`, `ndcg_at_10=+0.038585`, `top_3_hit_rate=-0.15`, `MAE=-11.85526`.
- `catboost_ranker`: gate failed on `top_3_hit_rate_regressed`, `rmse_not_comparable`, `mae_not_comparable`, and `ranking_family_absolute_error_not_viable`; deltas vs reference are `spearman_mean=+0.225487`, `ndcg_at_10=+0.029194`, `top_3_hit_rate=-0.15`, `MAE=+48.391709`.
- Smoke explainability rows: `4/4` available, but only `3/4` are exact query matches; `ремонт квартир москва` used the documented fallback `ремонт квартир цена Москва`.
- Explainability sensibility heuristic: passed for all three candidates. The heuristic requires non-empty finite top features containing a known SEO signal and bounded smoke explanations containing known explanation factor keys.
- D35 decision: `keep_reference`. D36 should use the keep-reference path unless the user explicitly requests additional model work before D36.

## D36: Controlled Publish Or Keep-Reference

Goal: publish only if D35 justifies it. Otherwise document a no-publish decision.

Publish path:

- Replace `backend/artifacts/page_quality_model.pkl` only through controlled publish flow.
- Update `page_quality_model.metadata.json`.
- Preserve rollback evidence for the previous artifact.
- Run full product smoke against the final selected model.

Keep-reference path:

- Leave production artifact unchanged.
- Preserve candidate and benchmark evidence.
- Document why publish was rejected.
- Run smoke to prove the product still works on the selected production model.

Final checks:

```powershell
cd E:\codexPROJ\diplom
npm run build
npm run site:check
npm run test:scripts

cd E:\codexPROJ\diplom\backend
$env:CELERY_BROKER_URL = "redis://localhost:1/0"
$env:CELERY_RESULT_BACKEND = "redis://localhost:1/0"
.venv\Scripts\python.exe -m pytest
Remove-Item Env:CELERY_BROKER_URL, Env:CELERY_RESULT_BACKEND
```

## Rules

- Do not close GitHub issues before implementation, checks, commit and push.
- Do not replace `backend/artifacts/page_quality_model.pkl` until D36.
- Do not add demo mode as part of this wave.
- Keep all generated evidence inside `E:\codexPROJ\diplom`.
- If GitHub Issues return `404`, continue from this file and `AGENTS.md`.
