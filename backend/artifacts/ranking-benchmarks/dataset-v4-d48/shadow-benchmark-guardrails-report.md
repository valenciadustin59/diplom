# Shadow Benchmark And Guardrails

- Dataset path: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v4\dataset.csv`
- Dataset version: `dataset-v4`
- Split mode: `group_by_query`
- Validation rows: `190`
- Publish recommendation: `keep_reference`
- Decision reason: `no_candidate_passed_all_publish_gates`

## Reference

- Path: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.pkl`
- Model type: `CatBoostRegressor`
- Spearman mean: `0.415837`
- NDCG@10: `0.97438`
- Top-3 hit rate: `0.95`
- MAE: `8.113452`

## Candidate Gate Results

### pointwise_random_forest
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed`
- Spearman mean: `0.918117`
- NDCG@10: `0.996819`
- Top-3 hit rate: `0.6`
- MAE: `1.878591`
- Delta `spearman_mean`: `0.50228`
- Delta `ndcg_at_10`: `0.022439`
- Delta `top_3_hit_rate`: `-0.35`
- Delta `rmse`: `-9.417723`
- Delta `mae`: `-6.234861`

### pointwise_catboost
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed`
- Spearman mean: `0.959054`
- NDCG@10: `0.998348`
- Top-3 hit rate: `0.65`
- MAE: `1.231731`
- Delta `spearman_mean`: `0.543217`
- Delta `ndcg_at_10`: `0.023968`
- Delta `top_3_hit_rate`: `-0.3`
- Delta `rmse`: `-10.131877`
- Delta `mae`: `-6.881721`

### catboost_ranker
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed, rmse_not_comparable, mae_not_comparable, ranking_family_absolute_error_not_viable`
- Spearman mean: `0.911027`
- NDCG@10: `0.996435`
- Top-3 hit rate: `0.7`
- MAE: `66.10666`
- Delta `spearman_mean`: `0.49519`
- Delta `ndcg_at_10`: `0.022055`
- Delta `top_3_hit_rate`: `-0.25`
- Delta `rmse`: `55.89217`
- Delta `mae`: `57.993208`

## Smoke Explainability

- Requested queries: `4`
- Covered queries: `4`
- Exact query matches: `4`
- Fallback query matches: `0`
- Missing queries: `0`

- `ремонт квартир Екатеринбург` -> `ремонт квартир Екатеринбург` (exact_casefold, `covered`)
- `пластиковые окна Самара` -> `пластиковые окна Самара` (exact_casefold, `covered`)
- `кухни на заказ Екатеринбург` -> `кухни на заказ Екатеринбург` (exact_casefold, `covered`)
- `натяжные потолки Москва` -> `натяжные потолки Москва` (exact_casefold, `covered`)

## Explainability Sensibility

- Passed: `True`
- Heuristic: Top features must be non-empty, finite and include at least one known SEO signal; smoke explanations must be present, bounded and include known explanation factor keys.
- `pointwise_random_forest`: passed `True`, failed checks `none`
- `pointwise_catboost`: passed `True`, failed checks `none`
- `catboost_ranker`: passed `True`, failed checks `none`
