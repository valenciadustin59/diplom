# Model Artifacts

This directory is intentionally small now. The product keeps only the active
runtime model binary here. Old candidate and rollback model binaries were
removed after the final query-competitiveness model became the product path.
Historical benchmark reports remain in `ranking-benchmarks/`. The working tree
keeps only the final training dataset under `backend/data/dataset_versions/`.

Runtime code should load the default model from
`backend/artifacts/page_quality_model.pkl`. Do not infer a runtime model by
scanning candidate filenames.

## Runtime Assets

| Asset | Role | Current state |
| --- | --- | --- |
| `page_quality_model.pkl` | Production runtime alias loaded by `app.ml.model.DEFAULT_MODEL_PATH`. | Active final query-competitiveness model. |
| `page_quality_model.metadata.json` | Public sidecar for the production alias. | Dataset `dataset-v7-final`, schema `v4`, model type `QueryCoreGuardrailCatBoostRegressor`, 156 features. |

Runtime code must not infer "latest" by scanning candidate filenames. New
research artifacts can coexist in this directory, but publication means copying
one selected, guardrail-approved model into `page_quality_model.pkl` through a
controlled publish workflow and refreshing `page_quality_model.metadata.json`.

## Rollback Policy

Local rollback binaries were removed to keep the project focused on the final
runtime model. If a rollback is needed later, regenerate or restore the required
artifact from Git history/evidence and then run a controlled publish or rollback
smoke. The product should not show old models as selectable choices.

## Research And Candidate Artifacts

Old `page_quality_model.dataset-*-candidate.pkl` binaries and their metadata
sidecars are no longer kept in the working tree. Their reports remain as
historical text evidence under `ranking-benchmarks/`. Future experiments should
write candidate binaries only while the experiment is active; if rejected, keep
the report and remove the binary.

## Ranking Benchmarks And Decisions

`ranking-benchmarks/` contains decision evidence, not runtime models.

| Directory | Main evidence | Decision meaning |
| --- | --- | --- |
| `dataset-v2/` | `ranking-benchmark-report.*` | Early dataset-v2 benchmark evidence. |
| `dataset-v2-d34/` | `candidate-artifact-training-report.*` | D34 candidate training evidence. |
| `dataset-v2-d35/` | `shadow-benchmark-guardrails-report.*` | D35 rejected dataset-v2 candidates. |
| `dataset-v2-d36/` | `no-publish-decision-report.*` | D36 keep-reference/no-publish record. |
| `dataset-v3-d37/` | `candidate-artifact-training-report.*` | D37 candidate training evidence. |
| `dataset-v3-d37-shadow/` | `shadow-benchmark-guardrails-report.*` | D37 selected pointwise CatBoost for controlled publish. |
| `dataset-v3-d37-d38/` | `controlled-publish-report.*` | D38 promoted CatBoost v3 to `page_quality_model.pkl`. |
| `dataset-v3-d41/` | `golden-replay-report.*` | Post-publish replay guardrails for the active model. |
| `dataset-v3-d44/` | `second-pass-experiment-report.*` | Non-production second-pass experiment, no publish. |
| `dataset-v4-d47/` | `d47-candidate-training-report.*`, `candidate-artifact-training-report.*` | SEO-weighted candidate training evidence. |
| `dataset-v4-d48/` | `d48-product-critical-shadow-report.*`, `shadow-benchmark-guardrails-report.*` | D48 keep-current recommendation. |
| `dataset-v4-d49/` | `d49-no-publish-decision-report.*` | D49 controlled no-publish record. |
| `dataset-v5-d50/` | `top3-regression-analysis.*` | Top-3 regression analysis for v5 work. |
| `dataset-v5-d52/` | `shortcut-feature-control-report.*` | Shortcut feature control policy evidence. |
| `dataset-v5-d53/` | `d53-candidate-training-report.*` | Ranking-aware v5 candidate training evidence. |
| `dataset-v5-d54/` | `shadow-benchmark-guardrails-report.*`, `d54-shadow-decision-report.*` | D54 keep-current/no-publish record. |

No file under `ranking-benchmarks/` should be interpreted as a publish by
itself. A publish is effective only when the production alias and metadata are
updated and the controlled publish report records successful verification.

## Dataset Evidence

Versioned dataset bundles live under `backend/data/dataset_versions/`. The
working tree now keeps only the final production-aligned dataset:

| Dataset | Purpose |
| --- | --- |
| `dataset-v7-final/` | Final query-competitiveness training dataset for the active runtime model. |

Old training datasets (`baseline-v1`, `dataset-v2`, `dataset-v3-d37`,
`dataset-v4`, `dataset-v5`, and `dataset-v6-query-relevance`) were removed from
the working tree after the final model path was selected. Historical decisions
remain documented in `ranking-benchmarks/`, plans and Git history. Restore or
regenerate an old dataset only for an explicit retrospective experiment.
Legacy root training files under `backend/data/ru_commercial_dataset.*` and
`backend/data/training_*` were removed too; ML publish and dataset helpers now
default to `dataset-v7-final`.
The old draft `backend/data/query_relevance_v1/` catalog was removed as well.
`backend/data/query_relevance_v2/` remains because it is the final query catalog
that matches `dataset-v7-final`; `backend/data/query_relevance_regression/`
remains because it stores current relevance regression cases.

Dataset rows and raw extraction artifacts are not loaded by the product
runtime. The retained dataset supports final-model reproducibility and future
training on the current contract.

## Quick Rules For Future Agents

1. Use `backend/artifacts/page_quality_model.pkl` as the only default runtime
   model path.
2. Keep old experiment reports, but do not keep rejected model binaries unless
   a task explicitly needs them.
3. Do not point runtime defaults at `*-candidate.pkl` files.
4. Treat `versions/` as optional local release history. It may be empty.
5. Treat `ranking-benchmarks/` and `backend/data/dataset_versions/` as
   reproducibility/evidence archives, not runtime asset roots. The only retained
   dataset bundle is `dataset-v7-final/`.
