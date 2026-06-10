"""Integration: fetch_url + web_search wrap their content in <untrusted> (M66)."""

from __future__ import annotations

import json
from unittest.mock import patch

from veles.core.tools.builtin import fetch_url as fetch_url_mod
from veles.core.tools.builtin import web_search as web_search_mod


class _FakeResponse:
    def __init__(self, *, text: str, status: int = 200, content_type: str = "text/plain"):
        self.text = text
        self.status_code = status
        self.headers = {"content-type": content_type}


def test_fetch_url_wraps_response_as_untrusted() -> None:
    fake = _FakeResponse(text="hello world", status=200)
    with patch.object(fetch_url_mod, "httpx") as h:
        h.get.return_value = fake
        h.HTTPError = Exception
        # Bypass the private-IP check.
        with patch.object(
            fetch_url_mod,
            "_is_safe_url",
            return_value=(True, ""),
        ):
            out = fetch_url_mod.fetch_url("https://example.com/page")
    assert '<untrusted source="https://example.com/page"' in out
    assert "</untrusted>" in out
    assert "<http 200>" in out
    assert "hello world" in out


def test_fetch_url_redacts_secrets_in_content() -> None:
    fake = _FakeResponse(text="leak: ghp_AbcdefghIjklmnopqrstuvwxyzABCDEF12 done", status=200)
    with patch.object(fetch_url_mod, "httpx") as h:
        h.get.return_value = fake
        h.HTTPError = Exception
        with patch.object(fetch_url_mod, "_is_safe_url", return_value=(True, "")):
            out = fetch_url_mod.fetch_url("https://example.com/leak")
    assert "ghp_AbcdefghIjklmnopqrstuvwxyzABCDEF12" not in out
    assert "[REDACTED:github-token]" in out


def test_web_search_wraps_results_as_untrusted() -> None:
    """The search payload (JSON of title/url/description) is attacker-controlled.
    Wrapper must appear on every successful return."""

    class _FakeProvider:
        def name(self):
            return "fake"

        def search(self, query, limit):
            return [
                {"title": "T", "url": "https://x", "description": "d", "position": 1}
            ]

    with patch.object(web_search_mod, "_resolve_provider", return_value=_FakeProvider()):
        out = web_search_mod.web_search("hello", limit=1)
    assert "<untrusted" in out
    assert 'source="web_search:fake:hello"' in out
    # The JSON payload is still recoverable from inside the wrapper.
    body = out.split("\n\n", 1)[1].rsplit("\n</untrusted>", 1)[0]
    payload = json.loads(body)
    assert payload["success"] is True
    assert payload["results"][0]["title"] == "T"
