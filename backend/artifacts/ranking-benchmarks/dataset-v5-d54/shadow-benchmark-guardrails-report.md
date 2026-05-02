# Shadow Benchmark And Guardrails

- Dataset path: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v5\dataset.controlled.csv`
- Dataset version: `dataset-v5`
- Split mode: `group_by_query`
- Validation rows: `190`
- Publish recommendation: `keep_reference`
- Decision reason: `no_candidate_passed_all_publish_gates`

## Reference

- Path: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.pkl`
- Model type: `CatBoostRegressor`
- Spearman mean: `0.51066`
- NDCG@10: `0.981438`
- Top-3 hit rate: `0.9`
- MAE: `7.452366`

## Candidate Gate Results

### pointwise_catboost_v5
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed`
- Spearman mean: `0.957788`
- NDCG@10: `0.998374`
- Top-3 hit rate: `0.6`
- MAE: `1.22855`
- Delta `spearman_mean`: `0.447128`
- Delta `ndcg_at_10`: `0.016936`
- Delta `top_3_hit_rate`: `-0.3`
- Delta `rmse`: `-8.791748`
- Delta `mae`: `-6.223816`

### ranking_aware_catboost_v5
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed, rmse_not_comparable, mae_not_comparable`
- Spearman mean: `0.889367`
- NDCG@10: `0.995447`
- Top-3 hit rate: `0.55`
- MAE: `14.448487`
- Delta `spearman_mean`: `0.378707`
- Delta `ndcg_at_10`: `0.014009`
- Delta `top_3_hit_rate`: `-0.35`
- Delta `rmse`: `6.947586`
- Delta `mae`: `6.996121`

### hybrid_catboost_ranker_v5
- Publish gate passed: `False`
- Rejection reasons: `top_3_hit_rate_regressed`
- Spearman mean: `0.953195`
- NDCG@10: `0.998127`
- Top-3 hit rate: `0.65`
- MAE: `2.816326`
- Delta `spearman_mean`: `0.442535`
- Delta `ndcg_at_10`: `0.016689`
- Delta `top_3_hit_rate`: `-0.25`
- Delta `rmse`: `-7.140836`
- Delta `mae`: `-4.63604`

## Smoke Explainability

- Requested queries: `4`
- Covered queries: `4`
- Exact query matches: `4`
- Fallback query matches: `0`
- Missing queries: `0`

- `натяжные потолки Москва` -> `натяжные потолки Москва` (exact_casefold, `covered`)
- `натяжные потолки Новосибирск` -> `натяжные потолки Новосибирск` (exact_casefold, `covered`)
- `натяжные потолки Казань` -> `натяжные потолки Казань` (exact_casefold, `covered`)
- `натяжные потолки отзывы` -> `натяжные потолки отзывы` (exact_casefold, `covered`)

## Explainability Sensibility

- Passed: `True`
- Heuristic: Top features must be non-empty, finite and include at least one known SEO signal; smoke explanations must be present, bounded and include known explanation factor keys.
- `pointwise_catboost_v5`: passed `True`, failed checks `none`
- `ranking_aware_catboost_v5`: passed `True`, failed checks `none`
- `hybrid_catboost_ranker_v5`: passed `True`, failed checks `none`
