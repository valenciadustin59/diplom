from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping


COMPETITIVENESS_RELEASE_POLICY_VERSION = "d55-product-aligned-v1"
RECOMMENDATION_CONSISTENCY_CONTRACT_VERSION = "recommendation-consistency-v1"

PAGE_QUALITY_METRIC_KEYS = ("mae", "spearman_mean", "ndcg_at_10")
SERP_ALIGNMENT_METRIC_KEYS = ("top_3_hit_rate",)
SERP_ALIGNMENT_REJECTION_REASONS = {"top_3_hit_rate_regressed"}

DEFAULT_MAX_SPEARMAN_REGRESSION = 0.0
DEFAULT_MAX_NDCG_REGRESSION = 0.001
DEFAULT_ABSOLUTE_ERROR_TOLERANCE_RATIO = 0.05
DEFAULT_TOP3_DIAGNOSTIC_FLOOR = 0.95


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _selected_metrics(metrics: Mapping[str, Any], keys: tuple[str, ...]) -> dict[str, float]:
    return {key: round(_safe_float(metrics.get(key)), 6) for key in keys if key in metrics}


def _metric_deltas(
    candidate_metrics: Mapping[str, Any],
    reference_metrics: Mapping[str, Any],
    keys: tuple[str, ...],
) -> dict[str, float]:
    return {
        key: round(_safe_float(candidate_metrics.get(key)) - _safe_float(reference_metrics.get(key)), 6)
        for key in keys
        if key in candidate_metrics or key in reference_metrics
    }


def _normalise_guardrail(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {"passed": False, "reason": "not_available"}


def build_recommendation_consistency_contract(
    *,
    candidate_name: str,
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the D55 recommendation consistency contract.

    D55 keeps this as an explicit release-policy slot even before candidate-aware
    recommendation replay evidence exists. A provided failed evidence payload is
    still blocking; the default placeholder is reported as non-blocking.
    """

    if isinstance(evidence, Mapping) and evidence:
        status = str(evidence.get("status") or "unknown")
        return {
            "contract_version": str(
                evidence.get("contract_version") or RECOMMENDATION_CONSISTENCY_CONTRACT_VERSION
            ),
            "candidate_name": str(evidence.get("candidate_name") or candidate_name),
            "status": status,
            "passed": bool(evidence.get("passed", status != "failed")),
            "blocking": bool(evidence.get("blocking", status == "failed")),
            "reason": str(evidence.get("reason") or status),
            "details": evidence.get("details") if isinstance(evidence.get("details"), Mapping) else {},
        }
    return {
        "contract_version": RECOMMENDATION_CONSISTENCY_CONTRACT_VERSION,
        "candidate_name": candidate_name,
        "status": "not_evaluated",
        "passed": True,
        "blocking": False,
        "reason": "candidate_recommendation_replay_not_available_in_d55",
        "expected_evidence": [
            "same audit rows scored by current and candidate artifacts",
            "recommendation priority/order comparison",
            "no high-priority recommendation disappears without score-supported reason",
        ],
    }


def competitiveness_candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[float, float, float]:
    metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), Mapping) else {}
    return (
        _safe_float(metrics.get("spearman_mean")),
        _safe_float(metrics.get("ndcg_at_10")),
        -_safe_float(metrics.get("mae")),
    )


def split_shadow_rejection_reasons(reasons: object) -> dict[str, list[str]]:
    all_reasons = [str(reason) for reason in (reasons if isinstance(reasons, list) else [])]
    serp_reasons = [reason for reason in all_reasons if reason in SERP_ALIGNMENT_REJECTION_REASONS]
    page_quality_reasons = [reason for reason in all_reasons if reason not in SERP_ALIGNMENT_REJECTION_REASONS]
    return {
        "all": all_reasons,
        "page_quality_competitiveness": page_quality_reasons,
        "serp_alignment": serp_reasons,
    }


def build_competitiveness_release_scorecard(
    *,
    candidate_name: str,
    candidate_metrics: Mapping[str, Any],
    reference_metrics: Mapping[str, Any],
    base_guardrails: Mapping[str, Any] | None = None,
    feature_dominance: Mapping[str, Any] | None = None,
    score_response: Mapping[str, Any] | None = None,
    prediction_bounds: Mapping[str, Any] | None = None,
    recommendation_consistency: Mapping[str, Any] | None = None,
    max_spearman_regression: float = DEFAULT_MAX_SPEARMAN_REGRESSION,
    max_ndcg_regression: float = DEFAULT_MAX_NDCG_REGRESSION,
    absolute_error_tolerance_ratio: float = DEFAULT_ABSOLUTE_ERROR_TOLERANCE_RATIO,
    top3_diagnostic_floor: float = DEFAULT_TOP3_DIAGNOSTIC_FLOOR,
) -> dict[str, Any]:
    base = _normalise_guardrail(base_guardrails)
    feature = _normalise_guardrail(feature_dominance)
    response = _normalise_guardrail(score_response)
    bounds = _normalise_guardrail(prediction_bounds)
    recommendation = build_recommendation_consistency_contract(
        candidate_name=candidate_name,
        evidence=recommendation_consistency,
    )

    candidate_mae = _safe_float(candidate_metrics.get("mae"))
    reference_mae = _safe_float(reference_metrics.get("mae"))
    mae_threshold = round(reference_mae * (1.0 + absolute_error_tolerance_ratio), 6)
    candidate_spearman = _safe_float(candidate_metrics.get("spearman_mean"))
    reference_spearman = _safe_float(reference_metrics.get("spearman_mean"))
    candidate_ndcg = _safe_float(candidate_metrics.get("ndcg_at_10"))
    reference_ndcg = _safe_float(reference_metrics.get("ndcg_at_10"))
    candidate_top3 = _safe_float(candidate_metrics.get("top_3_hit_rate"))
    reference_top3 = _safe_float(reference_metrics.get("top_3_hit_rate"))

    base_checks = base.get("checks") if isinstance(base.get("checks"), Mapping) else {}
    candidate_available = bool(base_checks.get("candidate_available", True))
    page_quality_checks = {
        "candidate_available": candidate_available,
        "spearman_mean_no_meaningful_regression": candidate_spearman
        >= reference_spearman - max_spearman_regression,
        "ndcg_at_10_no_meaningful_regression": candidate_ndcg >= reference_ndcg - max_ndcg_regression,
        "mae_comparable_or_better": candidate_mae <= mae_threshold,
    }
    recommendation_contract_present = (
        recommendation.get("contract_version") == RECOMMENDATION_CONSISTENCY_CONTRACT_VERSION
        and recommendation.get("candidate_name") == candidate_name
    )
    product_guardrail_checks = {
        "validation_scores_bounded": bool(bounds.get("passed")),
        "feature_dominance_guardrail_passed": bool(feature.get("passed")),
        "score_response_guardrail_passed": bool(response.get("passed")),
        "recommendation_consistency_contract_present": bool(recommendation_contract_present),
        "recommendation_consistency_not_failed": bool(recommendation.get("passed")),
    }
    checks = {**page_quality_checks, **product_guardrail_checks}
    failed = [name for name, passed in checks.items() if not bool(passed)]

    top3_delta = round(candidate_top3 - reference_top3, 6)
    serp_warnings = []
    if candidate_top3 < top3_diagnostic_floor:
        serp_warnings.append("top_3_hit_rate_below_diagnostic_floor")
    if candidate_top3 < reference_top3:
        serp_warnings.append("top_3_hit_rate_below_reference")
    shadow_reasons = split_shadow_rejection_reasons(base.get("rejection_reasons"))

    return {
        "policy_version": COMPETITIVENESS_RELEASE_POLICY_VERSION,
        "passed": not failed,
        "failed_checks": failed,
        "checks": checks,
        "page_quality_checks": page_quality_checks,
        "product_guardrail_checks": product_guardrail_checks,
        "metric_groups": {
            "page_quality_competitiveness": {
                "candidate": _selected_metrics(candidate_metrics, PAGE_QUALITY_METRIC_KEYS),
                "reference": _selected_metrics(reference_metrics, PAGE_QUALITY_METRIC_KEYS),
                "deltas": _metric_deltas(candidate_metrics, reference_metrics, PAGE_QUALITY_METRIC_KEYS),
                "blocking": True,
            },
            "serp_alignment": {
                "candidate": _selected_metrics(candidate_metrics, SERP_ALIGNMENT_METRIC_KEYS),
                "reference": _selected_metrics(reference_metrics, SERP_ALIGNMENT_METRIC_KEYS),
                "deltas": _metric_deltas(candidate_metrics, reference_metrics, SERP_ALIGNMENT_METRIC_KEYS),
                "blocking": False,
                "warnings": serp_warnings,
            },
        },
        "serp_alignment_diagnostics": {
            "blocking": False,
            "top_3_hit_rate": {
                "candidate": round(candidate_top3, 6),
                "reference": round(reference_top3, 6),
                "delta": top3_delta,
                "diagnostic_floor": top3_diagnostic_floor,
            },
            "warnings": serp_warnings,
        },
        "legacy_shadow_gate": {
            "publish_gate_passed": bool(base.get("publish_gate_passed")),
            "ignored_as_release_boolean": True,
            "rejection_reasons": shadow_reasons,
        },
        "base_rejection_reasons": shadow_reasons["all"],
        "base_page_quality_rejection_reasons": shadow_reasons["page_quality_competitiveness"],
        "base_serp_alignment_rejection_reasons": shadow_reasons["serp_alignment"],
        "thresholds": {
            "max_spearman_meaningful_regression": max_spearman_regression,
            "max_ndcg_meaningful_regression": max_ndcg_regression,
            "absolute_error_tolerance_ratio": absolute_error_tolerance_ratio,
            "mae_comparable_threshold": mae_threshold,
            "top_3_hit_rate_diagnostic_floor": top3_diagnostic_floor,
        },
        "feature_dominance_guardrail": feature,
        "score_response_guardrail": response,
        "prediction_bounds": bounds,
        "recommendation_consistency": recommendation,
    }
