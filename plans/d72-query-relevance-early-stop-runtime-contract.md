# D72 Query Relevance Early-Stop Runtime Contract

## Summary

D72 turns the D71 early-stop behavior into a stable runtime/API contract.
The product no longer requires consumers to inspect raw `score_breakdown.relevance_guardrail` fields to understand why an audit stopped before competitors.

## Implemented

- Added `backend/app/audit_early_stop.py` with a single `early-stop-summary-v1` builder.
- Added `early_stop` to:
  - `GET /audits`;
  - `GET /audits/{audit_id}`;
  - `GET /audits/{audit_id}/results`;
  - `GET /audits/{audit_id}/events/diagnostics`.
- The public early-stop summary exposes:
  - `type=query_relevance_full_mismatch`;
  - user-facing `title` and `message`;
  - bounded score and score floor/ceiling;
  - `score_basis=query_relevance_early_stop`;
  - skipped stages;
  - competitor processing status.
- Timeline diagnostics now carries the same `early_stop` summary as audit/results payloads.
- D71 event details were expanded with `score_floor`, `score_ceiling`, `safe_to_skip_competitors` and `skipped_stages`.
- Frontend timeline renders the early-stop state, adds a summary metric and labels `preflight_stop` / `preflight_continue` as product events.

## Verification

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_audits_api.py backend/tests/test_audit_pipeline.py backend/tests/test_query_relevance_runtime.py -q
```

Result: `54 passed`.

```powershell
npm --prefix frontend run test -- --run src/lib/auditTimeline.test.ts src/lib/ui.test.tsx src/lib/auditReport.test.ts
```

Result: `29 passed`.

```powershell
npm --prefix frontend run build
```

Result: passed.

## Non-Goals

- No model artifact was replaced.
- No controlled publish or rollback was executed.
- No `dataset-v7-final` collection was started.
