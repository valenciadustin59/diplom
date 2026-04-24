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
- `docs/roadmap/` — roadmap и backlog.
- `plans/` и `PLANS.md` — вспомогательные planning-документы.
- `docker-compose.searxng.yml` — локальный стек `SearxNG + Redis`.

## Текущий backlog

Старые product issues `#1-#25` больше не считаются активным backlog source of truth. Они остаются только как архив истории проекта.

Канонический backlog текущего этапа — distributed sequence `D1-D12`.

Статус:

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

Итог: backlog `D1-D12` завершён.

Если ниже в каких-либо старых документах встречаются упоминания о незавершённом `D12`, считать их историческими и неактуальными.

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
- `docs/roadmap/product-development-roadmap.md` — roadmap и backlog.
- `backend/docs/ml_methodology_appendix.md` — ML methodology appendix.

## Git и публикация

- Коммитить только после проверок.
- Не заявлять о закрытии issue, если push не выполнен.
- Если используется `Closes #<n>`, issue должен закрываться через push в `main`, а не вручную без кода.


## D13-D20 Status

Current next-wave backlog: `D13-D20`.

- `D13` - completed: versioned extraction pipeline, `feature schema v2`, persistent `target_snapshot`, DOM-based extraction, and API snapshot summary.
- `D14` - completed: пакет технических SEO-сигналов поверх `target_snapshot`, включая canonical/redirect/indexability/url-hygiene признаки, технические рекомендации и технические факторы в score explanation без изменения текущего `FEATURE_COLUMNS`.
- `D15` - completed: пакет commercial/trust signals для коммерческих landing pages, включая contact/business identity признаки, CTA/messenger detection, агрегированные commercial/trust scores и recommendation layer, доступный также в dataset builder.
- `D16` - completed: query intent detection, intent-alignment features for target and competitors, persisted `query_intent` in `Audit`, SERP-relative gaps/percentiles/z-scores for key signal groups, and relative/intent-aware explanation and recommendation rules.
- `D17` - completed: versioned dataset workflow, frozen `baseline-v1`, prepared `dataset-v2` seed bundle, hybrid labeling contract (`weak_target_score`, `expert_target_score`, `target_score`, `label_source`), raw extraction artifacts for dataset rows, enriched dataset manifest and persisted `group_by_query` split.
- `D18` - completed: model schema v2, artifact-driven runtime/training/publish flow, ranking benchmark workflow, ranking candidate publish/report path.
- `D19` - completed: grouped recommendations API/UI, factor groups (`Technical SEO`, `Commercial and Trust`, `Semantic and Intent`, `Competitor Gap`), competitor-relative deviations, richer explainability payload, legacy recommendation normalization for old audits.
- `D20` - completed: dedicated `audits.heavy_analysis` queue/profile, target heavy-analysis stage, split competitor network fetch vs heavy semantic/ML analysis, heavy queue admission guard, metrics pressure visibility and benchmark topology profile summary.

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

## Что Делать Дальше

Если следующий чат продолжает развитие проекта, ближайший логичный фокус нужно брать из актуальных open GitHub issues после push D20.

Перед началом любой новой задачи:

- сначала перечитать `AGENTS.md` и `README.md`;
- затем проверить `git status`;
- затем посмотреть open issues в GitHub и выбрать следующий backlog scope;
- не откатывать уже выполненные `D13-D20` без прямой причины.

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
