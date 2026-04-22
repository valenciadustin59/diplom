# Site Audit

Р’РµР±-РїСЂРёР»РѕР¶РµРЅРёРµ РґР»СЏ Р°РІС‚РѕРјР°С‚РёР·РёСЂРѕРІР°РЅРЅРѕРіРѕ SEO-Р°СѓРґРёС‚Р° РїРѕСЃР°РґРѕС‡РЅС‹С… СЃС‚СЂР°РЅРёС† РїРѕ РїРѕРёСЃРєРѕРІРѕРјСѓ Р·Р°РїСЂРѕСЃСѓ. РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ СѓРєР°Р·С‹РІР°РµС‚ Р·Р°РїСЂРѕСЃ Рё URL СЃРІРѕРµР№ СЃС‚СЂР°РЅРёС†С‹, РїРѕСЃР»Рµ С‡РµРіРѕ СЃРёСЃС‚РµРјР° РЅР°С…РѕРґРёС‚ РєРѕРЅРєСѓСЂРµРЅС‚РѕРІ, СЃРѕР±РёСЂР°РµС‚ РїСЂРёР·РЅР°РєРё СЃС‚СЂР°РЅРёС†С‹, СЃС‡РёС‚Р°РµС‚ ML score, СЃСЂР°РІРЅРёРІР°РµС‚ СЂРµР·СѓР»СЊС‚Р°С‚ СЃ SERP Рё С„РѕСЂРјРёСЂСѓРµС‚ СЂРµРєРѕРјРµРЅРґР°С†РёРё.

## Р§С‚Рѕ РЅР°С…РѕРґРёС‚СЃСЏ РІ СЂРµРїРѕР·РёС‚РѕСЂРёРё

- `backend/` вЂ” FastAPI API, SQLite, Celery orchestration Рё ML scoring pipeline
- `frontend/` вЂ” React + TypeScript РёРЅС‚РµСЂС„РµР№СЃ РґР»СЏ Р·Р°РїСѓСЃРєР° Р°СѓРґРёС‚РѕРІ Рё РїСЂРѕСЃРјРѕС‚СЂР° СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ
- `docker-compose.searxng.yml` вЂ” Р»РѕРєР°Р»СЊРЅС‹Р№ Docker stack РґР»СЏ `SearxNG` Рё `Redis`
- `scripts/` вЂ” root-level dev scripts Рё СѓС‚РёР»РёС‚С‹ Р»РѕРєР°Р»СЊРЅРѕР№ СЂР°Р·СЂР°Р±РѕС‚РєРё
- `docs/roadmap/` вЂ” roadmap Рё GitHub backlog РґР°Р»СЊРЅРµР№С€РµРіРѕ СЂР°Р·РІРёС‚РёСЏ

## Distributed Backlog Status

### D12 Update

`D12` is implemented. The distributed backlog `D1-D12` is now complete.

The benchmark/reporting workflow measures the real runtime surface instead of a synthetic demo path:

- `POST /audits` records admission and launch behavior.
- `GET /audits/{audit_id}` tracks lifecycle completion for each benchmark audit.
- `GET /audits/{audit_id}/events/diagnostics` provides end-to-end latency and critical-path timing.
- `GET /health/metrics` provides backlog, queue pressure, worker utilization and runtime alerts.

Reports are written to `backend/artifacts/benchmarks/<timestamp>-<benchmark-name>/` as `benchmark-report.json` and `benchmark-report.md`.

Р”Р»СЏ С‚РµРєСѓС‰РµРіРѕ СЌС‚Р°РїР° РґРёРїР»РѕРјР° РєР°РЅРѕРЅРёС‡РµСЃРєРёРј backlog СЃС‡РёС‚Р°РµС‚СЃСЏ РЅРµ СЃС‚Р°СЂС‹Р№ product backlog, Р° distributed sequence `D1-D12`.

РЈР¶Рµ РІС‹РїРѕР»РЅРµРЅРѕ:

- `D1` вЂ” stage-based decomposition audit pipeline
- `D2` вЂ” routing СЃС‚Р°РґРёР№ РїРѕ РѕС‚РґРµР»СЊРЅС‹Рј Celery queues
- `D3` вЂ” distributed fan-out РїРѕ competitor pages
- `D4` вЂ” retry-safe / version-aware orchestration
- `D5` вЂ” `health/live` Рё `health/ready`
- `D6` вЂ” `health/metrics` Рё runtime telemetry
- `D7` вЂ” persistent audit event log Рё stage duration telemetry
- `D8` вЂ” audit timeline diagnostics API Рё critical-path breakdown
- `D9` вЂ” queue pressure snapshots Рё stuck/backlogged execution detector
- `D10` вЂ” admission control Рё scheduling guards РїСЂРё РґРµРіСЂР°РґРёСЂРѕРІР°РЅРЅРѕРј runtime capacity
- `D11` вЂ” worker topology profiles Рё queue affinity validation

Р•С‰С‘ РїСЂРµРґСЃС‚РѕРёС‚:

- `D12` вЂ” benchmark/reporting workflow РґР»СЏ РґРµРјРѕРЅСЃС‚СЂР°С†РёРё distributed runtime РІ РґРёРїР»РѕРјРµ

РџРѕРґСЂРѕР±РЅС‹Р№ СЃС‚Р°С‚СѓСЃ Рё РїРѕСЃР»РµРґРѕРІР°С‚РµР»СЊРЅРѕСЃС‚СЊ РЅР°С…РѕРґСЏС‚СЃСЏ РІ [docs/roadmap/product-development-roadmap.md](./docs/roadmap/product-development-roadmap.md).

## РўСЂРµР±РѕРІР°РЅРёСЏ

- `Python 3.12` РёР»Рё `3.13`
- `Node.js 20+` Рё 
pm`
- `Docker Desktop` РёР»Рё СЃРѕРІРјРµСЃС‚РёРјС‹Р№ Docker runtime

РџРµСЂРµРґ Р·Р°РїСѓСЃРєРѕРј 
pm run dev:full` Рё 
pm run searxng:*` СѓР±РµРґРёС‚РµСЃСЊ, С‡С‚Рѕ Docker Desktop СѓР¶Рµ Р·Р°РїСѓС‰РµРЅ Рё Docker daemon СѓСЃРїРµР» РїРѕРґРЅСЏС‚СЊСЃСЏ.

Р’Рѕ РІСЃРµС… РєРѕРјР°РЅРґР°С… РЅРёР¶Рµ `<repo-root>` РѕР·РЅР°С‡Р°РµС‚ РєРѕСЂРµРЅСЊ СЌС‚РѕРіРѕ СЂРµРїРѕР·РёС‚РѕСЂРёСЏ.

## Р РµРєРѕРјРµРЅРґСѓРµРјС‹Р№ СЂРµР¶РёРј: РїРѕР»РЅС‹Р№ Р»РѕРєР°Р»СЊРЅС‹Р№ СЃС‚РµРє

Р­С‚РѕС‚ СЂРµР¶РёРј СЂРµРєРѕРјРµРЅРґСѓРµС‚СЃСЏ РґР»СЏ РѕР±С‹С‡РЅРѕР№ СЂР°Р·СЂР°Р±РѕС‚РєРё Рё РґРµРјРѕРЅСЃС‚СЂР°С†РёРё РґРёРїР»РѕРјР°. РћРЅ РїРѕРґРЅРёРјР°РµС‚ РїРѕРёСЃРє, Redis, backend, frontend Рё Celery worker.

### 1. РЈСЃС‚Р°РЅРѕРІРёС‚СЊ root Рё frontend Р·Р°РІРёСЃРёРјРѕСЃС‚Рё

```powershell
cd <repo-root>
npm install
npm --prefix frontend install
```

### 2. РџРѕРґРіРѕС‚РѕРІРёС‚СЊ backend РѕРєСЂСѓР¶РµРЅРёРµ

```powershell
cd <repo-root>
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
copy .env.example .env
```

Р•СЃР»Рё РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ `Python 3.13`, РєРѕРјР°РЅРґР° СѓСЃС‚Р°РЅРѕРІРєРё РѕСЃС‚Р°С‘С‚СЃСЏ С‚РѕР№ Р¶Рµ, РµСЃР»Рё С‚РµРєСѓС‰РёР№ `pyproject.toml` РµС‘ РґРѕРїСѓСЃРєР°РµС‚.

### 3. Р—Р°РїСѓСЃС‚РёС‚СЊ РїРѕР»РЅС‹Р№ Р»РѕРєР°Р»СЊРЅС‹Р№ СЃС‚РµРє

```powershell
cd <repo-root>
npm run dev:full
```

РљРѕРјР°РЅРґР° РґРµР»Р°РµС‚ СЃР»РµРґСѓСЋС‰РµРµ:

- РїРѕРґРЅРёРјР°РµС‚ Docker services `diplom-searxng` Рё `diplom-searxng-redis`
- РїСЂРѕРІРµСЂСЏРµС‚ РґРѕСЃС‚СѓРїРЅРѕСЃС‚СЊ `SearxNG` РїРѕ `http://127.0.0.1:8888`
- Р·Р°РїСѓСЃРєР°РµС‚ backend API РЅР° СЃРІРѕР±РѕРґРЅРѕРј Р»РѕРєР°Р»СЊРЅРѕРј РїРѕСЂС‚Сѓ, РЅР°С‡РёРЅР°СЏ СЃ `8000`
- Р·Р°РїСѓСЃРєР°РµС‚ frontend Рё РїСЂРѕРєРёРґС‹РІР°РµС‚ РІ РЅРµРіРѕ Р°РєС‚СѓР°Р»СЊРЅС‹Р№ `VITE_API_URL`
- Р·Р°РїСѓСЃРєР°РµС‚ Celery worker РґР»СЏ stage-based audit queues

Р•СЃР»Рё `backend/.env` РѕС‚СЃСѓС‚СЃС‚РІСѓРµС‚, root dev script СЃР°Рј РїРѕРґСЃС‚Р°РІР»СЏРµС‚ Р»РѕРєР°Р»СЊРЅС‹Рµ dev defaults РґР»СЏ `SEARXNG_BASE_URL`, `CELERY_BROKER_URL` Рё `CELERY_RESULT_BACKEND`, С‡С‚РѕР±С‹ РїРѕР»РЅС‹Р№ СЃС‚РµРє РЅРµ Р·Р°РїСѓСЃРєР°Р»СЃСЏ РІ РґРµРіСЂР°РґРёСЂРѕРІР°РЅРЅРѕРј СЂРµР¶РёРјРµ.

РќР° Windows worker Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё СЃС‚Р°СЂС‚СѓРµС‚ СЃ `--pool=solo`, РїРѕС‚РѕРјСѓ С‡С‚Рѕ СЌС‚Рѕ СЃР°РјС‹Р№ РЅР°РґС‘Р¶РЅС‹Р№ СЂРµР¶РёРј РґР»СЏ Р»РѕРєР°Р»СЊРЅРѕРіРѕ Р·Р°РїСѓСЃРєР° Celery.

## Р СѓС‡РЅРѕР№ Р·Р°РїСѓСЃРє РїРѕ С‡Р°СЃС‚СЏРј

Р­С‚РѕС‚ СЂРµР¶РёРј СѓРґРѕР±РµРЅ, РµСЃР»Рё РЅСѓР¶РЅРѕ РѕС‚РґРµР»СЊРЅРѕ РїРµСЂРµР·Р°РїСѓСЃРєР°С‚СЊ С‚РѕР»СЊРєРѕ РѕРґРёРЅ РєРѕРјРїРѕРЅРµРЅС‚.

### РРЅС„СЂР°СЃС‚СЂСѓРєС‚СѓСЂР°: SearxNG Рё Redis

```powershell
cd <repo-root>
npm run searxng:up
npm run searxng:check
```

РџРѕСЃР»Рµ Р·Р°РїСѓСЃРєР° РґРѕСЃС‚СѓРїРЅС‹:

- `SearxNG`: `http://127.0.0.1:8888`
- `Redis`: `redis://127.0.0.1:6379/0`

### Backend API

```powershell
cd <repo-root>
cd backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Celery workers

Starting with `D11`, `npm run dev:full` launches three queue-affinity profiles (`pipeline`, `network`, `cpu_ml`). The single all-queues worker command below is now a legacy fallback for debugging only; the canonical topology for `health/ready` is the three profile workers shown after it.

```powershell
cd <repo-root>
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.pipeline,audits.fetch,audits.features,audits.scoring,audits.competitors,audits.competitor_pages,audits.recommendations,audits.finalize --pool=solo
```

Р”Р»СЏ Linux/macOS С„Р»Р°Рі `--pool=solo` РјРѕР¶РЅРѕ СѓР±СЂР°С‚СЊ, РЅРѕ РґР»СЏ Windows РµРіРѕ Р»СѓС‡С€Рµ РѕСЃС‚Р°РІРёС‚СЊ.

Р•СЃР»Рё РЅСѓР¶РЅРѕ СЏРІРЅРѕ СЂР°Р·РґРµР»РёС‚СЊ РЅР°РіСЂСѓР·РєСѓ РјРµР¶РґСѓ worker-РїСЂРѕС†РµСЃСЃР°РјРё, РјРѕР¶РЅРѕ РїРѕРґРЅРёРјР°С‚СЊ РёС… РїРѕ РіСЂСѓРїРїР°Рј РѕС‡РµСЂРµРґРµР№:

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

## РќР°СЃС‚СЂРѕР№РєРё РѕРєСЂСѓР¶РµРЅРёСЏ backend

РњРёРЅРёРјР°Р»СЊРЅР°СЏ Р»РѕРєР°Р»СЊРЅР°СЏ РєРѕРЅС„РёРіСѓСЂР°С†РёСЏ РѕРїРёСЃР°РЅР° РІ [`backend/.env.example`](./backend/.env.example):

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

Р•СЃР»Рё `SEARXNG_BASE_URL` РЅРµ РЅР°СЃС‚СЂРѕРµРЅ РёР»Рё `SearxNG` РІСЂРµРјРµРЅРЅРѕ РЅРµРґРѕСЃС‚СѓРїРµРЅ, С‡Р°СЃС‚СЊ search/competitor СЃС†РµРЅР°СЂРёРµРІ РјРѕР¶РµС‚ РґРµРіСЂР°РґРёСЂРѕРІР°С‚СЊ. Р”Р»СЏ РЅРѕСЂРјР°Р»СЊРЅРѕРіРѕ РїРѕР»РЅРѕРіРѕ audit lifecycle СЂРµРєРѕРјРµРЅРґСѓРµС‚СЃСЏ РґРµСЂР¶Р°С‚СЊ `SearxNG`, `Redis` Рё Celery worker Р·Р°РїСѓС‰РµРЅРЅС‹РјРё РѕРґРЅРѕРІСЂРµРјРµРЅРЅРѕ.

## Р§С‚Рѕ РїСЂРѕРІРµСЂРёС‚СЊ РїРѕСЃР»Рµ Р·Р°РїСѓСЃРєР°

1. РћС‚РєСЂС‹С‚СЊ `http://127.0.0.1:8888` Рё СѓР±РµРґРёС‚СЊСЃСЏ, С‡С‚Рѕ `SearxNG` РѕС‚РІРµС‡Р°РµС‚.
2. РћС‚РєСЂС‹С‚СЊ `http://127.0.0.1:8000/docs` РёР»Рё РїРѕСЂС‚, РєРѕС‚РѕСЂС‹Р№ РІС‹РІРµР» root dev script.
3. РћС‚РєСЂС‹С‚СЊ `http://127.0.0.1:8000/health/live` Рё СѓР±РµРґРёС‚СЊСЃСЏ, С‡С‚Рѕ backend process Р¶РёРІ.
4. РћС‚РєСЂС‹С‚СЊ `http://127.0.0.1:8000/health/ready` Рё СѓР±РµРґРёС‚СЊСЃСЏ, С‡С‚Рѕ distributed stack РІРµСЂРЅСѓР» `status=ready`.
5. РћС‚РєСЂС‹С‚СЊ `http://127.0.0.1:8000/health/metrics` Рё СѓР±РµРґРёС‚СЊСЃСЏ, С‡С‚Рѕ backend РїРѕРєР°Р·С‹РІР°РµС‚ queue depth, worker activity Рё pipeline counters.
6. РћС‚РєСЂС‹С‚СЊ frontend URL РёР· `vite` output.
7. РЎРѕР·РґР°С‚СЊ Р°СѓРґРёС‚ Рё СѓР±РµРґРёС‚СЊСЃСЏ, С‡С‚Рѕ worker РѕР±СЂР°Р±Р°С‚С‹РІР°РµС‚ Р·Р°РґР°С‡Сѓ, Р° СЃС‚Р°С‚СѓСЃ РЅРµ РѕСЃС‚Р°С‘С‚СЃСЏ РІ `queued`.

`/health/ready` С‚РµРїРµСЂСЊ РїСЂРѕРІРµСЂСЏРµС‚ РЅРµ С‚РѕР»СЊРєРѕ СЃР°Рј API, РЅРѕ Рё СЂРµР°Р»СЊРЅС‹Рµ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё СЂР°СЃРїСЂРµРґРµР»С‘РЅРЅРѕРіРѕ РєРѕРЅС‚СѓСЂР°:

- Р±Р°Р·Сѓ РґР°РЅРЅС‹С…;
- Redis broker/result backend;
- Р°РєС‚РёРІРЅС‹Рµ Celery worker'С‹;
- РїРѕРєСЂС‹С‚РёРµ РІСЃРµС… expected audit queues;
- РґРѕСЃС‚СѓРїРЅРѕСЃС‚СЊ `SearxNG`, РµСЃР»Рё РІС‹Р±СЂР°РЅ provider `searxng`.

Р•СЃР»Рё endpoint РІРµСЂРЅСѓР» `503`, СЌС‚Рѕ Р·РЅР°С‡РёС‚, С‡С‚Рѕ СЃС‚РµРє РЅРµ РіРѕС‚РѕРІ Рє РїРѕР»РЅРѕС†РµРЅРЅРѕРјСѓ distributed audit execution, РґР°Р¶Рµ РµСЃР»Рё `FastAPI` РїСЂРѕС†РµСЃСЃ СѓР¶Рµ РїРѕРґРЅСЏР»СЃСЏ.

РќР°С‡РёРЅР°СЏ СЃ `D10`, backend РёСЃРїРѕР»СЊР·СѓРµС‚ СЌС‚Рё runtime-СЃРёРіРЅР°Р»С‹ РЅРµ С‚РѕР»СЊРєРѕ РґР»СЏ observability, РЅРѕ Рё РґР»СЏ СѓРїСЂР°РІР»РµРЅРёСЏ РЅР°РіСЂСѓР·РєРѕР№. Р•СЃР»Рё `POST /audits` РІРёРґРёС‚, С‡С‚Рѕ `audits.pipeline` СѓР¶Рµ `backlogged`/`stuck` РёР»Рё detector С„РёРєСЃРёСЂСѓРµС‚ СЃР»РёС€РєРѕРј РґРѕР»РіСѓСЋ РѕС‡РµСЂРµРґСЊ РѕР¶РёРґР°СЋС‰РёС… Р·Р°РїСѓСЃРєРѕРІ, API РІРѕР·РІСЂР°С‰Р°РµС‚ `503` Рё РЅРµ СЃРѕР·РґР°С‘С‚ РЅРѕРІС‹Р№ audit. Р”Р»СЏ СѓР¶Рµ РёСЃРїРѕР»РЅСЏСЋС‰РёС…СЃСЏ СЃС‚Р°РґРёР№ orchestration, РЅР°РѕР±РѕСЂРѕС‚, РїСЂРµРґРїРѕС‡РёС‚Р°РµС‚ `inline`-fallback РІРјРµСЃС‚Рѕ РґР°Р»СЊРЅРµР№С€РµРіРѕ СЂР°Р·РґСѓРІР°РЅРёСЏ РґРµРіСЂР°РґРёСЂРѕРІР°РІС€РµР№ РѕС‡РµСЂРµРґРё.

## Р Р°Р·РЅРёС†Р° РјРµР¶РґСѓ 
pm run dev` Рё 
pm run dev:full`

- 
pm run dev` Р·Р°РїСѓСЃРєР°РµС‚ С‚РѕР»СЊРєРѕ backend Рё frontend.
- 
pm run dev:full` Р·Р°РїСѓСЃРєР°РµС‚ `SearxNG`, `Redis`, backend, frontend Рё Celery worker.

Р•СЃР»Рё `Redis` СѓР¶Рµ РґРѕСЃС‚СѓРїРµРЅ, РЅРѕ worker РЅРµ Р·Р°РїСѓС‰РµРЅ РёР»Рё С†РµР»РµРІС‹Рµ РѕС‡РµСЂРµРґРё РЅРµ РѕР±СЃР»СѓР¶РёРІР°СЋС‚СЃСЏ, РЅРѕРІС‹Рµ Р°СѓРґРёС‚С‹ РјРѕРіСѓС‚ Р±С‹С‚СЊ РѕС‚РєР»РѕРЅРµРЅС‹ СЃСЂР°Р·Сѓ СЃ `503` РїРѕ admission guard `D10`, Р° РЅРµ РѕСЃС‚Р°РІР»РµРЅС‹ РјРѕР»С‡Р° РІ `queued`. Р”Р»СЏ РїРѕР»РЅРѕС†РµРЅРЅРѕР№ Р»РѕРєР°Р»СЊРЅРѕР№ СЂР°Р±РѕС‚С‹ РёСЃРїРѕР»СЊР·СѓР№С‚Рµ РёРјРµРЅРЅРѕ 
pm run dev:full` РёР»Рё Р·Р°РїСѓСЃРєР°Р№С‚Рµ worker РѕС‚РґРµР»СЊРЅРѕР№ РєРѕРјР°РЅРґРѕР№.

## РџСЂРѕРІРµСЂРєРё

## Distributed benchmark workflow

Run the benchmark after `npm run dev:full` or after bringing up `backend`, `Redis`, Celery workers and `SearxNG` separately:

```powershell
cd <repo-root>
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

The script drives the live HTTP API, samples runtime metrics during execution and writes machine-readable plus human-readable evidence under `backend/artifacts/benchmarks/`.

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

## РџРѕР»РµР·РЅС‹Рµ СЃСЃС‹Р»РєРё

- [backend/README.md](./backend/README.md) вЂ” backend-specific РєРѕРјР°РЅРґС‹, training pipeline Рё ML workflow
- [AGENTS.md](./AGENTS.md) вЂ” operational instructions РґР»СЏ Р°РіРµРЅС‚РѕРІ Рё СЂР°Р·СЂР°Р±РѕС‚С‡РёРєРѕРІ
- [docs/roadmap/product-development-roadmap.md](./docs/roadmap/product-development-roadmap.md) вЂ” roadmap Рё GitHub backlog
- [backend/docs/ml_methodology_appendix.md](./backend/docs/ml_methodology_appendix.md) - appendix-ready description of ML methodology, evaluation and limitations


