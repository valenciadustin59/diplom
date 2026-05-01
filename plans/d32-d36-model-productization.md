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

- [ ] `D32` / GitHub `#51`: add expert labels for `dataset-v2` model productization.
- [ ] `D33` / GitHub `#52`: refresh `dataset-v2` manifest and group split after expert labels.
- [ ] `D34` / GitHub `#53`: train ranking-aware candidate models for product deployment.
- [ ] `D35` / GitHub `#54`: run shadow benchmark and explainability guardrails before publish.
- [ ] `D36` / GitHub `#55`: controlled model publish, rollback path and product smoke verification.

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
.venv\Scripts\python.exe -m pytest tests\test_ranking_benchmark.py tests\test_model_evaluate.py tests\test_model_publish.py

cd E:\codexPROJ\diplom
npm run test:scripts
```

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
