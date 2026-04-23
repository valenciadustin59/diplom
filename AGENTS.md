# AGENTS

Этот файл описывает текущее состояние репозитория и служит стартовой инструкцией для любого агента или разработчика, который начинает работу в проекте.

Текущий корень репозитория:

- `E:\codexPROJ\diplom`

## Обязательные ограничения

- Работать только внутри этого репозитория.
- Не создавать временные директории, симлинки, клоны и рабочие файлы вне `E:\codexPROJ\diplom`.
- Если нужен временный вспомогательный скрипт, создавать его только внутри репозитория и удалять после использования.
- Не закрывать GitHub issue до тех пор, пока реализация не проверена, не закоммичена и не запушена.
- Для backlog-задач придерживаться порядка: реализация -> проверки -> commit -> push.

## Кратко о проекте

Проект автоматизирует SEO-аудит посадочных страниц по поисковому запросу.

Пользователь задаёт:

- поисковый запрос;
- URL своей страницы.

Система после этого:

- находит конкурентов в выдаче;
- анализирует целевую страницу и конкурентов;
- извлекает признаки;
- вычисляет ML score;
- сравнивает результат с конкурентами;
- формирует рекомендации с приоритетами.

Проект должен убедительно соответствовать теме диплома: web-приложение машинного обучения на основе распределённых вычислений.

## Структура репозитория

- `backend/` — FastAPI backend, SQLite, Celery runtime, ML scoring, training workflow.
- `frontend/` — React + TypeScript интерфейс.
- `scripts/` — dev scripts, benchmark runner, training utilities.
- `docs/roadmap/` — roadmap и backlog.
- `plans/` и `PLANS.md` — вспомогательные planning-документы.
- `docker-compose.searxng.yml` — локальный стек `SearxNG + Redis`.

## Текущий backlog

Старые product issues `#1-#25` больше не считаются активным backlog source of truth. Они остаются только как архив истории проекта.

Канонический backlog текущего этапа — distributed sequence `D1-D12`.

Статус:

- `D1` — stage-based decomposition audit pipeline
- `D2` — per-stage Celery queues and routing
- `D3` — distributed fan-out по competitor pages
- `D4` — retry-safe / version-aware orchestration
- `D5` — `health/live` и `health/ready`
- `D6` — `health/metrics` и runtime telemetry
- `D7` — persistent audit event log
- `D8` — audit timeline diagnostics API
- `D9` — queue pressure snapshots и stuck/backlogged detector
- `D10` — admission control и scheduling guards
- `D11` — worker topology profiles и queue-affinity validation
- `D12` — benchmark/reporting workflow для distributed runtime evidence

Итог: backlog `D1-D12` завершён.

Если ниже в каких-либо старых документах встречаются упоминания о незавершённом `D12`, считать их историческими и неактуальными.

## Архитектурные ориентиры

### Backend

- `FastAPI`
- `SQLAlchemy 2`
- `Pydantic v2`
- `SQLite`

### Distributed runtime

- `Celery`
- `Redis`
- stage-based audit pipeline
- queue-affinity worker topology

### ML

- `scikit-learn`
- `sentence-transformers`
- `CatBoost`

### Frontend

- `React`
- `TypeScript`
- `Vite`

## Каноническая worker topology

Начиная с `D11`, проект использует три профиля workers:

- `pipeline`
- `network`
- `cpu_ml`

Соответствие очередей задаётся в:

- `backend/app/worker_topology_profiles.json`

Эта topology валидируется через readiness и runtime metrics. Старый single all-queues worker допустим только как debugging fallback.

## Важные runtime contracts

### Health endpoints

- `GET /health`
- `GET /health/live`
- `GET /health/ready`
- `GET /health/metrics`

### Audit endpoints

- `GET /audits`
- `POST /audits`
- `GET /audits/{audit_id}`
- `GET /audits/{audit_id}/results`
- `GET /audits/{audit_id}/recommendations`
- `GET /audits/{audit_id}/events`
- `GET /audits/{audit_id}/events/diagnostics`

### Admission semantics

Начиная с `D10`, `POST /audits` может вернуть `503`, если runtime capacity деградирована. Это нормальная часть поведения системы, а не баг по умолчанию.

## D12 benchmark workflow

Benchmark runner находится в:

- `scripts/run_distributed_benchmark.py`

Пример workload-файла:

- `scripts/distributed_benchmark.workload.example.json`

Артефакты benchmark запуска сохраняются в:

- `backend/artifacts/benchmarks/`

Benchmark использует production API surface:

- `POST /audits`
- `GET /audits/{audit_id}`
- `GET /audits/{audit_id}/events/diagnostics`
- `GET /health/metrics`

## Основные команды

### Полный локальный стек

```powershell
cd E:\codexPROJ\diplom
npm install
npm --prefix frontend install
npm run dev:full
```

### Backend tests

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest
```

### Script tests

```powershell
cd E:\codexPROJ\diplom
npm run test:scripts
```

### Frontend build

```powershell
cd E:\codexPROJ\diplom
npm run build
```

## Документы, на которые стоит смотреть первыми

- `README.md` — обзор проекта и локальный запуск.
- `backend/README.md` — backend, API, workers, benchmark.
- `docs/roadmap/product-development-roadmap.md` — roadmap и backlog.
- `backend/docs/ml_methodology_appendix.md` — ML methodology appendix.

## Git и публикация

- Коммитить только после проверок.
- Не заявлять о закрытии issue, если push не выполнен.
- Если используется `Closes #<n>`, issue должен закрываться через push в `main`, а не вручную без кода.


## D13-D20 Status

Current next-wave backlog: `D13-D20`.

- `D13` - completed: versioned extraction pipeline, `feature schema v2`, persistent `target_snapshot`, DOM-based extraction, and API snapshot summary.
- `D14` - completed: пакет технических SEO-сигналов поверх `target_snapshot`, включая canonical/redirect/indexability/url-hygiene признаки, технические рекомендации и технические факторы в score explanation без изменения текущего `FEATURE_COLUMNS`.
- `D15` - completed: пакет commercial/trust signals для коммерческих landing pages, включая contact/business identity признаки, CTA/messenger detection, агрегированные commercial/trust scores и recommendation layer, доступный также в dataset builder.
- `D16` - completed: query intent detection, intent-alignment features for target and competitors, persisted `query_intent` in `Audit`, SERP-relative gaps/percentiles/z-scores for key signal groups, and relative/intent-aware explanation and recommendation rules.
- `D17-D20` - pending.
