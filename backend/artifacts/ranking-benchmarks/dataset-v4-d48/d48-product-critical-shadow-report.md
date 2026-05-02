# D48 Product-Critical Shadow Benchmark

- Dataset: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v4\dataset.csv`
- Decision: `keep_current`
- Selected candidate: `None`
- Reason: `no_candidate_passed_product_critical_guardrails`
- Production artifact changed by D48: `False`

## Reference Metrics

- MAE: `8.113452`
- Spearman: `0.415837`
- NDCG@10: `0.97438`
- Top-3 hit rate: `0.95`

## Candidate Guardrails

### pointwise_random_forest
- Shadow gate passed: `False`
- Product gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed`
- Product failed checks: `base_shadow_publish_gate_passed`
- MAE: `1.878591`
- Spearman: `0.918117`
- NDCG@10: `0.996819`
- Top-3 hit rate: `0.6`
- Delta `spearman_mean`: `0.50228`
- Delta `ndcg_at_10`: `0.022439`
- Delta `top_3_hit_rate`: `-0.35`
- Delta `rmse`: `-9.417723`
- Delta `mae`: `-6.234861`
- Top feature: `informational_intent_alignment` (`critical`)
- Avg critical/supporting drop: `34.5498` / `5.763`

### pointwise_catboost
- Shadow gate passed: `False`
- Product gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed`
- Product failed checks: `base_shadow_publish_gate_passed, feature_importance_seo_weighted`
- MAE: `1.231731`
- Spearman: `0.959054`
- NDCG@10: `0.998348`
- Top-3 hit rate: `0.65`
- Delta `spearman_mean`: `0.543217`
- Delta `ndcg_at_10`: `0.023968`
- Delta `top_3_hit_rate`: `-0.3`
- Delta `rmse`: `-10.131877`
- Delta `mae`: `-6.881721`
- Top feature: `word_count` (`supporting`)
- Avg critical/supporting drop: `21.3917` / `3.9823`

### catboost_ranker
- Shadow gate passed: `False`
- Product gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed, rmse_not_comparable, mae_not_comparable, ranking_family_absolute_error_not_viable`
- Product failed checks: `base_shadow_publish_gate_passed`
- MAE: `66.10666`
- Spearman: `0.911027`
- NDCG@10: `0.996435`
- Top-3 hit rate: `0.7`
- Delta `spearman_mean`: `0.49519`
- Delta `ndcg_at_10`: `0.022055`
- Delta `top_3_hit_rate`: `-0.25`
- Delta `rmse`: `55.89217`
- Delta `mae`: `57.993208`
- Top feature: `canonical_signal_score` (`critical`)
- Avg critical/supporting drop: `0.8909` / `0.1436`

## Interpretation

D48 is a release gate, not a training step. If the recommendation is `keep_current`, D49 should record a controlled no-publish decision instead of replacing the runtime model.
