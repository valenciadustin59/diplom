# D70 Conservative Query Relevance Contract

## Goal

Separate two decisions that were previously mixed together:

- `relevance_score`: how well the page matches the query.
- `early_stop_decision`: whether it is safe to stop the audit before competitors and heavy analysis.

The key product rule is conservative: a bad page may continue to a full audit with a low cap, but a potentially relevant page must not be stopped just because one semantic/vector signal is noisy.

## Implemented

- `app.query_relevance` now uses `query-relevance-contract-v2`.
- Added `query-relevance-early-stop-v1` via `build_query_relevance_preflight_decision`.
- Early stop is only allowed for a confident full mismatch:
  - enough page text is available;
  - page loaded/indexability signals are not unusable;
  - relevance score is extremely low;
  - semantic similarity is very low;
  - query core coverage and core density are near zero;
  - exact query, title and heading signals are absent;
  - query prominence is absent.
- Full mismatch is now `0-5`, not `0-15`.
- Ambiguous low relevance is not early-stopped. It becomes `probable_mismatch` with `6-25`.
- Weak and partial matches keep broader caps:
  - `weak_match`: up to `55`;
  - `partial_match`: up to `80`.

## Runtime Contract

```text
full_mismatch       -> 0-5 and eligible for future preflight early stop
probable_mismatch   -> 6-25, continue audit
weak_match          -> up to 55, continue audit
partial_match       -> up to 80, continue audit
strong_match        -> no relevance cap
```

Early stop is not wired into audit orchestration yet. That belongs to D71.

## Regression Cases

- Good generic page from another topic with enough text and no query signals -> `full_mismatch`, early-stop candidate, score `0-5`.
- Page with only a commercial modifier match, for example only `купить` but wrong product -> `probable_mismatch`, no early stop.
- Low relevance page with any strong structural signal -> no early stop.
- Relevant page without `купить`/`цена` remains valid when the query core matches.

## Verification

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_query_relevance_runtime.py backend/tests/test_final_query_competitiveness.py backend/tests/test_model_schema.py::test_query_relevance_guardrail_caps_unrelated_commercial_page backend/tests/test_model_schema.py::test_query_relevance_guardrail_caps_partial_query_match -q
```

Current targeted result: `16 passed`.

Additional compatibility checks:

```powershell
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_recommendations.py backend/tests/test_ml_compare.py backend/tests/test_competitiveness_score.py -q
```

Current compatibility result: `17 passed`.
