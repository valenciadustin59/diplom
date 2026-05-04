# Roadmap текущего этапа Site Audit

Этот документ нужен как читаемый стратегический ориентир для разработчиков и Codex-агентов. Операционный handoff, ограничения и актуальные ссылки на GitHub issues всегда начинаются с `AGENTS.md`; этот roadmap объясняет, куда развивать проект дальше и какие завершённые волны не нужно повторять.

Проект находится в репозитории `E:\codexPROJ\diplom`. Тема диплома: web-приложение машинного обучения на основе распределённых вычислений. Поэтому roadmap оценивается не только по SEO-функциям, но и по тому, насколько хорошо проект демонстрирует ML workflow, distributed runtime и понятный web-интерфейс.

## Текущий статус

Базовый пользовательский сценарий уже реализован: пользователь вводит поисковый запрос и URL, система собирает конкурентные страницы из SERP, анализирует target и competitors, считает базовый ML score страницы, пересчитывает итоговый конкурентный score относительно обработанных конкурентов и формирует рекомендации по самым важным отставаниям.

Завершённые волны:

- `D1-D12` — distributed runtime foundation: stage-based Celery pipeline, per-stage queues, distributed fan-out, retry-safe orchestration, health/live, health/ready, health/metrics, event log, timeline diagnostics, queue pressure, admission control, worker topology profiles и benchmark/reporting workflow.
- `D13-D26` — SEO/ML/product/frontend evidence wave: snapshot extraction, feature schema v2, technical SEO features, commercial/trust features, intent-aware and SERP-relative features, dataset-v2 workflow, model schema v2, artifact-driven training/publish flow, grouped recommendations API/UI, isolated `audits.heavy_analysis` queue, audit report/export dashboard, audit execution timeline UI, панель состояния рабочего стека/очередей, audit history management, recommendation action tracking и interface terminology polish.

После `D26` проект уже соответствовал дипломной теме, а последующие волны довели ML/product layer до текущей product-aligned версии. Исторически D27-D44 построили dataset/model evidence, v3 rollout, runtime observability и second-pass experiment. D45-D54 проверили SEO-weighted и ranking-aware candidates. D55-D58 уточнили продуктовую цель: не копировать SERP top-3 как абсолютную истину, а оценивать конкурентоспособность страницы в top-N контексте. D58 опубликовал активный `dataset-v5` pointwise CatBoost artifact.

Текущий runtime: `backend/artifacts/page_quality_model.pkl`, SHA1 `5374ca30f48f70d8629e7d84ec3df0524ef35b52`, dataset `dataset-v5`, artifact `dataset-v5-20260502151507`, schema `v3`, `CatBoostRegressor`, `148` features. `top_3_hit_rate` теперь SERP-alignment diagnostics, not a release blocker.

Важно: GitHub Issues приватного репозитория могут быть недоступны другим Codex-диалогам без авторизации и возвращать `404 Not Found`. Поэтому актуальный operational status продублирован локально в `AGENTS.md`, `README.md`, `backend/README.md`, `backend/docs/ml_methodology_appendix.md` и planning files.

## Завершённая волна: D21-D26 Frontend/Product Layer

Эта волна была заведена в GitHub как issues `#40-#45` и закрыта после D26. Demo mode намеренно не входил в этот backlog: пользователь выбрал развивать продуктовые и демонстрационные возможности без отдельного демо-режима.

## Завершённая волна: D27-D31 Final ML Model Evidence

Эта волна заведена как GitHub issues `#46-#50` и закрыта как completed после проверки кода, артефактов, коммитов и push.

- `D27` / `#46`: completed/pushed; `dataset-v2` собран из seed catalog контролируемыми батчами.
- `D28` / `#47`: completed/pushed; quality gates, `manifest.json`, artifact coverage и `group_by_query` split проверены.
- `D29` / `#48`: completed; candidate page-quality model обучена на `dataset-v2` без замены production artifact.
- `D30` / `#49`: completed; ranking benchmark сравнил candidate с текущей моделью и рекомендует `keep_reference`.
- `D31` / `#50`: completed locally; no-publish/keep-reference decision по D30 принят, продукт проверен smoke-аудитом.
- D31 clean rerun evidence: `scripts/d31-runtime-smoke.mjs` regenerated `output/runtime-smoke/d31-smoke-summary.json` from a clean stack; audit `45ca43ab-fb3a-4045-a28a-5f012cee4ffb` completed with `4` workers, missing queues `[]`, `2/2` competitors analyzed, `13` recommendations, `competitor_page` fan-out `2/2`, and runtime model `ru_commercial_dataset-20260421-primary` / schema `v1`.

Подробный план выполнения находится в `plans/d27-d31-final-model-training.md`.

## Завершённая волна: D32-D36 Model Productization

Эта волна заведена как GitHub issues `#51-#55`. Её смысл — не заменить модель любой ценой, а довести candidate до безопасного publish gate: экспертные метки, ranking-aware обучение, shadow benchmark, explainability guardrails, controlled publish или documented keep-reference.

- `D32` / `#51`: completed locally; `197` expert-rubric labels for `dataset-v2`.
- `D33` / `#52`: completed locally; refreshed `manifest.json` and `split.json` after expert labels.
- `D34` / `#53`: completed locally; RF, CatBoost and CatBoostRanker candidate artifacts trained without replacing production.
- `D35` / `#54`: completed locally; shadow benchmark and explainability guardrails recommend `keep_reference`.
- `D36` / `#55`: completed locally; controlled keep-reference/no-publish decision, rollback evidence and product smoke verification.

Подробный план выполнения находится в `plans/d32-d36-model-productization.md`.

## Current D37 Evidence: Unified V3 Feature Model

GitHub issue `#56` is implemented locally for `D37: Unified v3 feature model with hybrid ensemble and top-3 guardrail`. Local source of truth: `plans/d37-unified-v3-hybrid-ensemble-top3-guardrail.md`.

D37 was implemented as a real unified feature model, not as only a prediction average of RF, CatBoost and Ranker artifacts.

Completed D37 scope:

- added `MODEL_SCHEMA_VERSION_V3`;
- used `148` pre-competitor features: `59` baseline + `49` technical/commercial + `25` heavy-analysis + `15` intent-alignment;
- created `backend/data/dataset_versions/dataset-v3-d37/` with actual v3 columns;
- trained non-production RF v3, CatBoost v3 and CatBoostRanker v3 candidates;
- compared every candidate against the current production reference;
- kept `backend/artifacts/page_quality_model.pkl` unchanged during D37 candidate training and benchmark.

D37 evidence:

- dataset rows: `885`
- queries: `99`
- split: `group_by_query`, `695` train rows, `190` validation rows, no query leakage
- source artifacts found: `885/885`
- training report: `backend/artifacts/ranking-benchmarks/dataset-v3-d37/candidate-artifact-training-report.json`
- shadow report: `backend/artifacts/ranking-benchmarks/dataset-v3-d37-shadow/shadow-benchmark-guardrails-report.json`
- decision: `publish_candidate`
- selected candidate: `pointwise_catboost`
- selected candidate metrics: `top_3_hit_rate=0.95`, `ndcg_at_10=0.945929`, `spearman_mean=0.421894`, `MAE=11.774165`
- reference metrics: `top_3_hit_rate=0.95`, `ndcg_at_10=0.909302`, `spearman_mean=0.153604`, `MAE=23.858757`
- D37 production SHA1 before rollout: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`

The full known runtime feature space is up to `177` features if `29` SERP-relative features are included. D37 intentionally treats `serp_relative` as a follow-up unless the implementation adds an explicit second post-competitor scoring pass, because those features are produced only after competitor aggregation.

## Current D38 Evidence: Controlled Publish CatBoost V3

GitHub issue `#57` is implemented locally for `D38: Controlled publish CatBoost v3 candidate`. Local source of truth: `plans/d38-controlled-publish-catboost-v3.md`.

D38 published the D37 `pointwise_catboost` candidate to the production runtime alias after validating the D37 shadow report and preserving the previous v1 artifact for rollback.

D38 evidence:

- production artifact: `backend/artifacts/page_quality_model.pkl`
- production SHA1 before publish: `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`
- production SHA1 after publish: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- dataset: `dataset-v3-d37`
- artifact version: `dataset-v3-d37-20260501200434`
- schema: `v3`
- model type: `CatBoostRegressor`
- feature count: `148`
- rollback artifact: `backend/artifacts/versions/page_quality_model--ru_commercial_dataset-20260421-primary-20260421174901.pkl`
- report: `backend/artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.json`
- smoke summary: `output/runtime-smoke/d38-smoke-summary.json`
- smoke audit: `690504f2-ca2f-42a6-a012-e622438437a7`, status `completed`, `2/2` competitors analyzed, `11` recommendations, missing queues `[]`

## Current D39 Evidence: Model Status In Interface

GitHub issue `#58` is implemented locally for `D39: Model status in interface`. Local source of truth: `plans/d39-model-status-interface.md`.

D39 exposes the active production model in product-visible surfaces without changing scoring behavior.

D39 evidence:

- backend endpoint: `GET /health/model`
- endpoint status for current artifact: `active`
- current runtime after D58: `CatBoostRegressor`, schema `v3`, dataset `dataset-v5`, artifact `dataset-v5-20260502151507`
- rollback availability: `true`
- UI surfaces: compact stack card, full `Стек` page, score breakdown, audit report, Markdown export, HTML export
- verification: `backend/tests/test_health_api.py` -> `24 passed`; `npm --prefix frontend run test` -> `45 passed`

## Current D40-D44 Evidence: Post-Publish Model Operations

GitHub issues `#59-#63` were created on `2026-05-02`. Local source of truth: `plans/d40-d44-post-publish-model-operations.md`.

The D40-D44 wave keeps the D38 CatBoost v3 production artifact in place and focuses on operating, validating and explaining it after publish.

Completed D40-D44 scope:

- `D40` / GitHub `#59`: post-publish model monitoring dashboard over real audit/model usage.
- `D41` / GitHub `#60`: golden query replay guardrails after publish.
- `D42` / GitHub `#61`: score confidence and data-quality warnings in audit UX.
- `D43` / GitHub `#62`: model registry and rollback evidence UI.
- `D44` / GitHub `#63`: non-production second-pass competitor-aware score experiment using `serp_relative` features.

D40 evidence:

- backend endpoint: `GET /health/model/monitoring`
- backend helper: `backend/app/model_monitoring.py`
- aggregation source: `Audit.score_breakdown.model_info`
- UI surface: full `Стек` runtime page, section `Мониторинг ML-модели`
- coverage: model artifact/schema/dataset usage, status/warning/failure counts, score distribution, competitor coverage and legacy/unknown audit counts

D41 evidence:

- command: `cd backend && .venv\Scripts\python.exe -m app.ml.golden_replay --output-dir artifacts/ranking-benchmarks/dataset-v3-d41`
- report: `backend/artifacts/ranking-benchmarks/dataset-v3-d41/golden-replay-report.json`
- markdown: `backend/artifacts/ranking-benchmarks/dataset-v3-d41/golden-replay-report.md`
- decision: `passed`
- guardrails: `3/3` replay items passed, `21 pass / 0 warn / 0 fail`
- default evidence: one D38 smoke artifact plus explicit synthetic stored fixtures for the remaining golden items; `/health/model.checked_at` is normalized to the fixed report timestamp for reproducible output
- invariant: no publish, no rollback, no mutation of `backend/artifacts/page_quality_model.pkl`

D42 evidence:

- frontend helper: `frontend/src/lib/auditConfidence.ts`
- classification: `high` / `medium` / `low` / `unknown` score confidence from fetch status/method, feature schema, heavy analysis, competitor coverage, recommendations, `score_breakdown.model_info`, warnings and failure context
- UI surfaces: audit overview compact badge and reason list; audit report tab; Markdown export; printable HTML export
- invariant: UX/data-quality layer only; no numeric score formula change, no backend scoring change, no model artifact mutation
- verification: `npm --prefix frontend run test -- src/lib/auditConfidence.test.ts src/lib/auditReport.test.ts src/lib/ui.test.tsx` -> `23 passed`; `npm --prefix frontend run build` -> passed

D43 evidence:

- backend endpoint: `GET /health/model/registry`
- backend helper: `backend/app/model_registry.py`
- discovery source: active alias `backend/artifacts/page_quality_model.pkl`, versioned artifacts in `backend/artifacts/versions/`, public metadata sidecars, controlled publish reports and golden replay reports
- UI surface: full `Стек` runtime page, section `Model registry и rollback evidence`
- coverage: current CatBoost v3 record, previous v1 RandomForest rollback record, SHA1 values, publish report paths, smoke evidence paths and rollback dry-run checklist
- invariant: read-only evidence/checklist layer only; no rollback execution, no publish action, no model artifact mutation

D44 evidence:

- backend helpers: `backend/app/ml/second_pass.py` and `backend/app/ml/second_pass_experiment.py`
- report: `backend/artifacts/ranking-benchmarks/dataset-v3-d44/second-pass-experiment-report.json`
- markdown: `backend/artifacts/ranking-benchmarks/dataset-v3-d44/second-pass-experiment-report.md`
- candidate artifact: `backend/artifacts/page_quality_model.dataset-v3-d44-second-pass-experiment.pkl` plus `.metadata.json`
- model schema: `v3-serp-relative-experiment`, `177` features (`148` v3 pre-competitor + `29` SERP-relative)
- decision: `do_not_continue_without_more_evidence`
- invariant: non-production experiment only; no runtime scoring change, no publish, no rollback, no mutation of `backend/artifacts/page_quality_model.pkl`

D40-D44 is complete locally. Do not start a second-pass publish path from D44 evidence without a new task.

## Current D45-D61 Evidence: Competitiveness-Oriented Product Goal

GitHub issues `#64-#80` cover the shift from "model score as abstract page quality" to "competitive SEO audit for a concrete query."

Completed scope:

- `D45-D49`: built SEO-weighted deterministic rubric labels and `dataset-v4`, trained candidates, and recorded no-publish because the then-current release gates rejected them.
- `D50-D54`: built `dataset-v5` with query-level preference labels and shortcut feature control, trained pointwise/ranking-aware/hybrid candidates, and recorded historical no-publish under the old top-3 blocking policy.
- `D55` / GitHub `#74`: product-aligned release policy. `top_3_hit_rate` is now SERP-alignment diagnostics; blocking model metrics are `MAE`, `Spearman`, `NDCG@10`, feature dominance, score response and recommendation consistency.
- `D56` / GitHub `#75`: runtime `competitiveness-score-v1`. The backend preserves `primary_page_score`, then sets final `competitiveness_score` after competitor aggregation when enough competitors are processed.
- `D57` / GitHub `#76`: recommendation priority model `competitor-gap-priority-v1`, using competitor gap, SEO/search importance and controllability.
- `D58` / GitHub `#77`: controlled publish of `pointwise_catboost_v5` under the competitiveness scorecard.
- `D59` / GitHub `#78`: product UI cleanup, removing user-facing ML/debug clutter.
- `D60` / GitHub `#79`: research artifact archiving and clearer runtime/evidence asset boundaries.
- `D61` / GitHub `#80`: documentation rewrite around the clarified competitiveness goal.

D58 current runtime evidence:

- production artifact: `backend/artifacts/page_quality_model.pkl`
- SHA1: `5374ca30f48f70d8629e7d84ec3df0524ef35b52`
- dataset: `dataset-v5`
- artifact version: `dataset-v5-20260502151507`
- model: `CatBoostRegressor`, schema `v3`, `148` features
- metrics: `MAE=1.22855`, `Spearman=0.957788`, `NDCG@10=0.998374`, `top_3_hit_rate=0.6` as non-blocking SERP diagnostics
- rollback artifact: `backend/artifacts/versions/page_quality_model--dataset-v3-d37-20260501200434.pkl`

The practical next tasks should now be product polish, documentation, evidence cleanup or carefully scoped new SEO capabilities. Do not re-run old D45-D54 no-publish logic as if it were still the current release policy.

### D21 / #40: Audit Report And Export Dashboard

Статус: выполнено.

Цель — дать пользователю единый отчёт по аудиту, который можно открыть, показать и экспортировать.

Реализованный состав:

- отдельная вкладка `Отчёт` для выбранного аудита;
- score, статус, поисковый запрос, target URL, конкуренты и ключевые проблемы;
- grouped recommendations и score explanation в компактной форме;
- существующие distributed-runtime evidence из `events/diagnostics`;
- экспорт в printable HTML/PDF-like view, downloadable HTML и downloadable Markdown artifact.

Приёмка выполнена: завершённый аудит открывается как цельный отчёт, а экспорт/печать работают без devtools и без повторного анализа страницы.

### D22 / #41: Audit Execution Timeline UI

Статус: выполнено.

Цель — визуально показать жизненный цикл распределённого аудита.

Реализованный состав:

- вкладка `Таймлайн` в audit workspace;
- timeline стадий `pipeline`, `fetch`, `heavy_analysis`, `features`, `scoring`, `competitors`, `competitor_page`, `competitor_analysis`, `competitor_aggregation`, `recommendations`, `finalize`;
- raw event stream из `GET /audits/{audit_id}/events`;
- длительности, ошибки, warnings, queues, fan-out summary и critical-path hints из existing events/diagnostics API;
- понятное состояние для completed, completed_with_warnings, failed и старых audits без event log.

Приёмка выполнена: пользователь может открыть аудит и понять, какие стадии прошли, где была задержка или ошибка, какие очереди/workers участвовали, где был fan-out и как это связано с распределённой архитектурой.

### D23 / #42: Состояние рабочего стека и здоровье очередей

Статус: выполнено.

Цель — сделать состояние локального распределённого стека понятным до запуска аудита и во время работы.

Реализованный состав:

- компактная панель `Готовность рабочего стека` на экране нового аудита;
- глобальный экран `Стек` для просмотра состояния рабочего стека во время работы;
- frontend использует `GET /health/live`, `GET /health/ready` и `GET /health/metrics`;
- отображение API, базы данных, брокера Redis, SearXNG, профилей воркеров и очередей;
- диагностика отсутствующих воркеров, нагрузки очередей, накопления задач, очередей без воркеров, готовности и алертов детектора выполнения;
- человекочитаемые подсказки для ошибок контроля допуска и очередей без активных воркеров.

Приёмка выполнена: пользователь видит, готов ли рабочий стек к новым аудитам, и понимает, что именно нужно восстановить при проблеме.

### D24 / #43: Audit History Management

Статус: выполнено.

Цель — превратить историю аудитов из пассивного списка в рабочую панель.

Реализованный состав:

- быстрые действия `Повторить аудит`, `Открыть последний успешный`, `Скрыть локально` и `Восстановить`;
- фильтры по статусу, домену, запросу и фокусу (`Все записи`, `Успешные`, `Проблемные`, `Зависшие/устаревшие`, `Скрытые локально`);
- метрики истории: всего, видимые, успешные, проблемные, скрытые;
- локальное скрытие через browser storage без удаления backend-данных;
- повторный запуск через существующий `POST /audits` с исходными `query`, `target_url`, `top_n`.

Приёмка выполнена: пользователь быстро находит нужный аудит, повторяет запуск и очищает локальную историю без риска случайно сломать данные.

### D25 / #44: Recommendation Action Tracking

Статус: выполнено.

Цель — сделать рекомендации планом работ, а не только текстом.

Реализованный состав:

- состояния для рекомендаций: `Не начато`, `В работе`, `Исправлено`, `Игнорируется`;
- сохранение состояния локально per-audit через browser storage без изменения backend recommendation payload;
- summary закрытых действий, процента прогресса и статусов в работе;
- group-level progress `Закрыто x/y` внутри grouped recommendations;
- controls на карточках рекомендаций для смены статуса действия.

Приёмка выполнена: пользователь может отмечать прогресс по рекомендациям, а страница рекомендаций показывает, сколько действий уже закрыто.

### D26 / #45: Interface Copy And Terminology Polish

Статус: выполнено.

Цель — сделать язык интерфейса стабильным, понятным и пригодным для дипломной демонстрации.

Реализованный состав:

- основные видимые строки UI переведены на русские primary labels без лишнего смешения `score`, `gap`, `semantic` и внутренних кодов;
- добавлен frontend terminology layer для backend-originated labels в рекомендациях, отчёте и объяснении оценки;
- отчёт, HTML/Markdown export, рекомендации, timeline/runtime screens, история и production smoke-check используют обновлённые фрагменты;
- backend recommendation display strings отполированы как пользовательская copy без изменения schema version, group keys или recommendation codes.

Приёмка выполнена: основные экраны понятны человеку без знания внутренних API-кодов, а техническая детализация остаётся доступной вторым уровнем там, где она полезна.

## Отложенные направления

Эти направления полезны, но не являются ближайшим фокусом:

- ML evidence hardening: expert labels для `dataset-v2`, ranking benchmark, обновление `backend/docs/ml_methodology_appendix.md`;
- SEO depth extensions: schema.org/JSON-LD recommendations, optional PageSpeed/Lighthouse integration, site-wide crawl как отдельная крупная волна;
- multi-project/domain management и сравнение аудитов во времени.

Их стоит брать только отдельной новой задачей, чтобы не распылять дипломную демонстрацию.

## Как пользоваться roadmap

Перед началом новой задачи агент или разработчик должен:

1. Прочитать `AGENTS.md` и `README.md`.
2. Проверить `git status`.
3. Если задача не задана явно, проверить актуальные open GitHub issues; не считать закрытый `D26` новым фокусом.
4. Не откатывать `D13-D26` без прямой причины.
5. Если нужен GitHub, использовать локальный credential helper или запросить токен вручную, не печатая секреты в чат, logs или файлы.

Канонический статус сейчас: `D1-D26` завершены; следующий практический backlog должен быть выбран явно пользователем или через новый open GitHub issue.

## Current Backlog Override

This section is intentionally written in plain ASCII/English so future agents can read it even if local terminal encoding renders Russian text incorrectly.

Canonical current status: `D1-D75` are complete locally through raw `dataset-v7-final` collection.

The final ML evidence and model productization waves kept the old production model while D30/D35 recommended `keep_reference`; D37 then built a wider `v3` candidate and D38 published it. D40-D44 added post-publish operations and second-pass evidence. D45-D54 explored SEO-weighted and ranking-aware candidates. D55 corrected the release policy around the clarified product goal, D56 added the `competitiveness_score` layer, D57 added competitor-gap recommendation priority, and D58 published the current v5 pointwise CatBoost artifact. D62-D68 then made query relevance the strict final score gate, and D69 made the `dataset-v7-final` collection path safer with domain caps and snapshot-based hard negatives. D70 tightens the relevance contract again: confident full mismatch is `0-5`, while ambiguous low relevance continues the audit as `probable_mismatch` up to `25`. D71 now wires confident full mismatch into backend preflight so heavy analysis and competitor fan-out are skipped only when the mismatch is clear enough; D72 exposes that decision as typed API/timeline runtime contract; D73-D74 add the user-facing state and regression coverage. D75 completed controlled live raw collection for `dataset-v7-final`: `500/500` seed queries have successful rows, with `3876` rows across `2253` domains. The dataset is still not training-ready until hard negatives, deterministic labels and split validation are produced. Production artifact `backend/artifacts/page_quality_model.pkl` still points to CatBoost v5 (`dataset-v5`, schema `v3`, SHA1 `5374ca30f48f70d8629e7d84ec3df0524ef35b52`) until `dataset-v7-final` is labeled and passed through controlled publish. `top_3_hit_rate` is retained as SERP-alignment diagnostics, not as the main release truth.

Local source of truth:

- `AGENTS.md`
- `README.md`
- `backend/README.md`
- `plans/d27-d31-final-model-training.md`
- `plans/d32-d36-model-productization.md`
- `plans/d37-unified-v3-hybrid-ensemble-top3-guardrail.md`
- `plans/d38-controlled-publish-catboost-v3.md`
- `plans/d39-model-status-interface.md`
- `plans/d40-d44-post-publish-model-operations.md`
- `plans/d45-d49-seo-weighted-score-retraining.md`
- `plans/d50-d54-v5-ranking-aware-model.md`
- `plans/d55-d61-product-aligned-competitiveness.md`
- `plans/d62-d68-final-query-competitiveness.md`
- `plans/d69-dataset-v7-collection-readiness.md`
- `plans/d70-conservative-query-relevance-contract.md`
- `plans/d72-query-relevance-early-stop-runtime-contract.md`
- `plans/d71-d74-query-relevance-preflight-ui-regression.md`

Completed tasks:

- `D27` / GitHub `#46`: completed/pushed; `dataset-v2` was built from seed catalog in controlled batches.
- `D28` / GitHub `#47`: completed/pushed; dataset quality gates, manifest, artifact coverage and group split were validated.
- `D29` / GitHub `#48`: completed; candidate page-quality model was trained from `dataset-v2` without replacing the production artifact.
- `D30` / GitHub `#49`: completed; ranking benchmark compared the candidate against the current artifact and recommends `keep_reference`.
- `D31` / GitHub `#50`: completed locally; final no-publish/keep-reference decision was made and product behavior was verified with smoke audits.
- D31 clean rerun evidence: `scripts/d31-runtime-smoke.mjs` regenerated `output/runtime-smoke/d31-smoke-summary.json` from a clean stack; audit `45ca43ab-fb3a-4045-a28a-5f012cee4ffb` completed with `4` workers, missing queues `[]`, `2/2` competitors analyzed, `13` recommendations, `competitor_page` fan-out `2/2`, and runtime model `ru_commercial_dataset-20260421-primary` / schema `v1`.

Completed recent tasks:

- `D32` / GitHub `#51`: completed locally; `197` expert-rubric labels added for `dataset-v2` model productization.
- `D33` / GitHub `#52`: completed locally; refreshed `dataset-v2` manifest and group split after expert labels.
- `D34` / GitHub `#53`: completed locally; RF, CatBoost and CatBoostRanker candidate artifacts trained without replacing production.
- `D35` / GitHub `#54`: completed locally; shadow benchmark and explainability guardrails recommend `keep_reference`.
- `D36` / GitHub `#55`: completed locally; controlled keep-reference/no-publish decision, rollback evidence and product smoke verification.

Completed model rollout/interface tasks:

- `D37` / GitHub `#56`: implemented locally; added unified `v3` feature schema, built `148`-feature pre-competitor dataset evidence, trained non-production candidates, ran shadow guardrails, and selected `pointwise_catboost` as publish-recommended.
- `D38` / GitHub `#57`: implemented locally; controlled publish of `pointwise_catboost` CatBoost v3 to `backend/artifacts/page_quality_model.pkl`, rollback artifact preserved, product smoke passed.
- `D39` / GitHub `#58`: implemented locally; active model status endpoint and UI visibility in stack, score explanation and audit report/export.
- `D40` / GitHub `#59`: implemented locally; post-publish model monitoring dashboard with `/health/model/monitoring` and `Стек` UI section.
- `D41` / GitHub `#60`: implemented locally; deterministic golden query replay guardrails with evidence in `backend/artifacts/ranking-benchmarks/dataset-v3-d41/`.
- `D42` / GitHub `#61`: implemented locally; score confidence/data-quality UX in audit overview, report UI, Markdown export and printable HTML export.
- `D43` / GitHub `#62`: implemented locally; read-only model registry and rollback evidence UI with `/health/model/registry` and `Стек` UI section.
- `D44` / GitHub `#63`: implemented locally; non-production second-pass competitor-aware score experiment with SERP-relative features and evidence in `backend/artifacts/ranking-benchmarks/dataset-v3-d44/`.
- `D45-D49` / GitHub `#64-#68`: completed; SEO-weighted labels, dataset-v4, candidates, shadow benchmark and no-publish evidence.
- `D50-D54` / GitHub `#69-#73`: completed; dataset-v5 preference labels, shortcut feature policy, candidates, historical shadow benchmark and no-publish evidence.
- `D55` / GitHub `#74`: completed/pushed; product-aligned competitiveness release policy.
- `D56` / GitHub `#75`: completed/pushed; runtime competitiveness score layer.
- `D57` / GitHub `#76`: completed/pushed; competitor-gap recommendation priority model.
- `D58` / GitHub `#77`: completed/pushed; controlled publish of `pointwise_catboost_v5`.
- `D59` / GitHub `#78`: completed/pushed; user-facing ML/debug clutter removed.
- `D60` / GitHub `#79`: completed/pushed; research artifacts archived and runtime/evidence asset boundaries clarified.
- `D61` / GitHub `#80`: documentation rewrite around the competitiveness goal.
- `D62-D68`: implemented locally; final query relevance multiplier, `dataset-v7-final` seed catalog, final release pipeline and grouped score explanation UI. Controlled publish is blocked until real top-10 collection and deterministic labels are available.
- `D69`: implemented locally; `dataset_builder` domain cap before parallel fetch, `final_hard_negatives` snapshot-based hard-negative materialization, and final pipeline readiness checks for `dataset.with-hard-negatives.csv`.
- `D70`: implemented locally; conservative early-stop decision contract, full mismatch `0-5`, probable mismatch up to `25`, and v7 final score contract bumped to `query-competitiveness-final-v2`.
- `D71`: implemented locally; backend preflight stops only confident full query mismatch before heavy analysis and competitors, completing the audit with `query_relevance_early_stop`.
- `D75`: completed locally as raw collection; `dataset-v7-final` has `500/500` seed queries with successful rows, `3876` rows, `367` failures, `2253` domains, `50` categories and `5` cities. No training or publish yet.
- `D72`: implemented locally; audit status, list, results and timeline diagnostics expose typed `early_stop` summary, and timeline events show skipped-stage evidence.
- `D73`: implemented locally; overview, competitors, history and report/export show the early-stop state as clear product copy without raw ML fields.
- `D74`: implemented locally; regression tests cover unrelated good pages, near-topic false positives, informational/commercial modifier behavior, rare low-signal pages and insufficient extraction.

Active post-publish operations tasks: materialize hard negatives from `dataset-v7-final` snapshots, apply deterministic expert labels, validate split/leakage/domain cap, then train/decide before any controlled publish.

Next agent instruction: select a new task explicitly before changing model/runtime behavior. Do not repeat old rollouts, publish the D44 candidate, add demo mode, or rewrite backend orchestration unless the user explicitly requests that scope.
