# D45-D49: SEO-Weighted Score Retraining Plan

GitHub issues: `D45` #64, `D46` #65, `D47` #66, `D48` #67, `D49` #68.

## Context

The current CatBoost v3 production model is stable, but recent product review showed that the visible score and recommendation priorities should better reflect SEO impact:

- crawl/indexability, canonical, title/query coverage, semantic relevance and intent alignment must dominate;
- weak supporting signals such as image count, link count, pure text volume, price presence, messenger availability and similar non-blockers should not look as important as primary SEO factors;
- competitor gaps should raise priority only when the lag is both meaningful and important for search ranking or page interpretation;
- final `score` must remain a validated ML output, not a manual UI-only score rewrite.

This wave should produce a new candidate model trained on an SEO-weighted target, prove that it improves product-critical behavior, and publish only if guardrails pass.

## D45 / GitHub #64: SEO-Weighted Label Rubric v4

Status: completed locally.

Goal: create a deterministic expert-rubric label layer that encodes SEO impact weighting explicitly.

Scope:

- Define a feature-importance taxonomy for training labels:
  - critical: indexability, HTTP status, canonical correctness, title/query coverage, H1, semantic relevance, intent alignment;
  - important: useful structure, technical metadata, contact/trust for commercial/local intent, CTA and offer clarity;
  - supporting: text volume sufficiency, images, internal links, price signal, messengers, payment/delivery details, social proof;
  - competitor-relative: only boost priority when the gap is meaningful and the factor is important.
- Generate/refresh expert-rubric labels for `dataset-v3-d37` into a new `dataset-v4` label sidecar.
- Make pure text volume a small sufficiency signal, not a quality driver.
- Document exactly that these are deterministic expert-rubric labels, not human labels.

Acceptance criteria:

- Completed: a JSON/CSV label evidence bundle exists for `dataset-v4`.
- Completed: the label report lists weights per feature group and examples of high/medium/low impact decisions.
- Completed: query-group split remains leakage-safe.
- Completed: no production artifact is changed.

Evidence:

- Generator: `backend/app/ml/seo_weighted_labels.py`.
- Label sidecar: `backend/data/dataset_versions/dataset-v4/expert_labels.csv`.
- Reports: `backend/data/dataset_versions/dataset-v4/d45-seo-weighted-label-report.json` and `.md`.
- Split validation: `backend/data/dataset_versions/dataset-v4/d45-split-validation.json`.
- Generated labels: `885` rows across `99` queries.
- Split validation: `group_by_query`, `79` train queries, `20` validation queries, `0` query overlap.
- Score distribution: min `13.7`, p25 `66.2`, mean `68.1355`, p50 `72.2`, p75 `76.3`, max `87.2`.
- Quality bands: `high=2`, `medium=704`, `low=102`, `blocked=77`.
- Production artifact SHA1 remains `29c4b29455f795a535da94b2c6f36ef603d003eb`.

Important wording: D45 labels are deterministic expert-rubric labels, not human labels.

## D46 / GitHub #65: Dataset v4 Build And Validation

Status: completed locally.

Goal: build a versioned `dataset-v4` bundle using the D45 SEO-weighted labels.

Scope:

- Materialize `backend/data/dataset_versions/dataset-v4/`.
- Include `dataset.csv`, `manifest.json`, `split.json`, `failures.csv` and source artifact references.
- Validate feature coverage for v3/v4 columns and label-source distribution.
- Add dataset-quality checks for:
  - no query leakage;
  - bounded target scores;
  - enough rows per query group;
  - importance-weighted labels present for critical SEO factors.

Acceptance criteria:

- Completed: `manifest.json` marks the dataset as ready for training.
- Completed: validation report proves no query leakage and stable row/query coverage.
- Completed: existing dataset versions remain immutable.

Evidence:

- Builder: `backend/app/ml/v4_dataset.py`.
- Dataset bundle: `backend/data/dataset_versions/dataset-v4/dataset.csv`, `failures.csv`, `seeds.csv`, `split.json`, `manifest.json`.
- Report: `backend/data/dataset_versions/dataset-v4/d46-dataset-v4-report.json` and `.md`.
- Rows: `885` successful rows, `49` failures, `450` seed rows copied from the D37 evidence.
- Labels: `885/885` D45 labels applied, `0` missing labels, `0` unmatched labels.
- Target policy: `target_score_equals_d45_seo_weighted_expert_label`. D46 does not re-hybridize with 30% weak SERP rank because D45 labels already include a small `5%` rank prior.
- Label schema: `seo-weighted-v4`; feature schema remains `v3`.
- Manifest quality gates: `ready_for_training=true`.
- Split: `group_by_query`, `695` train rows, `190` validation rows, `79` train queries, `20` validation queries, `0` query overlap.
- Coverage: `99` successful/attempted queries, `568` unique domains, `6` categories, `8` cities.
- New target distribution: min `13.7`, p25 `66.2`, mean `68.1355`, p50 `72.2`, p75 `76.3`, max `87.2`.
- Production artifact SHA1 remains `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D47 / GitHub #66: Train SEO-Weighted Candidate Models

Status: completed locally.

Goal: train non-production candidates optimized for credible SEO score behavior.

Scope:

- Train at least:
  - CatBoostRegressor SEO-weighted candidate;
  - RandomForest or baseline candidate for sanity comparison;
  - optional ranking-aware candidate if it can be evaluated without destabilizing absolute score.
- Preserve feature schema compatibility with runtime scoring.
- Store candidates as non-production artifacts with metadata sidecars.
- Do not overwrite `backend/artifacts/page_quality_model.pkl`.

Acceptance criteria:

- Completed: candidate artifacts load through the runtime model loader.
- Completed: candidate metadata includes dataset version, feature count, training parameters and metrics.
- Completed: training report explains why each candidate is or is not viable.
- Completed: no production artifact is changed.

Evidence:

- Training wrapper: `backend/app/ml/seo_weighted_candidate_training.py`.
- Generic training report: `backend/artifacts/ranking-benchmarks/dataset-v4-d47/candidate-artifact-training-report.json` and `.md`.
- D47 report: `backend/artifacts/ranking-benchmarks/dataset-v4-d47/d47-candidate-training-report.json` and `.md`.
- Dataset: `dataset-v4`, label schema `seo-weighted-v4`, model schema `v3`, `148` features, `885` rows, `99` queries, `568` domains.
- Split: `group_by_query`, `695` train rows, `190` validation rows, `79` train queries, `20` validation queries, `0` query overlap.
- Saved non-production artifacts:
  - `backend/artifacts/page_quality_model.dataset-v4-seo-weighted-rf-candidate.pkl`, SHA1 `6ff84515690e07c2f0b5daa141deede491bd0c9d`;
  - `backend/artifacts/page_quality_model.dataset-v4-seo-weighted-catboost-candidate.pkl`, SHA1 `24b774fea9402478223a6ab1d87b0758efd6d131`;
  - `backend/artifacts/page_quality_model.dataset-v4-seo-weighted-ranking-candidate.pkl`, SHA1 `e7af615565ddec429fa592c1a8f9418bbba26471`.
- Each artifact has a `.metadata.json` sidecar with `training_task=D47`, `non_production=true`, `runtime_enabled=false`, `target_policy=target_score_equals_d45_seo_weighted_expert_label` and compatibility check `passed=true`.
- Metrics:
  - RandomForestRegressor: `RMSE=2.556254`, `MAE=1.878591`, `Spearman=0.918117`, `NDCG@10=0.996819`, `top_3_hit_rate=0.6`.
  - CatBoostRegressor: `RMSE=1.8421`, `MAE=1.231731`, `Spearman=0.959054`, `NDCG@10=0.998348`, `top_3_hit_rate=0.65`.
  - CatBoostRanker: `RMSE=67.866147`, `MAE=66.10666`, `Spearman=0.911027`, `NDCG@10=0.996435`, `top_3_hit_rate=0.7`.
- LightGBM and XGBoost ranking candidates were unavailable in the local environment (`lightgbm_not_installed`, `xgboost_not_installed`).
- D47 is not a publish decision. The current production artifact SHA1 remains `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D48 / GitHub #67: Product-Critical Shadow Benchmark

Status: completed locally.

Goal: prove whether a D47 candidate is better than the current production model for product use.

Guardrails:

- `top_3_hit_rate` must be at least current production.
- `NDCG@10` and Spearman must not regress materially.
- MAE/RMSE must not regress beyond a documented tolerance.
- Score boundedness must remain `0..100`.
- Recommendation-priority consistency must improve or remain stable.
- Critical SEO failures should produce lower score than pages that only miss supporting signals.
- Supporting-factor gaps must not dominate high-priority recommendations.

Acceptance criteria:

- Completed: shadow benchmark report recommends one of:
  - `publish_candidate`;
  - `keep_current`;
  - `needs_more_data`.
- Completed: report includes product-critical examples for score response to critical vs supporting degradation.
- Completed: no production artifact is changed.

Evidence:

- Runner: `backend/app/ml/seo_weighted_shadow_benchmark.py`.
- D48 report: `backend/artifacts/ranking-benchmarks/dataset-v4-d48/d48-product-critical-shadow-report.json` and `.md`.
- Base shadow report: `backend/artifacts/ranking-benchmarks/dataset-v4-d48/shadow-benchmark-guardrails-report.json` and `.md`.
- Reference production metrics against `dataset-v4`: `MAE=8.113452`, `Spearman=0.415837`, `NDCG@10=0.97438`, `top_3_hit_rate=0.95`.
- D48 decision: `keep_current`, reason `no_candidate_passed_product_critical_guardrails`.
- RF candidate: improved absolute/ranking correlation metrics (`MAE=1.878591`, `Spearman=0.918117`, `NDCG@10=0.996819`) but failed publish because `top_3_hit_rate=0.6`, delta `-0.35`.
- CatBoostRegressor candidate: best absolute fit (`MAE=1.231731`, `Spearman=0.959054`, `NDCG@10=0.998348`) but failed publish because `top_3_hit_rate=0.65`, delta `-0.30`; product feature guardrail also failed because top feature is supporting `word_count`.
- CatBoostRanker candidate: failed publish because `top_3_hit_rate=0.7`, delta `-0.25`, and absolute-error viability failed (`MAE=66.10666`).
- Product score-response check passed for all saved candidates: critical SEO degradation drops score more than supporting degradation, but this does not override top-3 and feature-dominance gates.
- Production artifact SHA1 remains `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D49 / GitHub #68: Controlled Publish Or No-Publish Decision

Goal: make a safe release decision for the best D47/D48 candidate.

Scope:

- If D48 passes: perform controlled publish with rollback artifact preservation and product smoke.
- If D48 fails: create an explicit no-publish report and keep current production model.
- Update runtime model status docs and local handoff files.
- Verify UI score explanations and recommendations against current audits.

Acceptance criteria:

- Completed: publish/no-publish decision is recorded in JSON and Markdown.
- Completed: no model was published because D48 returned `keep_current`.
- Completed: production SHA remains unchanged and the reason is clear.
- Completed: backend ML regression checks passed for the D45-D49 wave.

Evidence:

- Runner: `backend/app/ml/seo_weighted_no_publish_decision.py`.
- D49 report: `backend/artifacts/ranking-benchmarks/dataset-v4-d49/d49-no-publish-decision-report.json` and `.md`.
- Decision: `keep_current` / `no_publish`.
- Reason: `d48_no_candidate_passed_product_critical_guardrails`.
- Runtime artifact kept: `backend/artifacts/page_quality_model.pkl`, SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`.
- Runtime model metadata kept: dataset `dataset-v3-d37`, schema `v3`, model type `CatBoostRegressor`, `148` features.
- D47 candidate artifacts remain non-production and are not runtime-selected.
- Verification: `tests/test_seo_weighted_no_publish_decision.py`, `tests/test_no_publish_decision.py`, `tests/test_seo_weighted_shadow_benchmark.py`, `tests/test_shadow_benchmark.py`, `tests/test_seo_weighted_candidate_training.py`, `tests/test_ranking_benchmark.py`, `tests/test_v4_dataset.py`, `tests/test_seo_weighted_labels.py`, `tests/test_training_pipeline.py`, `tests/test_training_dataset_quality.py`, and `tests/test_model_schema.py` passed together as `48 passed`.
