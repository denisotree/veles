"""Web search tool — query the web and return ranked results.

Supports multiple search backends selected by env-var priority:

| Provider   | Env var              | Notes                             |
|------------|----------------------|-----------------------------------|
| Brave      | BRAVE_SEARCH_API_KEY | 2 000 free queries/month          |
| Tavily     | TAVILY_API_KEY       | AI-optimised results, paid tier   |
| SearXNG    | SEARXNG_URL          | Self-hosted meta-search, free     |
| DuckDuckGo | (none)               | Fallback; requires `ddgs` package |

Auto-detect order: Brave → Tavily → SearXNG → DuckDuckGo.
Override with `VELES_WEB_SEARCH_BACKEND=brave|tavily|searxng|ddgs`.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

from veles.core.risk import RiskClass
from veles.core.tools.registry import tool
from veles.core.untrusted import wrap_untrusted

_TIMEOUT = 30.0
_USER_AGENT = "Veles/0.0.1"
_DEFAULT_LIMIT = 5
_MAX_LIMIT = 20

# ---- provider base ----


class _Provider(ABC):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def search(self, query: str, limit: int) -> list[dict[str, Any]]: ...


# ---- Brave Search ----


class _BraveProvider(_Provider):
    _API = "https://api.search.brave.com/res/v1/web/search"

    def name(self) -> str:
        return "brave"

    def available(self) -> bool:
        return bool(os.environ.get("BRAVE_SEARCH_API_KEY"))

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        api_key = os.environ["BRAVE_SEARCH_API_KEY"]
        resp = httpx.get(
            self._API,
            params={"q": query, "count": min(limit, 20)},
            headers={
                "X-Subscription-Token": api_key,
                "Accept": "application/json",
                "User-Agent": _USER_AGENT,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("web", {}).get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("description", ""),
                "position": i + 1,
            }
            for i, r in enumerate(raw[:limit])
        ]


# ---- Tavily ----


class _TavilyProvider(_Provider):
    _API = "https://api.tavily.com/search"

    def name(self) -> str:
        return "tavily"

    def available(self) -> bool:
        return bool(os.environ.get("TAVILY_API_KEY"))

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        resp = httpx.post(
            self._API,
            json={
                "api_key": os.environ["TAVILY_API_KEY"],
                "query": query,
                "max_results": min(limit, 20),
                "include_raw_content": False,
                "include_images": False,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        raw = resp.json().get("results", [])
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("content", ""),
                "position": i + 1,
            }
            for i, r in enumerate(raw[:limit])
        ]


# ---- SearXNG ----


class _SearXNGProvider(_Provider):
    def name(self) -> str:
        return "searxng"

    def available(self) -> bool:
        return bool(os.environ.get("SEARXNG_URL"))

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        base_url = os.environ["SEARXNG_URL"].rstrip("/")
        resp = httpx.get(
            f"{base_url}/search",
            params={"q": query, "format": "json", "pageno": 1},
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        raw = resp.json().get("results", [])
        raw.sort(key=lambda r: r.get("score", 0), reverse=True)
        return [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "description": r.get("content", ""),
                "position": i + 1,
            }
            for i, r in enumerate(raw[:limit])
        ]


# ---- DuckDuckGo (soft dependency) ----


class _DDGProvider(_Provider):
    def name(self) -> str:
        return "ddgs"

    def available(self) -> bool:
        try:
            import ddgs as _  # noqa: F401

            return True
        except ImportError:
            return False

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        from ddgs import DDGS  # type: ignore[import]

        results: list[dict[str, Any]] = []
        with DDGS() as client:
            for i, hit in enumerate(client.text(query, max_results=limit)):
                results.append(
                    {
                        "title": hit.get("title", ""),
                        "url": hit.get("href") or hit.get("url", ""),
                        "description": hit.get("body", ""),
                        "position": i + 1,
                    }
                )
                if len(results) >= limit:
                    break
        return results


# ---- provider registry ----

_PROVIDERS: list[_Provider] = [
    _BraveProvider(),
    _TavilyProvider(),
    _SearXNGProvider(),
    _DDGProvider(),
]

_PROVIDER_BY_NAME: dict[str, _Provider] = {p.name(): p for p in _PROVIDERS}


def _resolve_provider() -> _Provider | None:
    override = os.environ.get("VELES_WEB_SEARCH_BACKEND", "").strip().lower()
    if override:
        p = _PROVIDER_BY_NAME.get(override)
        if p is None:
            return None
        return p if p.available() else None
    for p in _PROVIDERS:
        if p.available():
            return p
    return None


# ---- tool ----


@tool(
    risk_class=RiskClass.NETWORK_OPEN_WORLD,
    side_effects=["network"],
)
def web_search(query: str, limit: int = _DEFAULT_LIMIT) -> str:
    """Search the web for `query` and return up to `limit` results.

    Automatically selects the first available backend from: Brave, Tavily,
    SearXNG, or DuckDuckGo. Configure via env vars (see module docstring).

    Returns JSON with keys `success`, `provider`, `query`, `results`.
    Each result has `title`, `url`, `description`, `position`.
    On error returns `<error: ...>`.
    """
    limit = max(1, min(limit, _MAX_LIMIT))
    provider = _resolve_provider()
    if provider is None:
        cfg_names = ", ".join(p.name() for p in _PROVIDERS)
        return (
            "<error: web_search: no backend configured. "
            f"Set BRAVE_SEARCH_API_KEY, TAVILY_API_KEY, SEARXNG_URL, "
            f"or install the `ddgs` package. "
            f"Available backends: {cfg_names}>"
        )
    try:
        results = provider.search(query, limit)
    except Exception as exc:
        return f"<error: web_search ({provider.name()}): {type(exc).__name__}: {exc}>"

    payload = json.dumps(
        {
            "success": True,
            "provider": provider.name(),
            "query": query,
            "results": results,
        },
        ensure_ascii=False,
        indent=2,
    )
    # Search results are external by definition — titles, descriptions, and
    # URLs are attacker-controlled. Wrap the JSON payload so the model sees
    # the trust boundary on every call.
    return wrap_untrusted(payload, source=f"web_search:{provider.name()}:{query}")
