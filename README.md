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
- выдача рекомендаций по улучшению страницы;
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
- `audits.features` — извлечение признаков;
- `audits.scoring` — rule-based и ML scoring;
- `audits.competitors` — поиск и подготовка конкурентов;
- `audits.competitor_pages` — fan-out обработка страниц конкурентов;
- `audits.recommendations` — генерация рекомендаций;
- `audits.finalize` — финализация результата.

### Профили workers

Начиная с `D11`, каноническая топология workers выглядит так:

- `pipeline` — orchestration и dispatch;
- `network` — сетевые стадии: `fetch`, `competitors`, `competitor_pages`;
- `cpu_ml` — `features`, `scoring`, `recommendations`, `finalize`.

Именно эта топология проверяется через `GET /health/ready` и `GET /health/metrics`.

## Структура репозитория

- `backend/` — FastAPI backend, Celery runtime, ML и тесты backend.
- `frontend/` — React frontend.
- `scripts/` — dev-скрипты, benchmark workflow, генерация обучающих запросов.
- `docs/roadmap/` — roadmap и backlog текущего этапа проекта.
- `docker-compose.searxng.yml` — локальный стек `SearxNG + Redis`.
- `plans/` и `PLANS.md` — вспомогательные проектные материалы.

## Статус distributed backlog

Текущий канонический backlog проекта — линия `D1-D12`.

Выполнено:

- `D1-D4` — stage-based pipeline, per-stage queues, distributed fan-out, retry-safe orchestration.
- `D5-D8` — `health/live`, `health/ready`, `health/metrics`, persistent event log и timeline diagnostics.
- `D9-D11` — queue pressure detector, admission control под нагрузкой, worker topology profiles.
- `D12` — benchmark/reporting workflow для измеримого подтверждения распределённого runtime.

Итог: backlog `D1-D12` завершён.

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

Команда:

- поднимает `SearxNG` и `Redis`;
- проверяет доступность `SearxNG`;
- запускает backend API;
- запускает frontend;
- запускает три worker-профиля: `pipeline`, `network`, `cpu_ml`.

Это рекомендуемый режим для полноценного аудита и для демонстрации распределённой архитектуры.

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
- `GET /health/metrics` — backlog, queue pressure, worker utilization и alerts.

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

## Статус D13-D20

Текущая продуктовая волна backlog — `D13-D20`.

Выполнено:

- `D13` - версионированный extraction pipeline и `feature schema v2`: постоянный `target_snapshot`, DOM-based extraction, повторяемый пересчёт признаков из сохранённого snapshot и API-поля `feature_schema_version` и `target_snapshot_summary`.
- `D14` - пакет технических SEO-признаков: technical signals из snapshot, технические рекомендации и technical factors в score explanation без изменения текущей ML-схемы признаков.
- `D15` - пакет commercial/trust signals: телефоны, адрес, часы работы, цены, доставка, оплата, гарантия, возврат, отзывы, рейтинг, FAQ, CTA, мессенджеры, legal/business identity признаки, агрегированные commercial/trust scores и новый recommendation layer.

В работе дальше:

- `D16` - SERP-relative и intent-aware слой: `query_intent`, intent-alignment features для target/competitors, relative gaps/percentiles/z-scores по ключевым signal groups и новый explanation/recommendation context.
- `D17-D20` - dataset v2, ranking-oriented model v2, UI/API expansion и тяжёлые distributed analyzers.
