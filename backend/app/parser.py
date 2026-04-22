from __future__ import annotations

from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
import logging
import re
import time
from typing import Any

import httpx


logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

HTTP_TIMEOUT = httpx.Timeout(connect=12.0, read=20.0, write=20.0, pool=12.0)

FEATURE_SCHEMA_VERSION = "v2"
EXTRACTION_ARTIFACT_VERSION = "extraction-v2"

FetchResult = dict[str, object]


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


class _DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._text_chunks: list[str] = []
        self._capture_stack: list[tuple[str, dict[str, str], list[str]]] = []
        self._json_ld_buffer: list[str] | None = None

        self.lang = ""
        self.title = ""
        self.meta_description = ""
        self.meta_robots = ""
        self.viewport = ""
        self.canonical = ""
        self.json_ld: list[str] = []
        self.hreflang_links: list[dict[str, str]] = []
        self.links: list[dict[str, str]] = []
        self.button_texts: list[str] = []
        self.h1_texts: list[str] = []
        self.h2_texts: list[str] = []
        self.h3_texts: list[str] = []
        self.counts = {
            "paragraph": 0,
            "h1": 0,
            "h2": 0,
            "h3": 0,
            "link": 0,
            "image": 0,
            "list_item": 0,
            "strong": 0,
            "form": 0,
            "input": 0,
        }

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:  # type: ignore[override]
        normalized_tag = tag.lower()
        attrs_map = {str(key).lower(): str(value or "").strip() for key, value in attrs}

        if normalized_tag == "html" and not self.lang:
            self.lang = attrs_map.get("lang", "")

        if normalized_tag == "meta":
            name = attrs_map.get("name", "").lower()
            content = attrs_map.get("content", "")
            if name == "description" and content and not self.meta_description:
                self.meta_description = _collapse_whitespace(content)
            elif name == "robots" and content and not self.meta_robots:
                self.meta_robots = _collapse_whitespace(content)
            elif name == "viewport" and content and not self.viewport:
                self.viewport = _collapse_whitespace(content)

        if normalized_tag == "link":
            rel_tokens = {token.strip().lower() for token in attrs_map.get("rel", "").split() if token.strip()}
            href = attrs_map.get("href", "")
            if "canonical" in rel_tokens and href and not self.canonical:
                self.canonical = href
            hreflang = attrs_map.get("hreflang", "")
            if hreflang and href:
                self.hreflang_links.append({"hreflang": hreflang, "href": href})

        if normalized_tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            if normalized_tag == "script" and "application/ld+json" in attrs_map.get("type", "").lower():
                self._json_ld_buffer = []

        if normalized_tag in {"title", "h1", "h2", "h3", "a", "button"}:
            self._capture_stack.append((normalized_tag, dict(attrs_map), []))

        if normalized_tag == "p":
            self.counts["paragraph"] += 1
        elif normalized_tag == "h1":
            self.counts["h1"] += 1
        elif normalized_tag == "h2":
            self.counts["h2"] += 1
        elif normalized_tag == "h3":
            self.counts["h3"] += 1
        elif normalized_tag == "a":
            self.counts["link"] += 1
        elif normalized_tag == "img":
            self.counts["image"] += 1
        elif normalized_tag == "li":
            self.counts["list_item"] += 1
        elif normalized_tag in {"strong", "b"}:
            self.counts["strong"] += 1
        elif normalized_tag == "form":
            self.counts["form"] += 1
        elif normalized_tag == "input":
            self.counts["input"] += 1

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        normalized_tag = tag.lower()

        if normalized_tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
            if normalized_tag == "script" and self._json_ld_buffer is not None:
                content = _collapse_whitespace(" ".join(self._json_ld_buffer))
                if content:
                    self.json_ld.append(content)
                self._json_ld_buffer = None

        if self._capture_stack and self._capture_stack[-1][0] == normalized_tag:
            _captured_tag, attrs_map, buffer = self._capture_stack.pop()
            captured_text = _collapse_whitespace(" ".join(buffer))
            if normalized_tag == "a":
                href = attrs_map.get("href", "")
                if href or captured_text:
                    self.links.append(
                        {
                            "href": href,
                            "text": captured_text,
                            "rel": attrs_map.get("rel", ""),
                        }
                    )
                return
            if normalized_tag == "button":
                if captured_text:
                    self.button_texts.append(captured_text)
                return
            if not captured_text:
                return
            if normalized_tag == "title" and not self.title:
                self.title = captured_text
            elif normalized_tag == "h1":
                self.h1_texts.append(captured_text)
            elif normalized_tag == "h2":
                self.h2_texts.append(captured_text)
            elif normalized_tag == "h3":
                self.h3_texts.append(captured_text)

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        normalized = _collapse_whitespace(data)
        if not normalized:
            return

        if self._json_ld_buffer is not None:
            self._json_ld_buffer.append(data)

        if self._skip_depth == 0:
            self._text_chunks.append(normalized)
            for _tag, _attrs, buffer in self._capture_stack:
                buffer.append(normalized)

    def as_document(self) -> dict[str, object]:
        text = _collapse_whitespace(" ".join(self._text_chunks))
        return {
            "text": text,
            "title": self.title,
            "meta_description": self.meta_description,
            "meta_robots": self.meta_robots,
            "viewport": self.viewport,
            "canonical": self.canonical,
            "lang": self.lang,
            "json_ld": list(self.json_ld),
            "hreflang_links": list(self.hreflang_links),
            "links": list(self.links),
            "button_texts": list(self.button_texts),
            "h1_texts": list(self.h1_texts),
            "h2_texts": list(self.h2_texts),
            "h3_texts": list(self.h3_texts),
            "counts": dict(self.counts),
        }


def extract_document(html: str) -> dict[str, object]:
    parser = _DocumentParser()
    parser.feed(html)
    parser.close()
    return parser.as_document()


def extract_text(html: str) -> str:
    document = extract_document(html)
    return str(document.get("text") or "")


def _normalize_headers(headers: Any) -> dict[str, str]:
    if not isinstance(headers, dict):
        try:
            items = dict(headers)
        except Exception:
            return {}
    else:
        items = headers

    normalized: dict[str, str] = {}
    for key, value in items.items():
        rendered_key = str(key).strip()
        if not rendered_key:
            continue
        normalized[rendered_key] = str(value).strip()
    return normalized


def _normalize_redirect_chain(redirect_chain: Any) -> list[dict[str, object]]:
    if not isinstance(redirect_chain, list):
        return []

    normalized: list[dict[str, object]] = []
    for item in redirect_chain:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        raw_status = item.get("status_code")
        status_code = int(raw_status) if isinstance(raw_status, (int, float)) else None
        normalized.append(
            {
                "url": url,
                "status_code": status_code,
            }
        )
    return normalized


def build_extraction_artifact(
    *,
    requested_url: str,
    final_url: str | None,
    status_code: int | None,
    response_headers: Any,
    response_time_ms: float | int | None,
    html: str | None,
    fetch_method: str | None,
    fetched_at: str | None = None,
    redirect_chain: Any = None,
    extracted_text: str | None = None,
) -> dict[str, object]:
    normalized_html = str(html or "") or None
    document = extract_document(normalized_html or "")
    parsed_text = str(document.get("text") or "") or None
    normalized_text = str(extracted_text or "").strip() or parsed_text
    normalized_json_ld = list(document.get("json_ld") or [])
    document_payload = {
        "title": str(document.get("title") or ""),
        "meta_description": str(document.get("meta_description") or ""),
        "meta_robots": str(document.get("meta_robots") or ""),
        "viewport": str(document.get("viewport") or ""),
        "canonical": str(document.get("canonical") or ""),
        "lang": str(document.get("lang") or ""),
        "hreflang_links": list(document.get("hreflang_links") or []),
        "links": list(document.get("links") or []),
        "button_texts": list(document.get("button_texts") or []),
        "h1_texts": list(document.get("h1_texts") or []),
        "h2_texts": list(document.get("h2_texts") or []),
        "h3_texts": list(document.get("h3_texts") or []),
        "counts": dict(document.get("counts") or {}),
    }

    normalized_status_code = int(status_code) if isinstance(status_code, (int, float)) else None
    normalized_response_time_ms = (
        round(float(response_time_ms), 4) if isinstance(response_time_ms, (int, float)) else None
    )

    return {
        "artifact_version": EXTRACTION_ARTIFACT_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "requested_url": str(requested_url),
        "final_url": str(final_url or requested_url),
        "status_code": normalized_status_code,
        "redirect_chain": _normalize_redirect_chain(redirect_chain),
        "response_headers": _normalize_headers(response_headers),
        "response_time_ms": normalized_response_time_ms,
        "fetch_method": str(fetch_method or "") or None,
        "fetched_at": fetched_at or datetime.now(UTC).isoformat(),
        "html": normalized_html,
        "text": normalized_text,
        "json_ld": normalized_json_ld,
        "document": document_payload,
    }


def ensure_extraction_artifact(
    *,
    requested_url: str,
    artifact: dict[str, object] | None = None,
    final_url: str | None = None,
    status_code: int | None = None,
    response_headers: Any = None,
    response_time_ms: float | int | None = None,
    html: str | None = None,
    extracted_text: str | None = None,
    fetch_method: str | None = None,
    fetched_at: str | None = None,
    redirect_chain: Any = None,
) -> dict[str, object]:
    source_artifact = artifact if isinstance(artifact, dict) else {}
    source_status_code = source_artifact.get("status_code")
    source_response_time_ms = source_artifact.get("response_time_ms")

    normalized_artifact = build_extraction_artifact(
        requested_url=str(source_artifact.get("requested_url") or requested_url),
        final_url=str(source_artifact.get("final_url") or final_url or requested_url),
        status_code=(int(source_status_code) if isinstance(source_status_code, (int, float)) else status_code),
        response_headers=(source_artifact.get("response_headers") or response_headers or {}),
        response_time_ms=(
            source_response_time_ms if isinstance(source_response_time_ms, (int, float)) else response_time_ms
        ),
        html=(source_artifact.get("html") if isinstance(source_artifact.get("html"), str) else html),
        extracted_text=(
            source_artifact.get("text") if isinstance(source_artifact.get("text"), str) else extracted_text
        ),
        fetch_method=str(source_artifact.get("fetch_method") or fetch_method or "") or None,
        fetched_at=str(source_artifact.get("fetched_at") or fetched_at or "") or None,
        redirect_chain=(source_artifact.get("redirect_chain") or redirect_chain or []),
    )
    source_json_ld = source_artifact.get("json_ld")
    if isinstance(source_json_ld, list) and source_json_ld and not normalized_artifact.get("json_ld"):
        normalized_artifact["json_ld"] = [str(item) for item in source_json_ld]
    return normalized_artifact


def extraction_artifact_text(artifact: dict[str, object] | None) -> str:
    if not isinstance(artifact, dict):
        return ""
    return str(artifact.get("text") or "")


def extraction_artifact_html(artifact: dict[str, object] | None) -> str:
    if not isinstance(artifact, dict):
        return ""
    return str(artifact.get("html") or "")


def ensure_fetch_result_snapshot(result: FetchResult, requested_url: str) -> FetchResult:
    snapshot = ensure_extraction_artifact(
        requested_url=requested_url,
        artifact=result.get("snapshot") if isinstance(result.get("snapshot"), dict) else None,
        final_url=str(result.get("final_url") or requested_url),
        status_code=int(result.get("http_status")) if isinstance(result.get("http_status"), (int, float)) else None,
        html=str(result.get("html") or "") or None,
        extracted_text=str(result.get("text") or "") or None,
        fetch_method=str(result.get("fetch_method") or "") or None,
    )
    result["snapshot"] = snapshot
    result["final_url"] = str(snapshot.get("final_url") or requested_url)
    result["http_status"] = snapshot.get("status_code")
    result["html"] = snapshot.get("html")
    result["text"] = snapshot.get("text")
    return result


def summarize_extraction_artifact(artifact: dict[str, object] | None) -> dict[str, object] | None:
    if not isinstance(artifact, dict):
        return None

    normalized = ensure_extraction_artifact(
        requested_url=str(artifact.get("requested_url") or artifact.get("final_url") or ""),
        artifact=artifact,
    )
    document = normalized.get("document") if isinstance(normalized.get("document"), dict) else {}
    json_ld = normalized.get("json_ld") if isinstance(normalized.get("json_ld"), list) else []
    html = str(normalized.get("html") or "")
    text = str(normalized.get("text") or "")

    return {
        "artifact_version": normalized.get("artifact_version"),
        "feature_schema_version": normalized.get("feature_schema_version"),
        "requested_url": normalized.get("requested_url"),
        "final_url": normalized.get("final_url"),
        "status_code": normalized.get("status_code"),
        "fetch_method": normalized.get("fetch_method"),
        "fetched_at": normalized.get("fetched_at"),
        "response_time_ms": normalized.get("response_time_ms"),
        "redirect_chain": normalized.get("redirect_chain"),
        "response_headers": normalized.get("response_headers"),
        "title": document.get("title"),
        "canonical": document.get("canonical"),
        "lang": document.get("lang"),
        "html_present": bool(html),
        "html_length_chars": len(html),
        "text_length_chars": len(text),
        "json_ld_count": len(json_ld),
    }


def _empty_fetch_result(url: str) -> FetchResult:
    return {
        "status": "failed",
        "fetch_method": None,
        "fetch_error_code": None,
        "fetch_error_message": None,
        "final_url": url,
        "http_status": None,
        "html": None,
        "text": None,
        "snapshot": None,
    }


def _response_headers_from_httpx(response: httpx.Response | None) -> dict[str, str]:
    if response is None:
        return {}
    return _normalize_headers(getattr(response, "headers", {}))


def _response_headers_from_browser_response(response: Any) -> dict[str, str]:
    if response is None:
        return {}

    all_headers = getattr(response, "all_headers", None)
    if callable(all_headers):
        try:
            raw_headers = all_headers()
            if isinstance(raw_headers, dict):
                return _normalize_headers(raw_headers)
        except Exception:
            pass

    headers = getattr(response, "headers", None)
    if isinstance(headers, dict):
        return _normalize_headers(headers)

    return {}


def _redirect_chain_from_response(response: httpx.Response | None) -> list[dict[str, object]]:
    if response is None:
        return []

    return [
        {
            "url": str(item.url),
            "status_code": int(item.status_code),
        }
        for item in list(getattr(response, "history", []))
    ]


def _attach_snapshot(
    result: FetchResult,
    *,
    requested_url: str,
    final_url: str | None,
    http_status: int | None,
    html: str | None,
    fetch_method: str | None,
    response_headers: Any = None,
    response_time_ms: float | int | None = None,
    redirect_chain: Any = None,
    extracted_text: str | None = None,
    fetched_at: str | None = None,
) -> FetchResult:
    snapshot = build_extraction_artifact(
        requested_url=requested_url,
        final_url=final_url,
        status_code=http_status,
        response_headers=response_headers or {},
        response_time_ms=response_time_ms,
        html=html,
        fetch_method=fetch_method,
        fetched_at=fetched_at or datetime.now(UTC).isoformat(),
        redirect_chain=redirect_chain or [],
        extracted_text=extracted_text,
    )
    result["snapshot"] = snapshot
    result["final_url"] = str(snapshot.get("final_url") or requested_url)
    result["http_status"] = snapshot.get("status_code")
    result["html"] = snapshot.get("html")
    result["text"] = snapshot.get("text")
    return result


def _success_fetch_result(
    *,
    requested_url: str,
    html: str,
    final_url: str,
    http_status: int | None,
    fetch_method: str,
    response_headers: Any,
    response_time_ms: float | int | None,
    redirect_chain: Any,
    fetched_at: str,
) -> FetchResult:
    result = _empty_fetch_result(requested_url)
    result.update(
        {
            "status": "success",
            "fetch_method": fetch_method,
            "fetch_error_code": None,
            "fetch_error_message": None,
        }
    )
    result = _attach_snapshot(
        result,
        requested_url=requested_url,
        final_url=final_url,
        http_status=http_status,
        html=html,
        fetch_method=fetch_method,
        response_headers=response_headers,
        response_time_ms=response_time_ms,
        redirect_chain=redirect_chain,
        fetched_at=fetched_at,
    )
    if not html.strip() or not str(result.get("text") or "").strip():
        result["status"] = "failed"
        result["fetch_error_code"] = "empty_content"
        result["fetch_error_message"] = "HTML or extracted text is empty"
    return result


def _normalize_http_error(error: Exception, response_status: int | None = None) -> tuple[str, str]:
    if response_status in {401, 403, 429}:
        return f"http_{response_status}", f"HTTP {response_status}"

    if isinstance(error, httpx.ConnectTimeout):
        message = str(error).lower()
        if "handshake" in message or "_ssl.c" in message:
            return "tls_handshake_failed", str(error)
        return "connect_timeout", str(error)
    if isinstance(error, httpx.ReadTimeout):
        return "read_timeout", str(error)
    if isinstance(error, httpx.TimeoutException):
        return "connect_timeout", str(error)
    if isinstance(error, httpx.HTTPStatusError) and error.response is not None:
        return _normalize_http_error(error, error.response.status_code)

    return "unknown_fetch_error", str(error)


def _looks_like_browser_required(html: str, text: str) -> bool:
    lowered_html = html.lower()
    lowered_text = text.lower()

    js_markers = [
        "enable javascript",
        "javascript required",
        "please turn javascript on",
        "please enable cookies",
        "cf-browser-verification",
        "attention required",
        "captcha",
        "access denied",
        "__next",
        "__nuxt",
        'id="app"',
        'id="root"',
    ]
    if any(marker in lowered_html or marker in lowered_text for marker in js_markers):
        return True

    return len(text.strip()) < 120 and lowered_html.count("<script") >= 5


def _http_fetch_once(url: str, *, fetch_method: str, verify: bool = True) -> FetchResult:
    with httpx.Client(
        follow_redirects=True,
        timeout=HTTP_TIMEOUT,
        headers=DEFAULT_HEADERS,
        http2=True,
        verify=verify,
    ) as client:
        started_at = time.perf_counter()
        response = client.get(url)
        response_time_ms = (time.perf_counter() - started_at) * 1000.0
        response.raise_for_status()
        html = response.text
        success_result = _success_fetch_result(
            requested_url=url,
            html=html,
            final_url=str(response.url),
            http_status=int(response.status_code),
            fetch_method=fetch_method,
            response_headers=_response_headers_from_httpx(response),
            response_time_ms=response_time_ms,
            redirect_chain=_redirect_chain_from_response(response),
            fetched_at=datetime.now(UTC).isoformat(),
        )
        if success_result["status"] == "success":
            text = str(success_result.get("text") or "")
            if _looks_like_browser_required(html, text):
                success_result["status"] = "failed"
                success_result["fetch_error_code"] = "javascript_required"
                success_result["fetch_error_message"] = "Page appears to require JavaScript rendering"
        return success_result


def _http_fetch(url: str) -> FetchResult:
    started_at = time.perf_counter()
    try:
        return _http_fetch_once(url, fetch_method="http", verify=True)
    except Exception as error:
        response = error.response if isinstance(error, httpx.HTTPStatusError) and error.response is not None else None
        error_code, error_message = _normalize_http_error(error)
        result = _empty_fetch_result(url)
        result.update(
            {
                "fetch_method": "http",
                "fetch_error_code": error_code,
                "fetch_error_message": error_message,
            }
        )
        return _attach_snapshot(
            result,
            requested_url=url,
            final_url=str(response.url) if response is not None else url,
            http_status=int(response.status_code) if response is not None else None,
            html=response.text if response is not None else None,
            fetch_method="http",
            response_headers=_response_headers_from_httpx(response),
            response_time_ms=(time.perf_counter() - started_at) * 1000.0,
            redirect_chain=_redirect_chain_from_response(response),
        )


def _http_fetch_with_retry(url: str, attempts: int = 2) -> FetchResult:
    last_result = _empty_fetch_result(url)
    for attempt in range(attempts):
        started_at = time.perf_counter()
        try:
            verify = attempt == 0
            result = _http_fetch_once(url, fetch_method="http_retry", verify=verify)
            if result["status"] == "success":
                return result
            last_result = result
        except Exception as error:
            response = error.response if isinstance(error, httpx.HTTPStatusError) and error.response is not None else None
            error_code, error_message = _normalize_http_error(error)
            last_result = _empty_fetch_result(url)
            last_result.update(
                {
                    "fetch_method": "http_retry",
                    "fetch_error_code": error_code,
                    "fetch_error_message": error_message,
                }
            )
            last_result = _attach_snapshot(
                last_result,
                requested_url=url,
                final_url=str(response.url) if response is not None else url,
                http_status=int(response.status_code) if response is not None else None,
                html=response.text if response is not None else None,
                fetch_method="http_retry",
                response_headers=_response_headers_from_httpx(response),
                response_time_ms=(time.perf_counter() - started_at) * 1000.0,
                redirect_chain=_redirect_chain_from_response(response),
            )
        if attempt < attempts - 1:
            time.sleep(0.8 * (attempt + 1))
    return last_result


def _browser_fetch(url: str) -> FetchResult:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except Exception as error:
        result = _empty_fetch_result(url)
        result.update(
            {
                "fetch_method": "browser",
                "fetch_error_code": "browser_unavailable",
                "fetch_error_message": str(error),
            }
        )
        return _attach_snapshot(
            result,
            requested_url=url,
            final_url=url,
            http_status=None,
            html=None,
            fetch_method="browser",
            response_headers={},
        )

    started_at = time.perf_counter()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=DEFAULT_HEADERS["User-Agent"],
                locale="ru-RU",
            )
            response = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            try:
                page.wait_for_load_state("networkidle", timeout=8_000)
            except PlaywrightError:
                pass
            html = page.content()
            final_url = page.url or url
            http_status = response.status if response is not None else None
            response_headers = _response_headers_from_browser_response(response)
            browser.close()
    except Exception as error:
        result = _empty_fetch_result(url)
        result.update(
            {
                "fetch_method": "browser",
                "fetch_error_code": "bot_protection_suspected",
                "fetch_error_message": str(error),
            }
        )
        return _attach_snapshot(
            result,
            requested_url=url,
            final_url=url,
            http_status=None,
            html=None,
            fetch_method="browser",
            response_headers={},
            response_time_ms=(time.perf_counter() - started_at) * 1000.0,
        )

    result = _success_fetch_result(
        requested_url=url,
        html=html,
        final_url=final_url,
        http_status=http_status,
        fetch_method="browser",
        response_headers=response_headers,
        response_time_ms=(time.perf_counter() - started_at) * 1000.0,
        redirect_chain=[],
        fetched_at=datetime.now(UTC).isoformat(),
    )
    if result["status"] != "success":
        result["fetch_error_code"] = "javascript_required"
        result["fetch_error_message"] = "Browser rendering did not produce usable content"
    return result


def fetch_page(url: str, use_browser: bool = True) -> FetchResult:
    first_result = ensure_fetch_result_snapshot(_http_fetch(url), requested_url=url)
    if first_result["status"] == "success":
        return first_result

    retry_result = ensure_fetch_result_snapshot(_http_fetch_with_retry(url), requested_url=url)
    if retry_result["status"] == "success":
        return retry_result

    should_use_browser = use_browser and (
        retry_result["fetch_error_code"] in {"http_403", "http_429", "javascript_required", "empty_content"}
        or retry_result["fetch_error_code"] == "tls_handshake_failed"
        or retry_result["fetch_error_code"] == "unknown_fetch_error"
    )
    if should_use_browser:
        browser_result = ensure_fetch_result_snapshot(_browser_fetch(url), requested_url=url)
        if browser_result["status"] == "success":
            return browser_result
        return browser_result

    return retry_result
