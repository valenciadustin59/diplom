# D38 Controlled Publish Decision

- Decision: `publish_candidate`
- Publish action: `controlled_publish`
- Selected candidate: `pointwise_catboost`
- Reason: `candidate_passed_all_publish_gates_and_outperformed_reference`
- Production SHA1 before: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`
- Production SHA1 after: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Production artifact changed: `True`

## Published Runtime Artifact

- Path: `artifacts\page_quality_model.pkl`
- SHA1: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Artifact version: `dataset-v3-d37-20260501200434`
- Dataset version: `dataset-v3-d37`
- Model schema version: `v3`
- Model type: `CatBoostRegressor`
- Feature count: `148`
- Versioned artifact: `E:\codexPROJ\diplom\backend\artifacts\versions\page_quality_model--dataset-v3-d37-20260501200434.pkl`

## Shadow Evidence

- D37 shadow report: `artifacts\ranking-benchmarks\dataset-v3-d37-shadow\shadow-benchmark-guardrails-report.json`
- Candidate metrics: `{"mae": 11.774165, "ndcg_at_10": 0.945929, "rmse": 14.865537, "spearman_mean": 0.421894, "top_3_hit_rate": 0.95, "validation_queries": 20.0}`
- Reference metrics: `{"mae": 23.858757, "ndcg_at_10": 0.909302, "rmse": 27.980756, "spearman_mean": 0.153604, "top_3_hit_rate": 0.95, "validation_queries": 20.0}`
- Metric deltas: `{"mae": -12.084592, "ndcg_at_10": 0.036627, "rmse": -13.115219, "spearman_mean": 0.26829, "top_3_hit_rate": 0.0}`
- Explainability sensibility passed: `True`

## Rollback Reference

- Rollback model path: `E:\codexPROJ\diplom\backend\artifacts\versions\page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl`
- Rollback model SHA1: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`
- Rollback metadata path: `E:\codexPROJ\diplom\backend\artifacts\versions\page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.metadata.json`

## Verification

- Overall status: `passed`
- Runtime smoke status: `passed`
- Runtime smoke summary: `..\output\runtime-smoke\d38-smoke-summary.json`
- Runtime smoke audit: `690504f2-ca2f-42a6-a012-e622438437a7`
- Runtime smoke model info: `{"artifact_family": "page_quality_model", "artifact_version": "dataset-v3-d37-20260501200434", "dataset_version": "dataset-v3-d37", "model_schema_version": "v3", "model_type": "CatBoostRegressor", "source": "local_dataset"}`
- `backend pytest D38/ML subset`: `passed`
- `npm run test:scripts`: `passed`
