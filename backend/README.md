# Backend

Backend проекта `Site Audit` реализован на `FastAPI` и отвечает за серверную часть SEO-аудита: запуск проверки, распределённые вычисления, хранение результата, расчёт признаков, применение ML-модели и генерацию рекомендаций.

## Стек

- Python 3.12 или 3.13;
- FastAPI;
- Pydantic;
- SQLAlchemy;
- SQLite;
- Celery;
- Redis;
- CatBoost;
- scikit-learn;
- sentence-transformers;
- Playwright/httpx для загрузки и анализа страниц.

## Основные зоны ответственности

- API для запуска и просмотра аудитов;
- хранение аудитов, событий и результатов;
- Celery pipeline для длительных задач;
- загрузка целевой страницы и конкурентов;
- извлечение технических, текстовых, коммерческих и семантических признаков;
- применение активной ML-модели;
- расчёт конкурентного score;
- формирование рекомендаций;
- диагностика готовности backend, очередей, workers и модели.

## Локальная подготовка

Из корня проекта:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cd ..
```

На Windows активация окружения выглядит так:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cd ..
```

## Переменные окружения

Пример настроек находится в `backend/.env.example`.

Основные переменные:

- `DATABASE_URL` - путь к SQLite или строка подключения к другой БД;
- `CELERY_BROKER_URL` - Redis broker;
- `CELERY_RESULT_BACKEND` - Redis result backend;
- `SERP_PROVIDER` - поисковый провайдер;
- `SEARXNG_BASE_URL` - адрес локального SearXNG;
- `CORS_ALLOW_ORIGINS` - разрешённые frontend-origin.

Реальный `.env` не должен попадать в GitHub.

## Распределённые вычисления

Аудит выполняется не одним монолитным процессом. Backend ставит стадии в очереди Celery, а workers выполняют их отдельно.

Основные очереди:

- `audits.pipeline` - управление стадиями;
- `audits.fetch` - загрузка целевой страницы;
- `audits.heavy_analysis` - тяжёлый анализ snapshot;
- `audits.features` - извлечение признаков;
- `audits.semantic` - семантические вычисления;
- `audits.scoring` - ML scoring;
- `audits.competitors` - получение конкурентов;
- `audits.competitor_pages` - параллельный анализ конкурентов;
- `audits.recommendations` - рекомендации;
- `audits.finalize` - финализация результата.

Worker-профили описаны в `backend/app/worker_topology_profiles.json`.

## Активная модель

Для обычного запуска нужна только активная runtime-модель:

- `backend/artifacts/page_quality_model.pkl`;
- `backend/artifacts/page_quality_model.metadata.json`.

Обучающие датасеты, benchmark-отчёты и исследовательские артефакты не требуются для запуска backend. Они должны храниться локально, а не в публичном GitHub-репозитории.

## Диагностика

Полезные endpoints:

- `/health/live` - backend запущен;
- `/health/ready` - стек готов к работе;
- `/health/metrics` - состояние очередей и workers;
- `/health/model` - сведения об активной ML-модели;
- `/health/model/monitoring` - агрегированная информация по использованию модели.

## Тесты

Из папки `backend`:

```bash
source .venv/bin/activate
pytest
```

На Windows:

```powershell
.\.venv\Scripts\Activate.ps1
pytest
```
