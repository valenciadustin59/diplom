# RoSBERTa vs MiniLM detailed embedding comparison

Generated: `2026-05-05T16:04:37Z`
Dataset: `backend\data\dataset_versions\dataset-v7-final\dataset.query-core.csv`
Rows: `4876`, queries: `500`

## Ranking

| Model | Strict AUC | Hard-negative AUC | Query top1 | Pairwise acc | Spearman relevance | Encode sec |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ru_en_rosberta | 0.977467 | 0.995472 | 0.985972 | 0.979774 | 0.691252 | 6391.566 |
| current_minilm | 0.944602 | 0.955988 | 0.97996 | 0.950947 | 0.710988 | 141.707 |

## Decision

RoSBERTa is a promising semantic-signal candidate, but publish only after runtime calibration because it is slower and must be tested inside the full score guardrail.
