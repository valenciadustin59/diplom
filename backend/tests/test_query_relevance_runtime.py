from app.features import build_features
from app.query_relevance import (
    build_query_relevance_guardrail,
    build_query_relevance_preflight_decision,
    has_strong_query_topic_fit,
)
from app.semantic_providers import (
    DEFAULT_ROSBERTA_MODEL,
    ROSBERTA_PROVIDER,
    build_semantic_numeric_metadata,
)


def _patch_semantic_similarity(monkeypatch, value: float) -> None:
    monkeypatch.setattr(
        "app.features.build_semantic_features",
        lambda text, query: {"semantic_similarity": value},
    )


def _rosberta_metadata() -> dict[str, float | int]:
    return build_semantic_numeric_metadata(
        provider=ROSBERTA_PROVIDER,
        model_name=DEFAULT_ROSBERTA_MODEL,
        fallback_used=False,
    )


def _rosberta_semantic_payload(similarity: float) -> dict[str, float | int]:
    return {
        "semantic_similarity": similarity,
        "semantic_similarity_raw": max(0.0, similarity - 0.04),
        **_rosberta_metadata(),
    }


def _base_relevance_features(**overrides: float | int) -> dict[str, float | int]:
    features: dict[str, float | int] = {
        "http_status_code": 200,
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "word_count": 1200,
        "text_length_chars": 7200,
        "semantic_similarity": 0.32,
        "keyword_coverage_ratio": 0.0,
        "query_core_keyword_coverage_ratio": 0.0,
        "query_intent_modifier_coverage_ratio": 0.0,
        "query_density": 0.0,
        "query_core_term_count": 0,
        "exact_query_count": 0,
        "query_in_title": 0,
        "query_in_text": 0,
        "title_semantic_alignment": 0.0,
        "heading_semantic_alignment": 0.0,
        "query_prominence_score": 0.0,
        **_rosberta_metadata(),
    }
    features.update(overrides)
    return features


def test_d88_rosberta_full_mismatch_still_stays_near_zero():
    features = _base_relevance_features(semantic_similarity=0.06)

    decision = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, 93.0)

    assert decision["should_stop"] is True
    assert guardrail["early_stop"] is True
    assert guardrail["band"] == "full_mismatch"
    assert 0.0 <= guardrail["adjusted_score"] <= 5.0
    assert guardrail["semantic_layer"]["provider"] == ROSBERTA_PROVIDER
    assert guardrail["semantic_layer"]["model_name"] == DEFAULT_ROSBERTA_MODEL


def test_commercial_modifier_only_match_is_capped_near_zero():
    features = _base_relevance_features(
        semantic_similarity=0.505,
        keyword_coverage_ratio=0.333333,
        query_core_keyword_coverage_ratio=0.0,
        query_intent_modifier_coverage_ratio=1.0,
        query_density=0.000233,
        query_core_term_count=0,
        title_semantic_alignment=0.1683,
        query_prominence_score=0.25,
    )

    decision = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, 93.0)

    assert decision["should_stop"] is False
    assert guardrail["early_stop"] is False
    assert guardrail["reason"] == "commercial_modifier_only_core_mismatch"
    assert guardrail["band"] == "core_mismatch"
    assert guardrail["band_max"] == 8.0
    assert guardrail["adjusted_score"] <= 8.0


def test_d100_labirint_like_city_bookstore_is_not_soft_partial_match():
    query = "детский стоматолог екатеринбург"
    text = (
        "Детские книги и учебные пособия в Екатеринбурге. "
        "Каталог книжного магазина, доставка заказов, акции и подборки для детей. "
        "На странице есть адрес пункта выдачи в Екатеринбурге, отзывы покупателей и условия оплаты. "
        * 8
    )
    html = (
        "<html><head><title>Детские книги в Екатеринбурге</title></head>"
        f"<body><h1>Детские книги и учебники</h1><p>{text}</p></body></html>"
    )

    features = build_features(
        html=html,
        text=text,
        query=query,
        semantic_features=_rosberta_semantic_payload(0.50),
    )
    guardrail = build_query_relevance_guardrail(features, 82.0)

    assert features["query_geo_modifier_coverage_ratio"] == 1.0
    assert features["query_core_keyword_coverage_ratio"] == 0.5
    assert features["query_primary_core_term_present"] == 0
    assert features["core_missing_but_geo_present"] == 1
    assert guardrail["early_stop"] is False
    assert guardrail["reason"] == "local_service_core_mismatch"
    assert guardrail["band"] == "probable_mismatch"
    assert guardrail["adjusted_score"] == 20.5


def test_d100_pokrishka_like_winter_tires_keeps_strong_core_fit():
    query = "купить зимние шины"
    text = (
        "Зимние шины для легковых автомобилей: каталог размеров, цены, наличие и доставка. "
        "Можно выбрать нешипованные и шипованные шины, сравнить бренды и оформить заказ. "
        * 8
    )
    html = (
        "<html><head><title>Купить зимние шины</title></head>"
        f"<body><h1>Зимние шины купить онлайн</h1><p>{text}</p></body></html>"
    )

    features = build_features(
        html=html,
        text=text,
        query=query,
        semantic_features=_rosberta_semantic_payload(0.36),
    )
    guardrail = build_query_relevance_guardrail(features, 86.0)

    assert features["query_primary_core_term_present"] == 1
    assert features["query_core_keyword_coverage_ratio"] == 1.0
    assert has_strong_query_topic_fit(features) is True
    assert guardrail["active"] is False
    assert guardrail["adjusted_score"] == 86.0


def test_d101_wikipedia_like_informational_query_has_no_commercial_penalty():
    query = "что такое вулкан"
    text = (
        "Что такое вулкан: вулкан это геологическое образование, через которое магма, пепел и газы "
        "выходят на поверхность Земли. Статья объясняет строение вулкана, извержения и типы лавы. "
        * 8
    )
    html = (
        "<html><head><title>Что такое вулкан</title></head>"
        f"<body><h1>Что такое вулкан</h1><p>{text}</p></body></html>"
    )

    features = build_features(
        html=html,
        text=text,
        query=query,
        semantic_features=_rosberta_semantic_payload(0.34),
    )
    guardrail = build_query_relevance_guardrail(features, 77.0)

    assert features["query_primary_core_term_present"] == 1
    assert features["query_core_keyword_coverage_ratio"] == 1.0
    assert has_strong_query_topic_fit(features) is True
    assert guardrail["early_stop"] is False
    assert guardrail["active"] is False
    assert guardrail["adjusted_score"] == 77.0


def test_d89_rosberta_approximate_match_is_not_probable_mismatch():
    features = _base_relevance_features(
        semantic_similarity=0.34,
        semantic_similarity_raw=0.29,
        keyword_coverage_ratio=0.0,
        query_core_keyword_coverage_ratio=0.0,
        query_density=0.0,
        query_core_term_count=0,
    )

    decision = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, 86.0)

    assert decision["should_stop"] is False
    assert guardrail["early_stop"] is False
    assert guardrail["band"] == "weak_match"
    assert guardrail["adjusted_score"] > 25.0
    assert guardrail["adjusted_score"] == 47.3


def test_d89_rosberta_relevant_page_without_commercial_modifier_keeps_score():
    features = _base_relevance_features(
        semantic_similarity=0.31,
        keyword_coverage_ratio=0.666667,
        query_core_keyword_coverage_ratio=1.0,
        query_intent_modifier_coverage_ratio=0.0,
        query_density=0.006,
        query_core_term_count=8,
        query_in_text=1,
        title_semantic_alignment=0.55,
        heading_semantic_alignment=0.62,
        query_prominence_score=0.58,
    )

    guardrail = build_query_relevance_guardrail(features, 82.0)

    assert has_strong_query_topic_fit(features) is True
    assert guardrail["active"] is False
    assert guardrail["adjusted_score"] == 82.0


def test_d89_commercial_modifiers_are_counted_only_from_query(monkeypatch):
    monkeypatch.setattr(
        "app.features.build_semantic_features",
        lambda text, query: {
            "semantic_similarity": 0.42,
            "semantic_similarity_raw": 0.36,
            **_rosberta_metadata(),
        },
    )
    query = "\u0447\u0435\u043a\u0430\u043f \u043e\u0440\u0433\u0430\u043d\u0438\u0437\u043c\u0430"
    text = (
        "\u0427\u0435\u043a\u0430\u043f \u043e\u0440\u0433\u0430\u043d\u0438\u0437\u043c\u0430 "
        "\u0432\u043a\u043b\u044e\u0447\u0430\u0435\u0442 \u043e\u0441\u043c\u043e\u0442\u0440, "
        "\u0430\u043d\u0430\u043b\u0438\u0437\u044b \u0438 \u043a\u043e\u043d\u0441\u0443\u043b\u044c\u0442\u0430\u0446\u0438\u044e. "
        "\u041d\u0430 \u0441\u0430\u0439\u0442\u0435 \u0435\u0441\u0442\u044c \u0441\u043b\u043e\u0432\u0430 "
        "\u043a\u0443\u043f\u0438\u0442\u044c, \u0446\u0435\u043d\u0430 \u0438 \u0437\u0430\u043a\u0430\u0437\u0430\u0442\u044c, "
        "\u043d\u043e \u043e\u043d\u0438 \u043d\u0435 \u0447\u0430\u0441\u0442\u044c \u0437\u0430\u043f\u0440\u043e\u0441\u0430."
    )

    features = build_features(html=f"<html><body><p>{text}</p></body></html>", text=text, query=query)

    assert features["query_intent_modifier_count"] == 0
    assert features["query_intent_modifier_matches"] == 0
    assert features["query_intent_modifier_coverage_ratio"] == 0.0
    assert features["query_core_keyword_coverage_ratio"] == 1.0


def test_d89_commercial_modifier_only_match_does_not_hide_core_mismatch(monkeypatch):
    monkeypatch.setattr(
        "app.features.build_semantic_features",
        lambda text, query: {
            "semantic_similarity": 0.29,
            "semantic_similarity_raw": 0.24,
            **_rosberta_metadata(),
        },
    )
    query = "\u043a\u0443\u043f\u0438\u0442\u044c \u0430\u043d\u0430\u043b\u0438\u0437\u044b \u043a\u0440\u043e\u0432\u0438"
    text = (
        "\u041a\u0443\u043f\u0438\u0442\u044c \u043d\u043e\u0443\u0442\u0431\u0443\u043a "
        "\u0441 \u0434\u043e\u0441\u0442\u0430\u0432\u043a\u043e\u0439 \u0438 \u0433\u0430\u0440\u0430\u043d\u0442\u0438\u0435\u0439. "
        "\u041a\u0430\u0442\u0430\u043b\u043e\u0433 \u043e\u043f\u0438\u0441\u044b\u0432\u0430\u0435\u0442 "
        "\u044d\u043a\u0440\u0430\u043d, \u043f\u0440\u043e\u0446\u0435\u0441\u0441\u043e\u0440, "
        "\u043f\u0430\u043c\u044f\u0442\u044c, \u0430\u043a\u043a\u0443\u043c\u0443\u043b\u044f\u0442\u043e\u0440, "
        "\u043f\u043e\u0440\u0442\u044b, \u043a\u043b\u0430\u0432\u0438\u0430\u0442\u0443\u0440\u0443, "
        "\u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b \u043a\u043e\u0440\u043f\u0443\u0441\u0430 "
        "\u0438 \u0443\u0441\u043b\u043e\u0432\u0438\u044f \u0441\u0435\u0440\u0432\u0438\u0441\u0430 "
        "\u0434\u043b\u044f \u044d\u043b\u0435\u043a\u0442\u0440\u043e\u043d\u0438\u043a\u0438."
    )

    features = build_features(html=f"<html><body><p>{text}</p></body></html>", text=text, query=query)
    guardrail = build_query_relevance_guardrail(features, 88.0)

    assert features["query_intent_modifier_coverage_ratio"] == 1.0
    assert features["query_core_keyword_coverage_ratio"] == 0.0
    assert guardrail["active"] is True
    assert guardrail["reason"] == "commercial_modifier_only_core_mismatch"
    assert guardrail["band"] == "core_mismatch"
    assert guardrail["adjusted_score"] <= 8.0


def test_relevant_medical_page_keeps_score_with_russian_word_forms(monkeypatch):
    _patch_semantic_similarity(monkeypatch, 0.22)
    html = """
    <html>
      <head>
        <title>Детская стоматология в Екатеринбурге</title>
        <meta name="description" content="Лечение зубов детям, запись к детскому стоматологу." />
      </head>
      <body>
        <h1>Детские стоматологи в Екатеринбурге</h1>
        <p>В клинике работает отделение детской стоматологии: осмотр, лечение кариеса,
        адаптация ребёнка и запись на приём к врачу.</p>
      </body>
    </html>
    """

    features = build_features(html=html, text="", query="детская стоматология екатеринбург")
    guardrail = build_query_relevance_guardrail(features, 84.0)

    assert features["keyword_coverage_ratio"] == 1.0
    assert features["query_core_keyword_coverage_ratio"] == 1.0
    assert has_strong_query_topic_fit(features) is True
    assert guardrail["active"] is False
    assert guardrail["adjusted_score"] == 84.0


def test_relevant_storage_page_keeps_score_with_inflected_commercial_query(monkeypatch):
    _patch_semantic_similarity(monkeypatch, 0.24)
    html = """
    <html>
      <head>
        <title>Складские помещения в аренду</title>
        <meta name="description" content="Аренда складов и помещений для бизнеса." />
      </head>
      <body>
        <h1>Складские помещения для аренды</h1>
        <p>Сдаём тёплые складские помещения разной площади. Можно выбрать помещение
        под хранение товара, получить договор аренды и оставить заявку на просмотр.</p>
      </body>
    </html>
    """

    features = build_features(html=html, text="", query="аренда складского помещения")
    guardrail = build_query_relevance_guardrail(features, 79.0)

    assert features["keyword_coverage_ratio"] == 1.0
    assert features["query_core_keyword_coverage_ratio"] == 1.0
    assert has_strong_query_topic_fit(features) is True
    assert guardrail["active"] is False


def test_relevant_noncommercial_query_does_not_require_buy_or_price_terms(monkeypatch):
    _patch_semantic_similarity(monkeypatch, 0.21)
    html = """
    <html>
      <head>
        <title>Пересадка орхидеи после цветения</title>
        <meta name="description" content="Когда пересаживать орхидею и как подготовить корни после цветения." />
      </head>
      <body>
        <h1>Как пересадить орхидею после цветения</h1>
        <p>Инструкция объясняет пересадку орхидеи после цветения: осмотр корней,
        выбор прозрачного горшка, удаление сухих участков и аккуратное добавление
        свежего субстрата без стресса для растения.</p>
      </body>
    </html>
    """

    features = build_features(html=html, text="", query="пересадка орхидеи после цветения")
    guardrail = build_query_relevance_guardrail(features, 78.0)

    assert features["query_intent_modifier_count"] == 0
    assert features["query_intent_modifier_coverage_ratio"] == 0.0
    assert features["query_core_keyword_coverage_ratio"] == 1.0
    assert has_strong_query_topic_fit(features) is True
    assert guardrail["active"] is False
    assert guardrail["adjusted_score"] == 78.0


def test_unrelated_ecommerce_page_is_capped_when_only_intent_modifier_matches(monkeypatch):
    _patch_semantic_similarity(monkeypatch, 0.29)
    html = """
    <html>
      <head>
        <title>Игровые ноутбуки купить онлайн</title>
        <meta name="description" content="Каталог ноутбуков, скидки, гарантия и доставка." />
      </head>
      <body>
        <h1>Купить игровой ноутбук</h1>
        <p>Интернет-магазин предлагает ноутбуки для игр, аксессуары, рассрочку,
        быструю доставку и гарантийное обслуживание.</p>
      </body>
    </html>
    """

    features = build_features(html=html, text="", query="купить беговую дорожку")
    guardrail = build_query_relevance_guardrail(features, 88.0)

    assert features["keyword_coverage_ratio"] == 0.333333
    assert features["query_intent_modifier_coverage_ratio"] == 1.0
    assert features["query_core_keyword_coverage_ratio"] == 0.0
    assert guardrail["active"] is True
    assert guardrail["reason"] == "probable_query_topic_mismatch"
    assert guardrail["band"] == "probable_mismatch"
    assert guardrail["band_min"] == 6.0
    assert guardrail["band_max"] == 25.0
    assert guardrail["query_relevance_multiplier"] == 0.25
    assert guardrail["adjusted_score"] == 22.0
    assert guardrail["early_stop"] is False


def test_relevant_product_page_without_buy_word_keeps_value_for_commercial_query(monkeypatch):
    _patch_semantic_similarity(monkeypatch, 0.26)
    html = """
    <html>
      <head>
        <title>Беговые дорожки для дома</title>
        <meta name="description" content="Подбор домашних беговых дорожек по размеру, нагрузке и типу полотна." />
      </head>
      <body>
        <h1>Беговые дорожки для квартиры и дома</h1>
        <p>Раздел помогает выбрать беговую дорожку под тренировки дома: сравнение мощности,
        амортизации, складной конструкции, ширины полотна и нагрузки пользователя.</p>
        <p>Есть описания дорожек для ходьбы, интервальных тренировок и восстановления после перерыва.</p>
      </body>
    </html>
    """

    features = build_features(html=html, text="", query="купить беговую дорожку")
    guardrail = build_query_relevance_guardrail(features, 87.0)

    assert features["keyword_coverage_ratio"] == 0.666667
    assert features["query_intent_modifier_coverage_ratio"] == 0.0
    assert features["query_core_keyword_coverage_ratio"] == 1.0
    assert has_strong_query_topic_fit(features) is True
    assert guardrail["active"] is False
    assert guardrail["adjusted_score"] == 87.0


def test_relevant_service_page_without_price_word_keeps_value_for_price_query(monkeypatch):
    _patch_semantic_similarity(monkeypatch, 0.27)
    html = """
    <html>
      <head>
        <title>Лазерная эпиляция лица и тела</title>
        <meta name="description" content="Описание процедур лазерной эпиляции, подготовка и противопоказания." />
      </head>
      <body>
        <h1>Лазерная эпиляция</h1>
        <p>Клиника выполняет лазерную эпиляцию ног, рук, лица и зоны бикини.
        На странице объясняется подготовка к процедуре, длительность курса,
        противопоказания, уход после сеанса и ожидаемый результат.</p>
      </body>
    </html>
    """

    features = build_features(html=html, text="", query="цена лазерной эпиляции")
    guardrail = build_query_relevance_guardrail(features, 82.0)

    assert features["keyword_coverage_ratio"] == 0.666667
    assert features["query_intent_modifier_coverage_ratio"] == 0.0
    assert features["query_core_keyword_coverage_ratio"] == 1.0
    assert has_strong_query_topic_fit(features) is True
    assert guardrail["active"] is False


def test_unrelated_good_page_keeps_quality_difference_inside_low_relevance_band(monkeypatch):
    _patch_semantic_similarity(monkeypatch, 0.18)
    html = """
    <html>
      <head>
        <title>Курсы английского языка для взрослых</title>
        <meta name="description" content="Групповые и индивидуальные занятия английским языком." />
      </head>
      <body>
        <h1>Курсы английского языка</h1>
        <p>Подготовка к собеседованию, разговорная практика, тестирование уровня,
        расписание групп, преподаватели и онлайн-занятия для взрослых.</p>
      </body>
    </html>
    """

    features = build_features(html=html, text="", query="купить беговую дорожку")
    weak_page = build_query_relevance_guardrail(features, 40.0)
    strong_page = build_query_relevance_guardrail(features, 90.0)

    assert weak_page["reason"] == "probable_query_topic_mismatch"
    assert strong_page["reason"] == "probable_query_topic_mismatch"
    assert weak_page["early_stop"] is False
    assert strong_page["early_stop"] is False
    assert weak_page["adjusted_score"] == 10.0
    assert strong_page["adjusted_score"] == 22.5
    assert weak_page["adjusted_score"] < strong_page["adjusted_score"] <= 25.0


def test_confident_full_mismatch_is_early_stop_candidate():
    features = {
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "word_count": 1200,
        "text_length_chars": 7200,
        "semantic_similarity": 0.08,
        "keyword_coverage_ratio": 0.0,
        "query_core_keyword_coverage_ratio": 0.0,
        "query_density": 0.0,
        "query_core_term_count": 0,
        "exact_query_count": 0,
        "query_in_title": 0,
        "query_in_text": 0,
        "title_semantic_alignment": 0.0,
        "heading_semantic_alignment": 0.0,
        "query_prominence_score": 0.0,
    }

    decision = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, 90.0)

    assert decision["should_stop"] is True
    assert decision["decision"] == "stop"
    assert decision["confidence"] == "high"
    assert decision["score_ceiling"] == 5.0
    assert guardrail["reason"] == "confident_full_query_mismatch"
    assert guardrail["band"] == "full_mismatch"
    assert guardrail["query_relevance_multiplier"] == 0.05
    assert guardrail["adjusted_score"] == 4.5
    assert guardrail["early_stop"] is True


def test_low_relevance_with_structural_signal_does_not_early_stop():
    features = {
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "word_count": 1200,
        "text_length_chars": 7200,
        "semantic_similarity": 0.1,
        "keyword_coverage_ratio": 0.0,
        "query_core_keyword_coverage_ratio": 0.0,
        "query_density": 0.0,
        "query_core_term_count": 0,
        "exact_query_count": 0,
        "query_in_title": 1,
        "query_in_text": 0,
        "title_semantic_alignment": 0.0,
        "heading_semantic_alignment": 0.0,
        "query_prominence_score": 0.0,
    }

    decision = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, 90.0)

    assert decision["should_stop"] is False
    assert guardrail["early_stop"] is False


def test_unusable_page_is_kept_in_zero_to_ten_band():
    features = {
        "http_status_code": 404,
        "http_status_ok": 0,
        "page_indexable": 0,
        "robots_noindex": 1,
        "word_count": 0,
        "text_length_chars": 0,
        "semantic_similarity": 0.0,
        "keyword_coverage_ratio": 0.0,
        "query_core_keyword_coverage_ratio": 0.0,
        "query_density": 0.0,
    }

    guardrail = build_query_relevance_guardrail(features, 80.0)

    assert guardrail["reason"] == "page_unusable"
    assert guardrail["band"] == "unusable"
    assert guardrail["band_min"] == 0.0
    assert guardrail["band_max"] == 10.0
    assert guardrail["adjusted_score"] == 8.0
    assert "http_status_not_ok" in guardrail["unusable_reasons"]


def test_d74_wine_store_for_buy_gantry_crane_is_confident_full_mismatch():
    features = {
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "word_count": 950,
        "text_length_chars": 6100,
        "semantic_similarity": 0.06,
        "keyword_coverage_ratio": 0.0,
        "query_core_keyword_coverage_ratio": 0.0,
        "query_intent_modifier_coverage_ratio": 1.0,
        "query_density": 0.0,
        "query_core_term_count": 0,
        "exact_query_count": 0,
        "query_in_title": 0,
        "query_in_text": 0,
        "title_semantic_alignment": 0.0,
        "heading_semantic_alignment": 0.0,
        "query_prominence_score": 0.0,
    }

    decision = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, 92.0)

    assert decision["should_stop"] is True
    assert decision["reason"] == "confident_full_query_mismatch"
    assert decision["score_ceiling"] == 5.0
    assert guardrail["early_stop"] is True
    assert guardrail["band"] == "full_mismatch"
    assert 0.0 <= guardrail["adjusted_score"] <= 5.0


def test_d74_relevant_gantry_crane_page_without_buy_word_does_not_early_stop():
    features = {
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "word_count": 860,
        "text_length_chars": 5200,
        "semantic_similarity": 0.31,
        "keyword_coverage_ratio": 0.666667,
        "query_core_keyword_coverage_ratio": 1.0,
        "query_intent_modifier_coverage_ratio": 0.0,
        "query_density": 0.006,
        "query_core_term_count": 8,
        "exact_query_count": 0,
        "query_in_title": 0,
        "query_in_text": 1,
        "title_semantic_alignment": 0.7,
        "heading_semantic_alignment": 0.8,
        "query_prominence_score": 0.62,
    }

    decision = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, 81.0)

    assert decision["should_stop"] is False
    assert has_strong_query_topic_fit(features) is True
    assert guardrail["early_stop"] is False
    assert guardrail["active"] is False
    assert guardrail["adjusted_score"] == 81.0


def test_d74_similar_but_wrong_crane_equipment_is_capped_without_early_stop():
    features = {
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "word_count": 780,
        "text_length_chars": 4700,
        "semantic_similarity": 0.3,
        "keyword_coverage_ratio": 0.333333,
        "query_core_keyword_coverage_ratio": 0.25,
        "query_intent_modifier_coverage_ratio": 0.0,
        "query_density": 0.001,
        "query_core_term_count": 1,
        "exact_query_count": 0,
        "query_in_title": 0,
        "query_in_text": 1,
        "title_semantic_alignment": 0.0,
        "heading_semantic_alignment": 0.0,
        "query_prominence_score": 0.12,
    }

    decision = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, 84.0)

    assert decision["should_stop"] is False
    assert guardrail["early_stop"] is False
    assert guardrail["band"] in {"probable_mismatch", "weak_match"}
    assert guardrail["adjusted_score"] < 84.0
    assert guardrail["band_max"] <= 55.0


def test_d74_informational_query_does_not_require_commercial_modifiers():
    features = {
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "word_count": 720,
        "text_length_chars": 4300,
        "semantic_similarity": 0.28,
        "keyword_coverage_ratio": 1.0,
        "query_core_keyword_coverage_ratio": 1.0,
        "query_intent_modifier_coverage_ratio": 0.0,
        "query_density": 0.007,
        "query_core_term_count": 7,
        "exact_query_count": 1,
        "query_in_title": 1,
        "query_in_text": 1,
        "title_semantic_alignment": 0.72,
        "heading_semantic_alignment": 0.7,
        "query_prominence_score": 0.68,
    }

    guardrail = build_query_relevance_guardrail(features, 76.0)

    assert has_strong_query_topic_fit(features) is True
    assert guardrail["early_stop"] is False
    assert guardrail["active"] is False
    assert guardrail["adjusted_score"] == 76.0


def test_d74_rare_technical_synonym_or_translit_signal_does_not_early_stop():
    features = {
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "word_count": 640,
        "text_length_chars": 3900,
        "semantic_similarity": 0.24,
        "keyword_coverage_ratio": 0.0,
        "query_core_keyword_coverage_ratio": 0.0,
        "query_intent_modifier_coverage_ratio": 0.0,
        "query_density": 0.0,
        "query_core_term_count": 0,
        "exact_query_count": 0,
        "query_in_title": 0,
        "query_in_text": 0,
        "title_semantic_alignment": 0.0,
        "heading_semantic_alignment": 0.0,
        "query_prominence_score": 0.0,
    }

    decision = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, 79.0)

    assert decision["should_stop"] is False
    assert decision["reason"] == "not_confident_enough_for_early_stop"
    assert guardrail["early_stop"] is False
    assert guardrail["band"] in {"probable_mismatch", "weak_match"}
    assert guardrail["adjusted_score"] < 79.0


def test_d74_insufficient_extracted_text_is_not_safe_for_early_stop():
    features = {
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "word_count": 35,
        "text_length_chars": 260,
        "semantic_similarity": 0.02,
        "keyword_coverage_ratio": 0.0,
        "query_core_keyword_coverage_ratio": 0.0,
        "query_intent_modifier_coverage_ratio": 0.0,
        "query_density": 0.0,
        "query_core_term_count": 0,
        "exact_query_count": 0,
        "query_in_title": 0,
        "query_in_text": 0,
        "title_semantic_alignment": 0.0,
        "heading_semantic_alignment": 0.0,
        "query_prominence_score": 0.0,
    }

    decision = build_query_relevance_preflight_decision(features)
    guardrail = build_query_relevance_guardrail(features, 70.0)

    assert decision["content_evaluable"] is False
    assert decision["should_stop"] is False
    assert decision["confidence"] == "insufficient_content"
    assert guardrail["early_stop"] is False
