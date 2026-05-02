# D58 Competitiveness Scorecard Re-Evaluation And Publish

- Decision: `publish_candidate`
- Publish action: `controlled_publish_required`
- Selected candidate: `pointwise_catboost_v5`
- Reason: `candidate_passed_v5_release_guardrails_and_outperformed_current`
- Release policy: `d55-product-aligned-v1`
- Production SHA1 before: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Production SHA1 after: `5374ca30f48f70d8629e7d84ec3df0524ef35b52`
- Production changed by D58: `True`

## Published Artifact

- Artifact version: `dataset-v5-20260502151507`
- Dataset: `dataset-v5`
- Model type: `CatBoostRegressor`
- Feature count: `148`

## Candidate Decisions

### pointwise_catboost_v5
- Publish allowed: `True`
- Failed checks: `none`
- Candidate metrics: `{"mae": 1.22855, "ndcg_at_10": 0.998374, "rmse": 1.874197, "spearman_mean": 0.957788, "top_3_hit_rate": 0.6, "validation_queries": 20.0}`
- Metric deltas: `{"mae": -6.223816, "ndcg_at_10": 0.016936, "rmse": -8.791748, "spearman_mean": 0.447128, "top_3_hit_rate": -0.3}`
- SERP diagnostics: `{"blocking": false, "top_3_hit_rate": {"candidate": 0.6, "delta": -0.3, "diagnostic_floor": 0.95, "reference": 0.9}, "warnings": ["top_3_hit_rate_below_diagnostic_floor", "top_3_hit_rate_below_reference"]}`

### ranking_aware_catboost_v5
- Publish allowed: `False`
- Failed checks: `mae_comparable_or_better`
- Candidate metrics: `{"mae": 14.448487, "ndcg_at_10": 0.995447, "rmse": 17.613531, "spearman_mean": 0.889367, "top_3_hit_rate": 0.55, "validation_queries": 20.0}`
- Metric deltas: `{"mae": 6.996121, "ndcg_at_10": 0.014009, "rmse": 6.947586, "spearman_mean": 0.378707, "top_3_hit_rate": -0.35}`
- SERP diagnostics: `{"blocking": false, "top_3_hit_rate": {"candidate": 0.55, "delta": -0.35, "diagnostic_floor": 0.95, "reference": 0.9}, "warnings": ["top_3_hit_rate_below_diagnostic_floor", "top_3_hit_rate_below_reference"]}`

### hybrid_catboost_ranker_v5
- Publish allowed: `True`
- Failed checks: `none`
- Candidate metrics: `{"mae": 2.816326, "ndcg_at_10": 0.998127, "rmse": 3.525109, "spearman_mean": 0.953195, "top_3_hit_rate": 0.65, "validation_queries": 20.0}`
- Metric deltas: `{"mae": -4.63604, "ndcg_at_10": 0.016689, "rmse": -7.140836, "spearman_mean": 0.442535, "top_3_hit_rate": -0.25}`
- SERP diagnostics: `{"blocking": false, "top_3_hit_rate": {"candidate": 0.65, "delta": -0.25, "diagnostic_floor": 0.95, "reference": 0.9}, "warnings": ["top_3_hit_rate_below_diagnostic_floor", "top_3_hit_rate_below_reference"]}`

## Verification

- Overall status: `passed`
- `backend_d58_ml_health_registry`: `passed`
- `frontend_report_ui`: `passed`
- `frontend_build`: `passed`
