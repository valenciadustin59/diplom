# D55-D61 Product-Aligned Competitiveness Wave

This document is the local mirror for GitHub issues `#74-#80`. It exists so future agents can understand the post-D54 change in product direction even if GitHub Issues are unavailable from their environment.

## Purpose

The clarified product goal is: evaluate how competitive a chosen landing page is for a concrete search query using popular/top-N SERP pages as context, then produce recommendations that help the page compete better for that query.

This wave corrects the earlier over-emphasis on `top_3_hit_rate`. Search top-3 can reflect page quality, but it can also reflect brand strength, marketplace dominance, advertising/popularity and historical authority. Therefore, `top_3_hit_rate` remains useful diagnostics, but the release decision should prioritize page-quality/competitiveness metrics and user-facing recommendation quality.

## Completed Tasks

- `D55` / GitHub `#74` - completed and pushed: release policy version `d55-product-aligned-v1`. Blocking checks are `MAE`, `Spearman`, `NDCG@10`, bounded scores, feature dominance, score response and recommendation consistency. `top_3_hit_rate` is SERP-alignment diagnostics, not a publish blocker.
- `D56` / GitHub `#75` - completed and pushed: runtime `competitiveness-score-v1`. The original model output is preserved as `primary_page_score`; when at least two competitors are processed, final `audit.score` and `score_breakdown.final_score` become `competitiveness_score`.
- `D57` / GitHub `#76` - completed and pushed: recommendations now use `competitor-gap-priority-v1`, combining competitor gap size, SEO/search importance and controllability.
- `D58` / GitHub `#77` - completed and pushed: re-evaluated D53 v5 candidates under the competitiveness scorecard and published `pointwise_catboost_v5`.
- `D59` / GitHub `#78` - completed and pushed: removed user-facing ML/debug clutter from the product UI.
- `D60` / GitHub `#79` - completed and pushed: archived research artifacts and clarified runtime versus evidence assets.
- `D61` / GitHub `#80` - completed locally by this documentation pass: root README, backend README, roadmap, ML appendix and AGENTS handoff now describe the competitiveness goal and current v5 runtime.

## Current Runtime

- Runtime artifact: `backend/artifacts/page_quality_model.pkl`
- SHA1: `5374ca30f48f70d8629e7d84ec3df0524ef35b52`
- Dataset: `dataset-v5`
- Artifact version: `dataset-v5-20260502151507`
- Model: `CatBoostRegressor`
- Schema: `v3`
- Feature count: `148`
- Candidate name: `pointwise_catboost_v5`
- Metrics: `MAE=1.22855`, `Spearman=0.957788`, `NDCG@10=0.998374`, `top_3_hit_rate=0.6`
- Interpretation: `top_3_hit_rate` is non-blocking SERP-alignment diagnostics.

## Runtime Score Semantics

- `primary_page_score` means the model's evaluation of the selected page from its own page/query features.
- `competitiveness_score` means the final product score after comparing the target page with processed competitors.
- `score_basis` tells whether the final score is based on competitor context or falls back to the primary page score.
- Recommendations should be read through `competitor-gap-priority-v1`, not raw factor values alone.

## Evidence

- D55 policy: `backend/app/ml/competitiveness_release_policy.py`
- D56 runtime layer: `backend/app/competitiveness.py`
- D57 recommendation layer: `backend/app/recommendations.py`
- D58 publish runner: `backend/app/ml/v5_competitiveness_publish.py`
- D58 reports: `backend/artifacts/ranking-benchmarks/dataset-v5-d58/`
- Active metadata: `backend/artifacts/page_quality_model.metadata.json`
- Rollback v3 artifact: `backend/artifacts/versions/page_quality_model--dataset-v3-d37-20260501200434.pkl`

## Notes For Future Work

Do not re-run the old D45-D54 no-publish conclusion as if it were the current release policy. D54 is historical evidence generated before D55. A new modeling task should use the product-aligned competitiveness scorecard and should also verify that recommendations remain useful, understandable and grounded in competitor gaps.
