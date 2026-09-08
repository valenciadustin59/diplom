# Развёртывание на сервере

Этот документ описывает общий подход к размещению проекта на VPS или сервере компании.

## Рекомендуемая среда

- Ubuntu 24.04 LTS;
- Docker и Docker Compose;
- Node.js 20+;
- Python 3.12 или 3.13;
- Nginx как reverse proxy;
- HTTPS-сертификат через Let's Encrypt.

## Компоненты на сервере

На сервере должны работать:

- backend API на FastAPI;
- Celery workers;
- Redis;
- SearXNG;
- frontend-сборка;
- SQLite-база или внешний сервер БД при развитии проекта;
- Nginx для маршрутизации HTTP/HTTPS.

## Базовая схема

```text
Internet
  |
  v
Nginx + HTTPS
  |
  +--> frontend static build
  |
  +--> FastAPI backend
          |
          +--> SQLite
          +--> Redis
          +--> Celery workers
          +--> SearXNG
          +--> CatBoost model artifact
```

## Общий порядок развёртывания

1. Установить системные пакеты.
2. Склонировать репозиторий.
3. Создать backend virtual environment.
4. Установить backend и frontend зависимости.
5. Настроить `.env`.
6. Запустить Redis и SearXNG.
7. Собрать frontend.
8. Запустить backend и Celery workers как systemd-сервисы или через Docker.
9. Настроить Nginx.
10. Выпустить HTTPS-сертификат.
11. Проверить `/health/live`, `/health/ready` и запуск тестового аудита.

## Важные замечания

- Не храните реальные пароли и токены в GitHub.
- Файл `.env` должен создаваться на сервере вручную.
- SQLite подходит для демонстрационного и небольшого внутреннего использования.
- Для постоянной промышленной эксплуатации лучше вынести БД в PostgreSQL.
- Активная ML-модель должна находиться в `backend/artifacts/page_quality_model.pkl`.
- Вспомогательные датасеты и benchmark-отчёты не нужны для работы сайта.
