# D27-D31 Final Model Training And Publication

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with `PLANS.md` in the repository root.

## Purpose / Big Picture

The project is already a working distributed SEO audit web application. The remaining diploma-critical work is to make the ML evidence stronger: build the versioned `dataset-v2`, validate its quality, train a candidate model, compare it against the current model, publish the final model artifact, and prove through smoke audits that the product still works end to end.

The user-visible result is simple: after this plan is complete, a new audit should show score explanations coming from a freshly published `dataset-v2` model, while the timeline still proves distributed competitor fan-out and the UI remains stable.

## Progress

- [x] (2026-05-01 16:00 +05:00) GitHub issues were created through the Codex GitHub connector: `#46` through `#50`.
- [x] (2026-05-01 16:15 +05:00) Local fallback documentation was added because unauthenticated GitHub access to this private repository can return `404 Not Found`.
- [x] (2026-05-01 20:19 +05:00) D27: Built `dataset-v2` from seed offsets `0-49` and `50-99` after a clean rebuild. Generated `dataset.csv` with `885` successful rows, `failures.csv` with `49` failed fetches, `checkpoint.json`, `dataset.dataset.json`, and `885` snapshot artifacts. A temporary D27 quality probe reported `ready_for_training=true`, `query_coverage_ratio=0.22`, `failure_rate=0.052463`, and `artifact_coverage_ratio=1.0`.
- [x] (2026-05-01 20:26 +05:00) D27 was committed and pushed to `origin/main` in commit `0a9cd40`; GitHub issue `#46` closure was not verified because `gh` is not installed in this environment.
- [x] (2026-05-01 20:42 +05:00) D28: Generated canonical `split.json` with `group_by_query` mode (`695` train rows / `190` validation rows, `79` train queries / `20` validation queries, no query overlap) and canonical `manifest.json`. The manifest reports `ready_for_training=true`, `885` rows, `99` unique queries, `568` unique domains, `6` categories, `8` cities, `query_coverage_ratio=0.22`, `failure_rate=0.052463`, `artifact_coverage_ratio=1.0`, `missing_artifacts_count=0`, and no unmet requirements. D28 was pushed to `origin/main`; GitHub issue `#47` closure was not verified because `gh` is not installed in this environment.
- [x] (2026-05-01 20:53 +05:00) D29: Trained `artifacts/page_quality_model.dataset-v2-candidate.pkl` from `dataset-v2` without replacing `artifacts/page_quality_model.pkl`. The candidate is `RandomForestRegressor`, `model_schema_version=v2`, `dataset_version=dataset-v2`, `885` rows, `99` queries, `568` domains, `108` features. Validation metrics: `rmse=15.026923`, `mae=12.478412`, `spearman_mean=0.282468`, `ndcg_at_10=0.939192`, `top_3_hit_rate=0.9`, `split_mode=group_by_query`; production artifact hash/timestamp stayed unchanged. The optional CatBoost benchmark from the same training run reported `rmse=14.870781`, `mae=12.251912`, `spearman_mean=0.268463`, `ndcg_at_10=0.942102`, and `top_3_hit_rate=0.8`.
- [x] (2026-05-01 21:02 +05:00) D30: Ran ranking benchmark against the current production artifact and wrote `backend/artifacts/ranking-benchmarks/dataset-v2/ranking-benchmark-report.json` plus `.md`. The D29 candidate artifact was evaluated directly via `--candidate-model`; it improved absolute error versus production (`rmse` delta `-11.412967`, `mae` delta `-9.769919`) but underperformed production on ranking metrics (`spearman_mean` delta `-0.05409`, `ndcg_at_10` delta `-0.008862`, `top_3_hit_rate` delta `-0.05`). The report's publish recommendation is `keep_reference`; `artifacts/page_quality_model.pkl` hash/timestamp stayed unchanged.
- [x] (2026-05-01 21:29 +05:00) D31: Kept the current production artifact because D30 recommended `keep_reference`, verified `artifacts/page_quality_model.pkl` still resolves to `ru_commercial_dataset-20260421-primary` / schema `v1`, and ran full product smoke. Smoke audit `73128723-6a5b-41e6-81a7-d10aaa2570ad` (`ремонт квартир москва`, `https://smartremontmsk.ru/`, `top_n=2`) completed with score `69.5249`, `2` competitors found/analyzed, `0` failed competitors, `13` recommendations across `4` groups, competitor context enabled, and timeline fan-out `competitor_page` dispatch/terminal count `2`. Runtime readiness was `ready` with `4` workers and no missing queues; `/health/metrics` was `degraded` only because the local SQLite DB still has `3` old stuck `processing` rows. Smoke evidence is saved at `output/runtime-smoke/d31-smoke-summary.json`.

## Surprises & Discoveries

- Observation: Other Codex dialogs may not see GitHub issues for this repository.
  Evidence: public `https://github.com/valenciadustin59/diplom/issues` and `https://api.github.com/repos/valenciadustin59/diplom/issues?state=all&per_page=100` can return `404 Not Found` without authenticated GitHub access, even though `git ls-remote origin` works.

- Observation: `--top-n 5` does not override `top_n` values already stored in `dataset-v2/seeds.csv`; it only provides a default when a seed row has no `top_n`.
  Evidence: `load_seed_rows('data/dataset_versions/dataset-v2/seeds.csv', default_top_n=5)` loads `top_n=10` and `pages_to_scan=2` from the seed catalog, so each 50-seed batch can try up to 100 SERP pages rather than 50 single-page queries.

- Observation: Lazy concurrent loading of the sentence-transformers model can degrade a dataset run if HuggingFace connectivity resets during worker threads.
  Evidence: an intermediate batch produced `486` rows with `semantic_similarity=0` while logs showed repeated `huggingface.co` HEAD retries. After the local model cache became available and the generated dataset was rebuilt, the final D27 dataset has only `3` zero-semantic rows.

- Observation: Some SERP payloads can contain duplicate result URLs for the same query, and the old builder only filtered keys already written before the current page.
  Evidence: an intermediate dataset had `42` duplicate `(query,url)` groups. `backend/app/ml/dataset_builder.py` now deduplicates search results before submitting page fetches to the thread pool, and the clean D27 rebuild has `duplicate_query_url_groups=0`.

- Observation: The pre-D28 docs described creating `split.json` through `app.ml.train --split-output`, whose default behavior also trains and writes a model artifact.
  Evidence: `app.ml.train` defaulted `--model-output` to `artifacts/page_quality_model.pkl`; using it only to create `split.json` would have risked replacing the production model before D29-D31.

- Observation: D29 candidate artifacts are intentionally model evidence, but generic `backend/artifacts/*.pkl` files are ignored by default.
  Evidence: `.gitignore` now has a narrow exception for `backend/artifacts/page_quality_model.dataset-v2-candidate.pkl` so the D29 candidate can be committed without opening the ignore rule for arbitrary training artifacts.

- Observation: CatBoost writes local scratch logs when its optional training path runs.
  Evidence: D29 created `backend/catboost_info/` with training logs; this path is already ignored by `.gitignore` and is not part of the D29 evidence bundle. No candidate-side metadata file was generated outside the committed `.pkl`; metadata is stored inside the model artifact.

- Observation: The ranking benchmark originally compared only newly trained ranking candidates against production, not the D29 candidate artifact itself.
  Evidence: `app.ml.ranking_benchmark` now accepts `--candidate-model` and records `candidate_model_comparison_to_reference` so D30 can directly compare `page_quality_model.dataset-v2-candidate.pkl` with `page_quality_model.pkl`.

- Observation: `publish_best_ranking_model` is intentionally narrower than D30 benchmark comparison.
  Evidence: it only publishes newly trained ranking candidates (`candidate_family=ranking`) and now raises if an in-memory benchmark winner comes from a non-ranking candidate artifact. The D29 pointwise candidate can be evaluated by D30, but it is not publishable through this ranking publish helper.

## Decision Log

- Decision: Keep GitHub issues `#46-#50`, but duplicate the active backlog locally in `AGENTS.md`, `README.md`, `backend/README.md`, `docs/roadmap/product-development-roadmap.md`, and this ExecPlan.
  Rationale: future agents need to continue work from the repository alone if GitHub Issues are private or unavailable.
  Date/Author: 2026-05-01 / Codex

- Decision: Split the final ML work into five tasks: dataset build, dataset quality, candidate training, ranking benchmark, and final publish/smoke verification.
  Rationale: each stage has different failure modes and evidence requirements; splitting keeps commits and validation understandable.
  Date/Author: 2026-05-01 / Codex

- Decision: Keep the seed catalog unchanged and process the first two 50-seed offsets using the catalog's stored `top_n=10` and `pages_to_scan=2`.
  Rationale: the catalog is the source of truth for D17/D27 dataset coverage, and the first two controlled batches already pass the D28 quantitative gates without needing offsets `100` or `150`.
  Date/Author: 2026-05-01 / Codex

- Decision: Add pre-fetch SERP result deduplication to `dataset_builder` and rebuild D27 artifacts with `--overwrite`.
  Rationale: duplicate training rows bias model training and make artifact coverage less clear; fixing the builder before publishing D27 data is safer than post-processing generated CSV files.
  Date/Author: 2026-05-01 / Codex

- Decision: Add `app.ml.train --split-only` for D28 split generation and make requested split files part of manifest readiness checks.
  Rationale: D28 needs a reproducible `group_by_query` split without training or publishing a model; a manifest that names a split path should fail readiness if that split is missing or leaks queries across train/validation.
  Date/Author: 2026-05-01 / Codex

- Decision: Keep the current production artifact after D30.
  Rationale: the D29 candidate has substantially lower absolute error, but ranking quality is the product-critical signal for SEO recommendations and the benchmark shows worse Spearman, NDCG@10 and top-3 hit rate than the current production artifact.
  Date/Author: 2026-05-01 / Codex

## Outcomes & Retrospective

D27 is complete and pushed. The versioned `dataset-v2` bundle has enough rows, query coverage, domain coverage, city coverage and artifact coverage for the final ML evidence wave. The main implementation lesson is that live dataset collection needs quality probes between batches: the first attempt revealed duplicate SERP rows and a transient semantic-model loading problem, both of which were resolved before keeping the final generated data.

D28 is complete. `backend/data/dataset_versions/dataset-v2/manifest.json` and `backend/data/dataset_versions/dataset-v2/split.json` are now the canonical training-readiness evidence for `dataset-v2`.

D29 is complete. The candidate model is saved at `backend/artifacts/page_quality_model.dataset-v2-candidate.pkl`, and the current production model `backend/artifacts/page_quality_model.pkl` still points to the older `ru_commercial_dataset-20260421-primary` artifact with schema `v1`. D29 reused the same deterministic split parameters as D28 (`test_size=0.2`, `random_state=42`); `split.json` and `manifest.json` were refreshed only so the embedded split summary timestamps match the training run, not because dataset rows or query partitions changed.

D30 is complete. The benchmark report recommends `keep_reference`, so D31 should not blindly publish the D29 candidate. If D31 still proceeds, it must either keep the current production artifact and document the no-publish decision, or explicitly override based on a stronger product rationale than the current ranking benchmark.

D31 is complete. The final decision is no-publish/keep-reference: `backend/artifacts/page_quality_model.pkl` remains the current production artifact, while the D29 candidate and D30 benchmark report remain versioned evidence. Runtime smoke confirmed the unchanged production model still serves audit scoring, recommendations, competitor analysis and timeline fan-out.

## Context and Orientation

The repository root is `E:\codexPROJ\diplom`. Work only inside this repository.

The backend lives in `backend/`. The relevant ML modules are:

- `backend/app/ml/dataset_builder.py`: builds CSV rows from query seeds, SERP results, fetched pages, extracted features, weak labels, optional expert labels, failures and raw extraction artifacts.
- `backend/app/ml/dataset_quality.py`: creates `manifest.json` and evaluates whether a dataset is ready for training.
- `backend/app/ml/train.py`: trains page-quality models, creates train/validation splits, records metrics and writes model artifacts.
- `backend/app/ml/ranking_benchmark.py`: compares candidate ranking-aware models with a reference model and can publish the best one.
- `backend/app/ml/publish.py`: publishes the primary runtime model artifact from a ready dataset manifest.
- `backend/app/ml/model.py`: runtime scoring, model loading, score explanation and fallback behavior.

The versioned dataset bundle is:

- `backend/data/dataset_versions/baseline-v1/`: frozen baseline dataset from the earlier model workflow.
- `backend/data/dataset_versions/dataset-v2/`: target bundle for the final model.

As of this plan, `dataset-v2` already has:

- `seeds.csv`: 450 seed queries.
- `expert_labels.csv`: template for expert labels.
- `dataset.json`: dataset metadata.

The expected new/generated files during this plan are:

- `backend/data/dataset_versions/dataset-v2/dataset.csv`
- `backend/data/dataset_versions/dataset-v2/failures.csv`
- `backend/data/dataset_versions/dataset-v2/checkpoint.json`
- `backend/data/dataset_versions/dataset-v2/manifest.json`
- `backend/data/dataset_versions/dataset-v2/split.json`
- `backend/data/dataset_versions/dataset-v2/artifacts/`
- candidate and final model artifacts under `backend/artifacts/`

Do not add demo mode. Do not rewrite backend orchestration. Do not close GitHub issues until implementation is verified, committed and pushed.

## Plan of Work

Start with D27. Build the dataset in small batches instead of one huge run. The dataset builder is idempotent when checkpoint files are kept, so interrupted runs can continue.

After enough rows are collected, run D28. The manifest must prove that the dataset is ready for training. If `ready_for_training` is false, return to D27 and collect more rows rather than forcing training.

Then run D29. Train a candidate model to a candidate path first. Do not overwrite `backend/artifacts/page_quality_model.pkl` until benchmark and smoke checks justify publishing.

Then run D30. Use ranking benchmark to compare the candidate against the current production artifact. SEO scoring is query-relative, so ranking evidence matters more than a single absolute regression metric.

Finally run D31. Apply the D30 publish/no-publish decision, run tests, start the full stack, run smoke audits, verify UI tabs, and commit/push the artifacts and docs.

## Concrete Steps

All commands below assume PowerShell.

### D27: Build dataset-v2 in batches

Working directory:

    cd E:\codexPROJ\diplom\backend

First batch:

    .venv\Scripts\python.exe -m app.ml.dataset_builder `
      --dataset-version dataset-v2 `
      --versioned-layout `
      --expert-labels data\dataset_versions\dataset-v2\expert_labels.csv `
      --top-n 5 `
      --seed-offset 0 `
      --seed-limit 50 `
      --max-workers 4 `
      --query-delay 1.0

Continue with offsets:

    --seed-offset 50
    --seed-offset 100
    --seed-offset 150

Continue until the manifest in D28 can pass quality gates. If SearXNG starts returning many empty SERPs, timeouts, CAPTCHA-like failures or 403 responses, reduce `--max-workers` to `2` and increase `--query-delay` to `2.0` or more.

Run D27 checks:

    .venv\Scripts\python.exe -m pytest tests\test_training_pipeline.py tests\test_training_dataset_quality.py

### D28: Validate quality gates and split

Working directory:

    cd E:\codexPROJ\diplom\backend

Create or update the query-grouped split without training a model:

    .venv\Scripts\python.exe -m app.ml.train `
      --dataset data\dataset_versions\dataset-v2\dataset.csv `
      --dataset-version dataset-v2 `
      --split-output data\dataset_versions\dataset-v2\split.json `
      --test-size 0.2 `
      --random-state 42 `
      --split-only

Create or update the manifest:

    .venv\Scripts\python.exe -m app.ml.dataset_quality `
      --dataset data\dataset_versions\dataset-v2\dataset.csv `
      --failures data\dataset_versions\dataset-v2\failures.csv `
      --seeds data\dataset_versions\dataset-v2\seeds.csv `
      --dataset-version dataset-v2 `
      --baseline-version baseline-v1 `
      --artifacts-dir data\dataset_versions\dataset-v2\artifacts `
      --split data\dataset_versions\dataset-v2\split.json `
      --output data\dataset_versions\dataset-v2\manifest.json

Open `backend/data/dataset_versions/dataset-v2/manifest.json` and check:

- `quality_gates.ready_for_training` is `true`, or unmet requirements are clearly understood.
- row, query, domain, category and city coverage are adequate.
- `artifact_coverage_ratio` is present.
- `label_source_distribution` is present.
- `split_path` points to `split.json` and split checks are satisfied.

Run D28 checks:

    .venv\Scripts\python.exe -m pytest tests\test_training_dataset_quality.py tests\test_training_pipeline.py

### D29: Train candidate model

Working directory:

    cd E:\codexPROJ\diplom\backend

Train without replacing production:

    .venv\Scripts\python.exe -m app.ml.train `
      --dataset data\dataset_versions\dataset-v2\dataset.csv `
      --dataset-version dataset-v2 `
      --model-output artifacts\page_quality_model.dataset-v2-candidate.pkl `
      --split-output data\dataset_versions\dataset-v2\split.json `
      --test-size 0.2 `
      --random-state 42 `
      --model-schema-version v2

Expected result:

- candidate artifact exists;
- output includes metrics;
- metadata contains `dataset_version=dataset-v2` and `model_schema_version=v2`;
- current `artifacts/page_quality_model.pkl` is not replaced.

Run D29 checks:

    .venv\Scripts\python.exe -m pytest tests\test_training_pipeline.py tests\test_model_schema.py tests\test_model_evaluate.py

### D30: Run ranking benchmark

Working directory:

    cd E:\codexPROJ\diplom\backend

Run benchmark against the current artifact:

    .venv\Scripts\python.exe -m app.ml.ranking_benchmark `
      --dataset data\dataset_versions\dataset-v2\dataset.csv `
      --manifest data\dataset_versions\dataset-v2\manifest.json `
      --reference-model artifacts\page_quality_model.pkl `
      --candidate-model artifacts\page_quality_model.dataset-v2-candidate.pkl `
      --output-dir artifacts\ranking-benchmarks\dataset-v2 `
      --test-size 0.2 `
      --random-state 42 `
      --model-schema-version v2

Expected result:

- a benchmark report exists in `backend/artifacts/ranking-benchmarks/dataset-v2/`;
- report includes best candidate, reference model and comparison;
- there is a clear publish/no-publish decision (`publish_recommendation`).

Run D30 checks:

    .venv\Scripts\python.exe -m pytest tests\test_ranking_benchmark.py tests\test_model_evaluate.py tests\test_model_publish.py

### D31: Publish/no-publish decision and smoke-test final model state

D30 currently recommends `keep_reference`. Treat this as a valid D31 completion path: do not replace `artifacts/page_quality_model.pkl` unless there is an explicit, documented override rationale.

If keeping the current production artifact, verify the no-publish state first:

    cd E:\codexPROJ\diplom\backend
    .venv\Scripts\python.exe -c "from pathlib import Path; from app.ml.model import load_model_artifact; artifact = load_model_artifact(Path('artifacts/page_quality_model.pkl')); print({'dataset_version': artifact.get('dataset_version'), 'model_schema_version': artifact.get('model_schema_version'), 'artifact_version': artifact.get('artifact_version')})"

Then run smoke checks against the unchanged production artifact.

Only publish through `app.ml.publish` if D31 intentionally overrides D30:

    cd E:\codexPROJ\diplom\backend
    .venv\Scripts\python.exe -m app.ml.publish `
      --dataset data\dataset_versions\dataset-v2\dataset.csv `
      --manifest data\dataset_versions\dataset-v2\manifest.json `
      --model-output artifacts\page_quality_model.pkl `
      --test-size 0.2 `
      --random-state 42 `
      --model-schema-version v2

Or publish the best newly trained ranking model if a new benchmark proves that path is better. This helper does not publish the D29 pointwise candidate artifact directly:

    cd E:\codexPROJ\diplom\backend
    .venv\Scripts\python.exe -m app.ml.ranking_benchmark `
      --dataset data\dataset_versions\dataset-v2\dataset.csv `
      --manifest data\dataset_versions\dataset-v2\manifest.json `
      --reference-model artifacts\page_quality_model.pkl `
      --model-output artifacts\page_quality_model.pkl `
      --output-dir artifacts\ranking-benchmarks\dataset-v2 `
      --publish-best `
      --test-size 0.2 `
      --random-state 42 `
      --model-schema-version v2

After the publish/no-publish decision, restart the full stack:

    cd E:\codexPROJ\diplom
    npm start

Check readiness:

    Invoke-RestMethod -Uri http://127.0.0.1:8000/health/ready

Run at least one smoke audit with competitors:

    $body = @{ query = "ремонт квартир москва"; target_url = "https://smartremontmsk.ru/"; top_n = 2 } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/audits -ContentType "application/json" -Body $body

Poll `GET /audits/{audit_id}` until status is `completed` or `completed_with_warnings`, then check `GET /audits/{audit_id}/events/diagnostics`. Acceptance requires `fan_out.stage=competitor_page` when competitors are found.

## Validation and Acceptance

At the end of D31, run:

    cd E:\codexPROJ\diplom
    npm run build
    npm run site:check
    npm --prefix frontend test -- --run
    npm run test:scripts

Backend deterministic regression:

    cd E:\codexPROJ\diplom\backend
    $env:CELERY_BROKER_URL = "redis://localhost:1/0"
    $env:CELERY_RESULT_BACKEND = "redis://localhost:1/0"
    .venv\Scripts\python.exe -m pytest
    Remove-Item Env:CELERY_BROKER_URL, Env:CELERY_RESULT_BACKEND

If full backend pytest exceeds the local timeout because of slow lifecycle tests, run by file and record split-run evidence. The known slow area is `tests/test_audits_api.py`, whose lifecycle tests can take tens of seconds each.

Acceptance for the whole plan:

- `dataset-v2` has dataset, failures, checkpoint, manifest, split and artifacts.
- Manifest says the dataset is ready for training, or a deliberate exception is documented.
- Candidate model has been trained and benchmarked.
- Final model artifact is either published with public metadata or deliberately kept unchanged when benchmark evidence says `keep_reference`.
- Runtime score explanation reports the final selected artifact. For this D31 run, that is the unchanged `ru_commercial_dataset-20260421-primary` / schema `v1` production artifact because D30 rejected publishing the `dataset-v2` candidate.
- At least one smoke audit with competitors completes and timeline diagnostics shows fan-out.
- UI tabs still render: overview, report, recommendations, timeline, pages, competitors, history and stack.
- Changes are committed and pushed.

## Idempotence and Recovery

Dataset build is safe to resume as long as `checkpoint.json` remains. Do not delete checkpoint unless intentionally rebuilding from scratch.

Candidate artifacts should use unique filenames and are safe to delete if a run is bad. Do not delete or replace `backend/artifacts/page_quality_model.pkl` until D31.

If the published model behaves badly, restore the previous `backend/artifacts/page_quality_model.pkl` from git history or from the versioned artifact copy produced by `app.ml.publish`.

If GitHub Issues are inaccessible, continue from this file and mention local D27-D31 references in commit messages and final summaries.

## Artifacts and Notes

GitHub issue mapping:

- `D27`: https://github.com/valenciadustin59/diplom/issues/46
- `D28`: https://github.com/valenciadustin59/diplom/issues/47
- `D29`: https://github.com/valenciadustin59/diplom/issues/48
- `D30`: https://github.com/valenciadustin59/diplom/issues/49
- `D31`: https://github.com/valenciadustin59/diplom/issues/50

These links may return `404 Not Found` without authenticated access. That is expected for a private repository and is not evidence that the tasks do not exist.

## Interfaces and Dependencies

Use the existing project interfaces only:

- `app.ml.dataset_builder.build_dataset`
- `app.ml.dataset_quality.save_dataset_manifest`
- `app.ml.train.train_quality_model`
- `app.ml.ranking_benchmark.run_ranking_benchmark`
- `app.ml.ranking_benchmark.publish_best_ranking_model`
- `app.ml.publish.publish_primary_model`
- `app.ml.model.load_model_artifact`

External services:

- Redis and Celery workers for runtime smoke audits.
- SearXNG for SERP collection and dataset building.

Python libraries already used by the project:

- `scikit-learn` for baseline modeling and split logic.
- `catboost` for optional candidate/benchmark paths.
- `httpx` for HTTP calls.
- `sentence-transformers` for semantic features.

Revision note: created on 2026-05-01 to make D27-D31 visible to future agents even when GitHub Issues are unavailable.
