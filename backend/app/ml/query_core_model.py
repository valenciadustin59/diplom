from __future__ import annotations

from typing import Any, Sequence


class QueryCoreGuardrailRegressor:
    """Wraps a regressor and caps raw score when the page misses the query core."""

    def __init__(
        self,
        base_model: Any,
        feature_columns: Sequence[str],
        *,
        cap: float,
        core_coverage_threshold: float,
        semantic_similarity_threshold: float,
    ) -> None:
        self.base_model = base_model
        self.feature_columns = tuple(str(feature) for feature in feature_columns)
        self.cap = float(cap)
        self.core_coverage_threshold = float(core_coverage_threshold)
        self.semantic_similarity_threshold = float(semantic_similarity_threshold)
        self._index = {feature: index for index, feature in enumerate(self.feature_columns)}

    def predict(self, matrix: Sequence[Sequence[float]]) -> list[float]:
        base_predictions = [float(value) for value in self.base_model.predict(matrix)]
        adjusted: list[float] = []
        for vector, prediction in zip(matrix, base_predictions, strict=False):
            adjusted.append(min(prediction, self.cap) if self._should_cap(vector) else prediction)
        return adjusted

    def _value(self, vector: Sequence[float], feature: str) -> float:
        index = self._index.get(feature)
        if index is None or index >= len(vector):
            return 0.0
        try:
            return float(vector[index] or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _should_cap(self, vector: Sequence[float]) -> bool:
        lexical_presence = max(
            self._value(vector, "exact_query_count"),
            self._value(vector, "query_in_text"),
            self._value(vector, "query_in_title"),
        )
        if lexical_presence > 0.0:
            return False
        core_coverage = self._value(vector, "query_core_keyword_coverage_ratio")
        core_phrase_count = self._value(vector, "query_core_phrase_count")
        semantic_similarity = self._value(vector, "semantic_similarity")
        word_count = self._value(vector, "word_count")
        if (
            core_phrase_count <= 1.0
            and word_count >= 8000.0
            and semantic_similarity < self.semantic_similarity_threshold
        ):
            return True
        return (
            core_coverage <= self.core_coverage_threshold
            and semantic_similarity < self.semantic_similarity_threshold
        )
