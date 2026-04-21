# Backend

FastAPI backend для аудитов сайтов, асинхронной обработки и ML scoring.

Полный локальный setup для всего стека описан в [../README.md](../README.md). Этот файл фокусируется на backend-командах, ML pipeline и backend-specific деталях.

Во всех командах ниже `<repo-root>` означает корень этого репозитория.

## Требования

- Python 3.12 или 3.13
- Redis для Celery
- Docker для локального бесплатного `SearxNG`

Перед запуском `npm run searxng:*` убедитесь, что Docker Desktop уже запущен и Docker daemon готов принимать команды.

## Setup

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Локальный SearxNG

Рекомендуемый бесплатный режим для проекта — свой локальный `SearxNG` в Docker. Текущий Docker stack также поднимает `Redis`, который используется как Celery broker/result backend для фоновой обработки аудитов.

Поднять локальный search provider:

```powershell
cd <repo-root>
npm run searxng:up
```

Проверить, что JSON API доступен:

```powershell
cd <repo-root>
npm run searxng:check
```

Остановить контейнеры:

```powershell
cd <repo-root>
npm run searxng:down
```

Локальный instance публикуется как:

- `http://127.0.0.1:8888`
- `redis://127.0.0.1:6379/0`

Конфигурация лежит в:

- [../docker-compose.searxng.yml](../docker-compose.searxng.yml)
- [../infra/searxng/settings.yml](../infra/searxng/settings.yml)

## Run API

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

API будет доступен на `http://127.0.0.1:8000`.

## Health and readiness

Backend теперь различает liveness и настоящую readiness distributed stack:

- `GET /health` - legacy совместимый минимальный healthcheck, возвращает только `{"status":"ok"}`
- `GET /health/live` - liveness процесса API, без проверки внешних зависимостей
- `GET /health/ready` - readiness всего backend/runtime-контура, включая зависимости распределённого пайплайна
- `GET /health/metrics` - runtime telemetry по распределённому пайплайну: backlog очередей, worker activity и агрегированные pipeline counters

`/health/ready` проверяет:

- `database` - SQLAlchemy connection и `SELECT 1`
- `redis` - broker ping через `Redis.from_url(...).ping()`
- `celery_workers` - отвечает ли хотя бы один worker и покрыты ли все expected audit queues
- `serp` - доступен ли `SearxNG JSON API`, если `SERP_PROVIDER=searxng`

`/health/metrics` дополняет readiness операционной телеметрией:

- агрегированные counts аудитов по `status`
- counts активных аудитов по `orchestration_stage`
- оценка backlog по Redis queue depth для всех `AUDIT_QUEUES`
- online workers, их queue coverage и количество `active/reserved/scheduled` задач
- укрупнённая статистика по `AuditCompetitor`

Контракт Redis backlog telemetry сейчас такой: endpoint считает глубину очередей по default Celery Redis list keys и поддерживает `broker_transport_options.global_keyprefix`. Если транспортный формат ключей будет переопределён глубже этого уровня, логику `/health/metrics` нужно обновлять вместе с Celery broker config.

Когда все обязательные компоненты доступны, endpoint возвращает `200` и `status=ready`. Если Redis недоступен, worker не отвечает или не обслуживаются все audit queues, либо недоступен обязательный `SearxNG`, endpoint возвращает `503` и `status=not_ready` с расшифровкой проблемного компонента.

Это важно для текущей stage-based distributed architecture: backend считается готовым только тогда, когда он не просто запущен, а реально может dispatch'ить и выполнять audit stages по всем очередям.

## Run Celery worker

```powershell
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.pipeline,audits.fetch,audits.features,audits.scoring,audits.competitors,audits.competitor_pages,audits.recommendations,audits.finalize --pool=solo
```

Для Windows рекомендуется оставлять `--pool=solo`. Если backend видит Redis, но worker не запущен, новые аудиты будут поставлены в очередь и останутся в `queued`.

Быстрая операционная проверка после старта стека:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/live"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/metrics"
```

Если `/health/ready` возвращает `503`, в payload будет видно, какой именно компонент не готов: `redis`, `celery_workers`, `serp` или `database`.

## Distributed audit pipeline

Аудит больше не исполняется одной длинной фоновой задачей. Runtime-пайплайн разрезан на отдельные stage tasks, чтобы их можно было независимо маршрутизировать, ретраить и масштабировать:

- `app.process_audit` - kickoff и перевод аудита в `processing`
- `app.process_audit_fetch_target` - загрузка целевой страницы
- `app.process_audit_extract_features` - извлечение признаков
- `app.process_audit_score_target` - scoring через rule-based + ML breakdown
- `app.process_audit_collect_competitors` - сбор и сравнение конкурентов
- `app.process_audit_collect_competitor_page` - обработка одной конкурентной страницы как отдельной distributed subtask
- `app.process_audit_aggregate_competitors` - агрегация fan-out результатов конкурентов обратно в audit summary
- `app.process_audit_generate_recommendations` - генерация рекомендаций
- `app.process_audit_finalize` - финализация результата и warning-агрегация

Если Redis/Celery доступны, каждый stage dispatch'ится как отдельная задача. Если брокер недоступен, backend сохраняет ту же бизнес-логику и исполняет стадии inline, что позволяет локально разрабатывать и тестировать пайплайн без отдельного worker-процесса.

Для D2 каждая стадия уже маршрутизируется в отдельную очередь:

- `audits.pipeline`
- `audits.fetch`
- `audits.features`
- `audits.scoring`
- `audits.competitors`
- `audits.competitor_pages`
- `audits.recommendations`
- `audits.finalize`

Это позволяет запускать один универсальный worker на всех очередях или поднимать специализированные worker-процессы под конкретные типы нагрузки. Например, сетевые стадии (`fetch`, `competitors`, `competitor_pages`) и CPU/ML стадии (`features`, `scoring`) теперь можно масштабировать независимо. В D3 конкурентные страницы больше не обрабатываются последовательно внутри одной задачи: каждая SERP-страница стала отдельной distributed subtask с последующей агрегацией.

## Retry-safe orchestration

Для D4 orchestration стал version-aware и retry-safe:

- каждый новый запуск аудита получает `processing_version`;
- stage tasks исполняются только если их `processing_version` совпадает с текущей версией аудита;
- если Celery повторно доставляет stale task старого запуска, backend игнорирует её как `stale_processing_version`;
- `process_audit` умеет безопасно возобновить текущий run и пере-dispatch'ить актуальную стадию без нового сброса состояния;
- fan-out конкурентных subtasks и aggregation защищены от повторного запуска старым orchestration state.

Это важно для распределённого исполнения: при падении worker'а, duplicate delivery или ручном requeue старые задачи не должны перетирать более новый audit run.

Примеры специализированных worker-процессов:

```powershell
# network-heavy worker
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.fetch,audits.competitors,audits.competitor_pages --pool=solo
```

```powershell
# CPU/ML-heavy worker
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.features,audits.scoring,audits.recommendations,audits.finalize --pool=solo
```

```powershell
# lightweight orchestration worker
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.pipeline --pool=solo
```

## Env

Скопируйте [`.env.example`](./.env.example) в `backend/.env`.

Минимальная локальная конфигурация:

```env
SERP_PROVIDER=searxng
SEARXNG_BASE_URL=http://127.0.0.1:8888
SEARXNG_LANGUAGE=ru-RU
SEARCH_TIMEOUT=20
```

Если локальный `SearxNG` временно недоступен, competitor lookup и dataset build могут откатиться на HTML fallback.

## Root commands

Из корня проекта доступны:

```powershell
npm run searxng:up
npm run searxng:check
npm run dev
```

Или одной командой поднять локальный поиск, Redis, frontend, backend и Celery worker:

```powershell
npm run dev:full
```

`npm run dev` поднимает только backend и frontend.

## RU training seeds

Сгенерировать RU commercial seed pack:

```powershell
cd backend
.venv\Scripts\python.exe ..\scripts\generate_training_queries.py
```

Скрипт создаёт:

- `data\training_query_seeds.csv`
- `data\training_queries.txt`

## Dataset build

Обычный прогон:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.dataset_builder `
  --seeds-file data\training_query_seeds.csv `
  --output data\training_dataset.csv `
  --failures-output data\training_failures.csv `
  --checkpoint data\training_dataset.checkpoint.json `
  --overwrite `
  --max-workers 2 `
  --query-delay 1.0
```

Пакетный прогон по 60 seed-ов с автотренировкой после достижения целевого объёма:

```powershell
cd backend
.venv\Scripts\python.exe ..\scripts\run_training_batches.py `
  --seeds-file data\training_query_seeds.csv `
  --dataset data\training_dataset.csv `
  --failures data\training_failures.csv `
  --checkpoint data\training_dataset.checkpoint.json `
  --batch-size 60 `
  --target-rows 1800 `
  --max-workers 2 `
  --query-delay 1.0 `
  --model-output artifacts\page_quality_model.pkl
```

## Training

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.train `
  --dataset data\training_dataset.csv `
  --model-output artifacts\page_quality_model.pkl
```

Во время обучения используется group-based split по `query`, считаются:

- `RMSE`
- `MAE`
- `Spearman mean`
- `NDCG@10`
- `Top-3 hit rate`

Если baseline `RandomForestRegressor` даёт слабую ranking-aware валидацию, pipeline пробует benchmark на `CatBoostRegressor`.

## Runtime scoring

Runtime по-прежнему использует один entrypoint: `predict_score(features)`.

Поведение:

- если задан `SEARXNG_BASE_URL`, поиск идёт через локальный или внешний `SearxNG JSON API`;
- если `SearxNG` недоступен, competitor lookup и dataset build могут откатиться на HTML fallback;
- если есть `artifacts\page_quality_model.pkl` с совместимой схемой features, он становится основной моделью;
- если артефакта нет или schema несовместима, используется bootstrap fallback;
- `score_breakdown.model_info` показывает источник модели, тип, дату обучения и версию датасета.

## Feature inventory

- [docs/ml_feature_inventory.md](./docs/ml_feature_inventory.md)

## Example API requests

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/audits" `
  -ContentType "application/json" `
  -Body '{"query":"ремонт квартир екатеринбург","target_url":"https://example.com","top_n":10}'
```

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "http://127.0.0.1:8000/audits/<AUDIT_ID>/results"
```

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "http://127.0.0.1:8000/audits/<AUDIT_ID>/events"
```

`GET /audits/{audit_id}/events` возвращает persisted timeline исполнения распределённого аудита:

- stage transitions `started/completed/failed/aborted`
- queue dispatch events для переходов между стадиями
- `duration_ms` для завершённых и упавших шагов
- `processing_version`, чтобы различать повторные запуски одного и того же аудита

Поведение endpoint:

- без query-параметров возвращается timeline последнего run этого аудита;
- с `?processing_version=<N>` можно запросить конкретический исторический run;
- response упорядочен по времени записи событий и подходит для построения timeline/debug UI.

## Tests

```powershell
cd backend
.venv\Scripts\python.exe -m pytest
```

## Dataset quality manifest

The RU-commercial dataset workflow now relies on a reproducible manifest-based process instead of an ad hoc CSV snapshot.

What the workflow produces:

- `data\training_query_seeds.csv` — seed pack for RU commercial queries.
- `data\training_queries.txt` — legacy flat list of the same queries.
- `<dataset>.manifest.json` — coverage report and quality gates for the collected dataset.

Seed catalog source of truth:

- 25 commercial categories
- 8 cities
- 200 unique query seeds in total

Generate the seed pack:

```powershell
cd backend
.venv\Scripts\python.exe ..\scripts\generate_training_queries.py
```

Build dataset quality manifest for an existing dataset:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.dataset_quality `
  --dataset data\training_dataset.csv `
  --failures data\training_failures.csv `
  --seeds data\training_query_seeds.csv
```

Run batched collection with quality gates:

```powershell
cd backend
.venv\Scripts\python.exe ..\scripts\run_training_batches.py `
  --seeds-file data\training_query_seeds.csv `
  --dataset data\training_dataset.csv `
  --failures data\training_failures.csv `
  --checkpoint data\training_dataset.checkpoint.json `
  --target-rows 400 `
  --batch-size 40
```

Default production-like quality gates:

- at least 400 successful rows;
- at least 40 unique queries;
- at least 250 unique domains;
- at least 6 categories and 6 cities represented in successful rows;
- at least 20% successful seed coverage;
- at least 5 rows per successful query on average;
- failure rate no higher than 20%.

## Primary model publish

To publish the real primary artifact from the committed RU-commercial dataset snapshot, run:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.publish `
  --dataset data\ru_commercial_dataset.csv `
  --manifest data\ru_commercial_dataset.manifest.json `
  --model-output artifacts\page_quality_model.pkl
```

What this does:

- validates that the dataset manifest is `ready_for_training`;
- trains the primary model from the real local dataset snapshot;
- writes the default runtime artifact to `artifacts\page_quality_model.pkl`;
- embeds `dataset_version`, `trained_at`, `rows_count`, `queries_count` and `domains_count` into the artifact metadata.

Expected runtime effect:

- `score_breakdown.model_info.source` becomes `local_dataset`;
- `score_breakdown.model_info.dataset_version` points to the published RU-commercial snapshot version;
- the scoring pipeline no longer depends on the bootstrap fallback when the published artifact is present.

## Offline model evaluation

Before publishing a new artifact, run offline evaluation on the same dataset split and compare candidate models against the currently published runtime model:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.evaluate `
  --dataset data\ru_commercial_dataset.csv `
  --reference-model artifacts\page_quality_model.pkl
```

What the offline evaluation reports:

- query-grouped train/validation split metadata;
- ranking-aware metrics for each newly trained candidate model;
- the best candidate on the validation set;
- optional comparison against the currently published runtime artifact on the same validation rows.

Key metrics to watch before publish:

- `Spearman mean`
- `NDCG@10`
- `Top-3 hit rate`
- `MAE`
- `RMSE`

Use this step before `python -m app.ml.publish` when you want to validate that the next candidate is not weaker than the currently published primary artifact.

## Artifact versioning and runtime metadata

Published primary models now produce two artifact forms:

- `artifacts\page_quality_model.pkl` — current runtime alias used by the scoring pipeline;
- `artifacts\versions\page_quality_model--<artifact_version>.pkl` — immutable versioned release copy.

Each published artifact also has a public JSON sidecar:

- `artifacts\page_quality_model.metadata.json`
- `artifacts\versions\page_quality_model--<artifact_version>.metadata.json`

The runtime `score_breakdown.model_info` now exposes:

- `artifact_version`
- `artifact_family`
- `trained_at`
- `published_at`
- `dataset_version`
- `dataset_rows`, `dataset_queries`, `dataset_domains`
- `dataset_categories`, `dataset_cities`
- `dataset_failure_rate`
- `dataset_query_coverage_ratio`
- `dataset_attempted_query_coverage_ratio`
- `dataset_manifest_generated_at`
- `metrics_summary`

This makes the active scoring model traceable in runtime: you can see exactly which artifact version is active, what dataset coverage it was trained on and what the key validation metrics were at publish time.
- [docs/ml_methodology_appendix.md](./docs/ml_methodology_appendix.md) - ML methodology, dataset design, evaluation and known limitations for diploma appendix
