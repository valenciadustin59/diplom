# Roadmap текущего этапа Site Audit

Этот документ нужен как читаемый стратегический ориентир для разработчиков и Codex-агентов. Операционный handoff, ограничения и актуальные ссылки на GitHub issues всегда начинаются с `AGENTS.md`; этот roadmap объясняет, куда развивать проект дальше и какие завершённые волны не нужно повторять.

Проект находится в репозитории `E:\codexPROJ\diplom`. Тема диплома: web-приложение машинного обучения на основе распределённых вычислений. Поэтому roadmap оценивается не только по SEO-функциям, но и по тому, насколько хорошо проект демонстрирует ML workflow, distributed runtime и понятный web-интерфейс.

## Текущий статус

Базовый пользовательский сценарий уже реализован: пользователь вводит поисковый запрос и URL, система собирает конкурентные страницы из SERP, анализирует target и competitors, считает ML score, сравнивает страницу с конкурентами и формирует рекомендации.

Завершённые волны:

- `D1-D12` — distributed runtime foundation: stage-based Celery pipeline, per-stage queues, distributed fan-out, retry-safe orchestration, health/live, health/ready, health/metrics, event log, timeline diagnostics, queue pressure, admission control, worker topology profiles и benchmark/reporting workflow.
- `D13-D26` — SEO/ML/product/frontend evidence wave: snapshot extraction, feature schema v2, technical SEO features, commercial/trust features, intent-aware and SERP-relative features, dataset-v2 workflow, model schema v2, artifact-driven training/publish flow, grouped recommendations API/UI, isolated `audits.heavy_analysis` queue, audit report/export dashboard, audit execution timeline UI, панель состояния рабочего стека/очередей, audit history management, recommendation action tracking и interface terminology polish.

После `D26` проект уже соответствует дипломной теме, имеет отдельный report/export view, dedicated timeline UI, панель состояния рабочего стека, управляемую историю аудитов, план действий по рекомендациям и стабильную русскую терминологию интерфейса для демонстрации распределённого исполнения. Этап `D27-D31` завершил финальное ML-evidence доведение: `dataset-v2` собран, candidate обучен, benchmark рекомендовал `keep_reference`, а D31 подтвердил продукт clean smoke-аудитом. Следующий активный этап выбран как безопасное внедрение модели в продукт: `D32-D36`.

Важно: GitHub Issues приватного репозитория могут быть недоступны другим Codex-диалогам без авторизации и возвращать `404 Not Found`. Поэтому активный backlog `D32-D36` продублирован локально в `AGENTS.md`, `README.md`, `backend/README.md` и `plans/d32-d36-model-productization.md`.

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
- model: `CatBoostRegressor`, schema `v3`, dataset `dataset-v3-d37`, artifact `dataset-v3-d37-20260501200434`
- rollback availability: `true`
- UI surfaces: compact stack card, full `Стек` page, score breakdown, audit report, Markdown export, HTML export
- verification: `backend/tests/test_health_api.py` -> `24 passed`; `npm --prefix frontend run test` -> `45 passed`

Next practical step: post-publish monitoring for active model quality/drift, or a separately scoped second-pass competitor-aware score using `serp_relative` features.

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

## Current Active Backlog Override

This section is intentionally written in plain ASCII/English so future agents can read it even if local terminal encoding renders Russian text incorrectly.

Canonical current status: `D1-D39` are complete locally. The final ML evidence and model productization waves kept the old production model while D30/D35 recommended `keep_reference`; D37 then built a wider `v3` candidate and the shadow benchmark recommended `publish_candidate` for `pointwise_catboost`; D38 completed the controlled rollout; D39 made the active model visible in API/UI/report surfaces. Production artifact `backend/artifacts/page_quality_model.pkl` now points to CatBoost v3 (`dataset-v3-d37`, schema `v3`, SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`). GitHub issues `#46-#50` were verified and closed as completed on `2026-05-01`; issues `#51-#55` were also completed locally and closed after verification; `#56`, `#57` and `#58` are the D37-D39 model rollout/interface evidence.

Local source of truth:

- `AGENTS.md`
- `README.md`
- `backend/README.md`
- `plans/d27-d31-final-model-training.md`
- `plans/d32-d36-model-productization.md`
- `plans/d37-unified-v3-hybrid-ensemble-top3-guardrail.md`
- `plans/d38-controlled-publish-catboost-v3.md`
- `plans/d39-model-status-interface.md`

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

Next agent instruction: `D32-D39` is complete locally. Do not repeat the CatBoost v3 rollout unless the user explicitly asks for rollback or republish. The next useful product work is post-publish monitoring, or a separately planned second-pass competitor-aware score that can use `serp_relative` features. Do not add demo mode or rewrite backend orchestration.
