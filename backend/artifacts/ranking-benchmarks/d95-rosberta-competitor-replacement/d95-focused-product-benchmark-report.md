# D95 Focused Product Benchmark

- Status: `passed`
- Decision: `focused_product_guardrails_passed_for_rosberta_and_competitor_replacement`
- Scope: `focused_product_benchmark_no_full_dataset_no_runtime_mutation`
- Cases: `6` (`4` relevance, `2` competitor replacement)
- Failed cases: `0`
- Semantic provider: `rosberta` / `ai-forever/ru-en-RoSBERTa`
- Catalog: `backend\artifacts\ranking-benchmarks\d95-rosberta-competitor-replacement\d95-focused-catalog.json`

## Criteria

- `full_mismatch_near_zero`: `pass` (d95-rosberta-full-mismatch-near-zero)
- `approximate_relevant_not_crushed_to_zero`: `pass` (d95-rosberta-approximate-relevant-not-crushed)
- `relevant_without_buy_price_not_penalized_when_query_lacks_modifiers`: `pass` (d95-relevant-no-buy-price-modifier-keeps-score)
- `bad_competitors_score_below_10_or_failed_excluded`: `pass` (d95-replacement-pool-excludes-bad-and-fills-context, d95-insufficient-after-bad-competitor-exclusion)
- `accepted_competitor_count_and_context_quality_visible`: `pass` (d95-replacement-pool-excludes-bad-and-fills-context, d95-insufficient-after-bad-competitor-exclusion)

## Query Relevance

- `d95-rosberta-full-mismatch-near-zero`: `pass`, band `full_mismatch`, score `94.0` -> `4.7`, early stop `True`
- `d95-rosberta-approximate-relevant-not-crushed`: `pass`, band `weak_match`, score `86.0` -> `47.3`, early stop `False`
- `d95-relevant-no-buy-price-modifier-keeps-score`: `pass`, band `None`, score `82.0` -> `82.0`, early stop `False`
- `d95-commercial-modifier-only-does-not-hide-core-mismatch`: `pass`, band `probable_mismatch`, score `88.0` -> `22.0`, early stop `False`

## Competitor Replacement

- `d95-replacement-pool-excludes-bad-and-fills-context`: `pass`, context `ready`, accepted `3`, discarded `3`, replacements `2/3`
- `d95-insufficient-after-bad-competitor-exclusion`: `pass`, context `insufficient_processed_competitors`, accepted `1`, discarded `2`, replacements `1/2`

## Stored Evidence Sources

- Smoke: `output\runtime-smoke\d84-d87-final-smoke-summary.json`, status `passed`, cases `4`
- RoSBERTa sample: `backend\artifacts\embedding-benchmarks\dataset-v7-rosberta-vs-minilm-sample\sample-comparison-report.json`, rows `226`, queries `90`

## Notes

- Focused benchmark only; it does not run dataset-v7 or network competitor fetching.
- Runtime modules are imported read-only to evaluate the current product contract.
