# D80 Dataset-v7 Controlled Decision

## Goal

Run the final product guardrails for the D79 `dataset-v7-final` candidate before any runtime publish. D80 is a release gate, not a publish step.

## Inputs

- `backend/data/dataset_versions/dataset-v7-final/dataset.labeled.csv`
- `backend/data/dataset_versions/dataset-v7-final/split.json`
- `backend/artifacts/page_quality_model.dataset-v7-final-candidate.pkl`
- Current production alias: `backend/artifacts/page_quality_model.pkl`

## Result

D80 decision is `no_publish`.

The candidate clearly improves validation fit versus the current runtime under the v7 target:

- Runtime-adjusted candidate MAE: `2.387708`
- Runtime-adjusted reference MAE: `6.322645`
- Runtime-adjusted candidate Spearman: `0.930727`
- Runtime-adjusted candidate NDCG@10: `0.996701`

But the candidate failed the product hard-negative guardrail:

- `hard_negatives_learned_below_cap=false`
- `25` validation hard-negative rows were predicted above the `35.0` cap
- worst raw hard-negative prediction: `67.1677`

This is a real release blocker because the final product goal is query competitiveness: a technically decent page from the wrong topic must not receive a medium/high score just because shared modifier words such as "для бизнеса", "как выбрать" or "с гарантией" appear.

## Evidence

- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d80/d80-controlled-decision-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d80/d80-controlled-decision-report.md`

## Next Step

D81 must record the controlled no-publish decision and keep the current production artifact unchanged.
