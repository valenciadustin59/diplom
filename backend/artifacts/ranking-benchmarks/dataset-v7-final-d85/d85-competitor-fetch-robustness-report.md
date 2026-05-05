# D85 Competitor Fetch Robustness

- Status: `passed`
- Cases: `5`
- Failed cases: `0`
- Decision: `competitor_context_is_explicit_and_no_fake_market_average`

## Case Results

- `d85-ready-all-processed`: `pass`, context `ready`, score basis `competitiveness_score`
- `d85-partial-but-usable`: `pass`, context `partial_but_usable`, score basis `competitiveness_score`
- `d85-insufficient-one-processed`: `pass`, context `insufficient_processed_competitors`, score basis `primary_page_score`
- `d85-all-blocked`: `pass`, context `insufficient_processed_competitors`, score basis `primary_page_score`
- `d85-no-serp-results`: `pass`, context `no_serp_results`, score basis `primary_page_score`
