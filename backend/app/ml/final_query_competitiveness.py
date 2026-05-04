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
FINAL_LABEL_REPORT_JSON_PATH = FINAL_DATASET_DIR / "d77-final-label-report.json"
FINAL_LABEL_REPORT_MD_PATH = FINAL_DATASET_DIR / "d77-final-label-report.md"
FINAL_MANIFEST_PATH = FINAL_DATASET_DIR / "manifest.json"
FINAL_SPLIT_PATH = FINAL_DATASET_DIR / "split.json"
FINAL_SPLIT_VALIDATION_JSON_PATH = FINAL_DATASET_DIR / "d78-split-validation-report.json"
FINAL_SPLIT_VALIDATION_MD_PATH = FINAL_DATASET_DIR / "d78-split-validation-report.md"
FINAL_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "ranking-benchmarks" / FINAL_DATASET_VERSION
FINAL_REPORT_JSON_PATH = FINAL_OUTPUT_DIR / "final-query-competitiveness-report.json"
FINAL_REPORT_MD_PATH = FINAL_OUTPUT_DIR / "final-query-competitiveness-report.md"
VERSIONED_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "versions"

DOMAIN_CAP_PER_DOMAIN = 12
MIN_FINAL_QUERIES = 500
MIN_FINAL_CATEGORIES = 50
MIN_FINAL_CITIES = 5
MIN_VALIDATION_ROWS = 40
HARD_NEGATIVE_SCORE_CAP = 35.0


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
        raise RuntimeError("Final D65 candidate must be CatBoostRegressor; CatBoost candidate was not produced.")
    selected = catboost_candidates[0]
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
            "split_mode": str(split.get("split_mode") or "unknown"),
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
    parser.add_argument("--split", action="store_true")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--decide", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--dataset", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--label-report", default="")
    parser.add_argument("--label-report-md", default="")
    parser.add_argument("--split-output", default="")
    parser.add_argument("--split-validation", default="")
    parser.add_argument("--split-validation-md", default="")
    parser.add_argument("--split-test-size", type=float, default=0.2)
    parser.add_argument("--split-random-state", type=int, default=42)
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
        print(json.dumps(train_final_candidate(), ensure_ascii=False, indent=2))
        return
    if args.decide:
        print(json.dumps(build_final_decision_report(), ensure_ascii=False, indent=2))
        return
    print(json.dumps(run_final_pipeline(publish=args.publish), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
