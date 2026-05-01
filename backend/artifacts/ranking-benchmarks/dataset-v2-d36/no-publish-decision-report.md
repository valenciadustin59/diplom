# D36 Keep-Reference Decision

- Decision: `keep_reference`
- Publish action: `no_publish`
- Reason: `d35_no_candidate_passed_all_publish_gates`
- D35 recommendation: `keep_reference`
- D35 reason: `no_candidate_passed_all_publish_gates`
- Production SHA1 before: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`
- Production SHA1 after: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`
- Production artifact unchanged: `True`

## Selected Runtime Artifact

- Path: `artifacts\page_quality_model.pkl`
- SHA1: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`
- Artifact version: `ru_commercial_dataset-20260421-primary-20260421174901`
- Dataset version: `ru_commercial_dataset-20260421-primary`
- Model schema version: `v1`
- Model type: `RandomForestRegressor`
- Feature count: `59`

## Shadow Evidence

- D35 report: `artifacts\ranking-benchmarks\dataset-v2-d35\shadow-benchmark-guardrails-report.json`
- Dataset version: `dataset-v2`
- Reference metrics: `{"mae": 23.858757, "ndcg_at_10": 0.909302, "rmse": 27.980756, "spearman_mean": 0.153604, "top_3_hit_rate": 0.95, "validation_queries": 20.0}`
- Smoke explainability: `{"covered_queries_count": 4, "exact_match_queries_count": 3, "fallback_match_queries_count": 1, "missing_queries_count": 0, "requested_queries_count": 4}`
- Explainability sensibility passed: `True`

## Candidate Rejections

### pointwise_random_forest
- Candidate family: `pointwise`
- Model path: `artifacts\page_quality_model.dataset-v2-expert-rf-candidate.pkl`
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed`
- Candidate metrics: `{"mae": 12.380441, "ndcg_at_10": 0.942676, "rmse": 15.309359, "spearman_mean": 0.398474, "top_3_hit_rate": 0.8, "validation_queries": 20.0}`
- Metric deltas vs reference: `{"mae": -11.478316, "ndcg_at_10": 0.033374, "rmse": -12.671397, "spearman_mean": 0.24487, "top_3_hit_rate": -0.15}`

### pointwise_catboost
- Candidate family: `pointwise`
- Model path: `artifacts\page_quality_model.dataset-v2-expert-catboost-candidate.pkl`
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed`
- Candidate metrics: `{"mae": 12.003497, "ndcg_at_10": 0.947887, "rmse": 14.980677, "spearman_mean": 0.404524, "top_3_hit_rate": 0.8, "validation_queries": 20.0}`
- Metric deltas vs reference: `{"mae": -11.85526, "ndcg_at_10": 0.038585, "rmse": -13.000079, "spearman_mean": 0.25092, "top_3_hit_rate": -0.15}`

### catboost_ranker
- Candidate family: `ranking`
- Model path: `artifacts\page_quality_model.dataset-v2-ranking-candidate.pkl`
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed, rmse_not_comparable, mae_not_comparable, ranking_family_absolute_error_not_viable`
- Candidate metrics: `{"mae": 72.250466, "ndcg_at_10": 0.938496, "rmse": 74.733525, "spearman_mean": 0.379091, "top_3_hit_rate": 0.8, "validation_queries": 20.0}`
- Metric deltas vs reference: `{"mae": 48.391709, "ndcg_at_10": 0.029194, "rmse": 46.752769, "spearman_mean": 0.225487, "top_3_hit_rate": -0.15}`

## Rollback Reference

- Rollback required: `False`
- Reason: No artifact was published in D36; the current production alias remains selected.
- Current alias path: `artifacts\page_quality_model.pkl`
- Current alias SHA1: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`
- Versioned reference path: `artifacts\versions\page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl`
- Versioned reference available: `True`
- Versioned reference SHA1: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`

## Verification

- Overall status: `passed`
- Runtime smoke status: `passed`
- Runtime smoke summary: `..\output\runtime-smoke\d36-smoke-summary.json`
- Runtime smoke audit: `a814ad9e-0f35-441e-a7d3-f82a34abaae9`
- Runtime smoke model info: `{"artifact_family": "page_quality_model", "artifact_version": "ru_commercial_dataset-20260421-primary-20260421174901", "dataset_version": "ru_commercial_dataset-20260421-primary", "model_schema_version": "v1", "model_type": "RandomForestRegressor", "source": "local_dataset"}`
- `npm run build`: `passed`
- `npm run site:check`: `passed`
- `npm run test:scripts`: `passed`
- `targeted backend pytest`: `passed`
- `backend full pytest`: `passed`
