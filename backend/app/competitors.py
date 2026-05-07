from __future__ import annotations

import logging
import re
from statistics import fmean
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.features import (
    build_features,
    detect_query_intent,
    merge_intent_alignment_features,
    merge_snapshot_auxiliary_features,
)
from app.competitiveness import build_competitiveness_score
from app.ml.model import predict_score
from app.parser import ensure_extraction_artifact, fetch_page
from app.serp import SerpConfigurationError, SerpProviderError, search as search_serp


logger = logging.getLogger(__name__)

SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
}

SEARCH_SOURCES = [
    {"name": "duckduckgo-lite", "url": "https://lite.duckduckgo.com/lite/", "kind": "duckduckgo"},
    {"name": "duckduckgo-html", "url": "https://html.duckduckgo.com/html/", "kind": "duckduckgo"},
    {"name": "brave-html", "url": "https://search.brave.com/search", "kind": "brave"},
]
SEARCH_ENGINE_DOMAINS = {"duckduckgo.com", "brave.com", "serpapi.com"}
MIN_COMPETITORS_FOR_COMPARISON = 2
MIN_ACCEPTED_COMPETITOR_SCORE = 10.0
MAX_COMPETITOR_CANDIDATE_LIMIT = 100
MIN_COMPETITOR_REPLACEMENT_RESERVE = 3
MAX_COMPETITOR_REPLACEMENT_RESERVE = 10
SUSPICIOUS_FETCH_ERROR_CODES = {
    "http_401",
    "http_403",
    "http_429",
    "browser_blocked",
    "bot_protection_suspected",
    "captcha_detected",
    "access_denied",
}
RENDER_LIMITED_FETCH_ERROR_CODES = {
    "javascript_required",
    "browser_fetch_failed",
    "browser_timeout",
    "browser_unavailable",
}
THIN_FETCH_ERROR_CODES = {"empty_content"}


def _normalize_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _is_search_engine_domain(domain: str) -> bool:
    return any(domain == root or domain.endswith(f".{root}") for root in SEARCH_ENGINE_DOMAINS)


def _extract_result_url(raw_url: str) -> str:
    cleaned_url = unescape(raw_url)
    if "uddg=" not in cleaned_url:
        return cleaned_url

    parsed = urlparse(cleaned_url)
    uddg = parse_qs(parsed.query).get("uddg", [])
    if not uddg:
        return cleaned_url
    return unquote(uddg[0])


def _extract_duckduckgo_links(html: str) -> list[str]:
    return [
        href
        for href in re.findall(r'<a[^>]+href="([^"]+)"', html, flags=re.IGNORECASE)
        if "uddg=" in href or href.startswith(("http://", "https://"))
    ]


def _extract_brave_links(html: str) -> list[str]:
    return [
        match.rstrip("&quot;").rstrip('",')
        for match in re.findall(r"https://[^\"'<>\\s]+", html, flags=re.IGNORECASE)
    ]


def _extract_links(html: str, kind: str) -> list[str]:
    if kind == "duckduckgo":
        return _extract_duckduckgo_links(html)
    if kind == "brave":
        return _extract_brave_links(html)
    return []


def search_serp_urls(
    query: str,
    limit: int,
    exclude_domain: str | None = None,
    unique_domains: bool = True,
) -> list[str]:
    results: list[str] = []
    seen_domains: set[str] = set()
    normalized_exclude_domain = (exclude_domain or "").lower().removeprefix("www.")

    def append_matches(matches: list[str]) -> None:
        for match in matches:
            candidate_url = _extract_result_url(match)
            candidate_domain = _normalize_domain(candidate_url)
            if not candidate_domain:
                continue
            if "." not in candidate_domain or candidate_domain.endswith("."):
                continue
            if len(candidate_domain.rsplit(".", maxsplit=1)[-1]) < 2:
                continue
            if not candidate_url.startswith(("http://", "https://")):
                continue
            if _is_search_engine_domain(candidate_domain):
                continue
            if normalized_exclude_domain and candidate_domain == normalized_exclude_domain:
                continue
            if unique_domains and candidate_domain in seen_domains:
                continue

            seen_domains.add(candidate_domain)
            results.append(candidate_url)
            if len(results) >= limit:
                break

    with httpx.Client(
        follow_redirects=True,
        timeout=15.0,
        headers=SEARCH_HEADERS,
    ) as client:
        for source in SEARCH_SOURCES:
            try:
                response = client.get(source["url"], params={"q": query})
                response.raise_for_status()
            except httpx.HTTPError:
                continue

            matches = _extract_links(response.text, source["kind"])
            append_matches(matches)
            if len(results) >= limit:
                break

    return results[:limit]


def _normalize_provider_results(
    query: str,
    target_url: str,
    limit: int,
) -> list[dict[str, object]]:
    target_domain = _normalize_domain(target_url)
    seen_domains: set[str] = set()
    normalized_results: list[dict[str, object]] = []
    page = 0

    while len(normalized_results) < limit and page < 3:
        raw_results = search_serp(query=query, top_n=max(limit * 2, 10), page=page)
        if not raw_results:
            break

        for result in raw_results:
            url = str(result.get("url") or "").strip()
            domain = _normalize_domain(url)
            if not domain or domain == target_domain or domain in seen_domains:
                continue

            seen_domains.add(domain)
            normalized_results.append(
                {
                    "url": url,
                    "domain": domain,
                    "title": str(result.get("title") or "").strip(),
                    "snippet": str(result.get("snippet") or "").strip(),
                    "rank": int(result.get("rank") or (len(normalized_results) + 1)),
                    "serp_page": int(result.get("serp_page") or page),
                }
            )
            if len(normalized_results) >= limit:
                break

        page += 1

    return normalized_results[:limit]


def search_competitor_pages(
    query: str,
    target_url: str,
    limit: int,
) -> list[dict[str, object]]:
    try:
        results = _normalize_provider_results(query=query, target_url=target_url, limit=limit)
        if results:
            return results
    except (SerpConfigurationError, SerpProviderError, httpx.HTTPError, ValueError) as error:
        logger.warning("Falling back to HTML SERP scraping for competitors: %s", error)

    fallback_urls = search_serp_urls(
        query=query,
        limit=limit,
        exclude_domain=_normalize_domain(target_url),
        unique_domains=True,
    )
    return [
        {
            "url": url,
            "domain": _normalize_domain(url) or url,
            "title": "",
            "snippet": "",
            "rank": index,
            "serp_page": 0,
        }
        for index, url in enumerate(fallback_urls, start=1)
    ]


def search_competitor_urls(query: str, target_url: str, limit: int) -> list[str]:
    return [str(item["url"]) for item in search_competitor_pages(query=query, target_url=target_url, limit=limit)]


def build_competitor_candidate_limit(requested_top_n: int | None) -> int:
    requested = requested_top_n if isinstance(requested_top_n, int) and requested_top_n > 0 else 10
    requested = min(requested, MAX_COMPETITOR_CANDIDATE_LIMIT)
    available_reserve = max(0, MAX_COMPETITOR_CANDIDATE_LIMIT - requested)
    reserve = min(
        max(MIN_COMPETITOR_REPLACEMENT_RESERVE, (requested + 1) // 2),
        MAX_COMPETITOR_REPLACEMENT_RESERVE,
        available_reserve,
    )
    return requested + reserve


def fetch_competitor_page(result: dict[str, object]) -> dict[str, object]:
    url = str(result["url"])
    fetch_result = fetch_page(url)

    competitor_payload: dict[str, object] = {
        "url": url,
        "domain": _normalize_domain(url) or url,
        "title": str(result.get("title") or "").strip(),
        "snippet": str(result.get("snippet") or "").strip(),
        "serp_rank": int(result.get("rank") or 0),
        "serp_page": int(result.get("serp_page") or 0),
        "fetch_status": str(fetch_result["status"]),
        "fetch_method": fetch_result.get("fetch_method"),
        "fetch_error_code": fetch_result.get("fetch_error_code"),
        "fetch_error_message": fetch_result.get("fetch_error_message"),
        "score": None,
        "features": None,
        "snapshot": None,
    }

    if fetch_result["status"] != "success":
        return competitor_payload

    html = str(fetch_result.get("html") or "")
    text = str(fetch_result.get("text") or "")
    snapshot = ensure_extraction_artifact(
        requested_url=url,
        artifact=fetch_result.get("snapshot") if isinstance(fetch_result.get("snapshot"), dict) else None,
        final_url=str(fetch_result.get("final_url") or url),
        status_code=int(fetch_result.get("http_status")) if isinstance(fetch_result.get("http_status"), (int, float)) else None,
        response_headers=fetch_result.get("response_headers") if isinstance(fetch_result.get("response_headers"), dict) else {},
        html=html or None,
        extracted_text=text or None,
        fetch_method=str(fetch_result.get("fetch_method") or "") or None,
        redirect_chain=fetch_result.get("redirect_chain") if isinstance(fetch_result.get("redirect_chain"), list) else [],
    )
    competitor_payload["snapshot"] = snapshot
    if not competitor_payload["title"]:
        competitor_payload["title"] = _extract_title(html)
    return competitor_payload


def analyze_competitor_snapshot(
    result: dict[str, object],
    query: str,
    snapshot: dict[str, object] | None,
) -> dict[str, object]:
    if not isinstance(snapshot, dict):
        raise RuntimeError("Competitor page snapshot is not available for heavy analysis")

    url = str(result["url"])
    query_intent = detect_query_intent(query)
    normalized_snapshot = ensure_extraction_artifact(
        requested_url=url,
        artifact=snapshot,
        final_url=str(snapshot.get("final_url") or url),
        html=str(snapshot.get("html") or "") or None,
        extracted_text=str(snapshot.get("text") or "") or None,
        fetch_method=str(snapshot.get("fetch_method") or "") or None,
    )
    html = str(normalized_snapshot.get("html") or "")
    text = str(normalized_snapshot.get("text") or "")
    analysis_text = _build_competitor_analysis_text(text, result)
    semantic_features = snapshot.get("semantic_features") if isinstance(snapshot.get("semantic_features"), dict) else None
    features = merge_intent_alignment_features(
        merge_snapshot_auxiliary_features(
            build_features(html=html, text=analysis_text, query=query, semantic_features=semantic_features),
            normalized_snapshot,
        ),
        query_intent,
    )
    score = predict_score(features)
    return {
        "url": url,
        "domain": str(result.get("domain") or _normalize_domain(url) or url),
        "title": str(result.get("title") or "").strip() or _extract_title(html),
        "snippet": str(result.get("snippet") or "").strip(),
        "serp_rank": int(result.get("rank") or result.get("serp_rank") or 0),
        "serp_page": int(result.get("serp_page") or 0),
        "fetch_status": str(result.get("fetch_status") or "success"),
        "fetch_method": result.get("fetch_method") or normalized_snapshot.get("fetch_method"),
        "fetch_error_code": result.get("fetch_error_code"),
        "fetch_error_message": result.get("fetch_error_message"),
        "score": score,
        "features": features,
    }


def analyze_competitor_page(result: dict[str, object], query: str) -> dict[str, object]:
    fetch_payload = fetch_competitor_page(result)
    if fetch_payload["fetch_status"] != "success":
        fetch_payload.pop("snapshot", None)
        return fetch_payload
    snapshot = fetch_payload.get("snapshot") if isinstance(fetch_payload.get("snapshot"), dict) else None
    return analyze_competitor_snapshot(fetch_payload, query, snapshot)


def build_failed_competitor_result(
    result: dict[str, object],
    error: Exception | str,
    *,
    fetch_error_code: str = "unknown_fetch_error",
    fetch_method: str | None = None,
) -> dict[str, object]:
    return {
        "url": str(result.get("url") or ""),
        "domain": str(result.get("domain") or ""),
        "title": str(result.get("title") or ""),
        "snippet": str(result.get("snippet") or ""),
        "serp_rank": int(result.get("rank") or 0),
        "serp_page": int(result.get("serp_page") or 0),
        "fetch_status": "failed",
        "fetch_method": fetch_method,
        "fetch_error_code": fetch_error_code,
        "fetch_error_message": str(error),
        "score": None,
        "features": None,
    }


def _safe_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _competitor_discard_reason(item: dict[str, object]) -> str | None:
    fetch_error_code = str(item.get("fetch_error_code") or "").strip().lower()
    fetch_status = str(item.get("fetch_status") or "").strip().lower()
    features = item.get("features") if isinstance(item.get("features"), dict) else None
    score = _safe_float(item.get("score"))

    if fetch_error_code in SUSPICIOUS_FETCH_ERROR_CODES:
        return "bot_block_suspected"
    if fetch_error_code in RENDER_LIMITED_FETCH_ERROR_CODES:
        return "render_limited"
    if fetch_error_code in THIN_FETCH_ERROR_CODES:
        return "thin_content"
    if fetch_status and fetch_status != "success" and (features is None or score is None):
        return "fetch_failed"
    if features is None or score is None:
        return "not_analyzed"
    if score < MIN_ACCEPTED_COMPETITOR_SCORE:
        return "score_below_minimum"

    word_count = _safe_float(features.get("word_count"))
    text_length_chars = _safe_float(features.get("text_length_chars"))
    if (
        word_count is not None
        and text_length_chars is not None
        and word_count < 20.0
        and text_length_chars < 200.0
    ):
        return "thin_content"

    return None


def _annotate_competitor_context(
    item: dict[str, object],
    *,
    status: str,
    candidate_index: int,
    discard_reason: str | None = None,
    replacement_candidate: bool = False,
) -> dict[str, object]:
    annotated = dict(item)
    annotated["competitor_context_status"] = status
    annotated["candidate_index"] = candidate_index
    if discard_reason:
        annotated["discard_reason"] = discard_reason
    else:
        annotated.pop("discard_reason", None)
    if replacement_candidate:
        annotated["replacement_candidate"] = True
    else:
        annotated.pop("replacement_candidate", None)
    return annotated


def select_competitor_context_candidates(
    competitor_results: list[dict[str, object]],
    *,
    requested_top_n: int | None = None,
) -> dict[str, object]:
    requested = requested_top_n if isinstance(requested_top_n, int) and requested_top_n > 0 else None
    accepted_results: list[dict[str, object]] = []
    annotated_results: list[dict[str, object]] = []
    discard_reasons: dict[str, int] = {}
    replacement_attempts = 0
    replacements_used = 0
    unused_candidates = 0

    for index, raw_item in enumerate(competitor_results, start=1):
        item = dict(raw_item)
        discard_reason = _competitor_discard_reason(item)
        if discard_reason:
            discard_reasons[discard_reason] = discard_reasons.get(discard_reason, 0) + 1
            if requested is not None and len(accepted_results) < requested:
                replacement_attempts += 1
            annotated_results.append(
                _annotate_competitor_context(
                    item,
                    status="discarded",
                    candidate_index=index,
                    discard_reason=discard_reason,
                )
            )
            continue

        if requested is None or len(accepted_results) < requested:
            replacement_candidate = requested is not None and index > requested
            annotated = _annotate_competitor_context(
                item,
                status="accepted",
                candidate_index=index,
                replacement_candidate=replacement_candidate,
            )
            if replacement_candidate:
                replacements_used += 1
            accepted_results.append(annotated)
            annotated_results.append(annotated)
            continue

        unused_candidates += 1
        annotated_results.append(
            _annotate_competitor_context(
                item,
                status="unused",
                candidate_index=index,
            )
        )

    return {
        "requested_top_n": requested_top_n,
        "collected_candidates": len(competitor_results),
        "accepted_competitors": len(accepted_results),
        "discarded_competitors": sum(discard_reasons.values()),
        "unused_candidates": unused_candidates,
        "replacement_attempts": replacement_attempts,
        "replacements_used": replacements_used,
        "discard_reasons": discard_reasons,
        "accepted_results": accepted_results,
        "annotated_results": annotated_results,
    }


def build_competitor_results(query: str, target_url: str, top_n: int) -> list[dict[str, object]]:
    competitor_pages = search_competitor_pages(
        query=query,
        target_url=target_url,
        limit=build_competitor_candidate_limit(top_n),
    )
    results: list[dict[str, object]] = []

    for competitor_page in competitor_pages:
        try:
            results.append(analyze_competitor_page(competitor_page, query))
        except Exception as error:
            logger.warning("Competitor analysis failed for %s: %s", competitor_page.get("url"), error)
            results.append(build_failed_competitor_result(competitor_page, error))

    return results


def build_competitor_context_quality(
    competitor_results: list[dict[str, object]],
    *,
    requested_top_n: int | None = None,
    min_competitors: int = MIN_COMPETITORS_FOR_COMPARISON,
) -> dict[str, object]:
    selection = select_competitor_context_candidates(competitor_results, requested_top_n=requested_top_n)
    found = int(selection["collected_candidates"])
    analyzed = int(selection["accepted_competitors"])
    failed = int(selection["discarded_competitors"])
    requested = requested_top_n if isinstance(requested_top_n, int) and requested_top_n > 0 else None
    expected_context = requested or max(found, min_competitors)
    coverage_ratio = round(analyzed / expected_context, 4) if expected_context else 0.0
    fetch_error_codes: dict[str, int] = {}
    for item in competitor_results:
        discard_reason = _competitor_discard_reason(dict(item))
        if discard_reason is None:
            continue
        code = (
            str(item.get("fetch_error_code") or "").strip()
            or (discard_reason if str(item.get("fetch_status") or "").strip().lower() == "success" else "")
            or str(item.get("fetch_status") or "").strip()
            or "unknown"
        )
        fetch_error_codes[code] = fetch_error_codes.get(code, 0) + 1

    if found == 0:
        status = "no_serp_results"
    elif analyzed < min_competitors:
        status = "insufficient_processed_competitors"
    elif requested is not None and analyzed >= requested:
        status = "ready"
    elif failed > 0:
        status = "partial_but_usable"
    else:
        status = "ready"

    return {
        "schema_version": "competitor-context-quality-v2",
        "status": status,
        "context_available": analyzed >= min_competitors,
        "score_safe_to_compare": analyzed >= min_competitors,
        "competitors_found": found,
        "competitors_analyzed": analyzed,
        "competitors_failed": failed,
        "required_competitors": min_competitors,
        "requested_top_n": requested_top_n,
        "collected_candidates": found,
        "accepted_competitors": analyzed,
        "discarded_competitors": failed,
        "replacement_attempts": selection["replacement_attempts"],
        "replacements_used": selection["replacements_used"],
        "unused_candidates": selection["unused_candidates"],
        "discard_reasons": selection["discard_reasons"],
        "coverage_ratio": coverage_ratio,
        "fetch_error_codes": fetch_error_codes,
    }


def build_comparison_summary(
    user_features: dict[str, float | int],
    user_score: float,
    competitor_results: list[dict[str, object]],
    query_intent: dict[str, object] | None = None,
    serp_relative_summary: dict[str, object] | None = None,
    requested_top_n: int | None = None,
) -> dict[str, object]:
    selection = select_competitor_context_candidates(competitor_results, requested_top_n=requested_top_n)
    analyzed_results = list(selection["accepted_results"])
    competitor_scores = [float(item["score"]) for item in analyzed_results if isinstance(item.get("score"), (int, float))]

    competitors_average_score: float | None = None
    score_difference: float | None = None
    if len(competitor_scores) >= MIN_COMPETITORS_FOR_COMPARISON:
        competitors_average_score = round(float(fmean(competitor_scores)), 4)
        score_difference = round(float(user_score) - competitors_average_score, 4)

    competitor_context_quality = build_competitor_context_quality(
        competitor_results,
        requested_top_n=requested_top_n,
        min_competitors=MIN_COMPETITORS_FOR_COMPARISON,
    )
    competitors_found = int(competitor_context_quality["collected_candidates"])
    competitors_analyzed = int(competitor_context_quality["accepted_competitors"])
    competitors_failed = int(competitor_context_quality["discarded_competitors"])
    competitiveness = build_competitiveness_score(
        user_score=user_score,
        competitor_results=analyzed_results,
        requested_top_n=requested_top_n,
        min_competitors=MIN_COMPETITORS_FOR_COMPARISON,
    )
    competitiveness_score = float(competitiveness["competitiveness_score"])
    primary_score_difference = (
        round(float(user_score) - competitors_average_score, 4)
        if competitors_analyzed >= MIN_COMPETITORS_FOR_COMPARISON and competitors_average_score is not None
        else score_difference
    )
    displayed_score_difference = (
        round(competitiveness_score - competitors_average_score, 4)
        if competitors_analyzed >= MIN_COMPETITORS_FOR_COMPARISON and competitors_average_score is not None
        else score_difference
    )

    return {
        "user_score": round(competitiveness_score, 4),
        "primary_page_score": round(user_score, 4),
        "competitiveness_score": round(competitiveness_score, 4),
        "score_basis": competitiveness.get("score_basis"),
        "competitors_average_score": competitors_average_score,
        "score_difference": displayed_score_difference,
        "primary_score_difference": primary_score_difference,
        "competitors_count": competitors_analyzed,
        "competitors_found": competitors_found,
        "competitors_analyzed": competitors_analyzed,
        "competitors_failed": competitors_failed,
        "requested_top_n": competitor_context_quality["requested_top_n"],
        "collected_candidates": competitor_context_quality["collected_candidates"],
        "accepted_competitors": competitor_context_quality["accepted_competitors"],
        "discarded_competitors": competitor_context_quality["discarded_competitors"],
        "replacement_attempts": competitor_context_quality["replacement_attempts"],
        "discard_reasons": competitor_context_quality["discard_reasons"],
        "competitor_context_status": competitor_context_quality["status"],
        "competitor_context_quality": competitor_context_quality,
        "competitor_best_score": competitiveness.get("competitor_best_score"),
        "competitor_median_score": competitiveness.get("competitor_median_score"),
        "competitiveness_position_band": competitiveness.get("position_band"),
        "competitiveness_score_delta": competitiveness.get("score_delta"),
        "score_percentile": competitiveness.get("score_percentile"),
        "competitiveness": competitiveness,
        "query_intent": query_intent if isinstance(query_intent, dict) else None,
        "serp_relative_summary": serp_relative_summary if isinstance(serp_relative_summary, dict) else None,
    }


def _extract_title(html: str) -> str:
    match = re.search(r"<title\b[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _build_competitor_analysis_text(text: str, result: dict[str, object]) -> str:
    """Use SERP title/snippet as query context when fetched competitor text is thin."""

    parts = [text.strip()]
    for key in ("title", "snippet"):
        value = str(result.get(key) or "").strip()
        if value:
            parts.append(value)

    url = str(result.get("url") or "").strip()
    if url:
        parsed = urlparse(url)
        url_context = " ".join(
            part
            for part in [
                parsed.netloc.removeprefix("www."),
                unquote(parsed.path).replace("-", " ").replace("_", " "),
                unquote(parsed.query).replace("+", " "),
            ]
            if part
        )
        if url_context:
            parts.append(url_context)

    return "\n".join(part for part in parts if part).strip()
