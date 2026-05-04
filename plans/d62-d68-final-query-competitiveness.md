# D62-D68 Final Query-Competitiveness Model

This local mirror records the final-model implementation direction after the product goal was tightened again: the score must first answer whether the selected page matches the concrete query, then judge page quality and competitiveness.

## Implemented

- `D62`: runtime query relevance is now `query-relevance-multiplier-v1`. Severe topic mismatch uses a multiplier and keeps the final score in `0-15`; page-unusable cases remain `0-10`; weak and partial matches use lower multipliers. Commercial modifiers such as `купить` and `цена` are still treated as modifiers, not as the topic core.
- `D63`: `query_relevance_v2` seed catalog and `dataset-v7-final` seed manifest were generated from `scripts/generate_final_query_catalog.py`: `500` unique queries, `50` expanded categories, top-10 collection intent, and five cities.
- `D64-D67`: `app.ml.final_query_competitiveness` now provides the final release pipeline: validate dataset readiness, apply deterministic expert-rubric labels, train a v3 CatBoost candidate, run product guardrails, and publish only after a `publish_candidate` decision.
- `D68`: score explanation now supports five user-facing factor groups: query relevance, topic completeness, commercial trust, technical access, and competitor context. The UI keeps old top positive/negative factors as fallback for legacy audits.
- `D69`: collection readiness was added after this wave. `dataset_builder` now has `--max-domain-rows-per-domain`, and `app.ml.final_hard_negatives` materializes `dataset.with-hard-negatives.csv` from saved snapshots before final training.

## Current State

- `dataset-v6-query-relevance` remains historical draft evidence and is not the final training source.
- `dataset-v7-final` is ready for collection, not ready for training. Its manifest intentionally has `ready_for_training=false` until live top-10 collection and deterministic labels are produced.
- Running `python -m app.ml.final_query_competitiveness` writes a blocked evidence report instead of publishing a weak/unfinished model.
- The active runtime artifact is still the D58 v5 CatBoost artifact, but the runtime score contract now applies the stricter final relevance multiplier around that model output.

## Commands

Generate final seeds:

```powershell
backend\.venv\Scripts\python.exe scripts\generate_final_query_catalog.py
```

Validate final dataset readiness:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --validate
```

Collect final top-10 dataset with domain cap:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.dataset_builder --versioned-layout --dataset-version dataset-v7-final --max-domain-rows-per-domain 12 --max-workers 6 --query-delay 1.0
```

After real top-10 collection and `ready_for_training=true`:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.final_hard_negatives --max-negatives-per-query 2
.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --train
.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --decide
.venv\Scripts\python.exe -m app.ml.final_query_competitiveness --publish
```

## Guardrails

- Full mismatch pages must stay below `20`, and unrelated pages must not exceed `35`.
- Relevant pages without `купить` or `цена` must not be penalized when the query does not contain those modifiers.
- Product guardrails take priority over `top_3_hit_rate`; top-3 is diagnostic only.
- Controlled publish must preserve rollback and write SHA1/report evidence.
