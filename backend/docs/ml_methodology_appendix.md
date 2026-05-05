# Appendix: ML Methodology And Limitations

## Purpose of the ML component

The ML subsystem in this project is not used as an isolated black-box classifier. Its practical purpose is to estimate the competitive quality of a landing page for a search query by combining many heterogeneous signals into one ranking-oriented score.

For the diploma context, this is important for two reasons:

1. The system does not rely only on hand-written SEO checks such as `title_present` or `h1_count`.
2. The final score is based on the interaction between textual relevance, query alignment, structural quality and commercial usefulness.

In production terms, the model answers the following question:

`How competitive does this page look relative to pages that already rank for the same query?`

## Target variable and learning setup

The active runtime artifact is trained as a regression model, but the product no longer treats the raw model prediction as the whole answer.

The current `dataset-v5` target is built from a deterministic SEO-weighted rubric and query-level preference evidence. It is not a human-label dataset. The rubric intentionally gives more influence to factors that affect search interpretation and page competitiveness: crawl/indexability, canonical correctness, title/query fit, semantic/query fit, intent alignment, technical metadata and commercial trust. SERP position is retained as a small context signal and as diagnostics, not as the only definition of quality.

This means that the model does not predict "absolute website quality" in a universal sense. It predicts a query-dependent page-quality score that is later interpreted against the actual competitors found for the user's query.

At runtime the product has two score layers:

- `primary_page_score`: the model's score for the selected page using only the page/query feature vector;
- `competitiveness_score`: the product score after competitor aggregation, derived from the target page score plus gaps to the average and strongest processed competitors.

That design is defensible for this project because the business task is comparative SEO audit: "how competitive is this page for this query, and what should be improved to compete better?"

## Dataset methodology

### Data source

The main training evidence is collected from real search results for RU commercial queries and then materialized as versioned dataset bundles.

Current published snapshot:

- `dataset_version`: `dataset-v5`
- `artifact_version`: `dataset-v5-20260502151507`
- `rows_count`: `885`
- `queries_count`: `99`
- `domains_count`: `568`
- `label_schema`: `ranking-aware-v5`
- `feature_policy`: `v5-shortcut-control-v1`

The active training/evidence bundle is stored in:

- `backend/data/dataset_versions/dataset-v5/dataset.csv`
- `backend/data/dataset_versions/dataset-v5/dataset.controlled.csv`
- `backend/data/dataset_versions/dataset-v5/page_labels.csv`
- `backend/data/dataset_versions/dataset-v5/preference_labels.csv`
- `backend/data/dataset_versions/dataset-v5/manifest.json`
- `backend/data/dataset_versions/dataset-v5/split.json`

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

The runtime supports artifact-compatible feature schemas. Legacy `v1` has `59` engineered features. `v2` extends the baseline with reproducible snapshot auxiliary technical, commercial and trust features. The active production family uses `v3`: `148` pre-competitor features built from baseline, technical/commercial, heavy-analysis and intent-alignment signals. Runtime inference remains backward-compatible with older artifacts.

They are intentionally heterogeneous and cover three signal families:

1. Structural signals.
2. Query-aware lexical and semantic signals.
3. Technical, commercial, intent and interaction signals derived from relationships between base features.

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

Examples of technical/commercial/intent signals:

- `page_indexable`
- `canonical_signal_score`
- `technical_metadata_score`
- `commercial_trust_score`
- `intent_alignment_score`
- `commercial_intent_alignment`

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

The active runtime model is a `CatBoostRegressor` trained over tabular features with ranking-aware and product-aware evaluation.

That means the model predicts a continuous `0..100` page score, but model selection is not based only on regression loss. It is also validated with metrics that reflect ordering quality and product behavior.

### Current model candidates

The current research pipeline has evaluated:

- `RandomForestRegressor`
- `CatBoostRegressor`
- `CatBoostRanker`
- a hybrid pointwise/ranker candidate

The active published artifact after D58 is `pointwise_catboost_v5`, because it passed the D55/D56/D57 competitiveness scorecard and outperformed the previous v3 runtime on the blocking metrics.

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

Current interpretation:

- `RMSE` and `MAE` reflect score error magnitude;
- `Spearman mean` reflects rank-order agreement;
- `NDCG@10` measures quality of the predicted ordering across the top ten context;
- `Top-3 hit rate` is SERP-alignment diagnostics, not a release blocker. It is useful evidence about how closely the model imitates observed search order, but the project no longer treats SERP top-3 as a perfect quality truth because brand strength, advertising/popularity and marketplace effects can distort observed positions.

## Published primary artifact

The currently published runtime artifact is:

- `backend/artifacts/page_quality_model.pkl`

The system also stores an immutable versioned copy:

- active D58 artifact: `backend/artifacts/versions/page_quality_model--dataset-v5-20260502151507.pkl`
- rollback v3 artifact: `backend/artifacts/versions/page_quality_model--dataset-v3-d37-20260501200434.pkl`
- archived v1 rollback artifact: `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl`

Public artifact metadata is stored in JSON sidecars:

- `backend/artifacts/page_quality_model.metadata.json`
- `backend/artifacts/versions/page_quality_model--dataset-v5-20260502151507.metadata.json`
- `backend/artifacts/versions/page_quality_model--dataset-v3-d37-20260501200434.metadata.json`
- `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.metadata.json`

### Current published validation summary

According to the active D58 published artifact metadata, the current model has:

- `dataset_version`: `dataset-v5`
- `artifact_version`: `dataset-v5-20260502151507`
- `model_schema_version`: `v3`
- `model_type`: `CatBoostRegressor`
- `feature_count`: `148`
- `rmse`: `1.874197`
- `mae`: `1.22855`
- `spearman_mean`: `0.957788`
- `ndcg_at_10`: `0.998374`
- `top_3_hit_rate`: `0.6` as non-blocking SERP-alignment diagnostics
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

## Runtime scoring methodology

The final product score is not only the raw ML output.

The runtime has two stages:

1. The model predicts `primary_page_score` from the target page and query features.
2. After competitors are processed, `competitiveness-score-v1` compares the target page with the processed competitor set and writes `competitiveness_score` as the final product score when enough context exists.

Rule-based explanation factors and recommendation rules remain important, but they are used to explain and prioritize, not to replace the active CatBoost v5 prediction.

This strategy is appropriate for the current maturity level of the project because it balances three goals:

- practical robustness;
- explainability;
- product relevance to the user's actual SERP competitors.

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

### 1. Label proxy limitation

The current labels are deterministic expert-rubric and preference labels, not direct business outcomes and not true human labels.

Consequence:

- the model learns a proxy of competitive quality, not a universal notion of page usefulness;
- rubric choices and SERP-derived context can introduce bias even when top-3 is no longer a hard release blocker.

### 2. Dataset size is still moderate

`885` rows is enough for a meaningful local artifact, but not enough to claim broad generalization across all SEO scenarios.

Consequence:

- the current model should be presented as a strong local primary artifact for this project stage, not as a final industrial-grade universal ranker.

### 3. Query coverage is still focused

The current evidence covers `99` successful query groups from a controlled RU-commercial seed space.

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

The current published validation summary is based on `20` validation queries.

Consequence:

- ranking-aware metrics are informative, but still statistically limited;
- future iterations should increase the number of query groups used for evaluation.

## Recommended next methodological steps

The most important next steps are:

1. Increase successful query coverage across the full RU commercial seed catalog.
2. Expand the dataset with more domains and query groups.
3. Keep `top_3_hit_rate` as diagnostics, but avoid treating SERP position as the only truth.
4. Continue validating recommendation quality, not only score metrics.
5. Add human-reviewed labels for disputed high-impact queries if the project needs stronger real-world claims.
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

D38 historically published the D37 `pointwise_catboost` candidate only after validating the D37 shadow report decision and preserving the previous production artifact as rollback evidence. D58 later superseded this runtime alias with the v5 pointwise CatBoost artifact.

Historical D38 runtime artifact:

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

The CatBoostRegressor is the best D47 pointwise candidate by validation quality, but D47 is deliberately not a release decision. At that historical stage D48 still compared candidates against the active production artifact with a top-3 release gate; D55 later changed that interpretation.

D47 evidence is stored in:

- `backend/artifacts/ranking-benchmarks/dataset-v4-d47/candidate-artifact-training-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v4-d47/candidate-artifact-training-report.md`
- `backend/artifacts/ranking-benchmarks/dataset-v4-d47/d47-candidate-training-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v4-d47/d47-candidate-training-report.md`

D47 does not publish or mutate a runtime model. The production artifact `backend/artifacts/page_quality_model.pkl` remains SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D48 product-critical shadow benchmark

D48 evaluates the D47 candidates against the then-current production artifact with the release guardrails that existed before D55. It is intentionally a benchmark and decision-evidence step, not a training or publish step.

D48 runs `backend/app/ml/seo_weighted_shadow_benchmark.py`, which wraps the existing shadow benchmark and adds product-specific checks:

- then-current top-3 release gate: candidate `top_3_hit_rate` must not regress against current production;
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

The product score-response check passed for all candidates: critical SEO degradation produced a larger average score drop than supporting degradation. This is useful evidence that the D45/D46 rubric moved in the right direction, but under the historical D48 policy it did not override the top-3 release gate.

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

D50 starts the ranking-aware v5 wave. It analyzes why the dataset-v4 candidates were not published under the historical D48/D49 policy: the candidates improved absolute score fit but regressed the then-blocking top-3 behavior.

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

## D53 non-production ranking-aware v5 candidates

D53 trains candidate artifacts from the D51/D52 v5 evidence without changing the runtime artifact. It uses `backend/app/ml/v5_candidate_training.py` and the controlled dataset `backend/data/dataset_versions/dataset-v5/dataset.controlled.csv`.

The D53 split reuses the D51/D52 group-by-query split: `695` train rows, `190` validation rows, `79` train queries, `20` validation queries and `0` query overlap. The training surface uses the `148` v3 features and `2863` usable D51 preferences (`2194` train preferences, `669` validation preferences).

D53 creates three non-production artifacts:

- `backend/artifacts/page_quality_model.dataset-v5-pointwise-catboost-candidate.pkl`
- `backend/artifacts/page_quality_model.dataset-v5-ranking-aware-catboost-candidate.pkl`
- `backend/artifacts/page_quality_model.dataset-v5-hybrid-candidate.pkl`

All three have `.metadata.json` sidecars marked `non_production=true`, `runtime_enabled=false` and `publish_decision_required=D54`. Compatibility smoke passed for all three through `load_model_artifact` and `predict_score`.

Validation metrics:

- `pointwise_catboost_v5`: `MAE=1.22855`, `Spearman=0.957788`, `NDCG@10=0.998374`, `top_3_hit_rate=0.6`, weighted preference accuracy `0.784322`.
- `ranking_aware_catboost_v5`: `MAE=14.448487`, `Spearman=0.889367`, `NDCG@10=0.995447`, `top_3_hit_rate=0.55`, weighted preference accuracy `0.797401`.
- `hybrid_catboost_ranker_v5`: `MAE=2.816326`, `Spearman=0.953195`, `NDCG@10=0.998127`, `top_3_hit_rate=0.65`, weighted preference accuracy `0.788169`.

The ranking-aware candidate uses CatBoostRanker with D51 preference pairs and a calibrated `0..100` wrapper. The hybrid candidate combines the pointwise score with calibrated ranker signal at `0.18` ranking weight. D52 feature-dominance and score-response prechecks passed for all three saved artifacts.

D53 verification passed with the D50-D53 and nearby ML regression set: `50` tests passed. D53 is not a publish decision. The candidates are valid non-production evidence. Under the historical pre-D55 policy their `top_3_hit_rate` was still below the release target, so D54 had to perform the formal shadow benchmark and controlled publish/no-publish decision. Production remained unchanged at that point: `backend/artifacts/page_quality_model.pkl` stayed SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D54 v5 shadow benchmark and controlled decision

D54 runs the release gate for the D53 v5 candidates. It does not train another model and does not mutate the production artifact unless a candidate passes the publish guardrails.

The D54 runner is `backend/app/ml/v5_shadow_decision.py`. It reuses the fixed D51/D52 group-by-query validation split and compares the active production CatBoost v3 model against the three D53 non-production candidates. D55 adds `backend/app/ml/competitiveness_release_policy.py` and changes the future release decision layer to policy version `d55-product-aligned-v1`.

Under D55, `top_3_hit_rate` is no longer an absolute publish blocker for page-quality/competitiveness scoring. It is reported as SERP-alignment diagnostics and warnings. The blocking release scorecard is now separated into:

- page-quality/competitiveness metrics: MAE comparability, Spearman and NDCG@10;
- product guardrails: bounded validation scores, D52 feature-dominance, D52 score-response, and an explicit recommendation-consistency contract placeholder;
- SERP-alignment diagnostics: `top_3_hit_rate` versus the diagnostic floor and current production, non-blocking.

D54 evidence is stored in:

- `backend/artifacts/ranking-benchmarks/dataset-v5-d54/shadow-benchmark-guardrails-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v5-d54/shadow-benchmark-guardrails-report.md`
- `backend/artifacts/ranking-benchmarks/dataset-v5-d54/d54-shadow-decision-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v5-d54/d54-shadow-decision-report.md`

The D54 validation scope is `190` rows, `20` validation queries and `0` query overlap. The production reference on this controlled split has `MAE=7.452366`, `Spearman=0.51066`, `NDCG@10=0.981438` and `top_3_hit_rate=0.9`.

Candidate results:

- `pointwise_catboost_v5`: `MAE=1.22855`, `Spearman=0.957788`, `NDCG@10=0.998374`, `top_3_hit_rate=0.6`.
- `ranking_aware_catboost_v5`: `MAE=14.448487`, `Spearman=0.889367`, `NDCG@10=0.995447`, `top_3_hit_rate=0.55`.
- `hybrid_catboost_ranker_v5`: `MAE=2.816326`, `Spearman=0.953195`, `NDCG@10=0.998127`, `top_3_hit_rate=0.65`.

The historical D54 evidence was generated before D55 and records `keep_current` / `no_publish` with reason `no_candidate_passed_v5_release_guardrails`. D55 does not publish a model and does not mutate the production artifact; it updates the decision policy so future v5 release checks evaluate competitiveness quality without requiring candidates to copy SERP top-3 ordering. The production artifact remains unchanged at SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`.

## D55 product-aligned release policy

D55 records the key methodological correction after the product goal was clarified. The project is not trying to predict "which page Google puts in the top three" as its final truth. It is trying to estimate whether the selected page is competitive for a query and what can be improved.

D55 adds `backend/app/ml/competitiveness_release_policy.py` and policy version `d55-product-aligned-v1`. The blocking release scorecard is now:

- `MAE` comparability or improvement;
- `Spearman` and `NDCG@10` improvement or non-regression;
- bounded `0..100` score behavior;
- feature dominance that prevents raw shortcut/count features from leading the model;
- score-response checks where critical SEO degradation should hurt more than supporting-factor degradation;
- recommendation consistency for user-facing priorities.

`top_3_hit_rate` remains in reports as SERP-alignment diagnostics. A low value is a warning that the model is not copying the observed top-3 order, but it is not a publish blocker by itself.

## D56 competitiveness score layer

D56 adds the runtime bridge between model output and product meaning. The model still produces `primary_page_score`, but the audit's final displayed score becomes `competitiveness_score` when at least two competitors have been processed.

The backend comparison summary now exposes:

- `primary_page_score`;
- `competitiveness_score`;
- `score_basis`;
- `primary_score_difference`;
- `competitor_best_score`;
- `competitor_median_score`;
- `score_percentile`;
- `competitiveness_position_band`;
- the full `competitiveness` payload.

This makes the score match the user story: "how strong is my page compared with the pages currently competing for this query?"

## D57 competitor-gap recommendation priority

D57 adds `competitor-gap-priority-v1` to the recommendation layer. A recommendation is not high priority merely because a numeric value differs. Priority is derived from:

- the size of the gap against a strong-but-realistic competitor benchmark;
- SEO/search importance of the factor;
- controllability, meaning whether the site owner can realistically improve the factor;
- risk of overvaluing weak supporting signals such as raw text length or image count.

The recommendation payload can include `priority_score`, `priority_reason` and `priority_model_version`. Legacy recommendations remain supported.

## D58 controlled v5 publish under competitiveness scorecard

D58 re-evaluates the D53 candidates under the D55/D56/D57 scorecard and publishes `pointwise_catboost_v5`.

Evidence:

- `backend/app/ml/v5_competitiveness_publish.py`
- `backend/artifacts/ranking-benchmarks/dataset-v5-d58/d58-competitiveness-publish-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v5-d58/d58-competitiveness-publish-report.md`
- `backend/artifacts/ranking-benchmarks/dataset-v5-d58/shadow-benchmark-guardrails-report.json`
- `backend/artifacts/ranking-benchmarks/dataset-v5-d58/shadow-benchmark-guardrails-report.md`

Decision:

- `decision`: `publish_candidate`
- selected candidate: `pointwise_catboost_v5`
- production SHA1 after publish: `5374ca30f48f70d8629e7d84ec3df0524ef35b52`
- dataset: `dataset-v5`
- artifact version: `dataset-v5-20260502151507`
- model type: `CatBoostRegressor`
- feature count: `148`

Published metrics:

- `MAE=1.22855`
- `Spearman=0.957788`
- `NDCG@10=0.998374`
- `top_3_hit_rate=0.6` as non-blocking SERP diagnostics

The previous CatBoost v3 artifact remains available for rollback at `backend/artifacts/versions/page_quality_model--dataset-v3-d37-20260501200434.pkl`.

## D59-D61 documentation and product cleanup

D59 removes user-facing ML/debug clutter from the interface. D60 archives research artifacts and clarifies the difference between runtime assets and evidence/archive assets. D61 updates project documentation so future agents and readers see the current product framing first:

- the project estimates query-specific competitiveness, not abstract page quality;
- the active runtime model is `dataset-v5` pointwise CatBoost;
- `primary_page_score` and `competitiveness_score` are separate;
- `top_3_hit_rate` is diagnostics, not the main release truth;
- recommendations are prioritized by competitor gaps and search importance.

## D62-D82 final query-competitiveness evidence

D62-D68 changed the final model framing from abstract page quality to query-specific competitiveness: the score must first answer whether the page is about the concrete query, and only then use SEO quality, content depth, commercial trust, technical accessibility and competitor context.

D75-D78 materialized the real `dataset-v7-final` evidence surface:

- `3876` regular top-10 rows from `500/500` seed queries;
- `1000` hard negatives materialized from saved snapshot artifacts;
- `4876` deterministic expert-rubric labels;
- leakage-safe `group_by_query_category_stratified` split with `3898/978` train/validation rows and `0` query overlap.

D79 trained a non-production CatBoost v7 candidate with schema `v3` and `148` features. D80/D81 correctly kept production unchanged because `25` validation hard negatives were still predicted above the `35.0` hard-negative cap.

D82 fixes that blocker by adding schema `v4` with `156` features: the original `148` v3 features plus `8` query-core features for core query term coverage, exact core phrase presence and intent modifier coverage. It also adds a pickle-safe `QueryCoreGuardrailRegressor` wrapper that caps raw predictions to `35.0` when the page misses the query core and semantic similarity is weak.

D82 evidence:

- candidate artifact: `backend/artifacts/page_quality_model.dataset-v7-final-query-core-candidate.pkl`;
- candidate SHA1: `2bbf84bfcc77662d66f62cfdafbb6ee4d8264e88`;
- dataset: `backend/data/dataset_versions/dataset-v7-final/dataset.query-core.csv`;
- reports: `backend/artifacts/ranking-benchmarks/dataset-v7-final-d82/`;
- hard negatives above `35.0`: `0` instead of the D80 blocker `25`;
- runtime-adjusted candidate metrics: `MAE=4.253847`, `Spearman=0.917044`, `NDCG@10=0.996873`, `top_3_hit_rate=0.93` as diagnostics;
- reference runtime on the same split: `MAE=6.556754`, `Spearman=0.77064`, `NDCG@10=0.984659`, `top_3_hit_rate=0.83`.

D82 controlled decision is `publish_candidate`, but the artifact remains non-production until a separate controlled publish task explicitly replaces `backend/artifacts/page_quality_model.pkl`. The current active runtime remains the D58 `dataset-v5` artifact.

D83 closes the deployment-readiness gap. Before D83, the existing `--publish` path still targeted the old D80/D81 v3 flow and could not safely publish the D82 schema `v4` artifact. D83 parameterizes the controlled publish helper, adds a read-only readiness report and creates explicit commands:

```powershell
backend\.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --prepare-query-core-publish
backend\.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --publish-query-core
```

The readiness report is stored in `backend/artifacts/ranking-benchmarks/dataset-v7-final-d83/` and currently passes with failed checks `[]`. It verifies the D82 decision, candidate loadability, schema `v4`, feature count `156`, hard-negative guardrails, production SHA matching the D82 reference and that production has not already been replaced by the candidate. `--publish-query-core` must only be run after an explicit user decision to switch runtime.

## Files relevant to the ML appendix

- `backend/app/ml/query_seeds.py`
- `backend/app/ml/dataset_builder.py`
- `backend/app/ml/final_query_competitiveness.py`
- `backend/app/ml/query_core_model.py`
- `backend/app/ml/v3_dataset.py`
- `backend/app/ml/v4_dataset.py`
- `backend/app/ml/seo_weighted_labels.py`
- `backend/app/ml/seo_weighted_candidate_training.py`
- `backend/app/ml/seo_weighted_shadow_benchmark.py`
- `backend/app/ml/seo_weighted_no_publish_decision.py`
- `backend/app/ml/top3_regression_analysis.py`
- `backend/app/ml/v5_preferences.py`
- `backend/app/ml/v5_feature_policy.py`
- `backend/app/ml/v5_candidate_training.py`
- `backend/app/ml/v5_shadow_decision.py`
- `backend/app/ml/competitiveness_release_policy.py`
- `backend/app/ml/v5_competitiveness_publish.py`
- `backend/app/competitiveness.py`
- `backend/app/recommendations.py`
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
