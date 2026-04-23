from __future__ import annotations

import logging
import re
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from app.features import (
    build_features,
    detect_query_intent,
    merge_intent_alignment_features,
    merge_snapshot_auxiliary_features,
)
from app.ml.model import compare_with_competitors, predict_score
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


def analyze_competitor_page(result: dict[str, object], query: str) -> dict[str, object]:
    url = str(result["url"])
    query_intent = detect_query_intent(query)
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
    features = merge_intent_alignment_features(
        merge_snapshot_auxiliary_features(
            build_features(html=html, text=text, query=query),
            snapshot,
        ),
        query_intent,
    )
    score = predict_score(features)
    if not competitor_payload["title"]:
        competitor_payload["title"] = _extract_title(html)

    competitor_payload["score"] = score
    competitor_payload["features"] = features
    return competitor_payload


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


def build_competitor_results(query: str, target_url: str, top_n: int) -> list[dict[str, object]]:
    competitor_pages = search_competitor_pages(query=query, target_url=target_url, limit=top_n)
    results: list[dict[str, object]] = []

    for competitor_page in competitor_pages:
        try:
            results.append(analyze_competitor_page(competitor_page, query))
        except Exception as error:
            logger.warning("Competitor analysis failed for %s: %s", competitor_page.get("url"), error)
            results.append(build_failed_competitor_result(competitor_page, error))

    return results


def build_comparison_summary(
    user_features: dict[str, float | int],
    user_score: float,
    competitor_results: list[dict[str, object]],
    query_intent: dict[str, object] | None = None,
    serp_relative_summary: dict[str, object] | None = None,
) -> dict[str, object]:
    analyzed_results = [
        item
        for item in competitor_results
        if isinstance(item.get("features"), dict) and isinstance(item.get("score"), (int, float))
    ]
    competitor_features = [item["features"] for item in analyzed_results]

    if len(competitor_features) >= MIN_COMPETITORS_FOR_COMPARISON:
        comparison = compare_with_competitors(
            user_pages_features=[user_features],
            competitor_pages_features=competitor_features,
        )
        competitors_average_score = float(comparison["competitors_average_score"])
        score_difference = float(comparison["score_difference"])
    else:
        competitors_average_score = 0.0
        score_difference = 0.0

    competitors_found = len(competitor_results)
    competitors_analyzed = len(analyzed_results)
    competitors_failed = competitors_found - competitors_analyzed

    return {
        "user_score": round(user_score, 4),
        "competitors_average_score": competitors_average_score,
        "score_difference": score_difference,
        "competitors_count": competitors_analyzed,
        "competitors_found": competitors_found,
        "competitors_analyzed": competitors_analyzed,
        "competitors_failed": competitors_failed,
        "query_intent": query_intent if isinstance(query_intent, dict) else None,
        "serp_relative_summary": serp_relative_summary if isinstance(serp_relative_summary, dict) else None,
    }


def _extract_title(html: str) -> str:
    match = re.search(r"<title\b[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()
