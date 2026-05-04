# Site Audit

Веб-приложение для автоматизации SEO-аудита конкурентоспособности посадочных страниц по конкретному поисковому запросу.

Пользователь задаёт поисковый запрос и URL своей страницы, после чего система:

- находит популярные конкурентные страницы в выдаче;
- анализирует целевую страницу и конкурентов;
- извлекает SEO, технические, текстовые, коммерческие и поведенчески значимые признаки;
- считает базовую ML-оценку самой страницы;
- пересчитывает итоговый конкурентный score с учётом обработанных конкурентов;
- показывает, где страница сильнее или слабее top-N контекста;
- формирует рекомендации с приоритетами, завязанными на поисковую важность и отставание от конкурентов.

Проект ориентирован на тему диплома: распределённое web-приложение машинного обучения. Распределённая часть построена на `Celery + Redis`, а доказательная база по runtime подтверждается health/metrics, event timeline и benchmark workflow.

## Основные возможности

- запуск нового аудита по запросу и URL;
- сбор конкурентов через `SearxNG`;
- пошаговая распределённая обработка аудита по stage-based pipeline;
- ML-scoring страницы и сохранение breakdown по оценке;
- technical SEO feature pack на основе snapshot-артефакта страницы;
- commercial/trust feature pack для коммерческих landing pages;
- изоляция тяжёлых analyzer-стадий в отдельную distributed queue;
- итоговый `Конкурентный score`, который отделён от внутренней `Оценки самой страницы`;
- выдача рекомендаций по улучшению страницы с competitor-gap priority model;
- локальное отслеживание статусов рекомендаций как плана работ;
- единый audit report dashboard с экспортом в печатный HTML/PDF-like view, HTML и Markdown;
- timeline событий аудита и диагностика критического пути;
- диагностика рабочего стека для очередей, воркеров, накопления задач и контроля допуска;
- панель истории аудитов с фильтрами, повторным запуском, быстрым открытием последнего успешного аудита и локальным скрытием строк;
- benchmark/reporting workflow для демонстрации распределённого исполнения.

## Архитектура

### Компоненты

- `frontend/` — интерфейс на `React + TypeScript + Vite`.
- `backend/` — API на `FastAPI`, orchestration, хранение данных, ML scoring и training workflow.
- `Redis` — broker/result backend для `Celery`.
- `Celery workers` — исполняют стадии аудита в распределённом runtime.
- `SearxNG` — поисковый провайдер для получения конкурентных страниц.
- `SQLite` — хранилище MVP.

### Распределённый pipeline

Аудит больше не выполняется одной монолитной задачей. Он разбит на отдельные стадии и очереди:

- `audits.pipeline` — orchestration, admission control, dispatch стадий;
- `audits.fetch` — загрузка целевой страницы;
- `audits.heavy_analysis` — snapshot-based тяжёлые анализаторы target и semantic/ML анализ competitor pages;
- `audits.features` — извлечение признаков;
- `audits.scoring` — rule-based и ML scoring;
- `audits.competitors` — поиск и подготовка конкурентов;
- `audits.competitor_pages` — fan-out обработка страниц конкурентов;
- `audits.recommendations` — генерация рекомендаций;
- `audits.finalize` — финализация результата.

### Профили workers

Начиная с `D20`, каноническая топология workers выглядит так:

- `pipeline` — orchestration и dispatch;
- `network` — сетевые стадии: `fetch`, `competitors`, `competitor_pages`;
- `heavy_analysis` — тяжёлые snapshot/semantic/ML analyzer-задачи;
- `cpu_ml` — `features`, `scoring`, `recommendations`, `finalize`.

Именно эта топология проверяется через `GET /health/ready` и `GET /health/metrics`.

## Структура репозитория

- `backend/` — FastAPI backend, Celery runtime, ML и тесты backend.
- `frontend/` — React frontend.
- `scripts/` — dev-скрипты, benchmark workflow, генерация обучающих запросов.
- `docs/roadmap/` — стратегический roadmap; operational handoff находится в `AGENTS.md`.
- `docker-compose.searxng.yml` — локальный стек `SearxNG + Redis`.
- `plans/` и `PLANS.md` — вспомогательные проектные материалы.

## Статус backlog

Завершённые волны проекта:

- `D1-D12` — distributed runtime foundation: stage-based pipeline, per-stage queues, fan-out, health/metrics, diagnostics, admission control и benchmark evidence.
- `D13-D26` — SEO/ML/product/frontend evidence wave: snapshot extraction, feature schema v2, technical SEO, commercial/trust, intent-aware и SERP-relative features, dataset/model workflow, grouped recommendations UI, isolated heavy-analysis queue, audit report/export dashboard, audit execution timeline UI, панель состояния рабочего стека/очередей, audit history management, recommendation action tracking и interface terminology polish.

Итог: проект уже закрывает ключевые требования дипломной темы — web-приложение машинного обучения с доказуемым распределённым runtime.

Завершённая frontend/product wave после `D21` была заведена в GitHub:

- `D21` / `#40` — completed: audit report and export dashboard.
- `D22` / `#41` — completed: audit execution timeline UI.
- `D23` / `#42` — completed: панель состояния рабочего стека и здоровья очередей.
- `D24` / `#43` — completed: audit history management.
- `D25` / `#44` — completed: recommendation action tracking.
- `D26` / `#45` — completed: interface copy and terminology polish.

Волна `D21-D26` закрыта. Demo mode в текущий backlog не входит.

Финальный ML-evidence этап `D27-D31` завершён и GitHub issues `#46-#50` закрыты как completed. Эти задачи собрали и провалидировали `dataset-v2`, обучили candidate model и доказали через D30 benchmark, что текущий production artifact пока нужно оставить (`keep_reference`). Репозиторий может быть приватным, поэтому другие Codex-диалоги без GitHub-авторизации могут видеть `404 Not Found` на `/issues` и через GitHub API. Локальная копия задач остаётся рабочим источником правды:

- `plans/d27-d31-final-model-training.md` — подробный план выполнения;
- `D27` / `#46` — completed/pushed: `dataset-v2` собран из seed catalog батчами;
- `D28` / `#47` — completed/pushed: quality gates, `manifest.json` и group split проверены;
- `D29` / `#48` — completed: candidate model обучена на `dataset-v2` без замены production artifact;
- `D30` / `#49` — completed: candidate сравнен с текущей моделью через ranking benchmark, recommendation `keep_reference`;
- `D31` / `#50` — completed locally: no-publish/keep-reference decision по D30 принят, продукт проверен smoke-аудитом.
- D31 clean rerun evidence: `scripts/d31-runtime-smoke.mjs` regenerated `output/runtime-smoke/d31-smoke-summary.json` from a clean stack; audit `45ca43ab-fb3a-4045-a28a-5f012cee4ffb` completed with `4` workers, missing queues `[]`, `2/2` competitors analyzed, `13` recommendations, `competitor_page` fan-out `2/2`, and runtime model `ru_commercial_dataset-20260421-primary` / schema `v1`.

Практический backlog `D32-D36` после `D31` завершён локально: модель внедрялась в продукт без слепой замены artifact, а GitHub issues `#51-#55` продублированы локально в `plans/d32-d36-model-productization.md`:

- `D32` / `#51` - completed locally: `197` expert-rubric labels for `dataset-v2`;
- `D33` / `#52` - completed locally: `manifest.json` and `split.json` refreshed after applying expert labels;
- `D34` / `#53` - completed locally: RF, CatBoost and CatBoostRanker candidate artifacts trained without replacing production;
- `D35` / `#54` - completed locally: shadow benchmark and explainability guardrails recommend `keep_reference`;
- `D36` / `#55` — completed locally: controlled keep-reference/no-publish decision, rollback evidence and product smoke verification.

D34 evidence is stored in `backend/artifacts/ranking-benchmarks/dataset-v2-d34/`. The saved artifacts are `backend/artifacts/page_quality_model.dataset-v2-expert-rf-candidate.pkl`, `backend/artifacts/page_quality_model.dataset-v2-expert-catboost-candidate.pkl`, and `backend/artifacts/page_quality_model.dataset-v2-ranking-candidate.pkl`. D35 evidence is stored in `backend/artifacts/ranking-benchmarks/dataset-v2-d35/` and recommends `keep_reference` because all candidates fail at least one publish gate; smoke explainability has `3/4` exact query matches and `1/4` documented fallback. D36 evidence is stored in `backend/artifacts/ranking-benchmarks/dataset-v2-d36/no-publish-decision-report.json` and `.md`; product smoke evidence is `output/runtime-smoke/d36-smoke-summary.json` for audit `a814ad9e-0f35-441e-a7d3-f82a34abaae9`. `backend/artifacts/page_quality_model.pkl` remains unchanged at SHA1 `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`.

D37 / GitHub `#56` реализован локально как unified `v3` feature model with hybrid/top-3 guardrail evidence. Локальная копия плана: `plans/d37-unified-v3-hybrid-ensemble-top3-guardrail.md`. D37 добавил `MODEL_SCHEMA_VERSION_V3` на `148` pre-competitor features (`59` baseline + `49` technical/commercial + `25` heavy-analysis + `15` intent-alignment), собрал `backend/data/dataset_versions/dataset-v3-d37/` на `885` строк и `99` запросов, обучил non-production RF/CatBoost/CatBoostRanker candidates и сравнил их с текущим reference. Shadow benchmark `backend/artifacts/ranking-benchmarks/dataset-v3-d37-shadow/shadow-benchmark-guardrails-report.json` рекомендует `publish_candidate` и выбирает `pointwise_catboost`: `top_3_hit_rate=0.95`, `ndcg_at_10=0.945929`, `spearman_mean=0.421894`, `MAE=11.774165` против reference `0.95`, `0.909302`, `0.153604`, `23.858757`.

D38 / GitHub `#57` реализован локально как historical controlled publish CatBoost v3. Локальная копия плана: `plans/d38-controlled-publish-catboost-v3.md`. После D38 production artifact `backend/artifacts/page_quality_model.pkl` указывал на CatBoost v3 candidate: SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`, dataset `dataset-v3-d37`, artifact `dataset-v3-d37-20260501200434`, schema `v3`, `148` features. D58 позже заменил runtime alias на v5 pointwise CatBoost, а v3 сохранён как rollback artifact `backend/artifacts/versions/page_quality_model--dataset-v3-d37-20260501200434.pkl`. D38 evidence: `backend/artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.json` и `.md`; runtime smoke: `output/runtime-smoke/d38-smoke-summary.json`, audit `690504f2-ca2f-42a6-a012-e622438437a7`, `2/2` competitors analyzed, `11` recommendations, runtime model `dataset-v3-d37` / schema `v3` / `CatBoostRegressor`.

D39 / GitHub `#58` реализован локально как model status в интерфейсе. Локальная копия плана: `plans/d39-model-status-interface.md`. Backend endpoint `GET /health/model` показывает активный runtime artifact, dataset/version metadata, guardrail metrics, publish context и rollback availability. Frontend использует эти данные только там, где они помогают объяснить работу системы, без пользовательского ML/debug clutter. Текущий runtime после D58: `active`, `CatBoostRegressor`, schema `v3`, dataset `dataset-v5`, artifact `dataset-v5-20260502151507`, rollback available.

D40 / GitHub `#59` реализован локально как post-publish model monitoring dashboard. Backend endpoint `GET /health/model/monitoring` агрегирует recent-аудиты по `score_breakdown.model_info`, показывает usage по artifact/schema/dataset, score distribution, competitor coverage, warnings/failures и legacy/unknown записи без model metadata. Frontend показывает это в существующем экране `Стек` рядом с D39 active model card.

D41 / GitHub `#60` реализован локально как deterministic golden query replay guardrails. Команда `cd backend && .venv\Scripts\python.exe -m app.ml.golden_replay --output-dir artifacts/ranking-benchmarks/dataset-v3-d41` формирует JSON/Markdown evidence без live network, publish или rollback; volatile `/health/model.checked_at` нормализуется к фиксированному report timestamp. Default evidence использует один D38 smoke artifact и явно помеченные synthetic stored fixtures для остальных golden items. Evidence: `backend/artifacts/ranking-benchmarks/dataset-v3-d41/golden-replay-report.json` и `.md`; текущий decision `passed`, `3/3` golden items passed, `21/21` guardrails passed.

D42 / GitHub `#61` реализован локально как score confidence/data-quality UX layer. Frontend helper `frontend/src/lib/auditConfidence.ts` классифицирует уверенность score как `high` / `medium` / `low` / `unknown` по существующим audit payloads: fetch status/method, feature schema, heavy analysis, competitor coverage, recommendations, `score_breakdown.model_info`, warnings и failure context. UI показывает компактный бейдж и reason list в обзоре аудита, а вкладка `Отчёт`, Markdown export и HTML/printable export включают те же confidence metrics. D42 не меняет numeric score formula, backend scoring pipeline или `backend/artifacts/page_quality_model.pkl`.

D43 / GitHub `#62` реализован локально как read-only model registry and rollback evidence UI. Backend endpoint `GET /health/model/registry` сканирует active alias, `backend/artifacts/versions/`, public metadata sidecars и evidence reports, показывает текущий CatBoost v3, rollback v1 RandomForest, SHA1, publish/smoke report paths и rollback guardrail warnings. Frontend показывает это в существующем экране `Стек` как `Model registry и rollback evidence` с dry-run checklist; UI не выполняет rollback, а actual rollback остаётся controlled engineering operation.

D44 / GitHub `#63` реализован локально как non-production second-pass competitor-aware score experiment. Локальная копия backlog: `plans/d40-d44-post-publish-model-operations.md`. Evidence: `backend/artifacts/ranking-benchmarks/dataset-v3-d44/second-pass-experiment-report.json` и `.md`; candidate artifact `backend/artifacts/page_quality_model.dataset-v3-d44-second-pass-experiment.pkl` помечен non-production и не заменяет active runtime model.

### Distributed foundation `D1-D12`

Выполнено:

- `D1-D4` — stage-based pipeline, per-stage queues, distributed fan-out, retry-safe orchestration.
- `D5-D8` — `health/live`, `health/ready`, `health/metrics`, persistent event log и timeline diagnostics.
- `D9-D11` — детектор нагрузки очередей, контроль допуска под нагрузкой, профили топологии воркеров.
- `D12` — benchmark/reporting workflow для измеримого подтверждения распределённого runtime.

Итог: backlog `D1-D12` завершён, а frontend/product wave `D21-D26` закрыта без нового серверного слоя исполнения или demo mode.

## Требования

- `Python 3.12` или `3.13`
- `Node.js 20+`
- `npm`
- `Docker Desktop` или совместимый Docker runtime

Все команды ниже приведены в формате `PowerShell` для Windows.

## Быстрый старт

### 1. Установить root и frontend зависимости

```powershell
cd E:\codexPROJ\diplom
npm install
npm --prefix frontend install
```

### 2. Подготовить backend окружение

```powershell
cd E:\codexPROJ\diplom\backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
copy .env.example .env
```

Если используется `Python 3.13`, workflow остаётся тем же: `backend/pyproject.toml` допускает версии `>=3.12,<3.14`.

### 3. Запустить полный локальный стек

```powershell
cd E:\codexPROJ\diplom
npm run dev:full
```

Короткий эквивалент для запуска из консоли:

```powershell
cd E:\codexPROJ\diplom
npm start
```

Команда:

- поднимает `SearxNG` и `Redis`;
- проверяет доступность `SearxNG` через лёгкий endpoint `/healthz`, не выполняя поисковый запрос и не расходуя лимиты внешних search engines;
- запускает backend API;
- запускает frontend;
- запускает четыре worker-профиля: `pipeline`, `network`, `heavy_analysis`, `cpu_ml`.

Если порт `8000` уже занят, root dev-скрипт выбирает следующий свободный порт backend API, например `8001`, и автоматически передаёт его во frontend через `VITE_API_URL`. Сайт при этом остаётся на `http://127.0.0.1:5173/`; для ручных `Invoke-RestMethod` используйте backend URL, который напечатал `npm start`.

Локальный `infra/searxng/settings.yml` фиксирует для dev-аудитов стабильный search engine `presearch`. Это снижает риск CAPTCHA/403 от движков, которые SearXNG включает по умолчанию, и делает сбор конкурентов устойчивее для демонстрации.

Это рекомендуемый режим для полноценного аудита и для демонстрации распределённой архитектуры.

### Проверка сборки и содержимого frontend

Перед демонстрацией можно проверить, что production-сборка собирается и содержит ключевые экраны интерфейса:

```powershell
cd E:\codexPROJ\diplom
npm run site:check
```

Команда выполняет `frontend` build и проверяет `frontend/dist/index.html`, подключённые JS/CSS assets и основные тексты интерфейса: запуск аудита, историю аудитов, рабочее пространство, конкурентов, рекомендации и конкурентный score.

### 4. Проверить готовность рабочего стека

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/live"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/metrics"
```

Если `npm start` выбрал другой backend port, замените `8000` на фактический порт из консоли запуска.

Что важно:

- `GET /health/live` показывает, что процесс API жив.
- `GET /health/ready` возвращает `200`, когда готовы БД, Redis, воркеры и нужные очереди.
- Проверка SearXNG внутри `GET /health/ready` ходит в `/healthz`, а не в `/search`, чтобы панель состояния не тратила поисковые лимиты и не ломала сбор конкурентов частым polling.
- `GET /health/ready` может вернуть `503`, если распределённый стек не готов.
- `GET /health/metrics` показывает накопление задач в очередях, нагрузку очередей, активность воркеров и алерты рабочего стека.
- `GET /health/model` показывает активный runtime ML artifact, dataset/schema metadata, guardrail metrics и rollback availability.
- `GET /health/model/registry` показывает read-only release history: current/rollback artifacts, versioned metadata sidecars, publish/smoke evidence paths, SHA1 и rollback dry-run checklist.
- `GET /health/model/monitoring` показывает recent usage опубликованной модели: coverage `model_info`, score distribution, competitor coverage, warnings/failures и legacy/unknown audit rows.
- Локальный `GET /health/metrics` может показывать `degraded`, если в SQLite остались старые audit rows со статусом `processing`; для фактической готовности нового запуска сначала смотрите `GET /health/ready` и покрытие очередей воркерами.

### Где смотреть параллельную работу воркеров

В интерфейсе:

- `http://127.0.0.1:5173/?view=runtime` или кнопка `Стек` — профили workers, какие очереди они покрывают, глубина очередей и активные задачи.
- Внутри аудита вкладка `Таймлайн` — lifecycle стадий, dispatch events, fan-out ветки competitors и critical path. Для конкурентов важны стадии `competitor_page` и `competitor_analysis`.

Через API:

- `GET /health/ready` — главный быстрый ответ, подняты ли `pipeline`, `network`, `heavy_analysis`, `cpu_ml` и покрыты ли все audit queues.
- `GET /health/metrics` — нагрузка очередей и активность workers; overall status может быть `degraded` из-за старых зависших строк в локальной SQLite, но `workers.status` и `queue_pressure.status` показывают текущее состояние очередей.
- `GET /audits/{audit_id}/events/diagnostics` — доказательство распределённого исполнения конкретного аудита: `fan_out.stage=competitor_page`, а в `critical_path_stages` competitor stages идут с `mode=fan_out_max`.

Контрольная проверка от `2026-04-30`: smoke-аудит `сайт для фрилансеров` / `https://gigle.ru/` / `top_n=3` завершился со статусом `completed`, нашёл `3` конкурента и проанализировал `3` конкурента. В timeline были отдельные fan-out стадии `competitor_page` и `competitor_analysis`.

## Разница между `npm run dev` и `npm run dev:full`

- `npm run dev` запускает только backend и frontend.
- `npm run dev:full` дополнительно поднимает `SearxNG`, `Redis` и Celery workers.

Для полного audit lifecycle используйте именно `npm run dev:full`.

Если backend запущен без worker-стека, `POST /audits` может вернуть `503` из-за admission guard, либо аудит не сможет полноценно пройти распределённые стадии.

## Ручной запуск компонентов

### SearxNG и Redis

```powershell
cd E:\codexPROJ\diplom
npm run searxng:up
npm run searxng:check
```

`npm run searxng:check` проверяет только `/healthz`. Реальную выдачу конкурентов проверяет сам audit pipeline на этапе `competitors`.

Остановка:

```powershell
cd E:\codexPROJ\diplom
npm run searxng:down
```

### Backend API

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd E:\codexPROJ\diplom\frontend
npm run dev
```

### Celery workers

Рекомендуемый вариант — `npm run dev:full`. Если нужен ручной запуск, используйте отдельные профили.

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

## Основные API endpoints

### Health

- `GET /health` — простой legacy healthcheck.
- `GET /health/live` — liveness API.
- `GET /health/ready` — готовность распределённого стека.
- `GET /health/metrics` — диагностика очередей, воркеров и накопления задач.
- `GET /health/model` — активная runtime ML-модель и её publish/rollback metadata.
- `GET /health/model/registry` — read-only model registry, release history и rollback evidence checklist.
- `GET /health/model/monitoring` — recent model usage monitoring over audit `score_breakdown.model_info`.

### Audits

- `GET /audits` — список аудитов.
- `POST /audits` — создать новый аудит.
- `GET /audits/{audit_id}` — текущее состояние аудита.
- `GET /audits/{audit_id}/results` — результат и score breakdown; frontend D42 дополнительно строит UX-уверенность score из этих полей без нового backend endpoint.
- `GET /audits/{audit_id}/recommendations` — рекомендации.
- `GET /audits/{audit_id}/events` — timeline событий.
- `GET /audits/{audit_id}/events/diagnostics` — диагностика critical path и fan-out.

Важно: начиная с `D10`, `POST /audits` может возвращать `503`, если пропускная способность рабочего стека деградировала и контроль допуска временно отклоняет новые аудиты.

## Benchmark workflow (`D12`)

Для подтверждения распределённого исполнения используется benchmark runner, который работает поверх реального HTTP API, а не отдельного synthetic path.

Пример запуска:

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

Benchmark использует:

- `POST /audits` — admission и запуск аудитов;
- `GET /audits/{audit_id}` — отслеживание жизненного цикла;
- `GET /audits/{audit_id}/events/diagnostics` — latency и critical path;
- `GET /health/metrics` — накопление задач, нагрузка очередей, профили топологии, занятость воркеров и алерты.

Артефакты сохраняются в:

- `backend/artifacts/benchmarks/<timestamp>-<benchmark-name>/benchmark-report.json`
- `backend/artifacts/benchmarks/<timestamp>-<benchmark-name>/benchmark-report.md`

Пример workload-файла лежит в `scripts/distributed_benchmark.workload.example.json`.

## Тесты и проверки

### Backend tests

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m pytest
```

### Script-level tests

```powershell
cd E:\codexPROJ\diplom
npm run test:scripts
```

### Frontend build

```powershell
cd E:\codexPROJ\diplom
npm run build
```

### Frontend unit tests

```powershell
cd E:\codexPROJ\diplom\frontend
npm run test
```

## Полезные скрипты

- `scripts/generate_training_queries.py` — генерация seed-набора обучающих запросов.
- `scripts/run_training_batches.py` — batch workflow для обучения.
- `scripts/run_distributed_benchmark.py` — benchmark distributed runtime.

## Что важно для диплома

Проект не ограничивается набором статических SEO-правил. Основная идея — оценка конкурентоспособности страницы по конкретному запросу через два слоя:

- `primary_page_score` — базовая ML-оценка самой страницы по её признакам: индексируемость, canonical, title/query fit, semantic/query fit, intent alignment, technical SEO, commercial/trust и другие сигналы;
- `competitiveness_score` — итоговый продуктовый score после сравнения с обработанными конкурентами: насколько страница выглядит сильной или слабой относительно top-N контекста;
- `competitor-gap-priority-v1` — слой рекомендаций, который поднимает выше факторы с большим отставанием от конкурентов, высокой SEO-важностью и понятным способом исправления.

За счёт `Celery`, очередей, fan-out обработки конкурентов, health/metrics, timeline diagnostics и benchmark workflow проект даёт не только ML-оценку, но и убедимую распределённую архитектуру для темы дипломной работы.

## Статус D13-D26

Продуктовая волна backlog — `D13-D26` — завершена.

Выполнено:

- `D13` - версионированный extraction pipeline и `feature schema v2`: постоянный `target_snapshot`, DOM-based extraction, повторяемый пересчёт признаков из сохранённого snapshot и API-поля `feature_schema_version` и `target_snapshot_summary`.
- `D14` - пакет технических SEO-признаков: technical signals из snapshot, технические рекомендации и technical factors в score explanation без изменения текущей ML-схемы признаков.
- `D15` - пакет commercial/trust signals: телефоны, адрес, часы работы, цены, доставка, оплата, гарантия, возврат, отзывы, рейтинг, FAQ, CTA, мессенджеры, legal/business identity признаки, агрегированные commercial/trust scores и новый recommendation layer.
- `D16` - SERP-relative и intent-aware слой: `query_intent`, intent-alignment features для target/competitors, relative gaps/percentiles/z-scores по ключевым signal groups и новый explanation/recommendation context.
- `D17` - versioned dataset workflow: заморожен `baseline-v1`, добавлен `dataset-v2` bundle, hybrid labeling (`weak_serp + expert subset`), сохранение raw extraction artifacts, versioned manifest и воспроизводимый `group_by_query` split.

Выполнено дополнительно:

- `D18` - model schema v2, artifact-driven runtime/training/publish flow, ranking benchmark workflow и publish/report path.
- `D19` - grouped recommendations API/UI, factor groups (`Technical SEO`, `Commercial and Trust`, `Semantic and Intent`, `Competitor Gap`), competitor-relative deviations, richer explainability payload и legacy normalization для старых аудитов.
- `D20` - dedicated `audits.heavy_analysis` queue/profile, target heavy-analysis stage, split competitor network fetch vs heavy semantic/ML analysis, heavy queue admission guard, queue-pressure metrics and benchmark topology-profile summary.
- `D21` - audit report/export dashboard: вкладка `Отчёт`, компактная сводка SEO/ML/recommendation/competitor/runtime evidence, printable HTML/PDF-like view, downloadable HTML и Markdown export без повторного анализа страницы.
- `D22` - audit execution timeline UI: вкладка `Таймлайн`, raw event stream, stage lifecycle, queues, fan-out branch summary, critical path, warnings/failure context поверх существующих events APIs.
- `D23` - панель состояния рабочего стека и здоровья очередей: компактная панель `Готовность рабочего стека` на экране запуска, глобальный экран `Стек`, использование `health/live`, `health/ready`, `health/metrics`, покрытие профилей воркеров, нагрузка очередей, накопление задач, очереди без воркеров и человекочитаемые подсказки восстановления.
- `D24` - audit history management: панель истории с метриками, фильтрами по статусу/домену/запросу/фокусу, быстрым открытием последнего успешного аудита, повторным запуском из строки и локальным скрытием/восстановлением записей без удаления backend-данных.
- `D25` - recommendation action tracking: локальный план действий на странице рекомендаций, статусы `Не начато`, `В работе`, `Исправлено`, `Игнорируется`, summary закрытых действий и прогресс по группам без изменения backend analysis data.
- `D26` - interface copy and terminology polish: русские primary labels для отчёта, рекомендаций, истории, runtime/timeline и production smoke-фрагментов; технические коды рекомендаций и очередей оставлены вторым уровнем.

Текущая волна `D13-D26` завершена. Если нет явно выбранного GitHub issue, новый фокус нужно брать из следующей явно поставленной задачи, не из закрытого D26 backlog.

## Dataset V2 Workflow (`D17`)

Начиная с `D17`, обучающие данные больше не рассматриваются как один неявный CSV в `backend/data/`. Для ML-части введён versioned bundle в `backend/data/dataset_versions/`.

Что уже есть в репозитории:

- `backend/data/dataset_versions/baseline-v1/` — зафиксированная копия текущего primary dataset, manifest, checkpoint и seeds.
- `backend/data/dataset_versions/dataset-v2/` — seed bundle нового датасета, metadata-файл, шаблон `expert_labels.csv` и целевая структура для `dataset.csv`, `failures.csv`, `manifest.json`, `split.json` и raw `artifacts/`.

Ключевые принципы `D17`:

- слабая метка строится из позиции в выдаче (`weak_target_score`);
- экспертная разметка хранится отдельно (`expert_target_score`);
- итоговая training label сохраняется как `target_score` и помечается `label_source`;
- по каждой строке dataset v2 может сохраняться raw snapshot-артефакт extraction schema v2;
- train/validation split сохраняется отдельно и воспроизводимо в формате `group_by_query`.

Базовый workflow построения `dataset-v2`:

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

После сборки manifest и split формируются так:

```powershell
cd E:\codexPROJ\diplom\backend
.venv\Scripts\python.exe -m app.ml.train `
  --dataset data\dataset_versions\dataset-v2\dataset.csv `
  --dataset-version dataset-v2 `
  --split-output data\dataset_versions\dataset-v2\split.json `
  --test-size 0.2 `
  --random-state 42 `
  --split-only

.venv\Scripts\python.exe -m app.ml.dataset_quality `
  --dataset data\dataset_versions\dataset-v2\dataset.csv `
  --failures data\dataset_versions\dataset-v2\failures.csv `
  --seeds data\dataset_versions\dataset-v2\seeds.csv `
  --dataset-version dataset-v2 `
  --baseline-version baseline-v1 `
  --artifacts-dir data\dataset_versions\dataset-v2\artifacts `
  --split data\dataset_versions\dataset-v2\split.json `
  --output data\dataset_versions\dataset-v2\manifest.json
```

Волна `D32-D36` завершена локально: D36 зафиксировал controlled keep-reference/no-publish decision, rollback/reference evidence и product smoke verification без замены production artifact. D37 реализован локально в `plans/d37-unified-v3-hybrid-ensemble-top3-guardrail.md`: v3 dataset/candidates/shadow guardrails доказали publishable `pointwise_catboost`. D38 исторически опубликовал CatBoost v3 в production alias и сохранил rollback artifact; D58 позже заменил runtime alias на v5. D39 реализован локально в `plans/d39-model-status-interface.md`: active model status выведен в `/health/model`, stack UI, score breakdown и audit report/export.

D40-D44 реализованы локально в `plans/d40-d44-post-publish-model-operations.md`: model monitoring добавлен в `/health/model/monitoring` и экран `Стек`, golden replay evidence хранится в `backend/artifacts/ranking-benchmarks/dataset-v3-d41/`, audit UX показывает score confidence/data-quality reason list без изменения модели, `/health/model/registry` и stack UI показывают current/rollback release evidence без выполнения rollback, а D44 добавляет offline second-pass experiment с `serp_relative` features.

D44 decision: `do_not_continue_without_more_evidence`. Second-pass CatBoost candidate slightly improves MAE but regresses top-3 and NDCG@10, so no publish/rollout should be started from D44 without a new explicit evidence task.

Текущий product-aligned этап после D44 изменил смысл score в сторону реальной задачи проекта: оценить, насколько выбранная страница конкурентоспособна по конкретному запросу на фоне top-N страниц из выдачи, и дать рекомендации, которые помогают стать сильнее именно в этом контексте.

- `D45-D49` — historical SEO-weighted retraining wave: собран `dataset-v4`, сделаны SEO-weighted deterministic rubric labels, обучены кандидаты, но публикации не было из-за тогдашних release guardrails.
- `D50-D54` — historical ranking-aware v5 wave: создан `dataset-v5` с query-level preference labels и shortcut feature control; первичная D54 decision была `keep_current`, потому что старая политика блокировала кандидатов по `top_3_hit_rate`.
- `D55` / `#74` — completed/pushed: release policy теперь считает `top_3_hit_rate` SERP-alignment диагностикой, а не абсолютным publish-блокером. Основные метрики для модели: `MAE`, `Spearman`, `NDCG@10`, score-response, feature dominance и recommendation consistency.
- `D56` / `#75` — completed/pushed: после обработки конкурентов появляется `competitiveness-score-v1`. Внутренний ML-score страницы сохраняется как `primary_page_score`, а итоговый `audit.score` при достаточном competitor context становится `competitiveness_score`.
- `D57` / `#76` — completed/pushed: рекомендации используют `competitor-gap-priority-v1`, где приоритет зависит от размера отставания, поисковой важности фактора и управляемости исправления.
- `D58` / `#77` — completed/pushed: v5 pointwise CatBoost опубликован как активный runtime artifact under competitiveness scorecard. Текущий `backend/artifacts/page_quality_model.pkl`: SHA1 `5374ca30f48f70d8629e7d84ec3df0524ef35b52`, dataset `dataset-v5`, artifact `dataset-v5-20260502151507`, schema `v3`, `CatBoostRegressor`, `148` features. Metrics: `MAE=1.22855`, `Spearman=0.957788`, `NDCG@10=0.998374`, `top_3_hit_rate=0.6` as non-blocking SERP diagnostic.
- `D59` / `#78` — completed/pushed: из пользовательского интерфейса убран лишний ML/debug clutter.
- `D60` / `#79` — completed/pushed: research artifacts archived; runtime assets and evidence/archive assets are separated more clearly.
- `D61` / `#80` — this documentation pass: README, backend README, roadmap and ML appendix describe the competitiveness goal, current v5 runtime and the new metric interpretation.
- `D62-D68` — implemented locally: финальный query-competitiveness contract. Runtime relevance теперь использует query relevance guardrail вокруг score, чтобы страница не по запросу не могла получить среднюю оценку только за общие SEO-сигналы. Новый `dataset-v7-final` пока готов как seed/evidence для реального top-10 сбора: `500` запросов, `50` категорий, пять городов. Финальный release pipeline находится в `backend/app/ml/final_query_competitiveness.py` и блокирует publish, пока `dataset-v7-final` не собран и не размечен deterministic expert rubric labels.
- `D69` — implemented locally: сборщик `dataset-v7-final` получил domain cap (`--max-domain-rows-per-domain`, рекомендовано `12`) до parallel fetch, а hard negatives теперь материализуются из сохранённых snapshot artifacts с пересчётом признаков под новый запрос. Финальный pipeline требует `dataset.with-hard-negatives.csv`, если manifest помечает hard negatives обязательными.
- `D70` — implemented locally: `query-relevance-contract-v2` разделяет relevance cap и `early_stop_decision`. Уверенный full mismatch теперь уходит в `0-5` и помечается как кандидат на раннюю остановку, а сомнительные случаи продолжают аудит в низком диапазоне (`probable_mismatch` до `25`), чтобы не отрезать релевантные страницы из-за ошибки векторизации.
- `D71` — implemented locally: backend preflight теперь запускается после загрузки и базового feature extraction. Только уверенное полное несоответствие запросу останавливает аудит до heavy analysis и конкурентов; аудит завершается как `completed`, score остаётся в `0-5`, а payload содержит `score_basis=query_relevance_early_stop`.
- `D73-D74` — implemented locally: UI показывает это как понятное состояние `Страница не соответствует запросу` в обзоре, конкурентах, истории и отчёте, без raw ML/debug полей; regression tests закрывают unrelated good pages, near-topic false positives, коммерческие модификаторы, редкие low-signal случаи и недостаточный текст.

Исторические планы `plans/d32-d36-model-productization.md`, `plans/d37-unified-v3-hybrid-ensemble-top3-guardrail.md`, `plans/d40-d44-post-publish-model-operations.md`, `plans/d45-d49-seo-weighted-score-retraining.md`, `plans/d50-d54-v5-ranking-aware-model.md`, `plans/d55-d61-product-aligned-competitiveness.md`, `plans/d62-d68-final-query-competitiveness.md`, `plans/d69-dataset-v7-collection-readiness.md`, `plans/d70-conservative-query-relevance-contract.md` и `plans/d71-d74-query-relevance-preflight-ui-regression.md` оставлены как evidence. Если GitHub Issues недоступны и возвращают `404`, `AGENTS.md` и эти локальные планы считать актуальным backlog source of truth.
