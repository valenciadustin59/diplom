# D54 Shadow Benchmark And Controlled Decision

- Decision: `keep_current`
- Publish action: `no_publish`
- Reason: `no_candidate_passed_v5_release_guardrails`
- Selected candidate: `None`
- Dataset: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v5\dataset.controlled.csv`
- Feature policy: `v5-shortcut-control-v1`
- Production SHA1 before: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Production SHA1 after: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Production changed by D54: `False`

## Current Production Reference

- Metrics: `{"mae": 7.452366, "ndcg_at_10": 0.981438, "rmse": 10.665945, "spearman_mean": 0.51066, "top_3_hit_rate": 0.9, "validation_queries": 20.0}`

## Candidate Decisions

### pointwise_catboost_v5
- Publish allowed: `False`
- Failed checks: `base_shadow_publish_gate_passed, top_3_hit_rate_at_least_release_floor, top_3_hit_rate_not_below_reference`
- Base rejection reasons: `top_3_hit_rate_regressed`
- Candidate metrics: `{"mae": 1.22855, "ndcg_at_10": 0.998374, "rmse": 1.874197, "spearman_mean": 0.957788, "top_3_hit_rate": 0.6, "validation_queries": 20.0}`
- Metric deltas: `{"mae": -6.223816, "ndcg_at_10": 0.016936, "rmse": -8.791748, "spearman_mean": 0.447128, "top_3_hit_rate": -0.3}`
- Top feature: `intent_alignment_score` (`critical`)
- Critical/supporting drop: `18.3175` / `3.8108`
- Prediction bounds: `{"max_score": 82.529887, "min_score": 17.09084, "passed": true}`

### ranking_aware_catboost_v5
- Publish allowed: `False`
- Failed checks: `base_shadow_publish_gate_passed, top_3_hit_rate_at_least_release_floor, top_3_hit_rate_not_below_reference, mae_comparable_or_better`
- Base rejection reasons: `top_3_hit_rate_regressed, rmse_not_comparable, mae_not_comparable`
- Candidate metrics: `{"mae": 14.448487, "ndcg_at_10": 0.995447, "rmse": 17.613531, "spearman_mean": 0.889367, "top_3_hit_rate": 0.55, "validation_queries": 20.0}`
- Metric deltas: `{"mae": 6.996121, "ndcg_at_10": 0.014009, "rmse": 6.947586, "spearman_mean": 0.378707, "top_3_hit_rate": -0.35}`
- Top feature: `navigational_intent_alignment` (`critical`)
- Critical/supporting drop: `45.5185` / `10.9712`
- Prediction bounds: `{"max_score": 96.94513, "min_score": 0.0, "passed": true}`

### hybrid_catboost_ranker_v5
- Publish allowed: `False`
- Failed checks: `base_shadow_publish_gate_passed, top_3_hit_rate_at_least_release_floor, top_3_hit_rate_not_below_reference`
- Base rejection reasons: `top_3_hit_rate_regressed`
- Candidate metrics: `{"mae": 2.816326, "ndcg_at_10": 0.998127, "rmse": 3.525109, "spearman_mean": 0.953195, "top_3_hit_rate": 0.65, "validation_queries": 20.0}`
- Metric deltas: `{"mae": -4.63604, "ndcg_at_10": 0.016689, "rmse": -7.140836, "spearman_mean": 0.442535, "top_3_hit_rate": -0.25}`
- Top feature: `intent_alignment_score` (`critical`)
- Critical/supporting drop: `23.2137` / `5.0996`
- Prediction bounds: `{"max_score": 85.12463, "min_score": 14.014489, "passed": true}`

## Verification

- Overall status: `passed`
- `D54 targeted pytest`: `passed`
- `D50-D54 ML regression set`: `passed`

## Interpretation

D54 is a release gate. If the decision is `keep_current`, D53 artifacts remain non-production evidence and the active runtime artifact is unchanged.
