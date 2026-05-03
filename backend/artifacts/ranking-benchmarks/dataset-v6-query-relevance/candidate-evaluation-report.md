# Dataset v6 query relevance candidate

## Dataset

- Dataset version: `dataset-v6-query-relevance`
- Rows: `1814`
- Queries: `200/200`
- Categories: `20`
- Domains: `1134`
- Failures: `130`
- Failure rate: `0.066872`
- Split: `group_by_query`
- Train / validation: `1457 / 357` rows
- Train / validation queries: `160 / 40`

## Training

- Production artifact was not replaced.
- Candidate artifact: `backend/artifacts/page_quality_model.dataset-v6-query-relevance-candidate.pkl`
- Selected candidate: `RandomForestRegressor`
- Schema: `v3`
- Features: `148`

## Validation Metrics

| Model | MAE | RMSE | Spearman | NDCG@10 | Top-3 hit rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| dataset-v6 candidate RF | `16.759190` | `20.984378` | `0.300122` | `0.919595` | `0.950000` |
| dataset-v6 candidate CatBoost benchmark | `16.752985` | `21.059531` | `0.275583` | `0.919969` | `0.925000` |
| current production v5 | `24.224482` | `30.063137` | `-0.022147` | `0.863113` | `0.825000` |

## Decision

The dataset-v6 candidate is useful evidence: on this new 200-query validation slice it beats the current v5 runtime on MAE, RMSE, Spearman, NDCG@10 and top-3 hit rate.

It is not published yet. The dataset is still weak-SERP labeled, so the next hardening step should add explicit cross-category hard negatives from the query relevance catalog before any controlled publish decision.
