# Backend

FastAPI backend РґР»СЏ Р°СѓРґРёС‚РѕРІ СЃР°Р№С‚РѕРІ, Р°СЃРёРЅС…СЂРѕРЅРЅРѕР№ РѕР±СЂР°Р±РѕС‚РєРё Рё ML scoring.

РџРѕР»РЅС‹Р№ Р»РѕРєР°Р»СЊРЅС‹Р№ setup РґР»СЏ РІСЃРµРіРѕ СЃС‚РµРєР° РѕРїРёСЃР°РЅ РІ [../README.md](../README.md). Р­С‚РѕС‚ С„Р°Р№Р» С„РѕРєСѓСЃРёСЂСѓРµС‚СЃСЏ РЅР° backend-РєРѕРјР°РЅРґР°С…, ML pipeline Рё backend-specific РґРµС‚Р°Р»СЏС….

Р’Рѕ РІСЃРµС… РєРѕРјР°РЅРґР°С… РЅРёР¶Рµ `<repo-root>` РѕР·РЅР°С‡Р°РµС‚ РєРѕСЂРµРЅСЊ СЌС‚РѕРіРѕ СЂРµРїРѕР·РёС‚РѕСЂРёСЏ.

## РўСЂРµР±РѕРІР°РЅРёСЏ

- Python 3.12 РёР»Рё 3.13
- Redis РґР»СЏ Celery
- Docker РґР»СЏ Р»РѕРєР°Р»СЊРЅРѕРіРѕ Р±РµСЃРїР»Р°С‚РЅРѕРіРѕ `SearxNG`

РџРµСЂРµРґ Р·Р°РїСѓСЃРєРѕРј `npm run searxng:*` СѓР±РµРґРёС‚РµСЃСЊ, С‡С‚Рѕ Docker Desktop СѓР¶Рµ Р·Р°РїСѓС‰РµРЅ Рё Docker daemon РіРѕС‚РѕРІ РїСЂРёРЅРёРјР°С‚СЊ РєРѕРјР°РЅРґС‹.

## Setup

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Р›РѕРєР°Р»СЊРЅС‹Р№ SearxNG

Р РµРєРѕРјРµРЅРґСѓРµРјС‹Р№ Р±РµСЃРїР»Р°С‚РЅС‹Р№ СЂРµР¶РёРј РґР»СЏ РїСЂРѕРµРєС‚Р° вЂ” СЃРІРѕР№ Р»РѕРєР°Р»СЊРЅС‹Р№ `SearxNG` РІ Docker. РўРµРєСѓС‰РёР№ Docker stack С‚Р°РєР¶Рµ РїРѕРґРЅРёРјР°РµС‚ `Redis`, РєРѕС‚РѕСЂС‹Р№ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РєР°Рє Celery broker/result backend РґР»СЏ С„РѕРЅРѕРІРѕР№ РѕР±СЂР°Р±РѕС‚РєРё Р°СѓРґРёС‚РѕРІ.

РџРѕРґРЅСЏС‚СЊ Р»РѕРєР°Р»СЊРЅС‹Р№ search provider:

```powershell
cd <repo-root>
npm run searxng:up
```

РџСЂРѕРІРµСЂРёС‚СЊ, С‡С‚Рѕ JSON API РґРѕСЃС‚СѓРїРµРЅ:

```powershell
cd <repo-root>
npm run searxng:check
```

РћСЃС‚Р°РЅРѕРІРёС‚СЊ РєРѕРЅС‚РµР№РЅРµСЂС‹:

```powershell
cd <repo-root>
npm run searxng:down
```

Р›РѕРєР°Р»СЊРЅС‹Р№ instance РїСѓР±Р»РёРєСѓРµС‚СЃСЏ РєР°Рє:

- `http://127.0.0.1:8888`
- `redis://127.0.0.1:6379/0`

РљРѕРЅС„РёРіСѓСЂР°С†РёСЏ Р»РµР¶РёС‚ РІ:

- [../docker-compose.searxng.yml](../docker-compose.searxng.yml)
- [../infra/searxng/settings.yml](../infra/searxng/settings.yml)

## Run API

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

API Р±СѓРґРµС‚ РґРѕСЃС‚СѓРїРµРЅ РЅР° `http://127.0.0.1:8000`.

## Health and readiness

Backend С‚РµРїРµСЂСЊ СЂР°Р·Р»РёС‡Р°РµС‚ liveness Рё РЅР°СЃС‚РѕСЏС‰СѓСЋ readiness distributed stack:

- `GET /health` - legacy СЃРѕРІРјРµСЃС‚РёРјС‹Р№ РјРёРЅРёРјР°Р»СЊРЅС‹Р№ healthcheck, РІРѕР·РІСЂР°С‰Р°РµС‚ С‚РѕР»СЊРєРѕ `{"status":"ok"}`
- `GET /health/live` - liveness РїСЂРѕС†РµСЃСЃР° API, Р±РµР· РїСЂРѕРІРµСЂРєРё РІРЅРµС€РЅРёС… Р·Р°РІРёСЃРёРјРѕСЃС‚РµР№
- `GET /health/ready` - readiness РІСЃРµРіРѕ backend/runtime-РєРѕРЅС‚СѓСЂР°, РІРєР»СЋС‡Р°СЏ Р·Р°РІРёСЃРёРјРѕСЃС‚Рё СЂР°СЃРїСЂРµРґРµР»С‘РЅРЅРѕРіРѕ РїР°Р№РїР»Р°Р№РЅР°
- `GET /health/metrics` - runtime telemetry РїРѕ СЂР°СЃРїСЂРµРґРµР»С‘РЅРЅРѕРјСѓ РїР°Р№РїР»Р°Р№РЅСѓ: backlog РѕС‡РµСЂРµРґРµР№, worker activity Рё Р°РіСЂРµРіРёСЂРѕРІР°РЅРЅС‹Рµ pipeline counters

`/health/ready` РїСЂРѕРІРµСЂСЏРµС‚:

- `database` - SQLAlchemy connection Рё `SELECT 1`
- `redis` - broker ping С‡РµСЂРµР· `Redis.from_url(...).ping()`
- `celery_workers` - РѕС‚РІРµС‡Р°РµС‚ Р»Рё С…РѕС‚СЏ Р±С‹ РѕРґРёРЅ worker Рё РїРѕРєСЂС‹С‚С‹ Р»Рё РІСЃРµ expected audit queues
- `serp` - РґРѕСЃС‚СѓРїРµРЅ Р»Рё `SearxNG JSON API`, РµСЃР»Рё `SERP_PROVIDER=searxng`

`/health/metrics` РґРѕРїРѕР»РЅСЏРµС‚ readiness РѕРїРµСЂР°С†РёРѕРЅРЅРѕР№ С‚РµР»РµРјРµС‚СЂРёРµР№:

- Р°РіСЂРµРіРёСЂРѕРІР°РЅРЅС‹Рµ counts Р°СѓРґРёС‚РѕРІ РїРѕ `status`
- counts Р°РєС‚РёРІРЅС‹С… Р°СѓРґРёС‚РѕРІ РїРѕ `orchestration_stage`
- РѕС†РµРЅРєР° backlog РїРѕ Redis queue depth РґР»СЏ РІСЃРµС… `AUDIT_QUEUES`
- online workers, РёС… queue coverage Рё РєРѕР»РёС‡РµСЃС‚РІРѕ `active/reserved/scheduled` Р·Р°РґР°С‡
- СѓРєСЂСѓРїРЅС‘РЅРЅР°СЏ СЃС‚Р°С‚РёСЃС‚РёРєР° РїРѕ `AuditCompetitor`
- `queue_pressure` snapshots РїРѕ РєР°Р¶РґРѕР№ audit queue: depth, consumers, inflight tasks, estimated capacity Рё derived pressure status
- `execution_detector` alerts РґР»СЏ stuck/backlogged runtime: stale processing audits, queued audits waiting too long Рё dispatched stages, РєРѕС‚РѕСЂС‹Рµ СЃР»РёС€РєРѕРј РґРѕР»РіРѕ РЅРµ СЃС‚Р°СЂС‚СѓСЋС‚

РљРѕРЅС‚СЂР°РєС‚ Redis backlog telemetry СЃРµР№С‡Р°СЃ С‚Р°РєРѕР№: endpoint СЃС‡РёС‚Р°РµС‚ РіР»СѓР±РёРЅСѓ РѕС‡РµСЂРµРґРµР№ РїРѕ default Celery Redis list keys Рё РїРѕРґРґРµСЂР¶РёРІР°РµС‚ `broker_transport_options.global_keyprefix`. Р•СЃР»Рё С‚СЂР°РЅСЃРїРѕСЂС‚РЅС‹Р№ С„РѕСЂРјР°С‚ РєР»СЋС‡РµР№ Р±СѓРґРµС‚ РїРµСЂРµРѕРїСЂРµРґРµР»С‘РЅ РіР»СѓР±Р¶Рµ СЌС‚РѕРіРѕ СѓСЂРѕРІРЅСЏ, Р»РѕРіРёРєСѓ `/health/metrics` РЅСѓР¶РЅРѕ РѕР±РЅРѕРІР»СЏС‚СЊ РІРјРµСЃС‚Рµ СЃ Celery broker config.

Р”Р»СЏ D9 `queue_pressure` РёСЃРїРѕР»СЊР·СѓРµС‚ РґРІР° СЃР»РѕСЏ СЃРёРіРЅР°Р»РѕРІ РѕРґРЅРѕРІСЂРµРјРµРЅРЅРѕ:

- Redis queue depth РєР°Рє snapshot С„Р°РєС‚РёС‡РµСЃРєРѕРіРѕ backlog;
- Celery worker inspect payload РєР°Рє snapshot consumer coverage, inflight tasks Рё estimated queue capacity.

`execution_detector` РїРѕРІРµСЂС… СЌС‚РѕРіРѕ РґРѕР±Р°РІР»СЏРµС‚ audit-level СЃРёРіРЅР°Р»С‹ РёР· Р±Р°Р·С‹ Рё event log:

- `stuck_processing_audits` вЂ” processing run СЃР»РёС€РєРѕРј РґР°РІРЅРѕ РЅРµ РѕР±РЅРѕРІР»СЏР»СЃСЏ;
- `queued_audits_waiting_too_long` вЂ” РЅРѕРІС‹Рµ Р°СѓРґРёС‚С‹ СЃР»РёС€РєРѕРј РґРѕР»РіРѕ СЃС‚РѕСЏС‚ РґРѕ СЃС‚Р°СЂС‚Р° pipeline;
- `dispatched_stages_waiting_too_long` вЂ” stage СѓР¶Рµ dispatch'РЅСѓС‚, РЅРѕ СЃР»РёС€РєРѕРј РґРѕР»РіРѕ РЅРµ РЅР°С‡Р°Р» РёСЃРїРѕР»РЅСЏС‚СЊСЃСЏ;
- `queue_without_workers` Рё `queue_backlog_detected` вЂ” operational backlog РЅР° СѓСЂРѕРІРЅРµ РѕС‡РµСЂРµРґРµР№.

РќР°С‡РёРЅР°СЏ СЃ `D10`, СЌС‚Рё СЃРёРіРЅР°Р»С‹ РёСЃРїРѕР»СЊР·СѓСЋС‚СЃСЏ РЅРµ С‚РѕР»СЊРєРѕ РґР»СЏ РЅР°Р±Р»СЋРґР°РµРјРѕСЃС‚Рё. `POST /audits` РїСЂРёРјРµРЅСЏРµС‚ admission guard: РµСЃР»Рё РѕС‡РµСЂРµРґСЊ `audits.pipeline` СѓР¶Рµ `backlogged`/`stuck` РёР»Рё detector РїРѕРєР°Р·С‹РІР°РµС‚ РЅР°РєРѕРїРёРІС€РёР№СЃСЏ backlog РЅРѕРІС‹С… Р·Р°РїСѓСЃРєРѕРІ, API РІРѕР·РІСЂР°С‰Р°РµС‚ `503` Рё РЅРµ СЃРѕР·РґР°С‘С‚ РЅРѕРІС‹Р№ audit run. Р”Р»СЏ СѓР¶Рµ РёСЃРїРѕР»РЅСЏСЋС‰РёС…СЃСЏ Р°СѓРґРёС‚РѕРІ stage dispatcher Рё competitor fan-out РёСЃРїРѕР»СЊР·СѓСЋС‚ С‚РѕС‚ Р¶Рµ runtime snapshot, РЅРѕ РІРјРµСЃС‚Рѕ reject РїРµСЂРµС…РѕРґСЏС‚ РЅР° `inline`-fallback, С‡С‚РѕР±С‹ РЅРµ СѓСЃРёР»РёРІР°С‚СЊ РґРµРіСЂР°РґРёСЂРѕРІР°РІС€РёР№ backlog РґРѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рј queue dispatch.

РљРѕРіРґР° РІСЃРµ РѕР±СЏР·Р°С‚РµР»СЊРЅС‹Рµ РєРѕРјРїРѕРЅРµРЅС‚С‹ РґРѕСЃС‚СѓРїРЅС‹, endpoint РІРѕР·РІСЂР°С‰Р°РµС‚ `200` Рё `status=ready`. Р•СЃР»Рё Redis РЅРµРґРѕСЃС‚СѓРїРµРЅ, worker РЅРµ РѕС‚РІРµС‡Р°РµС‚ РёР»Рё РЅРµ РѕР±СЃР»СѓР¶РёРІР°СЋС‚СЃСЏ РІСЃРµ audit queues, Р»РёР±Рѕ РЅРµРґРѕСЃС‚СѓРїРµРЅ РѕР±СЏР·Р°С‚РµР»СЊРЅС‹Р№ `SearxNG`, endpoint РІРѕР·РІСЂР°С‰Р°РµС‚ `503` Рё `status=not_ready` СЃ СЂР°СЃС€РёС„СЂРѕРІРєРѕР№ РїСЂРѕР±Р»РµРјРЅРѕРіРѕ РєРѕРјРїРѕРЅРµРЅС‚Р°.

Р­С‚Рѕ РІР°Р¶РЅРѕ РґР»СЏ С‚РµРєСѓС‰РµР№ stage-based distributed architecture: backend СЃС‡РёС‚Р°РµС‚СЃСЏ РіРѕС‚РѕРІС‹Рј С‚РѕР»СЊРєРѕ С‚РѕРіРґР°, РєРѕРіРґР° РѕРЅ РЅРµ РїСЂРѕСЃС‚Рѕ Р·Р°РїСѓС‰РµРЅ, Р° СЂРµР°Р»СЊРЅРѕ РјРѕР¶РµС‚ dispatch'РёС‚СЊ Рё РІС‹РїРѕР»РЅСЏС‚СЊ audit stages РїРѕ РІСЃРµРј РѕС‡РµСЂРµРґСЏРј.

## Run Celery workers

Starting with `D11`, `health/ready` and `health/metrics` validate worker queue-affinity, not only total queue coverage. The single all-queues worker command below is now a legacy fallback for debugging only; the canonical topology is the specialized `pipeline`, `network` and `cpu_ml` profile split shown later in this file.

```powershell
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.pipeline,audits.fetch,audits.features,audits.scoring,audits.competitors,audits.competitor_pages,audits.recommendations,audits.finalize --pool=solo
```

Р”Р»СЏ Windows СЂРµРєРѕРјРµРЅРґСѓРµС‚СЃСЏ РѕСЃС‚Р°РІР»СЏС‚СЊ `--pool=solo`. Р•СЃР»Рё backend РІРёРґРёС‚ Redis, РЅРѕ worker РЅРµ Р·Р°РїСѓС‰РµРЅ РёР»Рё РЅРµ РѕР±СЃР»СѓР¶РёРІР°РµС‚СЃСЏ РЅСѓР¶РЅР°СЏ РѕС‡РµСЂРµРґСЊ, РЅРѕРІС‹Рµ Р°СѓРґРёС‚С‹ РјРѕРіСѓС‚ Р±С‹С‚СЊ РѕС‚РєР»РѕРЅРµРЅС‹ admission guard'РѕРј `D10` СЃ `503`, Р° СѓР¶Рµ РІС‹РїРѕР»РЅСЏСЋС‰РёРµСЃСЏ СЃС‚Р°РґРёРё РїРµСЂРµР№РґСѓС‚ РЅР° `inline`-fallback РІРјРµСЃС‚Рѕ РґР°Р»СЊРЅРµР№С€РµРіРѕ queue fan-out.

Р‘С‹СЃС‚СЂР°СЏ РѕРїРµСЂР°С†РёРѕРЅРЅР°СЏ РїСЂРѕРІРµСЂРєР° РїРѕСЃР»Рµ СЃС‚Р°СЂС‚Р° СЃС‚РµРєР°:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/live"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/ready"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health/metrics"
```

Р•СЃР»Рё `/health/ready` РІРѕР·РІСЂР°С‰Р°РµС‚ `503`, РІ payload Р±СѓРґРµС‚ РІРёРґРЅРѕ, РєР°РєРѕР№ РёРјРµРЅРЅРѕ РєРѕРјРїРѕРЅРµРЅС‚ РЅРµ РіРѕС‚РѕРІ: `redis`, `celery_workers`, `serp` РёР»Рё `database`.

## Distributed audit pipeline

РђСѓРґРёС‚ Р±РѕР»СЊС€Рµ РЅРµ РёСЃРїРѕР»РЅСЏРµС‚СЃСЏ РѕРґРЅРѕР№ РґР»РёРЅРЅРѕР№ С„РѕРЅРѕРІРѕР№ Р·Р°РґР°С‡РµР№. Runtime-РїР°Р№РїР»Р°Р№РЅ СЂР°Р·СЂРµР·Р°РЅ РЅР° РѕС‚РґРµР»СЊРЅС‹Рµ stage tasks, С‡С‚РѕР±С‹ РёС… РјРѕР¶РЅРѕ Р±С‹Р»Рѕ РЅРµР·Р°РІРёСЃРёРјРѕ РјР°СЂС€СЂСѓС‚РёР·РёСЂРѕРІР°С‚СЊ, СЂРµС‚СЂР°РёС‚СЊ Рё РјР°СЃС€С‚Р°Р±РёСЂРѕРІР°С‚СЊ:

- `app.process_audit` - kickoff Рё РїРµСЂРµРІРѕРґ Р°СѓРґРёС‚Р° РІ `processing`
- `app.process_audit_fetch_target` - Р·Р°РіСЂСѓР·РєР° С†РµР»РµРІРѕР№ СЃС‚СЂР°РЅРёС†С‹
- `app.process_audit_extract_features` - РёР·РІР»РµС‡РµРЅРёРµ РїСЂРёР·РЅР°РєРѕРІ
- `app.process_audit_score_target` - scoring С‡РµСЂРµР· rule-based + ML breakdown
- `app.process_audit_collect_competitors` - СЃР±РѕСЂ Рё СЃСЂР°РІРЅРµРЅРёРµ РєРѕРЅРєСѓСЂРµРЅС‚РѕРІ
- `app.process_audit_collect_competitor_page` - РѕР±СЂР°Р±РѕС‚РєР° РѕРґРЅРѕР№ РєРѕРЅРєСѓСЂРµРЅС‚РЅРѕР№ СЃС‚СЂР°РЅРёС†С‹ РєР°Рє РѕС‚РґРµР»СЊРЅРѕР№ distributed subtask
- `app.process_audit_aggregate_competitors` - Р°РіСЂРµРіР°С†РёСЏ fan-out СЂРµР·СѓР»СЊС‚Р°С‚РѕРІ РєРѕРЅРєСѓСЂРµРЅС‚РѕРІ РѕР±СЂР°С‚РЅРѕ РІ audit summary
- `app.process_audit_generate_recommendations` - РіРµРЅРµСЂР°С†РёСЏ СЂРµРєРѕРјРµРЅРґР°С†РёР№
- `app.process_audit_finalize` - С„РёРЅР°Р»РёР·Р°С†РёСЏ СЂРµР·СѓР»СЊС‚Р°С‚Р° Рё warning-Р°РіСЂРµРіР°С†РёСЏ

Р•СЃР»Рё Redis/Celery РґРѕСЃС‚СѓРїРЅС‹, РєР°Р¶РґС‹Р№ stage dispatch'РёС‚СЃСЏ РєР°Рє РѕС‚РґРµР»СЊРЅР°СЏ Р·Р°РґР°С‡Р°. Р•СЃР»Рё Р±СЂРѕРєРµСЂ РЅРµРґРѕСЃС‚СѓРїРµРЅ, backend СЃРѕС…СЂР°РЅСЏРµС‚ С‚Сѓ Р¶Рµ Р±РёР·РЅРµСЃ-Р»РѕРіРёРєСѓ Рё РёСЃРїРѕР»РЅСЏРµС‚ СЃС‚Р°РґРёРё inline, С‡С‚Рѕ РїРѕР·РІРѕР»СЏРµС‚ Р»РѕРєР°Р»СЊРЅРѕ СЂР°Р·СЂР°Р±Р°С‚С‹РІР°С‚СЊ Рё С‚РµСЃС‚РёСЂРѕРІР°С‚СЊ РїР°Р№РїР»Р°Р№РЅ Р±РµР· РѕС‚РґРµР»СЊРЅРѕРіРѕ worker-РїСЂРѕС†РµСЃСЃР°.

Р”Р»СЏ D2 РєР°Р¶РґР°СЏ СЃС‚Р°РґРёСЏ СѓР¶Рµ РјР°СЂС€СЂСѓС‚РёР·РёСЂСѓРµС‚СЃСЏ РІ РѕС‚РґРµР»СЊРЅСѓСЋ РѕС‡РµСЂРµРґСЊ:

- `audits.pipeline`
- `audits.fetch`
- `audits.features`
- `audits.scoring`
- `audits.competitors`
- `audits.competitor_pages`
- `audits.recommendations`
- `audits.finalize`

Р­С‚Рѕ РїРѕР·РІРѕР»СЏРµС‚ Р·Р°РїСѓСЃРєР°С‚СЊ РѕРґРёРЅ СѓРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Р№ worker РЅР° РІСЃРµС… РѕС‡РµСЂРµРґСЏС… РёР»Рё РїРѕРґРЅРёРјР°С‚СЊ СЃРїРµС†РёР°Р»РёР·РёСЂРѕРІР°РЅРЅС‹Рµ worker-РїСЂРѕС†РµСЃСЃС‹ РїРѕРґ РєРѕРЅРєСЂРµС‚РЅС‹Рµ С‚РёРїС‹ РЅР°РіСЂСѓР·РєРё. РќР°РїСЂРёРјРµСЂ, СЃРµС‚РµРІС‹Рµ СЃС‚Р°РґРёРё (`fetch`, `competitors`, `competitor_pages`) Рё CPU/ML СЃС‚Р°РґРёРё (`features`, `scoring`) С‚РµРїРµСЂСЊ РјРѕР¶РЅРѕ РјР°СЃС€С‚Р°Р±РёСЂРѕРІР°С‚СЊ РЅРµР·Р°РІРёСЃРёРјРѕ. Р’ D3 РєРѕРЅРєСѓСЂРµРЅС‚РЅС‹Рµ СЃС‚СЂР°РЅРёС†С‹ Р±РѕР»СЊС€Рµ РЅРµ РѕР±СЂР°Р±Р°С‚С‹РІР°СЋС‚СЃСЏ РїРѕСЃР»РµРґРѕРІР°С‚РµР»СЊРЅРѕ РІРЅСѓС‚СЂРё РѕРґРЅРѕР№ Р·Р°РґР°С‡Рё: РєР°Р¶РґР°СЏ SERP-СЃС‚СЂР°РЅРёС†Р° СЃС‚Р°Р»Р° РѕС‚РґРµР»СЊРЅРѕР№ distributed subtask СЃ РїРѕСЃР»РµРґСѓСЋС‰РµР№ Р°РіСЂРµРіР°С†РёРµР№.

## Retry-safe orchestration

Р”Р»СЏ D4 orchestration СЃС‚Р°Р» version-aware Рё retry-safe:

- РєР°Р¶РґС‹Р№ РЅРѕРІС‹Р№ Р·Р°РїСѓСЃРє Р°СѓРґРёС‚Р° РїРѕР»СѓС‡Р°РµС‚ `processing_version`;
- stage tasks РёСЃРїРѕР»РЅСЏСЋС‚СЃСЏ С‚РѕР»СЊРєРѕ РµСЃР»Рё РёС… `processing_version` СЃРѕРІРїР°РґР°РµС‚ СЃ С‚РµРєСѓС‰РµР№ РІРµСЂСЃРёРµР№ Р°СѓРґРёС‚Р°;
- РµСЃР»Рё Celery РїРѕРІС‚РѕСЂРЅРѕ РґРѕСЃС‚Р°РІР»СЏРµС‚ stale task СЃС‚Р°СЂРѕРіРѕ Р·Р°РїСѓСЃРєР°, backend РёРіРЅРѕСЂРёСЂСѓРµС‚ РµС‘ РєР°Рє `stale_processing_version`;
- `process_audit` СѓРјРµРµС‚ Р±РµР·РѕРїР°СЃРЅРѕ РІРѕР·РѕР±РЅРѕРІРёС‚СЊ С‚РµРєСѓС‰РёР№ run Рё РїРµСЂРµ-dispatch'РёС‚СЊ Р°РєС‚СѓР°Р»СЊРЅСѓСЋ СЃС‚Р°РґРёСЋ Р±РµР· РЅРѕРІРѕРіРѕ СЃР±СЂРѕСЃР° СЃРѕСЃС‚РѕСЏРЅРёСЏ;
- fan-out РєРѕРЅРєСѓСЂРµРЅС‚РЅС‹С… subtasks Рё aggregation Р·Р°С‰РёС‰РµРЅС‹ РѕС‚ РїРѕРІС‚РѕСЂРЅРѕРіРѕ Р·Р°РїСѓСЃРєР° СЃС‚Р°СЂС‹Рј orchestration state.

Р­С‚Рѕ РІР°Р¶РЅРѕ РґР»СЏ СЂР°СЃРїСЂРµРґРµР»С‘РЅРЅРѕРіРѕ РёСЃРїРѕР»РЅРµРЅРёСЏ: РїСЂРё РїР°РґРµРЅРёРё worker'Р°, duplicate delivery РёР»Рё СЂСѓС‡РЅРѕРј requeue СЃС‚Р°СЂС‹Рµ Р·Р°РґР°С‡Рё РЅРµ РґРѕР»Р¶РЅС‹ РїРµСЂРµС‚РёСЂР°С‚СЊ Р±РѕР»РµРµ РЅРѕРІС‹Р№ audit run.

РџСЂРёРјРµСЂС‹ СЃРїРµС†РёР°Р»РёР·РёСЂРѕРІР°РЅРЅС‹С… worker-РїСЂРѕС†РµСЃСЃРѕРІ:

```powershell
# network-heavy worker
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.fetch,audits.competitors,audits.competitor_pages --pool=solo
```

```powershell
# CPU/ML-heavy worker
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.features,audits.scoring,audits.recommendations,audits.finalize --pool=solo
```

```powershell
# lightweight orchestration worker
cd backend
.venv\Scripts\python.exe -m celery -A app.celery_app:celery_app worker --loglevel=info -Q audits.pipeline --pool=solo
```

## Env

РЎРєРѕРїРёСЂСѓР№С‚Рµ [`.env.example`](./.env.example) РІ `backend/.env`.

РњРёРЅРёРјР°Р»СЊРЅР°СЏ Р»РѕРєР°Р»СЊРЅР°СЏ РєРѕРЅС„РёРіСѓСЂР°С†РёСЏ:

```env
SERP_PROVIDER=searxng
SEARXNG_BASE_URL=http://127.0.0.1:8888
SEARXNG_LANGUAGE=ru-RU
SEARCH_TIMEOUT=20
```

Р•СЃР»Рё Р»РѕРєР°Р»СЊРЅС‹Р№ `SearxNG` РІСЂРµРјРµРЅРЅРѕ РЅРµРґРѕСЃС‚СѓРїРµРЅ, competitor lookup Рё dataset build РјРѕРіСѓС‚ РѕС‚РєР°С‚РёС‚СЊСЃСЏ РЅР° HTML fallback.

## Root commands

РР· РєРѕСЂРЅСЏ РїСЂРѕРµРєС‚Р° РґРѕСЃС‚СѓРїРЅС‹:

```powershell
npm run searxng:up
npm run searxng:check
npm run dev
```

РР»Рё РѕРґРЅРѕР№ РєРѕРјР°РЅРґРѕР№ РїРѕРґРЅСЏС‚СЊ Р»РѕРєР°Р»СЊРЅС‹Р№ РїРѕРёСЃРє, Redis, frontend, backend Рё Celery worker:

```powershell
npm run dev:full
```

`npm run dev` РїРѕРґРЅРёРјР°РµС‚ С‚РѕР»СЊРєРѕ backend Рё frontend.

## RU training seeds

РЎРіРµРЅРµСЂРёСЂРѕРІР°С‚СЊ RU commercial seed pack:

```powershell
cd backend
.venv\Scripts\python.exe ..\scripts\generate_training_queries.py
```

РЎРєСЂРёРїС‚ СЃРѕР·РґР°С‘С‚:

- `data\training_query_seeds.csv`
- `data\training_queries.txt`

## Dataset build

РћР±С‹С‡РЅС‹Р№ РїСЂРѕРіРѕРЅ:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.dataset_builder `
  --seeds-file data\training_query_seeds.csv `
  --output data\training_dataset.csv `
  --failures-output data\training_failures.csv `
  --checkpoint data\training_dataset.checkpoint.json `
  --overwrite `
  --max-workers 2 `
  --query-delay 1.0
```

РџР°РєРµС‚РЅС‹Р№ РїСЂРѕРіРѕРЅ РїРѕ 60 seed-РѕРІ СЃ Р°РІС‚РѕС‚СЂРµРЅРёСЂРѕРІРєРѕР№ РїРѕСЃР»Рµ РґРѕСЃС‚РёР¶РµРЅРёСЏ С†РµР»РµРІРѕРіРѕ РѕР±СЉС‘РјР°:

```powershell
cd backend
.venv\Scripts\python.exe ..\scripts\run_training_batches.py `
  --seeds-file data\training_query_seeds.csv `
  --dataset data\training_dataset.csv `
  --failures data\training_failures.csv `
  --checkpoint data\training_dataset.checkpoint.json `
  --batch-size 60 `
  --target-rows 1800 `
  --max-workers 2 `
  --query-delay 1.0 `
  --model-output artifacts\page_quality_model.pkl
```

## Training

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.train `
  --dataset data\training_dataset.csv `
  --model-output artifacts\page_quality_model.pkl
```

Р’Рѕ РІСЂРµРјСЏ РѕР±СѓС‡РµРЅРёСЏ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ group-based split РїРѕ `query`, СЃС‡РёС‚Р°СЋС‚СЃСЏ:

- `RMSE`
- `MAE`
- `Spearman mean`
- `NDCG@10`
- `Top-3 hit rate`

Р•СЃР»Рё baseline `RandomForestRegressor` РґР°С‘С‚ СЃР»Р°Р±СѓСЋ ranking-aware РІР°Р»РёРґР°С†РёСЋ, pipeline РїСЂРѕР±СѓРµС‚ benchmark РЅР° `CatBoostRegressor`.

## Runtime scoring

Runtime РїРѕ-РїСЂРµР¶РЅРµРјСѓ РёСЃРїРѕР»СЊР·СѓРµС‚ РѕРґРёРЅ entrypoint: `predict_score(features)`.

РџРѕРІРµРґРµРЅРёРµ:

- РµСЃР»Рё Р·Р°РґР°РЅ `SEARXNG_BASE_URL`, РїРѕРёСЃРє РёРґС‘С‚ С‡РµСЂРµР· Р»РѕРєР°Р»СЊРЅС‹Р№ РёР»Рё РІРЅРµС€РЅРёР№ `SearxNG JSON API`;
- РµСЃР»Рё `SearxNG` РЅРµРґРѕСЃС‚СѓРїРµРЅ, competitor lookup Рё dataset build РјРѕРіСѓС‚ РѕС‚РєР°С‚РёС‚СЊСЃСЏ РЅР° HTML fallback;
- РµСЃР»Рё РµСЃС‚СЊ `artifacts\page_quality_model.pkl` СЃ СЃРѕРІРјРµСЃС‚РёРјРѕР№ СЃС…РµРјРѕР№ features, РѕРЅ СЃС‚Р°РЅРѕРІРёС‚СЃСЏ РѕСЃРЅРѕРІРЅРѕР№ РјРѕРґРµР»СЊСЋ;
- РµСЃР»Рё Р°СЂС‚РµС„Р°РєС‚Р° РЅРµС‚ РёР»Рё schema РЅРµСЃРѕРІРјРµСЃС‚РёРјР°, РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ bootstrap fallback;
- `score_breakdown.model_info` РїРѕРєР°Р·С‹РІР°РµС‚ РёСЃС‚РѕС‡РЅРёРє РјРѕРґРµР»Рё, С‚РёРї, РґР°С‚Сѓ РѕР±СѓС‡РµРЅРёСЏ Рё РІРµСЂСЃРёСЋ РґР°С‚Р°СЃРµС‚Р°.

## Feature inventory

- [docs/ml_feature_inventory.md](./docs/ml_feature_inventory.md)

## Example API requests

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://127.0.0.1:8000/audits" `
  -ContentType "application/json" `
  -Body '{"query":"СЂРµРјРѕРЅС‚ РєРІР°СЂС‚РёСЂ РµРєР°С‚РµСЂРёРЅР±СѓСЂРі","target_url":"https://example.com","top_n":10}'
```

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "http://127.0.0.1:8000/audits/<AUDIT_ID>/results"
```

```powershell
Invoke-RestMethod `
  -Method Get `
  -Uri "http://127.0.0.1:8000/audits/<AUDIT_ID>/events"
```

`GET /audits/{audit_id}/events` РІРѕР·РІСЂР°С‰Р°РµС‚ persisted timeline РёСЃРїРѕР»РЅРµРЅРёСЏ СЂР°СЃРїСЂРµРґРµР»С‘РЅРЅРѕРіРѕ Р°СѓРґРёС‚Р°:

- stage transitions `started/completed/failed/aborted`
- queue dispatch events РґР»СЏ РїРµСЂРµС…РѕРґРѕРІ РјРµР¶РґСѓ СЃС‚Р°РґРёСЏРјРё
- `duration_ms` РґР»СЏ Р·Р°РІРµСЂС€С‘РЅРЅС‹С… Рё СѓРїР°РІС€РёС… С€Р°РіРѕРІ
- `processing_version`, С‡С‚РѕР±С‹ СЂР°Р·Р»РёС‡Р°С‚СЊ РїРѕРІС‚РѕСЂРЅС‹Рµ Р·Р°РїСѓСЃРєРё РѕРґРЅРѕРіРѕ Рё С‚РѕРіРѕ Р¶Рµ Р°СѓРґРёС‚Р°

РџРѕРІРµРґРµРЅРёРµ endpoint:

- Р±РµР· query-РїР°СЂР°РјРµС‚СЂРѕРІ РІРѕР·РІСЂР°С‰Р°РµС‚СЃСЏ timeline РїРѕСЃР»РµРґРЅРµРіРѕ run СЌС‚РѕРіРѕ Р°СѓРґРёС‚Р°;
- СЃ `?processing_version=<N>` РјРѕР¶РЅРѕ Р·Р°РїСЂРѕСЃРёС‚СЊ РєРѕРЅРєСЂРµС‚РёС‡РµСЃРєРёР№ РёСЃС‚РѕСЂРёС‡РµСЃРєРёР№ run;
- response СѓРїРѕСЂСЏРґРѕС‡РµРЅ РїРѕ РІСЂРµРјРµРЅРё Р·Р°РїРёСЃРё СЃРѕР±С‹С‚РёР№ Рё РїРѕРґС…РѕРґРёС‚ РґР»СЏ РїРѕСЃС‚СЂРѕРµРЅРёСЏ timeline/debug UI.

`GET /audits/{audit_id}/events/diagnostics` СЃС‚СЂРѕРёС‚ РїРѕРІРµСЂС… event log СѓР¶Рµ Р°РіСЂРµРіРёСЂРѕРІР°РЅРЅСѓСЋ РґРёР°РіРЅРѕСЃС‚РёРєСѓ РєРѕРЅРєСЂРµС‚РЅРѕРіРѕ run:

- stage breakdown РїРѕ `fetch/features/scoring/competitors/...`;
- terminal status run Рё РѕР±С‰РµРµ `total_duration_ms`;
- critical-path breakdown СЃ СѓС‡С‘С‚РѕРј fan-out СЃС‚Р°РґРёРё `competitor_page`;
- РѕС‚РґРµР»СЊРЅС‹Р№ `fan_out` summary РґР»СЏ distributed subtask execution.

Endpoint РёСЃРїРѕР»СЊР·СѓРµС‚ persisted D7 events, Р° РЅРµ scraping runtime logs, РїРѕСЌС‚РѕРјСѓ РїРѕРґС…РѕРґРёС‚ РґР»СЏ РёСЃС‚РѕСЂРёС‡РµСЃРєРѕРіРѕ СЂР°Р·Р±РѕСЂР° СѓР¶Рµ Р·Р°РІРµСЂС€С‘РЅРЅС‹С… Р·Р°РїСѓСЃРєРѕРІ.

## Tests

```powershell
cd backend
.venv\Scripts\python.exe -m pytest
```

## Dataset quality manifest

The RU-commercial dataset workflow now relies on a reproducible manifest-based process instead of an ad hoc CSV snapshot.

What the workflow produces:

- `data\training_query_seeds.csv` вЂ” seed pack for RU commercial queries.
- `data\training_queries.txt` вЂ” legacy flat list of the same queries.
- `<dataset>.manifest.json` вЂ” coverage report and quality gates for the collected dataset.

Seed catalog source of truth:

- 25 commercial categories
- 8 cities
- 200 unique query seeds in total

Generate the seed pack:

```powershell
cd backend
.venv\Scripts\python.exe ..\scripts\generate_training_queries.py
```

Build dataset quality manifest for an existing dataset:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.dataset_quality `
  --dataset data\training_dataset.csv `
  --failures data\training_failures.csv `
  --seeds data\training_query_seeds.csv
```

Run batched collection with quality gates:

```powershell
cd backend
.venv\Scripts\python.exe ..\scripts\run_training_batches.py `
  --seeds-file data\training_query_seeds.csv `
  --dataset data\training_dataset.csv `
  --failures data\training_failures.csv `
  --checkpoint data\training_dataset.checkpoint.json `
  --target-rows 400 `
  --batch-size 40
```

Default production-like quality gates:

- at least 400 successful rows;
- at least 40 unique queries;
- at least 250 unique domains;
- at least 6 categories and 6 cities represented in successful rows;
- at least 20% successful seed coverage;
- at least 5 rows per successful query on average;
- failure rate no higher than 20%.

## Primary model publish

To publish the real primary artifact from the committed RU-commercial dataset snapshot, run:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.publish `
  --dataset data\ru_commercial_dataset.csv `
  --manifest data\ru_commercial_dataset.manifest.json `
  --model-output artifacts\page_quality_model.pkl
```

What this does:

- validates that the dataset manifest is `ready_for_training`;
- trains the primary model from the real local dataset snapshot;
- writes the default runtime artifact to `artifacts\page_quality_model.pkl`;
- embeds `dataset_version`, `trained_at`, `rows_count`, `queries_count` and `domains_count` into the artifact metadata.

Expected runtime effect:

- `score_breakdown.model_info.source` becomes `local_dataset`;
- `score_breakdown.model_info.dataset_version` points to the published RU-commercial snapshot version;
- the scoring pipeline no longer depends on the bootstrap fallback when the published artifact is present.

## Offline model evaluation

Before publishing a new artifact, run offline evaluation on the same dataset split and compare candidate models against the currently published runtime model:

```powershell
cd backend
.venv\Scripts\python.exe -m app.ml.evaluate `
  --dataset data\ru_commercial_dataset.csv `
  --reference-model artifacts\page_quality_model.pkl
```

What the offline evaluation reports:

- query-grouped train/validation split metadata;
- ranking-aware metrics for each newly trained candidate model;
- the best candidate on the validation set;
- optional comparison against the currently published runtime artifact on the same validation rows.

Key metrics to watch before publish:

- `Spearman mean`
- `NDCG@10`
- `Top-3 hit rate`
- `MAE`
- `RMSE`

Use this step before `python -m app.ml.publish` when you want to validate that the next candidate is not weaker than the currently published primary artifact.

## Artifact versioning and runtime metadata

Published primary models now produce two artifact forms:

- `artifacts\page_quality_model.pkl` вЂ” current runtime alias used by the scoring pipeline;
- `artifacts\versions\page_quality_model--<artifact_version>.pkl` вЂ” immutable versioned release copy.

Each published artifact also has a public JSON sidecar:

- `artifacts\page_quality_model.metadata.json`
- `artifacts\versions\page_quality_model--<artifact_version>.metadata.json`

The runtime `score_breakdown.model_info` now exposes:

- `artifact_version`
- `artifact_family`
- `trained_at`
- `published_at`
- `dataset_version`
- `dataset_rows`, `dataset_queries`, `dataset_domains`
- `dataset_categories`, `dataset_cities`
- `dataset_failure_rate`
- `dataset_query_coverage_ratio`
- `dataset_attempted_query_coverage_ratio`
- `dataset_manifest_generated_at`
- `metrics_summary`

This makes the active scoring model traceable in runtime: you can see exactly which artifact version is active, what dataset coverage it was trained on and what the key validation metrics were at publish time.
- [docs/ml_methodology_appendix.md](./docs/ml_methodology_appendix.md) - ML methodology, dataset design, evaluation and known limitations for diploma appendix

