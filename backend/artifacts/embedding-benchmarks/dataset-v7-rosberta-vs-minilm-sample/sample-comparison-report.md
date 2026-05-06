# RoSBERTa vs current MiniLM sample comparison

Generated: `2026-05-05T16:30:02Z`
Sample: `226` rows / `90` queries

| Model | AUC | Query top1 | Pairwise acc | Mean margin | Spearman relevance | Encode sec |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ru_en_rosberta | 0.97451 | 0.955556 | 0.970588 | 0.239642 | 0.816753 | 413.004 |
| current_minilm | 0.961275 | 0.933333 | 0.948529 | 0.357147 | 0.823493 | 9.785 |

## Decision

RoSBERTa improves binary separation on this sample, but needs more validation because pairwise/query-level gains are not decisive.
