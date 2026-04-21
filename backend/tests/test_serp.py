from types import SimpleNamespace

import pytest

from app.serp import SerpConfigurationError, search


def test_serp_search_requires_searxng_base_url(monkeypatch):
    monkeypatch.setattr(
        "app.serp.get_settings",
        lambda: SimpleNamespace(
            serp_provider="searxng",
            searxng_base_url=None,
            searxng_language="ru-RU",
            search_timeout=20.0,
        ),
    )

    with pytest.raises(SerpConfigurationError):
        search(query="ремонт квартир москва", top_n=10)


def test_serp_search_normalizes_searxng_results(monkeypatch):
    monkeypatch.setattr(
        "app.serp.get_settings",
        lambda: SimpleNamespace(
            serp_provider="searxng",
            searxng_base_url="https://searx.example",
            searxng_language="ru-RU",
            search_timeout=20.0,
        ),
    )
    monkeypatch.setattr(
        "app.serp._fetch_searxng_payload",
        lambda base_url, params: {
            "results": [
                {
                    "title": "Ремонт квартир",
                    "url": "https://example.com/remont",
                    "content": "Описание",
                },
                {
                    "title": "YouTube",
                    "url": "https://youtube.com/watch?v=1",
                    "content": "Видео",
                },
                {
                    "title": "Повтор",
                    "url": "https://example.com/remont",
                    "content": "Дубликат",
                },
                {
                    "title": "Окна",
                    "url": "https://example.org/okna",
                    "content": "Описание 2",
                },
            ]
        },
    )

    results = search(query="ремонт квартир москва", top_n=10)

    assert results == [
        {
            "url": "https://example.com/remont",
            "title": "Ремонт квартир",
            "snippet": "Описание",
            "rank": 1,
            "serp_page": 0,
        },
        {
            "url": "https://example.org/okna",
            "title": "Окна",
            "snippet": "Описание 2",
            "rank": 2,
            "serp_page": 0,
        },
    ]
