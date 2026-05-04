from __future__ import annotations

import csv
import json
from pathlib import Path

from app.ml.final_query_competitiveness import (
    D79_REPORT_JSON_PATH,
    D80_REPORT_JSON_PATH,
    D81_REPORT_JSON_PATH,
    FINAL_MODEL_PATH,
    FINAL_LABEL_SCHEMA_VERSION,
    HARD_NEGATIVE_SCORE_CAP,
    apply_final_labels,
    final_target_score,
    materialize_final_split,
    validate_final_dataset,
)
from app.ml.model import DEFAULT_MODEL_PATH, load_model_artifact, load_saved_model
from app.ml.model_schema import get_model_feature_schema
from app.ml.no_publish_decision import sha1_file


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

    assert label["query_relevance_multiplier"] == 0.05
    assert label["query_relevance_band"] == "full_mismatch"
    assert 0.0 <= label["target_score"] <= 5.0


def test_final_target_keeps_strong_relevance_without_buy_or_price_terms() -> None:
    label = final_target_score(_feature_row(query="пересадка орхидеи после цветения"))

    assert label["query_relevance_multiplier"] == 1.0
    assert label["query_relevance_band"] == "strong_match"
    assert label["target_score"] == label["competitiveness_base_score"]


def test_final_target_caps_cross_category_hard_negative() -> None:
    label = final_target_score(
        _feature_row(
            hard_negative=1,
            hard_negative_source_category="wine_store",
            hard_negative_source_query="buy wine online",
        )
    )

    assert label["target_score"] == HARD_NEGATIVE_SCORE_CAP
    assert label["query_relevance_band"] == "hard_negative_cap"
    assert label["query_relevance_reason"] == "cross_category_hard_negative_cap"
    assert label["hard_negative_cap_applied"] == 1


def test_apply_final_labels_writes_expert_rubric_columns(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    output_path = tmp_path / "dataset.labeled.csv"
    report_path = tmp_path / "d77-label-report.json"
    markdown_report_path = tmp_path / "d77-label-report.md"
    rows = [_feature_row(domain="a.example"), _feature_row(domain="b.example", query_core_keyword_coverage_ratio=0.0)]
    fieldnames = sorted({key for row in rows for key in row})
    with dataset_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    report = apply_final_labels(
        dataset_path=dataset_path,
        output_path=output_path,
        report_path=report_path,
        markdown_report_path=markdown_report_path,
    )
    with output_path.open(encoding="utf-8", newline="") as file:
        labeled_rows = list(csv.DictReader(file))

    assert report["rows_count"] == 2
    assert report["hard_negative_above_cap_count"] == 0
    assert report_path.exists()
    assert markdown_report_path.exists()
    assert labeled_rows[0]["label_schema_version"] == FINAL_LABEL_SCHEMA_VERSION
    assert labeled_rows[0]["label_source"] == "deterministic_expert_rubric_v7"
    assert labeled_rows[0]["query_relevance_multiplier"] == "1.0"


def test_materialize_final_split_writes_leakage_safe_manifest(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    labeled_path = tmp_path / "dataset.labeled.csv"
    split_path = tmp_path / "split.json"
    validation_path = tmp_path / "d78-split-validation-report.json"
    markdown_path = tmp_path / "d78-split-validation-report.md"
    manifest_path = tmp_path / "manifest.json"
    rows = []
    for query, category in [
        ("q-a-1", "category-a"),
        ("q-a-2", "category-a"),
        ("q-b-1", "category-b"),
        ("q-b-2", "category-b"),
    ]:
        rows.append(_feature_row(query=query, category=category, domain=f"{query}.example"))
        rows.append(
            _feature_row(
                query=query,
                category=category,
                domain=f"negative-{query}.example",
                hard_negative=1,
                hard_negative_source_category="other-category",
            )
        )
    fieldnames = sorted({key for row in rows for key in row})
    with dataset_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    manifest_path.write_text(
        json.dumps({"dataset_version": "dataset-v7-final", "ready_for_training": False}, ensure_ascii=False),
        encoding="utf-8",
    )
    apply_final_labels(dataset_path=dataset_path, output_path=labeled_path, report_path=None, markdown_report_path=None)

    report = materialize_final_split(
        labeled_dataset_path=labeled_path,
        output_split_path=split_path,
        output_validation_path=validation_path,
        output_markdown_path=markdown_path,
        manifest_path=manifest_path,
        test_size=0.5,
        random_state=42,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert report["validation"]["passed"] is True
    assert report["validation"]["query_overlap_count"] == 0
    assert report["validation"]["train_partition"]["categories_count"] == 2
    assert report["validation"]["validation_partition"]["categories_count"] == 2
    assert report["validation"]["hard_negative_above_cap_count"] == 0
    assert split_path.exists()
    assert validation_path.exists()
    assert markdown_path.exists()
    assert manifest["ready_for_training"] is True
    assert manifest["quality_gates"]["ready_for_training"] is True


def test_validate_dataset_v7_is_ready_after_d78_split_validation() -> None:
    validation = validate_final_dataset()

    assert validation["passed"] is True
    assert "manifest_ready_for_training" not in validation["failed_checks"]
    assert "hard_negatives_materialized" not in validation["failed_checks"]
    assert "hard_negatives_present" not in validation["failed_checks"]
    assert "min_queries" not in validation["failed_checks"]
    assert validation["queries_count"] >= 500
    assert validation["hard_negative_rows_count"] >= 1000
    assert validation["rows_count"] >= validation["queries_count"]


def test_d79_candidate_artifact_is_non_production_and_loadable() -> None:
    report = json.loads(D79_REPORT_JSON_PATH.read_text(encoding="utf-8"))
    artifact = load_model_artifact(FINAL_MODEL_PATH)
    raw_payload = load_saved_model(FINAL_MODEL_PATH)

    assert artifact is not None
    assert isinstance(raw_payload, dict)
    assert report["task"] == "D79"
    assert report["candidate_sha1"] == sha1_file(FINAL_MODEL_PATH)
    assert report["production_artifact_sha1"] == sha1_file(DEFAULT_MODEL_PATH)
    assert report["production_artifact_changed"] is False
    assert report["runtime_enabled"] is False
    assert artifact["dataset_version"] == "dataset-v7-final"
    assert raw_payload["candidate_name"] == "final_query_competitiveness_catboost_v7"
    assert raw_payload["non_production"] is True
    assert raw_payload["runtime_enabled"] is False
    assert artifact["model_schema_version"] == "v3"
    assert len(artifact["feature_columns"]) == 148


def test_d80_blocks_candidate_when_hard_negatives_exceed_cap() -> None:
    report = json.loads(D80_REPORT_JSON_PATH.read_text(encoding="utf-8"))
    guardrails = report["product_guardrails"]

    assert report["task"] == "D80"
    assert report["split"]["split_mode"] == "group_by_query_category_stratified"
    assert report["validation_rows_count"] == 978
    assert report["decision"]["decision"] == "no_publish"
    assert guardrails["passed"] is False
    assert guardrails["checks"]["hard_negatives_learned_below_cap"] is False
    assert "hard_negatives_learned_below_cap" in guardrails["failed_checks"]
    assert guardrails["hard_negative_above_cap_count"] > 0
    assert report["runtime_adjusted_metrics"]["mae"] < report["reference_runtime_adjusted_metrics"]["mae"]


def test_d81_records_no_publish_without_runtime_mutation() -> None:
    report = json.loads(D81_REPORT_JSON_PATH.read_text(encoding="utf-8"))

    assert report["task"] == "D81"
    assert report["decision"] == "no_publish"
    assert report["publish_action"] == "no_publish"
    assert report["production_changed"] is False
    assert report["production_sha1_before"] == report["production_sha1_after"]
    assert report["production_sha1_after"] == sha1_file(DEFAULT_MODEL_PATH)
    assert report["candidate_sha1"] == sha1_file(FINAL_MODEL_PATH)
