import csv
from pathlib import Path
from app.ml import FEATURE_COLUMNS, explain_score, load_saved_model, predict_score, train_quality_model
from app.ml.dataset_builder import DATASET_COLUMNS
from app.ml.model import ARTIFACTS_DIR, DEFAULT_MODEL_PATH
from app.ml.model import calculate_rule_score, load_model_artifact, save_model, train_model
from app.features import INTENT_ALIGNMENT_FEATURE_COLUMNS, SERP_RELATIVE_FEATURE_COLUMNS, SNAPSHOT_AUXILIARY_FEATURE_COLUMNS
from app.heavy_analysis import HEAVY_ANALYSIS_FEATURE_COLUMNS
from app.ml.model_schema import get_model_feature_schema
EXPECTED_V2_FEATURE_COUNT = len(get_model_feature_schema("v2").feature_columns)
EXPECTED_V3_FEATURE_COUNT = len(get_model_feature_schema("v3").feature_columns)


class ConstantScoreModel:
    def __init__(self, score: float):
        self.score = score

    def predict(self, rows):
        return [self.score for _ in rows]


def test_default_runtime_model_path_is_production_alias():
    assert DEFAULT_MODEL_PATH == ARTIFACTS_DIR / "page_quality_model.pkl"
    assert DEFAULT_MODEL_PATH.name == "page_quality_model.pkl"
    assert "candidate" not in DEFAULT_MODEL_PATH.name


def _write_training_dataset(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
        for query_index, query in enumerate(("╤А╨╡╨╝╨╛╨╜╤В ╨║╨▓╨░╤А╤В╨╕╤А ╨╝╨╛╤Б╨║╨▓╨░", "╨┐╨╗╨░╤Б╤В╨╕╨║╨╛╨▓╤Л╨╡ ╨╛╨║╨╜╨░ ╨╝╨╛╤Б╨║╨▓╨░"), start=1):
            for rank in range(1, 4):
                row = {column: "" for column in DATASET_COLUMNS}
                row.update(
                    {
                        "dataset_version": "dataset-v2-test",
                        "feature_schema_version": "v2",
                        "extraction_artifact_version": "extraction-v2",
                        "label_schema_version": "hybrid-v1",
                        "label_source": "weak_serp",
                        "weak_target_score": round(((3 - rank) / 2) * 100.0, 4),
                        "expert_target_score": "",
                        "query": query,
                        "category": "services",
                        "intent": "commercial",
                        "city": "╨╝╨╛╤Б╨║╨▓╨░",
                        "region_code": 213,
                        "url": f"https://example{query_index}.com/page-{rank}",
                        "domain": f"example{query_index}.com",
                        "rank": rank,
                        "serp_page": 0,
                        "title": f"Title {rank}",
                        "snippet": f"Snippet {rank}",
                        "page_type": "content",
                        "fetch_status": "ok",
                        "fetch_error": "",
                        "target_score": round(((3 - rank) / 2) * 100.0, 4),
                        "phone_present": 1,
                        "address_present": 1,
                        "price_present": 1,
                        "commercial_signals_score": 0.8,
                        "trust_signals_score": 0.7,
                        "commercial_trust_score": 0.75,
                        "page_indexable": 1,
                        "technical_seo_score": 0.9,
                    }
                )
                for index, feature_name in enumerate(FEATURE_COLUMNS, start=1):
                    row[feature_name] = float(index * (query_index * 2 + rank))
                writer.writerow(row)
def test_train_quality_model_defaults_to_model_schema_v2(tmp_path):
    dataset_path = tmp_path / "dataset.csv"
    model_path = tmp_path / "model.pkl"
    _write_training_dataset(dataset_path)
    result = train_quality_model(dataset_path=dataset_path, model_path=model_path, test_size=0.34)
    artifact = load_saved_model(model_path)
    explanation = explain_score(
        {feature_name: float(index * 2) for index, feature_name in enumerate(FEATURE_COLUMNS, start=1)},
        model_path=model_path,
    )
    assert artifact is not None
    assert artifact["model_schema_version"] == "v2"
    assert len(artifact["feature_columns"]) == EXPECTED_V2_FEATURE_COUNT
    assert result["model_schema_version"] == "v2"
    assert result["feature_count"] == EXPECTED_V2_FEATURE_COUNT
    assert explanation["model_info"]["model_schema_version"] == "v2"
    assert explanation["model_info"]["feature_count"] == EXPECTED_V2_FEATURE_COUNT
def test_predict_score_accepts_legacy_v1_artifact(tmp_path):
    model_path = tmp_path / "legacy-model.pkl"
    features = {feature_name: float(index + 1) for index, feature_name in enumerate(FEATURE_COLUMNS)}
    save_model(
        model=train_model(n_samples=40, seed=7),
        metrics={"rmse": 10.0},
        model_path=model_path,
        metadata={
            "source": "local_dataset",
            "dataset_version": "legacy-v1",
        },
    )
    artifact = load_model_artifact(model_path)
    explanation = explain_score(features, model_path=model_path)
    score = predict_score(features, model_path=model_path)
    assert artifact is not None
    assert artifact["model_schema_version"] == "v1"
    assert explanation["model_info"]["model_schema_version"] == "v1"
    assert explanation["model_info"]["feature_count"] == len(FEATURE_COLUMNS)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0


def test_published_model_score_is_not_inflated_by_rule_layer(tmp_path):
    model_path = tmp_path / "published-model.pkl"
    features = {feature_name: 1.0 for feature_name in FEATURE_COLUMNS}
    features.update(
        {
            "word_count": 1800,
            "heading_count": 12,
            "title_present": 1,
            "title_length_quality": 1,
            "meta_description_present": 1,
            "meta_length_quality": 1,
            "semantic_similarity": 0.9,
            "keyword_coverage_ratio": 1,
            "title_semantic_alignment": 0.9,
            "heading_semantic_alignment": 0.9,
            "content_depth_semantic_score": 0.9,
            "semantic_content_richness": 0.9,
            "keyword_balance_score": 1,
            "conversion_signal_score": 1,
            "query_prominence_score": 1,
            "text_to_html_ratio": 0.25,
            "unique_word_ratio": 0.9,
        }
    )
    save_model(
        model=train_model(n_samples=40, seed=11),
        metrics={"rmse": 10.0},
        model_path=model_path,
        metadata={
            "source": "local_dataset",
            "dataset_version": "test-dataset",
        },
    )

    explanation = explain_score(features, model_path=model_path)

    assert explanation["weights"] == {"rule_weight": 0.0, "ml_weight": 1.0}
    assert explanation["final_score"] == explanation["ml_score"]
    assert 0.0 <= explanation["rule_score"] < 100.0
    assert any(
        factor.get("key") == "query_topic_fit" and float(factor.get("impact", 0.0)) > 0.0
        for factor in explanation["top_positive_factors"]
    )


def test_query_relevance_guardrail_caps_unrelated_commercial_page(tmp_path):
    model_path = tmp_path / "constant-v3-model.pkl"
    v3_columns = get_model_feature_schema("v3").feature_columns
    features = {feature_name: 0.0 for feature_name in v3_columns}
    features.update(
        {
            "word_count": 3600,
            "heading_count": 8,
            "title_present": 1,
            "title_length_quality": 0.9,
            "meta_description_present": 1,
            "meta_length_quality": 0.9,
            "semantic_similarity": 0.298144,
            "keyword_coverage_ratio": 0.333333,
            "query_density": 0.00028,
            "query_in_title": 0,
            "query_in_text": 0,
            "exact_query_count": 0,
            "title_semantic_alignment": 0,
            "heading_semantic_alignment": 0,
            "query_prominence_score": 0,
            "page_indexable": 1,
            "canonical_present": 1,
            "canonical_matches_final_url": 1,
            "commercial_signals_score": 0.888889,
            "trust_signals_score": 0.925926,
            "commercial_trust_score": 0.925926,
            "intent_alignment_score": 0.534753,
            "intent_is_commercial": 1,
            "commercial_intent_alignment": 0.534753,
        }
    )
    save_model(
        model=ConstantScoreModel(86.0),
        metrics={"mae": 1.0},
        model_path=model_path,
        metadata={
            "source": "local_dataset",
            "dataset_version": "guardrail-test",
            "model_schema_version": "v3",
            "feature_columns": v3_columns,
        },
    )

    explanation = explain_score(features, model_path=model_path)

    assert explanation["ml_score"] == 86.0
    assert explanation["uncapped_final_score"] == 86.0
    assert explanation["final_score"] == 12.9
    assert explanation["relevance_guardrail"]["active"] is True
    assert explanation["relevance_guardrail"]["reason"] == "severe_query_topic_mismatch"
    assert explanation["relevance_guardrail"]["band"] == "mismatch"
    assert explanation["relevance_guardrail"]["band_max"] == 15.0
    assert explanation["relevance_guardrail"]["query_relevance_multiplier"] == 0.15
    assert explanation["relevance_guardrail"]["cap"] == 12.9
    assert any(
        factor.get("key") == "query_relevance_guardrail" and float(factor.get("impact", 0.0)) < 0.0
        for factor in explanation["top_negative_factors"]
    )


def test_query_relevance_guardrail_keeps_strong_lexical_match(tmp_path):
    model_path = tmp_path / "constant-v3-relevant-model.pkl"
    v3_columns = get_model_feature_schema("v3").feature_columns
    features = {feature_name: 0.0 for feature_name in v3_columns}
    features.update(
        {
            "word_count": 836,
            "heading_count": 7,
            "title_present": 1,
            "title_length_quality": 0.8,
            "meta_description_present": 1,
            "meta_length_quality": 0.8,
            "semantic_similarity": 0.196525,
            "keyword_coverage_ratio": 1.0,
            "query_density": 0.04067,
            "query_in_title": 0,
            "query_in_text": 0,
            "exact_query_count": 0,
            "title_semantic_alignment": 0,
            "heading_semantic_alignment": 0,
            "query_prominence_score": 0,
            "page_indexable": 1,
            "canonical_present": 1,
            "canonical_matches_final_url": 1,
            "commercial_signals_score": 0.666667,
            "trust_signals_score": 0.711111,
            "commercial_trust_score": 0.711111,
            "intent_alignment_score": 0.54301,
            "intent_is_commercial": 1,
            "commercial_intent_alignment": 0.54301,
        }
    )
    save_model(
        model=ConstantScoreModel(64.0),
        metrics={"mae": 1.0},
        model_path=model_path,
        metadata={
            "source": "local_dataset",
            "dataset_version": "guardrail-test",
            "model_schema_version": "v3",
            "feature_columns": v3_columns,
        },
    )

    explanation = explain_score(features, model_path=model_path)

    assert explanation["ml_score"] == 64.0
    assert explanation["final_score"] == 64.0
    assert explanation["relevance_guardrail"]["active"] is False
    assert {group["key"] for group in explanation["factor_groups"]} >= {
        "query_relevance",
        "content_depth",
        "commercial_trust",
        "technical_access",
        "competitor_context",
    }
    assert any(
        factor.get("key") == "query_topic_fit" and float(factor.get("impact", 0.0)) > 0.0
        for factor in explanation["top_positive_factors"]
    )
    assert not any(
        factor.get("key") in {"semantic_relevance", "content_depth_semantic_score", "semantic_content_richness"}
        and float(factor.get("impact", 0.0)) < 0.0
        for factor in explanation["top_negative_factors"]
    )


def test_query_relevance_guardrail_caps_partial_query_match(tmp_path):
    model_path = tmp_path / "constant-v3-partial-relevance-model.pkl"
    v3_columns = get_model_feature_schema("v3").feature_columns
    features = {feature_name: 0.0 for feature_name in v3_columns}
    features.update(
        {
            "word_count": 2100,
            "heading_count": 9,
            "title_present": 1,
            "title_length_quality": 0.85,
            "meta_description_present": 1,
            "meta_length_quality": 0.85,
            "semantic_similarity": 0.52,
            "keyword_coverage_ratio": 0.5,
            "query_density": 0.006,
            "query_in_title": 0,
            "query_in_text": 0,
            "exact_query_count": 0,
            "title_semantic_alignment": 0.1,
            "heading_semantic_alignment": 0.1,
            "query_prominence_score": 0.2,
            "page_indexable": 1,
            "canonical_present": 1,
            "canonical_matches_final_url": 1,
            "commercial_signals_score": 1,
            "trust_signals_score": 1,
            "commercial_trust_score": 1,
            "intent_alignment_score": 0.8,
            "intent_is_commercial": 1,
            "commercial_intent_alignment": 0.8,
        }
    )
    save_model(
        model=ConstantScoreModel(91.0),
        metrics={"mae": 1.0},
        model_path=model_path,
        metadata={
            "source": "local_dataset",
            "dataset_version": "guardrail-test",
            "model_schema_version": "v3",
            "feature_columns": v3_columns,
        },
    )

    explanation = explain_score(features, model_path=model_path)

    assert explanation["ml_score"] == 91.0
    assert explanation["final_score"] == 65.52
    assert explanation["relevance_guardrail"]["reason"] == "partial_query_topic_match"
    assert explanation["relevance_guardrail"]["active"] is True
    assert explanation["relevance_guardrail"]["query_relevance_multiplier"] == 0.72


def test_rule_score_is_calibrated_instead_of_saturating_at_raw_impact_cap():
    features = {
        "word_count": 1621,
        "heading_count": 12,
        "title_present": 1,
        "title_length_quality": 0.818182,
        "meta_description_present": 1,
        "meta_length_quality": 0.475862,
        "semantic_similarity": 0.574954,
        "keyword_coverage_ratio": 1,
        "title_semantic_alignment": 0.3833,
        "heading_semantic_alignment": 0.3833,
        "content_depth_semantic_score": 0.574954,
        "semantic_content_richness": 0.242439,
        "keyword_balance_score": 0.992392,
        "conversion_signal_score": 1,
        "query_prominence_score": 0.8,
        "text_to_html_ratio": 0.0951,
        "unique_word_ratio": 0.4682,
        "page_indexable": 1,
        "canonical_present": 1,
        "canonical_matches_final_url": 0,
        "redirect_efficiency_score": 1,
        "redirect_count": 0,
        "url_hygiene_score": 1,
        "technical_metadata_score": 1,
        "commercial_signals_score": 1,
        "trust_signals_score": 0.888889,
        "contact_options_score": 0.6,
        "intent_alignment_score": 0.782425,
        "intent_is_local_commercial": 1,
        "local_intent_alignment": 0.782425,
        "intent_is_commercial": 1,
        "commercial_intent_alignment": 0.743608,
    }

    rule_score, factors = calculate_rule_score(features)
    raw_impact = sum(float(factor["impact"]) for factor in factors)

    assert raw_impact > 100.0
    assert 0.0 <= rule_score < 85.0


def test_offer_readiness_does_not_require_price_on_the_audited_page():
    features = {
        "commercial_signals_score": 0.555556,
        "phone_present": 1,
        "address_present": 1,
        "business_hours_present": 1,
        "cta_present": 1,
        "value_proposition_present": 1,
        "price_present": 0,
        "delivery_info_present": 0,
        "payment_info_present": 0,
    }

    _, factors = calculate_rule_score(features)
    offer_factor = next(factor for factor in factors if factor["key"] == "commercial_completeness")

    assert offer_factor["label"] == "Offer and conversion completeness"
    assert offer_factor["value"] == 1.0
    assert offer_factor["impact"] == 6.5


def test_text_volume_is_only_a_small_sufficiency_signal():
    features = {
        "word_count": 2400,
        "semantic_similarity": 0.25,
        "keyword_coverage_ratio": 0.2,
        "title_present": 1,
        "title_length_quality": 0.8,
        "meta_description_present": 1,
        "meta_length_quality": 0.8,
        "heading_count": 4,
        "title_semantic_alignment": 0.2,
        "heading_semantic_alignment": 0.2,
        "content_depth_semantic_score": 0.25,
        "semantic_content_richness": 0.1,
        "keyword_balance_score": 0.2,
        "conversion_signal_score": 0.4,
        "query_prominence_score": 0.2,
        "text_to_html_ratio": 0.2,
        "unique_word_ratio": 0.5,
    }

    _, factors = calculate_rule_score(features)
    text_factor = next(factor for factor in factors if factor["key"] == "content_depth")

    assert text_factor["label"] == "Text sufficiency"
    assert text_factor["impact"] == 4.0
    assert "не оценка качества" in str(text_factor["detail"])


def test_model_schema_v3_combines_pre_competitor_feature_groups():
    v1_columns = get_model_feature_schema("v1").feature_columns
    v2_columns = get_model_feature_schema("v2").feature_columns
    v3_columns = get_model_feature_schema("v3").feature_columns

    assert EXPECTED_V3_FEATURE_COUNT == (
        len(v1_columns)
        + len(SNAPSHOT_AUXILIARY_FEATURE_COLUMNS)
        + len(HEAVY_ANALYSIS_FEATURE_COLUMNS)
        + len(INTENT_ALIGNMENT_FEATURE_COLUMNS)
    )
    assert len(v3_columns) == len(set(v3_columns))
    assert v3_columns[: len(v2_columns)] == v2_columns
    assert "heavy_analysis_overall_score" in v3_columns
    assert "intent_alignment_score" in v3_columns
    assert not any(feature_name in v3_columns for feature_name in SERP_RELATIVE_FEATURE_COLUMNS)
