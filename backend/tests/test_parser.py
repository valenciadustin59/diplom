import httpx

from app.parser import extract_text, fetch_page
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
