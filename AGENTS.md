# AGENTS

Этот файл описывает фактическое состояние репозитория `E:\codexPROJ\diplom` и служит стартовой инструкцией для любого агента или разработчика.

## Обязательные ограничения работы

- Работать только внутри `E:\codexPROJ\diplom`.
- Не создавать временные директории, junction/symlink, вспомогательные клоны и файлы на других дисках или вне репозитория.
- Если для автоматизации нужен временный скрипт, создавать его только внутри репозитория и удалять после использования.
- Перед закрытием GitHub issue убедиться, что реализация закоммичена, запушена и подтверждена проверками.
- Для задач из GitHub backlog придерживаться порядка: реализация -> тесты -> commit -> push -> комментарий/закрытие issue.

## Текущее состояние

Проект уже инициализирован и состоит из двух основных частей:

- `backend/` — FastAPI backend, SQLite, Celery, ML scoring pipeline, training pipeline
- `frontend/` — React + TypeScript интерфейс для запуска аудитов и просмотра результатов

Проект решает задачу автоматизированного SEO-аудита посадочных страниц по поисковому запросу. Пользователь указывает запрос и URL своего сайта, после чего система:

- находит конкурентные страницы в выдаче
- анализирует целевую страницу и конкурентов
- вычисляет score качества страницы на основе ML и признаков страницы
- строит сравнение с конкурентами
- формирует рекомендации с приоритетами

Также в репозитории есть:

- `scripts/` — служебные скрипты, включая генерацию RU training seed pack и batch workflow
- `plans/` — только ExecPlan-документы
- `docs/roadmap/` — roadmap и продуктовые планы, не относящиеся к ExecPlans
- `PLANS.md` — канонические правила для ExecPlans

## Текущий статус backlog

На текущий момент уже реализованы и должны сохраняться без регрессий следующие задачи:

- GitHub issue `#1` — стабилизированы переходы статусов аудита и обработка повторных запусков/ошибок
- GitHub issue `#2` — добавлено структурированное логирование шагов аудита
- GitHub issue `#3` — добавлены backend integration tests для полного жизненного цикла аудита через API

Следующие известные задачи backlog:

- GitHub issue `#4` — документация полного локального setup
- GitHub issue `#5` — отображение причин ошибок аудита во frontend workspace

## Стек проекта

- Backend: `Python 3.12+`, `FastAPI`, `Pydantic v2`, `SQLAlchemy 2`
- Async/background: `Celery`, `Redis`
- Search provider: `SearxNG` JSON API с HTML fallback
- ML: `scikit-learn`, `sentence-transformers`, `CatBoost` как benchmark fallback для обучения
- Хранение: `SQLite` для MVP
- Frontend: `React`, `TypeScript`, `Vite`

## Ключевые команды

### Backend setup

```powershell
cd E:\codexPROJ\diplom\backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Примечание: текущая локальная `.venv` в рабочем каталоге уже запускается на `Python 3.13.5`, и `pyproject.toml` допускает `3.12` и `3.13`.

### Backend run

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Local SearxNG up

```powershell
cd E:\codexPROJ\diplom
npm run searxng:up
```

Команда поднимает локальные `SearxNG` и `Redis` из `docker-compose.searxng.yml`.

### Local SearxNG check

```powershell
cd E:\codexPROJ\diplom
npm run searxng:check
```

### Local SearxNG down

```powershell
cd E:\codexPROJ\diplom
npm run searxng:down
```

### Backend tests

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest
```

### RU training seed generation

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe ..\scripts\generate_training_queries.py
```

Скрипт создаёт:

- `backend/data/training_query_seeds.csv`
- `backend/data/training_queries.txt`

### ML dataset build

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m app.ml.dataset_builder `
  --seeds-file data\training_query_seeds.csv `
  --output data\training_dataset.csv `
  --failures-output data\training_failures.csv `
  --checkpoint data\training_dataset.checkpoint.json `
  --overwrite `
  --max-workers 2 `
  --query-delay 1.0
```

### Batch dataset build + train

```powershell
cd E:\codexPROJ\diplom\backend
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

### ML training

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m app.ml.train `
  --dataset data\training_dataset.csv `
  --model-output artifacts\page_quality_model.pkl
```

### Frontend run

```powershell
cd E:\codexPROJ\diplom\frontend
npm install
npm run dev
```

### Root convenience run

```powershell
cd E:\codexPROJ\diplom
npm run dev
```

Команда поднимает только backend и frontend.

### Root full stack run

```powershell
cd E:\codexPROJ\diplom
npm run dev:full
```

Команда поднимает `SearxNG`, `Redis`, backend, frontend и Celery worker.

## Где искать важные части

- `README.md` — полный локальный setup для backend, frontend, Redis и SearxNG
- `backend/app/main.py` — вход в API
- `docker-compose.searxng.yml` — локальный Docker stack для бесплатного `SearxNG`
- `infra/searxng/settings.yml` — конфигурация локального `SearxNG`
- `backend/app/tasks.py` — основной audit pipeline
- `backend/app/audit_status.py` — допустимые переходы статусов аудита
- `backend/app/features.py` — feature engineering
- `backend/app/semantic.py` — sentence-transformers semantic features
- `backend/app/serp.py` — SearxNG-backed provider для выдачи
- `backend/app/competitors.py` — competitor lookup и competitor analysis
- `backend/app/ml/model.py` — runtime scoring, fallback и `model_info`
- `backend/app/ml/dataset_builder.py` — сбор CSV-датасета с seed CSV, failures и checkpoint
- `backend/app/ml/train.py` — обучение и сохранение модели
- `backend/docs/ml_feature_inventory.md` — текущий список ML-признаков
- `scripts/generate_training_queries.py` — генерация RU commercial seed pack
- `scripts/run_training_batches.py` — пакетный workflow для массового dataset build
- `backend/tests/test_audit_pipeline.py` — тесты pipeline-логики и переходов статусов
- `backend/tests/test_audits_api.py` — API lifecycle tests для completed/failed аудитов

## Правила кода

- не смешивать несколько способов сделать одно и то же без причины
- backend-схемы запросов и ответов держать явными
- ML-часть держать разделённой на:
  - feature engineering
  - serp provider
  - dataset build
  - training
  - inference
- все фоновые задачи должны быть idempotent и обновлять статус аудита
- нельзя менять контракт `POST /audits` ради тестов: endpoint должен создавать аудит и возвращать запись в `queued`, а результат проверяется последующими `GET`
- при ошибке нельзя оставлять stale derived data: `score`, `features`, `recommendations`, comparison и другие производные поля должны очищаться или пересоздаваться консистентно
- если меняются команды запуска, тестов или обучения, обновлять этот файл
- для крупных фич и значимых рефакторингов использовать ExecPlan по правилам `PLANS.md`

## GitHub workflow

Если работа ведётся по GitHub issues/tasks, используйте следующий процесс:

1. Прочитать связанный код и подтвердить контракт текущего поведения.
2. Реализовать задачу без побочных изменений вне согласованного scope.
3. Запустить релевантные тесты и, если нужно, сборку frontend.
4. Проверить `git status`, не захватывая артефакты вроде `audit.db` и `catboost_info/`.
5. Создать отдельный commit по задаче и запушить его.
6. Добавить комментарий в соответствующий GitHub issue с кратким итогом и SHA commit.
7. Закрыть issue только после успешного push и локальной проверки.

Если issue связан с уже реализованными задачами `#1-#3`, новые изменения не должны ломать:

- явную модель переходов статусов аудита
- step-level logging в pipeline
- backend API lifecycle tests

## Предпочтительные инструменты локального анализа

Перед тем как читать большие файлы целиком, агент должен по возможности использовать локальные CLI-инструменты:

- `ast-index`
- `ast-grep`
- `rg`
- `fd`
- `jq`
- `yq`
- `rtk`

Правило:

- сначала пробовать структурный или быстрый локальный поиск
- читать только нужные фрагменты файлов
- не тащить в контекст большие файлы без необходимости

## ExecPlans

Для сложных задач и крупных рефакторингов обязательны ExecPlans.

Канонические правила находятся в [PLANS.md](./PLANS.md).

Актуальный ML ExecPlan для training pipeline:

- [plans/real-ml-training-pipeline.md](./plans/real-ml-training-pipeline.md)

## Проверка перед крупными изменениями

Минимальный чек:

1. Зависимости ставятся без ошибок.
2. Backend поднимается локально.
3. `pytest` проходит.
4. Для заметных изменений в ML обновлены команды и документация.
5. Если менялся training pipeline, обновлены `README.md`, `AGENTS.md` и соответствующий ExecPlan.
6. Для задач по backend pipeline проходят как минимум:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest backend\tests\test_audit_pipeline.py
.venv\Scripts\python.exe -m pytest backend\tests\test_audits_api.py
```

7. Для задач по frontend проходит как минимум:

```powershell
cd E:\codexPROJ\diplom\frontend
npm run build
```
