# D76 Dataset-v7 Hard Negatives

## Goal

Materialize hard negatives for `dataset-v7-final` from saved D75 extraction snapshots. The point is to teach the final relevance-first model that a technically good page from another topic must still score low for the wrong query.

## Status

Status: `completed_locally`.

D76 generated:

- `3876` original raw rows.
- `1000` hard-negative rows.
- `4876` total rows in `dataset.with-hard-negatives.csv`.
- `500/500` target queries with hard negatives.
- Exactly `2` hard negatives per target query.
- `50/50` target categories covered.
- `50/50` source categories covered.
- `0` same-category hard-negative pairs.
- `0` missing snapshot artifacts.

## Evidence

- `backend/data/dataset_versions/dataset-v7-final/dataset.with-hard-negatives.csv`
- `backend/data/dataset_versions/dataset-v7-final/d76-hard-negatives-report.json`
- `backend/app/ml/final_hard_negatives.py`
- `backend/tests/test_final_hard_negatives.py`

## Implementation Notes

- Policy version: `dataset-v7-hard-negatives-v1`.
- Hard-negative rows are cloned from saved D75 page snapshots from a different category.
- Query-dependent features are recomputed under the target query before writing the cloned row.
- The source category selection is balanced round-robin across all source categories, so the negative set is not dominated by a few early categories.
- `dataset.csv` still contains collection-time placeholder labels. D76 does not create final labels.

## Readiness

`python -m app.ml.final_query_competitiveness --validate` now passes hard-negative checks and blocks only on `manifest_ready_for_training=false`.

No model artifact was trained, replaced or published in D76.
