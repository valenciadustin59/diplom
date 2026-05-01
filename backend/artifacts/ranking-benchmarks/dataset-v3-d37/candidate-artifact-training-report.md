# Candidate Artifact Training Report

- Dataset path: `data\dataset_versions\dataset-v3-d37\dataset.csv`
- Dataset version: `dataset-v3-d37`
- Model schema version: `v3`
- Feature count: `148`
- Rows: `885`
- Queries: `99`
- Split mode: `group_by_query`
- Validation rows: `190`

## Reference Artifact

- Path: `artifacts\page_quality_model.pkl`
- SHA1: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`

## Saved Artifacts

- `pointwise_random_forest`: `artifacts\page_quality_model.dataset-v3-d37-rf-candidate.pkl`
- `pointwise_catboost`: `artifacts\page_quality_model.dataset-v3-d37-catboost-candidate.pkl`
- `catboost_ranker`: `artifacts\page_quality_model.dataset-v3-d37-ranking-candidate.pkl`

## Candidates

### pointwise_random_forest
- Family: `pointwise`
- Status: `available`
- Model path: `artifacts\page_quality_model.dataset-v3-d37-rf-candidate.pkl`
- Model type: `RandomForestRegressor`
- RMSE: `15.182424`
- MAE: `12.27095`
- NDCG@10: `0.941689`
- Top-3 hit rate: `0.8`
- Spearman mean: `0.39803`

### pointwise_catboost
- Family: `pointwise`
- Status: `available`
- Model path: `artifacts\page_quality_model.dataset-v3-d37-catboost-candidate.pkl`
- Model type: `CatBoostRegressor`
- RMSE: `14.865537`
- MAE: `11.774165`
- NDCG@10: `0.945929`
- Top-3 hit rate: `0.95`
- Spearman mean: `0.421894`

### catboost_ranker
- Family: `ranking`
- Status: `available`
- Model path: `artifacts\page_quality_model.dataset-v3-d37-ranking-candidate.pkl`
- Model type: `CatBoostRanker`
- RMSE: `74.747766`
- MAE: `72.26261`
- NDCG@10: `0.934413`
- Top-3 hit rate: `0.75`
- Spearman mean: `0.37355`

### lightgbm_ranker
- Family: `ranking`
- Status: `unavailable`
- Model path: `None`
- Model type: `None`
- RMSE: `None`
- MAE: `None`
- NDCG@10: `None`
- Top-3 hit rate: `None`
- Spearman mean: `None`
- Reason: `lightgbm_not_installed`

### xgboost_rank_pairwise
- Family: `ranking`
- Status: `unavailable`
- Model path: `None`
- Model type: `None`
- RMSE: `None`
- MAE: `None`
- NDCG@10: `None`
- Top-3 hit rate: `None`
- Spearman mean: `None`
- Reason: `xgboost_not_installed`

## Best Pointwise Candidate

- Candidate: `pointwise_catboost`
- Family: `pointwise`
- Model path: `artifacts\page_quality_model.dataset-v3-d37-catboost-candidate.pkl`
- NDCG@10: `0.945929`
- Top-3 hit rate: `0.95`
- Spearman mean: `0.421894`

## Best Ranking Candidate

- Candidate: `catboost_ranker`
- Family: `ranking`
- Model path: `artifacts\page_quality_model.dataset-v3-d37-ranking-candidate.pkl`
- NDCG@10: `0.934413`
- Top-3 hit rate: `0.75`
- Spearman mean: `0.37355`

## Best Overall Candidate

- Candidate: `pointwise_catboost`
- Family: `pointwise`
- Model path: `artifacts\page_quality_model.dataset-v3-d37-catboost-candidate.pkl`
- NDCG@10: `0.945929`
- Top-3 hit rate: `0.95`
- Spearman mean: `0.421894`
