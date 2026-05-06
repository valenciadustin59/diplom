from __future__ import annotations

from math import sqrt
from types import SimpleNamespace

from app.semantic import build_semantic_features
from app.semantic_providers import (
    DEFAULT_MINILM_MODEL,
    DEFAULT_ROSBERTA_MODEL,
    MINILM_PROVIDER,
    ROSBERTA_PROVIDER,
    semantic_model_code,
    semantic_provider_code,
)


def _settings(**overrides):
    values = {
        "semantic_provider": ROSBERTA_PROVIDER,
        "semantic_model_name": DEFAULT_ROSBERTA_MODEL,
        "semantic_fallback_provider": MINILM_PROVIDER,
        "semantic_fallback_model_name": DEFAULT_MINILM_MODEL,
        "semantic_max_text_chars": 3000,
        "semantic_max_query_chars": 300,
        "semantic_batch_size": 7,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _vectors_for_similarity(similarity: float) -> list[list[float]]:
    return [[1.0, 0.0], [similarity, sqrt(1.0 - similarity * similarity)]]


class FakeProvider:
    def __init__(self, *, similarity: float, fail: bool = False):
        self.similarity = similarity
        self.fail = fail

    def encode(self, texts):
        if self.fail:
            raise RuntimeError("provider unavailable")
        assert len(texts) == 2
        return _vectors_for_similarity(self.similarity)


def test_rosberta_provider_is_selected_and_similarity_is_calibrated(monkeypatch):
    calls = []

    def fake_provider(provider: str, model_name: str, batch_size: int):
        calls.append((provider, model_name, batch_size))
        assert provider == ROSBERTA_PROVIDER
        assert model_name == DEFAULT_ROSBERTA_MODEL
        assert batch_size == 7
        return FakeProvider(similarity=0.30)

    monkeypatch.setattr("app.semantic.get_settings", lambda: _settings())
    monkeypatch.setattr("app.semantic.get_semantic_provider", fake_provider)

    features = build_semantic_features(text="page text", query="query text")

    assert calls == [(ROSBERTA_PROVIDER, DEFAULT_ROSBERTA_MODEL, 7)]
    assert features["semantic_similarity_raw"] == 0.3
    assert 0.35 <= float(features["semantic_similarity"]) <= 0.36
    assert features["semantic_provider_code"] == semantic_provider_code(ROSBERTA_PROVIDER)
    assert features["semantic_model_code"] == semantic_model_code(DEFAULT_ROSBERTA_MODEL)
    assert features["semantic_fallback_used"] == 0
    assert features["semantic_embedding_failure"] == 0


def test_rosberta_provider_falls_back_to_minilm(monkeypatch):
    calls = []

    def fake_provider(provider: str, model_name: str, batch_size: int):
        calls.append((provider, model_name, batch_size))
        if provider == ROSBERTA_PROVIDER:
            return FakeProvider(similarity=0.0, fail=True)
        return FakeProvider(similarity=0.64)

    monkeypatch.setattr("app.semantic.get_settings", lambda: _settings())
    monkeypatch.setattr("app.semantic.get_semantic_provider", fake_provider)

    features = build_semantic_features(text="page text", query="query text")

    assert calls == [
        (ROSBERTA_PROVIDER, DEFAULT_ROSBERTA_MODEL, 7),
        (MINILM_PROVIDER, DEFAULT_MINILM_MODEL, 7),
    ]
    assert features["semantic_similarity_raw"] == 0.64
    assert features["semantic_similarity"] == 0.64
    assert features["semantic_provider_code"] == semantic_provider_code(MINILM_PROVIDER)
    assert features["semantic_model_code"] == semantic_model_code(DEFAULT_MINILM_MODEL)
    assert features["semantic_fallback_used"] == 1
    assert features["semantic_embedding_failure"] == 0
