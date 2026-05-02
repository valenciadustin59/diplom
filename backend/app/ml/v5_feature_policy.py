from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha1
import json
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

from app.ml.model import DEFAULT_MODEL_PATH, load_model_artifact, predict_score
from app.ml.model_schema import MODEL_SCHEMA_VERSION_V3, get_model_feature_schema
from app.ml.publish import ARTIFACTS_DIR
from app.ml.seo_weighted_candidate_training import DEFAULT_D47_REPORT_JSON_PATH
from app.ml.train import load_dataset_rows
from app.ml.v3_dataset import DATASET_VERSIONS_DIR


FEATURE_POLICY_VERSION_V5 = "v5-shortcut-control-v1"
DEFAULT_DATASET_VERSION = "dataset-v5"
DEFAULT_SOURCE_DATASET_DIR = DATASET_VERSIONS_DIR / DEFAULT_DATASET_VERSION
DEFAULT_SOURCE_DATASET_PATH = DEFAULT_SOURCE_DATASET_DIR / "dataset.csv"
DEFAULT_SOURCE_SPLIT_PATH = DEFAULT_SOURCE_DATASET_DIR / "split.json"
DEFAULT_CONTROLLED_DATASET_PATH = DEFAULT_SOURCE_DATASET_DIR / "dataset.controlled.csv"
DEFAULT_FEATURE_POLICY_PATH = DEFAULT_SOURCE_DATASET_DIR / "feature_policy.json"
DEFAULT_D52_OUTPUT_DIR = ARTIFACTS_DIR / "ranking-benchmarks" / "dataset-v5-d52"
DEFAULT_D52_REPORT_JSON_PATH = DEFAULT_D52_OUTPUT_DIR / "shortcut-feature-control-report.json"
DEFAULT_D52_REPORT_MD_PATH = DEFAULT_D52_OUTPUT_DIR / "shortcut-feature-control-report.md"

CRITICAL_FEATURES = frozenset(
    {
        "http_status_ok",
        "page_indexable",
        "robots_noindex",
        "robots_nofollow",
        "canonical_present",
        "canonical_matches_final_url",
        "canonical_signal_score",
        "title_present",
        "query_in_title",
        "title_keyword_coverage_ratio",
        "query_terms_in_headings",
        "heading_query_coverage_ratio",
        "semantic_similarity",
        "query_semantic_alignment",
        "title_semantic_alignment",
        "heading_semantic_alignment",
        "title_heading_keyword_alignment",
        "keyword_coverage_ratio",
        "keyword_balance_score",
        "query_prominence_score",
        "intent_alignment_score",
        "commercial_intent_alignment",
        "local_intent_alignment",
        "informational_intent_alignment",
        "navigational_intent_alignment",
    }
)
IMPORTANT_FEATURES = frozenset(
    {
        "technical_seo_score",
        "technical_metadata_score",
        "redirect_efficiency_score",
        "url_hygiene_score",
        "meta_description_present",
        "meta_length_quality",
        "mobile_readiness_score",
        "rendering_score",
        "performance_proxy_score",
        "heavy_analysis_overall_score",
        "structured_data_score",
        "commercial_signals_score",
        "trust_signals_score",
        "commercial_trust_score",
        "contact_options_score",
        "company_identity_present",
        "legal_requisites_present",
        "phone_present",
        "email_present",
        "address_present",
        "business_hours_present",
        "cta_present",
        "cta_count",
        "cta_semantic_score",
        "value_proposition_present",
        "form_count",
        "input_count",
        "inputs_per_form_ratio",
    }
)
SUPPORTING_FEATURES = frozenset(
    {
        "text_length_chars",
        "html_length_chars",
        "word_count",
        "unique_word_count",
        "sentence_count",
        "paragraph_count",
        "avg_sentence_length",
        "avg_paragraph_length",
        "h1_count",
        "h2_count",
        "h3_count",
        "heading_count",
        "link_count",
        "image_count",
        "list_item_count",
        "strong_tag_count",
        "link_density_per_1000_words",
        "image_density_per_1000_words",
        "list_density_per_1000_words",
        "strong_density_per_1000_words",
        "content_link_ratio",
        "content_depth_semantic_score",
        "semantic_content_richness",
        "price_present",
        "currency_present",
        "delivery_info_present",
        "payment_info_present",
        "warranty_info_present",
        "returns_info_present",
        "reviews_present",
        "rating_present",
        "messenger_present",
        "faq_present",
        "structured_data_valid_json_ld_count",
        "structured_data_breadcrumb_schema_present",
        "structured_data_faq_schema_present",
    }
)

CRITICAL_KEYWORDS = (
    "index",
    "canonical",
    "robots",
    "http_status",
    "title",
    "semantic",
    "intent",
    "keyword",
    "query_prominence",
)
SUPPORTING_KEYWORDS = (
    "word_count",
    "text_length",
    "html_length",
    "sentence_count",
    "paragraph_count",
    "image_count",
    "link_count",
    "list_item",
    "strong_tag",
    "density",
    "messenger",
    "price",
    "payment",
    "delivery",
    "warranty",
    "returns",
    "reviews",
    "rating",
)

SHORTCUT_CAPS: dict[str, float] = {
    "text_length_chars": 9600.0,
    "html_length_chars": 60000.0,
    "word_count": 1600.0,
    "unique_word_count": 1200.0,
    "sentence_count": 90.0,
    "paragraph_count": 36.0,
    "avg_sentence_length": 38.0,
    "avg_paragraph_length": 180.0,
    "h1_count": 2.0,
    "h2_count": 10.0,
    "h3_count": 12.0,
    "heading_count": 18.0,
    "link_count": 80.0,
    "image_count": 24.0,
    "list_item_count": 40.0,
    "strong_tag_count": 24.0,
    "link_density_per_1000_words": 80.0,
    "image_density_per_1000_words": 28.0,
    "list_density_per_1000_words": 60.0,
    "strong_density_per_1000_words": 40.0,
    "content_link_ratio": 80.0,
    "structured_data_valid_json_ld_count": 4.0,
}
UNIT_INTERVAL_FEATURES = frozenset(
    {
        "unique_word_ratio",
        "title_keyword_coverage_ratio",
        "meta_keyword_coverage_ratio",
        "heading_query_coverage_ratio",
        "early_query_coverage_ratio",
        "keyword_coverage_ratio",
        "text_to_html_ratio",
        "semantic_similarity",
        "query_semantic_alignment",
        "title_semantic_alignment",
        "heading_semantic_alignment",
        "title_heading_keyword_alignment",
        "content_depth_semantic_score",
        "query_prominence_score",
        "title_length_quality",
        "meta_length_quality",
        "keyword_balance_score",
        "semantic_content_richness",
        "cta_semantic_score",
        "canonical_signal_score",
        "technical_seo_score",
        "technical_metadata_score",
        "redirect_efficiency_score",
        "url_hygiene_score",
        "commercial_signals_score",
        "trust_signals_score",
        "contact_options_score",
        "commercial_trust_score",
        "mobile_readiness_score",
        "rendering_score",
        "performance_proxy_score",
        "performance_resource_complexity_score",
        "heavy_analysis_overall_score",
        "intent_alignment_score",
        "commercial_intent_alignment",
        "local_intent_alignment",
        "informational_intent_alignment",
        "navigational_intent_alignment",
    }
)
BINARY_FEATURE_SUFFIXES = ("_present", "_ok", "_matches_final_url", "_indexable")

CRITICAL_DEGRADATION_FEATURES: dict[str, float] = {
    "http_status_ok": 0.0,
    "page_indexable": 0.0,
    "canonical_present": 0.0,
    "canonical_matches_final_url": 0.0,
    "canonical_signal_score": 0.0,
    "title_present": 0.0,
    "query_in_title": 0.0,
    "title_keyword_coverage_ratio": 0.0,
    "query_terms_in_headings": 0.0,
    "heading_query_coverage_ratio": 0.0,
    "semantic_similarity": 0.0,
    "query_semantic_alignment": 0.0,
    "title_semantic_alignment": 0.0,
    "heading_semantic_alignment": 0.0,
    "title_heading_keyword_alignment": 0.0,
    "keyword_coverage_ratio": 0.0,
    "query_prominence_score": 0.0,
    "intent_alignment_score": 0.0,
    "commercial_intent_alignment": 0.0,
    "local_intent_alignment": 0.0,
    "informational_intent_alignment": 0.0,
    "navigational_intent_alignment": 0.0,
}
SUPPORTING_DEGRADATION_FEATURES: dict[str, float] = {
    "text_length_chars": 500.0,
    "html_length_chars": 3500.0,
    "word_count": 80.0,
    "unique_word_count": 55.0,
    "sentence_count": 5.0,
    "paragraph_count": 1.0,
    "image_count": 0.0,
    "link_count": 0.0,
    "list_item_count": 0.0,
    "strong_tag_count": 0.0,
    "price_present": 0.0,
    "currency_present": 0.0,
    "delivery_info_present": 0.0,
    "payment_info_present": 0.0,
    "warranty_info_present": 0.0,
    "returns_info_present": 0.0,
    "reviews_present": 0.0,
    "rating_present": 0.0,
    "messenger_present": 0.0,
}


@dataclass(frozen=True, slots=True)
class ShortcutPolicyRule:
    feature: str
    group: str
    cap: float
    rationale: str


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_float(value: float) -> str:
    rounded = round(float(value), 6)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.6f}".rstrip("0").rstrip(".")


def _sha1_file(path: str | Path | None) -> str | None:
    if path is None:
        return None
    resolved_path = Path(path)
    if not resolved_path.exists() or not resolved_path.is_file():
        return None
    digest = sha1()
    with resolved_path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: str | Path) -> dict[str, Any]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return {}
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_csv_rows(path: str | Path) -> tuple[list[str], list[dict[str, str]]]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return [], []
    with resolved_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def _write_csv_rows(path: str | Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def classify_feature_group(feature_name: str) -> str:
    normalized = feature_name.strip()
    if normalized in CRITICAL_FEATURES:
        return "critical"
    if normalized in IMPORTANT_FEATURES:
        return "important"
    if normalized in SUPPORTING_FEATURES:
        return "supporting"
    lower = normalized.casefold()
    if any(keyword in lower for keyword in CRITICAL_KEYWORDS):
        return "critical"
    if any(keyword in lower for keyword in SUPPORTING_KEYWORDS):
        return "supporting"
    return "important"


def shortcut_policy_rules() -> list[ShortcutPolicyRule]:
    return [
        ShortcutPolicyRule(
            feature=feature,
            group=classify_feature_group(feature),
            cap=cap,
            rationale=(
                "Preserve low-value penalties for thin pages while removing unlimited upside "
                "from raw volume/count shortcuts."
            ),
        )
        for feature, cap in sorted(SHORTCUT_CAPS.items())
    ]


def _is_binary_feature(feature_name: str) -> bool:
    return feature_name.endswith(BINARY_FEATURE_SUFFIXES) or feature_name.startswith("intent_is_")


def control_feature_value(feature_name: str, value: object) -> float:
    numeric = max(0.0, _safe_float(value))
    if feature_name in SHORTCUT_CAPS:
        return min(numeric, SHORTCUT_CAPS[feature_name])
    if feature_name in UNIT_INTERVAL_FEATURES or _is_binary_feature(feature_name):
        return min(numeric, 1.0)
    return numeric


def apply_feature_policy_to_features(
    features: Mapping[str, object],
    *,
    feature_columns: Sequence[str] | None = None,
) -> dict[str, float]:
    columns = tuple(feature_columns or features.keys())
    return {feature_name: control_feature_value(feature_name, features.get(feature_name, 0.0)) for feature_name in columns}


def _feature_change_summary() -> dict[str, dict[str, Any]]:
    return {
        feature: {
            "feature": feature,
            "group": classify_feature_group(feature),
            "cap": cap,
            "affected_rows": 0,
            "max_before": 0.0,
            "max_after": 0.0,
        }
        for feature, cap in SHORTCUT_CAPS.items()
    }


def build_controlled_dataset(
    dataset_path: str | Path = DEFAULT_SOURCE_DATASET_PATH,
    output_path: str | Path = DEFAULT_CONTROLLED_DATASET_PATH,
    *,
    feature_columns: Sequence[str] | None = None,
) -> dict[str, Any]:
    fieldnames, rows = _read_csv_rows(dataset_path)
    if not fieldnames:
        raise FileNotFoundError(f"Dataset CSV not found or empty: {dataset_path}")
    resolved_feature_columns = tuple(feature_columns or get_model_feature_schema(MODEL_SCHEMA_VERSION_V3).feature_columns)
    controlled_rows: list[dict[str, object]] = []
    feature_changes = _feature_change_summary()
    unit_interval_clamps: Counter[str] = Counter()

    for row in rows:
        controlled = dict(row)
        for feature_name in resolved_feature_columns:
            if feature_name not in row:
                continue
            before = _safe_float(row.get(feature_name))
            after = control_feature_value(feature_name, before)
            if feature_name in feature_changes:
                summary = feature_changes[feature_name]
                summary["max_before"] = max(float(summary["max_before"]), before)
                summary["max_after"] = max(float(summary["max_after"]), after)
                if after != before:
                    summary["affected_rows"] += 1
            elif after != before and (feature_name in UNIT_INTERVAL_FEATURES or _is_binary_feature(feature_name)):
                unit_interval_clamps[feature_name] += 1
            controlled[feature_name] = _format_float(after)
        controlled["dataset_version"] = DEFAULT_DATASET_VERSION
        controlled["feature_policy_version"] = FEATURE_POLICY_VERSION_V5
        controlled_rows.append(controlled)

    output_fieldnames = list(fieldnames)
    if "feature_policy_version" not in output_fieldnames:
        output_fieldnames.append("feature_policy_version")
    _write_csv_rows(output_path, output_fieldnames, controlled_rows)
    changed_shortcuts = [summary for summary in feature_changes.values() if int(summary["affected_rows"]) > 0]
    return {
        "dataset_path": str(Path(dataset_path)),
        "controlled_dataset_path": str(Path(output_path)),
        "rows_count": len(controlled_rows),
        "feature_policy_version": FEATURE_POLICY_VERSION_V5,
        "feature_columns_count": len(resolved_feature_columns),
        "shortcut_features_count": len(SHORTCUT_CAPS),
        "changed_shortcut_features_count": len(changed_shortcuts),
        "changed_shortcut_rows_total": int(sum(int(item["affected_rows"]) for item in changed_shortcuts)),
        "changed_shortcut_features": sorted(changed_shortcuts, key=lambda item: str(item["feature"])),
        "unit_interval_clamps": dict(sorted(unit_interval_clamps.items())),
    }


def build_feature_policy_document(*, generated_at: str | None = None) -> dict[str, Any]:
    generated = generated_at or datetime.now(UTC).isoformat()
    feature_columns = get_model_feature_schema(MODEL_SCHEMA_VERSION_V3).feature_columns
    group_counts = Counter(classify_feature_group(feature_name) for feature_name in feature_columns)
    return {
        "generated_at": generated,
        "feature_policy_version": FEATURE_POLICY_VERSION_V5,
        "model_schema_version": MODEL_SCHEMA_VERSION_V3,
        "feature_count": len(feature_columns),
        "group_counts": dict(sorted(group_counts.items())),
        "groups": {
            "critical": sorted(feature for feature in feature_columns if classify_feature_group(feature) == "critical"),
            "important": sorted(feature for feature in feature_columns if classify_feature_group(feature) == "important"),
            "supporting": sorted(feature for feature in feature_columns if classify_feature_group(feature) == "supporting"),
        },
        "shortcut_caps": [asdict(rule) for rule in shortcut_policy_rules()],
        "score_response_contract": {
            "critical_degradation": dict(sorted(CRITICAL_DEGRADATION_FEATURES.items())),
            "supporting_degradation": dict(sorted(SUPPORTING_DEGRADATION_FEATURES.items())),
            "requirement": "average critical score drop must be greater than supporting shortcut drop",
        },
        "notes": [
            "Deterministic policy for D52/D53/D54 only; not a production artifact mutation.",
            "Raw volume/count features stay available for thin-page risk, but high values are capped before v5 training.",
            "Commercial binary signals are supporting unless they are aggregated into page-specific trust/offer features.",
        ],
    }


def write_feature_policy(path: str | Path = DEFAULT_FEATURE_POLICY_PATH) -> dict[str, Any]:
    document = build_feature_policy_document()
    resolved_path = Path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**document, "path": str(resolved_path)}


def feature_dominance_guardrail(
    candidate: Mapping[str, Any],
    *,
    max_supporting_top10_share: float = 0.35,
    max_supporting_top5_count: int = 2,
) -> dict[str, Any]:
    importance = candidate.get("feature_importance_summary")
    top_features = importance.get("top_features") if isinstance(importance, dict) else []
    rows = [feature for feature in top_features if isinstance(feature, dict)]
    grouped_importance = {"critical": 0.0, "important": 0.0, "supporting": 0.0}
    grouped_counts = {"critical": 0, "important": 0, "supporting": 0}
    for feature in rows[:10]:
        feature_name = str(feature.get("feature") or "")
        group = classify_feature_group(feature_name)
        grouped_importance[group] += _safe_float(feature.get("importance"))
        grouped_counts[group] += 1
    total_importance = sum(grouped_importance.values())
    supporting_share = grouped_importance["supporting"] / total_importance if total_importance > 0.0 else 0.0
    top_feature = str(rows[0].get("feature") or "") if rows else ""
    top_feature_group = classify_feature_group(top_feature) if top_feature else "missing"
    top5_groups = [classify_feature_group(str(feature.get("feature") or "")) for feature in rows[:5]]
    checks = {
        "top_features_present": bool(rows),
        "top_feature_not_supporting": top_feature_group != "supporting",
        "supporting_top10_share_within_limit": supporting_share <= max_supporting_top10_share,
        "supporting_top5_count_within_limit": top5_groups.count("supporting") <= max_supporting_top5_count,
        "critical_signal_in_top5": "critical" in top5_groups,
        "critical_plus_important_at_least_supporting": (
            grouped_importance["critical"] + grouped_importance["important"]
        )
        >= grouped_importance["supporting"],
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not failed,
        "failed_checks": failed,
        "top_feature": top_feature,
        "top_feature_group": top_feature_group,
        "top_10_grouped_importance": {key: round(value, 6) for key, value in grouped_importance.items()},
        "top_10_grouped_counts": grouped_counts,
        "supporting_top10_share": round(supporting_share, 6),
        "thresholds": {
            "max_supporting_top10_share": max_supporting_top10_share,
            "max_supporting_top5_count": max_supporting_top5_count,
        },
        "checks": checks,
    }


def _artifact_feature_columns(model_path: str | Path, fallback: Sequence[str] | None = None) -> tuple[str, ...]:
    artifact = load_model_artifact(model_path)
    if artifact is not None and isinstance(artifact.get("feature_columns"), (list, tuple)):
        return tuple(str(item) for item in artifact["feature_columns"])
    return tuple(fallback or get_model_feature_schema(MODEL_SCHEMA_VERSION_V3).feature_columns)


def _row_to_features(
    row: Mapping[str, object],
    *,
    feature_columns: Sequence[str],
    apply_policy: bool,
) -> dict[str, float]:
    raw = {feature_name: _safe_float(row.get(feature_name)) for feature_name in feature_columns}
    return apply_feature_policy_to_features(raw, feature_columns=feature_columns) if apply_policy else raw


def _apply_degradation(features: Mapping[str, float], degradation: Mapping[str, float]) -> dict[str, float]:
    output = dict(features)
    for feature_name, value in degradation.items():
        if feature_name in output:
            output[feature_name] = control_feature_value(feature_name, value)
    return output


def _representative_rows(rows: Sequence[dict[str, str]], limit: int = 12) -> list[dict[str, str]]:
    usable = [row for row in rows if str(row.get("fetch_status") or "ok") != "failed"]
    return sorted(usable, key=lambda row: _safe_float(row.get("target_score")), reverse=True)[:limit]


def score_response_guardrail(
    *,
    model_path: str | Path,
    rows: Sequence[dict[str, str]],
    feature_columns: Sequence[str] | None = None,
    apply_policy: bool = True,
    min_critical_drop: float = 0.5,
    min_critical_over_supporting_delta: float = 0.5,
) -> dict[str, Any]:
    resolved_feature_columns = tuple(feature_columns or _artifact_feature_columns(model_path))
    base_scores: list[float] = []
    critical_drops: list[float] = []
    supporting_drops: list[float] = []
    examples: list[dict[str, Any]] = []

    for row in _representative_rows(rows):
        features = _row_to_features(row, feature_columns=resolved_feature_columns, apply_policy=apply_policy)
        base_score = predict_score(features, model_path=model_path)
        critical_score = predict_score(
            _apply_degradation(features, CRITICAL_DEGRADATION_FEATURES),
            model_path=model_path,
        )
        supporting_score = predict_score(
            _apply_degradation(features, SUPPORTING_DEGRADATION_FEATURES),
            model_path=model_path,
        )
        critical_drop = max(0.0, float(base_score) - float(critical_score))
        supporting_drop = max(0.0, float(base_score) - float(supporting_score))
        base_scores.append(float(base_score))
        critical_drops.append(critical_drop)
        supporting_drops.append(supporting_drop)
        if len(examples) < 5:
            examples.append(
                {
                    "query": str(row.get("query") or ""),
                    "url": str(row.get("url") or ""),
                    "base_score": round(float(base_score), 4),
                    "critical_degraded_score": round(float(critical_score), 4),
                    "supporting_degraded_score": round(float(supporting_score), 4),
                    "critical_drop": round(critical_drop, 4),
                    "supporting_drop": round(supporting_drop, 4),
                }
            )

    avg_critical_drop = mean(critical_drops) if critical_drops else 0.0
    avg_supporting_drop = mean(supporting_drops) if supporting_drops else 0.0
    checks = {
        "rows_present": bool(base_scores),
        "base_scores_bounded": all(0.0 <= score <= 100.0 for score in base_scores),
        "critical_drop_positive": avg_critical_drop >= min_critical_drop,
        "critical_drop_greater_than_supporting": avg_critical_drop >= avg_supporting_drop + min_critical_over_supporting_delta,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {
        "model_path": str(Path(model_path)),
        "passed": not failed,
        "failed_checks": failed,
        "rows_count": len(base_scores),
        "feature_policy_version": FEATURE_POLICY_VERSION_V5 if apply_policy else None,
        "average_base_score": round(mean(base_scores), 4) if base_scores else 0.0,
        "average_critical_drop": round(avg_critical_drop, 4),
        "average_supporting_drop": round(avg_supporting_drop, 4),
        "thresholds": {
            "min_critical_drop": min_critical_drop,
            "min_critical_over_supporting_delta": min_critical_over_supporting_delta,
        },
        "checks": checks,
        "examples": examples,
    }


def _candidate_entries(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    nested = report.get("candidate_artifact_training_report")
    if isinstance(nested, dict):
        candidates = nested.get("candidates")
    else:
        candidates = report.get("candidates")
    saved_candidates: list[dict[str, Any]] = []
    for candidate in candidates or []:
        if not isinstance(candidate, dict):
            continue
        model_path = str(candidate.get("model_path") or "")
        if candidate.get("status") != "available" or not model_path:
            continue
        saved_candidates.append(dict(candidate))
    return saved_candidates


def _validation_rows_from_split(dataset_path: str | Path, split_path: str | Path) -> list[dict[str, str]]:
    rows = load_dataset_rows(dataset_path)
    split = _read_json(split_path)
    validation_queries = {str(query) for query in split.get("validation_queries") or [] if str(query).strip()}
    if not validation_queries:
        return rows
    return [row for row in rows if str(row.get("query") or "") in validation_queries]


def build_candidate_guardrail_evidence(
    *,
    candidate_report_path: str | Path = DEFAULT_D47_REPORT_JSON_PATH,
    validation_rows: Sequence[dict[str, str]],
) -> dict[str, Any]:
    report = _read_json(candidate_report_path)
    candidates = _candidate_entries(report)
    guardrails: dict[str, Any] = {}
    for candidate in candidates:
        candidate_name = str(candidate.get("candidate_name") or Path(str(candidate.get("model_path") or "model")).stem)
        model_path = str(candidate.get("model_path") or "")
        feature_dominance = feature_dominance_guardrail(candidate)
        if model_path and Path(model_path).exists():
            score_response = score_response_guardrail(model_path=model_path, rows=validation_rows)
        else:
            score_response = {
                "passed": False,
                "failed_checks": ["model_path_missing"],
                "model_path": model_path,
                "rows_count": 0,
            }
        checks = {
            "feature_dominance_passed": bool(feature_dominance.get("passed")),
            "score_response_passed": bool(score_response.get("passed")),
        }
        failed = [name for name, passed in checks.items() if not passed]
        guardrails[candidate_name] = {
            "passed": not failed,
            "failed_checks": failed,
            "checks": checks,
            "model_path": model_path,
            "feature_dominance_guardrail": feature_dominance,
            "score_response_guardrail": score_response,
        }
    return {
        "candidate_report_path": str(Path(candidate_report_path)),
        "candidates_count": len(candidates),
        "guardrails": guardrails,
    }


def _render_markdown(report: Mapping[str, Any]) -> str:
    dataset = report.get("controlled_dataset") if isinstance(report.get("controlled_dataset"), dict) else {}
    policy = report.get("feature_policy") if isinstance(report.get("feature_policy"), dict) else {}
    candidate_evidence = report.get("candidate_guardrail_evidence") if isinstance(report.get("candidate_guardrail_evidence"), dict) else {}
    guardrails = candidate_evidence.get("guardrails") if isinstance(candidate_evidence.get("guardrails"), dict) else {}
    lines = [
        "# D52 Shortcut Feature Control Report",
        "",
        f"- Decision: `{report.get('decision')}`",
        f"- Production SHA1 before: `{report.get('production_sha1_before')}`",
        f"- Production SHA1 after: `{report.get('production_sha1_after')}`",
        f"- Feature policy: `{policy.get('feature_policy_version')}`",
        f"- Controlled dataset: `{dataset.get('controlled_dataset_path')}`",
        f"- Rows: `{dataset.get('rows_count')}`",
        f"- Shortcut features changed: `{dataset.get('changed_shortcut_features_count')}`",
        f"- Shortcut row changes total: `{dataset.get('changed_shortcut_rows_total')}`",
        "",
        "## Feature Groups",
        "",
    ]
    for group, count in (policy.get("group_counts") or {}).items():
        lines.append(f"- `{group}`: `{count}`")
    lines.extend(["", "## Candidate Guardrails", ""])
    if not guardrails:
        lines.append("No saved candidate guardrails were evaluated.")
    for candidate_name, guardrail in guardrails.items():
        if not isinstance(guardrail, dict):
            continue
        feature_guard = guardrail.get("feature_dominance_guardrail") if isinstance(guardrail.get("feature_dominance_guardrail"), dict) else {}
        score_guard = guardrail.get("score_response_guardrail") if isinstance(guardrail.get("score_response_guardrail"), dict) else {}
        lines.extend(
            [
                f"### {candidate_name}",
                f"- Passed: `{guardrail.get('passed')}`",
                f"- Failed checks: `{', '.join(guardrail.get('failed_checks') or []) or 'none'}`",
                f"- Top feature: `{feature_guard.get('top_feature')}` (`{feature_guard.get('top_feature_group')}`)",
                f"- Supporting top-10 share: `{feature_guard.get('supporting_top10_share')}`",
                f"- Avg critical/supporting drop: `{score_guard.get('average_critical_drop')}` / `{score_guard.get('average_supporting_drop')}`",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def write_d52_report(report: dict[str, Any], output_dir: str | Path = DEFAULT_D52_OUTPUT_DIR) -> dict[str, str]:
    resolved_dir = Path(output_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)
    json_path = resolved_dir / DEFAULT_D52_REPORT_JSON_PATH.name
    markdown_path = resolved_dir / DEFAULT_D52_REPORT_MD_PATH.name
    paths = {"json_path": str(json_path), "markdown_path": str(markdown_path)}
    report_with_paths = {**report, "report_paths": paths}
    json_path.write_text(json.dumps(report_with_paths, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(report_with_paths), encoding="utf-8")
    return paths


def run_d52_shortcut_feature_control(
    *,
    dataset_path: str | Path = DEFAULT_SOURCE_DATASET_PATH,
    controlled_dataset_path: str | Path = DEFAULT_CONTROLLED_DATASET_PATH,
    feature_policy_path: str | Path = DEFAULT_FEATURE_POLICY_PATH,
    split_path: str | Path = DEFAULT_SOURCE_SPLIT_PATH,
    candidate_report_path: str | Path = DEFAULT_D47_REPORT_JSON_PATH,
    output_dir: str | Path = DEFAULT_D52_OUTPUT_DIR,
) -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat()
    production_sha1_before = _sha1_file(DEFAULT_MODEL_PATH)
    controlled_dataset = build_controlled_dataset(dataset_path, controlled_dataset_path)
    feature_policy = write_feature_policy(feature_policy_path)
    validation_rows = _validation_rows_from_split(controlled_dataset_path, split_path)
    candidate_guardrail_evidence = build_candidate_guardrail_evidence(
        candidate_report_path=candidate_report_path,
        validation_rows=validation_rows,
    )
    production_sha1_after = _sha1_file(DEFAULT_MODEL_PATH)
    report: dict[str, Any] = {
        "generated_at": generated_at,
        "task": "D52",
        "decision": "ready_for_d53",
        "dataset_version": DEFAULT_DATASET_VERSION,
        "model_schema_version": MODEL_SCHEMA_VERSION_V3,
        "feature_policy": feature_policy,
        "controlled_dataset": controlled_dataset,
        "candidate_guardrail_evidence": candidate_guardrail_evidence,
        "validation_rows_count": len(validation_rows),
        "production_artifact_path": str(DEFAULT_MODEL_PATH),
        "production_sha1_before": production_sha1_before,
        "production_sha1_after": production_sha1_after,
        "production_artifact_unchanged": production_sha1_before == production_sha1_after,
        "acceptance": {
            "feature_policy_implemented": True,
            "controlled_dataset_written": Path(controlled_dataset_path).exists(),
            "guardrails_reusable": True,
            "production_artifact_unchanged": production_sha1_before == production_sha1_after,
        },
        "next_step": (
            "D53 should train v5 candidates with the controlled dataset or apply this same feature "
            "policy before vectorization; D54 must reuse these guardrails before any publish."
        ),
    }
    report_paths = write_d52_report(report, output_dir)
    report["report_paths"] = report_paths
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build D52 shortcut feature policy and guardrail evidence.")
    parser.add_argument("--dataset", default=str(DEFAULT_SOURCE_DATASET_PATH))
    parser.add_argument("--controlled-dataset", default=str(DEFAULT_CONTROLLED_DATASET_PATH))
    parser.add_argument("--feature-policy", default=str(DEFAULT_FEATURE_POLICY_PATH))
    parser.add_argument("--split", default=str(DEFAULT_SOURCE_SPLIT_PATH))
    parser.add_argument("--candidate-report", default=str(DEFAULT_D47_REPORT_JSON_PATH))
    parser.add_argument("--output-dir", default=str(DEFAULT_D52_OUTPUT_DIR))
    args = parser.parse_args()
    report = run_d52_shortcut_feature_control(
        dataset_path=args.dataset,
        controlled_dataset_path=args.controlled_dataset,
        feature_policy_path=args.feature_policy,
        split_path=args.split,
        candidate_report_path=args.candidate_report,
        output_dir=args.output_dir,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
