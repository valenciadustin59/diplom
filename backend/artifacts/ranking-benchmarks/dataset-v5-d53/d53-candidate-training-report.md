# D53 Ranking-Aware v5 Candidate Training

- Dataset: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v5\dataset.controlled.csv`
- Dataset version: `dataset-v5`
- Feature policy: `v5-shortcut-control-v1`
- Model schema: `v3`
- Feature count: `148`
- Production artifact changed: `False`

## Saved Non-Production Artifacts

### pointwise_catboost_v5
- Artifact: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v5-pointwise-catboost-candidate.pkl`
- Metadata: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v5-pointwise-catboost-candidate.metadata.json`
- SHA1: `3e53b54fdd4b05bfbc6e23e35024584e5f7066f8`
- Compatibility passed: `True`

### ranking_aware_catboost_v5
- Artifact: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v5-ranking-aware-catboost-candidate.pkl`
- Metadata: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v5-ranking-aware-catboost-candidate.metadata.json`
- SHA1: `50dcf8120cc829fcee43dd1a035f5fcc0c60560e`
- Compatibility passed: `True`

### hybrid_catboost_ranker_v5
- Artifact: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v5-hybrid-candidate.pkl`
- Metadata: `E:\codexPROJ\diplom\backend\artifacts\page_quality_model.dataset-v5-hybrid-candidate.metadata.json`
- SHA1: `9b43a3ec65e72c584e720052d3d228de2e1ee9ae`
- Compatibility passed: `True`

## Candidates

### pointwise_catboost_v5
- Status: `available`
- Family: `pointwise`
- Model type: `CatBoostRegressor`
- RMSE: `1.874197`
- MAE: `1.22855`
- Spearman: `0.957788`
- NDCG@10: `0.998374`
- Top-3 hit rate: `0.6`
- Preference accuracy: `0.784322`
- Reason: `none`

### ranking_aware_catboost_v5
- Status: `available`
- Family: `ranking`
- Model type: `V5CalibratedRankerModel`
- RMSE: `17.613531`
- MAE: `14.448487`
- Spearman: `0.889367`
- NDCG@10: `0.995447`
- Top-3 hit rate: `0.55`
- Preference accuracy: `0.797401`
- Reason: `none`

### hybrid_catboost_ranker_v5
- Status: `available`
- Family: `hybrid`
- Model type: `V5HybridRankerModel`
- RMSE: `3.525109`
- MAE: `2.816326`
- Spearman: `0.953195`
- NDCG@10: `0.998127`
- Top-3 hit rate: `0.65`
- Preference accuracy: `0.788169`
- Reason: `none`

## Best Validation Candidate

- Candidate: `pointwise_catboost_v5`
- Family: `pointwise`

D53 is not a publish decision. D54 must compare these artifacts against the current production model with release guardrails before any publish/no-publish decision.
