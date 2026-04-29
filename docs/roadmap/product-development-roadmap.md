# Roadmap текущего этапа Site Audit

Этот документ нужен как читаемый стратегический ориентир для разработчиков и Codex-агентов. Операционный handoff, ограничения и актуальные ссылки на GitHub issues всегда начинаются с `AGENTS.md`; этот roadmap объясняет, куда развивать проект дальше и какие завершённые волны не нужно повторять.

Проект находится в репозитории `E:\codexPROJ\diplom`. Тема диплома: web-приложение машинного обучения на основе распределённых вычислений. Поэтому roadmap оценивается не только по SEO-функциям, но и по тому, насколько хорошо проект демонстрирует ML workflow, distributed runtime и понятный web-интерфейс.

## Текущий статус

Базовый пользовательский сценарий уже реализован: пользователь вводит поисковый запрос и URL, система собирает конкурентные страницы из SERP, анализирует target и competitors, считает ML score, сравнивает страницу с конкурентами и формирует рекомендации.

Завершённые волны:

- `D1-D12` — distributed runtime foundation: stage-based Celery pipeline, per-stage queues, distributed fan-out, retry-safe orchestration, health/live, health/ready, health/metrics, event log, timeline diagnostics, queue pressure, admission control, worker topology profiles и benchmark/reporting workflow.
- `D13-D22` — SEO/ML/product/frontend evidence wave: snapshot extraction, feature schema v2, technical SEO features, commercial/trust features, intent-aware and SERP-relative features, dataset-v2 workflow, model schema v2, artifact-driven training/publish flow, grouped recommendations API/UI, isolated `audits.heavy_analysis` queue, audit report/export dashboard и audit execution timeline UI.

После `D22` проект уже соответствует дипломной теме, имеет отдельный report/export view и dedicated timeline UI для демонстрации distributed runtime. Следующий этап должен в первую очередь углублять frontend-доказательную базу runtime health, а не переписывать backend runtime или добавлять новый анализ без необходимости.

## Активная волна: D22-D26 Frontend/Product Layer

Эта волна заведена в GitHub как open issues `#40-#45`. Demo mode намеренно не входит в текущий backlog: пользователь выбрал развивать продуктовые и демонстрационные возможности без отдельного демо-режима.

### D21 / #40: Audit Report And Export Dashboard

Статус: выполнено.

Цель — дать пользователю единый отчёт по аудиту, который можно открыть, показать и экспортировать.

Реализованный состав:

- отдельная вкладка `Отчёт` для выбранного аудита;
- score, статус, поисковый запрос, target URL, конкуренты и ключевые проблемы;
- grouped recommendations и score explanation в компактной форме;
- существующие distributed-runtime evidence из `events/diagnostics`;
- экспорт в printable HTML/PDF-like view, downloadable HTML и downloadable Markdown artifact.

Приёмка выполнена: завершённый аудит открывается как цельный отчёт, а экспорт/печать работают без devtools и без повторного анализа страницы.

### D22 / #41: Audit Execution Timeline UI

Статус: выполнено.

Цель — визуально показать жизненный цикл распределённого аудита.

Реализованный состав:

- вкладка `Таймлайн` в audit workspace;
- timeline стадий `pipeline`, `fetch`, `heavy_analysis`, `features`, `scoring`, `competitors`, `competitor_page`, `competitor_analysis`, `competitor_aggregation`, `recommendations`, `finalize`;
- raw event stream из `GET /audits/{audit_id}/events`;
- длительности, ошибки, warnings, queues, fan-out summary и critical-path hints из existing events/diagnostics API;
- понятное состояние для completed, completed_with_warnings, failed и старых audits без event log.

Приёмка выполнена: пользователь может открыть аудит и понять, какие стадии прошли, где была задержка или ошибка, какие очереди/workers участвовали, где был fan-out и как это связано с распределённой архитектурой.

### D23 / #42: Runtime Status And Queue Health UI

Цель — сделать состояние локального distributed stack понятным до запуска аудита и во время работы.

Ожидаемый состав:

- компактная панель состояния API, Redis, SearxNG, worker profiles и queues;
- отображение missing workers, queue pressure, backlog и readiness;
- человекочитаемые сообщения для admission-control ошибок и очередей без активных workers.

Приёмка: пользователь видит, готов ли runtime к новым аудитам, и понимает, что именно нужно восстановить при проблеме.

### D24 / #43: Audit History Management

Цель — превратить историю аудитов из пассивного списка в рабочую панель.

Ожидаемый состав:

- действия `повторить аудит`, `открыть последний успешный`, безопасно удалить или скрыть локальный audit row;
- фильтры по статусу, домену, запросу и проблемным/stale запускам;
- аккуратное разделение dev-only cleanup и обычного product behavior.

Приёмка: пользователь быстро находит нужный аудит, повторяет запуск и очищает локальную историю без риска случайно сломать данные.

### D25 / #44: Recommendation Action Tracking

Цель — сделать рекомендации планом работ, а не только текстом.

Ожидаемый состав:

- состояния для рекомендаций: например, `не начато`, `в работе`, `исправлено`, `игнорируется`;
- сохранение состояния локально или через минимальное backend-поле, если это потребуется;
- summary прогресса по группам рекомендаций.

Приёмка: пользователь может отмечать прогресс по рекомендациям, а страница рекомендаций показывает, сколько действий уже закрыто.

### D26 / #45: Interface Copy And Terminology Polish

Цель — сделать язык интерфейса стабильным, понятным и пригодным для дипломной демонстрации.

Ожидаемый состав:

- пройтись по видимым строкам UI и убрать лишнее смешение `score`, `gap`, `semantic`, внутренних кодов и русских подписей;
- оставить технические детали вторым уровнем, но добавить человеческие primary labels;
- исправить оставшиеся mojibake/awkward strings в frontend-facing copy и документации.

Приёмка: основные экраны понятны человеку без знания внутренних API-кодов, а техническая детализация остаётся доступной там, где она полезна.

## Отложенные направления

Эти направления полезны, но не являются ближайшим фокусом:

- ML evidence hardening: expert labels для `dataset-v2`, ranking benchmark, обновление `backend/docs/ml_methodology_appendix.md`;
- SEO depth extensions: schema.org/JSON-LD recommendations, optional PageSpeed/Lighthouse integration, site-wide crawl как отдельная крупная волна;
- multi-project/domain management и сравнение аудитов во времени.

Их стоит брать только после закрытия или явного отложения `D22-D26`, чтобы не распылять дипломную демонстрацию.

## Как пользоваться roadmap

Перед началом новой задачи агент или разработчик должен:

1. Прочитать `AGENTS.md` и `README.md`.
2. Проверить `git status`.
3. Если задача не задана явно, выбрать следующий open GitHub issue из `D23-D26`, начиная с `D23` / `#42`.
4. Не откатывать `D13-D22` без прямой причины.
5. Если нужен GitHub, использовать локальный credential helper или запросить токен вручную, не печатая секреты в чат, logs или файлы.

Канонический статус сейчас: `D1-D22` завершены, активный практический backlog — `D23-D26` frontend/product layer, первый приоритет — runtime status and queue health UI.
