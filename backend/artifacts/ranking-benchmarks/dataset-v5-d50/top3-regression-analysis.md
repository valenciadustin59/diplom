# D50 Top-3 Regression Analysis

- Decision: `analysis_only`
- Production SHA1: `29c4b29455f795a535da94b2c6f36ef603d003eb`
- Production unchanged by D50: `True`
- Validation queries: `20`
- Total candidate/query regressions: `20`
- Queries for D51 focus: `9`

## Pattern Summary

- `rank_prior_disagreement`: `20`
- `shortcut_text_volume`: `16`
- `aggregator_or_marketplace_distortion`: `7`

## Candidate Summaries

### pointwise_random_forest
- Regressed queries: `8`
- Improved queries: `1`
- Same hit state queries: `11`
- Patterns: `{"aggregator_or_marketplace_distortion": 2, "rank_prior_disagreement": 8, "shortcut_text_volume": 5}`

### pointwise_catboost
- Regressed queries: `6`
- Improved queries: `0`
- Same hit state queries: `14`
- Patterns: `{"aggregator_or_marketplace_distortion": 2, "rank_prior_disagreement": 6, "shortcut_text_volume": 6}`

### catboost_ranker
- Regressed queries: `6`
- Improved queries: `1`
- Same hit state queries: `13`
- Patterns: `{"aggregator_or_marketplace_distortion": 3, "rank_prior_disagreement": 6, "shortcut_text_volume": 5}`

## Regression Examples

### pointwise_random_forest / входные двери Екатеринбург
- Patterns: `rank_prior_disagreement`
- Lost SERP top-3 domains: `ekb.dvernayamarka.ru, ekat.steklodom.com, dveron.ru`
- Promoted non-top-3 domains: `ekaterinburg.dverimagnat.ru, ekaterinburg.mall-of-doors.ru, dverhome.ru`

### pointwise_catboost / входные двери Екатеринбург
- Patterns: `rank_prior_disagreement, shortcut_text_volume`
- Lost SERP top-3 domains: `ekb.dvernayamarka.ru, ekat.steklodom.com, dveron.ru`
- Promoted non-top-3 domains: `ekb.rusdver.net, ekaterinburg.dverimagnat.ru, ekaterinburg.mall-of-doors.ru`

### pointwise_random_forest / входные двери Нижний Новгород
- Patterns: `rank_prior_disagreement, shortcut_text_volume`
- Lost SERP top-3 domains: `n-gr.ru, nizhny-novgorod.doorsstore.ru, dveridaromnn.ru`
- Promoted non-top-3 domains: `nizhniy-novgorod.mosdveri.ru, nn.fabrichnie-dveri.ru, nigny-novgorod.dverimagnat.ru`

### pointwise_catboost / входные двери Нижний Новгород
- Patterns: `rank_prior_disagreement, shortcut_text_volume`
- Lost SERP top-3 domains: `n-gr.ru, nizhny-novgorod.doorsstore.ru, dveridaromnn.ru`
- Promoted non-top-3 domains: `nizhniy-novgorod.mosdveri.ru, nn.fabrichnie-dveri.ru, nigny-novgorod.dverimagnat.ru`

### catboost_ranker / входные двери Нижний Новгород
- Patterns: `rank_prior_disagreement, shortcut_text_volume`
- Lost SERP top-3 domains: `n-gr.ru, nizhny-novgorod.doorsstore.ru, dveridaromnn.ru`
- Promoted non-top-3 domains: `nizhniy-novgorod.mosdveri.ru, nn.fabrichnie-dveri.ru, nigny-novgorod.dverimagnat.ru`

### pointwise_random_forest / кухни на заказ Екатеринбург
- Patterns: `rank_prior_disagreement`
- Lost SERP top-3 domains: `ekaterinburg.vernokuhni.ru, kitchenrm.ru, lovekuhnya.ru`
- Promoted non-top-3 domains: `vkuskuhni.ru, dom-mania.ru, na-zakaz-mebel.com`

### pointwise_random_forest / кухни на заказ Нижний Новгород
- Patterns: `rank_prior_disagreement`
- Lost SERP top-3 domains: `kuhni-nn.ru, kuhni-slavichi.ru, kuhni-52.ru`
- Promoted non-top-3 domains: `kuhni-pod-zakaz-nn.ru, julison.ru, love-kuhnya-na-zakaz-nn.ru`

### pointwise_random_forest / натяжные потолки Новосибирск
- Patterns: `rank_prior_disagreement, shortcut_text_volume`
- Lost SERP top-3 domains: `vipceiling.ru, новосибирск.натяжные-потолки24.рф, sibirpotolki.ru`
- Promoted non-top-3 domains: `alansa.ru, mirpotolkov-54.ru, nskpotolki.ru`

### pointwise_catboost / натяжные потолки Новосибирск
- Patterns: `rank_prior_disagreement, shortcut_text_volume`
- Lost SERP top-3 domains: `vipceiling.ru, новосибирск.натяжные-потолки24.рф, sibirpotolki.ru`
- Promoted non-top-3 domains: `alansa.ru, mirpotolkov-54.ru, nskpotolki.ru`

### catboost_ranker / натяжные потолки Новосибирск
- Patterns: `rank_prior_disagreement, shortcut_text_volume`
- Lost SERP top-3 domains: `vipceiling.ru, новосибирск.натяжные-потолки24.рф, sibirpotolki.ru`
- Promoted non-top-3 domains: `alansa.ru, mirpotolkov-54.ru, nskpotolki.ru`

### pointwise_catboost / натяжные потолки отзывы
- Patterns: `aggregator_or_marketplace_distortion, rank_prior_disagreement, shortcut_text_volume`
- Lost SERP top-3 domains: `irecommend.ru, vipceiling.ru, vyboroved.ru`
- Promoted non-top-3 domains: `mixline-shop.ru, kaskadagenstvo.ru, onello.ru`

### catboost_ranker / натяжные потолки отзывы
- Patterns: `aggregator_or_marketplace_distortion, rank_prior_disagreement`
- Lost SERP top-3 domains: `irecommend.ru, vipceiling.ru, vyboroved.ru`
- Promoted non-top-3 domains: `psmith.ru, kaskadagenstvo.ru, onello.ru`

## D51 Focus

- `query_level_preference_labels`: Add pairwise/listwise labels for queries where candidate top-3 missed all SERP top-3 pages.
- `shortcut_feature_control`: Constrain text volume and other supporting signals when they displace stronger SERP pages.
- `serp_relative_manual_review`: Review rank-prior disagreements and aggregator/marketplace distortions before v5 labeling.
