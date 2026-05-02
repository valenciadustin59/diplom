import type { FetchMethod, RecommendationGroup, RecommendationGroupKey } from "../types";

const recommendationGroupLabels: Record<RecommendationGroupKey, string> = {
  technical_seo: "Техническое SEO",
  commercial_trust: "Коммерция и доверие",
  semantic_intent: "Смысл и намерение",
  competitor_gap: "Разрыв с конкурентами",
};

const recommendationGroupDescriptions: Record<RecommendationGroupKey, string> = {
  technical_seo: "Индексация, canonical, URL и другие технические сигналы ранжируемой страницы.",
  commercial_trust: "Контакты, офферы, призывы к действию, социальное доказательство и сигналы доверия к бизнесу.",
  semantic_intent: "Насколько структура и контент страницы совпадают с запросом и поисковым намерением.",
  competitor_gap: "Где страница уступает конкурентам и лидерам выдачи по ключевым факторам.",
};

const recommendationGroupEmptyStates: Record<RecommendationGroupKey, string> = {
  technical_seo: "Критичных технических просадок в этом блоке не обнаружено.",
  commercial_trust: "Коммерческий профиль и сигналы доверия выглядят достаточно конкурентно.",
  semantic_intent: "Смысловой профиль и поисковое намерение не показывают явных слабых мест.",
  competitor_gap: "Существенных отставаний от лидеров выдачи по главным сигналам не выявлено.",
};

const intentLabels: Record<string, string> = {
  commercial: "коммерческий",
  local_commercial: "локально-коммерческий",
  informational: "информационный",
  navigational: "навигационный",
  other: "не определён",
};

const fetchMethodLabels: Record<NonNullable<FetchMethod>, string> = {
  http: "HTTP",
  http_retry: "HTTP с повтором",
  browser: "браузер",
};

const humanLabelOverrides: Record<string, string> = {
  "Action Backlog": "Список действий",
  "Business identity signals": "Сведения о компании",
  "Commercial and Trust": "Коммерция и доверие",
  "Commercial completeness": "Оффер и запись/заявка",
  "Commercial fit": "Коммерческое соответствие",
  "Commercial signals": "Коммерческие сигналы",
  "Competitor Gap": "Разрыв с конкурентами",
  "Competitor context": "Конкурентный контекст",
  "Canonical consistency": "Корректность canonical",
  "Content depth": "Достаточность текста",
  "Content richness": "Смысловая полнота контента",
  "Contact accessibility": "Доступность контактов",
  CTA: "Призыв к действию",
  "Depth and semantic match": "Раскрытие темы по смыслу",
  "Gap до топа: commercial/trust": "Разрыв с топом: коммерция и доверие",
  "Gap до топа: intent alignment": "Разрыв с топом: соответствие намерению",
  "Gap до топа: semantic": "Разрыв с топом: смысловое соответствие",
  "Gap до топа: technical SEO": "Разрыв с топом: техническое SEO",
  Hreflang: "Hreflang-разметка",
  "Heading structure": "Структура заголовков",
  "Heading-query alignment": "Связь заголовков с запросом",
  "Informational fit": "Информационное соответствие",
  "Intent alignment": "Соответствие намерению",
  "Keyword balance": "Баланс ключевых слов",
  "Keyword coverage": "Покрытие ключевых слов",
  "Lexical uniqueness": "Разнообразие слов",
  "Local commercial fit": "Локально-коммерческое соответствие",
  "Meta description": "Мета-описание",
  "Meta description quality": "Качество мета-описания",
  "Meta viewport": "Мобильная область просмотра",
  "No issues": "Проблем не найдено.",
  "Offer and conversion completeness": "Оффер и запись/заявка",
  "Recommendation plan": "План рекомендаций",
  "Query intent": "Намерение запроса",
  "Query match": "Совпадение с запросом",
  "Query prominence": "Выраженность запроса",
  "Redirect efficiency": "Эффективность редиректов",
  "Semantic and Intent": "Смысл и намерение",
  "Semantic relevance": "Смысловое соответствие",
  "SERP gap score": "Паритет с лидерами выдачи",
  "SERP commercial and trust": "Коммерция и доверие относительно выдачи",
  "SERP content depth": "Глубина контента относительно выдачи",
  "SERP intent alignment": "Соответствие намерению относительно выдачи",
  "SERP semantic relevance": "Смысловое соответствие относительно выдачи",
  "SERP technical SEO": "Техническое SEO относительно выдачи",
  "SERP percentile": "Позиция относительно выдачи",
  "Social proof": "Социальное доказательство",
  "Technical indexability": "Индексируемость",
  "Technical metadata": "Технические метаданные",
  "Technical SEO": "Техническое SEO",
  "Text sufficiency": "Достаточность текста",
  "Text-to-HTML ratio": "Доля полезного текста",
  Title: "Заголовок title",
  "Title quality": "Качество заголовка title",
  "Title-query alignment": "Связь title с запросом",
  "Trust signals": "Сигналы доверия",
  "Цель: паритет с SERP-лидерами": "Цель: паритет с лидерами выдачи",
  "Цель: конкурентный диапазон SERP": "Цель: конкурентный диапазон выдачи",
  "URL hygiene": "Чистота URL",
};

export function getRecommendationGroupLabel(groupKey: RecommendationGroupKey): string {
  return recommendationGroupLabels[groupKey];
}

export function getRecommendationGroupDescription(group: Pick<RecommendationGroup, "key" | "description">): string {
  return recommendationGroupDescriptions[group.key] ?? group.description;
}

export function getRecommendationGroupEmptyState(group: Pick<RecommendationGroup, "key" | "empty_state">): string {
  return recommendationGroupEmptyStates[group.key] ?? getHumanReadableLabel(group.empty_state);
}

export function getIntentLabel(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return intentLabels[value] ?? value;
}

export function getFetchMethodLabel(value: FetchMethod | string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return fetchMethodLabels[value as NonNullable<FetchMethod>] ?? value;
}

export function getHumanReadableLabel(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }

  return humanLabelOverrides[value] ?? value;
}
