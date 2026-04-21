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

## Run Celery worker

```powershell
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits --pool=solo
```

Для Windows рекомендуется оставлять `--pool=solo`. Если backend видит Redis, но worker не запущен, новые аудиты будут поставлены в очередь и останутся в `queued`.

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

## Tests

```powershell
cd backend
.venv\Scripts\python.exe -m pytest
```

## Dataset quality manifest

`task 6` now relies on a reproducible RU-commercial dataset workflow instead of an ad hoc CSV snapshot.

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
