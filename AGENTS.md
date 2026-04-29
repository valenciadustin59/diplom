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
- `D13-D21` — SEO/ML/product wave: snapshot extraction, feature schema v2, technical SEO, commercial/trust, intent-aware и SERP-relative features, dataset/model workflow, grouped recommendations UI, isolated heavy-analysis queue и audit report/export dashboard.

Активная планируемая волна после `D21`: `D22-D26` — frontend/product layer без изменения ядра анализа:

- `D21` / GitHub `#40` — completed: audit report and export dashboard;
- `D22` / GitHub `#41` — audit execution timeline UI;
- `D23` / GitHub `#42` — runtime status and queue health UI;
- `D24` / GitHub `#43` — audit history management;
- `D25` / GitHub `#44` — recommendation action tracking;
- `D26` / GitHub `#45` — interface copy and terminology polish.

Текущий практический фокус: не переписывать backend и не добавлять demo mode, а усиливать демонстрационный и управленческий frontend layer, который показывает уже существующие SEO/ML/distributed evidence. Если пользователь просит новый backlog scope без конкретного GitHub issue, ближайший логичный кандидат после `D21` — `D22` / `#41`: audit execution timeline UI.

### D1-D12 Summary

Статус `D1-D12`: завершено.

- `D1` — stage-based decomposition audit pipeline
- `D2` — per-stage Celery queues and routing
- `D3` — distributed fan-out по competitor pages
- `D4` — retry-safe / version-aware orchestration
- `D5` — `health/live` и `health/ready`
- `D6` — `health/metrics` и runtime telemetry
- `D7` — persistent audit event log
- `D8` — audit timeline diagnostics API
- `D9` — queue pressure snapshots и stuck/backlogged detector
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

Эта topology валидируется через readiness и runtime metrics. Старый single all-queues worker допустим только как debugging fallback.

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

Начиная с `D10`, `POST /audits` может вернуть `503`, если runtime capacity деградирована. Это нормальная часть поведения системы, а не баг по умолчанию.

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
- `docs/roadmap/product-development-roadmap.md` — стратегический roadmap после `D20`.
- `backend/docs/ml_methodology_appendix.md` — ML methodology appendix.

## Git и публикация

- Коммитить только после проверок.
- Не заявлять о закрытии issue, если push не выполнен.
- Если используется `Closes #<n>`, issue должен закрываться через push в `main`, а не вручную без кода.


## D13-D21 Status

Completed product/ML/SEO/frontend evidence wave: `D13-D21`.

- `D13` - completed: versioned extraction pipeline, `feature schema v2`, persistent `target_snapshot`, DOM-based extraction, and API snapshot summary.
- `D14` - completed: пакет технических SEO-сигналов поверх `target_snapshot`, включая canonical/redirect/indexability/url-hygiene признаки, технические рекомендации и технические факторы в score explanation без изменения текущего `FEATURE_COLUMNS`.
- `D15` - completed: пакет commercial/trust signals для коммерческих landing pages, включая contact/business identity признаки, CTA/messenger detection, агрегированные commercial/trust scores и recommendation layer, доступный также в dataset builder.
- `D16` - completed: query intent detection, intent-alignment features for target and competitors, persisted `query_intent` in `Audit`, SERP-relative gaps/percentiles/z-scores for key signal groups, and relative/intent-aware explanation and recommendation rules.
- `D17` - completed: versioned dataset workflow, frozen `baseline-v1`, prepared `dataset-v2` seed bundle, hybrid labeling contract (`weak_target_score`, `expert_target_score`, `target_score`, `label_source`), raw extraction artifacts for dataset rows, enriched dataset manifest and persisted `group_by_query` split.
- `D18` - completed: model schema v2, artifact-driven runtime/training/publish flow, ranking benchmark workflow, ranking candidate publish/report path.
- `D19` - completed: grouped recommendations API/UI, factor groups (`Technical SEO`, `Commercial and Trust`, `Semantic and Intent`, `Competitor Gap`), competitor-relative deviations, richer explainability payload, legacy recommendation normalization for old audits.
- `D20` - completed: dedicated `audits.heavy_analysis` queue/profile, target heavy-analysis stage, split competitor network fetch vs heavy semantic/ML analysis, heavy queue admission guard, metrics pressure visibility and benchmark topology profile summary.
- `D21` - completed: audit report tab, client-side export dashboard, printable HTML/PDF-like view, downloadable Markdown/HTML report, compact SEO/ML/recommendation/competitor/runtime evidence summary using existing audit results and timeline diagnostics APIs.

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
- После создания или выбора аудита frontend открывает отчёт как основной demonstration view (`?tab=report`).
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
- `frontend/src/components/AuditTabs.tsx` и `frontend/src/App.tsx` — вкладка `report` и default navigation в отчёт;
- `scripts/site-content-check.mjs` — smoke-check ключевых строк report/export UI.

## Что Делать Дальше

Если следующий чат продолжает развитие проекта, ближайший логичный фокус нужно брать из явно выбранной пользователем задачи или из актуальных open GitHub issues. Актуальная новая волна создана в GitHub как `#40-#45`; после завершения `D21` приоритет реализации — `D22` / `#41` timeline UI, затем `D23` / `#42` runtime status. Demo mode намеренно не входит в backlog.

Перед началом любой новой задачи:

- сначала перечитать `AGENTS.md` и `README.md`;
- затем проверить `git status`;
- если нужен GitHub, посмотреть open issues через локальный credential helper без вывода секретов;
- не откатывать уже выполненные `D13-D21` без прямой причины.

## Последняя runtime smoke-проверка

Последняя проверка полного локального stack после запуска Docker Desktop выполнялась `2026-04-24`:

- `npm start` поднял `Redis`, `SearxNG`, backend, frontend и четыре Celery worker-профиля;
- frontend отвечал на `http://127.0.0.1:5173/`;
- `GET /health/live` вернул `200 OK`;
- `GET /health/ready` вернул `200 OK` и показал workers `pipeline`, `network`, `heavy_analysis`, `cpu_ml`;
- smoke audit `seo audit` / `https://example.com/` / `top_n=2` завершился со status `completed`, score `48.3578`, `2` competitors и `26` recommendations.

Локальный `GET /health/metrics` может показывать `degraded`, если в игнорируемой SQLite БД остались старые audit rows со статусом `processing`. Это не означает, что текущий worker stack не поднялся: для готовности distributed runtime сначала смотреть `GET /health/ready` и queue/worker statuses внутри metrics.

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
- `app.ml.dataset_builder` умеет собирать versioned dataset через `--versioned-layout` и писать raw snapshot artifacts.
- `app.ml.dataset_quality` теперь включает dataset metadata, label provenance, artifact coverage и optional split summary.
- `app.ml.train` умеет сохранять persisted split manifest.
- `app.ml.publish` использует manifest dataset version и dataset split metadata.
