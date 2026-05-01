# D35 Shadow Benchmark And Guardrails

- Dataset path: `data\dataset_versions\dataset-v2\dataset.csv`
- Dataset version: `dataset-v2`
- Split mode: `group_by_query`
- Validation rows: `190`
- Publish recommendation: `keep_reference`
- Decision reason: `no_candidate_passed_all_publish_gates`

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
- Spearman mean: `0.398474`
- NDCG@10: `0.942676`
- Top-3 hit rate: `0.8`
- MAE: `12.380441`
- Delta `spearman_mean`: `0.24487`
- Delta `ndcg_at_10`: `0.033374`
- Delta `top_3_hit_rate`: `-0.15`
- Delta `rmse`: `-12.671397`
- Delta `mae`: `-11.478316`

### pointwise_catboost
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed`
- Spearman mean: `0.404524`
- NDCG@10: `0.947887`
- Top-3 hit rate: `0.8`
- MAE: `12.003497`
- Delta `spearman_mean`: `0.25092`
- Delta `ndcg_at_10`: `0.038585`
- Delta `top_3_hit_rate`: `-0.15`
- Delta `rmse`: `-13.000079`
- Delta `mae`: `-11.85526`

### catboost_ranker
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed, rmse_not_comparable, mae_not_comparable, ranking_family_absolute_error_not_viable`
- Spearman mean: `0.379091`
- NDCG@10: `0.938496`
- Top-3 hit rate: `0.8`
- MAE: `72.250466`
- Delta `spearman_mean`: `0.225487`
- Delta `ndcg_at_10`: `0.029194`
- Delta `top_3_hit_rate`: `-0.15`
- Delta `rmse`: `46.752769`
- Delta `mae`: `48.391709`

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
