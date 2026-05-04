from __future__ import annotations

import csv
import json
from pathlib import Path

from app.ml.final_query_competitiveness import (
    FINAL_LABEL_SCHEMA_VERSION,
    apply_final_labels,
    final_target_score,
    validate_final_dataset,
)
from app.ml.model_schema import get_model_feature_schema


def _feature_row(**overrides: float | int | str) -> dict[str, object]:
    row: dict[str, object] = {feature: 0.0 for feature in get_model_feature_schema("v3").feature_columns}
    row.update(
        {
            "dataset_version": "dataset-v7-final",
            "query": "аренда учебного класса",
            "category": "classroom_rental",
            "city": "Казань",
            "domain": "example.org",
            "rank": 3,
            "fetch_status": "ok",
            "http_status_code": 200,
            "http_status_ok": 1,
            "page_indexable": 1,
            "robots_noindex": 0,
            "word_count": 900,
            "text_length_chars": 6200,
            "semantic_similarity": 0.72,
            "keyword_coverage_ratio": 1.0,
            "query_core_keyword_coverage_ratio": 1.0,
            "query_density": 0.012,
            "query_core_term_count": 12,
            "query_in_title": 1,
            "query_in_text": 1,
            "exact_query_count": 1,
            "query_prominence_score": 0.9,
            "semantic_content_richness": 0.72,
            "content_depth_semantic_score": 0.68,
            "keyword_balance_score": 0.8,
            "commercial_trust_score": 0.7,
            "trust_signals_score": 0.75,
            "commercial_signals_score": 0.65,
            "technical_seo_score": 0.85,
            "canonical_signal_score": 0.9,
            "url_hygiene_score": 0.8,
            "technical_metadata_score": 0.85,
            "intent_alignment_score": 0.78,
            "commercial_intent_alignment": 0.7,
            "informational_intent_alignment": 0.4,
        }
    )
    row.update(overrides)
    return row


def test_final_target_uses_relevance_multiplier_for_unrelated_page() -> None:
    row = _feature_row(
        semantic_similarity=0.1,
        keyword_coverage_ratio=0.0,
        query_core_keyword_coverage_ratio=0.0,
        query_density=0.0,
        query_core_term_count=0,
        query_in_title=0,
        query_in_text=0,
        exact_query_count=0,
        query_prominence_score=0.0,
    )

    label = final_target_score(row)

    assert label["query_relevance_multiplier"] == 0.15
    assert label["query_relevance_band"] == "mismatch"
    assert 0.0 <= label["target_score"] <= 15.0


def test_final_target_keeps_strong_relevance_without_buy_or_price_terms() -> None:
    label = final_target_score(_feature_row(query="пересадка орхидеи после цветения"))

    assert label["query_relevance_multiplier"] == 1.0
    assert label["query_relevance_band"] == "strong_match"
    assert label["target_score"] == label["competitiveness_base_score"]


def test_apply_final_labels_writes_expert_rubric_columns(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    output_path = tmp_path / "dataset.labeled.csv"
    rows = [_feature_row(domain="a.example"), _feature_row(domain="b.example", query_core_keyword_coverage_ratio=0.0)]
    fieldnames = list(rows[0].keys())
    with dataset_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    report = apply_final_labels(dataset_path=dataset_path, output_path=output_path)
    with output_path.open(encoding="utf-8", newline="") as file:
        labeled_rows = list(csv.DictReader(file))

    assert report["rows_count"] == 2
    assert labeled_rows[0]["label_schema_version"] == FINAL_LABEL_SCHEMA_VERSION
    assert labeled_rows[0]["label_source"] == "deterministic_expert_rubric_v7"
    assert labeled_rows[0]["query_relevance_multiplier"] == "1.0"


def test_validate_dataset_v7_blocks_seed_only_manifest() -> None:
    validation = validate_final_dataset()

    assert validation["passed"] is False
    assert "manifest_ready_for_training" in validation["failed_checks"]
    assert validation["queries_count"] == 0
