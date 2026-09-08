# Запуск проекта на macOS

Инструкция рассчитана на локальный запуск проекта из терминала macOS.

## 1. Установить системные зависимости

Установите Xcode Command Line Tools:

```bash
xcode-select --install
```

Установите:

- Git;
- Node.js 20+;
- Python 3.12 или 3.13;
- Docker Desktop.

Проверка:

```bash
git --version
node --version
npm --version
python3 --version
docker --version
```

## 2. Скачать проект

```bash
git clone https://github.com/valenciadustin59/diplom.git
cd diplom
```

## 3. Установить зависимости frontend

```bash
npm install
npm --prefix frontend install
```

## 4. Подготовить backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cd ..
```

## 5. Запустить Docker Desktop

Откройте Docker Desktop и дождитесь, пока Docker Engine станет активным.

## 6. Запустить проект

```bash
chmod +x scripts/macos/start-site.sh scripts/macos/stop-site.sh
./scripts/macos/start-site.sh
```

После запуска откройте:

```text
http://127.0.0.1:5173
```

## 7. Остановить проект

```bash
./scripts/macos/stop-site.sh
```

## Что делает start-site.sh

Скрипт:

- проверяет наличие Node.js, npm, Python и Docker;
- запускает Redis и SearXNG через Docker Compose;
- проверяет доступность SearXNG;
- запускает backend, frontend и Celery workers через существующий `npm run dev:full`;
- выводит адрес интерфейса.

## Частые проблемы на macOS

**Docker daemon is not running**

Запустите Docker Desktop и повторите команду.

**python3: command not found**

Установите Python 3.12 или 3.13.

**Port 5173 is already in use**

Остановите старый frontend-процесс или задайте другой порт:

```bash
FRONTEND_PORT=5174 ./scripts/macos/start-site.sh
```

**Permission denied для shell-скрипта**

Выполните:

```bash
chmod +x scripts/macos/start-site.sh scripts/macos/stop-site.sh
```
