from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.features import QUERY_INTENT_MODIFIER_TERMS
from app.features import _coverage_ratio as _feature_coverage_ratio
from app.features import _normalize_query_token, _tokenize
from app.features import _phrase_count as _feature_phrase_count
from app.ml.controlled_publish import build_controlled_versioned_artifact_path, ensure_rollback_reference
from app.ml.model import DEFAULT_MODEL_PATH, clear_model_cache, load_model_artifact, load_saved_model, save_model
from app.ml.model_schema import (
    MODEL_SCHEMA_VERSION_V3,
    MODEL_SCHEMA_VERSION_V4,
    QUERY_RELEVANCE_CORE_FEATURE_COLUMNS,
    get_model_feature_schema,
)
from app.ml.no_publish_decision import build_production_artifact_state, sha1_file
from app.ml.publish import (
    build_artifact_metadata_path,
    build_artifact_public_metadata,
    build_primary_artifact_version,
    write_artifact_public_metadata,
)
from app.ml.query_core_model import QueryCoreGuardrailRegressor
from app.ml.ranking_benchmark import build_feature_importance_summary
from app.ml.train import (
    evaluate_model_rows,
    load_dataset_rows,
    ranking_metrics,
    rows_to_matrix,
    save_dataset_split_manifest,
    split_dataset_rows,
    train_candidate_models,
)
from app.query_relevance import build_query_relevance_guardrail, build_query_topic_metrics


TASK_RANGE = "D62-D82"
FINAL_DATASET_VERSION = "dataset-v7-final"
FINAL_ARTIFACT_VERSION = "dataset-v7-final-query-competitiveness"
D82_ARTIFACT_VERSION = "dataset-v7-final-query-core-v1"
FINAL_SCORE_CONTRACT_VERSION = "query-competitiveness-final-v2"
FINAL_LABEL_SCHEMA_VERSION = "query-competitiveness-rubric-v1"
FINAL_MODEL_PATH = Path(__file__).resolve().parents[2] / "artifacts" / "page_quality_model.dataset-v7-final-candidate.pkl"
D82_MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "artifacts"
    / "page_quality_model.dataset-v7-final-query-core-candidate.pkl"
)
FINAL_DATASET_DIR = Path(__file__).resolve().parents[2] / "data" / "dataset_versions" / FINAL_DATASET_VERSION
FINAL_DATASET_PATH = FINAL_DATASET_DIR / "dataset.csv"
FINAL_HARD_NEGATIVE_DATASET_PATH = FINAL_DATASET_DIR / "dataset.with-hard-negatives.csv"
FINAL_LABELED_DATASET_PATH = FINAL_DATASET_DIR / "dataset.labeled.csv"
D82_QUERY_CORE_DATASET_PATH = FINAL_DATASET_DIR / "dataset.query-core.csv"
FINAL_LABEL_REPORT_JSON_PATH = FINAL_DATASET_DIR / "d77-final-label-report.json"
FINAL_LABEL_REPORT_MD_PATH = FINAL_DATASET_DIR / "d77-final-label-report.md"
FINAL_MANIFEST_PATH = FINAL_DATASET_DIR / "manifest.json"
FINAL_SPLIT_PATH = FINAL_DATASET_DIR / "split.json"
FINAL_SPLIT_VALIDATION_JSON_PATH = FINAL_DATASET_DIR / "d78-split-validation-report.json"
FINAL_SPLIT_VALIDATION_MD_PATH = FINAL_DATASET_DIR / "d78-split-validation-report.md"
FINAL_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "ranking-benchmarks" / FINAL_DATASET_VERSION
FINAL_REPORT_JSON_PATH = FINAL_OUTPUT_DIR / "final-query-competitiveness-report.json"
FINAL_REPORT_MD_PATH = FINAL_OUTPUT_DIR / "final-query-competitiveness-report.md"
D79_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "ranking-benchmarks" / "dataset-v7-final-d79"
D79_REPORT_JSON_PATH = D79_OUTPUT_DIR / "d79-candidate-training-report.json"
D79_REPORT_MD_PATH = D79_OUTPUT_DIR / "d79-candidate-training-report.md"
D80_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "ranking-benchmarks" / "dataset-v7-final-d80"
D80_REPORT_JSON_PATH = D80_OUTPUT_DIR / "d80-controlled-decision-report.json"
D80_REPORT_MD_PATH = D80_OUTPUT_DIR / "d80-controlled-decision-report.md"
D81_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "ranking-benchmarks" / "dataset-v7-final-d81"
D81_REPORT_JSON_PATH = D81_OUTPUT_DIR / "d81-controlled-release-report.json"
D81_REPORT_MD_PATH = D81_OUTPUT_DIR / "d81-controlled-release-report.md"
D82_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "ranking-benchmarks" / "dataset-v7-final-d82"
D82_REPORT_JSON_PATH = D82_OUTPUT_DIR / "d82-query-core-hardening-report.json"
D82_REPORT_MD_PATH = D82_OUTPUT_DIR / "d82-query-core-hardening-report.md"
D82_DECISION_JSON_PATH = D82_OUTPUT_DIR / "d82-controlled-decision-report.json"
D82_DECISION_MD_PATH = D82_OUTPUT_DIR / "d82-controlled-decision-report.md"
VERSIONED_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "versions"

DOMAIN_CAP_PER_DOMAIN = 12
MIN_FINAL_QUERIES = 500
MIN_FINAL_CATEGORIES = 50
MIN_FINAL_CITIES = 5
MIN_VALIDATION_ROWS = 40
HARD_NEGATIVE_SCORE_CAP = 35.0
D82_HARD_NEGATIVE_TRAINING_CAP = 25.0
D82_HARD_NEGATIVE_SAMPLE_WEIGHT = 10.0
D82_QUERY_CORE_COVERAGE_THRESHOLD = 0.75
D82_SEMANTIC_SIMILARITY_THRESHOLD = 0.55


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


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _score_summary(values: Sequence[float]) -> dict[str, float]:
    if not values:
        return {"count": 0.0, "min": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0, "max": 0.0}
    sorted_values = sorted(float(value) for value in values)

    def percentile(fraction: float) -> float:
        index = min(len(sorted_values) - 1, int(len(sorted_values) * fraction))
        return round(sorted_values[index], 4)

    return {
        "count": float(len(sorted_values)),
        "min": round(sorted_values[0], 4),
        "p25": percentile(0.25),
        "p50": percentile(0.50),
        "p75": percentile(0.75),
        "p90": percentile(0.90),
        "max": round(sorted_values[-1], 4),
    }


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


def _write_label_report_md(path: str | Path, report: Mapping[str, Any]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# D77 deterministic labels for dataset-v7-final",
        "",
        f"- Dataset: `{report['dataset_path']}`",
        f"- Labeled dataset: `{report['labeled_dataset_path']}`",
        f"- Rows: `{report['rows_count']}`",
        f"- Regular rows: `{report['regular_rows_count']}`",
        f"- Hard negatives: `{report['hard_negative_rows_count']}`",
        f"- Hard negative cap: `{report['hard_negative_cap']}`",
        f"- Hard negatives above cap: `{report['hard_negative_above_cap_count']}`",
        f"- Cap applications: `{report['hard_negative_cap_applied_count']}`",
        f"- Label schema: `{report['label_schema_version']}`",
        f"- Score contract: `{report['score_contract_version']}`",
        "",
        "## Score distribution",
        "",
    ]
    for name, summary in [
        ("all", report["score_distribution"]),
        ("regular", report["regular_score_distribution"]),
        ("hard_negative", report["hard_negative_score_distribution"]),
    ]:
        lines.append(
            "- "
            + name
            + ": "
            + ", ".join(f"{key}={value}" for key, value in dict(summary).items())
        )
    lines.extend(["", "## Query relevance bands", ""])
    lines.append("- all: " + ", ".join(f"{key}={value}" for key, value in dict(report["band_counts"]).items()))
    lines.append(
        "- hard_negative: "
        + ", ".join(f"{key}={value}" for key, value in dict(report["hard_negative_band_counts"]).items())
    )
    resolved_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_json(path: str | Path) -> dict[str, Any]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return {}
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_artifact_text(artifact_path: object, *, dataset_dir: str | Path = FINAL_DATASET_DIR) -> str:
    rendered_path = str(artifact_path or "").strip()
    if not rendered_path:
        return ""
    resolved_path = Path(rendered_path)
    if not resolved_path.is_absolute():
        resolved_path = Path(dataset_dir) / resolved_path
    if not resolved_path.exists():
        return ""
    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    parts = [
        str(payload.get("text") or ""),
        str(payload.get("title") or ""),
        str(payload.get("description") or ""),
    ]
    document = payload.get("document")
    if isinstance(document, dict):
        parts.extend(
            [
                str(document.get("title") or ""),
                str(document.get("description") or ""),
                str(document.get("h1") or ""),
            ]
        )
    return " ".join(part for part in parts if part.strip())


def _query_core_feature_values(query: object, text: str) -> dict[str, float]:
    query_tokens = [_normalize_query_token(token) for token in _tokenize(str(query or ""))]
    query_tokens = [token for token in query_tokens if token]
    text_tokens = [_normalize_query_token(token) for token in _tokenize(text)]
    word_freq = Counter(text_tokens)
    core_query_words = [word for word in query_tokens if word not in QUERY_INTENT_MODIFIER_TERMS]
    intent_modifier_words = [word for word in query_tokens if word in QUERY_INTENT_MODIFIER_TERMS]
    core_phrase_count = _feature_phrase_count(core_query_words or query_tokens, text_tokens)
    return {
        "query_core_term_count": float(sum(word_freq[word] for word in core_query_words)),
        "query_core_term_matches": float(sum(1 for word in core_query_words if word in word_freq)),
        "query_core_keyword_coverage_ratio": round(
            _feature_coverage_ratio(core_query_words or query_tokens, word_freq),
            6,
        ),
        "query_core_phrase_count": float(core_phrase_count),
        "query_core_phrase_present": float(int(core_phrase_count > 0)),
        "query_intent_modifier_count": float(sum(word_freq[word] for word in intent_modifier_words)),
        "query_intent_modifier_matches": float(sum(1 for word in intent_modifier_words if word in word_freq)),
        "query_intent_modifier_coverage_ratio": round(
            _feature_coverage_ratio(intent_modifier_words, word_freq),
            6,
        ),
    }


def materialize_query_core_dataset(
    *,
    labeled_dataset_path: str | Path = FINAL_LABELED_DATASET_PATH,
    output_path: str | Path = D82_QUERY_CORE_DATASET_PATH,
    dataset_dir: str | Path = FINAL_DATASET_DIR,
) -> dict[str, Any]:
    rows = load_dataset_rows(labeled_dataset_path)
    if not rows:
        raise ValueError(f"Dataset is empty: {labeled_dataset_path}")
    text_cache: dict[str, str] = {}
    enriched_rows: list[dict[str, str]] = []
    fallback_rows_count = 0
    for row in rows:
        enriched_row = dict(row)
        artifact_key = str(row.get("artifact_path") or "").strip()
        if artifact_key not in text_cache:
            text_cache[artifact_key] = _read_artifact_text(artifact_key, dataset_dir=dataset_dir)
        snapshot_text = text_cache[artifact_key]
        if not snapshot_text.strip():
            fallback_rows_count += 1
        combined_text = " ".join(
            part
            for part in (
                snapshot_text,
                str(row.get("title") or ""),
                str(row.get("snippet") or ""),
                str(row.get("url") or ""),
                str(row.get("domain") or ""),
            )
            if part.strip()
        )
        for key, value in _query_core_feature_values(row.get("query"), combined_text).items():
            enriched_row[key] = str(value)
        enriched_rows.append(enriched_row)

    fieldnames = list(rows[0].keys())
    for feature in QUERY_RELEVANCE_CORE_FEATURE_COLUMNS:
        if feature not in fieldnames:
            fieldnames.append(feature)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(enriched_rows)

    core_coverages = [_float(row, "query_core_keyword_coverage_ratio") for row in enriched_rows]
    hard_negative_coverages = [
        _float(row, "query_core_keyword_coverage_ratio") for row in enriched_rows if _truthy(row.get("hard_negative"))
    ]
    return {
        "task": "D82",
        "dataset_path": str(Path(labeled_dataset_path)),
        "output_path": str(output),
        "rows_count": len(enriched_rows),
        "artifact_texts_read": len(text_cache),
        "fallback_rows_count": fallback_rows_count,
        "added_feature_columns": list(QUERY_RELEVANCE_CORE_FEATURE_COLUMNS),
        "query_core_coverage_summary": _score_summary(core_coverages),
        "hard_negative_core_coverage_summary": _score_summary(hard_negative_coverages),
    }


def _majority_value(rows: Sequence[Mapping[str, object]], key: str) -> str:
    values = [str(row.get(key) or "").strip() for row in rows if str(row.get(key) or "").strip()]
    if not values:
        return ""
    counter = Counter(values)
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _is_hard_negative(row: Mapping[str, object]) -> bool:
    return _truthy(row.get("hard_negative"))


def _partition_rows_by_queries(
    rows: Sequence[dict[str, str]],
    train_queries: set[str],
    validation_queries: set[str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    train_rows: list[dict[str, str]] = []
    validation_rows: list[dict[str, str]] = []
    for row in rows:
        query = str(row.get("query") or "").strip()
        if query in validation_queries:
            validation_rows.append(row)
        elif query in train_queries:
            train_rows.append(row)
    return train_rows, validation_rows


def _split_partition_stats(rows: Sequence[Mapping[str, object]]) -> dict[str, Any]:
    queries = {str(row.get("query") or "").strip() for row in rows if str(row.get("query") or "").strip()}
    categories = {str(row.get("category") or "").strip() for row in rows if str(row.get("category") or "").strip()}
    cities = {str(row.get("city") or "").strip() for row in rows if str(row.get("city") or "").strip()}
    domains = [str(row.get("domain") or "").strip() for row in rows if str(row.get("domain") or "").strip()]
    domain_counts = Counter(domains)
    score_values = [_float(row, "target_score") for row in rows]
    hard_negative_rows = [row for row in rows if _is_hard_negative(row)]
    return {
        "rows_count": len(rows),
        "queries_count": len(queries),
        "categories_count": len(categories),
        "cities_count": len(cities),
        "domains_count": len(domain_counts),
        "max_domain_rows": max(domain_counts.values(), default=0),
        "hard_negative_rows_count": len(hard_negative_rows),
        "regular_rows_count": len(rows) - len(hard_negative_rows),
        "hard_negative_queries_count": len(
            {str(row.get("query") or "").strip() for row in hard_negative_rows if str(row.get("query") or "").strip()}
        ),
        "hard_negative_above_cap_count": sum(
            1 for row in hard_negative_rows if _float(row, "target_score") > HARD_NEGATIVE_SCORE_CAP
        ),
        "score_distribution": _score_summary(score_values),
        "band_counts": dict(Counter(str(row.get("query_relevance_band") or "unknown") for row in rows)),
        "label_source_counts": dict(Counter(str(row.get("label_source") or "unknown") for row in rows)),
    }


def _write_split_validation_markdown(path: str | Path, report: Mapping[str, Any]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    validation = report.get("validation") if isinstance(report.get("validation"), dict) else report
    train = validation.get("train_partition") if isinstance(validation.get("train_partition"), dict) else {}
    validation_partition = (
        validation.get("validation_partition") if isinstance(validation.get("validation_partition"), dict) else {}
    )
    lines = [
        "# D78 Leakage-Safe Split Validation",
        "",
        f"- Passed: `{validation.get('passed')}`",
        f"- Split mode: `{validation.get('split_mode')}`",
        f"- Labeled dataset: `{validation.get('labeled_dataset_path')}`",
        f"- Split path: `{validation.get('split_path')}`",
        f"- Query overlap: `{validation.get('query_overlap_count')}`",
        f"- Uncovered queries: `{validation.get('uncovered_labeled_queries_count')}`",
        f"- Hard negatives above cap: `{validation.get('hard_negative_above_cap_count')}`",
        "",
        "## Partitions",
        "",
        f"- Train: `{train.get('rows_count')}` rows, `{train.get('queries_count')}` queries, "
        f"`{train.get('categories_count')}` categories, `{train.get('hard_negative_rows_count')}` hard negatives",
        f"- Validation: `{validation_partition.get('rows_count')}` rows, "
        f"`{validation_partition.get('queries_count')}` queries, "
        f"`{validation_partition.get('categories_count')}` categories, "
        f"`{validation_partition.get('hard_negative_rows_count')}` hard negatives",
        "",
        "## Failed Checks",
        "",
    ]
    failed_checks = validation.get("failed_checks") if isinstance(validation.get("failed_checks"), list) else []
    if failed_checks:
        lines.extend(f"- `{check}`" for check in failed_checks)
    else:
        lines.append("- none")
    resolved_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_training_report_markdown(path: str | Path, report: Mapping[str, Any]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    split = report.get("split") if isinstance(report.get("split"), dict) else {}
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    feature_importance = (
        report.get("feature_importance_summary")
        if isinstance(report.get("feature_importance_summary"), dict)
        else {}
    )
    top_features = feature_importance.get("top_features") if isinstance(feature_importance.get("top_features"), list) else []
    lines = [
        "# D79 Dataset-v7 Final Candidate Training",
        "",
        f"- Dataset version: `{report.get('dataset_version')}`",
        f"- Selected candidate: `{report.get('selected_candidate')}`",
        f"- Candidate artifact: `{report.get('candidate_model_path')}`",
        f"- Candidate SHA1: `{report.get('candidate_sha1')}`",
        f"- Runtime enabled: `{report.get('runtime_enabled')}`",
        f"- Production artifact changed: `{report.get('production_artifact_changed')}`",
        f"- Split mode: `{split.get('split_mode')}`",
        f"- Train rows: `{split.get('train_rows_count')}`",
        f"- Validation rows: `{split.get('validation_rows_count')}`",
        "",
        "## Metrics",
        "",
        f"- MAE: `{metrics.get('mae')}`",
        f"- RMSE: `{metrics.get('rmse')}`",
        f"- Spearman: `{metrics.get('spearman_mean')}`",
        f"- NDCG@10: `{metrics.get('ndcg_at_10')}`",
        f"- Top-3 diagnostic: `{metrics.get('top_3_hit_rate')}`",
        "",
        "## Top Features",
        "",
    ]
    if top_features:
        lines.extend(
            f"- `{item.get('feature')}`: `{item.get('importance')}`"
            for item in top_features[:10]
            if isinstance(item, dict)
        )
    else:
        lines.append("- unavailable")
    resolved_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    guarded_score = float(guardrail["adjusted_score"])
    is_hard_negative = _truthy(row.get("hard_negative"))
    hard_negative_cap_applied = False
    if is_hard_negative and guarded_score > HARD_NEGATIVE_SCORE_CAP:
        guarded_score = HARD_NEGATIVE_SCORE_CAP
        hard_negative_cap_applied = True
    return {
        "target_score": _round_score(guarded_score),
        "competitiveness_base_score": base_score,
        "query_relevance_multiplier": round(multiplier, 4),
        "query_relevance_band": "hard_negative_cap" if hard_negative_cap_applied else guardrail["band"] or "strong_match",
        "query_relevance_reason": "cross_category_hard_negative_cap"
        if hard_negative_cap_applied
        else guardrail["reason"] or "strong_query_topic_fit",
        "query_relevance_score": guardrail["metrics"]["relevance_score"],
        "hard_negative_cap": HARD_NEGATIVE_SCORE_CAP if is_hard_negative else "",
        "hard_negative_cap_applied": int(hard_negative_cap_applied),
    }


def apply_final_labels(
    *,
    dataset_path: str | Path = FINAL_DATASET_PATH,
    output_path: str | Path = FINAL_LABELED_DATASET_PATH,
    report_path: str | Path | None = FINAL_LABEL_REPORT_JSON_PATH,
    markdown_report_path: str | Path | None = FINAL_LABEL_REPORT_MD_PATH,
) -> dict[str, Any]:
    rows = load_dataset_rows(dataset_path)
    if not rows:
        raise ValueError("Final dataset is empty and cannot be labeled.")
    labeled_rows: list[dict[str, Any]] = []
    band_counts: dict[str, int] = {}
    hard_negative_band_counts: dict[str, int] = {}
    regular_band_counts: dict[str, int] = {}
    label_source_counts: dict[str, int] = {}
    score_values: list[float] = []
    hard_negative_score_values: list[float] = []
    regular_score_values: list[float] = []
    hard_negative_cap_applied_count = 0
    hard_negative_above_cap_count = 0
    for row in rows:
        label = final_target_score(row)
        is_hard_negative = _truthy(row.get("hard_negative"))
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
            "hard_negative_cap": label["hard_negative_cap"],
            "hard_negative_cap_applied": label["hard_negative_cap_applied"],
        }
        band = str(label["query_relevance_band"])
        band_counts[band] = band_counts.get(band, 0) + 1
        label_source = str(labeled_row["label_source"])
        label_source_counts[label_source] = label_source_counts.get(label_source, 0) + 1
        score = float(label["target_score"])
        score_values.append(score)
        if is_hard_negative:
            hard_negative_score_values.append(score)
            hard_negative_band_counts[band] = hard_negative_band_counts.get(band, 0) + 1
            hard_negative_cap_applied_count += int(label["hard_negative_cap_applied"])
            if score > HARD_NEGATIVE_SCORE_CAP:
                hard_negative_above_cap_count += 1
        else:
            regular_score_values.append(score)
            regular_band_counts[band] = regular_band_counts.get(band, 0) + 1
        labeled_rows.append(labeled_row)

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(labeled_rows[0].keys())
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(labeled_rows)
    report = {
        "task": "D77",
        "dataset_path": str(Path(dataset_path)),
        "labeled_dataset_path": str(output),
        "rows_count": len(labeled_rows),
        "band_counts": band_counts,
        "regular_band_counts": regular_band_counts,
        "hard_negative_band_counts": hard_negative_band_counts,
        "label_source_counts": label_source_counts,
        "hard_negative_rows_count": len(hard_negative_score_values),
        "regular_rows_count": len(regular_score_values),
        "hard_negative_cap": HARD_NEGATIVE_SCORE_CAP,
        "hard_negative_cap_applied_count": hard_negative_cap_applied_count,
        "hard_negative_above_cap_count": hard_negative_above_cap_count,
        "score_distribution": _score_summary(score_values),
        "regular_score_distribution": _score_summary(regular_score_values),
        "hard_negative_score_distribution": _score_summary(hard_negative_score_values),
        "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
    }
    if report_path is not None:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if markdown_report_path is not None:
        _write_label_report_md(markdown_report_path, report)
    return report


def split_final_labeled_rows(
    rows: Sequence[dict[str, str]],
    *,
    test_size: float = 0.2,
    random_state: int = 42,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, object]]:
    query_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        query = str(row.get("query") or "").strip()
        if query:
            query_rows[query].append(row)
    if len(query_rows) < 2:
        return split_dataset_rows(list(rows), test_size=test_size, random_state=random_state)

    query_categories = {
        query: _majority_value(query_group, "category") or "unknown"
        for query, query_group in query_rows.items()
    }
    queries_by_category: dict[str, list[str]] = defaultdict(list)
    for query, category in query_categories.items():
        queries_by_category[category].append(query)

    rng = random.Random(random_state)
    validation_queries: set[str] = set()
    validation_queries_by_category: dict[str, int] = {}
    for category in sorted(queries_by_category):
        category_queries = sorted(queries_by_category[category])
        shuffled_queries = list(category_queries)
        rng.shuffle(shuffled_queries)
        validation_count = max(1, int(round(len(shuffled_queries) * test_size)))
        if validation_count >= len(shuffled_queries) and len(shuffled_queries) > 1:
            validation_count = len(shuffled_queries) - 1
        selected_validation_queries = set(shuffled_queries[:validation_count])
        validation_queries.update(selected_validation_queries)
        validation_queries_by_category[category] = len(selected_validation_queries)

    if not validation_queries or validation_queries == set(query_rows):
        return split_dataset_rows(list(rows), test_size=test_size, random_state=random_state)

    train_queries = set(query_rows) - validation_queries
    train_rows, validation_rows = _partition_rows_by_queries(list(rows), train_queries, validation_queries)
    return train_rows, validation_rows, {
        "split_mode": "group_by_query_category_stratified",
        "stratify_by": "category",
        "validation_queries_by_category": validation_queries_by_category,
    }


def validate_final_split(
    rows: Sequence[dict[str, str]],
    split: Mapping[str, object],
    *,
    labeled_dataset_path: str | Path = FINAL_LABELED_DATASET_PATH,
    split_path: str | Path = FINAL_SPLIT_PATH,
) -> dict[str, Any]:
    labeled_queries = {str(row.get("query") or "").strip() for row in rows if str(row.get("query") or "").strip()}
    labeled_categories = {str(row.get("category") or "").strip() for row in rows if str(row.get("category") or "").strip()}
    labeled_cities = {str(row.get("city") or "").strip() for row in rows if str(row.get("city") or "").strip()}
    train_queries = {str(query).strip() for query in split.get("train_queries") or [] if str(query).strip()}
    validation_queries = {
        str(query).strip() for query in split.get("validation_queries") or [] if str(query).strip()
    }
    train_rows, validation_rows = _partition_rows_by_queries(list(rows), train_queries, validation_queries)
    train_categories = {
        str(row.get("category") or "").strip() for row in train_rows if str(row.get("category") or "").strip()
    }
    validation_categories = {
        str(row.get("category") or "").strip()
        for row in validation_rows
        if str(row.get("category") or "").strip()
    }
    train_cities = {str(row.get("city") or "").strip() for row in train_rows if str(row.get("city") or "").strip()}
    validation_cities = {
        str(row.get("city") or "").strip() for row in validation_rows if str(row.get("city") or "").strip()
    }
    query_overlap = sorted(train_queries & validation_queries)
    split_queries = train_queries | validation_queries
    uncovered_queries = sorted(labeled_queries - split_queries)
    extra_queries = sorted(split_queries - labeled_queries)
    hard_negative_above_cap_count = sum(
        1 for row in rows if _is_hard_negative(row) and _float(row, "target_score") > HARD_NEGATIVE_SCORE_CAP
    )
    target_score_missing_count = sum(1 for row in rows if str(row.get("target_score") or "").strip() == "")
    label_schema_mismatch_count = sum(
        1 for row in rows if str(row.get("label_schema_version") or "") != FINAL_LABEL_SCHEMA_VERSION
    )
    min_validation_rows = min(MIN_VALIDATION_ROWS, max(1, int(len(rows) * 0.2)))
    checks = {
        "split_exists": bool(split),
        "split_mode_grouped": str(split.get("split_mode") or "").startswith("group_by_query"),
        "query_overlap_absent": not query_overlap,
        "all_labeled_queries_covered": not uncovered_queries,
        "no_extra_split_queries": not extra_queries,
        "train_rows_present": bool(train_rows),
        "validation_rows_present": len(validation_rows) >= min_validation_rows,
        "validation_queries_present": bool(validation_queries),
        "categories_present_in_train": labeled_categories <= train_categories,
        "categories_present_in_validation": labeled_categories <= validation_categories,
        "cities_present_in_train": labeled_cities <= train_cities,
        "cities_present_in_validation": labeled_cities <= validation_cities,
        "hard_negatives_in_train": any(_is_hard_negative(row) for row in train_rows),
        "hard_negatives_in_validation": any(_is_hard_negative(row) for row in validation_rows),
        "hard_negative_cap_respected": hard_negative_above_cap_count == 0,
        "target_scores_present": target_score_missing_count == 0,
        "label_schema_consistent": label_schema_mismatch_count == 0,
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    return {
        "task": "D78",
        "generated_at": datetime.now(UTC).isoformat(),
        "passed": not failed_checks,
        "checks": checks,
        "failed_checks": failed_checks,
        "labeled_dataset_path": str(Path(labeled_dataset_path)),
        "split_path": str(Path(split_path)),
        "split_mode": str(split.get("split_mode") or ""),
        "rows_count": len(rows),
        "labeled_queries_count": len(labeled_queries),
        "train_queries_count": len(train_queries),
        "validation_queries_count": len(validation_queries),
        "query_overlap_count": len(query_overlap),
        "query_overlap": query_overlap,
        "uncovered_labeled_queries_count": len(uncovered_queries),
        "uncovered_labeled_queries": uncovered_queries,
        "extra_split_queries_count": len(extra_queries),
        "extra_split_queries": extra_queries,
        "categories_count": len(labeled_categories),
        "train_missing_categories": sorted(labeled_categories - train_categories),
        "validation_missing_categories": sorted(labeled_categories - validation_categories),
        "cities_count": len(labeled_cities),
        "train_missing_cities": sorted(labeled_cities - train_cities),
        "validation_missing_cities": sorted(labeled_cities - validation_cities),
        "target_score_missing_count": target_score_missing_count,
        "label_schema_mismatch_count": label_schema_mismatch_count,
        "hard_negative_cap": HARD_NEGATIVE_SCORE_CAP,
        "hard_negative_above_cap_count": hard_negative_above_cap_count,
        "min_validation_rows": min_validation_rows,
        "train_partition": _split_partition_stats(train_rows),
        "validation_partition": _split_partition_stats(validation_rows),
    }


def materialize_final_split(
    *,
    labeled_dataset_path: str | Path = FINAL_LABELED_DATASET_PATH,
    output_split_path: str | Path = FINAL_SPLIT_PATH,
    output_validation_path: str | Path = FINAL_SPLIT_VALIDATION_JSON_PATH,
    output_markdown_path: str | Path = FINAL_SPLIT_VALIDATION_MD_PATH,
    manifest_path: str | Path = FINAL_MANIFEST_PATH,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict[str, Any]:
    rows = load_dataset_rows(labeled_dataset_path)
    if not rows:
        raise ValueError("D78 requires a non-empty labeled dataset.")
    train_rows, validation_rows, split_metadata = split_final_labeled_rows(
        rows,
        test_size=test_size,
        random_state=random_state,
    )
    split = save_dataset_split_manifest(
        train_rows,
        validation_rows,
        dataset_path=labeled_dataset_path,
        dataset_version=FINAL_DATASET_VERSION,
        test_size=test_size,
        random_state=random_state,
        split_metadata=split_metadata,
        output_path=output_split_path,
    )
    validation = validate_final_split(
        rows,
        split,
        labeled_dataset_path=labeled_dataset_path,
        split_path=output_split_path,
    )
    report = {
        "task": "D78",
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": FINAL_DATASET_VERSION,
        "split": split,
        "validation": validation,
        "manifest_path": str(Path(manifest_path)),
        "model_artifact_changed": False,
    }
    _write_json(output_validation_path, report)
    _write_split_validation_markdown(output_markdown_path, report)

    manifest = _read_manifest(manifest_path)
    manifest["status"] = "split_validated" if validation["passed"] else "split_validation_failed"
    manifest["ready_for_training"] = bool(validation["passed"])
    manifest["reason"] = (
        "Final labels and leakage-safe split validation completed. Dataset is ready for D79 training."
        if validation["passed"]
        else "D78 split validation failed; fix split evidence before training."
    )
    manifest["split_progress"] = {
        "task": "D78",
        "completed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "split_path": str(Path(output_split_path).resolve()),
        "split_validation_report_path": str(Path(output_validation_path).resolve()),
        "split_validation_markdown_path": str(Path(output_markdown_path).resolve()),
        "split_mode": validation["split_mode"],
        "passed": validation["passed"],
        "failed_checks": validation["failed_checks"],
        "train_rows_count": validation["train_partition"]["rows_count"],
        "validation_rows_count": validation["validation_partition"]["rows_count"],
        "train_queries_count": validation["train_queries_count"],
        "validation_queries_count": validation["validation_queries_count"],
        "query_overlap_count": validation["query_overlap_count"],
        "categories_count": validation["categories_count"],
        "validation_categories_count": validation["validation_partition"]["categories_count"],
        "cities_count": validation["cities_count"],
        "validation_cities_count": validation["validation_partition"]["cities_count"],
        "hard_negative_cap": validation["hard_negative_cap"],
        "hard_negative_above_cap_count": validation["hard_negative_above_cap_count"],
        "notes": "D78 creates split evidence only. No model was trained or published.",
    }
    manifest["quality_gates"] = {
        "ready_for_training": bool(validation["passed"]),
        "unmet_requirements": list(validation["failed_checks"]),
        "split_validation_passed": bool(validation["passed"]),
        "query_overlap_count": validation["query_overlap_count"],
        "hard_negative_above_cap_count": validation["hard_negative_above_cap_count"],
        "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
    }
    _write_json(manifest_path, manifest)
    return {
        **report,
        "split_path": str(Path(output_split_path)),
        "split_validation_path": str(Path(output_validation_path)),
        "split_validation_markdown_path": str(Path(output_markdown_path)),
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
    report_json_path: str | Path = D79_REPORT_JSON_PATH,
    report_md_path: str | Path = D79_REPORT_MD_PATH,
    random_state: int = 42,
    test_size: float = 0.2,
    relabel: bool = False,
) -> dict[str, Any]:
    validation = validate_final_dataset(dataset_path=dataset_path)
    if not validation["passed"]:
        raise ValueError(f"dataset-v7-final is not ready for training: {validation['failed_checks']}")
    resolved_training_dataset_path = Path(training_dataset_path)
    if not resolved_training_dataset_path.exists():
        resolved_training_dataset_path = Path(dataset_path)
    if relabel or not Path(labeled_dataset_path).exists():
        label_report = apply_final_labels(dataset_path=resolved_training_dataset_path, output_path=labeled_dataset_path)
    else:
        label_report = _load_json(FINAL_LABEL_REPORT_JSON_PATH)
    rows = load_dataset_rows(labeled_dataset_path)
    existing_split = _load_json(split_output_path)
    if existing_split:
        train_queries = {
            str(query).strip() for query in existing_split.get("train_queries") or [] if str(query).strip()
        }
        validation_queries = {
            str(query).strip() for query in existing_split.get("validation_queries") or [] if str(query).strip()
        }
        split_validation = validate_final_split(
            rows,
            existing_split,
            labeled_dataset_path=labeled_dataset_path,
            split_path=split_output_path,
        )
        if not split_validation["passed"]:
            raise ValueError(f"Existing D78 split is not valid for training: {split_validation['failed_checks']}")
        train_rows, validation_rows = _partition_rows_by_queries(rows, train_queries, validation_queries)
        split = {**existing_split, "split_path": str(Path(split_output_path))}
    else:
        train_rows, validation_rows, split_metadata = split_final_labeled_rows(
            rows,
            test_size=test_size,
            random_state=random_state,
        )
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
        raise RuntimeError("Final D79 candidate must be CatBoostRegressor; CatBoost candidate was not produced.")
    selected = catboost_candidates[0]
    feature_importance_summary = build_feature_importance_summary(
        selected["model"],
        feature_schema.feature_columns,
        top_n=15,
    )
    generated_at = datetime.now(UTC).isoformat()
    metadata = {
        "source": "local_dataset",
        "model_type": _candidate_name(selected),
        "dataset_version": FINAL_DATASET_VERSION,
        "artifact_version": FINAL_ARTIFACT_VERSION,
        "artifact_family": "page_quality_model.dataset-v7-final",
        "candidate_name": "final_query_competitiveness_catboost_v7",
        "candidate_family": "query_competitiveness",
        "training_task": "D79",
        "trained_at": generated_at,
        "model_schema_version": MODEL_SCHEMA_VERSION_V3,
        "feature_columns": list(feature_schema.feature_columns),
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
        "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
        "split_path": str(Path(split_output_path)),
        "split_mode": str(split.get("split_mode") or "unknown"),
        "feature_importance_summary": feature_importance_summary,
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
            "labeled_dataset_path": str(Path(labeled_dataset_path)),
        },
    }
    metrics = {
        **selected["metrics"],
        "train_rows": float(len(train_rows)),
        "validation_rows": float(len(validation_rows)),
        "split_mode": str(split.get("split_mode") or "unknown"),
    }
    saved_path = save_model(
        model=selected["model"],
        metrics=metrics,
        model_path=candidate_model_path,
        metadata=metadata,
    )
    sidecar_path = Path(f"{saved_path}.metadata.json")
    candidate_sha1 = sha1_file(Path(saved_path))
    sidecar_path.write_text(
        json.dumps(
            {
                **metadata,
                "metrics": metrics,
                "model_path": str(saved_path),
                "candidate_sha1": candidate_sha1,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    report = {
        "task": "D79",
        "generated_at": generated_at,
        "dataset_version": FINAL_DATASET_VERSION,
        "artifact_version": FINAL_ARTIFACT_VERSION,
        "candidate_model_path": str(saved_path),
        "candidate_metadata_path": str(sidecar_path),
        "candidate_sha1": candidate_sha1,
        "selected_candidate": _candidate_name(selected),
        "candidate_name": "final_query_competitiveness_catboost_v7",
        "metrics": metrics,
        "candidates": [
            {
                "model_type": str(candidate.get("model_type") or "unknown"),
                "metrics": candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
                "selected": candidate is selected,
            }
            for candidate in candidates
        ],
        "benchmark": benchmark,
        "label_report": label_report,
        "split": split,
        "validation": validation,
        "feature_importance_summary": feature_importance_summary,
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
        "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
        "model_schema_version": MODEL_SCHEMA_VERSION_V3,
        "feature_count": len(feature_schema.feature_columns),
        "runtime_enabled": False,
        "production_artifact_changed": False,
        "production_artifact_sha1": sha1_file(Path(DEFAULT_MODEL_PATH)),
    }
    _write_json(report_json_path, report)
    _write_training_report_markdown(report_md_path, report)

    manifest = _read_manifest(FINAL_MANIFEST_PATH)
    manifest["status"] = "candidate_trained"
    manifest["ready_for_training"] = True
    manifest["reason"] = "D79 non-production candidate trained. Controlled decision/publish is still required before runtime changes."
    manifest["training_progress"] = {
        "task": "D79",
        "completed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "candidate_model_path": str(Path(saved_path).resolve()),
        "candidate_metadata_path": str(sidecar_path.resolve()),
        "candidate_sha1": candidate_sha1,
        "report_path": str(Path(report_json_path).resolve()),
        "markdown_report_path": str(Path(report_md_path).resolve()),
        "selected_candidate": report["candidate_name"],
        "model_type": _candidate_name(selected),
        "model_schema_version": MODEL_SCHEMA_VERSION_V3,
        "feature_count": len(feature_schema.feature_columns),
        "metrics": metrics,
        "runtime_enabled": False,
        "production_artifact_changed": False,
        "notes": "D79 trains a non-production candidate only. D80 must benchmark/decide before any publish.",
    }
    quality_gates = manifest.get("quality_gates") if isinstance(manifest.get("quality_gates"), dict) else {}
    manifest["quality_gates"] = {
        **quality_gates,
        "ready_for_training": True,
        "candidate_training_completed": True,
        "candidate_runtime_enabled": False,
    }
    _write_json(FINAL_MANIFEST_PATH, manifest)
    return report


def train_query_core_hardened_candidate(
    *,
    labeled_dataset_path: str | Path = FINAL_LABELED_DATASET_PATH,
    query_core_dataset_path: str | Path = D82_QUERY_CORE_DATASET_PATH,
    candidate_model_path: str | Path = D82_MODEL_PATH,
    split_path: str | Path = FINAL_SPLIT_PATH,
    report_json_path: str | Path = D82_REPORT_JSON_PATH,
    report_md_path: str | Path = D82_REPORT_MD_PATH,
    force_materialize: bool = False,
    random_state: int = 42,
) -> dict[str, Any]:
    try:
        from catboost import CatBoostError, CatBoostRegressor
    except ImportError as error:
        raise RuntimeError("CatBoost is required for D82 query-core candidate training.") from error

    if force_materialize or not Path(query_core_dataset_path).exists():
        materialization = materialize_query_core_dataset(
            labeled_dataset_path=labeled_dataset_path,
            output_path=query_core_dataset_path,
        )
    else:
        materialization = {
            "task": "D82",
            "dataset_path": str(Path(labeled_dataset_path)),
            "output_path": str(Path(query_core_dataset_path)),
            "reused_existing_output": True,
        }

    rows = load_dataset_rows(query_core_dataset_path)
    train_rows, validation_rows, split_metadata, split_validation = _rows_from_materialized_split(
        rows,
        split_path=split_path,
    )
    feature_schema = get_model_feature_schema(MODEL_SCHEMA_VERSION_V4)
    training_rows: list[dict[str, str]] = []
    sample_weights: list[float] = []
    hard_negative_train_rows = 0
    hard_negative_training_cap_applications = 0
    for row in train_rows:
        training_row = dict(row)
        if _truthy(row.get("hard_negative")):
            hard_negative_train_rows += 1
            sample_weights.append(D82_HARD_NEGATIVE_SAMPLE_WEIGHT)
            current_target = _float(row, "target_score")
            capped_target = min(current_target, D82_HARD_NEGATIVE_TRAINING_CAP)
            if capped_target < current_target:
                hard_negative_training_cap_applications += 1
            training_row["target_score"] = str(round(capped_target, 4))
        else:
            sample_weights.append(1.0)
        training_rows.append(training_row)

    x_train, y_train = rows_to_matrix(training_rows, feature_columns=feature_schema.feature_columns)
    base_model = CatBoostRegressor(
        loss_function="RMSE",
        depth=6,
        learning_rate=0.05,
        iterations=700,
        l2_leaf_reg=8,
        random_seed=random_state,
        verbose=False,
    )
    try:
        base_model.fit(x_train, y_train, sample_weight=sample_weights)
    except CatBoostError as error:
        raise RuntimeError(f"D82 query-core CatBoost training failed: {error}") from error

    guarded_model = QueryCoreGuardrailRegressor(
        base_model,
        feature_schema.feature_columns,
        cap=HARD_NEGATIVE_SCORE_CAP,
        core_coverage_threshold=D82_QUERY_CORE_COVERAGE_THRESHOLD,
        semantic_similarity_threshold=D82_SEMANTIC_SIMILARITY_THRESHOLD,
    )
    base_predictions = _predict_rows(base_model, validation_rows, feature_schema.feature_columns)
    guarded_predictions = _predict_rows(guarded_model, validation_rows, feature_schema.feature_columns)
    runtime_predictions = _runtime_adjusted_predictions(validation_rows, guarded_predictions)
    base_metrics = _evaluate_predictions(validation_rows, base_predictions)
    metrics = _evaluate_predictions(validation_rows, guarded_predictions)
    runtime_metrics = _evaluate_predictions(validation_rows, runtime_predictions)
    feature_importance_summary = build_feature_importance_summary(
        base_model,
        feature_schema.feature_columns,
        top_n=20,
    )
    generated_at = datetime.now(UTC).isoformat()
    metadata = {
        "source": "local_dataset",
        "model_type": "QueryCoreGuardrailCatBoostRegressor",
        "dataset_version": FINAL_DATASET_VERSION,
        "artifact_version": D82_ARTIFACT_VERSION,
        "artifact_family": "page_quality_model.dataset-v7-final-query-core",
        "candidate_name": "final_query_competitiveness_query_core_catboost_v7",
        "candidate_family": "query_competitiveness",
        "training_task": "D82",
        "trained_at": generated_at,
        "model_schema_version": MODEL_SCHEMA_VERSION_V4,
        "feature_columns": list(feature_schema.feature_columns),
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
        "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
        "split_path": str(Path(split_path)),
        "split_mode": str(split_metadata.get("split_mode") or "unknown"),
        "feature_importance_summary": feature_importance_summary,
        "query_core_guardrail": {
            "cap": HARD_NEGATIVE_SCORE_CAP,
            "core_coverage_threshold": D82_QUERY_CORE_COVERAGE_THRESHOLD,
            "semantic_similarity_threshold": D82_SEMANTIC_SIMILARITY_THRESHOLD,
        },
        "training_adjustments": {
            "hard_negative_training_cap": D82_HARD_NEGATIVE_TRAINING_CAP,
            "hard_negative_sample_weight": D82_HARD_NEGATIVE_SAMPLE_WEIGHT,
            "hard_negative_train_rows": hard_negative_train_rows,
            "hard_negative_training_cap_applications": hard_negative_training_cap_applications,
        },
        "non_production": True,
        "runtime_enabled": False,
        "dataset_metadata": {
            "dataset_version": FINAL_DATASET_VERSION,
            "rows_count": len(rows),
            "queries_count": len({str(row.get("query") or "") for row in rows}),
            "domains_count": len({str(row.get("domain") or "") for row in rows}),
            "categories_count": len({str(row.get("category") or "") for row in rows}),
            "cities_count": len({str(row.get("city") or "").strip() for row in rows if str(row.get("city") or "").strip()}),
            "manifest_generated_at": _read_manifest().get("generated_at"),
            "source_dataset_path": str(Path(labeled_dataset_path)),
            "query_core_dataset_path": str(Path(query_core_dataset_path)),
        },
    }
    saved_path = save_model(
        model=guarded_model,
        metrics=runtime_metrics,
        model_path=candidate_model_path,
        metadata=metadata,
    )
    sidecar_path = Path(f"{saved_path}.metadata.json")
    candidate_sha1 = sha1_file(Path(saved_path))
    sidecar_path.write_text(
        json.dumps(
            {
                **metadata,
                "metrics": runtime_metrics,
                "raw_metrics": metrics,
                "base_model_metrics": base_metrics,
                "model_path": str(saved_path),
                "candidate_sha1": candidate_sha1,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    report = {
        "task": "D82",
        "generated_at": generated_at,
        "dataset_version": FINAL_DATASET_VERSION,
        "artifact_version": D82_ARTIFACT_VERSION,
        "candidate_model_path": str(saved_path),
        "candidate_metadata_path": str(sidecar_path),
        "candidate_sha1": candidate_sha1,
        "candidate_name": "final_query_competitiveness_query_core_catboost_v7",
        "model_type": "QueryCoreGuardrailCatBoostRegressor",
        "model_schema_version": MODEL_SCHEMA_VERSION_V4,
        "feature_count": len(feature_schema.feature_columns),
        "metrics": runtime_metrics,
        "raw_metrics": metrics,
        "base_model_metrics": base_metrics,
        "materialization": materialization,
        "split": split_metadata,
        "split_validation": split_validation,
        "feature_importance_summary": feature_importance_summary,
        "query_core_guardrail": metadata["query_core_guardrail"],
        "training_adjustments": metadata["training_adjustments"],
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
        "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
        "runtime_enabled": False,
        "production_artifact_changed": False,
        "production_artifact_sha1": sha1_file(Path(DEFAULT_MODEL_PATH)),
    }
    _write_json(report_json_path, report)
    Path(report_md_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_md_path).write_text(
        "\n".join(
            [
                "# D82 Query-Core Hard Negative Hardening",
                "",
                f"- Candidate: `{saved_path}`",
                f"- Candidate SHA1: `{candidate_sha1}`",
                f"- Schema: `{MODEL_SCHEMA_VERSION_V4}` / `{len(feature_schema.feature_columns)}` features",
                f"- Runtime-adjusted MAE: `{runtime_metrics.get('mae')}`",
                f"- Runtime-adjusted Spearman: `{runtime_metrics.get('spearman_mean')}`",
                f"- Runtime-adjusted NDCG@10: `{runtime_metrics.get('ndcg_at_10')}`",
                f"- Base MAE before query-core guardrail: `{base_metrics.get('mae')}`",
                f"- Hard negative training cap: `{D82_HARD_NEGATIVE_TRAINING_CAP}`",
                f"- Hard negative sample weight: `{D82_HARD_NEGATIVE_SAMPLE_WEIGHT}`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    manifest = _read_manifest(FINAL_MANIFEST_PATH)
    manifest["status"] = "query_core_candidate_trained"
    manifest["training_progress"] = {
        **(manifest.get("training_progress") if isinstance(manifest.get("training_progress"), dict) else {}),
        "d82": {
            "completed_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "candidate_model_path": str(Path(saved_path).resolve()),
            "candidate_metadata_path": str(sidecar_path.resolve()),
            "candidate_sha1": candidate_sha1,
            "report_path": str(Path(report_json_path).resolve()),
            "markdown_report_path": str(Path(report_md_path).resolve()),
            "selected_candidate": report["candidate_name"],
            "model_type": report["model_type"],
            "model_schema_version": MODEL_SCHEMA_VERSION_V4,
            "feature_count": len(feature_schema.feature_columns),
            "metrics": runtime_metrics,
            "runtime_enabled": False,
            "production_artifact_changed": False,
            "notes": "D82 hardens D79/D80 by adding query-core features and a conservative raw-score cap for missing query core.",
        },
    }
    _write_json(FINAL_MANIFEST_PATH, manifest)
    return report


def _predict_rows(model: Any, rows: Sequence[Mapping[str, str]], feature_columns: Sequence[str]) -> list[float]:
    matrix = [[float(row.get(feature, 0.0) or 0.0) for feature in feature_columns] for row in rows]
    return [_round_score(float(value)) for value in model.predict(matrix)]


def _evaluate_predictions(rows: Sequence[Mapping[str, str]], predictions: Sequence[float]) -> dict[str, float]:
    targets = [_float(row, "target_score") for row in rows]
    if not targets:
        return {
            "rmse": 0.0,
            "mae": 0.0,
            "spearman_mean": 0.0,
            "ndcg_at_10": 0.0,
            "top_3_hit_rate": 0.0,
            "validation_queries": 0.0,
        }
    errors = [float(prediction) - target for target, prediction in zip(targets, predictions, strict=False)]
    rmse = (sum(error * error for error in errors) / len(errors)) ** 0.5
    mae = sum(abs(error) for error in errors) / len(errors)
    metrics = {"rmse": round(rmse, 6), "mae": round(mae, 6)}
    metrics.update(ranking_metrics([dict(row) for row in rows], [float(value) for value in predictions]))
    return metrics


def _runtime_adjusted_predictions(rows: Sequence[Mapping[str, str]], predictions: Sequence[float]) -> list[float]:
    adjusted: list[float] = []
    for row, prediction in zip(rows, predictions, strict=False):
        guardrail = build_query_relevance_guardrail(_numeric_mapping(row), float(prediction))
        adjusted.append(float(guardrail["adjusted_score"]))
    return adjusted


def _prediction_summary(values: Sequence[float]) -> dict[str, float]:
    return _score_summary([float(value) for value in values])


def _rows_from_materialized_split(
    rows: Sequence[dict[str, str]],
    split_path: str | Path = FINAL_SPLIT_PATH,
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    split = _load_json(split_path)
    validation = validate_final_split(rows, split, split_path=split_path)
    if not validation["passed"]:
        failed = ", ".join(str(item) for item in validation["failed_checks"])
        raise ValueError(f"Final split validation failed before D80 decision: {failed}")
    train_queries = {str(query).strip() for query in split.get("train_queries") or [] if str(query).strip()}
    validation_queries = {
        str(query).strip() for query in split.get("validation_queries") or [] if str(query).strip()
    }
    train_rows, validation_rows = _partition_rows_by_queries(list(rows), train_queries, validation_queries)
    return train_rows, validation_rows, split, validation


def _query_has_commercial_modifier(query: object) -> bool:
    normalized = str(query or "").lower()
    return any(term in normalized for term in ("купить", "цена", "стоимость", "заказать"))


def _sample_prediction_rows(
    rows: Sequence[Mapping[str, str]],
    raw_predictions: Sequence[float],
    runtime_predictions: Sequence[float],
    *,
    predicate: Any,
    limit: int = 8,
) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    for row, raw_prediction, runtime_prediction in zip(rows, raw_predictions, runtime_predictions, strict=False):
        if not predicate(row, raw_prediction, runtime_prediction):
            continue
        samples.append(
            {
                "query": row.get("query"),
                "domain": row.get("domain"),
                "url": row.get("url"),
                "target_score": _float(row, "target_score"),
                "competitiveness_base_score": _float(row, "competitiveness_base_score"),
                "query_relevance_band": row.get("query_relevance_band"),
                "hard_negative": _truthy(row.get("hard_negative")),
                "hard_negative_source_query": row.get("hard_negative_source_query"),
                "hard_negative_source_category": row.get("hard_negative_source_category"),
                "raw_prediction": round(float(raw_prediction), 4),
                "runtime_prediction": round(float(runtime_prediction), 4),
                "semantic_similarity": _float(row, "semantic_similarity"),
                "keyword_coverage_ratio": _float(row, "keyword_coverage_ratio"),
                "query_density": _float(row, "query_density"),
                "query_prominence_score": _float(row, "query_prominence_score"),
            }
        )
        if len(samples) >= limit:
            break
    return samples


def final_product_guardrails(
    candidate_path: str | Path,
    validation_rows: Sequence[Mapping[str, str]],
    *,
    split_validation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    artifact = load_model_artifact(candidate_path)
    if artifact is None:
        raise FileNotFoundError(f"Candidate artifact not found: {candidate_path}")
    feature_columns = artifact["feature_columns"]
    predictions = _predict_rows(artifact["model"], validation_rows, feature_columns)  # type: ignore[arg-type]
    runtime_predictions = _runtime_adjusted_predictions(validation_rows, predictions)
    rows_with_predictions = list(zip(validation_rows, predictions, runtime_predictions, strict=False))
    mismatch_rows = [
        (row, prediction, runtime_prediction)
        for row, prediction, runtime_prediction in rows_with_predictions
        if float(row.get("query_relevance_multiplier") or 1.0) <= 0.15
    ]
    strong_rows = [
        (row, prediction, runtime_prediction)
        for row, prediction, runtime_prediction in rows_with_predictions
        if str(row.get("query_relevance_band") or "") == "strong_match"
    ]
    full_mismatch_rows = [
        (row, prediction, runtime_prediction)
        for row, prediction, runtime_prediction in rows_with_predictions
        if str(row.get("query_relevance_band") or "") == "full_mismatch"
    ]
    probable_mismatch_rows = [
        (row, prediction, runtime_prediction)
        for row, prediction, runtime_prediction in rows_with_predictions
        if str(row.get("query_relevance_band") or "") == "probable_mismatch"
    ]
    weak_match_rows = [
        (row, prediction, runtime_prediction)
        for row, prediction, runtime_prediction in rows_with_predictions
        if str(row.get("query_relevance_band") or "") == "weak_match"
    ]
    partial_match_rows = [
        (row, prediction, runtime_prediction)
        for row, prediction, runtime_prediction in rows_with_predictions
        if str(row.get("query_relevance_band") or "") == "partial_match"
    ]
    hard_negative_rows = [
        (row, prediction, runtime_prediction)
        for row, prediction, runtime_prediction in rows_with_predictions
        if _truthy(row.get("hard_negative"))
    ]
    strong_low_base_rows = [
        (row, prediction, runtime_prediction)
        for row, prediction, runtime_prediction in strong_rows
        if _float(row, "competitiveness_base_score", _float(row, "target_score")) <= 55.0
    ]
    noncommercial_strong_rows = [
        (row, prediction, runtime_prediction)
        for row, prediction, runtime_prediction in strong_rows
        if not _query_has_commercial_modifier(row.get("query"))
    ]
    unrelated_above_35 = [runtime_prediction for _row, _prediction, runtime_prediction in mismatch_rows if runtime_prediction > 35.0]
    mismatch_below_20_ratio = (
        sum(1 for _row, _prediction, runtime_prediction in mismatch_rows if runtime_prediction <= 20.0) / len(mismatch_rows)
        if mismatch_rows
        else 1.0
    )
    strong_average_prediction = (
        sum(runtime_prediction for _row, _prediction, runtime_prediction in strong_rows) / len(strong_rows)
        if strong_rows
        else 0.0
    )
    hard_negative_above_cap = [
        prediction for _row, prediction, _runtime_prediction in hard_negative_rows if prediction > HARD_NEGATIVE_SCORE_CAP
    ]
    strong_low_average_prediction = (
        sum(runtime_prediction for _row, _prediction, runtime_prediction in strong_low_base_rows) / len(strong_low_base_rows)
        if strong_low_base_rows
        else 0.0
    )
    strong_low_max_prediction = max((runtime_prediction for _row, _prediction, runtime_prediction in strong_low_base_rows), default=0.0)
    noncommercial_strong_average_prediction = (
        sum(runtime_prediction for _row, _prediction, runtime_prediction in noncommercial_strong_rows)
        / len(noncommercial_strong_rows)
        if noncommercial_strong_rows
        else 0.0
    )
    split_passed = True if split_validation is None else bool(split_validation.get("passed"))
    checks = {
        "candidate_available": True,
        "validation_rows_present": len(validation_rows) >= MIN_VALIDATION_ROWS,
        "materialized_split_valid": split_passed,
        "unrelated_pages_not_above_35": not unrelated_above_35,
        "mismatch_below_20_ratio": mismatch_below_20_ratio >= 0.9,
        "full_mismatch_runtime_cap_5": all(runtime_prediction <= 5.0 for _row, _prediction, runtime_prediction in full_mismatch_rows),
        "probable_mismatch_runtime_cap_25": all(
            runtime_prediction <= 25.0 for _row, _prediction, runtime_prediction in probable_mismatch_rows
        ),
        "weak_match_runtime_cap_55": all(runtime_prediction <= 55.0 for _row, _prediction, runtime_prediction in weak_match_rows),
        "partial_match_runtime_cap_80": all(
            runtime_prediction <= 80.0 for _row, _prediction, runtime_prediction in partial_match_rows
        ),
        "hard_negatives_learned_below_cap": not hard_negative_above_cap,
        "strong_relevance_not_collapsed": strong_average_prediction >= 45.0 if strong_rows else True,
        "strong_relevance_with_weak_seo_not_overrated": (
            strong_low_average_prediction <= 55.0 and strong_low_max_prediction <= 65.0
        )
        if strong_low_base_rows
        else True,
        "noncommercial_relevant_pages_not_cut": noncommercial_strong_average_prediction >= 45.0
        if noncommercial_strong_rows
        else True,
        "score_contract_version_present": artifact.get("artifact_version") == FINAL_ARTIFACT_VERSION
        or artifact.get("dataset_version") == FINAL_DATASET_VERSION,
    }
    failed_checks = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failed_checks,
        "checks": checks,
        "failed_checks": failed_checks,
        "mismatch_rows": len(mismatch_rows),
        "full_mismatch_rows": len(full_mismatch_rows),
        "probable_mismatch_rows": len(probable_mismatch_rows),
        "weak_match_rows": len(weak_match_rows),
        "partial_match_rows": len(partial_match_rows),
        "hard_negative_rows": len(hard_negative_rows),
        "hard_negative_above_cap_count": len(hard_negative_above_cap),
        "hard_negative_max_raw_prediction": round(max((prediction for _row, prediction, _runtime in hard_negative_rows), default=0.0), 6),
        "strong_rows": len(strong_rows),
        "strong_low_base_rows": len(strong_low_base_rows),
        "noncommercial_strong_rows": len(noncommercial_strong_rows),
        "mismatch_below_20_ratio": round(mismatch_below_20_ratio, 6),
        "strong_average_prediction": round(strong_average_prediction, 6),
        "strong_low_average_prediction": round(strong_low_average_prediction, 6),
        "strong_low_max_prediction": round(strong_low_max_prediction, 6),
        "noncommercial_strong_average_prediction": round(noncommercial_strong_average_prediction, 6),
        "max_unrelated_prediction": max(unrelated_above_35, default=None),
        "prediction_summaries": {
            "raw": _prediction_summary(predictions),
            "runtime_adjusted": _prediction_summary(runtime_predictions),
        },
        "failure_samples": {
            "hard_negative_above_cap": _sample_prediction_rows(
                validation_rows,
                predictions,
                runtime_predictions,
                predicate=lambda row, raw, _runtime: _truthy(row.get("hard_negative"))
                and raw > HARD_NEGATIVE_SCORE_CAP,
            ),
            "unrelated_above_35": _sample_prediction_rows(
                validation_rows,
                predictions,
                runtime_predictions,
                predicate=lambda row, _raw, runtime: float(row.get("query_relevance_multiplier") or 1.0) <= 0.15
                and runtime > 35.0,
            ),
        },
    }


def build_final_decision_report(
    *,
    candidate_model_path: str | Path = FINAL_MODEL_PATH,
    reference_model_path: str | Path = DEFAULT_MODEL_PATH,
    labeled_dataset_path: str | Path = FINAL_LABELED_DATASET_PATH,
    split_path: str | Path = FINAL_SPLIT_PATH,
    report_json_path: str | Path = D80_REPORT_JSON_PATH,
    report_md_path: str | Path = D80_REPORT_MD_PATH,
    task: str = "D80",
    candidate_name: str = "final_query_competitiveness_catboost_v7",
    markdown_title: str = "D80 Final Query-Competitiveness Controlled Decision",
    next_step: str = "D81 controlled publish if decision is publish_candidate; otherwise D81 records no-publish evidence.",
) -> dict[str, Any]:
    rows = load_dataset_rows(labeled_dataset_path)
    train_rows, validation_rows, split_metadata, split_validation = _rows_from_materialized_split(rows, split_path=split_path)
    artifact = load_model_artifact(candidate_model_path)
    if artifact is None:
        raise FileNotFoundError(f"Candidate artifact not found: {candidate_model_path}")
    reference_artifact = load_model_artifact(reference_model_path)
    if reference_artifact is None:
        raise FileNotFoundError(f"Reference artifact not found: {reference_model_path}")

    candidate_raw_predictions = _predict_rows(artifact["model"], validation_rows, artifact["feature_columns"])  # type: ignore[arg-type]
    candidate_runtime_predictions = _runtime_adjusted_predictions(validation_rows, candidate_raw_predictions)
    reference_raw_predictions = _predict_rows(reference_artifact["model"], validation_rows, reference_artifact["feature_columns"])  # type: ignore[arg-type]
    reference_runtime_predictions = _runtime_adjusted_predictions(validation_rows, reference_raw_predictions)
    metrics = _evaluate_predictions(validation_rows, candidate_raw_predictions)
    runtime_metrics = _evaluate_predictions(validation_rows, candidate_runtime_predictions)
    reference_metrics = _evaluate_predictions(validation_rows, reference_raw_predictions)
    reference_runtime_metrics = _evaluate_predictions(validation_rows, reference_runtime_predictions)
    guardrails = final_product_guardrails(candidate_model_path, validation_rows, split_validation=split_validation)
    decision = {
        "decision": "publish_candidate" if guardrails["passed"] else "no_publish",
        "publish_action": "controlled_publish_required" if guardrails["passed"] else "no_publish",
        "selected_candidate": candidate_name if guardrails["passed"] else None,
        "reason": "final_product_guardrails_passed" if guardrails["passed"] else "final_product_guardrails_failed",
    }
    report = {
        "task": task,
        "generated_at": datetime.now(UTC).isoformat(),
        "dataset_version": FINAL_DATASET_VERSION,
        "candidate_model_path": str(Path(candidate_model_path)),
        "candidate_sha1": sha1_file(Path(candidate_model_path)),
        "reference_model_path": str(Path(reference_model_path)),
        "reference_sha1": sha1_file(Path(reference_model_path)),
        "metrics": metrics,
        "runtime_adjusted_metrics": runtime_metrics,
        "reference_metrics": reference_metrics,
        "reference_runtime_adjusted_metrics": reference_runtime_metrics,
        "metric_deltas_vs_reference_runtime": {
            "mae": round(runtime_metrics["mae"] - reference_runtime_metrics["mae"], 6),
            "rmse": round(runtime_metrics["rmse"] - reference_runtime_metrics["rmse"], 6),
            "spearman_mean": round(runtime_metrics["spearman_mean"] - reference_runtime_metrics["spearman_mean"], 6),
            "ndcg_at_10": round(runtime_metrics["ndcg_at_10"] - reference_runtime_metrics["ndcg_at_10"], 6),
        },
        "split": split_metadata,
        "split_validation": split_validation,
        "train_rows_count": len(train_rows),
        "validation_rows_count": len(validation_rows),
        "product_guardrails": guardrails,
        "decision": decision,
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
        "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
        "next_step": next_step,
    }
    _write_json(report_json_path, report)
    Path(report_md_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_md_path).write_text(
        "\n".join(
            [
                f"# {markdown_title}",
                "",
                f"- Decision: `{decision['decision']}`",
                f"- Reason: `{decision['reason']}`",
                f"- Candidate: `{candidate_model_path}`",
                f"- Candidate SHA1: `{report['candidate_sha1']}`",
                f"- Reference SHA1: `{report['reference_sha1']}`",
                f"- Split mode: `{split_metadata.get('split_mode')}`",
                f"- Validation rows: `{len(validation_rows)}`",
                f"- Raw MAE: `{metrics.get('mae')}`",
                f"- Runtime-adjusted MAE: `{runtime_metrics.get('mae')}`",
                f"- Runtime-adjusted Spearman: `{runtime_metrics.get('spearman_mean')}`",
                f"- Runtime-adjusted NDCG@10: `{runtime_metrics.get('ndcg_at_10')}`",
                f"- Reference runtime MAE: `{reference_runtime_metrics.get('mae')}`",
                f"- Product guardrails passed: `{guardrails['passed']}`",
                f"- Failed checks: `{', '.join(guardrails['failed_checks']) or 'none'}`",
                f"- Hard negatives above cap: `{guardrails['hard_negative_above_cap_count']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return report


def run_final_controlled_publish(
    *,
    report_json_path: str | Path = D80_REPORT_JSON_PATH,
    release_report_json_path: str | Path = D81_REPORT_JSON_PATH,
    release_report_md_path: str | Path = D81_REPORT_MD_PATH,
    candidate_model_path: str | Path = FINAL_MODEL_PATH,
    production_model_path: str | Path = DEFAULT_MODEL_PATH,
) -> dict[str, Any]:
    if not Path(report_json_path).exists():
        build_final_decision_report(report_json_path=report_json_path)
    report = json.loads(Path(report_json_path).read_text(encoding="utf-8"))
    decision = report.get("decision") if isinstance(report.get("decision"), dict) else {}
    production_path = Path(production_model_path)
    candidate_path = Path(candidate_model_path)
    if not candidate_path.exists():
        raise FileNotFoundError(f"Candidate artifact not found: {candidate_path}")

    before_sha1 = sha1_file(production_path) if production_path.exists() else None
    production_before = build_production_artifact_state(production_path)
    publish_result: dict[str, Any] | None = None
    rollback_reference: dict[str, Any] | None = None
    generated_at = datetime.now(UTC)

    if decision.get("decision") == "publish_candidate":
        candidate_raw = load_saved_model(candidate_path)
        candidate_artifact = load_model_artifact(candidate_path)
        if not isinstance(candidate_raw, dict) or candidate_artifact is None:
            raise ValueError(f"Candidate artifact is not loadable: {candidate_path}")
        if candidate_artifact.get("model_schema_version") != MODEL_SCHEMA_VERSION_V3:
            raise ValueError(
                f"D81 expects schema {MODEL_SCHEMA_VERSION_V3}, got {candidate_artifact.get('model_schema_version')!r}"
            )
        selected_candidate = str(decision.get("selected_candidate") or "")
        if candidate_raw.get("candidate_name") != selected_candidate:
            raise ValueError(
                "Candidate artifact name does not match D80 decision: "
                f"{candidate_raw.get('candidate_name')!r} vs {selected_candidate!r}"
            )

        rollback_reference = ensure_rollback_reference(production_before, model_path=production_path)
        artifact_version = build_primary_artifact_version(FINAL_DATASET_VERSION, generated_at)
        dataset_metadata = candidate_raw.get("dataset_metadata") if isinstance(candidate_raw.get("dataset_metadata"), dict) else {}
        metrics = candidate_raw.get("metrics") if isinstance(candidate_raw.get("metrics"), dict) else {}
        metadata = {
            "artifact_version": artifact_version,
            "artifact_family": production_path.stem,
            "published_at": generated_at.isoformat(),
            "trained_at": candidate_raw.get("trained_at"),
            "source": candidate_raw.get("source", "local_dataset"),
            "model_type": candidate_raw.get("model_type", candidate_artifact.get("model_type")),
            "dataset_version": FINAL_DATASET_VERSION,
            "rows_count": candidate_artifact.get("rows_count"),
            "queries_count": candidate_artifact.get("queries_count"),
            "domains_count": candidate_artifact.get("domains_count"),
            "dataset_metadata": dataset_metadata,
            "model_schema_version": candidate_artifact.get("model_schema_version"),
            "feature_columns": candidate_artifact.get("feature_columns"),
            "candidate_name": candidate_raw.get("candidate_name"),
            "candidate_family": candidate_raw.get("candidate_family"),
            "feature_importance_summary": candidate_raw.get("feature_importance_summary"),
            "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
            "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
            "non_production": False,
            "runtime_enabled": True,
            "publish_decision_required": "completed_d81",
            "d81_publish": {
                "source_candidate_path": str(candidate_path),
                "source_candidate_sha1": sha1_file(candidate_path),
                "d80_report_path": str(Path(report_json_path)),
                "decision": dict(decision),
                "product_guardrails": report.get("product_guardrails"),
                "rollback_reference": dict(rollback_reference),
            },
        }
        save_model(
            model=candidate_raw["model"],
            metrics=metrics,
            model_path=production_path,
            metadata=metadata,
        )
        clear_model_cache()
        published_artifact = load_model_artifact(production_path)
        if published_artifact is None:
            raise RuntimeError(f"Published artifact is not loadable: {production_path}")

        versioned_model_path = build_controlled_versioned_artifact_path(production_path, artifact_version)
        versioned_model_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(production_path, versioned_model_path)
        alias_metadata = {
            **build_artifact_public_metadata(published_artifact, production_path),
            "candidate_name": candidate_raw.get("candidate_name"),
            "candidate_family": candidate_raw.get("candidate_family"),
            "feature_importance_summary": candidate_raw.get("feature_importance_summary"),
            "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
            "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
            "d80_report_path": str(Path(report_json_path)),
            "d80_decision": dict(decision),
            "rollback_reference": dict(rollback_reference),
        }
        alias_metadata_path = write_artifact_public_metadata(
            alias_metadata,
            build_artifact_metadata_path(production_path),
        )
        versioned_metadata_path = write_artifact_public_metadata(
            {**alias_metadata, "artifact_path": str(versioned_model_path)},
            build_artifact_metadata_path(versioned_model_path),
        )
        publish_result = {
            "artifact_version": artifact_version,
            "candidate_model_path": str(candidate_path),
            "candidate_model_sha1": sha1_file(candidate_path),
            "published_model_path": str(production_path),
            "published_model_sha1": sha1_file(production_path),
            "published_metadata_path": str(alias_metadata_path),
            "published_metadata_sha1": sha1_file(alias_metadata_path),
            "versioned_model_path": str(versioned_model_path),
            "versioned_model_sha1": sha1_file(versioned_model_path),
            "versioned_metadata_path": str(versioned_metadata_path),
            "versioned_metadata_sha1": sha1_file(versioned_metadata_path),
        }

    after_sha1 = sha1_file(production_path) if production_path.exists() else None
    production_after = build_production_artifact_state(production_path)
    release_decision = "published" if publish_result else "no_publish"
    release_report = {
        "task": "D81",
        "generated_at": generated_at.isoformat(),
        "decision": release_decision,
        "publish_action": "controlled_publish" if publish_result else "no_publish",
        "source_d80_report": str(Path(report_json_path)),
        "d80_decision": decision,
        "candidate_model_path": str(candidate_path),
        "candidate_sha1": sha1_file(candidate_path),
        "production_model_path": str(production_path),
        "production_sha1_before": before_sha1,
        "production_sha1_after": after_sha1,
        "production_changed": before_sha1 != after_sha1,
        "production_changed_only_for_publish": (before_sha1 != after_sha1) == bool(publish_result),
        "rollback_reference": rollback_reference,
        "publish_result": publish_result,
        "production_before": production_before,
        "production_after": production_after,
        "score_contract_version": FINAL_SCORE_CONTRACT_VERSION,
        "label_schema_version": FINAL_LABEL_SCHEMA_VERSION,
        "reason": decision.get("reason") or "d80_decision",
    }
    _write_json(release_report_json_path, release_report)
    Path(release_report_md_path).parent.mkdir(parents=True, exist_ok=True)
    Path(release_report_md_path).write_text(
        "\n".join(
            [
                "# D81 Final Query-Competitiveness Controlled Release",
                "",
                f"- Decision: `{release_decision}`",
                f"- Publish action: `{release_report['publish_action']}`",
                f"- D80 decision: `{decision.get('decision')}`",
                f"- Reason: `{release_report['reason']}`",
                f"- Candidate SHA1: `{release_report['candidate_sha1']}`",
                f"- Production SHA1 before: `{before_sha1}`",
                f"- Production SHA1 after: `{after_sha1}`",
                f"- Production changed: `{before_sha1 != after_sha1}`",
                f"- Rollback available: `{bool(rollback_reference)}`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    manifest = _read_manifest(FINAL_MANIFEST_PATH)
    manifest["status"] = "runtime_published" if publish_result else "controlled_no_publish"
    manifest["release_progress"] = {
        "task": "D81",
        "completed_at": generated_at.isoformat(timespec="seconds"),
        "decision": release_decision,
        "d80_report_path": str(Path(report_json_path).resolve()),
        "d81_report_path": str(Path(release_report_json_path).resolve()),
        "candidate_sha1": sha1_file(candidate_path),
        "production_sha1_before": before_sha1,
        "production_sha1_after": after_sha1,
        "runtime_enabled": bool(publish_result),
    }
    quality_gates = manifest.get("quality_gates") if isinstance(manifest.get("quality_gates"), dict) else {}
    manifest["quality_gates"] = {
        **quality_gates,
        "candidate_runtime_enabled": bool(publish_result),
        "controlled_release_decision_recorded": True,
        "production_changed_only_for_controlled_publish": (before_sha1 != after_sha1) == bool(publish_result),
    }
    _write_json(FINAL_MANIFEST_PATH, manifest)
    return release_report


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
    parser.add_argument("--split", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--decide", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--harden-query-core", action="store_true")
    parser.add_argument("--force-query-core-materialize", action="store_true")
    parser.add_argument("--dataset", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--label-report", default="")
    parser.add_argument("--label-report-md", default="")
    parser.add_argument("--split-output", default="")
    parser.add_argument("--split-validation", default="")
    parser.add_argument("--split-validation-md", default="")
    parser.add_argument("--split-test-size", type=float, default=0.2)
    parser.add_argument("--split-random-state", type=int, default=42)
    parser.add_argument("--training-report", default="")
    parser.add_argument("--training-report-md", default="")
    parser.add_argument("--candidate-model-output", default="")
    parser.add_argument("--relabel", action="store_true")
    args = parser.parse_args()
    if args.validate:
        print(json.dumps(validate_final_dataset(), ensure_ascii=False, indent=2))
        return
    if args.label:
        label_dataset_path = Path(args.dataset) if args.dataset else (
            FINAL_HARD_NEGATIVE_DATASET_PATH if FINAL_HARD_NEGATIVE_DATASET_PATH.exists() else FINAL_DATASET_PATH
        )
        label_output_path = Path(args.output) if args.output else FINAL_LABELED_DATASET_PATH
        label_report_path = Path(args.label_report) if args.label_report else FINAL_LABEL_REPORT_JSON_PATH
        label_report_md_path = Path(args.label_report_md) if args.label_report_md else FINAL_LABEL_REPORT_MD_PATH
        print(
            json.dumps(
                apply_final_labels(
                    dataset_path=label_dataset_path,
                    output_path=label_output_path,
                    report_path=label_report_path,
                    markdown_report_path=label_report_md_path,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.split:
        print(
            json.dumps(
                materialize_final_split(
                    labeled_dataset_path=Path(args.dataset) if args.dataset else FINAL_LABELED_DATASET_PATH,
                    output_split_path=Path(args.split_output) if args.split_output else FINAL_SPLIT_PATH,
                    output_validation_path=Path(args.split_validation)
                    if args.split_validation
                    else FINAL_SPLIT_VALIDATION_JSON_PATH,
                    output_markdown_path=Path(args.split_validation_md)
                    if args.split_validation_md
                    else FINAL_SPLIT_VALIDATION_MD_PATH,
                    test_size=args.split_test_size,
                    random_state=args.split_random_state,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.train:
        print(
            json.dumps(
                train_final_candidate(
                    candidate_model_path=Path(args.candidate_model_output)
                    if args.candidate_model_output
                    else FINAL_MODEL_PATH,
                    report_json_path=Path(args.training_report) if args.training_report else D79_REPORT_JSON_PATH,
                    report_md_path=Path(args.training_report_md) if args.training_report_md else D79_REPORT_MD_PATH,
                    relabel=bool(args.relabel),
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.harden_query_core:
        training_report = train_query_core_hardened_candidate(
            force_materialize=bool(args.force_query_core_materialize),
        )
        decision_report = build_final_decision_report(
            candidate_model_path=D82_MODEL_PATH,
            labeled_dataset_path=D82_QUERY_CORE_DATASET_PATH,
            report_json_path=D82_DECISION_JSON_PATH,
            report_md_path=D82_DECISION_MD_PATH,
            task="D82",
            candidate_name="final_query_competitiveness_query_core_catboost_v7",
            markdown_title="D82 Query-Core Controlled Decision",
            next_step="Controlled publish can be considered only after D82 evidence review.",
        )
        print(
            json.dumps(
                {
                    "task": "D82",
                    "training": training_report,
                    "decision": decision_report,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.decide:
        print(json.dumps(build_final_decision_report(), ensure_ascii=False, indent=2))
        return
    if args.publish:
        print(json.dumps(run_final_controlled_publish(), ensure_ascii=False, indent=2))
        return
    print(json.dumps(run_final_pipeline(publish=args.publish), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
