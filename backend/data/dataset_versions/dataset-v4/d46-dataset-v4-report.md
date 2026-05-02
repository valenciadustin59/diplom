# D46 Dataset v4 Build And Validation

- Source dataset: `dataset-v3-d37`
- Output dataset: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v4\dataset.csv`
- Labels: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v4\expert_labels.csv`
- Rows: `885`
- Label schema: `seo-weighted-v4`
- Target policy: `target_score_equals_d45_seo_weighted_expert_label`
- Manifest ready for training: `True`
- Split leakage check: `passed`
- Production artifact changed by D46: `False`

## Label Application

- Labels loaded: `885`
- Labels applied: `885`
- Missing labels: `0`
- Unmatched labels: `0`

## New Target Score Distribution

- `min`: `13.7`
- `p25`: `66.2`
- `mean`: `68.1355`
- `p50`: `72.2`
- `p75`: `76.3`
- `max`: `87.2`

## Label Evidence

- Label sources: `{'seo_weighted_rubric_v4': 885}`
- Quality bands: `{'blocked': 77, 'high': 2, 'low': 102, 'medium': 704}`

## Split

- Mode: `group_by_query`
- Train queries: `79`
- Validation queries: `20`
- Query overlap: `0`
