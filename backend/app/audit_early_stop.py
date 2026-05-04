from __future__ import annotations

from typing import Any, Mapping

from app.models import Audit


EARLY_STOP_SUMMARY_VERSION = "early-stop-summary-v1"
QUERY_RELEVANCE_EARLY_STOP_TYPE = "query_relevance_full_mismatch"
QUERY_RELEVANCE_EARLY_STOP_TITLE = "Страница не соответствует запросу"
QUERY_RELEVANCE_EARLY_STOP_MESSAGE = (
    "Сравнение с конкурентами не запускалось, потому что страница не отвечает теме запроса. "
    "Выберите другую страницу или измените запрос."
)
QUERY_RELEVANCE_EARLY_STOP_SKIPPED_STAGES = [
    "heavy_analysis",
    "competitors",
    "competitor_page",
    "competitor_analysis",
    "competitor_aggregation",
    "recommendations",
]


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _finite_float(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    result = float(value)
    if result != result or result in {float("inf"), float("-inf")}:
        return None
    return result


def _first_finite_float(*values: object) -> float | None:
    for value in values:
        result = _finite_float(value)
        if result is not None:
            return result
    return None


def build_audit_early_stop_summary(audit: Audit) -> dict[str, object] | None:
    score_breakdown = _as_mapping(audit.score_breakdown)
    guardrail = _as_mapping(score_breakdown.get("relevance_guardrail"))
    if guardrail.get("early_stop") is not True:
        return None

    decision = _as_mapping(guardrail.get("early_stop_decision"))
    comparison_summary = _as_mapping(audit.comparison_summary)
    comparison_guardrail = _as_mapping(comparison_summary.get("relevance_guardrail"))
    reason = str(
        decision.get("reason")
        or guardrail.get("early_stop_reason")
        or guardrail.get("reason")
        or comparison_guardrail.get("reason")
        or "query_relevance_early_stop"
    )
    score = _first_finite_float(
        audit.score,
        score_breakdown.get("final_score"),
        comparison_summary.get("final_score"),
    )
    score_floor = _first_finite_float(decision.get("score_floor"), guardrail.get("band_min")) or 0.0
    score_ceiling = (
        _first_finite_float(
            decision.get("score_ceiling"),
            guardrail.get("band_max"),
            comparison_guardrail.get("score_ceiling"),
        )
        or 5.0
    )
    return {
        "schema_version": EARLY_STOP_SUMMARY_VERSION,
        "active": True,
        "type": QUERY_RELEVANCE_EARLY_STOP_TYPE,
        "reason": reason,
        "status": str(guardrail.get("early_stop_status") or comparison_guardrail.get("status") or "completed"),
        "title": QUERY_RELEVANCE_EARLY_STOP_TITLE,
        "message": QUERY_RELEVANCE_EARLY_STOP_MESSAGE,
        "score": round(score, 4) if score is not None else None,
        "score_floor": score_floor,
        "score_ceiling": score_ceiling,
        "score_basis": str(comparison_summary.get("score_basis") or "query_relevance_early_stop"),
        "safe_to_skip_competitors": decision.get("safe_to_skip_competitors") is True,
        "skipped_stages": QUERY_RELEVANCE_EARLY_STOP_SKIPPED_STAGES,
        "competitor_processing_status": audit.competitor_processing_status,
    }
