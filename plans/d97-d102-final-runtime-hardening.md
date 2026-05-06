# D97-D102: Final Runtime Hardening And Product Explanation

Status: D97-D102 implemented locally.

## Summary

This wave keeps the D83 `dataset-v7-final` query-core model as the active runtime artifact and hardens the last product/runtime edges discovered during live checks: overly strict second-layer penalties, misleading readiness under busy workers, unavailable-page UX, and false positives where only city/commercial modifiers match.

## D97: Second-Layer Score Rebalance

- Added `score-second-layer-rebalance-v1` after ML/rule scoring and before query relevance guardrails.
- Strong query fit can blend in bounded rule-score uplift:
  - high-confidence fit: `rule_weight=0.40`;
  - softer strong fit: `rule_weight=0.25`;
  - weak/partial/unrelated pages: `rule_weight=0`.
- Uplift is capped, and query relevance guardrails still apply after the rebalance.
- Score explanations and recommendations de-emphasize literal exact-phrase negatives when the page is already strongly relevant.

## D98: Distributed Stack Stability

- `GET /health/ready` now preserves recently observed worker queue ownership for `300s`.
- This prevents a busy Windows `solo` worker from making readiness falsely report missing queues while it is still processing long browser/network tasks.
- Queue pressure payloads distinguish current, recent and absent workers.

## D99-D102: Low-Score UX And Query-Core Mismatch

- UI/report/export now show clearer low-score reasons for unavailable pages, 404/noindex states, query mismatch and weak competitor context.
- Query-core mismatch features were added for local/commercial false positives:
  - a city match alone is not enough;
  - a commercial word such as `купить` is not enough;
  - the main service/product core must be present semantically or lexically.
- Regression coverage includes 404/unusable pages and local-service mismatch cases.

## Evidence

- Final live smoke: `output/runtime-smoke/d98-d102-final-live-smoke-summary.json`.
- Final smoke result: `overall_passed=true`, `health_not_ready_count=0`.
- Smoke cases:
  - `купить зимние шины` / `https://www.pokrishka.ru/zimnie-shiny/` -> score `80.4859`;
  - `купить зимние шины` / 404 URL -> score `0`, reason `page_unusable`;
  - `детский стоматолог екатеринбург` / `https://www.labirint.ru/` -> score `0`, reason `local_service_core_mismatch`;
  - `что такое вулкан` / Wikipedia -> score `66.4222`, no active guardrail;
  - `купить козловой кран` / `https://winemore.ru/` -> score `0`, reason `commercial_modifier_only_core_mismatch`.

## Verification

- Backend targeted suite: `129 passed`.
- Frontend tests: `73 passed`.
- Frontend build: passed.
- Script tests: `13 passed`.
- `git diff --check`: only CRLF warnings.

## Next Step

Do a final UX pass across launch, history and result screens; only change copy/layout if it improves clarity for the user. Then run a broader 8-10 case live smoke before demo/defense preparation.
