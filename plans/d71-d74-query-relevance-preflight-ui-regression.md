# D71-D74 Query Relevance Preflight, UI And Regression Evidence

## Summary

This wave wires the conservative D70 relevance contract into the product without retraining or publishing a new model.
The runtime now stops only for a confident full query mismatch, keeps the audit completed instead of failed, and explains the result as a product state rather than as ML internals.

## Completed Scope

### D71 Backend Preflight

- `backend/app/tasks.py` now routes target fetch into feature extraction before heavy analysis.
- Feature extraction runs `build_query_relevance_preflight_decision(...)` when heavy analysis has not yet been executed.
- If the decision is a confident full mismatch:
  - heavy analysis is skipped;
  - competitor search and competitor page fan-out are skipped;
  - the audit is marked `completed`, not `failed`;
  - score stays in the D70 `0-5` full-mismatch band;
  - `score_breakdown.relevance_guardrail.early_stop` is persisted;
  - `score_breakdown.relevance_guardrail.early_stop_status` is `completed`;
  - `comparison_summary.score_basis` is `query_relevance_early_stop`;
  - `competitor_processing_status` is `skipped_early_stop`.
- If the decision is not confident enough, the normal route continues into heavy analysis, scoring, competitors and recommendations.

### D73 UI And Copy

- Added `frontend/src/lib/earlyStop.ts` as the UI-facing early-stop view model.
- Audit overview, competitors tab, report page, Markdown/HTML export and history list show the mismatch as:
  - `Страница не соответствует запросу`;
  - `Сравнение с конкурентами не запускалось...`.
- UI intentionally hides raw fields such as `relevance_guardrail`, `early_stop` and `confident_full_query_mismatch`.
- Competitor blocks show that comparison was not launched instead of rendering empty/failed competitor state.

### D74 Regression Cases

Regression tests now cover:

- a clearly unrelated but otherwise good page, for example wine content for `купить козловой кран`, stops in `0-5`;
- a relevant gantry crane page without `купить` does not stop when commercial modifiers are not part of the query logic;
- similar but wrong equipment is capped without early stop;
- informational queries do not require commercial modifiers;
- rare synonym/translit-like cases do not early-stop if evidence is not confident enough;
- insufficient extracted text is never considered safe for early stop.

## Verification

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_audit_pipeline.py backend/tests/test_query_relevance_runtime.py backend/tests/test_model_schema.py backend/tests/test_final_query_competitiveness.py -q
```

Result: `51 passed`.

```powershell
npm --prefix frontend run test -- --run src/lib/ui.test.tsx src/lib/auditReport.test.ts
```

Result: `23 passed`.

## Non-Goals

- No model artifact was replaced.
- No controlled publish or rollback was executed.
- No `dataset-v7-final` live collection was started.
- D72 was not changed in this pass.
