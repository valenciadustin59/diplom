# AGENTS

Этот файл описывает текущее состояние репозитория и служит стартовой инструкцией для любого агента или разработчика, который начинает работу в проекте.

Текущий корень репозитория:

- `E:\codexPROJ\diplom`

## Обязательные ограничения

- Работать только внутри этого репозитория.
- Не создавать временные директории, симлинки, клоны и рабочие файлы вне `E:\codexPROJ\diplom`.
- Если нужен временный вспомогательный скрипт, создавать его только внутри репозитория и удалять после использования.
- Не закрывать GitHub issue до тех пор, пока реализация не проверена, не закоммичена и не запушена.
- Для backlog-задач придерживаться порядка: реализация -> проверки -> commit -> push.

## Быстрый Handoff Для Нового Чата

Если новый агент только открыл репозиторий, ему нужно сразу понимать следующее.

- Проект: distributed ML web-приложение для SEO-аудита посадочных страниц по поисковому запросу.
- Практический сценарий: пользователь вводит query + URL, система сама собирает конкурентов из SERP, анализирует target/competitors, считает score, показывает competitor-aware сравнение и выдаёт рекомендации.
- Дипломный акцент: важны одновременно и ML, и распределённые вычисления. Поэтому в проекте уже есть stage-based Celery runtime, queue topology, diagnostics, benchmark workflow, versioned dataset/model pipeline и explainable recommendation layer.
- Канонический корень репозитория: `E:\codexPROJ\diplom`.
- Сразу смотреть сюда:
  - `AGENTS.md` — этот файл;
  - `README.md` — обзор продукта и локальный запуск;
  - `backend/app/tasks.py` — orchestration audit pipeline;
  - `backend/app/recommendations.py` — recommendation engine и explainability payload;
  - `backend/app/schemas/audit.py` — API contracts для audit/status/results/recommendations;
  - `frontend/src/components/AuditWorkspace.tsx` — основная рабочая область аудита;
  - `frontend/src/pages/RecommendationsPage.tsx` и `frontend/src/components/RecommendationList.tsx` — recommendation UI;
  - `frontend/src/types.ts` — frontend contracts;
  - `backend/tests/` и `frontend/src/lib/ui.test.tsx` — регрессии.

## Кратко о проекте

Проект автоматизирует SEO-аудит посадочных страниц по поисковому запросу.

Пользователь задаёт:

- поисковый запрос;
- URL своей страницы.

Система после этого:

- находит конкурентов в выдаче;
- анализирует целевую страницу и конкурентов;
- извлекает признаки;
- вычисляет ML score;
- сравнивает результат с конкурентами;
- формирует рекомендации с приоритетами.

Проект должен убедительно соответствовать теме диплома: web-приложение машинного обучения на основе распределённых вычислений.

## Структура репозитория

- `backend/` — FastAPI backend, SQLite, Celery runtime, ML scoring, training workflow.
- `frontend/` — React + TypeScript интерфейс.
- `scripts/` — dev scripts, benchmark runner, training utilities.
- `docs/roadmap/` — стратегический roadmap; operational source of truth остаётся `AGENTS.md`.
- `plans/` и `PLANS.md` — вспомогательные planning-документы.
- `docker-compose.searxng.yml` — локальный стек `SearxNG + Redis`.

## Статус backlog

Старые product issues `#1-#25` больше не считаются активным backlog source of truth. Они остаются только как архив истории проекта.

Завершённые волны текущего дипломного проекта:

- `D1-D12` — distributed runtime foundation: stage-based pipeline, queue topology, fan-out, health/metrics, event log, diagnostics, admission control и benchmark evidence.
- `D13-D26` — SEO/ML/product/frontend evidence wave: snapshot extraction, feature schema v2, technical SEO, commercial/trust, intent-aware и SERP-relative features, dataset/model workflow, grouped recommendations UI, isolated heavy-analysis queue, audit report/export dashboard, audit execution timeline UI, панель состояния рабочего стека/очередей, audit history management, recommendation action tracking и interface terminology polish.

Завершённая frontend/product wave: `D21-D26` — frontend/product layer без изменения ядра анализа:

- `D21` / GitHub `#40` — completed: audit report and export dashboard;
- `D22` / GitHub `#41` — completed: audit execution timeline UI;
- `D23` / GitHub `#42` — completed: панель состояния рабочего стека и здоровья очередей;
- `D24` / GitHub `#43` — completed: audit history management;
- `D25` / GitHub `#44` — completed: recommendation action tracking;
- `D26` / GitHub `#45` — completed: interface copy and terminology polish.

Практический фокус после `D26`: не переписывать backend orchestration и не добавлять demo mode без явного запроса. Предыдущая волна `D21-D26` закрыта.

Активный backlog после `D26` теперь зафиксирован локально, потому что GitHub Issues приватного репозитория могут быть недоступны другим Codex-диалогам без авторизации и возвращать `404 Not Found`. Если GitHub недоступен, считать локальные документы источником правды:

- `plans/d27-d31-final-model-training.md` — подробный ExecPlan для финального ML-этапа;
- `D27` / GitHub `#46` — completed and pushed; GitHub issue closure unverified: `dataset-v2` собран из seed catalog батчами `0-49` и `50-99`;
- `D28` / GitHub `#47` — completed: `manifest.json` и `group_by_query` `split.json` сформированы, `ready_for_training=true`;
- `D29` / GitHub `#48` — open: обучить candidate page-quality model на `dataset-v2`;
- `D30` / GitHub `#49` — open: прогнать ranking benchmark и сравнить candidate с текущим artifact;
- `D31` / GitHub `#50` — open: опубликовать финальную model artifact и проверить продукт smoke-аудитами.

### D1-D12 Summary

Статус `D1-D12`: завершено.

- `D1` — stage-based decomposition audit pipeline
- `D2` — per-stage Celery queues and routing
- `D3` — distributed fan-out по competitor pages
- `D4` — retry-safe / version-aware orchestration
- `D5` — `health/live` и `health/ready`
- `D6` — `health/metrics` и диагностика рабочего стека
- `D7` — persistent audit event log
- `D8` — audit timeline diagnostics API
- `D9` — снимки нагрузки очередей и детектор очередей с накоплением/без воркеров
- `D10` — admission control и scheduling guards
- `D11` — worker topology profiles и queue-affinity validation
- `D12` — benchmark/reporting workflow для distributed runtime evidence

Если в старых документах встречаются упоминания о незавершённом `D12`, считать их историческими и неактуальными.

## Архитектурные ориентиры

### Backend

- `FastAPI`
- `SQLAlchemy 2`
- `Pydantic v2`
- `SQLite`

### Distributed runtime

- `Celery`
- `Redis`
- stage-based audit pipeline
- queue-affinity worker topology

### ML

- `scikit-learn`
- `sentence-transformers`
- `CatBoost`

### Frontend

- `React`
- `TypeScript`
- `Vite`

## Каноническая worker topology

Начиная с `D20`, проект использует четыре профиля workers:

- `pipeline`
- `network`
- `heavy_analysis`
- `cpu_ml`

Соответствие очередей задаётся в:

- `backend/app/worker_topology_profiles.json`

Эта topology валидируется через проверку готовности и runtime metrics. Старый single all-queues worker допустим только как debugging fallback.

## Важные runtime contracts

### Health endpoints

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /health/metrics`

### Audit endpoints

- `GET /audits`
- `POST /audits`
- `GET /audits/{audit_id}`
- `GET /audits/{audit_id}/results`
- `GET /audits/{audit_id}/recommendations`
- `GET /audits/{audit_id}/events`
- `GET /audits/{audit_id}/events/diagnostics`

### Admission semantics

Начиная с `D10`, `POST /audits` может вернуть `503`, если пропускная способность рабочего стека деградировала. Это нормальная часть поведения системы, а не баг по умолчанию.

## D12 benchmark workflow

Benchmark runner находится в:

- `scripts/run_distributed_benchmark.py`

Пример workload-файла:

- `scripts/distributed_benchmark.workload.example.json`

Артефакты benchmark запуска сохраняются в:

- `backend/artifacts/benchmarks/`

Benchmark использует production API surface:

- `POST /audits`
- `GET /audits/{audit_id}`
- `GET /audits/{audit_id}/events/diagnostics`
- `GET /health/metrics`

## Основные команды

### Полный локальный стек

```powershell
cd E:\codexPROJ\diplom
npm install
npm --prefix frontend install
npm run dev:full
```

Короткий эквивалент полного запуска:

```powershell
cd E:\codexPROJ\diplom
npm start
```

### Frontend site smoke-check

```powershell
cd E:\codexPROJ\diplom
npm run site:check
```

Команда собирает frontend и проверяет, что `frontend/dist` содержит production `index.html`, подключённые JS/CSS assets и ключевые тексты интерфейса.

### Backend tests

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest
```

Если локальный dev stack/Redis содержит очереди без воркеров, тесты admission/dispatch guards могут прочитать live-состояние очередей и упасть со stale `queue_capacity_guard`. Для детерминированной backend-регрессии без привязки к текущему Redis используйте изолированный unavailable broker URL:

```powershell
cd E:/codexPROJ/diplom/backend
$env:CELERY_BROKER_URL = "redis://localhost:1/0"
$env:CELERY_RESULT_BACKEND = "redis://localhost:1/0"
.venv/Scripts/python.exe -m pytest
Remove-Item Env:CELERY_BROKER_URL, Env:CELERY_RESULT_BACKEND
```

### Script tests

```powershell
cd E:\codexPROJ\diplom
npm run test:scripts
```

### Frontend build

```powershell
cd E:\codexPROJ\diplom
npm run build
```

## Документы, на которые стоит смотреть первыми

- `README.md` — обзор проекта и локальный запуск.
- `backend/README.md` — backend, API, workers, benchmark.
- `docs/roadmap/product-development-roadmap.md` — стратегический roadmap после `D26`.
- `backend/docs/ml_methodology_appendix.md` — ML methodology appendix.

## Git и публикация

- Коммитить только после проверок.
- Не заявлять о закрытии issue, если push не выполнен.
- Если используется `Closes #<n>`, issue должен закрываться через push в `main`, а не вручную без кода.


## D13-D26 Status

Completed product/ML/SEO/frontend evidence wave: `D13-D26`.

- `D13` - completed: versioned extraction pipeline, `feature schema v2`, persistent `target_snapshot`, DOM-based extraction, and API snapshot summary.
- `D14` - completed: пакет технических SEO-сигналов поверх `target_snapshot`, включая canonical/redirect/indexability/url-hygiene признаки, технические рекомендации и технические факторы в score explanation без изменения текущего `FEATURE_COLUMNS`.
- `D15` - completed: пакет commercial/trust signals для коммерческих landing pages, включая contact/business identity признаки, CTA/messenger detection, агрегированные commercial/trust scores и recommendation layer, доступный также в dataset builder.
- `D16` - completed: query intent detection, intent-alignment features for target and competitors, persisted `query_intent` in `Audit`, SERP-relative gaps/percentiles/z-scores for key signal groups, and relative/intent-aware explanation and recommendation rules.
- `D17` - completed: versioned dataset workflow, frozen `baseline-v1`, prepared `dataset-v2` seed bundle, hybrid labeling contract (`weak_target_score`, `expert_target_score`, `target_score`, `label_source`), raw extraction artifacts for dataset rows, enriched dataset manifest and persisted `group_by_query` split.
- `D18` - completed: model schema v2, artifact-driven runtime/training/publish flow, ranking benchmark workflow, ranking candidate publish/report path.
- `D19` - completed: grouped recommendations API/UI, factor groups (`Technical SEO`, `Commercial and Trust`, `Semantic and Intent`, `Competitor Gap`), competitor-relative deviations, richer explainability payload, legacy recommendation normalization for old audits.
- `D20` - completed: dedicated `audits.heavy_analysis` queue/profile, target heavy-analysis stage, split competitor network fetch vs heavy semantic/ML analysis, heavy queue admission guard, metrics pressure visibility and benchmark topology profile summary.
- `D21` - completed: audit report tab, client-side export dashboard, printable HTML/PDF-like view, downloadable Markdown/HTML report, compact SEO/ML/recommendation/competitor/runtime evidence summary using existing audit results and timeline diagnostics APIs.
- `D22` - completed: audit execution timeline tab, raw audit event stream consumption, stage lifecycle model, queue/worker/fan-out/critical-path visualization and warnings/failure context over existing event diagnostics APIs.
- `D23` - completed: панель состояния рабочего стека и здоровья очередей, компактная карточка готовности перед запуском, глобальный экран `Стек`, использование `/health/live`, `/health/ready`, `/health/metrics`, покрытие профилей воркеров, нагрузка очередей, накопление задач, очереди без воркеров и понятные подсказки восстановления.
- `D24` - completed: audit history management panel with metrics, status/domain/query/focus filters, stale/problematic/hidden slices, quick latest-successful open, repeat audit action, and local hide/restore without backend deletion.
- `D25` - completed: recommendation action tracking with local per-audit action statuses, progress summary, group-level closure counts, and recommendation card status controls without mutating backend recommendation payloads.
- `D26` - completed: interface copy and terminology polish with Russian primary UI labels, frontend terminology helpers, polished recommendation/report/runtime/timeline copy, production smoke fragments, and backend recommendation display strings without schema/code changes.

## Актуальное состояние после D20

Состояние реализации после D20:

- `D20` реализует GitHub issue `#39`.
- Каноническая topology теперь: `pipeline`, `network`, `heavy_analysis`, `cpu_ml`.
- Новая очередь: `audits.heavy_analysis`.
- Target pipeline теперь идёт `fetch -> heavy_analysis -> features -> scoring`.
- Competitor fan-out split: `competitor_page` выполняет network fetch и сохраняет snapshot, `competitor_analysis` выполняет semantic/ML analysis в heavy queue.
- `GET /health/metrics` и benchmark report показывают отдельную pressure/topology evidence для heavy queue.
- Admission control отклоняет новые аудиты при `backlogged`/`stuck` heavy queue с кодом `heavy_analysis_queue_capacity_exhausted`.

Что реально изменилось в `D20`:

- добавлен `backend/app/heavy_analysis.py` с deterministic snapshot-based heavy analyzer payload;
- добавлены JSON columns `audits.heavy_analysis` и `audit_competitors.snapshot`;
- `AuditRead` и `AuditResultsRead` теперь отдают `heavy_analysis`;
- `worker_topology_profiles.json` содержит отдельный profile `heavy_analysis`;
- `scripts/dev.mjs` автоматически запускает heavy worker через JSON topology;
- timeline diagnostics знает стадии `heavy_analysis` и `competitor_analysis`;
- benchmark markdown содержит section `Topology Profiles` и `Heavy Analysis Isolated`.

Ключевые места D20:

- `backend/app/heavy_analysis.py`
  - `build_heavy_analysis_payload(...)`
  - `merge_heavy_analysis_features(...)`
- `backend/app/competitors.py`
  - `fetch_competitor_page(...)`
  - `analyze_competitor_snapshot(...)`
- `backend/app/tasks.py`
  - `process_audit_run_heavy_analysis(...)`
  - `process_audit_collect_competitor_page(...)`
  - `process_audit_analyze_competitor_page(...)`
- `backend/app/celery_app.py`
  - `AUDIT_HEAVY_ANALYSIS_QUEUE`
  - heavy task routes and task annotations
- `backend/app/worker_topology_profiles.json`
  - `heavy_analysis` worker profile
- `backend/app/distributed_benchmark.py`
  - topology profile summary in JSON/markdown report
- `backend/app/schemas/audit.py`
  - `heavy_analysis` fields in audit/results contracts

## Актуальное состояние после D21

Состояние реализации после D21:

- `D21` реализует GitHub issue `#40`.
- В audit workspace добавлена вкладка `Отчёт`.
- После создания или выбора аудита frontend открывает `Обзор`; `Отчёт` остаётся явной вкладкой (`?tab=report`).
- Отчёт агрегирует `results`, grouped `recommendations`, competitor evidence и `events/diagnostics`.
- Экспорт выполняется на клиенте без повторного анализа страницы:
  - printable HTML view с возможностью `Save as PDF`;
  - downloadable HTML;
  - downloadable Markdown.
- `site:check` теперь проверяет наличие report/export UI в production bundle.

Ключевые места D21:

- `frontend/src/pages/AuditReportPage.tsx` — report dashboard и export actions;
- `frontend/src/lib/auditReport.ts` — pure report model, Markdown/HTML export builders и filename helper;
- `frontend/src/hooks/useAuditWorkspace.ts` — загрузка timeline diagnostics вместе с results/recommendations;
- `frontend/src/api/api.ts` — `getTimelineDiagnostics(...)`;
- `frontend/src/types.ts` — frontend contracts для timeline diagnostics, `query_intent`, `feature_schema_version`, `target_snapshot_summary`;
- `frontend/src/components/AuditTabs.tsx` и `frontend/src/App.tsx` — вкладка `report`, explicit tab routing и default navigation в `Обзор`;
- `scripts/site-content-check.mjs` — smoke-check ключевых строк report/export UI.

## Актуальное состояние после D26

Состояние реализации после D26:

- `D22` реализовал GitHub issue `#41`: в audit workspace есть вкладка `Таймлайн`, которая использует `GET /audits/{audit_id}/events` и `GET /audits/{audit_id}/events/diagnostics` без изменения backend orchestration.
- `D22` показывает lifecycle стадий, dispatch-события очередей, raw event stream, fan-out branches, critical path, warnings/failure context и graceful empty state для старых аудитов без event log.
- `D23` реализовал GitHub issue `#42`: в приложении есть глобальный экран `Стек`, а на экране запуска — компактная панель `Готовность рабочего стека`.
- `D23` использует существующие backend endpoints `GET /health/live`, `GET /health/ready` и `GET /health/metrics`; серверная оркестрация не менялась.
- Пользователь видит готовность API/Redis/SearXNG, покрытие профилей воркеров, нагрузку очередей, накопление задач, очереди без воркеров и подсказки восстановления.
- `D24` реализовал GitHub issue `#43`: экран истории стал audit management panel поверх существующего `GET /audits`.
- Пользователь может фильтровать историю по статусу, домену, запросу и фокусу (`успешные`, `проблемные`, `зависшие/устаревшие`, `скрытые локально`), открыть последний успешный аудит, повторить запуск из строки и локально скрыть/восстановить запись.
- D24 не добавляет backend delete/hide endpoint: скрытие хранится в `localStorage`, а повтор использует существующий `POST /audits` с исходными `query`, `target_url`, `top_n`.
- `site:check` проверяет ключевые строки timeline UI, report/export UI, панели состояния рабочего стека, управления историей и плана действий в production bundle.
- `D25` реализует GitHub issue `#44`: страница рекомендаций стала локальным планом действий.
- Пользователь может отмечать каждую рекомендацию статусами `Не начато`, `В работе`, `Исправлено`, `Игнорируется`; UI показывает `План действий`, общее число закрытых действий, процент прогресса и закрытие по группам.
- D25 не меняет backend recommendation payload: action tracking сохраняется per-audit в `localStorage` и остаётся user workflow metadata.
- `D26` реализует GitHub issue `#45`: основные интерфейсные labels переведены на понятную русскую терминологию, а технические коды рекомендаций, очередей и этапов оставлены вторым уровнем.
- D26 не меняет API schema, ключи групп, коды рекомендаций или localStorage contracts; backend recommendation display strings отполированы только как пользовательская copy.

Ключевые места D23-D26:

- `frontend/src/lib/runtimeHealth.ts` — pure view model состояния рабочего стека поверх ответов live/ready/metrics;
- `frontend/src/hooks/useRuntimeHealth.ts` — периодический frontend polling диагностики рабочего стека;
- `frontend/src/pages/RuntimeStatusPage.tsx` — полная панель состояния стека и компактная карточка готовности перед запуском;
- `frontend/src/api/api.ts` — `runtimeApi.getLiveness()`, `getReadiness()`, `getMetrics()`;
- `frontend/src/App.tsx`, `frontend/src/components/ControlRail.tsx`, `frontend/src/components/AuditWorkspace.tsx` — глобальный route `/?view=runtime` и компактная карточка на экране запуска;
- `scripts/site-content-check.mjs` — production smoke-check ключевых строк панели состояния рабочего стека, управления историей, плана действий, report/export и D26 copy polish;
- `frontend/src/lib/auditHistory.ts` — pure model истории, фильтров, stale/problematic/hidden classification и repeat payload;
- `frontend/src/components/AuditHistoryPanel.tsx` — панель истории, localStorage hide/restore, метрики, фильтры и быстрые действия;
- `frontend/src/components/RecentAuditList.tsx` — строки истории без nested buttons, row actions `Открыть`, `Повторить аудит`, `Скрыть локально`/`Восстановить`;
- `frontend/src/App.tsx` — repeat audit wiring через существующий create-audit flow;
- `frontend/src/lib/recommendationActions.ts` — pure model статусов действий, persisted state validation, summaries and group progress;
- `frontend/src/pages/RecommendationsPage.tsx` — localStorage state, `План действий`, summary metrics and status updates;
- `frontend/src/components/RecommendationList.tsx` — controls на карточках рекомендаций и group-level progress;
- `frontend/src/lib/terminology.ts` — frontend display-label layer для backend-originated labels;
- `frontend/src/lib/auditReport.ts`, `frontend/src/lib/auditReportHtml.ts`, `frontend/src/pages/AuditReportPage.tsx` — русская report/export copy;
- `backend/app/recommendations.py` — user-facing recommendation labels/messages polished without schema/code changes;

## Что Делать Дальше

Если следующий чат продолжает развитие проекта, ближайший логичный фокус сейчас — финальный ML-этап `D27-D31`, если пользователь не выбрал другую задачу явно. Волна GitHub `#40-#45` закрыта после `D26`; demo mode намеренно не входит в backlog.

Важно для новых Codex-диалогов: GitHub Issues этого репозитория могут быть не видны через публичный API и обычный браузер (`404 Not Found`) без авторизованного GitHub-доступа. Поэтому задачи `D27-D31` продублированы локально и должны быть видны из рабочей копии:

- `plans/d27-d31-final-model-training.md`;
- этот раздел `AGENTS.md`;
- `README.md`;
- `backend/README.md`;
- `docs/roadmap/product-development-roadmap.md`.

Перед началом любой новой задачи:

- сначала перечитать `AGENTS.md` и `README.md`;
- затем проверить `git status`;
- если нужен GitHub, посмотреть open issues через локальный credential helper без вывода секретов; если GitHub возвращает `404`, использовать локальный backlog `D27-D31`;
- не откатывать уже выполненные `D13-D26` без прямой причины.

## Последняя runtime smoke-проверка

Последняя проверка полного локального stack выполнялась `2026-04-30` после фикса SearXNG readiness:

- `npm start` поднял `Redis`, `SearxNG`, backend, frontend и четыре Celery worker-профиля;
- frontend отвечал на `http://127.0.0.1:5173/`;
- backend в этой проверке выбрал `http://127.0.0.1:8001/`, потому что `8000` уже был занят; root dev-скрипт автоматически передал этот API URL во frontend;
- `GET /health/live` вернул `200 OK`;
- `GET /health/ready` вернул `200 OK`, проверил SearXNG через `/healthz` и показал workers `pipeline`, `network`, `heavy_analysis`, `cpu_ml` без `missing_queues`;
- `GET /health/metrics` показал `workers.status=ok` и `queue_pressure.status=ok`; общий `status=degraded` был только из-за старых SQLite rows со статусом `processing`;
- локальный `infra/searxng/settings.yml` фиксирует stable engine `presearch`, потому что default SearXNG engines часто дают CAPTCHA/403 при частых dev-проверках;
- smoke audit `сайт для фрилансеров` / `https://gigle.ru/` / `top_n=3` (`128aee58-5bf3-480f-9511-bb96af3898fa`) завершился со status `completed`, score `57.2905`, `3` competitors found/analyzed и без failed competitors;
- timeline diagnostics подтвердил распределённую обработку конкурентов: `fan_out.stage=competitor_page`, `dispatch_count=3`, `terminal_count=3`, а `critical_path_stages` содержит `competitor_page` и `competitor_analysis` с `mode=fan_out_max`.

Локальный `GET /health/metrics` может показывать `degraded`, если в игнорируемой SQLite БД остались старые audit rows со статусом `processing`. Это не означает, что текущий worker stack не поднялся: для готовности distributed runtime сначала смотреть `GET /health/ready`, `workers.status`, `queue_pressure.status` и отсутствие `missing_queues`.

Где смотреть параллельную работу в UI: кнопка/экран `Стек` показывает профили workers и очереди, а вкладка `Таймлайн` внутри аудита показывает fan-out ветки конкурентов, dispatch events и critical path.

## GitHub И Секреты

- Для GitHub-операций на этой машине уже использовался локальный credential helper (`manager`).
- Не печатать секреты, токены и значения из credential store в вывод и не писать их в файлы репозитория.
- Если нужен GitHub API или push, использовать локальный credential helper или запросить новый токен у пользователя, но не сохранять его в репозитории.

## Dataset Bundles (`D17`)

Начиная с `D17`, каноническое место для обучающих датасетов и их metadata:

- `backend/data/dataset_versions/baseline-v1/`
- `backend/data/dataset_versions/dataset-v2/`

Что важно для следующего агента:

- `baseline-v1` уже заморожен из текущего `ru_commercial_dataset.*`.
- `dataset-v2/seeds.csv` уже создан и содержит 450 запросов.
- `dataset-v2/expert_labels.csv` — шаблон для экспертной подвыборки.
- `dataset-v2/dataset.csv`, `failures.csv`, `checkpoint.json`, `dataset.dataset.json` и `artifacts/` уже созданы и отправлены в `origin/main` в рамках `D27`; `manifest.json` и `split.json` сформированы в рамках `D28`; следующий шаг — `D29`, то есть обучить candidate model без замены production artifact.
- `app.ml.dataset_builder` умеет собирать versioned dataset через `--versioned-layout` и писать raw snapshot artifacts.
- `app.ml.dataset_quality` теперь включает dataset metadata, label provenance, artifact coverage и optional split summary.
- `app.ml.train` умеет сохранять persisted split manifest и имеет `--split-only` режим без обучения модели.
- `app.ml.publish` использует manifest dataset version и dataset split metadata.
