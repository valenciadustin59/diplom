# Дорожная карта дальнейшего развития продукта Site Audit

Этот документ фиксирует практический план дальнейшего развития репозитория `E:\codexPROJ\diplom`. Он построен не как абстрактный список идей, а как последовательность продуктовых и инженерных шагов, которые можно переносить в GitHub issues почти без переписывания.

## Зачем нужен следующий этап развития

Текущая версия проекта уже закрывает базовый сценарий: пользователь запускает аудит страницы по поисковому запросу, система собирает целевую страницу и страницы конкурентов, рассчитывает score, показывает сравнение и формирует рекомендации. Однако для устойчивого использования и сильной дипломной презентации этого недостаточно. Следующий этап должен превратить проект из MVP-демонстрации в предсказуемый инструмент, который даёт воспроизводимый результат, объяснимую ML-оценку и удобный интерфейс для принятия решений.

В развитии проекта нужно последовательно усилить три направления: надёжность pipeline, качество ML-модели и аналитическую ценность результата для пользователя.

## Этап 1. Стабилизация MVP

На первом этапе нужно устранить основные технические риски. Пользовательский эффект от этого этапа должен быть простым: аудит чаще завершается успешно, а если возникает ошибка, она отображается явно и по понятной причине.

Приоритетные работы:

- нормализовать обработку ошибок на этапах `fetch`, `SERP search`, `competitor analysis` и `scoring`;
- сделать более прозрачное логирование этапов аудита в backend;
- ввести явные таймауты, retry-policy и защиту от зависающих background-задач;
- добавить интеграционные тесты для полного цикла `create audit -> processing -> results`;
- довести документацию локального запуска до состояния, когда новый разработчик поднимает стек без чтения кода.

## Этап 2. Доведение ML-части до основного рабочего режима

Это самый важный этап с точки зрения темы диплома. Сейчас проект уже использует hybrid-scoring подход, но следующий шаг должен перевести ML-модель из продвинутого MVP в полноценный основной механизм оценки.

Приоритетные работы:

- собрать production-like датасет на реальных RU commercial запросах;
- обучить основной артефакт модели на реальном датасете;
- зафиксировать и задокументировать метрики качества модели;
- добавить versioning артефактов и metadata: дата обучения, размер датасета, схема фич;
- сделать offline evaluation script для проверки новой модели перед публикацией.

Проверяемый результат: в `score_breakdown.model_info` runtime показывает, что итоговая оценка построена на реальном локально обученном артефакте, а не на bootstrap fallback.

## Этап 3. Усиление объяснимости и конкурентной аналитики

Следующая зона роста находится во frontend. Сейчас интерфейс показывает score, сравнение и рекомендации, но для практической SEO-работы важно быстрее понимать, почему страница проигрывает конкурентам и какие действия дадут наибольший эффект.

Приоритетные работы:

- добавить детальную карточку каждой конкурентной страницы с breakdown её признаков;
- показывать дельту пользователя относительно среднего по конкурентам по ключевым сигналам;
- расширить раздел рекомендаций фильтрацией по приоритету и типу проблемы;
- добавить экспорт результатов аудита в shareable report format;
- улучшить страницу истории запусков с поиском, фильтрами и повторным запуском аудита.

## Этап 4. Архитектурная декомпозиция и эксплуатационная устойчивость

Когда стабильность и объяснимость будут усилены, нужно убрать архитектурные узкие места. Сейчас основной orchestration сосредоточен в `backend/app/tasks.py`, что удобно для MVP, но плохо масштабируется по мере роста продукта.

Приоритетные работы:

- декомпозировать orchestration из `tasks.py` в pipeline services или application services;
- добавить более устойчивую стратегию retry и idempotent execution для Celery jobs;
- подготовить Docker-based full-stack локальное окружение;
- добавить health/readiness checks для backend и worker-стека;
- оценить необходимость разделения агрегата `Audit` на write model и отдельную read model результатов.

### Distributed Computing Backlog

Для темы диплома `Разработка web-приложения машинного обучения на основе распределённых вычислений` внутри этапа архитектуры зафиксирована отдельная последовательность distributed-задач. Она показывает не просто использование Celery, а поэтапное усиление реально распределённого runtime.

Уже выполнено:

- `D1` - разрезать monolithic `process_audit` на stage-based pipeline tasks
- `D2` - маршрутизировать стадии в отдельные Celery queues
- `D3` - вынести обработку competitor pages в distributed fan-out subtasks
- `D4` - сделать orchestration retry-safe и version-aware
- `D5` - добавить `health/live` и `health/ready` для backend/worker stack
- `D6` - добавить `health/metrics` и runtime telemetry для очередей, worker activity и pipeline counters

Следующий шаг:

- `D7` - сохранить структурированные execution events и stage duration telemetry в persistent audit event log, чтобы анализировать не только текущее состояние runtime, но и историю распределённого исполнения каждого аудита

Именно эта последовательность должна использоваться как актуальный distributed backlog для следующих GitHub issues и следующих задач `task 7+`.

## Этап 5. Продуктовые расширения

После стабилизации основы проект можно расширять в сторону реальной прикладной ценности для digital-команд.

Наиболее полезные направления:

- аудит не одной страницы, а нескольких посадочных страниц домена;
- кластеризация запросов и подбор релевантной страницы под каждый кластер;
- сравнение запусков во времени, чтобы отслеживать прогресс после доработок;
- поддержка нескольких проектов и доменов в одном интерфейсе;
- шаблоны рекомендаций по типу бизнеса: услуги, e-commerce, локальный бизнес.

## Рекомендуемый порядок реализации

Практически правильная последовательность такая:

1. Стабилизировать текущий pipeline и ошибки.
2. Довести ML training pipeline до реальной основной модели.
3. Усилить конкурентную аналитику и объяснимость интерфейса.
4. Выполнить архитектурную декомпозицию orchestration-слоя.
5. После этого расширять продукт функционально.

Этот порядок выбран потому, что он минимизирует технический риск и одновременно усиливает дипломную ценность проекта. Сначала нужна надёжность, затем содержательная ML-часть, затем глубина пользовательской аналитики.

## GitHub Task Backlog

Ниже приведён стартовый backlog задач. Формулировки можно переносить в GitHub issues почти без изменений.

### Epic 1. MVP Stability

- `Stabilize audit pipeline error handling and status transitions`
- `Add structured audit step logging for fetch, features, competitors and scoring`
- `Add backend integration tests for full audit lifecycle`
- `Document full local setup for backend, frontend, Redis and SearxNG`
- `Surface fetch/search/scoring failure reasons in frontend workspace`

### Epic 2. ML Quality

- `Collect production-like RU commercial dataset for page quality model`
- `Train and publish primary ML artifact from real dataset`
- `Add offline evaluation script with ranking-aware metrics`
- `Version model artifacts and expose dataset metadata in runtime`
- `Document ML methodology and model limitations for diploma appendix`

### Epic 3. UX and Analytics

- `Add competitor detail view with feature breakdown and score explanation`
- `Show delta versus competitors for key page signals`
- `Add recommendation grouping and filtering by priority`
- `Add audit result export to shareable report format`
- `Improve audit history with search, filters and rerun action`

### Epic 4. Architecture and Operations

- `Refactor monolithic tasks.py orchestration into pipeline services`
- `Introduce resilient retry strategy for Celery audit jobs`
- `Prepare Docker-based local full-stack environment`
- `Add health and readiness checks for backend worker stack`
- `Evaluate splitting Audit aggregate into write model and result read model`

### Epic 5. Product Expansion

- `Support multi-page audits for one domain`
- `Add query clustering and landing page matching`
- `Track audit progress over time with run-to-run comparison`
- `Add project workspace for multiple domains`
- `Add recommendation presets by business type`

## Что считать успешным ближайшим релизом

Ближайший релиз можно считать успешным, если одновременно выполняются четыре условия:

- новый разработчик поднимает проект локально по документации без скрытых ручных шагов;
- типовой аудит завершается предсказуемо и показывает внятную причину ошибки, если внешние сайты или SERP недоступны;
- runtime использует реальный ML-артефакт, а не bootstrap fallback;
- интерфейс показывает достаточно конкурентной аналитики, чтобы по результату можно было принять решение о доработках страницы.

## Примечание по GitHub

Этот документ специально оформлен как исходник для GitHub issue backlog. После публикации репозитория в `https://github.com/valenciadustin59/diplom` задачи из раздела `GitHub Task Backlog` нужно перенести в issues и при возможности сгруппировать по milestone или project board.
