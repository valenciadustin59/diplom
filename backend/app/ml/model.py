from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
import logging
from pathlib import Path
import pickle
import random
from typing import Any

from sklearn.ensemble import RandomForestRegressor


logger = logging.getLogger(__name__)

FEATURE_COLUMNS = [
    "text_length_chars",
    "html_length_chars",
    "word_count",
    "unique_word_count",
    "unique_word_ratio",
    "avg_word_length",
    "sentence_count",
    "avg_sentence_length",
    "paragraph_count",
    "h1_count",
    "h2_count",
    "h3_count",
    "heading_count",
    "title_present",
    "title_length",
    "meta_description_present",
    "meta_description_length",
    "query_in_title",
    "query_in_text",
    "exact_query_count",
    "query_term_count",
    "title_query_term_count",
    "meta_query_term_count",
    "title_keyword_coverage_ratio",
    "meta_keyword_coverage_ratio",
    "query_terms_in_headings",
    "heading_query_coverage_ratio",
    "first_200_words_query_term_count",
    "query_density",
    "keyword_coverage_ratio",
    "link_count",
    "image_count",
    "list_item_count",
    "strong_tag_count",
    "form_count",
    "input_count",
    "inputs_per_form_ratio",
    "avg_paragraph_length",
    "link_density_per_1000_words",
    "image_density_per_1000_words",
    "list_density_per_1000_words",
    "strong_density_per_1000_words",
    "text_to_html_ratio",
    "semantic_similarity",
    "early_query_coverage_ratio",
    "conversion_signal_score",
    "content_link_ratio",
    "heading_paragraph_balance",
    "query_semantic_alignment",
    "title_semantic_alignment",
    "heading_semantic_alignment",
    "title_heading_keyword_alignment",
    "content_depth_semantic_score",
    "query_prominence_score",
    "title_length_quality",
    "meta_length_quality",
    "keyword_balance_score",
    "semantic_content_richness",
    "cta_semantic_score",
]

BACKEND_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = BACKEND_DIR / "artifacts"
DEFAULT_MODEL_PATH = ARTIFACTS_DIR / "page_quality_model.pkl"


def _resolve_model_path(model_path: str | Path | None = None) -> Path:
    return Path(model_path) if model_path is not None else DEFAULT_MODEL_PATH


def _rounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 4)


def _bounded_quality(value: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return max(0.0, 1.0 - (abs(value - target) / target))


def _vectorize_features(features: dict[str, float | int]) -> list[float]:
    return [float(features.get(name, 0.0)) for name in FEATURE_COLUMNS]


def _feature_value(features: dict[str, float | int], key: str) -> float:
    return float(features.get(key, 0.0))


def create_dataset(n_samples: int = 500, seed: int = 42) -> tuple[list[list[float]], list[float]]:
    rng = random.Random(seed)
    rows: list[list[float]] = []
    targets: list[float] = []

    for _ in range(n_samples):
        word_count = rng.randint(80, 3500)
        unique_word_ratio = rng.uniform(0.25, 0.95)
        unique_word_count = int(word_count * unique_word_ratio)
        sentence_count = max(1, word_count // rng.randint(8, 24))
        avg_sentence_length = word_count / sentence_count
        text_length_chars = word_count * rng.randint(4, 8)
        html_length_chars = text_length_chars + rng.randint(500, 12000)
        paragraph_count = max(1, word_count // rng.randint(40, 160))
        h1_count = rng.randint(0, 3)
        h2_count = rng.randint(0, 12)
        h3_count = rng.randint(0, 16)
        heading_count = h1_count + h2_count + h3_count
        title_present = rng.randint(0, 1)
        title_length = rng.randint(0, 80) if title_present else 0
        meta_description_present = rng.randint(0, 1)
        meta_description_length = rng.randint(0, 180) if meta_description_present else 0
        query_in_title = rng.randint(0, 1)
        query_in_text = rng.randint(0, 1)
        exact_query_count = rng.randint(0, 8)
        query_term_count = rng.randint(0, 30)
        title_query_term_count = rng.randint(0, 4)
        meta_query_term_count = rng.randint(0, 4)
        query_terms_in_headings = rng.randint(0, 6)
        first_200_words_query_term_count = rng.randint(0, 12)
        query_density = rng.uniform(0.0, 0.2)
        keyword_coverage_ratio = rng.uniform(0.0, 1.0)
        title_keyword_coverage_ratio = rng.uniform(0.0, 1.0)
        meta_keyword_coverage_ratio = rng.uniform(0.0, 1.0)
        heading_query_coverage_ratio = rng.uniform(0.0, 1.0)
        link_count = rng.randint(0, 150)
        image_count = rng.randint(0, 60)
        list_item_count = rng.randint(0, 80)
        strong_tag_count = rng.randint(0, 40)
        form_count = rng.randint(0, 5)
        input_count = rng.randint(0, 20)
        inputs_per_form_ratio = (input_count / form_count) if form_count else 0.0
        avg_paragraph_length = word_count / paragraph_count if paragraph_count else 0.0
        avg_word_length = rng.uniform(3.5, 8.0)
        text_to_html_ratio = rng.uniform(0.01, 0.9)
        semantic_similarity = rng.uniform(0.0, 1.0)

        early_query_coverage_ratio = min(first_200_words_query_term_count / 3.0, 1.0)
        conversion_signal_score = (
            int(form_count > 0)
            + int(input_count > 0)
            + int(image_count > 0)
            + int(list_item_count > 0)
        ) / 4.0
        content_link_ratio = (word_count / max(link_count, 1)) if word_count else 0.0
        heading_paragraph_balance = heading_count / paragraph_count if paragraph_count else 0.0
        query_semantic_alignment = semantic_similarity * keyword_coverage_ratio
        title_semantic_alignment = semantic_similarity * title_keyword_coverage_ratio
        heading_semantic_alignment = semantic_similarity * heading_query_coverage_ratio
        title_heading_keyword_alignment = title_keyword_coverage_ratio * heading_query_coverage_ratio
        content_depth_semantic_score = semantic_similarity * min(word_count / 1500.0, 1.0)
        query_prominence_score = (
            title_keyword_coverage_ratio * 0.35
            + heading_query_coverage_ratio * 0.25
            + early_query_coverage_ratio * 0.25
            + keyword_coverage_ratio * 0.15
        )
        title_length_quality = _bounded_quality(float(title_length), 55.0) if title_present else 0.0
        meta_length_quality = (
            _bounded_quality(float(meta_description_length), 145.0) if meta_description_present else 0.0
        )
        keyword_balance_score = keyword_coverage_ratio * max(
            0.0,
            1.0 - min(abs(query_density - 0.03) / 0.03, 1.0),
        )
        semantic_content_richness = semantic_similarity * min(word_count / 1800.0, 1.0) * min(
            unique_word_ratio,
            1.0,
        )
        cta_semantic_score = conversion_signal_score * semantic_similarity

        row_features = {
            "text_length_chars": float(text_length_chars),
            "html_length_chars": float(html_length_chars),
            "word_count": float(word_count),
            "unique_word_count": float(unique_word_count),
            "unique_word_ratio": float(unique_word_ratio),
            "avg_word_length": float(avg_word_length),
            "sentence_count": float(sentence_count),
            "avg_sentence_length": float(avg_sentence_length),
            "paragraph_count": float(paragraph_count),
            "h1_count": float(h1_count),
            "h2_count": float(h2_count),
            "h3_count": float(h3_count),
            "heading_count": float(heading_count),
            "title_present": float(title_present),
            "title_length": float(title_length),
            "meta_description_present": float(meta_description_present),
            "meta_description_length": float(meta_description_length),
            "query_in_title": float(query_in_title),
            "query_in_text": float(query_in_text),
            "exact_query_count": float(exact_query_count),
            "query_term_count": float(query_term_count),
            "title_query_term_count": float(title_query_term_count),
            "meta_query_term_count": float(meta_query_term_count),
            "title_keyword_coverage_ratio": float(title_keyword_coverage_ratio),
            "meta_keyword_coverage_ratio": float(meta_keyword_coverage_ratio),
            "query_terms_in_headings": float(query_terms_in_headings),
            "heading_query_coverage_ratio": float(heading_query_coverage_ratio),
            "first_200_words_query_term_count": float(first_200_words_query_term_count),
            "query_density": float(query_density),
            "keyword_coverage_ratio": float(keyword_coverage_ratio),
            "link_count": float(link_count),
            "image_count": float(image_count),
            "list_item_count": float(list_item_count),
            "strong_tag_count": float(strong_tag_count),
            "form_count": float(form_count),
            "input_count": float(input_count),
            "inputs_per_form_ratio": float(inputs_per_form_ratio),
            "avg_paragraph_length": float(avg_paragraph_length),
            "link_density_per_1000_words": float((link_count * 1000.0 / word_count) if word_count else 0.0),
            "image_density_per_1000_words": float((image_count * 1000.0 / word_count) if word_count else 0.0),
            "list_density_per_1000_words": float((list_item_count * 1000.0 / word_count) if word_count else 0.0),
            "strong_density_per_1000_words": float((strong_tag_count * 1000.0 / word_count) if word_count else 0.0),
            "text_to_html_ratio": float(text_to_html_ratio),
            "semantic_similarity": float(semantic_similarity),
            "early_query_coverage_ratio": float(early_query_coverage_ratio),
            "conversion_signal_score": float(conversion_signal_score),
            "content_link_ratio": float(content_link_ratio),
            "heading_paragraph_balance": float(heading_paragraph_balance),
            "query_semantic_alignment": float(query_semantic_alignment),
            "title_semantic_alignment": float(title_semantic_alignment),
            "heading_semantic_alignment": float(heading_semantic_alignment),
            "title_heading_keyword_alignment": float(title_heading_keyword_alignment),
            "content_depth_semantic_score": float(content_depth_semantic_score),
            "query_prominence_score": float(query_prominence_score),
            "title_length_quality": float(title_length_quality),
            "meta_length_quality": float(meta_length_quality),
            "keyword_balance_score": float(keyword_balance_score),
            "semantic_content_richness": float(semantic_content_richness),
            "cta_semantic_score": float(cta_semantic_score),
        }
        rows.append(_vectorize_features(row_features))

        score = 18.0
        score += min(word_count / 100.0, 18.0)
        score += keyword_coverage_ratio * 12.0
        score += semantic_similarity * 18.0
        score += query_semantic_alignment * 10.0
        score += title_semantic_alignment * 6.0
        score += heading_semantic_alignment * 5.0
        score += query_prominence_score * 6.0
        score += min(content_depth_semantic_score * 8.0, 8.0)
        score += semantic_content_richness * 9.0
        score += keyword_balance_score * 7.0
        score += cta_semantic_score * 4.0
        score += query_in_title * 8.0
        score += query_in_text * 6.0
        score += min(title_query_term_count, 3) * 1.8
        score += title_keyword_coverage_ratio * 4.5
        score += meta_keyword_coverage_ratio * 2.5
        score += title_length_quality * 3.5
        score += meta_length_quality * 2.5
        score += heading_query_coverage_ratio * 6.0
        score += min(first_200_words_query_term_count, 6) * 1.0
        score += title_present * 4.0
        score += meta_description_present * 3.0
        score += min(h2_count, 6) * 1.0
        score += min(text_to_html_ratio * 16.0, 10.0)
        score += min(link_count, 35) * 0.08
        score += min(image_count, 18) * 0.12
        score += min(form_count, 1) * 4.0
        score += min(inputs_per_form_ratio, 6.0) * 0.4
        score += conversion_signal_score * 3.0
        score -= abs(query_density - 0.03) * 140.0
        score -= min(abs(heading_paragraph_balance - 0.45) * 6.0, 5.0)
        score -= max(h1_count - 1, 0) * 3.0
        score -= max(title_length - 65, 0) * 0.18
        score -= max(avg_sentence_length - 28, 0) * 0.45
        score += rng.uniform(-3.5, 3.5)
        targets.append(_rounded_score(score))

    return rows, targets


def train_model(n_samples: int = 500, seed: int = 42) -> RandomForestRegressor:
    x_train, y_train = create_dataset(n_samples=n_samples, seed=seed)
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=10,
        min_samples_split=4,
        min_samples_leaf=2,
        random_state=seed,
        n_jobs=-1,
    )
    model.fit(x_train, y_train)
    return model


def save_model(
    model: Any,
    metrics: dict[str, Any],
    model_path: str | Path | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    output_path = _resolve_model_path(model_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload_metadata = dict(metadata or {})
    payload = {
        "model": model,
        "metrics": dict(metrics),
        "feature_columns": payload_metadata.pop("feature_columns", FEATURE_COLUMNS),
        "trained_at": payload_metadata.pop("trained_at", datetime.now(UTC).isoformat()),
        "source": payload_metadata.pop("source", "local_dataset"),
        "model_type": payload_metadata.pop("model_type", model.__class__.__name__),
        **payload_metadata,
    }
    with output_path.open("wb") as file:
        pickle.dump(payload, file)
    return output_path


def load_saved_model(model_path: str | Path | None = None) -> dict[str, object] | None:
    resolved_path = _resolve_model_path(model_path)
    if not resolved_path.exists():
        return None
    with resolved_path.open("rb") as file:
        payload = pickle.load(file)
    return payload if isinstance(payload, dict) else None


def _bootstrap_artifact() -> dict[str, object]:
    bootstrap_model = train_model()
    return {
        "model": bootstrap_model,
        "metrics": {},
        "feature_columns": FEATURE_COLUMNS,
        "trained_at": None,
        "source": "bootstrap",
        "model_type": bootstrap_model.__class__.__name__,
        "rows_count": 0,
        "queries_count": 0,
        "domains_count": 0,
        "dataset_version": None,
    }


def _ensure_artifact_compatibility(payload: dict[str, object]) -> dict[str, object]:
    model = payload.get("model")
    if model is None or not hasattr(model, "predict"):
        raise TypeError("Saved artifact does not contain a compatible model with predict().")

    feature_columns = payload.get("feature_columns")
    if list(feature_columns or []) != FEATURE_COLUMNS:
        raise ValueError("Saved artifact feature schema does not match current FEATURE_COLUMNS.")

    metrics = payload.get("metrics")
    normalized_metrics = metrics if isinstance(metrics, dict) else {}
    return {
        "model": model,
        "metrics": normalized_metrics,
        "feature_columns": FEATURE_COLUMNS,
        "trained_at": payload.get("trained_at"),
        "source": payload.get("source", "local_dataset"),
        "model_type": payload.get("model_type", model.__class__.__name__),
        "rows_count": int(payload.get("rows_count") or normalized_metrics.get("rows_count") or 0),
        "queries_count": int(payload.get("queries_count") or 0),
        "domains_count": int(payload.get("domains_count") or 0),
        "dataset_version": payload.get("dataset_version"),
    }


@lru_cache(maxsize=4)
def _get_cached_model_artifact(model_path_str: str) -> dict[str, object]:
    saved_payload = load_saved_model(model_path_str)
    if saved_payload is not None:
        try:
            return _ensure_artifact_compatibility(saved_payload)
        except Exception as error:
            logger.warning("Falling back to bootstrap model due to artifact incompatibility: %s", error)
    return _bootstrap_artifact()


def clear_model_cache() -> None:
    _get_cached_model_artifact.cache_clear()


def get_model_artifact(model_path: str | Path | None = None) -> dict[str, object]:
    return _get_cached_model_artifact(str(_resolve_model_path(model_path)))


def _build_model_info(artifact: dict[str, object]) -> dict[str, object]:
    return {
        "source": artifact.get("source", "unknown"),
        "model_type": artifact.get("model_type", artifact["model"].__class__.__name__),
        "trained_at": artifact.get("trained_at"),
        "dataset_rows": int(artifact.get("rows_count") or 0),
        "dataset_version": artifact.get("dataset_version"),
    }


def calculate_rule_score(features: dict[str, float | int]) -> tuple[float, list[dict[str, object]]]:
    factors: list[dict[str, object]] = []
    score = 45.0

    def add_factor(code: str, label: str, impact: float, detail: str) -> None:
        nonlocal score
        score += impact
        factors.append(
            {
                "code": code,
                "label": label,
                "impact": round(impact, 2),
                "detail": detail,
            }
        )

    title_present = int(_feature_value(features, "title_present"))
    meta_description_present = int(_feature_value(features, "meta_description_present"))
    h1_count = int(_feature_value(features, "h1_count"))
    word_count = _feature_value(features, "word_count")
    keyword_coverage_ratio = _feature_value(features, "keyword_coverage_ratio")
    title_keyword_coverage_ratio = _feature_value(features, "title_keyword_coverage_ratio")
    heading_query_coverage_ratio = _feature_value(features, "heading_query_coverage_ratio")
    semantic_similarity = _feature_value(features, "semantic_similarity")
    query_density = _feature_value(features, "query_density")
    text_to_html_ratio = _feature_value(features, "text_to_html_ratio")
    query_semantic_alignment = _feature_value(features, "query_semantic_alignment")
    title_semantic_alignment = _feature_value(features, "title_semantic_alignment")
    heading_semantic_alignment = _feature_value(features, "heading_semantic_alignment")
    query_prominence_score = _feature_value(features, "query_prominence_score")
    content_depth_semantic_score = _feature_value(features, "content_depth_semantic_score")
    heading_paragraph_balance = _feature_value(features, "heading_paragraph_balance")
    conversion_signal_score = _feature_value(features, "conversion_signal_score")
    keyword_balance_score = _feature_value(features, "keyword_balance_score")
    semantic_content_richness = _feature_value(features, "semantic_content_richness")
    cta_semantic_score = _feature_value(features, "cta_semantic_score")
    title_length_quality = _feature_value(features, "title_length_quality")
    meta_length_quality = _feature_value(features, "meta_length_quality")

    if title_present:
        add_factor("TITLE_PRESENT", "Есть title", 5.0, "У страницы есть title, это базовый SEO-сигнал.")
    else:
        add_factor("MISSING_TITLE", "Нет title", -9.0, "Нужно добавить title, иначе страница теряет понятный поисковый заголовок.")

    if int(_feature_value(features, "query_in_title")):
        add_factor("QUERY_IN_TITLE", "Запрос отражён в title", 6.0, "Title явно поддерживает основной поисковый интент.")
    else:
        add_factor("NO_QUERY_IN_TITLE", "Запрос не отражён в title", -6.0, "Title не помогает поиску понять главный запрос страницы.")

    if meta_description_present:
        add_factor("META_DESCRIPTION", "Есть meta description", 2.5, "Описание присутствует и помогает формировать сниппет.")
    else:
        add_factor("NO_META_DESCRIPTION", "Нет meta description", -2.5, "Стоит добавить описание, чтобы страница выглядела сильнее в выдаче.")

    if h1_count == 1:
        add_factor("GOOD_H1", "Один H1", 4.0, "Основной заголовок оформлен аккуратно и без дублей.")
    elif h1_count == 0:
        add_factor("NO_H1", "Нет H1", -6.0, "Странице нужен один главный заголовок.")
    else:
        add_factor("MULTIPLE_H1", "Несколько H1", -3.5, "Лучше оставить один основной H1 и вынести остальное в H2-H3.")

    if word_count >= 1600:
        add_factor("DETAILED_TEXT", "Глубина контента высокая", 6.0, "Контент достаточно подробный для коммерческой страницы.")
    elif word_count >= 900:
        add_factor("SOLID_TEXT", "Глубина контента нормальная", 3.0, "Контент не пустой, но его ещё можно усилить.")
    else:
        add_factor("THIN_TEXT", "Контент слишком тонкий", -7.0, "Текста недостаточно, чтобы страница выглядела сильной относительно конкурентов.")

    if keyword_coverage_ratio >= 0.8:
        add_factor("GOOD_KEYWORD_COVERAGE", "Запрос покрыт лексически", 5.0, "Текст использует большую часть слов из запроса.")
    elif keyword_coverage_ratio < 0.45:
        add_factor("LOW_KEYWORD_COVERAGE", "Запрос покрыт слабо", -5.5, "Странице не хватает словаря и формулировок, близких к запросу.")

    if semantic_similarity >= 0.72:
        add_factor("STRONG_SEMANTICS", "Смысл текста близок к запросу", 7.0, "Страница релевантна запросу не только по словам, но и по смыслу.")
    elif semantic_similarity < 0.5:
        add_factor("WEAK_SEMANTICS", "Смысл текста недостаточно релевантен", -7.0, "Даже если ключевые слова встречаются, общий смысл страницы пока слабый.")

    if query_semantic_alignment >= 0.55:
        add_factor("QUERY_SEMANTIC_ALIGNMENT", "Семантика и keyword coverage работают вместе", 8.0, "Модель видит, что страница одновременно покрывает запрос по словам и по смыслу.")
    elif semantic_similarity >= 0.55 and keyword_coverage_ratio < 0.4:
        add_factor("SEMANTICS_WITHOUT_QUERY_COVERAGE", "Есть смысловая близость, но слабое покрытие запроса", -4.0, "Контент тематически близок, но недостаточно явно закрывает сам запрос.")
    elif keyword_coverage_ratio >= 0.7 and semantic_similarity < 0.4:
        add_factor("KEYWORDS_WITHOUT_SEMANTICS", "Есть ключевые слова, но мало смысловой релевантности", -4.0, "Похожий на переоптимизацию случай: слова есть, а смысловое соответствие слабое.")

    if title_semantic_alignment >= 0.35 and heading_semantic_alignment >= 0.3:
        add_factor("TITLE_HEADING_ALIGNMENT", "Title и заголовки поддерживают один интент", 5.0, "Верх страницы согласован: и title, и H1-H3 ведут пользователя в одну тему.")
    elif title_keyword_coverage_ratio == 0 and heading_query_coverage_ratio == 0:
        add_factor("WEAK_TOP_STRUCTURE", "Верх страницы не транслирует запрос", -4.5, "Ни title, ни заголовки не помогают быстро понять релевантность страницы.")

    if query_prominence_score >= 0.65:
        add_factor("STRONG_QUERY_PROMINENCE", "Запрос хорошо вынесен в верх страницы", 4.5, "Ключевой интент заметен в title, заголовках и начале текста.")
    elif query_prominence_score < 0.3:
        add_factor("WEAK_QUERY_PROMINENCE", "Запрос слабо вынесен в ключевые зоны", -4.0, "Запрос не закреплён в title, заголовках и ранней части текста.")

    if keyword_balance_score >= 0.5:
        add_factor("BALANCED_QUERY_USAGE", "Запрос распределён естественно", 3.0, "Модель видит хороший баланс между покрытием запроса и плотностью ключевых слов.")
    elif query_density > 0.09:
        add_factor("OVEROPTIMIZED_QUERY", "Есть риск переспама", -4.5, "Плотность ключевых слов слишком высокая, это может выглядеть искусственно.")
    else:
        add_factor("LOW_QUERY_SIGNAL", "Сигнал запроса выражен слабо", -2.0, "Запрос присутствует недостаточно заметно или распределён неудачно.")

    if content_depth_semantic_score >= 0.45 and semantic_content_richness >= 0.3:
        add_factor("DEEP_RELEVANT_CONTENT", "Контент одновременно глубокий и релевантный", 6.0, "Это сильная совокупность признаков: хороший объём, смысловая близость и разнообразный словарь.")
    elif word_count >= 1200 and semantic_similarity < 0.4:
        add_factor("LONG_BUT_OFF_TARGET", "Контент объёмный, но уходит от запроса", -4.0, "Большой объём сам по себе не помогает, если страница смыслово уходит в сторону.")

    if 0.18 <= text_to_html_ratio <= 0.7:
        add_factor("GOOD_TEXT_HTML", "Текст и разметка сбалансированы", 3.0, "На странице достаточно полезного текста относительно HTML-обвязки.")
    elif text_to_html_ratio < 0.08:
        add_factor("LOW_TEXT_HTML", "Слишком много обвязки и мало текста", -4.0, "HTML много, а полезного содержимого мало.")

    if 0.18 <= heading_paragraph_balance <= 0.7:
        add_factor("HEADING_BALANCE", "Структура заголовков выглядит здоровой", 2.5, "Количество заголовков и абзацев находится в адекватном соотношении.")
    elif heading_paragraph_balance > 1.0:
        add_factor("HEADING_OVERLOAD", "Структура выглядит дробной", -2.5, "Заголовков слишком много относительно объёма текста.")

    if conversion_signal_score >= 0.5 and cta_semantic_score >= 0.3:
        add_factor("RELEVANT_CTA", "Коммерческие элементы поддерживают контент", 3.5, "Формы, CTA и контент выглядят согласованно для коммерческого интента.")
    elif conversion_signal_score == 0 and word_count > 800:
        add_factor("NO_CONVERSION_LAYER", "Нет конверсионного слоя", -2.5, "Для коммерческой страницы не хватает формы, CTA или других точек действия.")

    if title_length_quality >= 0.7:
        add_factor("TITLE_LENGTH_OK", "Длина title близка к рабочему диапазону", 1.5, "Title не слишком короткий и не слишком длинный.")
    elif title_present and title_length_quality < 0.35:
        add_factor("TITLE_LENGTH_WEAK", "Длина title неудачна", -1.5, "Title либо слишком короткий, либо перегруженный.")

    if meta_description_present and meta_length_quality >= 0.6:
        add_factor("META_LENGTH_OK", "Meta description выглядит рабочим", 1.0, "Описание не выглядит слишком коротким или обрезанным.")

    return _rounded_score(score), factors


def _predict_model_score(features: dict[str, float | int], model_path: str | Path | None = None) -> float:
    artifact = get_model_artifact(model_path)
    model = artifact["model"]
    vector = _vectorize_features(features)
    return _rounded_score(float(model.predict([vector])[0]))


def _interaction_signals(features: dict[str, float | int]) -> dict[str, float]:
    return {
        "query_semantic_alignment": round(_feature_value(features, "query_semantic_alignment"), 4),
        "title_semantic_alignment": round(_feature_value(features, "title_semantic_alignment"), 4),
        "heading_semantic_alignment": round(_feature_value(features, "heading_semantic_alignment"), 4),
        "query_prominence_score": round(_feature_value(features, "query_prominence_score"), 4),
        "keyword_balance_score": round(_feature_value(features, "keyword_balance_score"), 4),
        "semantic_content_richness": round(_feature_value(features, "semantic_content_richness"), 4),
        "cta_semantic_score": round(_feature_value(features, "cta_semantic_score"), 4),
    }


def explain_score(
    features: dict[str, float | int],
    model_path: str | Path | None = None,
) -> dict[str, object]:
    artifact = get_model_artifact(model_path)
    ml_score = _predict_model_score(features, model_path=model_path)
    rule_score, factors = calculate_rule_score(features)

    rule_weight = 0.65 if artifact.get("source") == "bootstrap" else 0.45
    ml_weight = 1.0 - rule_weight
    final_score = _rounded_score(rule_score * rule_weight + ml_score * ml_weight)

    positives = sorted(
        [factor for factor in factors if float(factor["impact"]) > 0],
        key=lambda item: float(item["impact"]),
        reverse=True,
    )[:4]
    negatives = sorted(
        [factor for factor in factors if float(factor["impact"]) < 0],
        key=lambda item: float(item["impact"]),
    )[:4]

    methodology = (
        "Итоговый score строится как гибрид explainable-слоя и ML-модели. "
        f"Сейчас {int(rule_weight * 100)}% веса дают объяснимые SEO и контентные сигналы, "
        f"ещё {int(ml_weight * 100)}% даёт табличная ML-модель. "
        "Ключевая идея модели не в отдельных метриках, а в их сочетаниях: "
        "например, смысловая близость усиливается только тогда, когда страница одновременно "
        "покрывает запрос по словам, выносит его в title и заголовки, держит естественный баланс ключевых слов "
        "и даёт достаточно глубокий контент."
    )

    return {
        "final_score": final_score,
        "rule_score": rule_score,
        "ml_score": ml_score,
        "methodology": methodology,
        "model_info": _build_model_info(artifact),
        "interaction_signals": _interaction_signals(features),
        "positives": positives,
        "negatives": negatives,
        "factors": factors,
    }


def predict_score(features: dict[str, float | int], model_path: str | Path | None = None) -> float:
    explanation = explain_score(features, model_path=model_path)
    return float(explanation["final_score"])


def score_pages(
    pages_features: list[dict[str, float | int]],
    model_path: str | Path | None = None,
) -> list[float]:
    return [predict_score(features, model_path=model_path) for features in pages_features]


def average_score(
    pages_features: list[dict[str, float | int]],
    model_path: str | Path | None = None,
) -> float:
    if not pages_features:
        return 0.0
    scores = score_pages(pages_features, model_path=model_path)
    return round(sum(scores) / len(scores), 4)


def compare_with_competitors(
    user_pages_features: list[dict[str, float | int]],
    competitor_pages_features: list[dict[str, float | int]],
    model_path: str | Path | None = None,
) -> dict[str, float | list[float]]:
    user_scores = score_pages(user_pages_features, model_path=model_path)
    competitor_scores = score_pages(competitor_pages_features, model_path=model_path)

    user_average_score = round(sum(user_scores) / len(user_scores), 4) if user_scores else 0.0
    competitors_average_score = (
        round(sum(competitor_scores) / len(competitor_scores), 4) if competitor_scores else 0.0
    )
    score_difference = round(user_average_score - competitors_average_score, 4)

    return {
        "user_scores": user_scores,
        "competitor_scores": competitor_scores,
        "user_average_score": user_average_score,
        "competitors_average_score": competitors_average_score,
        "score_difference": score_difference,
    }


def train_and_predict(
    features: dict[str, float | int],
    model_path: str | Path | None = None,
) -> dict[str, Any]:
    explanation = explain_score(features, model_path=model_path)
    artifact = get_model_artifact(model_path)
    metrics = artifact.get("metrics", {})
    model_info = _build_model_info(artifact)
    return {
        "model_type": str(model_info["model_type"]),
        "feature_count": len(FEATURE_COLUMNS),
        "score": float(explanation["final_score"]),
        "rule_score": float(explanation["rule_score"]),
        "ml_score": float(explanation["ml_score"]),
        "metrics": metrics if isinstance(metrics, dict) else {},
        "source": str(model_info["source"]),
        "model_info": model_info,
    }
