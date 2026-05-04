# Backend

Backend проекта `Site Audit` построен на `FastAPI` и отвечает за полный серверный цикл SEO-аудита:

- создание и хранение аудитов;
- распределённую обработку stage-based pipeline через `Celery`;
- получение и нормализацию данных по целевой странице и конкурентам;
- извлечение контентных, семантических, технических, commercial и trust-признаков;
- базовый ML scoring страницы и competitor-aware пересчёт итогового конкурентного score;
- генерацию приоритетных рекомендаций на основе отставания от конкурентов;
- диагностику рабочего стека, проверку готовности и состояние распределённого исполнения.

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
- `artifacts/` — модельные и benchmark-артефакты; `artifacts/README.md` фиксирует границу между production runtime alias и research/evidence archive.

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

Локальная конфигурация `../infra/searxng/settings.yml` оставляет для dev-аудитов стабильный engine `presearch`. Это сделано для устойчивого сбора конкурентов в демонстрационном окружении: часть default SearXNG engines часто отвечает CAPTCHA/403 при частом polling или серии аудитов.

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

Если порт `8000` уже занят, root dev-скрипт автоматически выбирает следующий свободный порт backend API, например `8001`, и прокидывает его во frontend через `VITE_API_URL`. Поэтому сайт может работать корректно на `5173`, даже если raw API для ручной проверки находится не на `8000`; смотрите backend URL в выводе `npm start`.

Перед демонстрацией frontend production bundle можно проверить командой:

```powershell
cd E:\codexPROJ\diplom
npm run site:check
```

Она выполняет `npm run build` и проверяет `frontend/dist/index.html`, подключённые JS/CSS assets и ключевые тексты интерфейса.

## Health endpoints

Backend предоставляет health/runtime endpoint'ы:

- `GET /health` — legacy healthcheck;
- `GET /health/live` — liveness процесса API;
- `GET /health/ready` — готовность всего распределённого стека;
- `GET /health/metrics` — диагностика очередей, воркеров и накопления задач;
- `GET /health/model` — активный runtime ML artifact, dataset/schema metadata, guardrail metrics и rollback availability.
- `GET /health/model/registry` — read-only model release history: current/rollback artifacts, versioned metadata sidecars, evidence paths, SHA1 guardrails и rollback dry-run checklist.
- `GET /health/model/monitoring` — post-publish usage monitoring по `Audit.score_breakdown.model_info`: artifact/schema/dataset usage, score distribution, competitor coverage, warnings/failures и legacy/unknown audit rows.

Если один из обязательных компонентов не готов, `GET /health/ready` возвращает `503`.

Readiness проверяет SearXNG через лёгкий endpoint `/healthz`, а не через `/search`. Это принципиально для локального UI: глобальный экран `Стек` и стартовая карточка готовности часто опрашивают runtime, поэтому health-check не должен тратить лимиты внешних поисковых движков и провоцировать CAPTCHA/403 перед сбором конкурентов.

`GET /health/metrics` показывает глубину очередей, нагрузку очередей, активность воркеров, покрытие очередей, проверку топологии и алерты рабочего стека.

В локальной SQLite БД могут оставаться старые audit rows со статусом `processing`; тогда `GET /health/metrics` показывает `degraded` по execution detector, даже если текущий стек готов. Для допуска новых аудитов сначала проверяйте `GET /health/ready`, `missing_queues` и `queue_pressure`.

Для ответа на вопрос "работают ли воркеры параллельно" смотрите две плоскости:

- `GET /health/ready` и `GET /health/metrics`: должны быть видны четыре профиля `pipeline`, `network`, `heavy_analysis`, `cpu_ml`; `network` обслуживает `audits.fetch`, `audits.competitors`, `audits.competitor_pages`, а `heavy_analysis` обслуживает `audits.heavy_analysis`.
- `GET /audits/{audit_id}/events/diagnostics`: у конкретного аудита fan-out конкурентов должен появляться как `fan_out.stage=competitor_page`, а в `critical_path_stages` стадии `competitor_page` и `competitor_analysis` должны иметь режим `fan_out_max`.

В frontend то же самое видно без raw JSON: глобальный экран `Стек` показывает профили workers и очереди, а вкладка `Таймлайн` внутри аудита показывает fan-out ветки конкурентов и critical path.

## Audit API

Основные backend endpoints:

- `GET /audits` — список аудитов;
- `POST /audits` — создать новый аудит;
- `GET /audits/{audit_id}` — текущее состояние аудита;
- `GET /audits/{audit_id}/results` — результат, features и score breakdown; D42 frontend confidence layer использует эти поля для data-quality UX без нового backend endpoint;
- `GET /audits/{audit_id}/recommendations` — рекомендации;
- `GET /audits/{audit_id}/events` — timeline событий аудита;
- `GET /audits/{audit_id}/events/diagnostics` — диагностика critical path и fan-out.

### Что важно в результатах после D13-D26

При успешном аудите API теперь может отдавать:

- `feature_schema_version`;
- `target_snapshot_summary`;
- `heavy_analysis` с versioned analyzer payload и proxy features;
- expanded `features`, включая technical SEO и commercial/trust keys;
- score breakdown с technical/commercial/trust rule factors;
- рекомендации с `TECHNICAL_*`, `COMMERCIAL_*` и `TRUST_*` codes.

После `D22` frontend использует эти payloads вместе с `GET /audits/{audit_id}/events` и `GET /audits/{audit_id}/events/diagnostics`, чтобы собрать report/export dashboard и отдельный timeline UI без повторного backend-анализа страницы.

После `D23` frontend также использует `GET /health/live`, `GET /health/ready` и `GET /health/metrics`, чтобы показать готовность рабочего стека, покрытие профилей воркеров, нагрузку очередей, накопление задач и очереди без воркеров перед запуском аудита и на глобальном экране `Стек`.

После `D24` frontend использует существующие `GET /audits` и `POST /audits` для панели истории: фильтры, повторный запуск и локальное скрытие строк выполняются без нового backend delete/hide endpoint.

После `D25` frontend добавляет локальный action tracking к рекомендациям: статусы действий, прогресс и закрытие по группам хранятся в браузере и не требуют изменения backend recommendation schema.

После `D26` frontend и recommendation generator используют более понятную русскую copy для групп, метрик и рекомендаций. Backend recommendation schema, group keys и recommendation codes не менялись: отполированы только frontend-facing display strings.

## Admission control

Начиная с `D10`, `POST /audits` может вернуть `503`, если пропускная способность рабочего стека деградировала.

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
- `GET /health/model`
- `GET /health/model/registry`

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

Если параллельно запущен dev stack или в локальном Redis остались очереди без воркеров, тесты queue admission/dispatch могут увидеть stale live Redis state. Для детерминированной проверки backend без привязки к текущему Redis используйте изолированный unavailable broker URL:

```powershell
cd E:/codexPROJ/diplom/backend
$env:CELERY_BROKER_URL = "redis://localhost:1/0"
$env:CELERY_RESULT_BACKEND = "redis://localhost:1/0"
.venv/Scripts/python.exe -m pytest
Remove-Item Env:CELERY_BROKER_URL, Env:CELERY_RESULT_BACKEND
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
- `../AGENTS.md` — operational notes и актуальный статус после закрытия `D26` (`#45`).
- `../docs/roadmap/product-development-roadmap.md` — стратегический roadmap после `D26`, включая frontend/product wave без изменения ядра backend-анализа.
- `../plans/d27-d31-final-model-training.md` — выполненный локальный план `D27-D31` для финального ML evidence, если GitHub Issues приватного репозитория недоступны и возвращают `404`.
- `../plans/d32-d36-model-productization.md` — активная локальная копия backlog `D32-D36` для безопасного внедрения модели в продукт.
- `../plans/d37-unified-v3-hybrid-ensemble-top3-guardrail.md` — активная локальная копия `D37` для unified `v3` feature model, hybrid candidate и top-3 guardrail.
- `../plans/d38-controlled-publish-catboost-v3.md` — выполненный план D38 controlled publish CatBoost v3.
- `../plans/d39-model-status-interface.md` — выполненный план D39 model status in interface.
- `../plans/d40-d44-post-publish-model-operations.md` — завершённый локально backlog D40-D44 после публикации модели.
- `../plans/d45-d49-seo-weighted-score-retraining.md` — historical SEO-weighted retraining wave, где публикации не было.
- `../plans/d50-d54-v5-ranking-aware-model.md` — historical ranking-aware v5 evidence, later reinterpreted by D55 competitiveness policy.
- `../plans/d55-d61-product-aligned-competitiveness.md` — текущая product-aligned competitiveness wave после D54.
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

Завершённый backend/ML backlog после `D26`:

- `D27` / `#46` — completed/pushed: `dataset-v2` собран батчами через `app.ml.dataset_builder --versioned-layout`;
- `D28` / `#47` — completed/pushed: `manifest.json`, quality gates и `split.json` сформированы;
- `D29` / `#48` — completed: candidate artifact обучен без замены production model;
- `D30` / `#49` — completed: ranking benchmark против текущего `artifacts/page_quality_model.pkl` выполнен, recommendation `keep_reference`;
- `D31` / `#50` — completed locally: no-publish/keep-reference decision по D30 принят, runtime подтверждён smoke-аудитом.
- D31 clean rerun evidence: `scripts/d31-runtime-smoke.mjs` regenerated `output/runtime-smoke/d31-smoke-summary.json` from a clean stack; audit `45ca43ab-fb3a-4045-a28a-5f012cee4ffb` completed with `4` workers, missing queues `[]`, `2/2` competitors analyzed, `13` recommendations, `competitor_page` fan-out `2/2`, and runtime model `ru_commercial_dataset-20260421-primary` / schema `v1`.

Завершённый backend/ML backlog `D32-D36` после `D31`:

- `D32` / `#51` - completed locally: `197` expert-rubric labels for `dataset-v2`;
- `D33` / `#52` - completed locally: `manifest.json` and `split.json` refreshed after applying expert labels;
- `D34` / `#53` - completed locally: RF, CatBoost and CatBoostRanker candidate artifacts trained без замены production artifact;
- `D35` / `#54` - completed locally: shadow benchmark and explainability guardrails recommend `keep_reference`;
- `D36` / `#55` — completed locally: controlled keep-reference/no-publish decision, rollback evidence and product smoke verification.

D34 evidence: `artifacts/page_quality_model.dataset-v2-expert-rf-candidate.pkl`, `artifacts/page_quality_model.dataset-v2-expert-catboost-candidate.pkl`, `artifacts/page_quality_model.dataset-v2-ranking-candidate.pkl`, and `artifacts/ranking-benchmarks/dataset-v2-d34/candidate-artifact-training-report.json`. Production artifact `artifacts/page_quality_model.pkl` remains unchanged.

D35 evidence: `artifacts/ranking-benchmarks/dataset-v2-d35/shadow-benchmark-guardrails-report.json` recommends `keep_reference`; RF/CatBoost fail `top_3_hit_rate`, while CatBoostRanker also fails absolute-error guardrails. Smoke explainability has `3/4` exact query matches and `1/4` documented fallback. D36 evidence: `artifacts/ranking-benchmarks/dataset-v2-d36/no-publish-decision-report.json` and `.md` record the no-publish decision, rollback/reference hashes, product verification and unchanged production SHA1 `5600b5f3fff9b1b7590bc90b2b5fbc24ec5466f9`; product smoke summary is `../output/runtime-smoke/d36-smoke-summary.json` for audit `a814ad9e-0f35-441e-a7d3-f82a34abaae9`.

D37 / GitHub `#56` реализован локально как backend/ML unified `v3` feature model with hybrid/top-3 guardrail evidence. План находится в `../plans/d37-unified-v3-hybrid-ensemble-top3-guardrail.md`. D37 добавил `MODEL_SCHEMA_VERSION_V3` на `148` pre-competitor features (`v1` baseline + technical/commercial + heavy-analysis + intent-alignment), создал `data/dataset_versions/dataset-v3-d37/` с реальными v3 columns (`885` rows, `99` queries, `695/190` group split, no query leakage), обучил non-production candidates и сравнил их с текущим reference. Shadow benchmark `artifacts/ranking-benchmarks/dataset-v3-d37-shadow/shadow-benchmark-guardrails-report.json` рекомендует `publish_candidate` и выбирает `pointwise_catboost`: `top_3_hit_rate=0.95`, `ndcg_at_10=0.945929`, `spearman_mean=0.421894`, `MAE=11.774165`; reference: `0.95`, `0.909302`, `0.153604`, `23.858757`. `serp_relative` остаётся follow-up для second-pass scoring.

D38 / GitHub `#57` реализован локально как historical controlled publish CatBoost v3. После D38 production artifact `artifacts/page_quality_model.pkl` указывал на CatBoost v3: SHA1 `29c4b29455f795a535da94b2c6f36ef603d003eb`, dataset `dataset-v3-d37`, artifact version `dataset-v3-d37-20260501200434`, schema `v3`, `148` features. D58 later superseded this alias with the v5 pointwise CatBoost runtime; the v3 artifact remains rollback evidence in `artifacts/versions/page_quality_model--dataset-v3-d37-20260501200434.pkl`. D38 evidence: `artifacts/ranking-benchmarks/dataset-v3-d37-d38/controlled-publish-report.json` и `.md`; smoke summary: `../output/runtime-smoke/d38-smoke-summary.json`.

D39 / GitHub `#58` реализован локально как model status in interface. Backend endpoint `GET /health/model` отдаёт активный artifact, SHA1, metadata sidecar, model/dataset sections, `metrics_summary`, publish context and rollback reference. После D58 endpoint describes the active `dataset-v5` runtime artifact. План: `../plans/d39-model-status-interface.md`.

D40 / GitHub `#59` реализован локально как model usage monitoring. Backend endpoint `GET /health/model/monitoring` построен на `app/model_monitoring.py`, агрегирует recent audit rows по runtime `model_info`, отдельно считает legacy/unknown audits и не меняет scoring/publish behavior.

D41 / GitHub `#60` реализован локально как deterministic golden replay guardrails. Backend module `app/ml/golden_replay.py` генерирует `artifacts/ranking-benchmarks/dataset-v3-d41/golden-replay-report.json` и `.md`; default mode evaluates stored evidence offline, normalizes volatile `/health/model.checked_at` to the fixed report timestamp, includes rollback SHA1, and does not publish/rollback/mutate `artifacts/page_quality_model.pkl`. Default evidence uses one D38 smoke artifact plus explicit synthetic stored fixtures for the remaining catalog items; pass `--evidence-json` to evaluate externally captured snapshots.

D42 / GitHub `#61` реализован локально как frontend score confidence/data-quality UX layer поверх существующих audit payloads. Backend endpoint или scoring formula не менялись: UI использует `GET /audits/{audit_id}`, `GET /audits/{audit_id}/results` и `GET /audits/{audit_id}/recommendations`, чтобы классифицировать confidence как `high` / `medium` / `low` / `unknown`.

D43 / GitHub `#62` реализован локально как read-only model registry and rollback evidence UI. Backend module `app/model_registry.py` exposes `GET /health/model/registry`, scans `artifacts/versions/` plus public metadata sidecars and evidence reports, normalizes current CatBoost v3 and rollback v1 RandomForest records, and warns rather than crashes when rollback metadata/SHA1 is missing. The endpoint and UI do not execute rollback or mutate `artifacts/page_quality_model.pkl`; actual rollback remains a controlled engineering operation.

D44 / GitHub `#63` реализован локально как non-production second-pass competitor-aware score experiment. Backend modules `app/ml/second_pass.py` and `app/ml/second_pass_experiment.py` define the two-stage score contract, split-safe SERP-relative enrichment and offline candidate evaluation. Evidence: `artifacts/ranking-benchmarks/dataset-v3-d44/second-pass-experiment-report.json` and `.md`; non-production candidate: `artifacts/page_quality_model.dataset-v3-d44-second-pass-experiment.pkl` plus `.metadata.json`. Decision: `do_not_continue_without_more_evidence` because top-3 and NDCG@10 regressed despite a tiny MAE improvement. D44 does not change runtime scoring or mutate `artifacts/page_quality_model.pkl`.

Текущий backend/ML статус после product clarification:

- `D55` switched release policy to `d55-product-aligned-v1`: `top_3_hit_rate` is now SERP-alignment diagnostics, while `MAE`, `Spearman`, `NDCG@10`, bounded scores, feature dominance, score response and recommendation consistency are release guardrails.
- `D56` added `competitiveness-score-v1` after competitor aggregation. Backend preserves the model's `primary_page_score`, then writes final `audit.score` / `score_breakdown.final_score` as `competitiveness_score` when enough competitors were processed.
- `D57` added `competitor-gap-priority-v1` for recommendations. Recommendation priority now depends on competitor gap, SEO/search importance and controllability, not only on a raw metric difference.
- `D58` published `pointwise_catboost_v5` under the competitiveness scorecard. Current runtime artifact is `artifacts/page_quality_model.pkl`, SHA1 `5374ca30f48f70d8629e7d84ec3df0524ef35b52`, dataset `dataset-v5`, artifact version `dataset-v5-20260502151507`, schema `v3`, `CatBoostRegressor`, `148` features. The previous v3 runtime is preserved as rollback evidence in `artifacts/versions/page_quality_model--dataset-v3-d37-20260501200434.pkl`.
- `D59` and `D60` cleaned product-facing ML/debug clutter and clarified runtime assets versus archived research/evidence artifacts.
- `D61` aligns this README, the root README, the roadmap and the ML appendix with the current competitiveness goal.
- `D62-D68` add the final query-competitiveness contract. Query relevance is applied around the runtime model score, so pages unrelated to the query cannot stay in a medium range because of good generic SEO signals. `dataset-v7-final` currently contains final seeds only (`500` queries, `50` categories, top-10 policy, five cities); `app.ml.final_query_competitiveness` blocks training/publish until real collection and deterministic expert labels are present.
- `D69` prepares the live `dataset-v7-final` collection path: `app.ml.dataset_builder` supports `--max-domain-rows-per-domain` and records skipped rows in dataset metadata; `app.ml.final_hard_negatives` writes `dataset.with-hard-negatives.csv` by recomputing features from saved snapshots under different target queries. The final training pipeline now requires that hard-negative file when the v7 manifest says hard negatives are mandatory.
- `D70` introduces `query-relevance-contract-v2` and `query-relevance-early-stop-v1`. Confident full mismatch is now capped to `0-5` and marked as a future early-stop candidate; ambiguous mismatch continues the audit as `probable_mismatch` up to `25` so noisy vectorization does not prematurely stop rare but relevant pages.
- `D71` wires that preflight into audit orchestration. Target fetch now goes through feature extraction before heavy analysis; confident full mismatch finishes as a completed early-stop audit with `competitor_processing_status=skipped_early_stop`, no heavy-analysis/competitor fan-out and `comparison_summary.score_basis=query_relevance_early_stop`.
- `D72` makes early stop a stable runtime/API contract. Audit status, list, results and timeline diagnostics expose typed `early_stop` summary with score band, user-facing copy, skipped stages and competitor skip status.
- `D73-D74` add product UI/copy and regression coverage around this contract. The frontend shows `Страница не соответствует запросу` instead of raw ML/debug fields, while backend tests cover unrelated good pages, near-topic false positives, commercial modifiers, rare low-signal pages and insufficient extraction.
- `D75` completed live raw `dataset-v7-final` collection. Final raw coverage: `500/500` seed queries with successful rows, `3876` rows, `367` failures, `2253` unique domains, `50` categories, `5` cities and max single-domain repeat `12` under cap `12`. This is not training-ready: builder weak labels in `dataset.csv` are placeholders, deterministic expert labels and hard negatives are still required.
- `D76` materializes `dataset.with-hard-negatives.csv` from D75 snapshots. It adds `1000` hard negatives, `2` per query, with all `500` queries, all `50` target/source categories, `0` same-category pairs and `0` missing artifacts. Validation now passes hard-negative checks and blocks only on the intentional `manifest_ready_for_training=false`.

Если GitHub Issues недоступны из текущего окружения, actual source of truth находится в `../AGENTS.md`, `../README.md`, `../docs/roadmap/product-development-roadmap.md`, `../plans/d45-d49-seo-weighted-score-retraining.md`, `../plans/d50-d54-v5-ranking-aware-model.md`, `../plans/d55-d61-product-aligned-competitiveness.md`, `../plans/d62-d68-final-query-competitiveness.md`, `../plans/d69-dataset-v7-collection-readiness.md`, `../plans/d70-conservative-query-relevance-contract.md`, `../plans/d72-query-relevance-early-stop-runtime-contract.md`, `../plans/d71-d74-query-relevance-preflight-ui-regression.md`, `../plans/d75-dataset-v7-controlled-collection.md`, `../plans/d76-dataset-v7-hard-negatives.md` и older historical plans. Не повторять rollout или менять runtime scoring без явно выбранной новой задачи.
