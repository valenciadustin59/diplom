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

The model currently uses `59` engineered features.

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

- `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl`

Public artifact metadata is stored in JSON sidecars:

- `backend/artifacts/page_quality_model.metadata.json`
- `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.metadata.json`

### Current published validation summary

According to the active published artifact metadata, the current model has:

- `model_type`: `RandomForestRegressor`
- `rmse`: `32.310547`
- `mae`: `27.884077`
- `spearman_mean`: `0.229632`
- `ndcg_at_10`: `0.844962`
- `top_3_hit_rate`: `0.9`
- `validation_queries`: `10`

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

## Files relevant to the ML appendix

- `backend/app/ml/query_seeds.py`
- `backend/app/ml/dataset_builder.py`
- `backend/app/ml/dataset_quality.py`
- `backend/app/ml/train.py`
- `backend/app/ml/evaluate.py`
- `backend/app/ml/publish.py`
- `backend/app/ml/model.py`
- `backend/docs/ml_feature_inventory.md`
- `backend/data/ru_commercial_dataset.manifest.json`
- `backend/artifacts/page_quality_model.metadata.json`
