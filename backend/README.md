# Backend

Backend проекта `Site Audit` построен на `FastAPI` и отвечает за:

- создание и хранение аудитов;
- распределённую обработку stage-based pipeline через `Celery`;
- сбор и обработку данных о целевой странице и конкурентах;
- ML scoring и формирование score breakdown;
- генерацию рекомендаций;
- runtime telemetry, readiness и диагностику distributed execution.

Корневой сценарий запуска всего проекта описан в [../README.md](../README.md). Этот файл сфокусирован на backend-командах, API и distributed runtime.

## Стек

- `Python 3.12` или `3.13`
- `FastAPI`
- `SQLAlchemy 2`
- `Pydantic v2`
- `Celery`
- `Redis`
- `scikit-learn`
- `sentence-transformers`
- `CatBoost`
- `SQLite` для MVP

## Структура backend

- `app/main.py` — вход в FastAPI приложение.
- `app/api/routes/` — HTTP endpoints.
- `app/tasks.py` — Celery tasks и orchestration pipeline.
- `app/health.py` — liveness, readiness и runtime metrics.
- `app/distributed_benchmark.py` — benchmark/reporting workflow для distributed runtime.
- `app/worker_topology.py` и `app/worker_topology_profiles.json` — профили workers и queue affinity.
- `tests/` — backend test suite.
- `artifacts/` — generated artifacts, включая benchmark reports.

## Установка

```powershell
cd E:\codexPROJ\diplom\backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
copy .env.example .env
```

Если используется `Python 3.13`, текущий `pyproject.toml` это поддерживает.

## Локальный запуск backend API

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Документация OpenAPI после запуска доступна по адресу:

- `http://127.0.0.1:8000/docs`

## Зависимости distributed runtime

Для полного цикла аудита backend опирается на:

- `Redis` как Celery broker/result backend;
- `SearxNG` как поисковый провайдер для конкурентных страниц;
- Celery workers с правильной queue-affinity топологией.

Рекомендуемый способ поднять весь runtime — из корня репозитория:

```powershell
cd E:\codexPROJ\diplom
npm run dev:full
```

## Health endpoints

Backend предоставляет четыре ключевых health/runtime endpoint'а:

- `GET /health` — простой legacy healthcheck.
- `GET /health/live` — проверка liveness процесса API.
- `GET /health/ready` — проверка готовности всего distributed stack.
- `GET /health/metrics` — runtime telemetry для очередей, workers и backlog.

### Что проверяет `/health/ready`

- доступность БД;
- доступность Redis;
- наличие активных Celery workers;
- покрытие ожидаемых audit queues;
- доступность `SearxNG`, если используется provider `searxng`.

Если один из обязательных компонентов не готов, endpoint вернёт `503`.

### Что показывает `/health/metrics`

- queue depth по audit queues;
- queue pressure snapshots;
- worker activity и queue coverage;
- worker topology profiles и queue affinity;
- alerts от execution detector для stuck/backlogged runtime;
- агрегированные pipeline counters.

## Audit API

Основные backend endpoint'ы:

- `GET /audits` — список аудитов.
- `POST /audits` — создать новый аудит.
- `GET /audits/{audit_id}` — текущее состояние аудита.
- `GET /audits/{audit_id}/results` — результат, score и breakdown.
- `GET /audits/{audit_id}/recommendations` — рекомендации.
- `GET /audits/{audit_id}/events` — timeline событий аудита.
- `GET /audits/{audit_id}/events/diagnostics` — диагностика critical path и fan-out.

### Admission control

Начиная с `D10`, `POST /audits` может вернуть `503`, если runtime capacity деградирована:

- очередь `audits.pipeline` backlogged/stuck;
- detector фиксирует длительное ожидание queued/dispatched работ;
- runtime не готов принимать новый audit без усугубления backlog.

Это поведение является частью архитектуры, а не ошибкой API.

## Распределённый pipeline

Канонические очереди backend:

- `audits.pipeline`
- `audits.fetch`
- `audits.features`
- `audits.scoring`
- `audits.competitors`
- `audits.competitor_pages`
- `audits.recommendations`
- `audits.finalize`

Обработка конкурентов вынесена в distributed fan-out: страницы конкурентов обрабатываются как отдельные подзадачи с последующей агрегацией.

## Профили workers

Каноническая topology из `D11`:

- `pipeline` — orchestration и dispatch.
- `network` — `fetch`, `competitors`, `competitor_pages`.
- `cpu_ml` — `features`, `scoring`, `recommendations`, `finalize`.

Примеры ручного запуска на Windows:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info --hostname site-audit.pipeline@%h -Q audits.pipeline --pool=solo
```

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info --hostname site-audit.network@%h -Q audits.fetch,audits.competitors,audits.competitor_pages --pool=solo
```

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info --hostname site-audit.cpu_ml@%h -Q audits.features,audits.scoring,audits.recommendations,audits.finalize --pool=solo
```

На Windows для локальной разработки используется `--pool=solo`.

## Benchmark workflow (`D12`)

Для демонстрации распределённого исполнения и дипломной доказательной базы используется benchmark runner:

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

Benchmark работает поверх production API surface:

- `POST /audits`
- `GET /audits/{audit_id}`
- `GET /audits/{audit_id}/events/diagnostics`
- `GET /health/metrics`

Он измеряет:

- admission success/rejection;
- end-to-end latency;
- throughput;
- backlog и queue pressure;
- worker utilization;
- runtime alerts.

Артефакты сохраняются в:

- `backend/artifacts/benchmarks/<timestamp>-<benchmark-name>/benchmark-report.json`
- `backend/artifacts/benchmarks/<timestamp>-<benchmark-name>/benchmark-report.md`

## Тесты

### Полный backend regression

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest
```

### Точечный тест benchmark workflow

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest tests\test_distributed_benchmark.py
```

## Training и ML workflow

В репозитории есть вспомогательные скрипты для подготовки обучающих данных и batch workflow:

- `scripts/generate_training_queries.py`
- `scripts/run_training_batches.py`

ML-модель — часть основной фичи проекта: оценка страницы строится по совокупности признаков, а не по набору независимых SEO-правил.

## Связанные документы

- [../README.md](../README.md) — обзор проекта и полный локальный запуск.
- [../AGENTS.md](../AGENTS.md) — operational notes и состояние репозитория.
- [../docs/roadmap/product-development-roadmap.md](../docs/roadmap/product-development-roadmap.md) — backlog и roadmap.
- [docs/ml_methodology_appendix.md](./docs/ml_methodology_appendix.md) — ML methodology appendix.
﻿
