from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import sqrt
from typing import Sequence

from app.config import get_settings
from app.semantic_providers import (
    build_semantic_numeric_metadata,
    calibrate_similarity,
    resolve_semantic_runtime_config,
)

MODEL_NAME = "ai-forever/ru-en-RoSBERTa"
FALLBACK_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MAX_TEXT_CHARS = 3000
MAX_QUERY_CHARS = 300


@dataclass(frozen=True)
class SemanticEncodingResult:
    embeddings: tuple[tuple[float, ...], ...]
    provider: str
    model_name: str
    fallback_used: bool


class SentenceTransformerSemanticProvider:
    def __init__(self, *, provider: str, model_name: str, batch_size: int):
        self.provider = provider
        self.model_name = model_name
        self.batch_size = batch_size
        self._model = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        model = self._get_model()
        embeddings = model.encode(
            list(texts),
            batch_size=self.batch_size,
            normalize_embeddings=True,
        )
        return [_to_vector(embedding) for embedding in embeddings]


@lru_cache(maxsize=4)
def get_embedding_model(model_name: str = MODEL_NAME):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


@lru_cache(maxsize=8)
def get_semantic_provider(provider: str, model_name: str, batch_size: int) -> SentenceTransformerSemanticProvider:
    return SentenceTransformerSemanticProvider(provider=provider, model_name=model_name, batch_size=batch_size)


def _to_vector(raw_vector) -> list[float]:
    if hasattr(raw_vector, "tolist"):
        values = raw_vector.tolist()
        if isinstance(values, list):
            return [float(value) for value in values]
    return [float(value) for value in raw_vector]


def _encode_single(text: str) -> list[float]:
    model = get_embedding_model(MODEL_NAME)
    embedding = model.encode(
        text or "",
        normalize_embeddings=True,
    )
    return _to_vector(embedding)


def _encode_texts(texts: Sequence[str]) -> SemanticEncodingResult:
    config = resolve_semantic_runtime_config(get_settings())
    primary = get_semantic_provider(config.provider, config.model_name, config.batch_size)
    try:
        embeddings = primary.encode(texts)
        return SemanticEncodingResult(
            embeddings=tuple(tuple(vector) for vector in embeddings),
            provider=config.provider,
            model_name=config.model_name,
            fallback_used=False,
        )
    except Exception:
        fallback = get_semantic_provider(config.fallback_provider, config.fallback_model_name, config.batch_size)
        embeddings = fallback.encode(texts)
        return SemanticEncodingResult(
            embeddings=tuple(tuple(vector) for vector in embeddings),
            provider=config.fallback_provider,
            model_name=config.fallback_model_name,
            fallback_used=True,
        )


@lru_cache(maxsize=2048)
def get_query_embedding(query: str) -> tuple[float, ...]:
    config = resolve_semantic_runtime_config(get_settings())
    result = _encode_texts([query.strip()[: config.max_query_chars]])
    return result.embeddings[0] if result.embeddings else tuple()


def get_embeddings(text: str, query: str) -> tuple[list[float], list[float]]:
    config = resolve_semantic_runtime_config(get_settings())
    result = _encode_texts(
        [
            text.strip()[: config.max_text_chars],
            query.strip()[: config.max_query_chars],
        ]
    )
    page_embedding = list(result.embeddings[0]) if len(result.embeddings) >= 1 else []
    query_embedding = list(result.embeddings[1]) if len(result.embeddings) >= 2 else []
    return page_embedding, query_embedding


def clear_semantic_caches() -> None:
    for cached_function in (get_embedding_model, get_semantic_provider, get_query_embedding):
        cache_clear = getattr(cached_function, "cache_clear", None)
        if callable(cache_clear):
            cache_clear()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0

    dot_product = sum(a * b for a, b in zip(left, right))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))

    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0

    return dot_product / (left_norm * right_norm)


def build_semantic_features(text: str, query: str) -> dict[str, float | int]:
    config = resolve_semantic_runtime_config(get_settings())
    if not text.strip() or not query.strip():
        return {
            "semantic_similarity": 0.0,
            "semantic_similarity_raw": 0.0,
            **build_semantic_numeric_metadata(
                provider=config.provider,
                model_name=config.model_name,
                fallback_used=False,
                failure=False,
            ),
        }

    try:
        result = _encode_texts(
            [
                text.strip()[: config.max_text_chars],
                query.strip()[: config.max_query_chars],
            ]
        )
        page_embedding = list(result.embeddings[0]) if len(result.embeddings) >= 1 else []
        query_embedding = list(result.embeddings[1]) if len(result.embeddings) >= 2 else []
        raw_similarity = cosine_similarity(page_embedding, query_embedding)
        similarity = calibrate_similarity(result.provider, raw_similarity)
        provider = result.provider
        model_name = result.model_name
        fallback_used = result.fallback_used
        failure = False
    except Exception:
        raw_similarity = 0.0
        similarity = 0.0
        provider = config.provider
        model_name = config.model_name
        fallback_used = config.provider != config.fallback_provider
        failure = True

    return {
        "semantic_similarity": round(similarity, 6),
        "semantic_similarity_raw": round(raw_similarity, 6),
        **build_semantic_numeric_metadata(
            provider=provider,
            model_name=model_name,
            fallback_used=fallback_used,
            failure=failure,
        ),
    }
