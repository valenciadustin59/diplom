# D34 Candidate Artifact Training Report

- Dataset path: `data\dataset_versions\dataset-v2\dataset.csv`
- Dataset version: `dataset-v2`
- Model schema version: `v2`
- Feature count: `108`
- Rows: `885`
- Queries: `99`
- Split mode: `group_by_query`
- Validation rows: `190`

## Reference Artifact

- Path: `artifacts\page_quality_model.pkl`
- SHA1: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`

## Saved Artifacts

- `pointwise_random_forest`: `artifacts\page_quality_model.dataset-v2-expert-rf-candidate.pkl`
- `pointwise_catboost`: `artifacts\page_quality_model.dataset-v2-expert-catboost-candidate.pkl`
- `catboost_ranker`: `artifacts\page_quality_model.dataset-v2-ranking-candidate.pkl`

## Candidates

### pointwise_random_forest
- Family: `pointwise`
- Status: `available`
- Model path: `artifacts\page_quality_model.dataset-v2-expert-rf-candidate.pkl`
- Model type: `RandomForestRegressor`
- RMSE: `15.309359`
- MAE: `12.380441`
- NDCG@10: `0.942676`
- Top-3 hit rate: `0.8`
- Spearman mean: `0.398474`

### pointwise_catboost
- Family: `pointwise`
- Status: `available`
- Model path: `artifacts\page_quality_model.dataset-v2-expert-catboost-candidate.pkl`
- Model type: `CatBoostRegressor`
- RMSE: `14.980677`
- MAE: `12.003497`
- NDCG@10: `0.947887`
- Top-3 hit rate: `0.8`
- Spearman mean: `0.404524`

### catboost_ranker
- Family: `ranking`
- Status: `available`
- Model path: `artifacts\page_quality_model.dataset-v2-ranking-candidate.pkl`
- Model type: `CatBoostRanker`
- RMSE: `74.733525`
- MAE: `72.250466`
- NDCG@10: `0.938496`
- Top-3 hit rate: `0.8`
- Spearman mean: `0.379091`

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
- Model path: `artifacts\page_quality_model.dataset-v2-expert-catboost-candidate.pkl`
- NDCG@10: `0.947887`
- Top-3 hit rate: `0.8`
- Spearman mean: `0.404524`

## Best Ranking Candidate

- Candidate: `catboost_ranker`
- Family: `ranking`
- Model path: `artifacts\page_quality_model.dataset-v2-ranking-candidate.pkl`
- NDCG@10: `0.938496`
- Top-3 hit rate: `0.8`
- Spearman mean: `0.379091`

## Best Overall Candidate

- Candidate: `pointwise_catboost`
- Family: `pointwise`
- Model path: `artifacts\page_quality_model.dataset-v2-expert-catboost-candidate.pkl`
- NDCG@10: `0.947887`
- Top-3 hit rate: `0.8`
- Spearman mean: `0.404524`
