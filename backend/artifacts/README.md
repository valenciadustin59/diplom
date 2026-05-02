# Model Artifact Archive

D60 archive note for GitHub #79. This directory intentionally mixes the
production runtime alias with research and diploma evidence assets. The
runtime contract is narrow: production code should load the default model from
`backend/artifacts/page_quality_model.pkl` unless a command explicitly receives
another path for an offline experiment, benchmark, publish, or rollback task.

## Runtime Assets

| Asset | Role | Current state |
| --- | --- | --- |
| `page_quality_model.pkl` | Production runtime alias loaded by `app.ml.model.DEFAULT_MODEL_PATH`. | Active CatBoost v3 model, SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`. |
| `page_quality_model.metadata.json` | Public sidecar for the production alias. | Dataset `dataset-v3-d37`, artifact version `dataset-v3-d37-20260501200434`, schema `v3`, model type `CatBoostRegressor`, 148 features. |
| `versions/page_quality_model--dataset-v3-d37-20260501200434.pkl` | Immutable versioned copy of the current production alias. | Same SHA1 as `page_quality_model.pkl`; useful for registry/history display, not a separate runtime selector. |
| `versions/page_quality_model--dataset-v3-d37-20260501200434.metadata.json` | Metadata sidecar for the current versioned copy. | Mirrors the active D38 publish metadata. |

Runtime code must not infer "latest" by scanning candidate filenames. New
research artifacts can coexist in this directory, but publication means copying
one selected, guardrail-approved model into `page_quality_model.pkl` through a
controlled publish workflow and refreshing `page_quality_model.metadata.json`.

## Rollback Asset

| Asset | Role | Current state |
| --- | --- | --- |
| `versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl` | Preserved previous production model for controlled rollback. | RandomForest v1 rollback artifact, SHA1 `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`. |
| `versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.metadata.json` | Rollback metadata sidecar. | Dataset `ru_commercial_dataset-20260421-primary`, schema `v1`, 59 features. |

Rollback is an engineering operation, not an automatic runtime fallback. The
registry endpoint may display this asset as rollback evidence, but rollback
still requires a deliberate copy back to the production alias followed by smoke
verification.

## Research And Candidate Artifacts

The following files are research artifacts unless a future controlled publish
explicitly promotes one of them into `page_quality_model.pkl`.

| Pattern or file | Evidence wave | Runtime status |
| --- | --- | --- |
| `page_quality_model.dataset-v2-candidate.pkl` | D29/D30 early dataset-v2 benchmark. | Archived research candidate. |
| `page_quality_model.dataset-v2-expert-*-candidate.pkl`, `page_quality_model.dataset-v2-ranking-candidate.pkl` | D34/D35 expert-label candidates. | Archived; D35/D36 recommended keep-reference/no-publish. |
| `page_quality_model.dataset-v3-d37-*-candidate.pkl` | D37 unified v3 candidates. | D37 CatBoost candidate was later published through D38; the candidate files themselves remain evidence, not runtime aliases. |
| `page_quality_model.dataset-v3-d44-second-pass-experiment.pkl` | D44 second-pass competitor-aware experiment. | Non-production experiment; D44 recommended not continuing without more evidence. |
| `page_quality_model.dataset-v4-seo-weighted-*-candidate.pkl` | D47/D48 SEO-weighted candidates. | Non-production; D48/D49 recommended keep-current/no-publish. |
| `page_quality_model.dataset-v5-*-candidate.pkl` | D53/D54 ranking-aware v5 candidates. | Non-production; D54 recommended keep-current/no-publish. |
| `page_quality_model_batch50.pkl` | Older training artifact kept for historical traceability. | Archived evidence; not a runtime selector. |

Many newer candidate files have `.metadata.json` sidecars with
`non_production=true` and/or `runtime_enabled=false`. Treat missing sidecars on
older artifacts as "archived research" rather than production eligibility.

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

Versioned dataset bundles live under `backend/data/dataset_versions/` and are
evidence inputs for training, analysis, and reproducibility:

| Dataset | Purpose |
| --- | --- |
| `baseline-v1/` | Original baseline dataset evidence. |
| `dataset-v2/` | D27-D36 dataset-v2, expert-label, and split evidence. |
| `dataset-v3-d37/` | D37 unified v3 feature dataset used for the active D38 CatBoost publish. |
| `dataset-v4/` | D45-D49 SEO-weighted label and candidate evidence; no publish. |
| `dataset-v5/` | D50-D54 ranking-aware preference and controlled dataset evidence; no publish. |

Dataset rows and raw extraction artifacts are not loaded by the product
runtime. They support reproducible training, audits of decisions, and diploma
evidence.

## Quick Rules For Future Agents

1. Use `backend/artifacts/page_quality_model.pkl` as the only default runtime
   model path.
2. Do not delete research artifacts just because they are not production; they
   are part of the diploma evidence trail.
3. Do not point runtime defaults at `*-candidate.pkl` files.
4. Treat `versions/` as release history and rollback evidence. Copying from it
   back to the alias is a controlled rollback task, not passive discovery.
5. Treat `ranking-benchmarks/` and `backend/data/dataset_versions/` as
   reproducibility/evidence archives, not runtime asset roots.
