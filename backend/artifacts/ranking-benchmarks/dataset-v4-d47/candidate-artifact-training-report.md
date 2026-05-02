# Candidate Artifact Training Report

- Dataset path: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v4\dataset.csv`
- Dataset version: `dataset-v4`
- Model schema version: `v3`
- Feature count: `148`
- Rows: `885`
- Queries: `99`
- Split mode: `group_by_query`
- Validation rows: `190`

## Reference Artifact

- Path: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.pkl`
- SHA1: `29c4b29455f795a535da94b2c6f36ef603d003eb`

## Saved Artifacts

- `pointwise_random_forest`: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-rf-candidate.pkl`
- `pointwise_catboost`: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-catboost-candidate.pkl`
- `catboost_ranker`: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-ranking-candidate.pkl`

## Candidates

### pointwise_random_forest
- Family: `pointwise`
- Status: `available`
- Model path: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-rf-candidate.pkl`
- Model type: `RandomForestRegressor`
- RMSE: `2.556254`
- MAE: `1.878591`
- NDCG@10: `0.996819`
- Top-3 hit rate: `0.6`
- Spearman mean: `0.918117`

### pointwise_catboost
- Family: `pointwise`
- Status: `available`
- Model path: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-catboost-candidate.pkl`
- Model type: `CatBoostRegressor`
- RMSE: `1.8421`
- MAE: `1.231731`
- NDCG@10: `0.998348`
- Top-3 hit rate: `0.65`
- Spearman mean: `0.959054`

### catboost_ranker
- Family: `ranking`
- Status: `available`
- Model path: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-ranking-candidate.pkl`
- Model type: `CatBoostRanker`
- RMSE: `67.866147`
- MAE: `66.10666`
- NDCG@10: `0.996435`
- Top-3 hit rate: `0.7`
- Spearman mean: `0.911027`

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
- Model path: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-catboost-candidate.pkl`
- NDCG@10: `0.998348`
- Top-3 hit rate: `0.65`
- Spearman mean: `0.959054`

## Best Ranking Candidate

- Candidate: `catboost_ranker`
- Family: `ranking`
- Model path: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-ranking-candidate.pkl`
- NDCG@10: `0.996435`
- Top-3 hit rate: `0.7`
- Spearman mean: `0.911027`

## Best Overall Candidate

- Candidate: `pointwise_catboost`
- Family: `pointwise`
- Model path: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-catboost-candidate.pkl`
- NDCG@10: `0.998348`
- Top-3 hit rate: `0.65`
- Spearman mean: `0.959054`
