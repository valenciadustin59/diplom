from __future__ import annotations

from collections.abc import Mapping, Sequence
from statistics import fmean, median


COMPETITIVENESS_SCORE_SCHEMA_VERSION = "competitiveness-score-v1"
DEFAULT_MIN_COMPETITORS = 2


def _rounded_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 4)


def _round_metric(value: float | None) -> float | None:
    return round(float(value), 4) if value is not None else None


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _gap_strength(gap: float, full_loss_gap: float) -> float:
    if gap >= 0.0:
        return 100.0
    if full_loss_gap <= 0.0:
        return 0.0
    return _clip(100.0 + (gap / full_loss_gap) * 100.0, 0.0, 100.0)


def _score_percentile(user_score: float, competitor_scores: Sequence[float]) -> float | None:
    if not competitor_scores:
        return None
    below = sum(1 for score in competitor_scores if user_score > score)
    ties = sum(1 for score in competitor_scores if user_score == score)
    return round(((below + ties * 0.5) / len(competitor_scores)) * 100.0, 4)


def _position_band(*, average_gap: float, best_gap: float) -> str:
    if average_gap >= 5.0 and best_gap >= 0.0:
        return "leading"
    if average_gap >= -3.0 and best_gap >= -8.0:
        return "competitive"
    if average_gap >= -8.0 and best_gap >= -15.0:
        return "close_gap"
    if average_gap >= -16.0:
        return "behind"
    return "far_behind"


def _competitor_scores(competitor_results: Sequence[Mapping[str, object]]) -> list[float]:
    scores: list[float] = []
    for item in competitor_results:
        if not isinstance(item.get("features"), Mapping):
            continue
        score = item.get("score")
        if isinstance(score, (int, float)):
            scores.append(_rounded_score(float(score)))
    return scores


def build_competitiveness_score(
    *,
    user_score: float,
    competitor_results: Sequence[Mapping[str, object]],
    requested_top_n: int | None = None,
    min_competitors: int = DEFAULT_MIN_COMPETITORS,
) -> dict[str, object]:
    """Build the product-facing competitiveness layer over the primary page score.

    The model still scores the target page by its own page/query features first.
    This layer turns that primary score into the final product score only after
    enough top-N competitor pages have been processed.
    """

    primary_page_score = _rounded_score(user_score)
    competitor_scores = _competitor_scores(competitor_results)
    competitors_analyzed = len(competitor_scores)

    base_payload: dict[str, object] = {
        "schema_version": COMPETITIVENESS_SCORE_SCHEMA_VERSION,
        "context_available": competitors_analyzed >= min_competitors,
        "score_basis": "primary_page_score",
        "primary_page_score": primary_page_score,
        "competitiveness_score": primary_page_score,
        "score_delta": 0.0,
        "requested_top_n": requested_top_n,
        "competitors_analyzed": competitors_analyzed,
        "required_competitors": min_competitors,
        "competitor_average_score": None,
        "competitor_best_score": None,
        "competitor_median_score": None,
        "average_score_gap": None,
        "best_score_gap": None,
        "score_percentile": None,
        "position_band": "not_enough_data",
    }

    if competitors_analyzed < min_competitors:
        base_payload["reason"] = "not_enough_processed_competitors"
        return base_payload

    average_score = float(fmean(competitor_scores))
    best_score = max(competitor_scores)
    median_score = float(median(competitor_scores))
    average_gap = primary_page_score - average_score
    best_gap = primary_page_score - best_score
    average_gap_strength = _gap_strength(average_gap, full_loss_gap=25.0)
    best_gap_strength = _gap_strength(best_gap, full_loss_gap=30.0)
    market_strength_score = (average_gap_strength * 0.62) + (best_gap_strength * 0.38)
    context_adjustment = _clip((average_gap * 0.12) + (best_gap * 0.08), -6.0, 4.0)
    competitiveness_score = _rounded_score((primary_page_score * 0.72) + (market_strength_score * 0.28) + context_adjustment)

    base_payload.update(
        {
            "score_basis": "competitiveness_score",
            "competitiveness_score": competitiveness_score,
            "score_delta": round(competitiveness_score - primary_page_score, 4),
            "competitor_average_score": _round_metric(average_score),
            "competitor_best_score": _round_metric(best_score),
            "competitor_median_score": _round_metric(median_score),
            "average_score_gap": _round_metric(average_gap),
            "best_score_gap": _round_metric(best_gap),
            "score_percentile": _score_percentile(primary_page_score, competitor_scores),
            "position_band": _position_band(average_gap=average_gap, best_gap=best_gap),
            "diagnostics": {
                "average_gap_strength_score": _round_metric(average_gap_strength),
                "best_gap_strength_score": _round_metric(best_gap_strength),
                "market_strength_score": _round_metric(market_strength_score),
                "context_adjustment": _round_metric(context_adjustment),
                "primary_weight": 0.72,
                "market_context_weight": 0.28,
            },
        }
    )
    return base_payload
