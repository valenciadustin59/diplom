# ML Feature Inventory

## Current schema status after D82

Production runtime artifact `backend/artifacts/page_quality_model.pkl` still uses the D58-published CatBoost `v3` artifact from `dataset-v5` with `148` pre-competitor features. D82 trained a non-production `v4` query-core candidate with `156` features, but it has not replaced the runtime alias.

The active runtime `v3` feature groups are:

- `59` baseline text/HTML/query features;
- `49` snapshot technical and commercial features;
- `25` heavy-analysis features;
- `15` intent-alignment features.

D82 `v4` extends that set with `8` query-core features:

- `query_core_term_count`
- `query_core_term_matches`
- `query_core_keyword_coverage_ratio`
- `query_core_phrase_count`
- `query_core_phrase_present`
- `query_intent_modifier_count`
- `query_intent_modifier_matches`
- `query_intent_modifier_coverage_ratio`

D37 intentionally does not include the `29` SERP-relative features in primary scoring, because they are available only after competitor aggregation. D58 is the current runtime publish: dataset `dataset-v5`, artifact `dataset-v5-20260502151507`, schema `v3`, model type `CatBoostRegressor`, SHA1 `5374ca30f48f70d8629e7d84ec3df0524ef35b52`. D82 candidate evidence is stored at `backend/artifacts/page_quality_model.dataset-v7-final-query-core-candidate.pkl` and `backend/artifacts/ranking-benchmarks/dataset-v7-final-d82/`; it is `non_production=true` until a separate controlled publish is run.

Текущий runtime scoring использует `59` признаков страницы. Набор специально смещён не в сторону одиночных SEO-галочек, а в сторону комбинаций сигналов, потому что для дипломного проекта важно показать: модель оценивает не один параметр сам по себе, а то, как несколько параметров работают вместе.

## Группы признаков

- `25` технических и структурных признаков
- `19` контентных и query-aware признаков
- `15` interaction-признаков

## Технические и структурные

- `html_length_chars`
- `sentence_count`
- `avg_sentence_length`
- `paragraph_count`
- `h1_count`
- `h2_count`
- `h3_count`
- `heading_count`
- `title_present`
- `title_length`
- `meta_description_present`
- `meta_description_length`
- `link_count`
- `image_count`
- `list_item_count`
- `strong_tag_count`
- `form_count`
- `input_count`
- `inputs_per_form_ratio`
- `avg_paragraph_length`
- `link_density_per_1000_words`
- `image_density_per_1000_words`
- `list_density_per_1000_words`
- `strong_density_per_1000_words`
- `text_to_html_ratio`

## Контентные и query-aware

- `text_length_chars`
- `word_count`
- `unique_word_count`
- `unique_word_ratio`
- `avg_word_length`
- `query_in_title`
- `query_in_text`
- `exact_query_count`
- `query_term_count`
- `title_query_term_count`
- `meta_query_term_count`
- `title_keyword_coverage_ratio`
- `meta_keyword_coverage_ratio`
- `query_terms_in_headings`
- `heading_query_coverage_ratio`
- `first_200_words_query_term_count`
- `query_density`
- `keyword_coverage_ratio`
- `semantic_similarity`

## Interaction-признаки

Эта группа и есть ядро текущей идеи модели. Здесь признаки строятся как совместное действие нескольких базовых сигналов.

- `early_query_coverage_ratio`
  Показывает, насколько рано запрос начинает раскрываться в тексте.
- `conversion_signal_score`
  Сводит форму, input-поля, изображения и списки в общий коммерческий сигнал.
- `content_link_ratio`
  Показывает, сколько содержимого приходится на одну ссылку.
- `heading_paragraph_balance`
  Проверяет, не развалена ли структура страницы на слишком много или слишком мало заголовков.
- `query_semantic_alignment`
  Семантическая близость, усиленная реальным keyword coverage.
- `title_semantic_alignment`
  Насколько title поддерживает семантическое ядро страницы.
- `heading_semantic_alignment`
  Насколько H1-H3 поддерживают семантику запроса.
- `title_heading_keyword_alignment`
  Согласованность между title и заголовками по query-лексике.
- `content_depth_semantic_score`
  Совмещает глубину текста и semantic similarity.
- `query_prominence_score`
  Суммарный вес запроса в title, headings и ранней части текста.
- `title_length_quality`
  Качество длины title относительно рабочего диапазона, а не просто факт наличия.
- `meta_length_quality`
  Качество длины meta description.
- `keyword_balance_score`
  Баланс между покрытием запроса и естественной плотностью ключевых слов.
- `semantic_content_richness`
  Совмещает semantic similarity, глубину текста и лексическое разнообразие.
- `cta_semantic_score`
  Проверяет, поддерживают ли коммерческие элементы общий смысл страницы.

## Что удалено как лишнее

- `semantic_match_flag`
  Удалён, потому что это бинарное упрощение `semantic_similarity`, которое ухудшало выразительность модели.
- `semantic_similarity_pct`
  Удалён, потому что дублировал ту же самую информацию в другом масштабе.
- Старые backend-слои `services/repositories` для аудитов
  В текущем runtime они не используются и только запутывают структуру.

## Почему идея совокупности параметров правильная

Если смотреть только на отдельные признаки, модель легко получает ложные положительные срабатывания:

- высокий `word_count` сам по себе не означает хороший документ;
- высокий `query_density` сам по себе может означать переспам;
- наличие формы само по себе не делает страницу качественной;
- высокая `semantic_similarity` сама по себе ещё не гарантирует, что запрос вынесен в ключевые зоны страницы.

Поэтому для MVP и для дипломной логики правильнее опираться на interaction-признаки. Они позволяют различать:

- длинный, но нерелевантный текст и длинный, релевантный текст;
- страницу с ключевыми словами и страницу, где ключевые слова естественно встроены в структуру;
- коммерческую страницу с формой ради формы и страницу, где CTA действительно поддерживает интент запроса.

Именно такие сочетания признаков и должны быть основной ценностью ML-модели в этом проекте.

## Следующее усиление модели

Следующий адекватный шаг — не просто добавлять ещё десятки одиночных метрик, а расширять именно interaction-слой:

- URL/query interactions: близость slug к запросу, коммерческие маркеры в URL
- SERP interactions: связь ранга, сниппета и on-page features
- layout interactions: hero-section, CTA above the fold, коммерческие блоки рядом с query-ядром
- competitor-relative features: отставание/опережение не по одному признаку, а по кластерам признаков
