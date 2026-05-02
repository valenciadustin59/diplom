# D45 SEO-Weighted Label Rubric v4

These labels are deterministic expert-rubric labels. They are not human labels.

- Source dataset: `dataset-v3-d37`
- Output labels: `E:\codexPROJ\diplom\backend\data\dataset_versions\dataset-v4\expert_labels.csv`
- Labels: `885` rows across `99` queries
- Split validation: `passed`
- Production artifact changed by D45: `False`

## Rubric Weights

- `critical` total weight: `0.55`
  - `crawl_indexability`: `0.18`
  - `canonical_consistency`: `0.12`
  - `title_query_fit`: `0.19`
  - `heading_query_fit`: `0.1`
  - `semantic_query_fit`: `0.25`
  - `intent_alignment`: `0.16`
- `important` total weight: `0.3`
  - `technical_metadata`: `0.22`
  - `page_structure`: `0.16`
  - `commercial_trust`: `0.24`
  - `offer_and_conversion`: `0.2`
  - `mobile_render_performance`: `0.18`
- `supporting` total weight: `0.1`
  - `text_sufficiency`: `0.25`
  - `media_and_internal_navigation`: `0.2`
  - `secondary_commercial_details`: `0.35`
  - `structured_support`: `0.2`
- `rank_prior` total weight: `0.05`
  - `serp_rank_prior`: `1.0`

## Score Distribution

- `min`: `13.7`
- `p25`: `66.2`
- `mean`: `68.1355`
- `p50`: `72.2`
- `p75`: `76.3`
- `max`: `87.2`

## Examples

### high
- `87.2` `как выбрать пластиковые окна` -> `https://okonti.ru/articles/kak-vybrat-plastikovye-okna-v-kvartiru/`; limits: `none`
- `86.0` `как выбрать пластиковые окна` -> `https://geometrium-school.ru/blog/kak-vybrat-plastikovye-okna/`; limits: `none`

### medium
- `72.0` `натяжные потолки Москва` -> `https://www.potolkoff.ru/`; limits: `none`
- `72.0` `натяжные потолки цена Самара` -> `https://www.potolkoffsam.ru/`; limits: `none`
- `72.0` `пластиковые окна Самара` -> `https://oknazavr.ru/samara/plastikovye-okna/`; limits: `none`

### low
- `13.7` `входные двери цена Нижний Новгород` -> `https://2gis.ru/n_novgorod/search/Входные двери/rubricId/9972`; limits: `critical_http_status_not_ok|critical_intent_alignment_weak|critical_page_not_indexable|critical_query_title_fit_weak|critical_semantic_query_fit_weak|critical_title_missing|important_commercial_trust_weak|important_extremely_thin_content`
- `13.9` `кухни на заказ цена Новосибирск` -> `http://mebelin-nsk.ru/kukhni`; limits: `critical_http_status_not_ok|critical_intent_alignment_weak|critical_page_not_indexable|critical_query_title_fit_weak|critical_semantic_query_fit_weak|important_commercial_trust_weak|important_extremely_thin_content`
- `14.3` `ремонт квартир Казань` -> `https://profi.ru/geo-kzn/remont/remont-kvartir/`; limits: `critical_http_status_not_ok|critical_intent_alignment_weak|critical_page_not_indexable|critical_query_title_fit_weak|critical_semantic_query_fit_weak|critical_title_missing|important_commercial_trust_weak|important_extremely_thin_content`

### capped
- `32.4` `входные двери Санкт-Петербург` -> `https://spb.lemanapro.ru/catalogue/vhodnye-dveri/`; limits: `critical_http_status_not_ok|critical_intent_alignment_weak|critical_page_not_indexable|critical_query_title_fit_weak|critical_semantic_query_fit_weak|important_extremely_thin_content`
- `32.4` `входные двери Самара` -> `https://samara.lemanapro.ru/catalogue/vhodnye-dveri/`; limits: `critical_http_status_not_ok|critical_intent_alignment_weak|critical_page_not_indexable|critical_query_title_fit_weak|critical_semantic_query_fit_weak|important_extremely_thin_content`
- `32.4` `шкафы-купе Самара` -> `https://samara.lemanapro.ru/catalogue/shkafy-kupe/`; limits: `critical_http_status_not_ok|critical_intent_alignment_weak|critical_page_not_indexable|critical_query_title_fit_weak|critical_semantic_query_fit_weak|important_extremely_thin_content`
