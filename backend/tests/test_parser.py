import httpx

from app.parser import (
    FEATURE_SCHEMA_VERSION,
    classify_browser_fetch_error,
    extract_document,
    extract_text,
    fetch_page,
    summarize_extraction_artifact,
)
from app.tasks import process_page


def test_extract_text_removes_script_and_style():
    html = """
    <html>
      <head>
        <style>.hidden { display:none; }</style>
        <script>console.log("ignore");</script>
      </head>
      <body>
        <main>
          <h1>Hello</h1>
          <p>World</p>
        </main>
      </body>
    </html>
    """

    text = extract_text(html)

    assert text == "Hello World"


def test_extract_document_captures_links_and_buttons():
    html = """
    <html>
      <body>
        <a href="tel:+79990000000" rel="nofollow">Позвонить</a>
        <a href="https://t.me/example">Telegram</a>
        <button>Оставить заявку</button>
      </body>
    </html>
    """

    document = extract_document(html)

    assert document["links"] == [
        {"href": "tel:+79990000000", "text": "Позвонить", "rel": "nofollow"},
        {"href": "https://t.me/example", "text": "Telegram", "rel": ""},
    ]
    assert document["button_texts"] == ["Оставить заявку"]


def test_fetch_page_returns_success_result(monkeypatch):
    class DummyResponse:
        status_code = 200
        text = "<html><body><h1>Example</h1><p>Page text</p></body></html>"
        url = "https://example.com/final"

        def raise_for_status(self) -> None:
            return None

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str):
            assert url == "https://example.com"
            return DummyResponse()

    monkeypatch.setattr("app.parser.httpx.Client", DummyClient)

    result = fetch_page("https://example.com", use_browser=False)

    assert result["status"] == "success"
    assert result["fetch_method"] == "http"
    assert result["text"] == "Example Page text"
    assert isinstance(result["snapshot"], dict)
    assert result["snapshot"]["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert result["snapshot"]["requested_url"] == "https://example.com"
    assert result["snapshot"]["final_url"] == "https://example.com/final"
    assert result["snapshot"]["status_code"] == 200
    assert result["snapshot"]["redirect_chain"] == []
    assert result["snapshot"]["document"]["h1_texts"] == ["Example"]


def test_fetch_page_retries_after_timeout(monkeypatch):
    attempts = {"count": 0}

    class DummyResponse:
        status_code = 200
        text = "<html><body><h1>Retry</h1><p>Worked</p></body></html>"
        url = "https://example.com/retry"

        def raise_for_status(self) -> None:
            return None

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url: str):
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise httpx.ConnectTimeout("timed out")
            return DummyResponse()

    monkeypatch.setattr("app.parser.httpx.Client", DummyClient)
    monkeypatch.setattr("app.parser.time.sleep", lambda value: None)

    result = fetch_page("https://example.com", use_browser=False)

    assert result["status"] == "success"
    assert result["fetch_method"] == "http_retry"
    assert result["snapshot"]["feature_schema_version"] == FEATURE_SCHEMA_VERSION


def test_process_page_returns_extracted_text(monkeypatch):
    def fake_fetch_page(url: str, use_browser: bool = True):
        assert url == "https://example.com"
        return {
            "status": "success",
            "fetch_method": "http",
            "fetch_error_code": None,
            "fetch_error_message": None,
            "final_url": url,
            "http_status": 200,
            "html": "<html><body><h1>Example</h1><p>Page text</p></body></html>",
            "text": "Example Page text",
        }

    monkeypatch.setattr("app.tasks.fetch_page", fake_fetch_page)

    text = process_page.run("https://example.com")

    assert text == "Example Page text"


def test_fetch_page_uses_browser_fallback_for_javascript_required(monkeypatch):
    monkeypatch.setattr(
        "app.parser._http_fetch",
        lambda url: {
            "status": "failed",
            "fetch_method": "http",
            "fetch_error_code": "javascript_required",
            "fetch_error_message": "JS required",
            "final_url": url,
            "http_status": 200,
            "html": None,
            "text": None,
        },
    )
    monkeypatch.setattr(
        "app.parser._http_fetch_with_retry",
        lambda url, attempts=2: {
            "status": "failed",
            "fetch_method": "http_retry",
            "fetch_error_code": "javascript_required",
            "fetch_error_message": "JS required",
            "final_url": url,
            "http_status": 200,
            "html": None,
            "text": None,
        },
    )
    monkeypatch.setattr(
        "app.parser._browser_fetch",
        lambda url: {
            "status": "success",
            "fetch_method": "browser",
            "fetch_error_code": None,
            "fetch_error_message": None,
            "final_url": url,
            "http_status": 200,
            "html": "<html><body><main>Rendered</main></body></html>",
            "text": "Rendered",
        },
    )

    result = fetch_page("https://example.com", use_browser=True)

    assert result["status"] == "success"
    assert result["fetch_method"] == "browser"
    assert result["snapshot"]["feature_schema_version"] == FEATURE_SCHEMA_VERSION


def test_browser_fetch_error_classification_does_not_call_generic_timeout_bot_protection():
    assert classify_browser_fetch_error("Timeout 30000ms exceeded") == "browser_timeout"
    assert classify_browser_fetch_error("Playwright page crashed") == "browser_fetch_failed"
    assert classify_browser_fetch_error("captcha challenge") == "captcha_detected"
    assert classify_browser_fetch_error("Access denied") == "access_denied"


def test_summarize_extraction_artifact_returns_compact_metadata():
    summary = summarize_extraction_artifact(
        {
            "requested_url": "https://example.com",
            "final_url": "https://example.com/final",
            "status_code": 200,
            "fetch_method": "http",
            "response_time_ms": 123.4,
            "response_headers": {"content-type": "text/html"},
            "redirect_chain": [{"url": "https://example.com", "status_code": 301}],
            "html": "<html><head><title>Example</title></head><body><h1>Hello</h1></body></html>",
            "text": "Hello",
            "json_ld": ["{}"],
        }
    )

    assert summary is not None
    assert summary["artifact_version"] == "extraction-v2"
    assert summary["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert summary["requested_url"] == "https://example.com"
    assert summary["final_url"] == "https://example.com/final"
    assert summary["status_code"] == 200
    assert summary["fetch_method"] == "http"
    assert summary["response_time_ms"] == 123.4
    assert summary["redirect_chain"] == [{"url": "https://example.com", "status_code": 301}]
    assert summary["response_headers"] == {"content-type": "text/html"}
    assert summary["title"] == "Example"
    assert summary["canonical"] == ""
    assert summary["lang"] == ""
    assert summary["html_present"] is True
    assert summary["html_length_chars"] > 0
    assert summary["text_length_chars"] == 5
    assert summary["json_ld_count"] == 1
    assert isinstance(summary["fetched_at"], str)
