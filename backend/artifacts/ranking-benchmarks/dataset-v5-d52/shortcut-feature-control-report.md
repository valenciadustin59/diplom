# D52 Shortcut Feature Control Report

- Decision: `ready_for_d53`
- Production SHA1 before: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Production SHA1 after: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Feature policy: `v5-shortcut-control-v1`
- Controlled dataset: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v5\dataset.controlled.csv`
- Rows: `885`
- Shortcut features changed: `22`
- Shortcut row changes total: `7733`

## Feature Groups

- `critical`: `41`
- `important`: `69`
- `supporting`: `38`

## Candidate Guardrails

### pointwise_random_forest
- Passed: `True`
- Failed checks: `none`
- Top feature: `informational_intent_alignment` (`critical`)
- Supporting top-10 share: `0.0`
- Avg critical/supporting drop: `32.3559` / `5.6314`

### pointwise_catboost
- Passed: `False`
- Failed checks: `feature_dominance_passed`
- Top feature: `word_count` (`supporting`)
- Supporting top-10 share: `0.280158`
- Avg critical/supporting drop: `19.2439` / `3.6276`

### catboost_ranker
- Passed: `True`
- Failed checks: `none`
- Top feature: `canonical_signal_score` (`critical`)
- Supporting top-10 share: `0.0`
- Avg critical/supporting drop: `0.8834` / `0.1342`
