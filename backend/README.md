# Backend

FastAPI backend для аудитов сайтов, асинхронной обработки и ML scoring.

## Требования

- Python 3.12 или 3.13
- Redis для Celery
- Docker для локального бесплатного `SearxNG`

## Setup

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Локальный SearxNG

Рекомендуемый бесплатный режим для проекта — свой локальный `SearxNG` в Docker.

Поднять локальный search provider:

```powershell
cd E:\codexPROJ\diplom
npm run searxng:up
```

Проверить, что JSON API доступен:

```powershell
cd E:\codexPROJ\diplom
npm run searxng:check
```

Остановить контейнеры:

```powershell
cd E:\codexPROJ\diplom
npm run searxng:down
```

Локальный instance публикуется как:

- `http://127.0.0.1:8888`

Конфигурация лежит в:

- [docker-compose.searxng.yml](/E:/codexPROJ/diplom/docker-compose.searxng.yml)
- [infra/searxng/settings.yml](/E:/codexPROJ/diplom/infra/searxng/settings.yml)

## Run API

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

API будет доступен на `http://127.0.0.1:8000`.

## Env

Скопируйте [backend/.env.example](/E:/codexPROJ/diplom/backend/.env.example) в `backend/.env`.

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

Или одной командой поднять локальный поиск и затем frontend + backend:

```powershell
npm run dev:full
```

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

- [docs/ml_feature_inventory.md](/E:/codexPROJ/diplom/backend/docs/ml_feature_inventory.md)

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
