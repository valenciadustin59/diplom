from __future__ import annotations

from dataclasses import dataclass
from zlib import crc32


MINILM_PROVIDER = "minilm"
ROSBERTA_PROVIDER = "rosberta"

DEFAULT_MINILM_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_ROSBERTA_MODEL = "ai-forever/ru-en-RoSBERTa"

SEMANTIC_PROVIDER_CODES = {
    MINILM_PROVIDER: 1,
    ROSBERTA_PROVIDER: 2,
}
SEMANTIC_PROVIDER_NAMES_BY_CODE = {code: name for name, code in SEMANTIC_PROVIDER_CODES.items()}
KNOWN_MODEL_CODES = {
    DEFAULT_MINILM_MODEL: 1,
    DEFAULT_ROSBERTA_MODEL: 2,
}


@dataclass(frozen=True)
class SemanticRuntimeConfig:
    provider: str
    model_name: str
    fallback_provider: str
    fallback_model_name: str
    max_text_chars: int
    max_query_chars: int
    batch_size: int

    @property
    def cache_key(self) -> tuple[str, str, str, str, int, int, int]:
        return (
            self.provider,
            self.model_name,
            self.fallback_provider,
            self.fallback_model_name,
            self.max_text_chars,
            self.max_query_chars,
            self.batch_size,
        )


def normalize_provider_name(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("_", "-")
    aliases = {
        "mini-lm": MINILM_PROVIDER,
        "multilingual-minilm": MINILM_PROVIDER,
        "paraphrase-multilingual-minilm": MINILM_PROVIDER,
        "ru-en-rosberta": ROSBERTA_PROVIDER,
        "roberta": ROSBERTA_PROVIDER,
        "ruenrosberta": ROSBERTA_PROVIDER,
    }
    return aliases.get(normalized, normalized or ROSBERTA_PROVIDER)


def default_model_for_provider(provider: str) -> str:
    if provider == MINILM_PROVIDER:
        return DEFAULT_MINILM_MODEL
    if provider == ROSBERTA_PROVIDER:
        return DEFAULT_ROSBERTA_MODEL
    return DEFAULT_ROSBERTA_MODEL


def semantic_provider_code(provider: str | None) -> int:
    return SEMANTIC_PROVIDER_CODES.get(normalize_provider_name(provider), 0)


def semantic_provider_name_from_code(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return SEMANTIC_PROVIDER_NAMES_BY_CODE.get(int(value))
    return None


def semantic_model_code(model_name: str | None) -> int:
    if not model_name:
        return 0
    if model_name in KNOWN_MODEL_CODES:
        return KNOWN_MODEL_CODES[model_name]
    return 1000 + (crc32(model_name.encode("utf-8")) % 900000)


def semantic_model_name_from_code(value: object) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    code = int(value)
    for model_name, model_code in KNOWN_MODEL_CODES.items():
        if model_code == code:
            return model_name
    return None


def resolve_semantic_runtime_config(settings: object) -> SemanticRuntimeConfig:
    provider = normalize_provider_name(str(getattr(settings, "semantic_provider", "") or ROSBERTA_PROVIDER))
    fallback_provider = normalize_provider_name(
        str(getattr(settings, "semantic_fallback_provider", "") or MINILM_PROVIDER)
    )
    model_name = str(getattr(settings, "semantic_model_name", "") or default_model_for_provider(provider))
    fallback_model_name = str(
        getattr(settings, "semantic_fallback_model_name", "") or default_model_for_provider(fallback_provider)
    )
    max_text_chars = max(256, int(getattr(settings, "semantic_max_text_chars", 3000) or 3000))
    max_query_chars = max(64, int(getattr(settings, "semantic_max_query_chars", 300) or 300))
    batch_size = max(1, int(getattr(settings, "semantic_batch_size", 16) or 16))
    return SemanticRuntimeConfig(
        provider=provider,
        model_name=model_name,
        fallback_provider=fallback_provider,
        fallback_model_name=fallback_model_name,
        max_text_chars=max_text_chars,
        max_query_chars=max_query_chars,
        batch_size=batch_size,
    )


def calibrate_similarity(provider: str | None, similarity: float) -> float:
    bounded = max(-1.0, min(1.0, float(similarity)))
    normalized = max(0.0, min(1.0, (bounded + 1.0) / 2.0 if bounded < 0.0 else bounded))
    if normalize_provider_name(provider) != ROSBERTA_PROVIDER:
        return normalized

    if normalized <= 0.18:
        return normalized
    if normalized <= 0.34:
        return min(1.0, 0.18 + (normalized - 0.18) * 1.45)
    return min(1.0, 0.412 + (normalized - 0.34) * 0.85)


def build_semantic_numeric_metadata(
    *,
    provider: str,
    model_name: str,
    fallback_used: bool,
    failure: bool = False,
) -> dict[str, float | int]:
    return {
        "semantic_provider_code": semantic_provider_code(provider),
        "semantic_model_code": semantic_model_code(model_name),
        "semantic_fallback_used": int(fallback_used),
        "semantic_embedding_failure": int(failure),
    }


def semantic_layer_metadata_from_features(features: dict[str, object] | object) -> dict[str, object]:
    if not isinstance(features, dict):
        return {}
    provider = semantic_provider_name_from_code(features.get("semantic_provider_code"))
    model_name = semantic_model_name_from_code(features.get("semantic_model_code"))
    fallback_used = bool(features.get("semantic_fallback_used")) if "semantic_fallback_used" in features else False
    failure = bool(features.get("semantic_embedding_failure")) if "semantic_embedding_failure" in features else False
    metadata: dict[str, object] = {
        "provider": provider or "unknown",
        "model_name": model_name or "unknown",
        "provider_code": features.get("semantic_provider_code"),
        "model_code": features.get("semantic_model_code"),
        "fallback_used": fallback_used,
        "embedding_failure": failure,
    }
    if fallback_used and provider == MINILM_PROVIDER:
        metadata["fallback_provider"] = MINILM_PROVIDER
        metadata["fallback_model_name"] = DEFAULT_MINILM_MODEL
    return metadata
