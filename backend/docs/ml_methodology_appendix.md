# Appendix: ML Methodology And Limitations

## Purpose of the ML component

The ML subsystem in this project is not used as an isolated black-box classifier. Its practical purpose is to estimate the competitive quality of a landing page for a search query by combining many heterogeneous signals into one ranking-oriented score.

For the diploma context, this is important for two reasons:

1. The system does not rely only on hand-written SEO checks such as `title_present` or `h1_count`.
2. The final score is based on the interaction between textual relevance, query alignment, structural quality and commercial usefulness.

In production terms, the model answers the following question:

`How competitive does this page look relative to pages that already rank for the same query?`

## Target variable and learning setup

The model is trained as a regression model.

The target variable is `target_score`, derived from the position of a page in the collected SERP sample. Higher-ranked pages receive higher target values. Inside the current pipeline this target is built from the observed rank and normalized to the `0..100` range.

This means that the model does not predict "absolute website quality" in a universal sense. It predicts a query-dependent approximation of competitive page quality using ranking-derived supervision.

That design is defensible for this project because the business task is comparative SEO audit, not generic content scoring.

## Dataset methodology

### Data source

The main training dataset is collected from real search results for RU commercial queries.

Current published snapshot:

- `dataset_version`: `ru_commercial_dataset-20260421-primary`
- `artifact_version`: `ru_commercial_dataset-20260421-primary-20260421174901`
- `rows_count`: `436`
- `queries_count`: `47`
- `domains_count`: `385`
- `categories_count`: `6`
- `cities_count`: `8`
- `failure_rate`: `0.07234`
- `query_coverage_ratio`: `0.235`

The dataset is stored in:

- `backend/data/ru_commercial_dataset.csv`
- `backend/data/ru_commercial_dataset_failures.csv`
- `backend/data/ru_commercial_dataset.manifest.json`

### Query sampling strategy

The seed catalog is intentionally commercial and region-aware.

It is generated from:

- a fixed set of RU commercial service categories;
- a fixed set of cities with region codes;
- query phrases built as `category + city`.

This gives the project a controlled and reproducible data collection strategy instead of ad hoc manual query selection.

The current seed catalog source of truth is implemented in:

- `backend/app/ml/query_seeds.py`
- `scripts/generate_training_queries.py`

### Page collection strategy

For each query, the pipeline retrieves SERP results and then fetches the corresponding landing pages. From each page it extracts text, HTML and structured features.

The collection stage records both:

- successful rows used for training;
- failed rows kept for auditability and data quality analysis.

This is important methodologically because data collection failures are not silently ignored. They are tracked in the dataset workflow and reflected in the manifest.

### Dataset quality gates

The project does not treat any collected CSV as automatically valid for training. A dataset is considered ready only if it passes explicit coverage and quality gates.

Current default thresholds:

- at least `400` successful rows;
- at least `40` unique queries;
- at least `250` unique domains;
- at least `6` categories;
- at least `6` cities;
- at least `20%` successful seed coverage;
- at least `5` rows per successful query on average;
- failure rate no higher than `20%`.

These checks are implemented in:

- `backend/app/ml/dataset_quality.py`

This makes the training pipeline reproducible and prevents publishing a model from an obviously weak dataset.

## Feature engineering methodology

The runtime now supports two artifact-compatible feature schemas: legacy `v1` with `59` engineered features, and ranking-oriented `v2` that extends those `59` baseline signals with reproducible snapshot auxiliary technical, commercial and trust features. New training and publish flows default to `v2`, while runtime inference remains backward-compatible with previously published `v1` artifacts.

They are intentionally heterogeneous and cover three signal families:

1. Structural signals.
2. Query-aware lexical and semantic signals.
3. Interaction signals derived from relationships between base features.

Examples of structural signals:

- `title_present`
- `title_length`
- `meta_description_present`
- `heading_count`
- `link_count`
- `image_count`
- `form_count`
- `text_to_html_ratio`

Examples of query-aware signals:

- `query_in_title`
- `query_in_text`
- `exact_query_count`
- `query_density`
- `keyword_coverage_ratio`
- `semantic_similarity`

Examples of interaction signals:

- `query_semantic_alignment`
- `title_semantic_alignment`
- `heading_semantic_alignment`
- `content_depth_semantic_score`
- `keyword_balance_score`
- `semantic_content_richness`
- `cta_semantic_score`

The detailed feature list is documented separately in:

- `backend/docs/ml_feature_inventory.md`

### Why engineered features are justified here

This project solves a relatively small-data, high-interpretability problem. In this context, engineered tabular features are a better fit than end-to-end deep learning for several practical reasons:

- the dataset size is still limited;
- feature importance and score explanations matter for user trust;
- the application needs stable local training and inference;
- the result must be explainable in a diploma setting.

## Model training methodology

### Problem formulation

The learning problem is treated as regression over tabular features with ranking-aware evaluation.

That means the model predicts a continuous page quality score, but model selection is not based only on regression loss. It is also validated with metrics that reflect ranking usefulness.

### Current model candidates

The current training pipeline evaluates at least the following candidates:

- `RandomForestRegressor`
- `CatBoostRegressor` when benchmark conditions are triggered

The implemented selection logic currently prefers the candidate with the strongest ranking-oriented validation profile.

### Data split strategy

The default split mode is query-grouped validation.

This is critical. If rows from the same query appeared in both train and validation without grouping, the evaluation would be too optimistic. Group-based split makes the validation scenario closer to the real use case: the model is evaluated on unseen query groups.

Current split mode in the published artifact:

- `split_mode = group_by_query`

### Model selection metrics

The current pipeline reports both regression and ranking-aware metrics:

- `RMSE`
- `MAE`
- `Spearman mean`
- `NDCG@10`
- `Top-3 hit rate`

This combination is justified because:

- `RMSE` and `MAE` reflect score error magnitude;
- `Spearman mean` reflects rank-order agreement;
- `NDCG@10` measures quality of top-ranked outputs;
- `Top-3 hit rate` checks whether the model places at least one truly strong page into the predicted top segment.

## Published primary artifact

The currently published runtime artifact is:

- `backend/artifacts/page_quality_model.pkl`

The system also stores an immutable versioned copy:

- active D38 artifact: `backend/artifacts/versions/page_quality_model--dataset-v3-d37-20260501200434.pkl`
- rollback v1 artifact: `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl`

Public artifact metadata is stored in JSON sidecars:

- `backend/artifacts/page_quality_model.metadata.json`
- `backend/artifacts/versions/page_quality_model--dataset-v3-d37-20260501200434.metadata.json`
- `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.metadata.json`

### Current published validation summary

According to the active D38 published artifact metadata, the current model has:

- `dataset_version`: `dataset-v3-d37`
- `artifact_version`: `dataset-v3-d37-20260501200434`
- `model_schema_version`: `v3`
- `model_type`: `CatBoostRegressor`
- `feature_count`: `148`
- `rmse`: `14.865537`
- `mae`: `11.774165`
- `spearman_mean`: `0.421894`
- `ndcg_at_10`: `0.945929`
- `top_3_hit_rate`: `0.95`
- `validation_queries`: `20`

### Runtime explainability metadata

The runtime now exposes the following fields in `score_breakdown.model_info`:

- artifact identity: `artifact_version`, `artifact_family`
- publication timestamps: `trained_at`, `published_at`
- dataset identity: `dataset_version`
- dataset size and coverage: `dataset_rows`, `dataset_queries`, `dataset_domains`, `dataset_categories`, `dataset_cities`
- dataset collection quality: `dataset_failure_rate`, `dataset_query_coverage_ratio`, `dataset_attempted_query_coverage_ratio`
- training summary: `metrics_summary`

This is important for the diploma because the runtime score can now be traced back to a concrete published model artifact and a concrete dataset snapshot.

## Offline evaluation before publish

The project includes an explicit offline evaluation step before publishing a new artifact.

Implemented flow:

- train candidate models on the train split;
- evaluate all candidates on the same validation split;
- compare the best new candidate against the currently published runtime artifact on the same validation rows.

This is implemented in:

- `backend/app/ml/evaluate.py`

This design reduces the risk of replacing a working runtime model with a weaker candidate.

## Hybrid scoring methodology

The final runtime score is not pure ML output.

The system combines:

- a rule-based score computed from interpretable feature logic;
- an ML score predicted by the trained artifact.

The weighting is adaptive:

- if the runtime falls back to bootstrap, rule-based weight is higher;
- if a real local dataset artifact is present, ML receives stronger influence.

This hybrid strategy is appropriate for the current maturity level of the project because it balances two goals:

- practical robustness;
- explainability.

## Why this methodology is suitable for the diploma

This methodology is suitable for the diploma because it demonstrates all major components of an applied ML system:

- reproducible data collection;
- quality-controlled dataset formation;
- engineered feature design connected to domain logic;
- ranking-aware evaluation;
- publishable model artifacts with versioning;
- runtime traceability and explainability.

In other words, the project is not just "using a model". It implements a compact but real ML lifecycle.

## Known limitations

The current implementation still has important limitations that must be stated explicitly.

### 1. Target proxy limitation

The target score is derived from observed ranking position, not from direct business outcomes or human expert labels.

Consequence:

- the model learns a proxy of competitive quality, not a universal notion of page usefulness;
- SERP noise and search engine bias are implicitly inherited by the dataset.

### 2. Dataset size is still moderate

`436` rows is enough for a meaningful local artifact, but not enough to claim broad generalization across all SEO scenarios.

Consequence:

- the current model should be presented as a strong local primary artifact for this project stage, not as a final industrial-grade universal ranker.

### 3. Query coverage is still partial

The successful query coverage ratio is `0.235` of the full seed catalog.

Consequence:

- the current artifact is representative for the collected subset, but not yet exhaustive over the full intended RU commercial query space.

### 4. Regional and vertical bias

The dataset is intentionally RU-commercial and city-oriented.

Consequence:

- model behaviour should not be generalized to informational content, non-commercial niches or other languages without a new dataset and separate validation.

### 5. Feature-based representation limits

The model relies on engineered tabular features instead of deep semantic end-to-end ranking architectures.

Consequence:

- the system gains explainability and local reproducibility;
- however, it may miss more subtle discourse-level or intent-level patterns that a larger neural ranking setup could capture.

### 6. External collection instability

Training data quality depends on live page fetch and SERP availability.

Consequence:

- network instability, blocked pages, anti-bot behaviour and rendering failures can affect coverage and introduce collection bias.

### 7. Validation size is limited

The current published validation summary is based on `10` validation queries.

Consequence:

- ranking-aware metrics are informative, but still statistically limited;
- future iterations should increase the number of query groups used for evaluation.

## Recommended next methodological steps

The most important next steps are:

1. Increase successful query coverage across the full RU commercial seed catalog.
2. Expand the dataset with more domains and query groups.
3. Re-run offline evaluation on larger validation splits.
4. Track artifact history over time instead of relying on a single primary publish.
5. Consider expert-labeled or weakly-labeled targets to complement rank-derived supervision.
6. Separate methodological claims for commercial local queries from broader SEO claims.

## D37 unified v3 candidate evidence

D37 adds a wider pre-competitor model schema named `v3`. It is not a simple average of older model predictions. The candidate is trained on one unified feature vector:

- `59` baseline text/HTML/query features;
- `49` snapshot technical and commercial features;
- `25` heavy-analysis features;
- `15` intent-alignment features.

The resulting schema has `148` features. It intentionally excludes the `29` SERP-relative features because those values are available only after competitor aggregation, while the current first scoring stage runs before that point.

D37 dataset evidence is stored in `backend/data/dataset_versions/dataset-v3-d37/`. The bundle contains `885` rows, `99` queries, `885/885` resolved source artifacts, and a `group_by_query` split with `695` training rows and `190` validation rows. The split has no train/validation query overlap.

D37 trained three non-production candidates:

- `backend/artifacts/page_quality_model.dataset-v3-d37-rf-candidate.pkl`
- `backend/artifacts/page_quality_model.dataset-v3-d37-catboost-candidate.pkl`
- `backend/artifacts/page_quality_model.dataset-v3-d37-ranking-candidate.pkl`

The D37 shadow benchmark is stored in `backend/artifacts/ranking-benchmarks/dataset-v3-d37-shadow/shadow-benchmark-guardrails-report.json`. It recommends `publish_candidate` and selects `pointwise_catboost`. The selected candidate preserved the reference `top_3_hit_rate` while improving the other release metrics:

- reference: `top_3_hit_rate=0.95`, `ndcg_at_10=0.909302`, `spearman_mean=0.153604`, `MAE=23.858757`;
- selected candidate: `top_3_hit_rate=0.95`, `ndcg_at_10=0.945929`, `spearman_mean=0.421894`, `MAE=11.774165`.

The existing production artifact `backend/artifacts/page_quality_model.pkl` was not overwritten during D37. Its SHA1 remained `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`. D38 then performed the controlled publish/smoke step and made the D37 CatBoost v3 candidate the selected runtime model.

## D38 controlled publish evidence

D38 publishes the D37 `pointwise_catboost` candidate only after validating the D37 shadow report decision and preserving the previous production artifact as rollback evidence.

Published runtime artifact:

- path: `backend/artifacts/page_quality_model.pkl`
- SHA1 before publish: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`
- SHA1 after publish: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- dataset version: `dataset-v3-d37`
- artifact version: `dataset-v3-d37-20260501200434`
- model schema version: `v3`
- model type: `CatBoostRegressor`
- feature count: `148`

Rollback artifact:

- `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl`
- SHA1: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`

D38 report evidence is stored in:

- `backend/artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.md`

Runtime smoke evidence is stored in `output/runtime-smoke/d38-smoke-summary.json`. The smoke audit `690504f2-ca2f-42a6-a012-e622438437a7` completed with `2/2` competitors analyzed, `11` recommendations, four workers, missing queues `[]`, and runtime model metadata `dataset-v3-d37` / schema `v3` / `CatBoostRegressor`.

## D45 SEO-weighted label evidence

D45 starts a new retraining wave by creating deterministic expert-rubric labels for `dataset-v4`.

These labels are not human labels. They are generated from a documented SEO-weighted rubric that intentionally gives more influence to factors that affect search ranking and page interpretation:

- critical factors: crawl/indexability, HTTP status, canonical consistency, title/query fit, heading/query fit, semantic/query fit and intent alignment;
- important factors: technical metadata, page structure, commercial trust, offer/conversion path and mobile/render/performance signals;
- supporting factors: text sufficiency, media/internal navigation, secondary commercial details and structured support;
- rank prior: a small stabilizing signal, not the dominant target.

D45 evidence is stored in:

- `backend/app/ml/seo_weighted_labels.py`
- `backend/data/dataset_versions/dataset-v4/expert_labels.csv`
- `backend/data/dataset_versions/dataset-v4/d45-seo-weighted-label-report.json`
- `backend/data/dataset_versions/dataset-v4/d45-seo-weighted-label-report.md`
- `backend/data/dataset_versions/dataset-v4/d45-split-validation.json`

The generated sidecar contains `885` labels across `99` queries. Split validation reuses the `dataset-v3-d37` query-group split and passes with `79` train queries, `20` validation queries and `0` train/validation query overlap.

The D45 score distribution is deliberately bounded away from automatic perfect scores: min `13.7`, p25 `66.2`, mean `68.1355`, p50 `72.2`, p75 `76.3`, max `87.2`. Quality bands: `high=2`, `medium=704`, `low=102`, `blocked=77`.

D45 does not publish or mutate a runtime model. The production artifact `backend/artifacts/page_quality_model.pkl` remains SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D46 dataset-v4 build evidence

D46 materializes the D45 SEO-weighted labels into a training-ready `dataset-v4` bundle.

The target policy is intentionally direct: `target_score` equals the D45 SEO-weighted expert-rubric label. D46 does not blend the target again with weak SERP rank, because the D45 rubric already includes a small `5%` rank prior. This keeps the next model training focused on SEO-impact weighting rather than re-amplifying historical SERP order.

D46 evidence is stored in:

- `backend/app/ml/v4_dataset.py`
- `backend/data/dataset_versions/dataset-v4/dataset.csv`
- `backend/data/dataset_versions/dataset-v4/failures.csv`
- `backend/data/dataset_versions/dataset-v4/seeds.csv`
- `backend/data/dataset_versions/dataset-v4/split.json`
- `backend/data/dataset_versions/dataset-v4/manifest.json`
- `backend/data/dataset_versions/dataset-v4/d46-dataset-v4-report.json`
- `backend/data/dataset_versions/dataset-v4/d46-dataset-v4-report.md`

The bundle contains `885` successful rows, `49` failures and `450` copied seed rows. D46 applied all `885/885` D45 labels with `0` missing labels and `0` unmatched labels. Label schema is `seo-weighted-v4`; feature schema remains the D37 `v3` feature set used by the current runtime model family.

The dataset is marked `ready_for_training=true`. The split is query-group safe: `695` train rows, `190` validation rows, `79` train queries, `20` validation queries and `0` train/validation query overlap. Coverage is `99` attempted/successful queries, `568` unique domains, `6` categories and `8` cities.

The new target distribution matches the D45 bounded rubric: min `13.7`, p25 `66.2`, mean `68.1355`, p50 `72.2`, p75 `76.3`, max `87.2`. Compared with the previous D37 target distribution, the max no longer reaches an automatic `100`, which directly addresses the product concern that score explanations looked overly generous for some pages.

D46 does not publish or mutate a runtime model. The production artifact `backend/artifacts/page_quality_model.pkl` remains SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D47 SEO-weighted candidate training evidence

D47 trains non-production model candidates from `dataset-v4`. It does not publish a model and does not change the active runtime artifact.

The D47 training path is `backend/app/ml/seo_weighted_candidate_training.py`. It reuses the shared candidate-artifact workflow, but fixes the task-specific inputs:

- dataset: `backend/data/dataset_versions/dataset-v4/dataset.csv`;
- target policy: `target_score_equals_d45_seo_weighted_expert_label`;
- label schema: `seo-weighted-v4`;
- model schema: `v3`;
- feature count: `148`;
- split: `group_by_query`, `695` train rows, `190` validation rows and `0` query overlap.

D47 saved three non-production candidates:

- `backend/artifacts/page_quality_model.dataset-v4-seo-weighted-rf-candidate.pkl`
- `backend/artifacts/page_quality_model.dataset-v4-seo-weighted-catboost-candidate.pkl`
- `backend/artifacts/page_quality_model.dataset-v4-seo-weighted-ranking-candidate.pkl`

Each candidate has a `.metadata.json` sidecar marked `training_task=D47`, `non_production=true`, `runtime_enabled=false` and `publish_decision_required=D48/D49`. Compatibility checks passed for all three saved artifacts: each loads through `load_model_artifact`, uses schema `v3`, has `148` features, reports `dataset-v4` and returns a bounded `predict_score` sample.

Validation metrics:

- RandomForestRegressor: `RMSE=2.556254`, `MAE=1.878591`, `Spearman=0.918117`, `NDCG@10=0.996819`, `top_3_hit_rate=0.6`.
- CatBoostRegressor: `RMSE=1.8421`, `MAE=1.231731`, `Spearman=0.959054`, `NDCG@10=0.998348`, `top_3_hit_rate=0.65`.
- CatBoostRanker: `RMSE=67.866147`, `MAE=66.10666`, `Spearman=0.911027`, `NDCG@10=0.996435`, `top_3_hit_rate=0.7`.

The CatBoostRegressor is the best D47 pointwise candidate by validation quality, but D47 is deliberately not a release decision. D48 must compare candidates against the active production artifact with product-critical guardrails, especially `top_3_hit_rate` and recommendation-priority consistency.

D47 evidence is stored in:

- `backend/artifacts/ranking-benchmarks/dataset-v4-d47/candidate-artifact-training-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v4-d47/candidate-artifact-training-report.md`
- `backend/artifacts/ranking-benchmarks/dataset-v4-d47/d47-candidate-training-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v4-d47/d47-candidate-training-report.md`

D47 does not publish or mutate a runtime model. The production artifact `backend/artifacts/page_quality_model.pkl` remains SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D48 product-critical shadow benchmark

D48 evaluates the D47 candidates against the current production artifact with release guardrails. It is intentionally a benchmark and decision-evidence step, not a training or publish step.

D48 runs `backend/app/ml/seo_weighted_shadow_benchmark.py`, which wraps the existing shadow benchmark and adds product-specific checks:

- top-3 release gate: candidate `top_3_hit_rate` must not regress against current production;
- absolute and ranking metrics: `MAE`, `RMSE`, Spearman and `NDCG@10` are compared to production;
- score boundedness: smoke explanations must stay within `0..100`;
- feature dominance: top features must not be led by weak supporting factors such as raw text volume;
- score response: synthetic critical SEO degradation must reduce score more than supporting-factor degradation.

D48 evidence is stored in:

- `backend/artifacts/ranking-benchmarks/dataset-v4-d48/d48-product-critical-shadow-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v4-d48/d48-product-critical-shadow-report.md`
- `backend/artifacts/ranking-benchmarks/dataset-v4-d48/shadow-benchmark-guardrails-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v4-d48/shadow-benchmark-guardrails-report.md`

Production CatBoost v3 remains the reference. Against `dataset-v4`, its metrics are `MAE=8.113452`, `Spearman=0.415837`, `NDCG@10=0.97438`, `top_3_hit_rate=0.95`.

D48 candidate outcomes:

- RandomForestRegressor improves `MAE` to `1.878591`, Spearman to `0.918117` and `NDCG@10` to `0.996819`, but regresses `top_3_hit_rate` to `0.6`.
- CatBoostRegressor improves `MAE` to `1.231731`, Spearman to `0.959054` and `NDCG@10` to `0.998348`, but regresses `top_3_hit_rate` to `0.65`; it also fails the feature-dominance guardrail because the top feature is `word_count`, a supporting signal.
- CatBoostRanker reaches `top_3_hit_rate=0.7`, but has unacceptable absolute error (`MAE=66.10666`).

The product score-response check passed for all candidates: critical SEO degradation produced a larger average score drop than supporting degradation. This is useful evidence that the D45/D46 rubric moved in the right direction, but it does not override the top-3 release gate.

D48 decision is `keep_current` with reason `no_candidate_passed_product_critical_guardrails`. The production artifact `backend/artifacts/page_quality_model.pkl` remains SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D49 no-publish release decision

D49 turns the D48 benchmark result into an explicit release decision. It does not train, publish, roll back or mutate the runtime artifact.

D49 runs `backend/app/ml/seo_weighted_no_publish_decision.py`. The decision is `keep_current` with publish action `no_publish`, because no D47 candidate passed the product-critical guardrails. This keeps the current CatBoost v3 production model active while preserving the dataset-v4 candidates as non-production evidence.

D49 evidence is stored in:

- `backend/artifacts/ranking-benchmarks/dataset-v4-d49/d49-no-publish-decision-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v4-d49/d49-no-publish-decision-report.md`

The selected runtime artifact remains `backend/artifacts/page_quality_model.pkl`, SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`, dataset `dataset-v3-d37`, schema `v3`, model type `CatBoostRegressor`, with `148` features. Candidate artifacts from D47 are explicitly not runtime-selected.

D49 verification passed with the D45-D49 ML regression set: `48` tests passed across no-publish, shadow benchmark, ranking benchmark, dataset-v4, SEO-weighted labels, training pipeline, dataset quality and model schema coverage.

## D50 top-3 regression analysis

D50 starts the ranking-aware v5 wave. It analyzes why the dataset-v4 candidates were not published: the candidates improved absolute score fit but regressed product-critical top-3 behavior.

D50 runs `backend/app/ml/top3_regression_analysis.py`. It reloads the current production artifact and all D47 candidates, recomputes predictions on the same group-by-query validation split, then compares predicted top-3 pages against SERP top-3 pages inside each query group. It is analysis-only: no training, no publish and no mutation of `backend/artifacts/page_quality_model.pkl`.

D50 evidence is stored in:

- `backend/artifacts/ranking-benchmarks/dataset-v5-d50/top3-regression-analysis.json`
- `backend/artifacts/ranking-benchmarks/dataset-v5-d50/top3-regression-analysis.md`

The analysis covers `190` validation rows across `20` validation queries. It found `20` candidate/query top-3 regressions and `9` query groups that need D51 preference-label focus. The main failure patterns are `rank_prior_disagreement=20`, `shortcut_text_volume=16` and `aggregator_or_marketplace_distortion=7`.

Candidate regression counts: RandomForestRegressor `8`, CatBoostRegressor `6`, CatBoostRanker `6`. The production CatBoost v3 artifact remains SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`.

D50 verification passed with `25` targeted ML tests covering the new top-3 analysis logic and nearby shadow/no-publish/training/model-schema behavior.

## D51 query-level preference labels

D51 materializes a ranking-aware `dataset-v5` evidence bundle. The goal is to keep the page-quality score signal from `dataset-v4`, while adding query-level preference labels that can teach the next model which pages should outrank others inside the same query group.

D51 runs `backend/app/ml/v5_preferences.py`. It copies `dataset-v4` into `dataset-v5`, marks the label schema as `ranking-aware-v5`, writes page labels and pairwise preference labels, regenerates the group-by-query split and writes dataset quality evidence. It does not train, publish, roll back or mutate the runtime artifact.

D51 evidence is stored in:

- `backend/data/dataset_versions/dataset-v5/dataset.csv`
- `backend/data/dataset_versions/dataset-v5/page_labels.csv`
- `backend/data/dataset_versions/dataset-v5/preference_labels.csv`
- `backend/data/dataset_versions/dataset-v5/split.json`
- `backend/data/dataset_versions/dataset-v5/manifest.json`
- `backend/data/dataset_versions/dataset-v5/d51-preference-split-validation.json`
- `backend/data/dataset_versions/dataset-v5/d51-query-preference-label-report.json`
- `backend/data/dataset_versions/dataset-v5/d51-query-preference-label-report.md`

The bundle contains `885` page labels and `3351` query-level preference labels. `2863` preferences are usable for training; `488` are marked `uncertain` with zero training weight so close or conflicting cases are documented without forcing a hard winner. Strength distribution: `strong=2047`, `weak=816`, `uncertain=488`.

D51 uses D50 evidence directly: all `9/9` D50 focus queries are represented in usable preference labels. Preference reasons are `ranking_target_margin=3258`, `d50_top3_recovery=74`, and `d50_top3_conflict_manual_review=19`. The split remains group-by-query with `79` train queries, `20` validation queries and `0` overlap; manifest is `ready_for_training=true`.

D51 verification passed with `35` targeted ML tests covering preference labels, D50 top-3 analysis, dataset-v4 compatibility, SEO-weighted labels, dataset quality, training pipeline and model schema behavior.

Production remains unchanged: `backend/artifacts/page_quality_model.pkl` stays SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D52 shortcut feature control

D52 adds a reusable feature policy for the ranking-aware v5 wave. It is not a training or publish step. The purpose is to prevent the next candidate from learning shortcuts such as "more text means better page" while still preserving genuine thin-page risk.

D52 runs `backend/app/ml/v5_feature_policy.py`. The policy version is `v5-shortcut-control-v1`. It classifies the `148` v3 features into `41` critical, `69` important and `38` supporting features. Critical features cover crawl/indexability, canonical, title/query fit, semantic fit and intent alignment. Supporting features include raw volume/count signals such as `word_count`, text/html length, heading counts, `link_count`, `image_count`, list/strong counts, density features and shallow commercial binaries.

The controlled dataset is stored at:

- `backend/data/dataset_versions/dataset-v5/dataset.controlled.csv`
- `backend/data/dataset_versions/dataset-v5/feature_policy.json`

The controlled dataset keeps all `885` rows and adds `feature_policy_version` per row. The policy caps `22` shortcut features and recorded `7733` capped shortcut values. This means a very thin page can still be penalized, but a long page cannot keep gaining score just because the extracted text, links or images are extremely large.

D52 also creates reusable release guardrails for D53/D54:

- feature dominance: a publishable candidate must not have a supporting shortcut as its top feature, and supporting features must not dominate top-10 importance;
- score response: synthetic degradation of critical SEO/search features must reduce score more than degradation of supporting shortcut features.

D52 evidence is stored in:

- `backend/artifacts/ranking-benchmarks/dataset-v5-d52/shortcut-feature-control-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v5-d52/shortcut-feature-control-report.md`

The guardrail smoke was run against the `3` saved D47 candidate artifacts. RF passed D52 feature/response checks; CatBoostRegressor failed feature dominance because its top feature remained supporting `word_count`; CatBoostRanker passed D52 feature/response checks but remains non-production due the D48/D49 top-3 and absolute-error release blockers. Verification passed with the D50-D52 and nearby ML regression set: `46` tests passed. Production remains unchanged: `backend/artifacts/page_quality_model.pkl` stays SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## Files relevant to the ML appendix

- `backend/app/ml/query_seeds.py`
- `backend/app/ml/dataset_builder.py`
- `backend/app/ml/v3_dataset.py`
- `backend/app/ml/v4_dataset.py`
- `backend/app/ml/seo_weighted_labels.py`
- `backend/app/ml/seo_weighted_candidate_training.py`
- `backend/app/ml/seo_weighted_shadow_benchmark.py`
- `backend/app/ml/seo_weighted_no_publish_decision.py`
- `backend/app/ml/top3_regression_analysis.py`
- `backend/app/ml/v5_preferences.py`
- `backend/app/ml/v5_feature_policy.py`
- `backend/app/ml/dataset_quality.py`
- `backend/app/ml/train.py`
- `backend/app/ml/evaluate.py`
- `backend/app/ml/publish.py`
- `backend/app/ml/controlled_publish.py`
- `backend/app/ml/model.py`
- `backend/app/ml/model_schema.py`
- `backend/docs/ml_feature_inventory.md`
- `backend/data/ru_commercial_dataset.manifest.json`
- `backend/artifacts/page_quality_model.metadata.json`


## D18 ranking benchmark workflow
A dedicated ranking benchmark workflow now exists in `app/ml/ranking_benchmark.py`.
Its purpose is to compare the current published baseline artifact against ranking-oriented candidates on the same grouped validation split.
The workflow supports the following candidate families:
- `CatBoostRanker` (`YetiRankPairwise`)
- `LightGBMRanker` when the dependency is available
- `XGBoost rank:pairwise` when the dependency is available
The benchmark report is written in both JSON and Markdown formats and includes:
- `NDCG@10`
- `Top-3 hit rate`
- `Spearman mean`
- stability across query groups
- stability across intents
- feature-importance summary for candidates that expose importances
This makes the D18 experiment reproducible and thesis-ready once the `dataset-v2` bundle has been materialized.
Example commands:
```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m app.ml.ranking_benchmark   --dataset data\dataset_versions\dataset-v2\dataset.csv   --manifest data\dataset_versions\dataset-v2\manifest.json   --reference-model artifacts\page_quality_model.pkl   --output-dir artifacts\ranking_reports\dataset-v2
```
To publish the best ranking candidate as the new primary artifact:
```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m app.ml.ranking_benchmark   --dataset data\dataset_versions\dataset-v2\dataset.csv   --manifest data\dataset_versions\dataset-v2\manifest.json   --reference-model artifacts\page_quality_model.pkl   --publish-best
```
