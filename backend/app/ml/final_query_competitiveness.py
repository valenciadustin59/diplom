from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.ml.model import DEFAULT_MODEL_PATH, clear_model_cache, load_model_artifact, save_model
from app.ml.model_schema import MODEL_SCHEMA_VERSION_V3, get_model_feature_schema
from app.ml.no_publish_decision import sha1_file
from app.ml.train import (
    evaluate_model_rows,
    load_dataset_rows,
    save_dataset_split_manifest,
    split_dataset_rows,
    train_candidate_models,
)
from app.query_relevance import build_query_relevance_guardrail, build_query_topic_metrics


TASK_RANGE = "D62-D70"
FINAL_DATASET_VERSION = "dataset-v7-final"
FINAL_ARTIFACT_VERSION = "dataset-v7-final-query-competitiveness"
FINAL_SCORE_CONTRACT_VERSION = "query-competitiveness-final-v2"
FINAL_LABEL_SCHEMA_VERSION = "query-competitiveness-rubric-v1"
FINAL_MODEL_PATH = Path(__file__).resolve().parents[2] / "artifacts" / "page_quality_model.dataset-v7-final-candidate.pkl"
FINAL_DATASET_DIR = Path(__file__).resolve().parents[2] / "data" / "dataset_versions" / FINAL_DATASET_VERSION
FINAL_DATASET_PATH = FINAL_DATASET_DIR / "dataset.csv"
FINAL_HARD_NEGATIVE_DATASET_PATH = FINAL_DATASET_DIR / "dataset.with-hard-negatives.csv"
FINAL_LABELED_DATASET_PATH = FINAL_DATASET_DIR / "dataset.labeled.csv"
FINAL_MANIFEST_PATH = FINAL_DATASET_DIR / "manifest.json"
FINAL_SPLIT_PATH = FINAL_DATASET_DIR / "split.json"
FINAL_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "ranking-benchmarks" / FINAL_DATASET_VERSION
FINAL_REPORT_JSON_PATH = FINAL_OUTPUT_DIR / "final-query-competitiveness-report.json"
FINAL_REPORT_MD_PATH = FINAL_OUTPUT_DIR / "final-query-competitiveness-report.md"
VERSIONED_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "versions"

DOMAIN_CAP_PER_DOMAIN = 12
MIN_FINAL_QUERIES = 500
MIN_FINAL_CATEGORIES = 50
MIN_FINAL_CITIES = 5
MIN_VALIDATION_ROWS = 40


def _float(row: Mapping[str, object], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default) or default)
    except (TypeError, ValueError):
        return default


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, value))


def _round_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 4)


def _numeric_mapping(row: Mapping[str, object]) -> dict[str, float]:
    numeric: dict[str, float] = {}
    for key, value in row.items():
        try:
            numeric[str(key)] = float(value or 0.0)
        except (TypeError, ValueError):
            continue
    return numeric


def _read_manifest(path: str | Path = FINAL_MANIFEST_PATH) -> dict[str, Any]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return {}
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _domain_counts(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        domain = str(row.get("domain") or "").strip()
        if domain:
            counts[domain] = counts.get(domain, 0) + 1
    return counts


def validate_final_dataset(
    *,
    dataset_path: str | Path = FINAL_DATASET_PATH,
    manifest_path: str | Path = FINAL_MANIFEST_PATH,
    hard_negative_dataset_path: str | Path = FINAL_HARD_NEGATIVE_DATASET_PATH,
    domain_cap: int = DOMAIN_CAP_PER_DOMAIN,
) -> dict[str, Any]:
    manifest = _read_manifest(manifest_path)
    resolved_dataset_path = Path(dataset_path)
    resolved_hard_negative_path = Path(hard_negative_dataset_path)
    hard_negatives_required = (
        manifest.get("collection_policy", {}).get("hard_negatives_required") is True
        if isinstance(manifest.get("collection_policy"), dict)
        else False
    )
    checks: dict[str, bool] = {
        "dataset_exists": resolved_dataset_path.exists(),
        "manifest_exists": Path(manifest_path).exists(),
        "manifest_is_final_version": manifest.get("dataset_version") == FINAL_DATASET_VERSION
        or manifest.get("version") == FINAL_DATASET_VERSION,
        "manifest_ready_for_training": bool(manifest.get("ready_for_training")),
        "weak_serp_labels_not_final": manifest.get("collection_policy", {}).get("weak_serp_labels_allowed") is False
        if isinstance(manifest.get("collection_policy"), dict)
        else True,
        "hard_negatives_materialized": resolved_hard_negative_path.exists() if hard_negatives_required else True,
    }
    rows: list[dict[str, str]] = []
    if resolved_dataset_path.exists():
        rows = load_dataset_rows(resolved_dataset_path)
    hard_negative_rows: list[dict[str, str]] = []
    if resolved_hard_negative_path.exists():
        hard_negative_rows = load_dataset_rows(resolved_hard_negative_path)
    hard_negative_rows_count = sum(
        1 for row in hard_negative_rows if str(row.get("hard_negative") or "").strip() in {"1", "true", "True"}
    )
    checks["hard_negatives_present"] = hard_negative_rows_count > 0 if hard_negatives_required else True
    queries = {str(row.get("query") or "") for row in rows if str(row.get("query") or "").strip()}
    categories = {str(row.get("category") or "") for row in rows if str(row.get("category") or "").strip()}
    cities = {str(row.get("city") or "") for row in rows if str(row.get("city") or "").strip()}
    domain_counts = _domain_counts(rows)
    max_domain_rows = max(domain_counts.values(), default=0)
    checks.update(
        {
            "min_queries": len(queries) >= MIN_FINAL_QUERIES,
            "min_categories": len(categories) >= MIN_FINAL_CATEGORIES,
            "min_cities": len(cities) >= MIN_FINAL_CITIES,
            "domain_cap": max_domain_rows <= domain_cap,
        }
    )
    failed_checks = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failed_checks,
        "checks": checks,
        "failed_checks": failed_checks,
        "rows_count": len(rows),
        "queries_count": len(queries),
        "categories_count": len(categories),
        "cities_count": len(cities),
        "domains_count": len(domain_counts),
        "max_domain_rows": max_domain_rows,
        "domain_cap": domain_cap,
        "dataset_path": str(resolved_dataset_path),
        "hard_negative_dataset_path": str(resolved_hard_negative_path),
        "hard_negative_rows_count": hard_negative_rows_count,
        "training_rows_count": len(hard_negative_rows) if hard_negative_rows else len(rows),
        "manifest_path": str(Path(manifest_path)),
    }


def competitiveness_base_score(row: Mapping[str, object]) -> float:
    features = _numeric_mapping(row)
    metrics = build_query_topic_metrics(features)
    topic_fit = float(metrics["relevance_score"])
    topic_depth = _bounded(
        (_float(row, "semantic_content_richness") * 0.40)
        + (_float(row, "content_depth_semantic_score") * 0.35)
        + (_float(row, "keyword_balance_score") * 0.25)
    )
    commercial = _bounded(
        (_float(row, "commercial_trust_score") * 0.45)
        + (_float(row, "trust_signals_score") * 0.30)
        + (_float(row, "commercial_signals_score") * 0.25)
    )
    technical = _bounded(
        (_float(row, "technical_seo_score") * 0.42)
        + (_float(row, "canonical_signal_score") * 0.22)
        + (_float(row, "url_hygiene_score") * 0.18)
        + (_float(row, "technical_metadata_score") * 0.18)
    )
    intent = _bounded(
        (_float(row, "intent_alignment_score") * 0.55)
        + (_float(row, "commercial_intent_alignment") * 0.25)
        + (_float(row, "informational_intent_alignment") * 0.20)
    )
    rank_prior = _bounded(1.0 - ((max(1.0, _float(row, "rank", 10.0)) - 1.0) / 9.0))
    base = (
        topic_fit * 38.0
        + topic_depth * 20.0
        + commercial * 15.0
        + technical * 12.0
        + intent * 10.0
        + rank_prior * 5.0
    )
    return _round_score(base)


def final_target_score(row: Mapping[str, object]) -> dict[str, Any]:
    base_score = competitiveness_base_score(row)
    guardrail = build_query_relevance_guardrail(_numeric_mapping(row), base_score)
    multiplier = float(guardrail["query_relevance_multiplier"])
    return {
        "target_score": _round_score(float(guardrail["adjusted_score"])),
        "competitiveness_base_score": base_score,
        "query_relevance_multiplier": round(multiplier, 4),
        "query_relevance_band": guardrail["band"] or "strong_match",
        "query_relevance_reason": guardrail["reason"] or "strong_query_topic_fit",
        "query_relevance_score": guardrail["metrics"]["relevance_score"],
    }


def apply_final_labels(
    *,
    dataset_path: str | Path = FINAL_DATASET_PATH,
    output_path: str | Path = FINAL_LABELED_DATASET_PATH,
) -> dict[str, Any]:
    rows = load_dataset_rows(dataset_path)
    if not rows:
        raise ValueError("Final dataset is empty and cannot be labeled.")
    labeled_rows: list[dict[str, Any]] = []
    band_counts: dict[str, int] = {}
    for row in rows:
        label = final_target_score(row)
        labeled_row = {
            **row,
            "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
            "label_source": "deterministic_expert_rubric_v7",
            "expert_target_score": label["target_score"],
            "target_score": label["target_score"],
            "competitiveness_base_score": label["competitiveness_base_score"],
            "query_relevance_multiplier": label["query_relevance_multiplier"],
            "query_relevance_band": label["query_relevance_band"],
            "query_relevance_reason": label["query_relevance_reason"],
            "query_relevance_score": label["query_relevance_score"],
        }
        band = str(label["query_relevance_band"])
        band_counts[band] = band_counts.get(band, 0) + 1
        labeled_rows.append(labeled_row)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(labeled_rows[0].keys())
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(labeled_rows)
    return {
        "dataset_path": str(Path(dataset_path)),
        "labeled_dataset_path": str(output),
        "rows_count": len(labeled_rows),
        "band_counts": band_counts,
        "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
    }


def _candidate_name(candidate: Mapping[str, Any]) -> str:
    return str(candidate.get("model_type") or "candidate")


def train_final_candidate(
    *,
    dataset_path: str | Path = FINAL_DATASET_PATH,
    training_dataset_path: str | Path = FINAL_HARD_NEGATIVE_DATASET_PATH,
    labeled_dataset_path: str | Path = FINAL_LABELED_DATASET_PATH,
    candidate_model_path: str | Path = FINAL_MODEL_PATH,
    split_output_path: str | Path = FINAL_SPLIT_PATH,
    random_state: int = 42,
    test_size: float = 0.2,
) -> dict[str, Any]:
    validation = validate_final_dataset(dataset_path=dataset_path)
    if not validation["passed"]:
        raise ValueError(f"dataset-v7-final is not ready for training: {validation['failed_checks']}")
    resolved_training_dataset_path = Path(training_dataset_path)
    if not resolved_training_dataset_path.exists():
        resolved_training_dataset_path = Path(dataset_path)
    label_report = apply_final_labels(dataset_path=resolved_training_dataset_path, output_path=labeled_dataset_path)
    rows = load_dataset_rows(labeled_dataset_path)
    train_rows, validation_rows, split_metadata = split_dataset_rows(rows, test_size=test_size, random_state=random_state)
    feature_schema = get_model_feature_schema(MODEL_SCHEMA_VERSION_V3)
    candidates, benchmark = train_candidate_models(
        train_rows,
        validation_rows,
        random_state=random_state,
        feature_columns=feature_schema.feature_columns,
        force_catboost=True,
    )
    catboost_candidates = [candidate for candidate in candidates if candidate.get("model_type") == "CatBoostRegressor"]
    if not catboost_candidates:
        raise RuntimeError("Final D65 candidate must be CatBoostRegressor; CatBoost candidate was not produced.")
    selected = catboost_candidates[0]
    split = save_dataset_split_manifest(
        train_rows,
        validation_rows,
        dataset_path=labeled_dataset_path,
        dataset_version=FINAL_DATASET_VERSION,
        test_size=test_size,
        random_state=random_state,
        split_metadata=split_metadata,
        output_path=split_output_path,
    )
    metadata = {
        "source": "local_dataset",
        "model_type": _candidate_name(selected),
        "dataset_version": FINAL_DATASET_VERSION,
        "artifact_version": FINAL_ARTIFACT_VERSION,
        "artifact_family": "page_quality_model.dataset-v7-final",
        "candidate_name": "final_query_competitiveness_catboost",
        "candidate_family": "query_competitiveness",
        "model_schema_version": MODEL_SCHEMA_VERSION_V3,
        "feature_columns": list(feature_schema.feature_columns),
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
        "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
        "non_production": True,
        "runtime_enabled": False,
        "dataset_metadata": {
            "dataset_version": FINAL_DATASET_VERSION,
            "rows_count": len(rows),
            "queries_count": len({str(row.get("query") or "") for row in rows}),
            "domains_count": len({str(row.get("domain") or "") for row in rows}),
            "categories_count": len({str(row.get("category") or "") for row in rows}),
            "cities_count": len({str(row.get("city") or "") for row in rows if str(row.get("city") or "").strip()}),
            "manifest_generated_at": _read_manifest().get("generated_at"),
            "source_dataset_path": str(Path(dataset_path)),
            "training_dataset_path": str(resolved_training_dataset_path),
        },
    }
    saved_path = save_model(
        model=selected["model"],
        metrics={
            **selected["metrics"],
            "train_rows": float(len(train_rows)),
            "validation_rows": float(len(validation_rows)),
            **split_metadata,
        },
        model_path=candidate_model_path,
        metadata=metadata,
    )
    sidecar_path = Path(f"{saved_path}.metadata.json")
    sidecar_path.write_text(
        json.dumps({**metadata, "metrics": selected["metrics"], "model_path": str(saved_path)}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "task": "D65",
        "candidate_model_path": str(saved_path),
        "candidate_metadata_path": str(sidecar_path),
        "selected_candidate": _candidate_name(selected),
        "metrics": selected["metrics"],
        "benchmark": benchmark,
        "label_report": label_report,
        "split": split,
        "validation": validation,
    }


def _predict_rows(model: Any, rows: Sequence[Mapping[str, str]], feature_columns: Sequence[str]) -> list[float]:
    matrix = [[float(row.get(feature, 0.0) or 0.0) for feature in feature_columns] for row in rows]
    return [_round_score(float(value)) for value in model.predict(matrix)]


def final_product_guardrails(candidate_path: str | Path, validation_rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    artifact = load_model_artifact(candidate_path)
    if artifact is None:
        raise FileNotFoundError(f"Candidate artifact not found: {candidate_path}")
    feature_columns = artifact["feature_columns"]
    predictions = _predict_rows(artifact["model"], validation_rows, feature_columns)  # type: ignore[arg-type]
    rows_with_predictions = list(zip(validation_rows, predictions, strict=False))
    mismatch_rows = [
        (row, prediction)
        for row, prediction in rows_with_predictions
        if float(row.get("query_relevance_multiplier") or 1.0) <= 0.15
    ]
    strong_rows = [
        (row, prediction)
        for row, prediction in rows_with_predictions
        if str(row.get("query_relevance_band") or "") == "strong_match"
    ]
    unrelated_above_35 = [prediction for _row, prediction in mismatch_rows if prediction > 35.0]
    mismatch_below_20_ratio = (
        sum(1 for _row, prediction in mismatch_rows if prediction <= 20.0) / len(mismatch_rows)
        if mismatch_rows
        else 1.0
    )
    strong_average_prediction = (
        sum(prediction for _row, prediction in strong_rows) / len(strong_rows)
        if strong_rows
        else 0.0
    )
    checks = {
        "candidate_available": True,
        "validation_rows_present": len(validation_rows) >= MIN_VALIDATION_ROWS,
        "unrelated_pages_not_above_35": not unrelated_above_35,
        "mismatch_below_20_ratio": mismatch_below_20_ratio >= 0.9,
        "strong_relevance_not_collapsed": strong_average_prediction >= 45.0 if strong_rows else True,
        "score_contract_version_present": artifact.get("artifact_version") == FINAL_ARTIFACT_VERSION
        or artifact.get("dataset_version") == FINAL_DATASET_VERSION,
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failed_checks,
        "checks": checks,
        "failed_checks": failed_checks,
        "mismatch_rows": len(mismatch_rows),
        "strong_rows": len(strong_rows),
        "mismatch_below_20_ratio": round(mismatch_below_20_ratio, 6),
        "strong_average_prediction": round(strong_average_prediction, 6),
        "max_unrelated_prediction": max(unrelated_above_35, default=None),
    }


def build_final_decision_report(
    *,
    candidate_model_path: str | Path = FINAL_MODEL_PATH,
    labeled_dataset_path: str | Path = FINAL_LABELED_DATASET_PATH,
    report_json_path: str | Path = FINAL_REPORT_JSON_PATH,
    report_md_path: str | Path = FINAL_REPORT_MD_PATH,
) -> dict[str, Any]:
    rows = load_dataset_rows(labeled_dataset_path)
    _train_rows, validation_rows, split_metadata = split_dataset_rows(rows, test_size=0.2, random_state=42)
    artifact = load_model_artifact(candidate_model_path)
    if artifact is None:
        raise FileNotFoundError(f"Candidate artifact not found: {candidate_model_path}")
    metrics = evaluate_model_rows(artifact["model"], validation_rows, feature_columns=artifact["feature_columns"])  # type: ignore[arg-type]
    guardrails = final_product_guardrails(candidate_model_path, validation_rows)
    decision = {
        "decision": "publish_candidate" if guardrails["passed"] else "no_publish",
        "publish_action": "controlled_publish_required" if guardrails["passed"] else "no_publish",
        "selected_candidate": "final_query_competitiveness_catboost" if guardrails["passed"] else None,
        "reason": "final_product_guardrails_passed" if guardrails["passed"] else "final_product_guardrails_failed",
    }
    report = {
        "task": "D66",
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": FINAL_DATASET_VERSION,
        "candidate_model_path": str(Path(candidate_model_path)),
        "candidate_sha1": sha1_file(Path(candidate_model_path)),
        "metrics": metrics,
        "split": split_metadata,
        "product_guardrails": guardrails,
        "decision": decision,
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
        "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
    }
    _write_json(report_json_path, report)
    Path(report_md_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_md_path).write_text(
        "\n".join(
            [
                "# D66 Final Query-Competitiveness Decision",
                "",
                f"- Decision: `{decision['decision']}`",
                f"- Reason: `{decision['reason']}`",
                f"- Candidate: `{candidate_model_path}`",
                f"- MAE: `{metrics.get('mae')}`",
                f"- Spearman: `{metrics.get('spearman_mean')}`",
                f"- NDCG@10: `{metrics.get('ndcg_at_10')}`",
                f"- Product guardrails passed: `{guardrails['passed']}`",
                f"- Failed checks: `{', '.join(guardrails['failed_checks']) or 'none'}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report


def run_final_controlled_publish(
    *,
    report_json_path: str | Path = FINAL_REPORT_JSON_PATH,
    candidate_model_path: str | Path = FINAL_MODEL_PATH,
    production_model_path: str | Path = DEFAULT_MODEL_PATH,
) -> dict[str, Any]:
    report = json.loads(Path(report_json_path).read_text(encoding="utf-8"))
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    if decision.get("decision") != "publish_candidate":
        raise ValueError(f"Final publish requires a publish_candidate decision, got {decision.get('decision')!r}")
    production_path = Path(production_model_path)
    candidate_path = Path(candidate_model_path)
    if not candidate_path.exists():
        raise FileNotFoundError(f"Candidate artifact not found: {candidate_path}")

    before_sha1 = sha1_file(production_path) if production_path.exists() else None
    VERSIONED_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    rollback_path = VERSIONED_ARTIFACTS_DIR / f"page_quality_model--rollback-before-{FINAL_ARTIFACT_VERSION}.pkl"
    if production_path.exists():
        shutil.copy2(production_path, rollback_path)
    shutil.copy2(candidate_path, production_path)
    clear_model_cache()
    after_sha1 = sha1_file(production_path)
    publish_report = {
        "task": "D67",
        "generated_at": datetime.now(UTC).isoformat(),
        "decision": "publish_candidate",
        "selected_candidate": "final_query_competitiveness_catboost",
        "candidate_model_path": str(candidate_path),
        "production_model_path": str(production_path),
        "rollback_model_path": str(rollback_path) if rollback_path.exists() else None,
        "production_sha1_before": before_sha1,
        "production_sha1_after": after_sha1,
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
        "source_decision_report": str(Path(report_json_path)),
    }
    _write_json(FINAL_OUTPUT_DIR / "controlled-publish-report.json", publish_report)
    return publish_report


def run_final_pipeline(*, publish: bool = False) -> dict[str, Any]:
    validation = validate_final_dataset()
    if not validation["passed"]:
        report = {
            "task": TASK_RANGE,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "blocked_until_dataset_v7_collection",
            "validation": validation,
            "next_command": (
                "Collect dataset-v7-final top-10 pages, mark manifest ready_for_training=true, "
                "materialize hard negatives with `python -m app.ml.final_hard_negatives`, "
                "then run `python -m app.ml.final_query_competitiveness --train --decide`."
            ),
        }
        _write_json(FINAL_REPORT_JSON_PATH, report)
        return report
    training = train_final_candidate()
    decision = build_final_decision_report()
    publish_report = run_final_controlled_publish() if publish and decision["decision"]["decision"] == "publish_candidate" else None
    return {
        "task": TASK_RANGE,
        "status": "completed",
        "training": training,
        "decision": decision,
        "publish": publish_report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run D62-D68 final query-competitiveness model pipeline.")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--label", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--decide", action="store_true")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    if args.validate:
        print(json.dumps(validate_final_dataset(), ensure_ascii=False, indent=2))
        return
    if args.label:
        print(json.dumps(apply_final_labels(), ensure_ascii=False, indent=2))
        return
    if args.train:
        print(json.dumps(train_final_candidate(), ensure_ascii=False, indent=2))
        return
    if args.decide:
        print(json.dumps(build_final_decision_report(), ensure_ascii=False, indent=2))
        return
    print(json.dumps(run_final_pipeline(publish=args.publish), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
