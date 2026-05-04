# D81 Dataset-v7 Controlled Release

## Goal

Execute the controlled release step after D80. If D80 says `publish_candidate`, D81 publishes through the controlled artifact path with rollback evidence. If D80 says `no_publish`, D81 records that decision and proves production was not changed.

## Result

D81 recorded `no_publish` because D80 failed `hard_negatives_learned_below_cap`.

Production was not changed:

- Production SHA1 before: `5374ca30f48f70d8629e7d84ec3df0524ef35b52`
- Production SHA1 after: `5374ca30f48f70d8629e7d84ec3df0524ef35b52`
- Candidate SHA1: `65c30b2611e6cde393fae52d1f820a00e7d42681`

The active runtime remains the D58 `dataset-v5` pointwise CatBoost artifact. The D79 `dataset-v7-final` candidate stays as non-production evidence.

## Evidence

- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d81/d81-controlled-release-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v7-final-d81/d81-controlled-release-report.md`
- `backend/data/dataset_versions/dataset-v7-final/manifest.json` now records `status=controlled_no_publish`.

## Follow-up

The next model task should not publish D79 as-is. It should harden query-topic discrimination for hard negatives, especially cases where generic modifiers make unrelated pages look superficially relevant.
