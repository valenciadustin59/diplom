# Довести training pipeline до реальной основной ML-модели для RU MVP

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This document must be maintained in accordance with [PLANS.md](/E:/codexPROJ/diplom/PLANS.md).

## Purpose / Big Picture

После этой работы backend должен уметь не только считать score через bootstrap fallback, но и обучать и использовать реальную локальную модель на страницах из RU commercial выдачи. Проверяемый пользовательский результат такой: из `backend/` можно сгенерировать seed pack, собрать CSV-датасет через бесплатный SearxNG JSON API или через HTML fallback, обучить модель, получить `artifacts/page_quality_model.pkl`, а затем запустить аудит и увидеть в `score_breakdown.model_info`, что scoring идёт из локально обученного артефакта.

## Progress

- [x] (2026-04-15 18:42 +05:00) Добавлен `backend/app/serp.py` с provider-слоем для бесплатного SearxNG JSON API, нормализацией results и конфигурацией через `SEARXNG_BASE_URL`.
- [x] (2026-04-15 18:46 +05:00) `backend/app/competitors.py` переведён на provider-first lookup; HTML scrape оставлен как fallback/debug path.
- [x] (2026-04-15 18:52 +05:00) `backend/app/ml/dataset_builder.py` переписан под `training_query_seeds.csv`, `training_failures.csv`, checkpoint/resume и metadata columns.
- [x] (2026-04-15 18:57 +05:00) `backend/app/ml/train.py` переведён на group-based split по `query`, ranking-aware metrics и optional CatBoost benchmark.
- [x] (2026-04-15 19:02 +05:00) `backend/app/ml/model.py` обновлён: runtime использует реальный артефакт как primary model, fallback срабатывает только при отсутствии или несовместимости артефакта, в `score_breakdown` добавлен `model_info`.
- [x] (2026-04-15 19:05 +05:00) Добавлены `backend/.env.example`, новый `scripts/generate_training_queries.py`, `scripts/run_training_batches.py`, обновлены `backend/README.md` и `AGENTS.md`.
- [x] (2026-04-15 19:08 +05:00) Сгенерирован `backend/data/training_query_seeds.csv` на 200 RU commercial seed-запросов и обновлён `backend/data/training_queries.txt`.
- [x] (2026-04-15 19:11 +05:00) Тесты обновлены под новый pipeline; `pytest` проходит полностью.
- [ ] (2026-04-15 19:11 +05:00) Собрать live датасет на `1500-2000` успешных страниц через SearxNG JSON API или стабильный HTML fallback.
- [ ] (2026-04-15 19:11 +05:00) Обучить production-like артефакт `backend/artifacts/page_quality_model.pkl` на реальном CSV.
- [ ] (2026-04-15 19:11 +05:00) Провести smoke-аудит с реальным артефактом и зафиксировать evidence, что runtime берёт `source=local_dataset`.

## Surprises & Discoveries

- Observation: массовый dataset build нельзя честно считать завершённым без стабильного provider API; HTML scraping search pages слишком нестабилен для repeatable MVP.
  Evidence: именно поэтому training path переведён на `backend/app/serp.py`, а HTML scrape оставлен только fallback-веткой.

- Observation: ranking-aware quality нельзя оценивать простым row-level split, потому что страницы одного и того же запроса начинают утекать и в train, и в validation.
  Evidence: `backend/app/ml/train.py` теперь использует `GroupShuffleSplit` по `query`.

- Observation: runtime должен не silently принимать несовместимый артефакт, а явно уходить в fallback.
  Evidence: `backend/app/ml/model.py` валидирует `feature_columns` и пишет warning при откате к bootstrap.

- Observation: бесплатный режим теперь не заблокирован внешним секретом, но качество и стабильность выдачи зависит от доступности выбранного SearxNG instance.
  Evidence: provider переведён на `SEARXNG_BASE_URL`, а dataset builder умеет откатываться на HTML fallback.

## Decision Log

- Decision: основным бесплатным provider для MVP выбран `SearxNG JSON API`, а HTML scraping оставлен fallback-веткой.
  Rationale: это снимает обязательную зависимость от платного API и даёт более чистый JSON-путь, чем прямой HTML scraping.
  Date/Author: 2026-04-15 / Codex

- Decision: seed pack переведён с plain-text query list на структурированный `training_query_seeds.csv`.
  Rationale: training pipeline должен знать не только сам запрос, но и `category`, `intent`, `city`, `region_code`, `top_n`, `pages_to_scan`.
  Date/Author: 2026-04-15 / Codex

- Decision: real-model runtime интегрирован без смены публичных audit endpoints.
  Rationale: scoring должен улучшиться без ломающего рефакторинга API или фронтенда.
  Date/Author: 2026-04-15 / Codex

- Decision: baseline модель оставлена `RandomForestRegressor`, а `CatBoostRegressor` включён как benchmark path только при слабой ranking-aware валидации.
  Rationale: это минимально рискованный способ получить working MVP и не завязать весь runtime на новую модель без фактических метрик.
  Date/Author: 2026-04-15 / Codex

- Decision: batch workflow оформлен отдельным скриптом `scripts/run_training_batches.py`.
  Rationale: так проще собирать датасет пакетами по 60 seed-ов и автоматически стартовать обучение после достижения целевого объёма.
  Date/Author: 2026-04-15 / Codex

## Outcomes & Retrospective

Промежуточный итог на 2026-04-15: кодовая часть real training pipeline доведена до рабочего состояния. В репозитории уже есть единый provider-слой, структурированный RU seed pack, dataset builder с failures/checkpoint, ranking-aware training и runtime metadata. Основной незавершённый кусок теперь не в секрете, а в фактическом длительном live collection: нужно выбрать рабочий `SEARXNG_BASE_URL` или опереться на fallback, собрать `1500-2000` успешных страниц и обучить production-like артефакт на реальном CSV.

## Context and Orientation

В этом репозитории backend находится в `backend/`. Для реализации и проверки этого плана важны следующие файлы:

- `backend/app/serp.py` — единый слой поиска через SearxNG JSON API.
- `backend/app/competitors.py` — production lookup конкурентных страниц.
- `backend/app/ml/dataset_builder.py` — массовый сбор training CSV.
- `backend/app/ml/train.py` — обучение, split и метрики.
- `backend/app/ml/model.py` — runtime scoring и fallback.
- `backend/data/training_query_seeds.csv` — основной RU seed pack.
- `scripts/generate_training_queries.py` — генератор seed pack.
- `scripts/run_training_batches.py` — batch workflow.

Термины:

- Provider: модуль, который получает поисковую выдачу через официальный API, а не через парсинг HTML.
- Checkpoint: JSON-файл, который помнит уже обработанные query/page комбинации и не даёт продублировать строки при повторном запуске.
- Ranking-aware metric: метрика, которая оценивает не только ошибку по числам, но и то, насколько правильно модель упорядочивает страницы внутри одного запроса.

## Plan of Work

Сначала подготовить локальное окружение backend и при желании заполнить `backend/.env` значением `SEARXNG_BASE_URL`. Затем сгенерировать или обновить `backend/data/training_query_seeds.csv` через `scripts/generate_training_queries.py`. После этого запускать dataset build либо одним проходом через `app.ml.dataset_builder`, либо пакетами через `scripts/run_training_batches.py`.

Когда CSV дойдёт минимум до `1500` успешных строк, выполнить `app.ml.train` и сохранить `backend/artifacts/page_quality_model.pkl`. Затем поднять backend, создать новый аудит и проверить, что в `GET /audits/{id}/results` поле `score_breakdown.model_info.source` равно `local_dataset`.

## Concrete Steps

Рабочая директория для команд ниже: `E:\codexPROJ\diplom\backend`.

Сгенерировать RU commercial seed pack:

    .\.venv\Scripts\python.exe ..\scripts\generate_training_queries.py

Собрать dataset одним прогоном:

    .\.venv\Scripts\python.exe -m app.ml.dataset_builder --seeds-file data\training_query_seeds.csv --output data\training_dataset.csv --failures-output data\training_failures.csv --checkpoint data\training_dataset.checkpoint.json --overwrite --max-workers 2 --query-delay 1.0

Собрать dataset пакетами и автоматически обучить модель после достижения целевого объёма:

    .\.venv\Scripts\python.exe ..\scripts\run_training_batches.py --seeds-file data\training_query_seeds.csv --dataset data\training_dataset.csv --failures data\training_failures.csv --checkpoint data\training_dataset.checkpoint.json --batch-size 60 --target-rows 1800 --max-workers 2 --query-delay 1.0 --model-output artifacts\page_quality_model.pkl

Обучить модель вручную на уже собранном CSV:

    .\.venv\Scripts\python.exe -m app.ml.train --dataset data\training_dataset.csv --model-output artifacts\page_quality_model.pkl

Проверить тесты:

    .\.venv\Scripts\python.exe -m pytest

## Validation and Acceptance

Проверка считается успешной, если выполняются все условия:

1. Без `SEARXNG_BASE_URL` система может продолжить работу через HTML fallback, а при наличии `SEARXNG_BASE_URL` использует бесплатный JSON provider.
2. `backend/data/training_query_seeds.csv` существует и содержит 200 seed rows, то есть 25 категорий на 8 городов.
3. После live collection основной CSV содержит не менее `1500` успешных строк, а failures пишутся отдельно в `training_failures.csv`.
4. `app.ml.train` создаёт `backend/artifacts/page_quality_model.pkl`, а metadata внутри артефакта содержит `source=local_dataset`.
5. После старта backend новый аудит доходит до `completed`, а `score_breakdown.model_info.source` указывает на `local_dataset`.

## Idempotence and Recovery

`scripts/generate_training_queries.py` можно запускать повторно: он просто пересобирает seed CSV и legacy txt. Dataset build безопасно повторяется с checkpoint-файлом. Если нужен чистый прогон, удалить или перезаписать:

- `backend/data/training_dataset.csv`
- `backend/data/training_failures.csv`
- `backend/data/training_dataset.checkpoint.json`

Если новый артефакт модели оказался плохим, достаточно удалить `backend/artifacts/page_quality_model.pkl`; runtime автоматически вернётся к bootstrap fallback.

## Artifacts and Notes

Ключевые артефакты:

- `backend/data/training_query_seeds.csv`
- `backend/data/training_queries.txt`
- `backend/data/training_dataset.csv`
- `backend/data/training_failures.csv`
- `backend/data/training_dataset.checkpoint.json`
- `backend/artifacts/page_quality_model.pkl`

Текущее подтверждение работоспособности кода:

    ======================== 19 passed in 2.26s ========================

## Interfaces and Dependencies

В `backend/app/serp.py` должен существовать интерфейс:

    def search(query: str, top_n: int, region_code: int | None = None, page: int = 0) -> list[dict[str, object]]

В `backend/app/ml/dataset_builder.py` должны существовать:

    def load_seed_rows(seeds_file: str | Path = DEFAULT_SEEDS_PATH, default_top_n: int = 10) -> list[TrainingSeed]
    def build_dataset(...) -> dict[str, object]

В `backend/app/ml/train.py` должны существовать:

    def load_dataset_rows(dataset_path: str | Path = DEFAULT_DATASET_PATH) -> list[dict[str, str]]
    def train_quality_model(...) -> dict[str, object]

В `backend/app/ml/model.py` должны существовать:

    def predict_score(features: dict[str, float | int], model_path: str | Path | None = None) -> float
    def explain_score(features: dict[str, float | int], model_path: str | Path | None = None) -> dict[str, object]
    def load_saved_model(model_path: str | Path | None = None) -> dict[str, object] | None

Используемые зависимости:

- `httpx` для SearxNG JSON API и загрузки страниц;
- `scikit-learn` для baseline модели и split logic;
- `catboost` для benchmark path;
- `sentence-transformers` для semantic features;
- `pickle` для хранения артефакта модели.

Revision note: документ обновлён после перевода search provider с платного SerpApi на бесплатный SearxNG JSON API с HTML fallback, чтобы отразить новый бесплатный путь для dataset collection.
