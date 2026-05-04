from app.features import build_features
from app.query_relevance import build_query_relevance_guardrail, has_strong_query_topic_fit


def _patch_semantic_similarity(monkeypatch, value: float) -> None:
    monkeypatch.setattr(
        "app.features.build_semantic_features",
        lambda text, query: {"semantic_similarity": value},
    )


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
    assert guardrail["reason"] == "severe_query_topic_mismatch"
    assert guardrail["band"] == "mismatch"
    assert guardrail["band_min"] == 0.0
    assert guardrail["band_max"] == 15.0
    assert guardrail["query_relevance_multiplier"] == 0.15
    assert guardrail["adjusted_score"] == 13.2


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

    assert weak_page["reason"] == "severe_query_topic_mismatch"
    assert strong_page["reason"] == "severe_query_topic_mismatch"
    assert weak_page["adjusted_score"] == 6.0
    assert strong_page["adjusted_score"] == 13.5
    assert weak_page["adjusted_score"] < strong_page["adjusted_score"] <= 15.0


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
