# D44 Second-Pass Competitor-Aware Score Experiment

- Decision: `do_not_continue_without_more_evidence`
- Runtime impact: `none`
- Dataset: `dataset-v3-d37`
- Feature schema: `v3-serp-relative-experiment`
- Feature count: `177`
- Candidate artifact: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v3-d44-second-pass-experiment.pkl`
- Candidate non-production: `True`

## Two-Stage Contract

- Primary score remains available before competitor aggregation.
- Optional second-pass score is evaluated only after SERP-relative features exist.
- Minimum competitors for second pass: `2`
- Weak or missing competitor coverage keeps the primary score.

## Primary Vs Candidate

- Primary model: `CatBoostRegressor` / `dataset-v3-d37-20260501200434`
- Candidate model: `CatBoostRegressor` / `dataset-v3-d37-d44-second-pass-experiment`
- Top-3 delta: `-0.1`
- NDCG@10 delta: `-0.000398`
- MAE delta: `-0.002376`

## Guardrails

- `no_query_leakage`: `passed` - Train and validation partitions must not share query groups.
- `top_3_no_regression`: `failed` - Second-pass candidate should not regress top-3 hit rate versus the active primary model.
- `ndcg_no_regression`: `failed` - Second-pass candidate should not regress NDCG@10 versus the active primary model.
- `mae_no_regression`: `passed` - Second-pass candidate should not increase validation MAE versus the active primary model.
- `score_stability`: `passed` - Second-pass predictions should not create large score jumps for most validation rows.
- `score_boundedness`: `passed` - Second-pass raw predictions should stay inside the product 0-100 score range.
- `recommendation_consistency`: `failed` - Score movement should not contradict existing SERP-relative competitor-gap recommendation signals.
- `weak_competitor_coverage_fallback`: `passed` - Audits with weak competitor coverage must keep a valid primary score and skip the optional second pass.
- `reference_artifact_unchanged`: `passed` - D44 must not mutate backend/artifacts/page_quality_model.pkl or the selected reference artifact.
- `candidate_non_production`: `passed` - Candidate artifact must be clearly separate from production and marked non-production.

## Non-Production Notes

- D44 does not publish, roll back or replace `backend/artifacts/page_quality_model.pkl`.
- Candidate artifact is for offline second-pass evidence only.
- A later D45+ task would be required before any runtime scoring change.
