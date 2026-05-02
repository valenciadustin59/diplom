# Query relevance v1

This catalog contains 200 Russian training queries for query-page relevance hardening.

The goal is to teach the model and guardrails to distinguish a genuinely relevant landing page from a technically polished but off-topic page.

Each row keeps the standard seed fields first:

- `query`
- `category`
- `intent`
- `city`
- `region_code`
- `top_n`
- `pages_to_scan`

Additional fields describe how to judge relevance:

- `target_topic` — what the query is actually about.
- `query_focus` — the exact user need inside the topic.
- `positive_page_pattern` — query-level evidence a strong relevant page should contain.
- `negative_page_traps` — query-level hard negatives that must be treated as irrelevant even if they have good SEO structure.

The positive/negative descriptions are intentionally generated per row. They vary by intent, city, price modifiers, purchase verbs, service verbs, technical modifiers and comparison/informational wording.

Recommended next training step:

1. Collect SERP pages for these 200 queries.
2. Add deliberate cross-category negatives for every query.
3. Label pages as `gold`, `partial`, or `garbage` using this catalog.
4. Make query relevance the first scoring gate before general SEO/commercial quality.
