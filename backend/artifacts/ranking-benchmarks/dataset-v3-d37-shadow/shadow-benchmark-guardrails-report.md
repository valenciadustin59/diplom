# Shadow Benchmark And Guardrails

- Dataset path: `data\dataset_versions\dataset-v3-d37\dataset.csv`
- Dataset version: `dataset-v3-d37`
- Split mode: `group_by_query`
- Validation rows: `190`
- Publish recommendation: `publish_candidate`
- Decision reason: `candidate_passed_all_publish_gates_and_outperformed_reference`

## Reference

- Path: `artifacts\page_quality_model.pkl`
- Model type: `RandomForestRegressor`
- Spearman mean: `0.153604`
- NDCG@10: `0.909302`
- Top-3 hit rate: `0.95`
- MAE: `23.858757`

## Candidate Gate Results

### pointwise_random_forest
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed`
- Spearman mean: `0.39803`
- NDCG@10: `0.941689`
- Top-3 hit rate: `0.8`
- MAE: `12.27095`
- Delta `spearman_mean`: `0.244426`
- Delta `ndcg_at_10`: `0.032387`
- Delta `top_3_hit_rate`: `-0.15`
- Delta `rmse`: `-12.798332`
- Delta `mae`: `-11.587807`

### pointwise_catboost
- Publish gate passed: `True`
- Rejection reasons: `none`
- Spearman mean: `0.421894`
- NDCG@10: `0.945929`
- Top-3 hit rate: `0.95`
- MAE: `11.774165`
- Delta `spearman_mean`: `0.26829`
- Delta `ndcg_at_10`: `0.036627`
- Delta `top_3_hit_rate`: `0.0`
- Delta `rmse`: `-13.115219`
- Delta `mae`: `-12.084592`

### catboost_ranker
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed, rmse_not_comparable, mae_not_comparable, ranking_family_absolute_error_not_viable`
- Spearman mean: `0.37355`
- NDCG@10: `0.934413`
- Top-3 hit rate: `0.75`
- MAE: `72.26261`
- Delta `spearman_mean`: `0.219946`
- Delta `ndcg_at_10`: `0.025111`
- Delta `top_3_hit_rate`: `-0.2`
- Delta `rmse`: `46.76701`
- Delta `mae`: `48.403853`

## Smoke Explainability

- Requested queries: `4`
- Covered queries: `4`
- Exact query matches: `3`
- Fallback query matches: `1`
- Missing queries: `0`

- `ремонт квартир москва` -> `ремонт квартир цена Москва` (contains_all_terms, `covered`)
- `пластиковые окна казань` -> `пластиковые окна Казань` (exact_casefold, `covered`)
- `кухни на заказ санкт-петербург` -> `кухни на заказ Санкт-Петербург` (exact_casefold, `covered`)
- `натяжные потолки новосибирск` -> `натяжные потолки Новосибирск` (exact_casefold, `covered`)

## Explainability Sensibility

- Passed: `True`
- Heuristic: Top features must be non-empty, finite and include at least one known SEO signal; smoke explanations must be present, bounded and include known explanation factor keys.
- `pointwise_random_forest`: passed `True`, failed checks `none`
- `pointwise_catboost`: passed `True`, failed checks `none`
- `catboost_ranker`: passed `True`, failed checks `none`
