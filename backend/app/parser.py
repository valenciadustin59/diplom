from __future__ import annotations

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

FetchResult = dict[str, object]


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    def get_text(self) -> str:
        joined = " ".join(self._chunks)
        normalized = re.sub(r"\s+", " ", unescape(joined))
        return normalized.strip()


def extract_text(html: str) -> str:
    parser = _TextExtractor()
    parser.feed(html)
    parser.close()
    return parser.get_text()


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
    }


def _success_fetch_result(
    *,
    html: str,
    final_url: str,
    http_status: int | None,
    fetch_method: str,
) -> FetchResult:
    text = extract_text(html)
    if not html.strip() or not text.strip():
        result = _empty_fetch_result(final_url)
        result.update(
            {
                "fetch_method": fetch_method,
                "http_status": http_status,
                "fetch_error_code": "empty_content",
                "fetch_error_message": "HTML or extracted text is empty",
            }
        )
        return result

    return {
        "status": "success",
        "fetch_method": fetch_method,
        "fetch_error_code": None,
        "fetch_error_message": None,
        "final_url": final_url,
        "http_status": http_status,
        "html": html,
        "text": text,
    }


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
    result = _empty_fetch_result(url)
    result["fetch_method"] = fetch_method

    with httpx.Client(
        follow_redirects=True,
        timeout=HTTP_TIMEOUT,
        headers=DEFAULT_HEADERS,
        http2=True,
        verify=verify,
    ) as client:
        response = client.get(url)
        result["final_url"] = str(response.url)
        result["http_status"] = int(response.status_code)
        response.raise_for_status()
        html = response.text
        success_result = _success_fetch_result(
            html=html,
            final_url=str(response.url),
            http_status=int(response.status_code),
            fetch_method=fetch_method,
        )
        if success_result["status"] == "success":
            text = str(success_result["text"] or "")
            if _looks_like_browser_required(html, text):
                success_result["status"] = "failed"
                success_result["fetch_error_code"] = "javascript_required"
                success_result["fetch_error_message"] = "Page appears to require JavaScript rendering"
        return success_result


def _http_fetch(url: str) -> FetchResult:
    try:
        return _http_fetch_once(url, fetch_method="http", verify=True)
    except Exception as error:
        error_code, error_message = _normalize_http_error(error)
        result = _empty_fetch_result(url)
        result.update(
            {
                "fetch_method": "http",
                "fetch_error_code": error_code,
                "fetch_error_message": error_message,
            }
        )
        if isinstance(error, httpx.HTTPStatusError) and error.response is not None:
            result["http_status"] = int(error.response.status_code)
            result["final_url"] = str(error.response.url)
        return result


def _http_fetch_with_retry(url: str, attempts: int = 2) -> FetchResult:
    last_result = _empty_fetch_result(url)
    for attempt in range(attempts):
        try:
            verify = attempt == 0
            result = _http_fetch_once(url, fetch_method="http_retry", verify=verify)
            if result["status"] == "success":
                return result
            last_result = result
        except Exception as error:
            error_code, error_message = _normalize_http_error(error)
            last_result = _empty_fetch_result(url)
            last_result.update(
                {
                    "fetch_method": "http_retry",
                    "fetch_error_code": error_code,
                    "fetch_error_message": error_message,
                }
            )
            if isinstance(error, httpx.HTTPStatusError) and error.response is not None:
                last_result["http_status"] = int(error.response.status_code)
                last_result["final_url"] = str(error.response.url)
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
        return result

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
        return result

    result = _success_fetch_result(
        html=html,
        final_url=final_url,
        http_status=http_status,
        fetch_method="browser",
    )
    if result["status"] != "success":
        result["fetch_error_code"] = "javascript_required"
        result["fetch_error_message"] = "Browser rendering did not produce usable content"
    return result


def fetch_page(url: str, use_browser: bool = True) -> FetchResult:
    first_result = _http_fetch(url)
    if first_result["status"] == "success":
        return first_result

    retry_result = _http_fetch_with_retry(url)
    if retry_result["status"] == "success":
        return retry_result

    should_use_browser = use_browser and (
        retry_result["fetch_error_code"] in {"http_403", "http_429", "javascript_required", "empty_content"}
        or retry_result["fetch_error_code"] == "tls_handshake_failed"
        or retry_result["fetch_error_code"] == "unknown_fetch_error"
    )
    if should_use_browser:
        browser_result = _browser_fetch(url)
        if browser_result["status"] == "success":
            return browser_result
        return browser_result

    return retry_result
