from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import get_settings


logger = logging.getLogger(__name__)

BLOCKED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".rar",
    ".7z",
    ".apk",
    ".dmg",
    ".exe",
}
BLOCKED_DOMAIN_MARKERS = (
    "youtube.",
    "youtu.be",
    "vk.com",
    "ok.ru",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "t.me",
    "reddit.com",
    "wikipedia.org",
    "2gis.",
    "maps.yandex.",
    "apple.com",
    "apps.apple.com",
    "play.google.com",
)
BLOCKED_PATH_MARKERS = (
    "/search",
    "/maps",
    "/map",
    "/video",
    "/videos",
    "/forum",
    "/thread",
    "/threads",
    "/community",
    "/wiki",
)
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
}


class SerpConfigurationError(RuntimeError):
    pass


class SerpProviderError(RuntimeError):
    pass


@dataclass(slots=True)
class SerpSearchResult:
    url: str
    title: str
    snippet: str
    rank: int
    serp_page: int

    def to_dict(self) -> dict[str, object]:
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "rank": self.rank,
            "serp_page": self.serp_page,
        }


def _normalize_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _is_valid_http_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def _is_excluded_url(url: str) -> bool:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = (parsed.path or "").lower()

    if not _is_valid_http_url(url):
        return True
    if any(marker in domain for marker in BLOCKED_DOMAIN_MARKERS):
        return True
    if any(marker in path for marker in BLOCKED_PATH_MARKERS):
        return True
    if any(path.endswith(extension) for extension in BLOCKED_EXTENSIONS):
        return True
    if domain.startswith("forum.") or ".forum." in domain:
        return True
    return False


def require_searxng_base_url() -> str:
    settings = get_settings()
    if settings.serp_provider != "searxng":
        raise SerpConfigurationError(
            f"Unsupported SERP provider '{settings.serp_provider}'. Expected 'searxng'."
        )
    if not settings.searxng_base_url:
        raise SerpConfigurationError(
            "SEARXNG_BASE_URL is not configured. Configure it to use the free SearxNG JSON API."
        )
    return settings.searxng_base_url.rstrip("/")


def _fetch_searxng_payload(base_url: str, params: dict[str, object]) -> dict[str, Any]:
    settings = get_settings()
    endpoint = f"{base_url}/search"
    with httpx.Client(
        timeout=settings.search_timeout,
        follow_redirects=True,
        headers=REQUEST_HEADERS,
    ) as client:
        response = client.get(endpoint, params=params)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise SerpProviderError("SearxNG returned a non-object payload.")
    return payload


def _normalize_results(payload: dict[str, Any], serp_page: int, top_n: int) -> list[dict[str, object]]:
    raw_results = payload.get("results", [])
    if not isinstance(raw_results, list):
        return []

    normalized: list[dict[str, object]] = []
    seen_urls: set[str] = set()
    rank_cursor = serp_page * top_n

    for item in raw_results:
        if not isinstance(item, dict):
            continue

        raw_url = str(item.get("url") or item.get("link") or "").strip()
        if not raw_url or _is_excluded_url(raw_url) or raw_url in seen_urls:
            continue

        seen_urls.add(raw_url)
        rank_cursor += 1
        result = SerpSearchResult(
            url=raw_url,
            title=str(item.get("title") or "").strip(),
            snippet=str(item.get("content") or item.get("snippet") or "").strip(),
            rank=rank_cursor,
            serp_page=serp_page,
        )
        normalized.append(result.to_dict())
        if len(normalized) >= top_n:
            break

    return normalized


def search(
    query: str,
    top_n: int,
    region_code: int | None = None,
    page: int = 0,
) -> list[dict[str, object]]:
    del region_code
    settings = get_settings()
    base_url = require_searxng_base_url()
    params: dict[str, object] = {
        "q": query,
        "format": "json",
        "categories": "general",
        "language": settings.searxng_language,
        "pageno": page + 1,
    }
    payload = _fetch_searxng_payload(base_url, params)
    results = _normalize_results(payload, serp_page=page, top_n=top_n)
    logger.info("SearxNG query='%s' page=%s returned %s usable results", query, page, len(results))
    return results[:top_n]
