# D47 SEO-Weighted Candidate Training

- Dataset: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v4\dataset.csv`
- Dataset version: `dataset-v4`
- Label schema: `seo-weighted-v4`
- Target policy: `target_score_equals_d45_seo_weighted_expert_label`
- Model schema: `v3`
- Feature count: `148`
- Production artifact changed: `False`

## Saved Non-Production Artifacts

### pointwise_random_forest
- Artifact: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-rf-candidate.pkl`
- Metadata: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-rf-candidate.metadata.json`
- SHA1: `6ff84515690e07c2f0b5daa141deede491bd0c9d`
- Compatibility passed: `True`

### pointwise_catboost
- Artifact: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-catboost-candidate.pkl`
- Metadata: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-catboost-candidate.metadata.json`
- SHA1: `24b774fea9402478223a6ab1d87b0758efd6d131`
- Compatibility passed: `True`

### catboost_ranker
- Artifact: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-ranking-candidate.pkl`
- Metadata: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v4-seo-weighted-ranking-candidate.metadata.json`
- SHA1: `e7af615565ddec429fa592c1a8f9418bbba26471`
- Compatibility passed: `True`

## Candidate Decisions

### pointwise_random_forest
- Decision: `trained_for_d48_shadow_benchmark`
- Reason: `artifact_saved_as_non_production_candidate`
- RMSE: `2.556254`
- MAE: `1.878591`
- NDCG@10: `0.996819`
- Top-3 hit rate: `0.6`
- Spearman mean: `0.918117`

### pointwise_catboost
- Decision: `trained_for_d48_shadow_benchmark`
- Reason: `artifact_saved_as_non_production_candidate`
- RMSE: `1.8421`
- MAE: `1.231731`
- NDCG@10: `0.998348`
- Top-3 hit rate: `0.65`
- Spearman mean: `0.959054`

### catboost_ranker
- Decision: `trained_for_d48_shadow_benchmark`
- Reason: `artifact_saved_as_non_production_candidate`
- RMSE: `67.866147`
- MAE: `66.10666`
- NDCG@10: `0.996435`
- Top-3 hit rate: `0.7`
- Spearman mean: `0.911027`

### lightgbm_ranker
- Decision: `not_trained`
- Reason: `lightgbm_not_installed`
- RMSE: `None`
- MAE: `None`
- NDCG@10: `None`
- Top-3 hit rate: `None`
- Spearman mean: `None`

### xgboost_rank_pairwise
- Decision: `not_trained`
- Reason: `xgboost_not_installed`
- RMSE: `None`
- MAE: `None`
- NDCG@10: `None`
- Top-3 hit rate: `None`
- Spearman mean: `None`

## Next Step

D47 is not a publish decision. D48 must compare these candidates against the current production artifact with product-critical guardrails before D49 can publish or explicitly keep the current model.
