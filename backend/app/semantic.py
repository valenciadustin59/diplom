from __future__ import annotations

from functools import lru_cache
from math import sqrt


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MAX_TEXT_CHARS = 3000
MAX_QUERY_CHARS = 300


@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


def _to_vector(raw_vector) -> list[float]:
    if hasattr(raw_vector, "tolist"):
        values = raw_vector.tolist()
        if isinstance(values, list):
            return [float(value) for value in values]
    return [float(value) for value in raw_vector]


def _encode_single(text: str) -> list[float]:
    model = get_embedding_model()
    embedding = model.encode(
        text or "",
        normalize_embeddings=True,
    )
    return _to_vector(embedding)


@lru_cache(maxsize=2048)
def get_query_embedding(query: str) -> tuple[float, ...]:
    return tuple(_encode_single(query.strip()[:MAX_QUERY_CHARS]))


def get_embeddings(text: str, query: str) -> tuple[list[float], list[float]]:
    page_embedding = _encode_single(text.strip()[:MAX_TEXT_CHARS])
    query_embedding = list(get_query_embedding(query))
    return page_embedding, query_embedding


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
    if not text.strip() or not query.strip():
        return {
            "semantic_similarity": 0.0,
        }

    try:
        page_embedding, query_embedding = get_embeddings(text, query)
        similarity = cosine_similarity(page_embedding, query_embedding)
    except Exception:
        similarity = 0.0

    return {
        "semantic_similarity": round(similarity, 6),
    }
