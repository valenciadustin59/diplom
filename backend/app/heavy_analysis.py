from __future__ import annotations

import json
import re
from typing import Iterable

from app.parser import ensure_extraction_artifact


HEAVY_ANALYSIS_SCHEMA_VERSION = "heavy-analysis-v1"

BUSINESS_SCHEMA_TYPES = {
    "corporation",
    "localbusiness",
    "organization",
    "professionalservice",
    "store",
}
OFFER_SCHEMA_TYPES = {"aggregateoffer", "offer", "product", "service"}
FAQ_SCHEMA_TYPES = {"faqpage"}
BREADCRUMB_SCHEMA_TYPES = {"breadcrumblist"}

HEAVY_ANALYSIS_FEATURE_COLUMNS = [
    "heavy_analysis_available",
    "heavy_analysis_overall_score",
    "structured_data_json_ld_count",
    "structured_data_valid_json_ld_count",
    "structured_data_malformed_json_ld_count",
    "structured_data_schema_type_count",
    "structured_data_business_schema_present",
    "structured_data_offer_schema_present",
    "structured_data_faq_schema_present",
    "structured_data_breadcrumb_schema_present",
    "structured_data_score",
    "mobile_viewport_present",
    "mobile_readiness_score",
    "rendering_browser_fetch_used",
    "rendering_js_dependency_risk",
    "rendering_text_html_ratio",
    "rendering_score",
    "performance_html_size_kb",
    "performance_dom_node_count",
    "performance_script_count",
    "performance_stylesheet_count",
    "performance_image_count",
    "performance_response_time_ms",
    "performance_resource_complexity_score",
    "performance_proxy_score",
]


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _round_score(value: float) -> float:
    return round(_clamp(value), 6)


def _safe_ratio(numerator: float, denominator: float) -> float:
    return 0.0 if denominator <= 0 else numerator / denominator


def _as_int(value: object) -> int:
    return int(value) if isinstance(value, (int, float)) else 0


def _normalize_snapshot(snapshot: dict[str, object] | None) -> dict[str, object]:
    if not isinstance(snapshot, dict):
        raise ValueError("Heavy analysis requires an extraction snapshot.")

    requested_url = str(snapshot.get("requested_url") or snapshot.get("final_url") or "").strip()
    if not requested_url:
        raise ValueError("Heavy analysis snapshot must define requested_url or final_url.")

    return ensure_extraction_artifact(requested_url=requested_url, artifact=snapshot)


def _walk_json_ld(value: object) -> Iterable[dict[str, object]]:
    if isinstance(value, dict):
        yield value
        graph = value.get("@graph")
        if isinstance(graph, list):
            yield from _walk_json_ld(graph)
        return
    if isinstance(value, list):
        for item in value:
            yield from _walk_json_ld(item)


def _parse_json_ld(raw_items: object) -> tuple[list[dict[str, object]], int]:
    if not isinstance(raw_items, list):
        return [], 0

    objects: list[dict[str, object]] = []
    malformed_count = 0
    for raw_item in raw_items:
        if not isinstance(raw_item, str) or not raw_item.strip():
            continue
        try:
            parsed = json.loads(raw_item)
        except json.JSONDecodeError:
            malformed_count += 1
            continue
        objects.extend(_walk_json_ld(parsed))
    return objects, malformed_count


def _schema_types(objects: Iterable[dict[str, object]]) -> set[str]:
    schema_types: set[str] = set()
    for item in objects:
        raw_type = item.get("@type")
        if isinstance(raw_type, str) and raw_type.strip():
            schema_types.add(raw_type.strip().lower())
        elif isinstance(raw_type, list):
            schema_types.update(str(value).strip().lower() for value in raw_type if str(value).strip())
    return schema_types


def _document(snapshot: dict[str, object]) -> dict[str, object]:
    document = snapshot.get("document")
    return document if isinstance(document, dict) else {}


def _document_counts(snapshot: dict[str, object]) -> dict[str, object]:
    counts = _document(snapshot).get("counts")
    return counts if isinstance(counts, dict) else {}


def _count_pattern(pattern: str, html: str) -> int:
    return len(re.findall(pattern, html, flags=re.IGNORECASE))


def _build_structured_data_analysis(snapshot: dict[str, object]) -> dict[str, object]:
    raw_json_ld = snapshot.get("json_ld")
    json_ld_count = len(raw_json_ld) if isinstance(raw_json_ld, list) else 0
    objects, malformed_count = _parse_json_ld(raw_json_ld)
    schema_types = _schema_types(objects)
    business_present = int(bool(schema_types & BUSINESS_SCHEMA_TYPES))
    offer_present = int(bool(schema_types & OFFER_SCHEMA_TYPES))
    faq_present = int(bool(schema_types & FAQ_SCHEMA_TYPES))
    breadcrumb_present = int(bool(schema_types & BREADCRUMB_SCHEMA_TYPES))
    type_count = len(schema_types)
    score = _round_score(
        min(len(objects), 4) / 4.0 * 0.35
        + min(type_count, 5) / 5.0 * 0.25
        + business_present * 0.15
        + offer_present * 0.15
        + max(faq_present, breadcrumb_present) * 0.10
        - min(malformed_count, 3) / 3.0 * 0.20
    )
    return {
        "json_ld_count": json_ld_count,
        "valid_json_ld_count": len(objects),
        "malformed_json_ld_count": malformed_count,
        "schema_types": sorted(schema_types),
        "schema_type_count": type_count,
        "business_schema_present": business_present,
        "offer_schema_present": offer_present,
        "faq_schema_present": faq_present,
        "breadcrumb_schema_present": breadcrumb_present,
        "score": score,
    }


def _build_resource_counts(snapshot: dict[str, object]) -> dict[str, int]:
    html = str(snapshot.get("html") or "")
    counts = _document_counts(snapshot)
    return {
        "dom_node_count": _count_pattern(r"<[a-zA-Z][^>]*", html),
        "image_count": _as_int(counts.get("image")),
        "script_count": _count_pattern(r"<script\b", html),
        "stylesheet_count": _count_pattern(r"<link\b[^>]*rel=[\"'][^\"']*stylesheet", html)
        + _count_pattern(r"<style\b", html),
        "noscript_count": _count_pattern(r"<noscript\b", html),
    }


def _build_mobile_analysis(snapshot: dict[str, object], resource_counts: dict[str, int]) -> dict[str, object]:
    document = _document(snapshot)
    viewport_present = int(bool(str(document.get("viewport") or "").strip()))
    image_count = resource_counts["image_count"]
    text_length = len(str(snapshot.get("text") or ""))
    content_density_score = _round_score(min(text_length / 1800.0, 1.0))
    image_pressure_score = _round_score(1.0 - min(image_count / 40.0, 1.0) * 0.45)
    score = _round_score(viewport_present * 0.55 + content_density_score * 0.25 + image_pressure_score * 0.20)
    return {
        "viewport_present": viewport_present,
        "content_density_score": content_density_score,
        "image_pressure_score": image_pressure_score,
        "score": score,
    }


def _build_rendering_analysis(snapshot: dict[str, object], resource_counts: dict[str, int]) -> dict[str, object]:
    html = str(snapshot.get("html") or "")
    text = str(snapshot.get("text") or "")
    browser_fetch_used = int(str(snapshot.get("fetch_method") or "").lower() == "browser")
    text_html_ratio = _safe_ratio(len(text), max(len(html), 1))
    script_pressure = min(resource_counts["script_count"] / 35.0, 1.0)
    low_text_penalty = 1.0 - min(text_html_ratio / 0.08, 1.0)
    js_dependency_risk = _round_score(script_pressure * 0.45 + low_text_penalty * 0.35 + browser_fetch_used * 0.20)
    return {
        "browser_fetch_used": browser_fetch_used,
        "text_html_ratio": round(text_html_ratio, 6),
        "js_dependency_risk": js_dependency_risk,
        "noscript_count": resource_counts["noscript_count"],
        "score": _round_score(1.0 - js_dependency_risk),
    }


def _build_performance_proxy_analysis(snapshot: dict[str, object], resource_counts: dict[str, int]) -> dict[str, object]:
    html_size_kb = round(len(str(snapshot.get("html") or "").encode("utf-8")) / 1024.0, 4)
    response_time_ms = float(snapshot.get("response_time_ms") or 0.0) if isinstance(snapshot.get("response_time_ms"), (int, float)) else 0.0
    resource_complexity_score = _round_score(
        1.0
        - (
            min(html_size_kb / 1024.0, 1.0) * 0.30
            + min(resource_counts["dom_node_count"] / 1800.0, 1.0) * 0.20
            + min(resource_counts["script_count"] / 35.0, 1.0) * 0.20
            + min(resource_counts["stylesheet_count"] / 16.0, 1.0) * 0.15
            + min(resource_counts["image_count"] / 45.0, 1.0) * 0.15
        )
    )
    response_score = 1.0 if response_time_ms <= 0 else _round_score(1.0 - min(response_time_ms / 3000.0, 1.0) * 0.35)
    return {
        "html_size_kb": html_size_kb,
        "dom_node_count": resource_counts["dom_node_count"],
        "script_count": resource_counts["script_count"],
        "stylesheet_count": resource_counts["stylesheet_count"],
        "image_count": resource_counts["image_count"],
        "response_time_ms": round(response_time_ms, 4),
        "resource_complexity_score": resource_complexity_score,
        "score": _round_score(resource_complexity_score * 0.75 + response_score * 0.25),
    }


def _risk_level(overall_score: float) -> str:
    if overall_score < 0.45:
        return "high"
    if overall_score < 0.70:
        return "medium"
    return "low"


def _build_feature_payload(
    *,
    overall_score: float,
    structured_data: dict[str, object],
    mobile: dict[str, object],
    rendering: dict[str, object],
    performance_proxy: dict[str, object],
) -> dict[str, float | int]:
    return {
        "heavy_analysis_available": 1,
        "heavy_analysis_overall_score": overall_score,
        "structured_data_json_ld_count": int(structured_data["json_ld_count"]),
        "structured_data_valid_json_ld_count": int(structured_data["valid_json_ld_count"]),
        "structured_data_malformed_json_ld_count": int(structured_data["malformed_json_ld_count"]),
        "structured_data_schema_type_count": int(structured_data["schema_type_count"]),
        "structured_data_business_schema_present": int(structured_data["business_schema_present"]),
        "structured_data_offer_schema_present": int(structured_data["offer_schema_present"]),
        "structured_data_faq_schema_present": int(structured_data["faq_schema_present"]),
        "structured_data_breadcrumb_schema_present": int(structured_data["breadcrumb_schema_present"]),
        "structured_data_score": float(structured_data["score"]),
        "mobile_viewport_present": int(mobile["viewport_present"]),
        "mobile_readiness_score": float(mobile["score"]),
        "rendering_browser_fetch_used": int(rendering["browser_fetch_used"]),
        "rendering_js_dependency_risk": float(rendering["js_dependency_risk"]),
        "rendering_text_html_ratio": float(rendering["text_html_ratio"]),
        "rendering_score": float(rendering["score"]),
        "performance_html_size_kb": float(performance_proxy["html_size_kb"]),
        "performance_dom_node_count": int(performance_proxy["dom_node_count"]),
        "performance_script_count": int(performance_proxy["script_count"]),
        "performance_stylesheet_count": int(performance_proxy["stylesheet_count"]),
        "performance_image_count": int(performance_proxy["image_count"]),
        "performance_response_time_ms": float(performance_proxy["response_time_ms"]),
        "performance_resource_complexity_score": float(performance_proxy["resource_complexity_score"]),
        "performance_proxy_score": float(performance_proxy["score"]),
    }


def build_heavy_analysis_payload(snapshot: dict[str, object] | None) -> dict[str, object]:
    normalized_snapshot = _normalize_snapshot(snapshot)
    resource_counts = _build_resource_counts(normalized_snapshot)
    structured_data = _build_structured_data_analysis(normalized_snapshot)
    mobile = _build_mobile_analysis(normalized_snapshot, resource_counts)
    rendering = _build_rendering_analysis(normalized_snapshot, resource_counts)
    performance_proxy = _build_performance_proxy_analysis(normalized_snapshot, resource_counts)
    analyzer_scores = [
        float(structured_data["score"]),
        float(mobile["score"]),
        float(rendering["score"]),
        float(performance_proxy["score"]),
    ]
    overall_score = _round_score(sum(analyzer_scores) / len(analyzer_scores))
    features = _build_feature_payload(
        overall_score=overall_score,
        structured_data=structured_data,
        mobile=mobile,
        rendering=rendering,
        performance_proxy=performance_proxy,
    )
    return {
        "schema_version": HEAVY_ANALYSIS_SCHEMA_VERSION,
        "status": "completed",
        "summary": {
            "overall_score": overall_score,
            "risk_level": _risk_level(overall_score),
            "analyzer_count": 4,
            "feature_count": len(features),
        },
        "features": features,
        "analyzers": {
            "structured_data": structured_data,
            "mobile": mobile,
            "rendering": rendering,
            "performance_proxy": performance_proxy,
        },
    }


def build_heavy_analysis_features(payload: dict[str, object] | None) -> dict[str, float | int]:
    if not isinstance(payload, dict):
        return {}
    features = payload.get("features")
    if not isinstance(features, dict):
        return {}
    return {
        str(key): value
        for key, value in features.items()
        if isinstance(value, (int, float)) and str(key) in HEAVY_ANALYSIS_FEATURE_COLUMNS
    }


def merge_heavy_analysis_features(
    features: dict[str, float | int],
    payload: dict[str, object] | None,
) -> dict[str, float | int]:
    heavy_features = build_heavy_analysis_features(payload)
    if not heavy_features:
        return dict(features)
    return {
        **features,
        **heavy_features,
    }
