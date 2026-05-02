from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha1
import json
from pathlib import Path
from statistics import fmean
from typing import Any, Mapping, Sequence

from app.ml.v3_dataset import DATASET_VERSIONS_DIR


DEFAULT_SOURCE_DATASET_DIR = DATASET_VERSIONS_DIR / "dataset-v3-d37"
DEFAULT_SOURCE_DATASET_PATH = DEFAULT_SOURCE_DATASET_DIR / "dataset.csv"
DEFAULT_SOURCE_SPLIT_PATH = DEFAULT_SOURCE_DATASET_DIR / "split.json"
DEFAULT_OUTPUT_DIR = DATASET_VERSIONS_DIR / "dataset-v4"
DEFAULT_OUTPUT_LABELS_PATH = DEFAULT_OUTPUT_DIR / "expert_labels.csv"
DEFAULT_OUTPUT_REPORT_JSON_PATH = DEFAULT_OUTPUT_DIR / "d45-seo-weighted-label-report.json"
DEFAULT_OUTPUT_REPORT_MD_PATH = DEFAULT_OUTPUT_DIR / "d45-seo-weighted-label-report.md"
DEFAULT_OUTPUT_SPLIT_VALIDATION_PATH = DEFAULT_OUTPUT_DIR / "d45-split-validation.json"
DEFAULT_PRODUCTION_ARTIFACT_PATH = Path(__file__).resolve().parents[2] / "artifacts" / "page_quality_model.pkl"
DEFAULT_LABELER = "d45_seo_weighted_rubric_v1"
DEFAULT_LABEL_SOURCE = "seo_weighted_rubric_v4"
DEFAULT_DATASET_VERSION = "dataset-v4"

LABEL_FIELDNAMES = [
    "query",
    "url",
    "expert_target_score",
    "label_source",
    "labeler",
    "notes",
    "critical_score",
    "important_score",
    "supporting_score",
    "rank_prior_score",
    "cap_applied",
    "cap_reasons",
    "quality_band",
    "top_positive_factors",
    "top_negative_factors",
]

RUBRIC_WEIGHTS = {
    "critical": {
        "total": 0.55,
        "features": {
            "crawl_indexability": 0.18,
            "canonical_consistency": 0.12,
            "title_query_fit": 0.19,
            "heading_query_fit": 0.10,
            "semantic_query_fit": 0.25,
            "intent_alignment": 0.16,
        },
    },
    "important": {
        "total": 0.30,
        "features": {
            "technical_metadata": 0.22,
            "page_structure": 0.16,
            "commercial_trust": 0.24,
            "offer_and_conversion": 0.20,
            "mobile_render_performance": 0.18,
        },
    },
    "supporting": {
        "total": 0.10,
        "features": {
            "text_sufficiency": 0.25,
            "media_and_internal_navigation": 0.20,
            "secondary_commercial_details": 0.35,
            "structured_support": 0.20,
        },
    },
    "rank_prior": {
        "total": 0.05,
        "features": {
            "serp_rank_prior": 1.0,
        },
    },
}


@dataclass(frozen=True, slots=True)
class FactorSignal:
    name: str
    score: float
    group: str
    importance: str


@dataclass(frozen=True, slots=True)
class RowLabel:
    query: str
    url: str
    expert_target_score: float
    label_source: str
    labeler: str
    notes: str
    critical_score: float
    important_score: float
    supporting_score: float
    rank_prior_score: float
    cap_applied: float
    cap_reasons: str
    quality_band: str
    top_positive_factors: str
    top_negative_factors: str


def _safe_float(row: Mapping[str, object], key: str, default: float = 0.0) -> float:
    value = row.get(key)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


def _round_score(value: float) -> float:
    return round(max(0.0, min(100.0, float(value))), 1)


def _score01(row: Mapping[str, object], key: str, default: float = 0.0) -> float:
    return _clamp(_safe_float(row, key, default))


def _boolean_score(row: Mapping[str, object], key: str, default: float = 0.0) -> float:
    return 1.0 if _safe_float(row, key, default) > 0.0 else 0.0


def _semantic_score(row: Mapping[str, object], key: str = "semantic_similarity") -> float:
    return _clamp((_safe_float(row, key) + 0.05) / 0.95)


def _word_sufficiency(word_count: float) -> float:
    if word_count <= 0.0:
        return 0.0
    if word_count < 80.0:
        return 0.12
    if word_count < 250.0:
        return 0.35
    if word_count < 600.0:
        return 0.62
    if word_count < 1400.0:
        return 0.85
    return 1.0


def _density_score(value: float, target: float) -> float:
    if target <= 0.0:
        return 0.0
    return _clamp(value / target)


def _weighted(signals: Mapping[str, float], weights: Mapping[str, float]) -> float:
    total_weight = sum(float(value) for value in weights.values())
    if total_weight <= 0.0:
        return 0.0
    return _clamp(sum(_clamp(signals.get(name, 0.0)) * weight for name, weight in weights.items()) / total_weight)


def _crawl_indexability(row: Mapping[str, object]) -> float:
    return _weighted(
        {
            "http_status_ok": _boolean_score(row, "http_status_ok", 1.0),
            "page_indexable": _boolean_score(row, "page_indexable", 1.0),
            "robots_clean": 1.0 - max(_score01(row, "robots_noindex"), _score01(row, "robots_nofollow")),
            "viewport_present": _boolean_score(row, "viewport_present", 1.0),
            "lang_present": _boolean_score(row, "lang_present", 1.0),
        },
        {
            "http_status_ok": 0.35,
            "page_indexable": 0.35,
            "robots_clean": 0.15,
            "viewport_present": 0.08,
            "lang_present": 0.07,
        },
    )


def _canonical_consistency(row: Mapping[str, object]) -> float:
    return _weighted(
        {
            "canonical_present": _boolean_score(row, "canonical_present"),
            "canonical_matches_final_url": _boolean_score(row, "canonical_matches_final_url"),
            "canonical_signal_score": _score01(row, "canonical_signal_score"),
        },
        {
            "canonical_present": 0.25,
            "canonical_matches_final_url": 0.55,
            "canonical_signal_score": 0.20,
        },
    )


def _title_query_fit(row: Mapping[str, object]) -> float:
    return _weighted(
        {
            "title_present": _boolean_score(row, "title_present"),
            "query_in_title": _boolean_score(row, "query_in_title"),
            "title_keyword_coverage_ratio": _score01(row, "title_keyword_coverage_ratio"),
            "title_semantic_alignment": _score01(row, "title_semantic_alignment"),
            "title_length_quality": _score01(row, "title_length_quality"),
        },
        {
            "title_present": 0.12,
            "query_in_title": 0.30,
            "title_keyword_coverage_ratio": 0.25,
            "title_semantic_alignment": 0.23,
            "title_length_quality": 0.10,
        },
    )


def _heading_query_fit(row: Mapping[str, object]) -> float:
    return _weighted(
        {
            "has_h1": 1.0 if _safe_float(row, "h1_count") >= 1.0 else 0.0,
            "heading_query_coverage_ratio": _score01(row, "heading_query_coverage_ratio"),
            "query_terms_in_headings": _density_score(_safe_float(row, "query_terms_in_headings"), 4.0),
            "heading_semantic_alignment": _score01(row, "heading_semantic_alignment"),
            "title_heading_keyword_alignment": _score01(row, "title_heading_keyword_alignment"),
        },
        {
            "has_h1": 0.20,
            "heading_query_coverage_ratio": 0.28,
            "query_terms_in_headings": 0.17,
            "heading_semantic_alignment": 0.22,
            "title_heading_keyword_alignment": 0.13,
        },
    )


def _semantic_query_fit(row: Mapping[str, object]) -> float:
    return _weighted(
        {
            "semantic_similarity": _semantic_score(row),
            "query_semantic_alignment": _score01(row, "query_semantic_alignment"),
            "keyword_coverage_ratio": _score01(row, "keyword_coverage_ratio"),
            "keyword_balance_score": _score01(row, "keyword_balance_score"),
            "query_prominence_score": _score01(row, "query_prominence_score"),
        },
        {
            "semantic_similarity": 0.30,
            "query_semantic_alignment": 0.22,
            "keyword_coverage_ratio": 0.22,
            "keyword_balance_score": 0.12,
            "query_prominence_score": 0.14,
        },
    )


def _intent_alignment(row: Mapping[str, object]) -> float:
    intent_score = _score01(row, "intent_alignment_score")
    if intent_score > 0.0:
        return intent_score
    return _weighted(
        {
            "commercial_intent_alignment": _score01(row, "commercial_intent_alignment"),
            "local_intent_alignment": _score01(row, "local_intent_alignment"),
            "informational_intent_alignment": _score01(row, "informational_intent_alignment"),
            "navigational_intent_alignment": _score01(row, "navigational_intent_alignment"),
        },
        {
            "commercial_intent_alignment": 0.35,
            "local_intent_alignment": 0.25,
            "informational_intent_alignment": 0.25,
            "navigational_intent_alignment": 0.15,
        },
    )


def _technical_metadata(row: Mapping[str, object]) -> float:
    return _weighted(
        {
            "technical_metadata_score": _score01(row, "technical_metadata_score"),
            "url_hygiene_score": _score01(row, "url_hygiene_score"),
            "redirect_efficiency_score": _score01(row, "redirect_efficiency_score"),
            "meta_description_present": _boolean_score(row, "meta_description_present"),
            "meta_length_quality": _score01(row, "meta_length_quality"),
        },
        {
            "technical_metadata_score": 0.32,
            "url_hygiene_score": 0.20,
            "redirect_efficiency_score": 0.16,
            "meta_description_present": 0.16,
            "meta_length_quality": 0.16,
        },
    )


def _page_structure(row: Mapping[str, object]) -> float:
    return _weighted(
        {
            "heading_paragraph_balance": _score01(row, "heading_paragraph_balance"),
            "content_link_ratio": _score01(row, "content_link_ratio"),
            "content_depth_semantic_score": _score01(row, "content_depth_semantic_score"),
            "semantic_content_richness": _score01(row, "semantic_content_richness"),
        },
        {
            "heading_paragraph_balance": 0.22,
            "content_link_ratio": 0.16,
            "content_depth_semantic_score": 0.34,
            "semantic_content_richness": 0.28,
        },
    )


def _commercial_trust(row: Mapping[str, object]) -> float:
    commercial_intent = max(_score01(row, "intent_is_commercial"), _score01(row, "intent_is_local_commercial"))
    raw = _weighted(
        {
            "contact_options_score": _score01(row, "contact_options_score"),
            "commercial_signals_score": _score01(row, "commercial_signals_score"),
            "trust_signals_score": _score01(row, "trust_signals_score"),
            "commercial_trust_score": _score01(row, "commercial_trust_score"),
            "company_identity": max(_boolean_score(row, "company_identity_present"), _boolean_score(row, "legal_requisites_present")),
        },
        {
            "contact_options_score": 0.24,
            "commercial_signals_score": 0.20,
            "trust_signals_score": 0.20,
            "commercial_trust_score": 0.26,
            "company_identity": 0.10,
        },
    )
    return raw if commercial_intent >= 0.5 else max(raw, 0.72)


def _offer_and_conversion(row: Mapping[str, object]) -> float:
    return _weighted(
        {
            "cta": max(_boolean_score(row, "cta_present"), _density_score(_safe_float(row, "cta_count"), 2.0)),
            "value_proposition": _boolean_score(row, "value_proposition_present"),
            "contact_path": max(_boolean_score(row, "phone_present"), _boolean_score(row, "email_present"), _boolean_score(row, "address_present")),
            "offer_schema": _boolean_score(row, "structured_data_offer_schema_present"),
            "price_signal": _boolean_score(row, "price_present"),
        },
        {
            "cta": 0.28,
            "value_proposition": 0.24,
            "contact_path": 0.22,
            "offer_schema": 0.14,
            "price_signal": 0.12,
        },
    )


def _mobile_render_performance(row: Mapping[str, object]) -> float:
    complexity = 1.0 - _score01(row, "performance_resource_complexity_score")
    return _weighted(
        {
            "mobile_readiness_score": _score01(row, "mobile_readiness_score"),
            "rendering_score": _score01(row, "rendering_score"),
            "performance_proxy_score": _score01(row, "performance_proxy_score"),
            "resource_complexity_inverse": complexity,
            "heavy_analysis_overall_score": _score01(row, "heavy_analysis_overall_score"),
        },
        {
            "mobile_readiness_score": 0.23,
            "rendering_score": 0.20,
            "performance_proxy_score": 0.20,
            "resource_complexity_inverse": 0.12,
            "heavy_analysis_overall_score": 0.25,
        },
    )


def _text_sufficiency(row: Mapping[str, object]) -> float:
    return _word_sufficiency(_safe_float(row, "word_count"))


def _media_and_internal_navigation(row: Mapping[str, object]) -> float:
    return _weighted(
        {
            "links": _density_score(_safe_float(row, "link_count"), 80.0),
            "images": _density_score(_safe_float(row, "image_count"), 20.0),
            "lists": _density_score(_safe_float(row, "list_item_count"), 40.0),
        },
        {
            "links": 0.38,
            "images": 0.24,
            "lists": 0.38,
        },
    )


def _secondary_commercial_details(row: Mapping[str, object]) -> float:
    return _weighted(
        {
            "price": _boolean_score(row, "price_present"),
            "payment": _boolean_score(row, "payment_info_present"),
            "delivery": _boolean_score(row, "delivery_info_present"),
            "warranty_returns": max(_boolean_score(row, "warranty_info_present"), _boolean_score(row, "returns_info_present")),
            "reviews": max(_boolean_score(row, "reviews_present"), _boolean_score(row, "rating_present")),
            "messenger": _boolean_score(row, "messenger_present"),
            "faq": _boolean_score(row, "faq_present"),
        },
        {
            "price": 0.18,
            "payment": 0.12,
            "delivery": 0.12,
            "warranty_returns": 0.12,
            "reviews": 0.18,
            "messenger": 0.10,
            "faq": 0.18,
        },
    )


def _structured_support(row: Mapping[str, object]) -> float:
    return _weighted(
        {
            "structured_data_score": _score01(row, "structured_data_score"),
            "valid_json_ld": _density_score(_safe_float(row, "structured_data_valid_json_ld_count"), 3.0),
            "breadcrumb": _boolean_score(row, "structured_data_breadcrumb_schema_present"),
            "faq_schema": _boolean_score(row, "structured_data_faq_schema_present"),
        },
        {
            "structured_data_score": 0.42,
            "valid_json_ld": 0.20,
            "breadcrumb": 0.18,
            "faq_schema": 0.20,
        },
    )


def _row_signals(row: Mapping[str, object]) -> list[FactorSignal]:
    signals = [
        FactorSignal("crawl_indexability", _crawl_indexability(row), "critical", "critical"),
        FactorSignal("canonical_consistency", _canonical_consistency(row), "critical", "critical"),
        FactorSignal("title_query_fit", _title_query_fit(row), "critical", "critical"),
        FactorSignal("heading_query_fit", _heading_query_fit(row), "critical", "critical"),
        FactorSignal("semantic_query_fit", _semantic_query_fit(row), "critical", "critical"),
        FactorSignal("intent_alignment", _intent_alignment(row), "critical", "critical"),
        FactorSignal("technical_metadata", _technical_metadata(row), "important", "important"),
        FactorSignal("page_structure", _page_structure(row), "important", "important"),
        FactorSignal("commercial_trust", _commercial_trust(row), "important", "important"),
        FactorSignal("offer_and_conversion", _offer_and_conversion(row), "important", "important"),
        FactorSignal("mobile_render_performance", _mobile_render_performance(row), "important", "important"),
        FactorSignal("text_sufficiency", _text_sufficiency(row), "supporting", "supporting"),
        FactorSignal("media_and_internal_navigation", _media_and_internal_navigation(row), "supporting", "supporting"),
        FactorSignal("secondary_commercial_details", _secondary_commercial_details(row), "supporting", "supporting"),
        FactorSignal("structured_support", _structured_support(row), "supporting", "supporting"),
    ]
    return signals


def _group_score(signals: Sequence[FactorSignal], group: str) -> float:
    group_signals = {signal.name: signal.score for signal in signals if signal.group == group}
    weights = RUBRIC_WEIGHTS[group]["features"]
    return _weighted(group_signals, weights)


def _rank_prior(row: Mapping[str, object]) -> float:
    weak_target = _safe_float(row, "weak_target_score", _safe_float(row, "target_score"))
    return _clamp(weak_target / 100.0)


def _page_type_adjustment(row: Mapping[str, object]) -> float:
    page_type = str(row.get("page_type") or "").strip().lower()
    commercial_intent = max(_score01(row, "intent_is_commercial"), _score01(row, "intent_is_local_commercial"))
    informational_intent = _score01(row, "intent_is_informational")
    if commercial_intent >= informational_intent:
        return {
            "product": 3.0,
            "category": 3.0,
            "homepage": 1.5,
            "content": -2.0,
            "article": -8.0,
        }.get(page_type, 0.0)
    return {
        "article": 3.0,
        "content": 2.0,
        "homepage": 0.5,
        "category": 0.0,
        "product": -3.0,
    }.get(page_type, 0.0)


def _caps(row: Mapping[str, object], signals: Sequence[FactorSignal]) -> tuple[float, list[str]]:
    cap = 100.0
    reasons: list[str] = []
    semantic = next(signal.score for signal in signals if signal.name == "semantic_query_fit")
    title = next(signal.score for signal in signals if signal.name == "title_query_fit")
    intent = next(signal.score for signal in signals if signal.name == "intent_alignment")
    commercial = next(signal.score for signal in signals if signal.name == "commercial_trust")
    word_count = _safe_float(row, "word_count")

    def apply(candidate: float, reason: str) -> None:
        nonlocal cap
        if candidate < cap:
            cap = candidate
        reasons.append(reason)

    if _boolean_score(row, "http_status_ok", 1.0) < 1.0:
        apply(35.0, "critical_http_status_not_ok")
    if _boolean_score(row, "page_indexable", 1.0) < 1.0 or _score01(row, "robots_noindex") > 0.0:
        apply(45.0, "critical_page_not_indexable")
    if _boolean_score(row, "title_present") < 1.0:
        apply(72.0, "critical_title_missing")
    if title < 0.35:
        apply(78.0, "critical_query_title_fit_weak")
    if semantic < 0.30 and _score01(row, "keyword_coverage_ratio") < 0.35:
        apply(62.0, "critical_semantic_query_fit_weak")
    if intent < 0.30:
        apply(70.0, "critical_intent_alignment_weak")
    if _boolean_score(row, "canonical_present") > 0.0 and _boolean_score(row, "canonical_matches_final_url") < 1.0:
        apply(82.0, "important_canonical_points_elsewhere")
    if commercial < 0.28 and max(_score01(row, "intent_is_commercial"), _score01(row, "intent_is_local_commercial")) >= 0.5:
        apply(76.0, "important_commercial_trust_weak")
    if word_count <= 0.0:
        apply(35.0, "critical_no_extracted_text")
    elif word_count < 80.0:
        apply(55.0, "important_extremely_thin_content")
    elif word_count < 250.0:
        apply(70.0, "supporting_text_insufficient")
    return cap, sorted(set(reasons))


def _quality_band(score: float) -> str:
    if score >= 85.0:
        return "high"
    if score >= 65.0:
        return "medium"
    if score >= 40.0:
        return "low"
    return "blocked"


def _format_factor_list(signals: Sequence[FactorSignal], *, positive: bool) -> str:
    ranked = sorted(
        signals,
        key=lambda signal: signal.score,
        reverse=positive,
    )
    selected = [signal for signal in ranked if (signal.score >= 0.78 if positive else signal.score <= 0.45)]
    if not selected:
        selected = ranked[:3]
    return "|".join(f"{signal.name}:{signal.score:.3f}" for signal in selected[:4])


def build_row_label(
    row: Mapping[str, object],
    *,
    labeler: str = DEFAULT_LABELER,
    label_source: str = DEFAULT_LABEL_SOURCE,
) -> RowLabel:
    signals = _row_signals(row)
    critical = _group_score(signals, "critical")
    important = _group_score(signals, "important")
    supporting = _group_score(signals, "supporting")
    rank_prior = _rank_prior(row)
    raw_score = 100.0 * (
        float(RUBRIC_WEIGHTS["critical"]["total"]) * critical
        + float(RUBRIC_WEIGHTS["important"]["total"]) * important
        + float(RUBRIC_WEIGHTS["supporting"]["total"]) * supporting
        + float(RUBRIC_WEIGHTS["rank_prior"]["total"]) * rank_prior
    )
    raw_score += _page_type_adjustment(row)
    cap, cap_reasons = _caps(row, signals)
    final_score = _round_score(min(raw_score, cap))
    notes = "; ".join(
        [
            "deterministic_expert_rubric=true",
            "human_label=false",
            f"rank={row.get('rank') or 'unknown'}",
            f"page_type={row.get('page_type') or 'unknown'}",
            f"raw_score={raw_score:.1f}",
            f"cap={cap:.1f}",
        ]
    )
    return RowLabel(
        query=str(row.get("query") or "").strip(),
        url=str(row.get("url") or "").strip(),
        expert_target_score=final_score,
        label_source=label_source,
        labeler=labeler,
        notes=notes,
        critical_score=round(critical, 6),
        important_score=round(important, 6),
        supporting_score=round(supporting, 6),
        rank_prior_score=round(rank_prior, 6),
        cap_applied=round(cap, 1),
        cap_reasons="|".join(cap_reasons),
        quality_band=_quality_band(final_score),
        top_positive_factors=_format_factor_list(signals, positive=True),
        top_negative_factors=_format_factor_list(signals, positive=False),
    )


def _read_dataset_rows(dataset_path: Path) -> list[dict[str, str]]:
    with dataset_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [dict(row) for row in reader if str(row.get("fetch_status") or "ok") != "failed"]


def _write_labels(labels_path: Path, labels: Sequence[RowLabel]) -> None:
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    with labels_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=LABEL_FIELDNAMES)
        writer.writeheader()
        for label in labels:
            writer.writerow({**asdict(label), "expert_target_score": f"{label.expert_target_score:.1f}"})


def _load_split(split_path: Path) -> dict[str, Any]:
    if not split_path.exists():
        return {}
    payload = json.loads(split_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def validate_label_split(rows: Sequence[Mapping[str, object]], split_path: str | Path) -> dict[str, object]:
    split = _load_split(Path(split_path))
    label_queries = {str(row.get("query") or "").strip() for row in rows if str(row.get("query") or "").strip()}
    train_queries = {str(query).strip() for query in split.get("train_queries") or [] if str(query).strip()}
    validation_queries = {
        str(query).strip() for query in split.get("validation_queries") or [] if str(query).strip()
    }
    overlap = sorted(train_queries & validation_queries)
    split_queries = train_queries | validation_queries
    uncovered = sorted(label_queries - split_queries)
    extra = sorted(split_queries - label_queries)
    passed = bool(split) and str(split.get("split_mode") or "") == "group_by_query" and not overlap and not uncovered
    return {
        "source_split_path": str(Path(split_path)),
        "passed": passed,
        "split_mode": str(split.get("split_mode") or ""),
        "label_queries_count": len(label_queries),
        "train_queries_count": len(train_queries),
        "validation_queries_count": len(validation_queries),
        "query_overlap_count": len(overlap),
        "query_overlap": overlap,
        "uncovered_label_queries_count": len(uncovered),
        "uncovered_label_queries": uncovered,
        "extra_split_queries_count": len(extra),
        "extra_split_queries": extra,
    }


def _score_stats(scores: Sequence[float]) -> dict[str, float]:
    if not scores:
        return {"min": 0.0, "mean": 0.0, "max": 0.0}
    sorted_scores = sorted(scores)

    def percentile(ratio: float) -> float:
        if not sorted_scores:
            return 0.0
        index = min(len(sorted_scores) - 1, max(0, round((len(sorted_scores) - 1) * ratio)))
        return round(sorted_scores[index], 4)

    return {
        "min": round(min(scores), 4),
        "p25": percentile(0.25),
        "mean": round(fmean(scores), 4),
        "p50": percentile(0.50),
        "p75": percentile(0.75),
        "max": round(max(scores), 4),
    }


def _counter(values: Sequence[str]) -> dict[str, int]:
    counter = Counter(values)
    return {key: counter[key] for key in sorted(counter)}


def _examples(labels: Sequence[RowLabel]) -> dict[str, list[dict[str, object]]]:
    bands = {
        "high": [label for label in labels if label.quality_band == "high"],
        "medium": [label for label in labels if label.quality_band == "medium"],
        "low": [label for label in labels if label.quality_band in {"low", "blocked"}],
        "capped": [label for label in labels if label.cap_reasons],
    }
    result: dict[str, list[dict[str, object]]] = {}
    for band, band_labels in bands.items():
        if band == "high":
            selected = sorted(band_labels, key=lambda label: label.expert_target_score, reverse=True)[:3]
        elif band == "medium":
            selected = sorted(band_labels, key=lambda label: abs(label.expert_target_score - 72.0))[:3]
        elif band == "capped":
            selected = sorted(band_labels, key=lambda label: (label.cap_applied, -label.expert_target_score))[:3]
        else:
            selected = sorted(band_labels, key=lambda label: label.expert_target_score)[:3]
        result[band] = [
            {
                "query": label.query,
                "url": label.url,
                "score": label.expert_target_score,
                "quality_band": label.quality_band,
                "cap_reasons": label.cap_reasons,
                "top_positive_factors": label.top_positive_factors,
                "top_negative_factors": label.top_negative_factors,
            }
            for label in selected
        ]
    return result


def _sha1(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = sha1()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_report(
    *,
    dataset_path: Path,
    labels_path: Path,
    labels: Sequence[RowLabel],
    rows: Sequence[Mapping[str, object]],
    split_validation: Mapping[str, object],
    production_artifact_path: Path,
) -> dict[str, object]:
    scores = [label.expert_target_score for label in labels]
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "task": "D45",
        "dataset_version": DEFAULT_DATASET_VERSION,
        "source_dataset_version": "dataset-v3-d37",
        "source_dataset_path": str(dataset_path),
        "labels_path": str(labels_path),
        "labeler": DEFAULT_LABELER,
        "label_source": DEFAULT_LABEL_SOURCE,
        "label_semantics": {
            "deterministic_expert_rubric": True,
            "human_labels": False,
            "description": "Labels are generated from a documented SEO-weighted rubric, not from manual human annotation.",
        },
        "rows_count": len(rows),
        "labels_count": len(labels),
        "queries_count": len({label.query for label in labels}),
        "domains_count": len({str(row.get("domain") or "") for row in rows if str(row.get("domain") or "")}),
        "rubric_weights": RUBRIC_WEIGHTS,
        "score_distribution": _score_stats(scores),
        "quality_band_distribution": _counter([label.quality_band for label in labels]),
        "cap_reason_distribution": _counter(
            reason
            for label in labels
            for reason in label.cap_reasons.split("|")
            if reason
        ),
        "page_type_distribution": _counter([str(row.get("page_type") or "unknown") for row in rows]),
        "label_examples": _examples(labels),
        "split_validation": dict(split_validation),
        "production_artifact": {
            "path": str(production_artifact_path),
            "sha1": _sha1(production_artifact_path),
            "changed_by_d45": False,
        },
    }


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_markdown(path: Path, report: Mapping[str, object]) -> None:
    weights = report.get("rubric_weights") if isinstance(report.get("rubric_weights"), dict) else {}
    score_distribution = report.get("score_distribution") if isinstance(report.get("score_distribution"), dict) else {}
    split_validation = report.get("split_validation") if isinstance(report.get("split_validation"), dict) else {}
    examples = report.get("label_examples") if isinstance(report.get("label_examples"), dict) else {}
    lines = [
        "# D45 SEO-Weighted Label Rubric v4",
        "",
        "These labels are deterministic expert-rubric labels. They are not human labels.",
        "",
        f"- Source dataset: `{report.get('source_dataset_version')}`",
        f"- Output labels: `{report.get('labels_path')}`",
        f"- Labels: `{report.get('labels_count')}` rows across `{report.get('queries_count')}` queries",
        f"- Split validation: `{'passed' if split_validation.get('passed') else 'failed'}`",
        f"- Production artifact changed by D45: `{report.get('production_artifact', {}).get('changed_by_d45') if isinstance(report.get('production_artifact'), dict) else False}`",
        "",
        "## Rubric Weights",
        "",
    ]
    for group_name, group_payload in weights.items():
        if not isinstance(group_payload, dict):
            continue
        lines.append(f"- `{group_name}` total weight: `{group_payload.get('total')}`")
        feature_weights = group_payload.get("features")
        if isinstance(feature_weights, dict):
            for feature_name, weight in feature_weights.items():
                lines.append(f"  - `{feature_name}`: `{weight}`")
    lines.extend(
        [
            "",
            "## Score Distribution",
            "",
            *[f"- `{key}`: `{value}`" for key, value in score_distribution.items()],
            "",
            "## Examples",
            "",
        ]
    )
    for band_name in ("high", "medium", "low", "capped"):
        lines.append(f"### {band_name}")
        band_examples = examples.get(band_name, [])
        if not isinstance(band_examples, list):
            band_examples = []
        for item in band_examples:
            lines.append(
                f"- `{item.get('score')}` `{item.get('query')}` -> `{item.get('url')}`; "
                f"limits: `{item.get('cap_reasons') or 'none'}`"
            )
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def generate_seo_weighted_labels(
    *,
    dataset_path: str | Path = DEFAULT_SOURCE_DATASET_PATH,
    split_path: str | Path = DEFAULT_SOURCE_SPLIT_PATH,
    output_labels_path: str | Path = DEFAULT_OUTPUT_LABELS_PATH,
    output_report_json_path: str | Path = DEFAULT_OUTPUT_REPORT_JSON_PATH,
    output_report_markdown_path: str | Path = DEFAULT_OUTPUT_REPORT_MD_PATH,
    output_split_validation_path: str | Path = DEFAULT_OUTPUT_SPLIT_VALIDATION_PATH,
    production_artifact_path: str | Path = DEFAULT_PRODUCTION_ARTIFACT_PATH,
    labeler: str = DEFAULT_LABELER,
    label_source: str = DEFAULT_LABEL_SOURCE,
) -> dict[str, object]:
    resolved_dataset_path = Path(dataset_path)
    resolved_split_path = Path(split_path)
    resolved_output_labels_path = Path(output_labels_path)
    resolved_output_report_json_path = Path(output_report_json_path)
    resolved_output_report_markdown_path = Path(output_report_markdown_path)
    resolved_output_split_validation_path = Path(output_split_validation_path)
    resolved_production_artifact_path = Path(production_artifact_path)

    rows = _read_dataset_rows(resolved_dataset_path)
    if not rows:
        raise ValueError(f"Source dataset has no rows: {resolved_dataset_path}")

    labels = [
        build_row_label(row, labeler=labeler, label_source=label_source)
        for row in rows
        if str(row.get("query") or "").strip() and str(row.get("url") or "").strip()
    ]
    if len(labels) != len(rows):
        raise ValueError("Every D45 source row must produce a label.")

    split_validation = validate_label_split(rows, resolved_split_path)
    _write_labels(resolved_output_labels_path, labels)
    _write_json(resolved_output_split_validation_path, split_validation)
    report = _build_report(
        dataset_path=resolved_dataset_path,
        labels_path=resolved_output_labels_path,
        labels=labels,
        rows=rows,
        split_validation=split_validation,
        production_artifact_path=resolved_production_artifact_path,
    )
    _write_json(resolved_output_report_json_path, report)
    _write_markdown(resolved_output_report_markdown_path, report)
    return {
        **report,
        "report_json_path": str(resolved_output_report_json_path),
        "report_markdown_path": str(resolved_output_report_markdown_path),
        "split_validation_path": str(resolved_output_split_validation_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate D45 SEO-weighted expert-rubric labels.")
    parser.add_argument("--dataset", default=str(DEFAULT_SOURCE_DATASET_PATH))
    parser.add_argument("--split", default=str(DEFAULT_SOURCE_SPLIT_PATH))
    parser.add_argument("--output-labels", default=str(DEFAULT_OUTPUT_LABELS_PATH))
    parser.add_argument("--output-report-json", default=str(DEFAULT_OUTPUT_REPORT_JSON_PATH))
    parser.add_argument("--output-report-md", default=str(DEFAULT_OUTPUT_REPORT_MD_PATH))
    parser.add_argument("--output-split-validation", default=str(DEFAULT_OUTPUT_SPLIT_VALIDATION_PATH))
    parser.add_argument("--production-artifact", default=str(DEFAULT_PRODUCTION_ARTIFACT_PATH))
    args = parser.parse_args()
    result = generate_seo_weighted_labels(
        dataset_path=args.dataset,
        split_path=args.split,
        output_labels_path=args.output_labels,
        output_report_json_path=args.output_report_json,
        output_report_markdown_path=args.output_report_md,
        output_split_validation_path=args.output_split_validation,
        production_artifact_path=args.production_artifact,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
