# D41 Golden Query Replay Guardrails

## Summary

- Mode: `stored_evidence`
- Generated at: `2026-05-02T00:00:00+00:00`
- Decision: `passed`
- Recommendation: Golden replay guardrails passed for the stored post-publish evidence.
- Active model: `CatBoostRegressor` / schema `v3`
- Dataset: `dataset-v3-d37`
- Artifact: `dataset-v3-d37-20260501200434`
- Artifact SHA1: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Rollback available: `True`
- Rollback SHA1: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`

## Guardrail Summary

- Items: `3`
- Passed items: `3`
- Warning items: `0`
- Failed items: `0`
- Guardrail counts: `{"fail": 0, "pass": 21, "warn": 0}`

## Replay Items

| ID | Query | Status | Score | Competitors | Recommendations | Decision |
| --- | --- | --- | ---: | --- | ---: | --- |
| renovation-moscow | ремонт квартир москва | completed | 83.7366 | 2/2 analyzed, 0 failed | 11 | passed |
| plastic-windows-ekaterinburg | пластиковые окна екатеринбург | completed | 78.4 | 2/3 analyzed, 1 failed | 9 | passed |
| seo-audit | seo audit | completed | 62.8 | 1/2 analyzed, 1 failed | 7 | passed |

## Item Guardrails

### renovation-moscow

- `audit_status`: `pass` - Audit reached a terminal successful status.
- `score_boundedness`: `pass` - Score is inside the expected 0-100 range.
- `competitor_coverage`: `pass` - Enough competitor pages were analyzed for a competitor-aware audit.
- `recommendation_availability`: `pass` - Replay produced at least one recommendation.
- `model_metadata_presence`: `pass` - Runtime model metadata is present in score_breakdown.model_info.
- `runtime_warnings`: `pass` - Replay completed without runtime warnings.
- `active_model_match`: `pass` - Stored evidence model metadata matches the active /health/model metadata.
- Reference comparison: `D38 rollback reference`, score delta `14.2117`

### plastic-windows-ekaterinburg

- `audit_status`: `pass` - Audit reached a terminal successful status.
- `score_boundedness`: `pass` - Score is inside the expected 0-100 range.
- `competitor_coverage`: `pass` - Enough competitor pages were analyzed for a competitor-aware audit.
- `recommendation_availability`: `pass` - Replay produced at least one recommendation.
- `model_metadata_presence`: `pass` - Runtime model metadata is present in score_breakdown.model_info.
- `runtime_warnings`: `pass` - Replay completed without runtime warnings.
- `active_model_match`: `pass` - Stored evidence model metadata matches the active /health/model metadata.
- Reference comparison: `D38 rollback reference`, score delta `7.4`

### seo-audit

- `audit_status`: `pass` - Audit reached a terminal successful status.
- `score_boundedness`: `pass` - Score is inside the expected 0-100 range.
- `competitor_coverage`: `pass` - Enough competitor pages were analyzed for a competitor-aware audit.
- `recommendation_availability`: `pass` - Replay produced at least one recommendation.
- `model_metadata_presence`: `pass` - Runtime model metadata is present in score_breakdown.model_info.
- `runtime_warnings`: `pass` - Replay completed without runtime warnings.
- `active_model_match`: `pass` - Stored evidence model metadata matches the active /health/model metadata.
- Reference comparison: `D38 rollback reference`, score delta `4.6`

## Invariants

- This workflow does not publish a model.
- This workflow does not roll back a model.
- This workflow does not mutate `backend/artifacts/page_quality_model.pkl`.
- Default mode evaluates stored deterministic evidence and does not require live network.
