# Backend

Backend проекта `Site Audit` построен на `FastAPI` и отвечает за полный серверный цикл SEO-аудита:

- создание и хранение аудитов;
- распределённую обработку stage-based pipeline через `Celery`;
- получение и нормализацию данных по целевой странице и конкурентам;
- извлечение контентных, семантических, технических, commercial и trust-признаков;
- ML scoring и формирование score breakdown;
- генерацию приоритетных рекомендаций;
- runtime telemetry, readiness и диагностику распределённого исполнения.

Корневой сценарий запуска всего проекта описан в `../README.md`. Этот файл сфокусирован на backend-архитектуре, API и распределённом runtime.

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
- `app/heavy_analysis.py` — snapshot-based тяжёлые анализаторы для structured data, mobile/rendering и performance proxy.
- `app/parser.py` — загрузка страниц, fallback-стратегии, snapshot/extraction artifact и DOM-derived document payload.
- `app/features.py` — контентные, семантические, technical SEO и commercial/trust features.
- `app/recommendations.py` — recommendation engine.
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
- `audits.heavy_analysis` — target heavy analysis и competitor semantic/ML analysis;
- `audits.features` — извлечение признаков;
- `audits.scoring` — rule-based и ML scoring;
- `audits.competitors` — поиск конкурентов;
- `audits.competitor_pages` — fan-out обработка страниц конкурентов;
- `audits.recommendations` — генерация рекомендаций;
- `audits.finalize` — финализация результата.

### 2. Каноническая worker topology

Начиная с `D20`, backend ориентирован на четыре профиля workers:

- `pipeline` — orchestration и dispatch;
- `network` — `fetch`, `competitors`, `competitor_pages`;
- `heavy_analysis` — snapshot-based тяжёлые анализаторы и competitor semantic/ML scoring;
- `cpu_ml` — `features`, `scoring`, `recommendations`, `finalize`.

Эта topology проверяется через readiness и runtime metrics. Single all-queues worker допустим только как debugging fallback.

### 3. Snapshot как источник правды

Начиная с `D13`, backend сохраняет `target_snapshot` — версионированный extraction artifact страницы.

В нём хранятся:

- `requested_url` и `final_url`;
- `status_code` и `response_headers`;
- `redirect_chain`;
- `html` и извлечённый `text`;
- DOM-derived document payload: `title`, `meta_description`, `meta_robots`, `canonical`, `viewport`, `lang`, `hreflang_links`, `links`, `button_texts`, heading texts и структурные counts.

Это позволяет:

- воспроизводимо пересчитывать признаки без повторной загрузки страницы;
- объяснять итоговую оценку из сохранённого артефакта;
- расширять feature-pack без дублирования источников данных.

### 4. Heavy Analysis Isolation (`D20`)

`D20` выносит тяжёлые analyzer-задачи из сетевых и lightweight CPU очередей в отдельную очередь `audits.heavy_analysis`.

Что изолировано:

- target stage `heavy_analysis` после fetch и до feature extraction;
- snapshot-based анализ structured data, mobile readiness, rendering/JS dependency risk и performance proxy;
- competitor flow split: `competitor_pages` делает только network fetch и сохраняет snapshot, а `competitor_analysis` выполняет semantic feature extraction и ML scoring в heavy queue.

Практический эффект для distributed runtime:

- сетевой worker больше не блокируется CPU/semantic анализом competitors;
- `GET /health/metrics` отдельно показывает pressure для `audits.heavy_analysis`;
- admission guard может отклонить новый audit при backlogged/stuck heavy queue;
- benchmark report содержит `Topology Profiles` и признак `Heavy Analysis Isolated`.

## D14: Technical SEO Feature Pack

Задача `D14` добавила технический SEO-слой поверх snapshot-пайплайна из `D13`.

Backend теперь извлекает и использует:

- HTTP status и признак корректного ответа;
- `redirect_count`, `has_redirect`;
- наличие `canonical` и его соответствие `final_url`;
- `meta robots` и `X-Robots-Tag`;
- `robots_noindex`, `robots_nofollow`, `page_indexable`;
- наличие `viewport`, `lang`, `hreflang`;
- глубину URL и количество query-параметров;
- производные technical scores: `redirect_efficiency_score`, `url_hygiene_score`, `technical_metadata_score`, `canonical_signal_score`, `technical_seo_score`.

Эти сигналы проходят через:

- target page feature extraction;
- competitor page analysis;
- rule-based score explanation;
- recommendation layer.

## D15: Commercial And Trust Feature Pack

Задача `D15` расширила snapshot-derived feature layer для коммерческих landing pages.

### Какие сигналы теперь считаются

Backend теперь извлекает и использует commercial/trust signals:

- `phone_present`, `phone_count`;
- `email_present`;
- `address_present`;
- `business_hours_present`;
- `price_present`, `currency_present`;
- `delivery_info_present`, `payment_info_present`;
- `warranty_info_present`, `returns_info_present`;
- `reviews_present`, `rating_present`;
- `faq_present`;
- `cta_present`, `cta_count`;
- `messenger_present`;
- `value_proposition_present`;
- `legal_requisites_present`, `company_identity_present`;
- агрегаты `contact_options_score`, `commercial_signals_score`, `trust_signals_score`, `commercial_trust_score`.

### Где эти сигналы используются

Новые D15 signals проходят через:

- target page feature extraction;
- competitor analysis;
- dataset builder для будущего retraining;
- recommendation layer (`COMMERCIAL_*` и `TRUST_*` codes);
- score explanation как дополнительные rule factors.

### Ограничение D15

Как и в `D14`, задача сознательно не меняет текущий `FEATURE_COLUMNS` production-model schema.

Причина: опубликованный ML artifact должен оставаться совместимым с текущим runtime. Поэтому D15:

- делает новые signals доступными продукту уже сейчас;
- экспортирует их в dataset builder для следующей волны retraining;
- сохраняет совместимость текущих `train.py` и `publish.py`, потому что они по-прежнему используют только `FEATURE_COLUMNS` и игнорируют вспомогательные D14/D15 dataset columns;
- не ломает текущий model artifact до задач `D17/D18`.

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

Короткий эквивалент:

```powershell
cd E:\codexPROJ\diplom
npm start
```

Frontend dev server при запуске через root scripts явно привязывается к `127.0.0.1`, поэтому сайт должен открываться по адресу:

- `http://127.0.0.1:5173/`

Перед демонстрацией frontend production bundle можно проверить командой:

```powershell
cd E:\codexPROJ\diplom
npm run site:check
```

Она выполняет `npm run build` и проверяет `frontend/dist/index.html`, подключённые JS/CSS assets и ключевые тексты интерфейса.

## Health endpoints

Backend предоставляет четыре основных health/runtime endpoint'а:

- `GET /health` — legacy healthcheck;
- `GET /health/live` — liveness процесса API;
- `GET /health/ready` — readiness всего distributed stack;
- `GET /health/metrics` — runtime telemetry по очередям, workers и backlog.

Если один из обязательных компонентов не готов, `GET /health/ready` возвращает `503`.

`GET /health/metrics` показывает queue depth, queue pressure, worker activity, queue coverage, topology validation и runtime alerts.

## Audit API

Основные backend endpoints:

- `GET /audits` — список аудитов;
- `POST /audits` — создать новый аудит;
- `GET /audits/{audit_id}` — текущее состояние аудита;
- `GET /audits/{audit_id}/results` — результат, features и score breakdown;
- `GET /audits/{audit_id}/recommendations` — рекомендации;
- `GET /audits/{audit_id}/events` — timeline событий аудита;
- `GET /audits/{audit_id}/events/diagnostics` — диагностика critical path и fan-out.

### Что важно в результатах после D13-D21

При успешном аудите API теперь может отдавать:

- `feature_schema_version`;
- `target_snapshot_summary`;
- `heavy_analysis` с versioned analyzer payload и proxy features;
- expanded `features`, включая technical SEO и commercial/trust keys;
- score breakdown с technical/commercial/trust rule factors;
- рекомендации с `TECHNICAL_*`, `COMMERCIAL_*` и `TRUST_*` codes.

После `D21` frontend использует эти payloads вместе с `GET /audits/{audit_id}/events/diagnostics`, чтобы собрать единый audit report/export dashboard без повторного backend-анализа страницы.

## Admission control

Начиная с `D10`, `POST /audits` может вернуть `503`, если runtime capacity деградирована.

Это нормальная часть архитектуры, а не баг API по умолчанию.

После `D20` admission учитывает не только pipeline backlog, но и состояние `audits.heavy_analysis`: если heavy queue `backlogged` или `stuck`, новый audit отклоняется с кодом `heavy_analysis_queue_capacity_exhausted`.

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

После `D20` markdown/JSON report дополнительно содержит section `Topology Profiles`: configured worker profiles, queue-to-profile map, per-profile queue pressure counts и флаг изоляции heavy analyzers.

Артефакты сохраняются в:

- `backend/artifacts/benchmarks/<timestamp>-<benchmark-name>/benchmark-report.json`
- `backend/artifacts/benchmarks/<timestamp>-<benchmark-name>/benchmark-report.md`

## Тесты

Полный backend regression:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest
```

Фокусный набор для distributed runtime и D20:

```powershell
cd E:\codexPROJ\diplom
backend\.venv\Scripts\python.exe -m pytest \
  backend\tests\test_audit_pipeline.py \
  backend\tests\test_audits_api.py \
  backend\tests\test_health_api.py \
  backend\tests\test_distributed_benchmark.py \
  backend\tests\test_worker_topology.py
```

Отдельно для совместимости training/publish workflow после D15 полезно проверить:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest tests\test_training_pipeline.py tests\test_model_publish.py tests\test_model_evaluate.py
```

Этот набор подтверждает, что CSV с новыми auxiliary columns из dataset builder по-прежнему совместим с текущим retraining-пайплайном.

## Связанные документы

- `../README.md` — обзор проекта и полный локальный запуск.
- `../AGENTS.md` — operational notes, текущий backlog и GitHub issues `D22-D26` (`#41-#45`).
- `../docs/roadmap/product-development-roadmap.md` — стратегический roadmap после `D21`, включая frontend/product wave без изменения ядра backend-анализа.
- `docs/ml_methodology_appendix.md` — ML methodology appendix.

## D16: SERP-Relative And Intent-Aware Features

`D16` добавляет поверх текущего audit pipeline сравнительный слой:

- определение и сохранение `query_intent` в `Audit` уже при создании аудита;
- intent-alignment признаки для target и competitor pages;
- SERP-relative gaps, median gaps, percentiles и z-scores по ключевым группам сигналов;
- `query_intent` в API payloads и `serp_relative_factors` в `score_breakdown`;
- новые relative и intent-aware recommendation codes.

Ограничения `D16`:

- не меняет `FEATURE_COLUMNS`;
- не требует немедленного retraining;
- не пересчитывает уже полученный audit score на competitor aggregation;
- корректно работает при неполном competitor set через fallback relative-context markers.

## D17: Dataset V2 And Labeling Pipeline

`D17` переводит training data workflow из режима одного неявного CSV в воспроизводимый versioned bundle.

Что добавлено:

- `baseline-v1` — замороженная копия текущего production-like dataset в `backend/data/dataset_versions/baseline-v1/`;
- `dataset-v2` — отдельный versioned bundle в `backend/data/dataset_versions/dataset-v2/`;
- raw extraction artifacts per row через snapshot-артефакты `D13`;
- hybrid labeling contract: `weak_target_score`, `expert_target_score`, `target_score`, `label_source`;
- version-aware manifest с информацией о label provenance, artifacts coverage и baseline lineage;
- persisted `group_by_query` split в отдельном `split.json`.

### Новый dataset contract

Строка dataset v2 теперь хранит:

- `dataset_version`;
- `feature_schema_version` и `extraction_artifact_version`;
- `label_schema_version`, `label_source`, `weak_target_score`, `expert_target_score`, `target_score`;
- `artifact_path`, `artifact_sha1`, `artifact_size_bytes`.

Это позволяет показать для диплома не просто "CSV для обучения", а воспроизводимую data pipeline с происхождением данных, версией схемы и сохранёнными артефактами extraction layer.

### Seed bundle `dataset-v2`

В репозитории уже подготовлен seed bundle:

- `backend/data/dataset_versions/dataset-v2/seeds.csv`
- `backend/data/dataset_versions/dataset-v2/expert_labels.csv`
- `backend/data/dataset_versions/dataset-v2/dataset.json`

Он задаёт `450` запросов:

- `25` категорий;
- `8` городов;
- `2` intent-типа;
- `4` query pattern templates.

### Сборка dataset v2

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

### Manifest и split

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
