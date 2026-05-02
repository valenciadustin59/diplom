from __future__ import annotations

import csv
import json
from pathlib import Path

from app.ml.seo_weighted_labels import (
    DEFAULT_LABEL_SOURCE,
    RUBRIC_WEIGHTS,
    build_row_label,
    generate_seo_weighted_labels,
    validate_label_split,
)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "query": "seo audit moscow",
        "url": "https://example.com/",
        "domain": "example.com",
        "rank": 1,
        "fetch_status": "ok",
        "weak_target_score": 92,
        "page_type": "category",
        "word_count": 900,
        "http_status_ok": 1,
        "page_indexable": 1,
        "robots_noindex": 0,
        "robots_nofollow": 0,
        "viewport_present": 1,
        "lang_present": 1,
        "canonical_present": 1,
        "canonical_matches_final_url": 1,
        "canonical_signal_score": 1,
        "title_present": 1,
        "query_in_title": 1,
        "title_keyword_coverage_ratio": 1,
        "title_semantic_alignment": 0.9,
        "title_length_quality": 0.9,
        "h1_count": 1,
        "heading_query_coverage_ratio": 0.8,
        "query_terms_in_headings": 3,
        "heading_semantic_alignment": 0.8,
        "title_heading_keyword_alignment": 0.8,
        "semantic_similarity": 0.7,
        "query_semantic_alignment": 0.85,
        "keyword_coverage_ratio": 0.9,
        "keyword_balance_score": 0.85,
        "query_prominence_score": 0.9,
        "intent_alignment_score": 0.9,
        "intent_is_commercial": 1,
        "intent_is_local_commercial": 1,
        "technical_metadata_score": 0.9,
        "url_hygiene_score": 0.9,
        "redirect_efficiency_score": 0.9,
        "meta_description_present": 1,
        "meta_length_quality": 0.9,
        "heading_paragraph_balance": 0.8,
        "content_link_ratio": 0.8,
        "content_depth_semantic_score": 0.85,
        "semantic_content_richness": 0.85,
        "contact_options_score": 0.9,
        "commercial_signals_score": 0.85,
        "trust_signals_score": 0.8,
        "commercial_trust_score": 0.86,
        "company_identity_present": 1,
        "legal_requisites_present": 1,
        "cta_present": 1,
        "cta_count": 2,
        "value_proposition_present": 1,
        "phone_present": 1,
        "email_present": 1,
        "address_present": 1,
        "structured_data_offer_schema_present": 1,
        "price_present": 0,
        "mobile_readiness_score": 0.95,
        "rendering_score": 0.9,
        "performance_proxy_score": 0.7,
        "performance_resource_complexity_score": 0.25,
        "heavy_analysis_overall_score": 0.85,
        "link_count": 40,
        "image_count": 8,
        "list_item_count": 20,
        "payment_info_present": 0,
        "delivery_info_present": 0,
        "warranty_info_present": 0,
        "returns_info_present": 0,
        "reviews_present": 1,
        "rating_present": 1,
        "messenger_present": 0,
        "faq_present": 1,
        "structured_data_score": 0.85,
        "structured_data_valid_json_ld_count": 2,
        "structured_data_breadcrumb_schema_present": 1,
        "structured_data_faq_schema_present": 1,
    }
    row.update(overrides)
    return row


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_critical_fetch_failure_caps_score_even_with_strong_supporting_signals() -> None:
    label = build_row_label(
        _row(
            http_status_ok=0,
            weak_target_score=100,
            word_count=3000,
            link_count=200,
            image_count=80,
            payment_info_present=1,
            delivery_info_present=1,
        )
    )

    assert label.expert_target_score <= 35.0
    assert label.cap_applied == 35.0
    assert "critical_http_status_not_ok" in label.cap_reasons
    assert label.label_source == DEFAULT_LABEL_SOURCE


def test_text_volume_is_only_a_small_supporting_signal() -> None:
    compact = build_row_label(_row(word_count=650))
    long = build_row_label(_row(word_count=3500))

    assert long.supporting_score > compact.supporting_score
    assert long.expert_target_score - compact.expert_target_score < 3.0
    assert RUBRIC_WEIGHTS["supporting"]["features"]["text_sufficiency"] == 0.25


def test_generate_seo_weighted_labels_writes_bundle_and_validates_split(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.csv"
    split_path = tmp_path / "split.json"
    labels_path = tmp_path / "dataset-v4" / "expert_labels.csv"
    report_json_path = tmp_path / "dataset-v4" / "d45-report.json"
    report_md_path = tmp_path / "dataset-v4" / "d45-report.md"
    split_validation_path = tmp_path / "dataset-v4" / "split-validation.json"
    artifact_path = tmp_path / "page_quality_model.pkl"
    artifact_path.write_bytes(b"production")

    rows = [
        _row(query="q1", url="https://a.example/", rank=1),
        _row(query="q1", url="https://b.example/", rank=2, semantic_similarity=0.35),
        _row(query="q2", url="https://c.example/", rank=1, page_indexable=0),
        _row(query="q2", url="https://d.example/", rank=2, word_count=300),
    ]
    _write_csv(dataset_path, rows)
    split_path.write_text(
        json.dumps(
            {
                "split_mode": "group_by_query",
                "train_queries": ["q1"],
                "validation_queries": ["q2"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report = generate_seo_weighted_labels(
        dataset_path=dataset_path,
        split_path=split_path,
        output_labels_path=labels_path,
        output_report_json_path=report_json_path,
        output_report_markdown_path=report_md_path,
        output_split_validation_path=split_validation_path,
        production_artifact_path=artifact_path,
    )

    assert labels_path.exists()
    assert report_json_path.exists()
    assert report_md_path.exists()
    assert split_validation_path.exists()
    assert report["labels_count"] == 4
    assert report["label_semantics"] == {
        "deterministic_expert_rubric": True,
        "human_labels": False,
        "description": "Labels are generated from a documented SEO-weighted rubric, not from manual human annotation.",
    }
    assert report["split_validation"]["passed"] is True
    assert report["rubric_weights"]["critical"]["total"] == 0.55
    label_rows = list(csv.DictReader(labels_path.open(encoding="utf-8", newline="")))
    assert {row["label_source"] for row in label_rows} == {DEFAULT_LABEL_SOURCE}


def test_validate_label_split_detects_query_leakage(tmp_path: Path) -> None:
    split_path = tmp_path / "split.json"
    split_path.write_text(
        json.dumps(
            {
                "split_mode": "group_by_query",
                "train_queries": ["q1", "q2"],
                "validation_queries": ["q2"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = validate_label_split([{"query": "q1"}, {"query": "q2"}], split_path)

    assert result["passed"] is False
    assert result["query_overlap"] == ["q2"]
