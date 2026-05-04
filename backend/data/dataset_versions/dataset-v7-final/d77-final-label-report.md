# D77 deterministic labels for dataset-v7-final

- Dataset: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v7-final\dataset.with-hard-negatives.csv`
- Labeled dataset: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v7-final\dataset.labeled.csv`
- Rows: `4876`
- Regular rows: `3876`
- Hard negatives: `1000`
- Hard negative cap: `35.0`
- Hard negatives above cap: `0`
- Cap applications: `192`
- Label schema: `query-competitiveness-rubric-v1`
- Score contract: `query-competitiveness-final-v2`

## Score distribution

- all: count=4876.0, min=0.4081, p25=35.0, p50=55.7246, p75=62.46, p90=67.652, max=78.4448
- regular: count=3876.0, min=0.5006, p25=52.5945, p50=58.4474, p75=64.1527, p90=68.4463, max=78.4448
- hard_negative: count=1000.0, min=0.4081, p25=2.9563, p50=17.4971, p75=32.4512, p90=35.0, max=35.0

## Query relevance bands

- all: strong_match=3611, unusable=234, probable_mismatch=238, partial_match=311, full_mismatch=217, weak_match=73, hard_negative_cap=192
- hard_negative: probable_mismatch=214, weak_match=72, partial_match=266, unusable=52, full_mismatch=202, hard_negative_cap=192, strong_match=2
