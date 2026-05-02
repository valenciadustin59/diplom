# D49 No-Publish Decision

- Decision: `keep_current`
- Publish action: `no_publish`
- Reason: `d48_no_candidate_passed_product_critical_guardrails`
- D48 recommendation: `keep_current`
- D48 reason: `no_candidate_passed_product_critical_guardrails`
- Production SHA1 before: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Production SHA1 after: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Production artifact unchanged: `True`

## Selected Runtime Artifact

- Path: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.pkl`
- SHA1: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Artifact version: `dataset-v3-d37-20260501200434`
- Dataset version: `dataset-v3-d37`
- Model schema version: `v3`
- Model type: `CatBoostRegressor`
- Feature count: `148`

## D48 Evidence

- D48 report: `E:\codexPROJ\diplom\backend\artifacts\ranking-benchmarks\dataset-v4-d48\d48-product-critical-shadow-report.json`
- Dataset version: `dataset-v4`
- Reference metrics: `{"mae": 8.113452, "ndcg_at_10": 0.97438, "rmse": 11.973977, "spearman_mean": 0.415837, "top_3_hit_rate": 0.95, "validation_queries": 20.0}`
- D48 decision: `{"publish_recommendation": "keep_current", "reason": "no_candidate_passed_product_critical_guardrails", "selected_candidate": null}`

## Candidate Decisions

### pointwise_random_forest
- Publish allowed: `False`
- Shadow gate passed: `False`
- Product gate passed: `False`
- Base rejection reasons: `top_3_hit_rate_regressed`
- Product failed checks: `base_shadow_publish_gate_passed`
- Candidate metrics: `{"mae": 1.878591, "ndcg_at_10": 0.996819, "rmse": 2.556254, "spearman_mean": 0.918117, "top_3_hit_rate": 0.6, "validation_queries": 20.0}`
- Metric deltas: `{"mae": -6.234861, "ndcg_at_10": 0.022439, "rmse": -9.417723, "spearman_mean": 0.50228, "top_3_hit_rate": -0.35}`
- Top feature: `informational_intent_alignment` (`critical`)
- Critical/supporting drop: `34.5498` / `5.763`

### pointwise_catboost
- Publish allowed: `False`
- Shadow gate passed: `False`
- Product gate passed: `False`
- Base rejection reasons: `top_3_hit_rate_regressed`
- Product failed checks: `base_shadow_publish_gate_passed, feature_importance_seo_weighted`
- Candidate metrics: `{"mae": 1.231731, "ndcg_at_10": 0.998348, "rmse": 1.8421, "spearman_mean": 0.959054, "top_3_hit_rate": 0.65, "validation_queries": 20.0}`
- Metric deltas: `{"mae": -6.881721, "ndcg_at_10": 0.023968, "rmse": -10.131877, "spearman_mean": 0.543217, "top_3_hit_rate": -0.3}`
- Top feature: `word_count` (`supporting`)
- Critical/supporting drop: `21.3917` / `3.9823`

### catboost_ranker
- Publish allowed: `False`
- Shadow gate passed: `False`
- Product gate passed: `False`
- Base rejection reasons: `top_3_hit_rate_regressed, rmse_not_comparable, mae_not_comparable, ranking_family_absolute_error_not_viable`
- Product failed checks: `base_shadow_publish_gate_passed`
- Candidate metrics: `{"mae": 66.10666, "ndcg_at_10": 0.996435, "rmse": 67.866147, "spearman_mean": 0.911027, "top_3_hit_rate": 0.7, "validation_queries": 20.0}`
- Metric deltas: `{"mae": 57.993208, "ndcg_at_10": 0.022055, "rmse": 55.89217, "spearman_mean": 0.49519, "top_3_hit_rate": -0.25}`
- Top feature: `canonical_signal_score` (`critical`)
- Critical/supporting drop: `0.8909` / `0.1436`

## Rollback Reference

- Rollback required: `False`
- Reason: D49 did not publish a dataset-v4 candidate; the current production alias remains selected.
- Current alias path: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.pkl`
- Current alias SHA1: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Versioned reference path: `E:\codexPROJ\diplom\backend\artifacts\versions\page_quality_model--dataset-v3-d37-20260501200434.pkl`
- Versioned reference available: `True`

## Verification

- Overall status: `passed`
- `D49 targeted no-publish tests`: `passed`
- `D45-D49 ML regression set (48 tests)`: `passed`
- `D48 product-critical evidence review`: `passed`
