# Backend

Backend проекта `Site Audit` построен на `FastAPI` и отвечает за полный серверный цикл SEO-аудита:

- создание и хранение аудитов;
- распределённую обработку stage-based pipeline через `Celery`;
- получение и нормализацию данных по целевой странице и конкурентам;
- извлечение контентных, семантических, коммерческих и технических SEO-признаков;
- ML scoring и формирование score breakdown;
- генерацию приоритетных рекомендаций;
- runtime telemetry, readiness и диагностику распределённого исполнения.

Корневой сценарий запуска всего проекта описан в `../README.md`. Этот файл сфокусирован именно на backend-архитектуре, API и распределённом runtime.

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

## Что находится в backend

- `app/main.py` — вход в FastAPI-приложение.
- `app/api/routes/` — HTTP endpoints.
- `app/tasks.py` — orchestration и Celery stages.
- `app/parser.py` — загрузка страниц, fallback-стратегии, snapshot/extraction artifact.
- `app/features.py` — контентные, семантические и technical SEO features.
- `app/recommendations.py` — рекомендационный движок.
- `app/ml/` — scoring, training, dataset builder и model artifact workflow.
- `app/health.py` — liveness, readiness и runtime metrics.
- `app/distributed_benchmark.py` — benchmark/reporting workflow для distributed runtime.
- `tests/` — backend test suite.
- `artifacts/` — модельные и benchmark-артефакты.

## Архитектурная модель

### 1. Распределённый audit pipeline

Аудит выполняется не одной монолитной задачей, а цепочкой отдельных стадий и очередей:

- `audits.pipeline` — orchestration и dispatch;
- `audits.fetch` — загрузка целевой страницы;
- `audits.features` — извлечение признаков;
- `audits.scoring` — rule-based и ML scoring;
- `audits.competitors` — поиск конкурентов;
- `audits.competitor_pages` — fan-out обработка страниц конкурентов;
- `audits.recommendations` — генерация рекомендаций;
- `audits.finalize` — финализация результата.

### 2. Каноническая worker topology

Начиная с `D11`, backend ориентирован на три профиля workers:

- `pipeline` — orchestration и dispatch;
- `network` — `fetch`, `competitors`, `competitor_pages`;
- `cpu_ml` — `features`, `scoring`, `recommendations`, `finalize`.

Эта topology проверяется через readiness и runtime metrics. Single all-queues worker допустим только как debugging fallback.

### 3. Snapshot как источник правды

Начиная с `D13`, backend сохраняет `target_snapshot` — версионированный extraction artifact страницы.

В нём хранятся:

- `requested_url` и `final_url`;
- `status_code` и `response_headers`;
- `redirect_chain`;
- `html` и извлечённый `text`;
- DOM-derived document payload: `title`, `meta_description`, `meta_robots`, `canonical`, `viewport`, `lang`, `hreflang_links`, counts и т.д.

Это позволяет:

- воспроизводимо пересчитывать признаки без повторной загрузки страницы;
- объяснять итоговую оценку из сохранённого артефакта;
- расширять feature-pack без дублирования источников данных.

## D14: Technical SEO Feature Pack

Задача `D14` добавила в backend технический SEO-слой поверх snapshot-пайплайна из `D13`.

### Какие сигналы теперь считаются

Backend теперь извлекает и использует snapshot-derived technical signals:

- HTTP status и признак корректного ответа;
- `redirect_count` и `has_redirect`;
- наличие `canonical` и его соответствие `final_url`;
- `meta robots` и `X-Robots-Tag`;
- `robots_noindex`, `robots_nofollow`, `page_indexable`;
- наличие `viewport`;
- наличие `lang`;
- `hreflang_count` и `hreflang_present`;
- глубину URL;
- количество query-параметров;
- производные technical scores: `redirect_efficiency_score`, `url_hygiene_score`, `technical_metadata_score`, `canonical_signal_score`, `technical_seo_score`.

### Где эти сигналы используются

Технические признаки проходят через три основных потока:

- target page feature extraction;
- competitor page analysis;
- dataset builder для будущей training-схемы.

Также они используются в:

- `score explanation` как дополнительные rule factors;
- рекомендациях пользователя (`TECHNICAL_*` codes);
- сравнении с конкурентами, когда контекст позволяет делать вывод без ложных срабатываний.

### Важное ограничение D14

В `D14` intentionally не менялся `FEATURE_COLUMNS` текущей ML-модели.

Причина простая: опубликованный model artifact всё ещё совместим со старой векторной схемой. Поэтому D14:

- расширяет runtime features и rule explanation;
- не ломает существующий ML artifact;
- оставляет расширение train-time feature schema на следующие задачи (`D17/D18`).

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

## Запуск backend API

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

OpenAPI после запуска доступен по адресу:

- `http://127.0.0.1:8000/docs`

## Полный локальный runtime

Для полного жизненного цикла аудита backend опирается на:

- `Redis` как Celery broker/result backend;
- `SearxNG` как поисковый провайдер;
- запущенные Celery workers с корректной queue-affinity topology.

Рекомендуемый способ поднять весь стек — из корня репозитория:

```powershell
cd E:\codexPROJ\diplom
npm run dev:full
```

## Health endpoints

Backend предоставляет четыре основных health/runtime endpoint'а:

- `GET /health` — legacy healthcheck;
- `GET /health/live` — liveness процесса API;
- `GET /health/ready` — readiness всего distributed stack;
- `GET /health/metrics` — runtime telemetry по очередям, workers и backlog.

### Что проверяет `/health/ready`

- доступность БД;
- доступность Redis;
- наличие активных Celery workers;
- покрытие ожидаемых audit queues;
- доступность `SearxNG`, если используется provider `searxng`.

Если один из обязательных компонентов не готов, endpoint возвращает `503`.

### Что показывает `/health/metrics`

- queue depth по audit queues;
- queue pressure snapshots;
- worker activity и queue coverage;
- worker topology profiles и queue affinity;
- alerts от stuck/backlogged detector;
- агрегированные pipeline counters.

## Audit API

Основные backend endpoints:

- `GET /audits` — список аудитов;
- `POST /audits` — создать новый аудит;
- `GET /audits/{audit_id}` — текущее состояние аудита;
- `GET /audits/{audit_id}/results` — результат, features и score breakdown;
- `GET /audits/{audit_id}/recommendations` — рекомендации;
- `GET /audits/{audit_id}/events` — timeline событий аудита;
- `GET /audits/{audit_id}/events/diagnostics` — диагностика critical path и fan-out.

### Что важно в результатах после D13/D14

При успешном аудите API теперь может отдавать:

- `feature_schema_version`;
- `target_snapshot_summary`;
- expanded `features`, включая technical SEO keys;
- score breakdown с technical rule factors;
- рекомендации с `TECHNICAL_*` codes при наличии обоснованных technical signals.

## Admission control

Начиная с `D10`, `POST /audits` может вернуть `503`, если runtime capacity деградирована:

- очередь `audits.pipeline` backlogged/stuck;
- detector фиксирует длительное ожидание queued/dispatched работ;
- runtime не готов принимать новый audit без усугубления backlog.

Это нормальная часть архитектуры, а не баг API по умолчанию.

## Ручной запуск workers

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

Артефакты сохраняются в:

- `backend/artifacts/benchmarks/<timestamp>-<benchmark-name>/benchmark-report.json`
- `backend/artifacts/benchmarks/<timestamp>-<benchmark-name>/benchmark-report.md`

## Тесты

Полный backend regression:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest
```

Фокусный набор после D14:

```powershell
cd E:\codexPROJ\diplom
backend\.venv\Scripts\python.exe -m pytest \
  backend\tests\test_features.py \
  backend\tests\test_recommendations.py \
  backend\tests\test_audit_pipeline.py \
  backend\tests\test_audits_api.py \
  backend\tests\test_training_pipeline.py
```

## Связанные документы

- `../README.md` — обзор проекта и полный локальный запуск.
- `../AGENTS.md` — operational notes и текущее состояние репозитория.
- `../docs/roadmap/product-development-roadmap.md` — roadmap и backlog.
- `docs/ml_methodology_appendix.md` — ML methodology appendix.
