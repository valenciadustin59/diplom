# Site Audit

Веб-приложение для автоматизированного SEO-аудита посадочных страниц по поисковому запросу. Пользователь указывает запрос и URL своей страницы, после чего система находит конкурентов, собирает признаки страницы, считает ML score, сравнивает результат с SERP и формирует рекомендации.

## Что находится в репозитории

- `backend/` — FastAPI API, SQLite, Celery orchestration и ML scoring pipeline
- `frontend/` — React + TypeScript интерфейс для запуска аудитов и просмотра результатов
- `docker-compose.searxng.yml` — локальный Docker stack для `SearxNG` и `Redis`
- `scripts/` — root-level dev scripts и утилиты локальной разработки
- `docs/roadmap/` — roadmap и GitHub backlog дальнейшего развития

## Distributed Backlog Status

Для текущего этапа диплома каноническим backlog считается не старый product backlog, а distributed sequence `D1-D12`.

Уже выполнено:

- `D1` — stage-based decomposition audit pipeline
- `D2` — routing стадий по отдельным Celery queues
- `D3` — distributed fan-out по competitor pages
- `D4` — retry-safe / version-aware orchestration
- `D5` — `health/live` и `health/ready`
- `D6` — `health/metrics` и runtime telemetry
- `D7` — persistent audit event log и stage duration telemetry
- `D8` — audit timeline diagnostics API и critical-path breakdown
- `D9` — queue pressure snapshots и stuck/backlogged execution detector
- `D10` — admission control и scheduling guards при деградированном runtime capacity

Ещё предстоит:

- `D11` — worker topology profiles и queue affinity validation
- `D12` — benchmark/reporting workflow для демонстрации distributed runtime в дипломе

Подробный статус и последовательность находятся в [docs/roadmap/product-development-roadmap.md](./docs/roadmap/product-development-roadmap.md).

## Требования

- `Python 3.12` или `3.13`
- `Node.js 20+` и `npm`
- `Docker Desktop` или совместимый Docker runtime

Перед запуском `npm run dev:full` и `npm run searxng:*` убедитесь, что Docker Desktop уже запущен и Docker daemon успел подняться.

Во всех командах ниже `<repo-root>` означает корень этого репозитория.

## Рекомендуемый режим: полный локальный стек

Этот режим рекомендуется для обычной разработки и демонстрации диплома. Он поднимает поиск, Redis, backend, frontend и Celery worker.

### 1. Установить root и frontend зависимости

```powershell
cd <repo-root>
npm install
npm --prefix frontend install
```

### 2. Подготовить backend окружение

```powershell
cd <repo-root>
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
copy .env.example .env
```

Если используется `Python 3.13`, команда установки остаётся той же, если текущий `pyproject.toml` её допускает.

### 3. Запустить полный локальный стек

```powershell
cd <repo-root>
npm run dev:full
```

Команда делает следующее:

- поднимает Docker services `diplom-searxng` и `diplom-searxng-redis`
- проверяет доступность `SearxNG` по `http://127.0.0.1:8888`
- запускает backend API на свободном локальном порту, начиная с `8000`
- запускает frontend и прокидывает в него актуальный `VITE_API_URL`
- запускает Celery worker для stage-based audit queues

Если `backend/.env` отсутствует, root dev script сам подставляет локальные dev defaults для `SEARXNG_BASE_URL`, `CELERY_BROKER_URL` и `CELERY_RESULT_BACKEND`, чтобы полный стек не запускался в деградированном режиме.

На Windows worker автоматически стартует с `--pool=solo`, потому что это самый надёжный режим для локального запуска Celery.

## Ручной запуск по частям

Этот режим удобен, если нужно отдельно перезапускать только один компонент.

### Инфраструктура: SearxNG и Redis

```powershell
cd <repo-root>
npm run searxng:up
npm run searxng:check
```

После запуска доступны:

- `SearxNG`: `http://127.0.0.1:8888`
- `Redis`: `redis://127.0.0.1:6379/0`

### Backend API

```powershell
cd <repo-root>
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Celery worker

```powershell
cd <repo-root>
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.pipeline,audits.fetch,audits.features,audits.scoring,audits.competitors,audits.competitor_pages,audits.recommendations,audits.finalize --pool=solo
```

Для Linux/macOS флаг `--pool=solo` можно убрать, но для Windows его лучше оставить.

Если нужно явно разделить нагрузку между worker-процессами, можно поднимать их по группам очередей:

```powershell
cd <repo-root>
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.fetch,audits.competitors,audits.competitor_pages --pool=solo
```

```powershell
cd <repo-root>
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.features,audits.scoring,audits.recommendations,audits.finalize --pool=solo
```

```powershell
cd <repo-root>
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.pipeline --pool=solo
```

### Frontend

```powershell
cd <repo-root>
cd frontend
set VITE_API_URL=http://127.0.0.1:8000
npm run dev
```

## Настройки окружения backend

Минимальная локальная конфигурация описана в [`backend/.env.example`](./backend/.env.example):

```env
APP_NAME=Site Audit API
APP_ENV=development
DATABASE_URL=sqlite:///./audit.db
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
SERP_PROVIDER=searxng
SEARXNG_BASE_URL=http://127.0.0.1:8888
SEARXNG_LANGUAGE=ru-RU
SEARCH_TIMEOUT=20
```

Если `SEARXNG_BASE_URL` не настроен или `SearxNG` временно недоступен, часть search/competitor сценариев может деградировать. Для нормального полного audit lifecycle рекомендуется держать `SearxNG`, `Redis` и Celery worker запущенными одновременно.

## Что проверить после запуска

1. Открыть `http://127.0.0.1:8888` и убедиться, что `SearxNG` отвечает.
2. Открыть `http://127.0.0.1:8000/docs` или порт, который вывел root dev script.
3. Открыть `http://127.0.0.1:8000/health/live` и убедиться, что backend process жив.
4. Открыть `http://127.0.0.1:8000/health/ready` и убедиться, что distributed stack вернул `status=ready`.
5. Открыть `http://127.0.0.1:8000/health/metrics` и убедиться, что backend показывает queue depth, worker activity и pipeline counters.
6. Открыть frontend URL из `vite` output.
7. Создать аудит и убедиться, что worker обрабатывает задачу, а статус не остаётся в `queued`.

`/health/ready` теперь проверяет не только сам API, но и реальные зависимости распределённого контура:

- базу данных;
- Redis broker/result backend;
- активные Celery worker'ы;
- покрытие всех expected audit queues;
- доступность `SearxNG`, если выбран provider `searxng`.

Если endpoint вернул `503`, это значит, что стек не готов к полноценному distributed audit execution, даже если `FastAPI` процесс уже поднялся.

Начиная с `D10`, backend использует эти runtime-сигналы не только для observability, но и для управления нагрузкой. Если `POST /audits` видит, что `audits.pipeline` уже `backlogged`/`stuck` или detector фиксирует слишком долгую очередь ожидающих запусков, API возвращает `503` и не создаёт новый audit. Для уже исполняющихся стадий orchestration, наоборот, предпочитает `inline`-fallback вместо дальнейшего раздувания деградировавшей очереди.

## Разница между `npm run dev` и `npm run dev:full`

- `npm run dev` запускает только backend и frontend.
- `npm run dev:full` запускает `SearxNG`, `Redis`, backend, frontend и Celery worker.

Если `Redis` уже доступен, но worker не запущен или целевые очереди не обслуживаются, новые аудиты могут быть отклонены сразу с `503` по admission guard `D10`, а не оставлены молча в `queued`. Для полноценной локальной работы используйте именно `npm run dev:full` или запускайте worker отдельной командой.

## Проверки

### Backend tests

```powershell
cd <repo-root>
cd backend
.venv\Scripts\python.exe -m pytest
```

### Frontend build

```powershell
cd <repo-root>
npm run build
```

## Полезные ссылки

- [backend/README.md](./backend/README.md) — backend-specific команды, training pipeline и ML workflow
- [AGENTS.md](./AGENTS.md) — operational instructions для агентов и разработчиков
- [docs/roadmap/product-development-roadmap.md](./docs/roadmap/product-development-roadmap.md) — roadmap и GitHub backlog
- [backend/docs/ml_methodology_appendix.md](./backend/docs/ml_methodology_appendix.md) - appendix-ready description of ML methodology, evaluation and limitations
