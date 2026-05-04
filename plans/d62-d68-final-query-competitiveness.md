# D62-D68 Final Query-Competitiveness Model

This local mirror records the final-model implementation direction after the product goal was tightened again: the score must first answer whether the selected page matches the concrete query, then judge page quality and competitiveness.

## Implemented

- `D62`: runtime query relevance was introduced as a multiplier around score. D70 later superseded the exact contract with `query-relevance-contract-v2`, where confident full mismatch is `0-5` and ambiguous mismatch continues as `probable_mismatch` up to `25`. Commercial modifiers such as `купить` and `цена` are still treated as modifiers, not as the topic core.
- `D63`: `query_relevance_v2` seed catalog and `dataset-v7-final` seed manifest were generated from `scripts/generate_final_query_catalog.py`: `500` unique queries, `50` expanded categories, top-10 collection intent, and five cities.
- `D64-D67`: `app.ml.final_query_competitiveness` now provides the final release pipeline: validate dataset readiness, apply deterministic expert-rubric labels, train a v3 CatBoost candidate, run product guardrails, and publish only after a `publish_candidate` decision.
- `D80-D81`: the fresh `dataset-v7-final` candidate was benchmarked and not published. D80 selected `no_publish` because hard negatives were not learned below the `35.0` cap; D81 recorded controlled no-publish and kept `dataset-v5` active.
- `D68`: score explanation now supports five user-facing factor groups: query relevance, topic completeness, commercial trust, technical access, and competitor context. The UI keeps old top positive/negative factors as fallback for legacy audits.
- `D69`: collection readiness was added after this wave. `dataset_builder` now has `--max-domain-rows-per-domain`, and `app.ml.final_hard_negatives` materializes `dataset.with-hard-negatives.csv` from saved snapshots before final training.
- `D70`: conservative early-stop contract was added after this wave. D71 later wired confident full mismatch into audit orchestration, while ambiguous cases still continue the full audit.

## Current State

- `dataset-v6-query-relevance` remains historical draft evidence and is not the final training source.
- `dataset-v7-final` has live top-10 collection, hard negatives, deterministic labels, split validation, D79 candidate training and D80/D81 controlled no-publish evidence.
- Running `python -m app.ml.final_query_competitiveness --decide` writes the D80 release gate. Running `--publish` records D81 controlled publish/no-publish; with the current D80 report it does not mutate production.
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
