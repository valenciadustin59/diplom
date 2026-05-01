import csv
from pathlib import Path
from app.ml import FEATURE_COLUMNS, explain_score, load_saved_model, predict_score, train_quality_model
from app.ml.dataset_builder import DATASET_COLUMNS
from app.ml.model import load_model_artifact, save_model, train_model
from app.features import INTENT_ALIGNMENT_FEATURE_COLUMNS, SERP_RELATIVE_FEATURE_COLUMNS, SNAPSHOT_AUXILIARY_FEATURE_COLUMNS
from app.heavy_analysis import HEAVY_ANALYSIS_FEATURE_COLUMNS
from app.ml.model_schema import get_model_feature_schema
EXPECTED_V2_FEATURE_COUNT = len(get_model_feature_schema("v2").feature_columns)
EXPECTED_V3_FEATURE_COUNT = len(get_model_feature_schema("v3").feature_columns)
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
