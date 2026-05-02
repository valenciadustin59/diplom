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

- `manifest.json` marks the dataset as ready for training.
- Validation report proves no query leakage and stable row/query coverage.
- Existing dataset versions remain immutable.

## D47 / GitHub #66: Train SEO-Weighted Candidate Models

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

- Candidate artifacts load through the runtime model loader.
- Candidate metadata includes dataset version, feature count, training parameters and metrics.
- Training report explains why each candidate is or is not viable.

## D48 / GitHub #67: Product-Critical Shadow Benchmark

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

- Shadow benchmark report recommends one of:
  - `publish_candidate`;
  - `keep_current`;
  - `needs_more_data`.
- Report includes examples where the new score looks more convincing than current v3.
- No production artifact is changed.

## D49 / GitHub #68: Controlled Publish Or No-Publish Decision

Goal: make a safe release decision for the best D47/D48 candidate.

Scope:

- If D48 passes: perform controlled publish with rollback artifact preservation and product smoke.
- If D48 fails: create an explicit no-publish report and keep current production model.
- Update runtime model status docs and local handoff files.
- Verify UI score explanations and recommendations against current audits.

Acceptance criteria:

- Publish/no-publish decision is recorded in JSON and Markdown.
- If published, `backend/artifacts/page_quality_model.pkl` SHA changes and rollback SHA is recorded.
- If not published, production SHA remains unchanged and the reason is clear.
- Backend tests, frontend tests, and product smoke pass.
