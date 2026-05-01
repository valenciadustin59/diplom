# Ranking Benchmark Report

- Dataset path: `data\dataset_versions\dataset-v2\dataset.csv`
- Dataset version: `dataset-v2`
- Model schema version: `v2`
- Feature count: `108`
- Split mode: `group_by_query`
- Validation rows: `190`

## Reference Baseline

- Artifact version: `ru_commercial_dataset-20260421-primary-20260421174901`
- Model type: `RandomForestRegressor`
- Dataset version: `ru_commercial_dataset-20260421-primary`
- NDCG@10: `0.948054`
- Top-3 hit rate: `0.95`
- Spearman mean: `0.336558`

## Ranking Candidates

### candidate_artifact
- Status: `available`
- Model type: `RandomForestRegressor`
- NDCG@10: `0.939192`
- Top-3 hit rate: `0.9`
- Spearman mean: `0.282468`
- Query-group NDCG stddev: `0.036044`
- Intent NDCG stddev: `0.011966`
- Top features:
  - `unique_word_ratio`: `0.050089`
  - `avg_word_length`: `0.03831`
  - `unique_word_count`: `0.034375`
  - `semantic_content_richness`: `0.026692`
  - `word_count`: `0.026294`

### catboost_ranker
- Status: `available`
- Model type: `CatBoostRanker`
- NDCG@10: `0.937031`
- Top-3 hit rate: `0.85`
- Spearman mean: `0.235887`
- Query-group NDCG stddev: `0.032451`
- Intent NDCG stddev: `0.011404`
- Top features:
  - `avg_word_length`: `11.081557`
  - `faq_present`: `6.928751`
  - `unique_word_count`: `6.592439`
  - `unique_word_ratio`: `6.434159`
  - `word_count`: `6.266142`

### lightgbm_ranker
- Status: `unavailable`
- Model type: `None`
- NDCG@10: `None`
- Top-3 hit rate: `None`
- Spearman mean: `None`
- Query-group NDCG stddev: `None`
- Intent NDCG stddev: `None`
- Reason: `lightgbm_not_installed`

### xgboost_rank_pairwise
- Status: `unavailable`
- Model type: `None`
- NDCG@10: `None`
- Top-3 hit rate: `None`
- Spearman mean: `None`
- Query-group NDCG stddev: `None`
- Intent NDCG stddev: `None`
- Reason: `xgboost_not_installed`

## Selected Candidate

- Candidate: `candidate_artifact`
- Model type: `RandomForestRegressor`
- NDCG@10: `0.939192`
- Top-3 hit rate: `0.9`
- Spearman mean: `0.282468`

## Comparison To Reference

- Publish recommendation: `keep_reference`
- Candidate outperforms reference: `False`
- `spearman_mean`: `-0.05409`
- `ndcg_at_10`: `-0.008862`
- `top_3_hit_rate`: `-0.05`
- `rmse`: `-11.412967`
- `mae`: `-9.769919`

## Candidate Artifact Comparison To Reference

- Publish recommendation: `keep_reference`
- Candidate outperforms reference: `False`
- `spearman_mean`: `-0.05409`
- `ndcg_at_10`: `-0.008862`
- `top_3_hit_rate`: `-0.05`
- `rmse`: `-11.412967`
- `mae`: `-9.769919`
