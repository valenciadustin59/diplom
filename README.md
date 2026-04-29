# Site Audit

Веб-приложение для автоматизации SEO-аудита посадочных страниц по поисковому запросу.

Пользователь задаёт поисковый запрос и URL своей страницы, после чего система:

- находит конкурентные страницы в выдаче;
- анализирует целевую страницу и конкурентов;
- извлекает SEO, технические, текстовые, коммерческие и поведенчески значимые признаки;
- оценивает качество страницы с помощью ML-модели;
- показывает сравнение с конкурентами;
- формирует рекомендации с приоритетами.

Проект ориентирован на тему диплома: распределённое web-приложение машинного обучения. Распределённая часть построена на `Celery + Redis`, а доказательная база по runtime подтверждается health/metrics, event timeline и benchmark workflow.

## Основные возможности

- запуск нового аудита по запросу и URL;
- сбор конкурентов через `SearxNG`;
- пошаговая распределённая обработка аудита по stage-based pipeline;
- ML-scoring страницы и сохранение breakdown по оценке;
- technical SEO feature pack на основе snapshot-артефакта страницы;
- commercial/trust feature pack для коммерческих landing pages;
- изоляция тяжёлых analyzer-стадий в отдельную distributed queue;
- выдача рекомендаций по улучшению страницы;
- единый audit report dashboard с экспортом в печатный HTML/PDF-like view, HTML и Markdown;
- timeline событий аудита и диагностика критического пути;
- runtime telemetry для очередей, workers, backlog и admission control;
- benchmark/reporting workflow для демонстрации распределённого исполнения.

## Архитектура

### Компоненты

- `frontend/` — интерфейс на `React + TypeScript + Vite`.
- `backend/` — API на `FastAPI`, orchestration, хранение данных, ML scoring и training workflow.
- `Redis` — broker/result backend для `Celery`.
- `Celery workers` — исполняют стадии аудита в распределённом runtime.
- `SearxNG` — поисковый провайдер для получения конкурентных страниц.
- `SQLite` — хранилище MVP.

### Распределённый pipeline

Аудит больше не выполняется одной монолитной задачей. Он разбит на отдельные стадии и очереди:

- `audits.pipeline` — orchestration, admission control, dispatch стадий;
- `audits.fetch` — загрузка целевой страницы;
- `audits.heavy_analysis` — snapshot-based тяжёлые анализаторы target и semantic/ML анализ competitor pages;
- `audits.features` — извлечение признаков;
- `audits.scoring` — rule-based и ML scoring;
- `audits.competitors` — поиск и подготовка конкурентов;
- `audits.competitor_pages` — fan-out обработка страниц конкурентов;
- `audits.recommendations` — генерация рекомендаций;
- `audits.finalize` — финализация результата.

### Профили workers

Начиная с `D20`, каноническая топология workers выглядит так:

- `pipeline` — orchestration и dispatch;
- `network` — сетевые стадии: `fetch`, `competitors`, `competitor_pages`;
- `heavy_analysis` — тяжёлые snapshot/semantic/ML analyzer-задачи;
- `cpu_ml` — `features`, `scoring`, `recommendations`, `finalize`.

Именно эта топология проверяется через `GET /health/ready` и `GET /health/metrics`.

## Структура репозитория

- `backend/` — FastAPI backend, Celery runtime, ML и тесты backend.
- `frontend/` — React frontend.
- `scripts/` — dev-скрипты, benchmark workflow, генерация обучающих запросов.
- `docs/roadmap/` — стратегический roadmap; operational handoff находится в `AGENTS.md`.
- `docker-compose.searxng.yml` — локальный стек `SearxNG + Redis`.
- `plans/` и `PLANS.md` — вспомогательные проектные материалы.

## Статус backlog

Завершённые волны проекта:

- `D1-D12` — distributed runtime foundation: stage-based pipeline, per-stage queues, fan-out, health/metrics, diagnostics, admission control и benchmark evidence.
- `D13-D23` — SEO/ML/product/frontend evidence wave: snapshot extraction, feature schema v2, technical SEO, commercial/trust, intent-aware и SERP-relative features, dataset/model workflow, grouped recommendations UI, isolated heavy-analysis queue, audit report/export dashboard, audit execution timeline UI и runtime status/queue health UI.

Итог: проект уже закрывает ключевые требования дипломной темы — web-приложение машинного обучения с доказуемым распределённым runtime.

Актуальная frontend/product wave после `D21` заведена в GitHub:

- `D21` / `#40` — completed: audit report and export dashboard.
- `D22` / `#41` — completed: audit execution timeline UI.
- `D23` / `#42` — completed: runtime status and queue health UI.
- `D24` / `#43` — audit history management.
- `D25` / `#44` — recommendation action tracking.
- `D26` / `#45` — interface copy and terminology polish.

Приоритет ближайшей разработки после `D23`: audit history management (`D24`). Demo mode в текущий backlog не входит.

### Distributed foundation `D1-D12`

Выполнено:

- `D1-D4` — stage-based pipeline, per-stage queues, distributed fan-out, retry-safe orchestration.
- `D5-D8` — `health/live`, `health/ready`, `health/metrics`, persistent event log и timeline diagnostics.
- `D9-D11` — queue pressure detector, admission control под нагрузкой, worker topology profiles.
- `D12` — benchmark/reporting workflow для измеримого подтверждения распределённого runtime.

Итог: backlog `D1-D12` завершён. После `D23` следующий практический фокус — не новый backend-runtime слой, а audit history management (`D24` / `#43`), который развивает продуктовый workflow вокруг уже существующих аудитов.

## Требования

- `Python 3.12` или `3.13`
- `Node.js 20+`
- `npm`
- `Docker Desktop` или совместимый Docker runtime

Все команды ниже приведены в формате `PowerShell` для Windows.

## Быстрый старт

### 1. Установить root и frontend зависимости

```powershell
cd E:\codexPROJ\diplom
npm install
npm --prefix frontend install
```

### 2. Подготовить backend окружение

```powershell
cd E:\codexPROJ\diplom\backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
copy .env.example .env
```

Если используется `Python 3.13`, workflow остаётся тем же: `backend/pyproject.toml` допускает версии `>=3.12,<3.14`.

### 3. Запустить полный локальный стек

```powershell
cd E:\codexPROJ\diplom
npm run dev:full
```

Короткий эквивалент для запуска из консоли:

```powershell
cd E:\codexPROJ\diplom
npm start
```

Команда:

- поднимает `SearxNG` и `Redis`;
- проверяет доступность `SearxNG`;
- запускает backend API;
- запускает frontend;
- запускает четыре worker-профиля: `pipeline`, `network`, `heavy_analysis`, `cpu_ml`.

Это рекомендуемый режим для полноценного аудита и для демонстрации распределённой архитектуры.

### Проверка сборки и содержимого frontend

Перед демонстрацией можно проверить, что production-сборка собирается и содержит ключевые экраны интерфейса:

```powershell
cd E:\codexPROJ\diplom
npm run site:check
```

Команда выполняет `frontend` build и проверяет `frontend/dist/index.html`, подключённые JS/CSS assets и основные тексты интерфейса: запуск аудита, историю аудитов, рабочее пространство, конкурентов, рекомендации, score и ML-калибровку.

### 4. Проверить готовность runtime

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/live"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/metrics"
```

Что важно:

- `GET /health/live` показывает, что процесс API жив.
- `GET /health/ready` возвращает `200`, когда готовы БД, Redis, workers и нужные очереди.
- `GET /health/ready` может вернуть `503`, если distributed runtime не готов.
- `GET /health/metrics` показывает backlog очередей, queue pressure, worker activity и runtime alerts.

## Разница между `npm run dev` и `npm run dev:full`

- `npm run dev` запускает только backend и frontend.
- `npm run dev:full` дополнительно поднимает `SearxNG`, `Redis` и Celery workers.

Для полного audit lifecycle используйте именно `npm run dev:full`.

Если backend запущен без worker-стека, `POST /audits` может вернуть `503` из-за admission guard, либо аудит не сможет полноценно пройти распределённые стадии.

## Ручной запуск компонентов

### SearxNG и Redis

```powershell
cd E:\codexPROJ\diplom
npm run searxng:up
npm run searxng:check
```

Остановка:

```powershell
cd E:\codexPROJ\diplom
npm run searxng:down
```

### Backend API

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd E:\codexPROJ\diplom\frontend
npm run dev
```

### Celery workers

Рекомендуемый вариант — `npm run dev:full`. Если нужен ручной запуск, используйте отдельные профили.

`pipeline`:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info --hostname site-audit.pipeline@%h -Q audits.pipeline --pool=solo
```

`network`:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info --hostname site-audit.network@%h -Q audits.fetch,audits.competitors,audits.competitor_pages --pool=solo
```

`heavy_analysis`:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info --hostname site-audit.heavy_analysis@%h -Q audits.heavy_analysis --pool=solo
```

`cpu_ml`:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info --hostname site-audit.cpu_ml@%h -Q audits.features,audits.scoring,audits.recommendations,audits.finalize --pool=solo
```

На Windows для локальной разработки используется `--pool=solo`.

## Основные API endpoints

### Health

- `GET /health` — простой legacy healthcheck.
- `GET /health/live` — liveness API.
- `GET /health/ready` — readiness distributed stack.
- `GET /health/metrics` — runtime telemetry по очередям, workers и backlog.

### Audits

- `GET /audits` — список аудитов.
- `POST /audits` — создать новый аудит.
- `GET /audits/{audit_id}` — текущее состояние аудита.
- `GET /audits/{audit_id}/results` — результат и score breakdown.
- `GET /audits/{audit_id}/recommendations` — рекомендации.
- `GET /audits/{audit_id}/events` — timeline событий.
- `GET /audits/{audit_id}/events/diagnostics` — диагностика critical path и fan-out.

Важно: начиная с `D10`, `POST /audits` может возвращать `503`, если runtime capacity деградирована и admission control временно отклоняет новые аудиты.

## Benchmark workflow (`D12`)

Для подтверждения распределённого исполнения используется benchmark runner, который работает поверх реального HTTP API, а не отдельного synthetic path.

Пример запуска:

```powershell
cd E:\codexPROJ\diplom
backend\.venv\Scripts\python.exe scripts\run_distributed_benchmark.py `
  --base-url http://127.0.0.1:8000 `
  --workload-file scripts\distributed_benchmark.workload.example.json `
  --benchmark-name diploma-distributed-runtime `
  --max-inflight 3 `
  --poll-interval 1.0 `
  --metrics-interval 2.0 `
  --timeout 600 `
  --print-markdown
```

Benchmark использует:

- `POST /audits` — admission и запуск аудитов;
- `GET /audits/{audit_id}` — отслеживание жизненного цикла;
- `GET /audits/{audit_id}/events/diagnostics` — latency и critical path;
- `GET /health/metrics` — backlog, queue pressure, topology profiles, worker utilization и alerts.

Артефакты сохраняются в:

- `backend/artifacts/benchmarks/<timestamp>-<benchmark-name>/benchmark-report.json`
- `backend/artifacts/benchmarks/<timestamp>-<benchmark-name>/benchmark-report.md`

Пример workload-файла лежит в `scripts/distributed_benchmark.workload.example.json`.

## Тесты и проверки

### Backend tests

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest
```

### Script-level tests

```powershell
cd E:\codexPROJ\diplom
npm run test:scripts
```

### Frontend build

```powershell
cd E:\codexPROJ\diplom
npm run build
```

### Frontend unit tests

```powershell
cd E:\codexPROJ\diplom\frontend
npm run test
```

## Полезные скрипты

- `scripts/generate_training_queries.py` — генерация seed-набора обучающих запросов.
- `scripts/run_training_batches.py` — batch workflow для обучения.
- `scripts/run_distributed_benchmark.py` — benchmark distributed runtime.

## Что важно для диплома

Проект не ограничивается набором статических SEO-правил. Основная идея — оценка качества страницы как совокупности признаков:

- соответствие запроса структуре страницы;
- согласованность `title`, `h1`, заголовков и основного текста;
- релевантность поисковому интенту;
- коммерческая полнота страницы;
- конкурентоспособность относительно страниц из выдачи.

За счёт `Celery`, очередей, fan-out обработки конкурентов, health/metrics, timeline diagnostics и benchmark workflow проект даёт не только ML-оценку, но и убедимую распределённую архитектуру для темы дипломной работы.

## Статус D13-D23

Продуктовая волна backlog — `D13-D23` — завершена.

Выполнено:

- `D13` - версионированный extraction pipeline и `feature schema v2`: постоянный `target_snapshot`, DOM-based extraction, повторяемый пересчёт признаков из сохранённого snapshot и API-поля `feature_schema_version` и `target_snapshot_summary`.
- `D14` - пакет технических SEO-признаков: technical signals из snapshot, технические рекомендации и technical factors в score explanation без изменения текущей ML-схемы признаков.
- `D15` - пакет commercial/trust signals: телефоны, адрес, часы работы, цены, доставка, оплата, гарантия, возврат, отзывы, рейтинг, FAQ, CTA, мессенджеры, legal/business identity признаки, агрегированные commercial/trust scores и новый recommendation layer.
- `D16` - SERP-relative и intent-aware слой: `query_intent`, intent-alignment features для target/competitors, relative gaps/percentiles/z-scores по ключевым signal groups и новый explanation/recommendation context.
- `D17` - versioned dataset workflow: заморожен `baseline-v1`, добавлен `dataset-v2` bundle, hybrid labeling (`weak_serp + expert subset`), сохранение raw extraction artifacts, versioned manifest и воспроизводимый `group_by_query` split.

Выполнено дополнительно:

- `D18` - model schema v2, artifact-driven runtime/training/publish flow, ranking benchmark workflow и publish/report path.
- `D19` - grouped recommendations API/UI, factor groups (`Technical SEO`, `Commercial and Trust`, `Semantic and Intent`, `Competitor Gap`), competitor-relative deviations, richer explainability payload и legacy normalization для старых аудитов.
- `D20` - dedicated `audits.heavy_analysis` queue/profile, target heavy-analysis stage, split competitor network fetch vs heavy semantic/ML analysis, heavy queue admission guard, queue-pressure metrics and benchmark topology-profile summary.
- `D21` - audit report/export dashboard: вкладка `Отчёт`, компактная сводка SEO/ML/recommendation/competitor/runtime evidence, printable HTML/PDF-like view, downloadable HTML и Markdown export без повторного анализа страницы.
- `D22` - audit execution timeline UI: вкладка `Таймлайн`, raw event stream, stage lifecycle, queues, fan-out branch summary, critical path, warnings/failure context поверх существующих events APIs.
- `D23` - runtime status and queue health UI: компактная панель готовности runtime на экране запуска, вкладка `Runtime` в audit workspace, health/live/ready/metrics consumption, worker profile coverage, queue pressure/backlog/stuck queues и человекочитаемые подсказки восстановления.

Текущая волна `D13-D23` завершена. Если нет явно выбранного GitHub issue, ближайшие открытые задачи: `D24` / `#43` history management, `D25` / `#44` recommendation action tracking, `D26` / `#45` copy polish.

## Dataset V2 Workflow (`D17`)

Начиная с `D17`, обучающие данные больше не рассматриваются как один неявный CSV в `backend/data/`. Для ML-части введён versioned bundle в `backend/data/dataset_versions/`.

Что уже есть в репозитории:

- `backend/data/dataset_versions/baseline-v1/` — зафиксированная копия текущего primary dataset, manifest, checkpoint и seeds.
- `backend/data/dataset_versions/dataset-v2/` — seed bundle нового датасета, metadata-файл, шаблон `expert_labels.csv` и целевая структура для `dataset.csv`, `failures.csv`, `manifest.json`, `split.json` и raw `artifacts/`.

Ключевые принципы `D17`:

- слабая метка строится из позиции в выдаче (`weak_target_score`);
- экспертная разметка хранится отдельно (`expert_target_score`);
- итоговая training label сохраняется как `target_score` и помечается `label_source`;
- по каждой строке dataset v2 может сохраняться raw snapshot-артефакт extraction schema v2;
- train/validation split сохраняется отдельно и воспроизводимо в формате `group_by_query`.

Базовый workflow построения `dataset-v2`:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m app.ml.dataset_builder `
  --dataset-version dataset-v2 `
  --versioned-layout `
  --freeze-baseline `
  --seeds-file data\dataset_versions\dataset-v2\seeds.csv `
  --expert-labels data\dataset_versions\dataset-v2\expert_labels.csv `
  --overwrite
```

После сборки manifest и split формируются так:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m app.ml.dataset_quality `
  --dataset data\dataset_versions\dataset-v2\dataset.csv `
  --failures data\dataset_versions\dataset-v2\failures.csv `
  --seeds data\dataset_versions\dataset-v2\seeds.csv `
  --dataset-version dataset-v2 `
  --baseline-version baseline-v1 `
  --artifacts-dir data\dataset_versions\dataset-v2\artifacts `
  --split data\dataset_versions\dataset-v2\split.json `
  --output data\dataset_versions\dataset-v2\manifest.json

.venv\Scripts\python.exe -m app.ml.train `
  --dataset data\dataset_versions\dataset-v2\dataset.csv `
  --dataset-version dataset-v2 `
  --split-output data\dataset_versions\dataset-v2\split.json
```
