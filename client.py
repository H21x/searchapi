"""Tiny client for the Free Web Search API — stdlib only, no dependencies.

Use from anywhere (e.g. a Telegram bot) without embedding the engine:

    from client import web_search, web_news, web_scrape

    resp = web_search("latest movies 2026", num=5, base_url="https://your-api.onrender.com")
    for r in resp["results"]:
        print(r["title"], r["url"])

If the API service sets API_KEY, pass api_key="...".
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request


class WebSearchError(Exception):
    pass


class WebSearchClient:
    def __init__(self, base_url: str, api_key: str = "", timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _get(self, path: str, params: dict) -> dict:
        url = self.base_url + path + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "free-websearch-client/1.0"})
        if self.api_key:
            req.add_header("X-API-Key", self.api_key)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8"))
            except Exception:
                detail = exc.reason
            raise WebSearchError(f"HTTP {exc.code}: {detail}") from None
        except Exception as exc:
            raise WebSearchError(str(exc)) from None

    def search(self, q: str, num: int = 5, freshness: str = "",
               ai: bool = False, ai_model: str = "openai") -> dict:
        """-> {query, source_type, status, backend, message, results,
        ai_answer, ai_model, ai_status}"""
        return self._get("/search", {"q": q, "num": num, "freshness": freshness,
                                     "ai": int(ai), "ai_model": ai_model})

    def news(self, q: str, num: int = 5, freshness: str = "") -> dict:
        return self._get("/news", {"q": q, "num": num, "freshness": freshness})

    def scrape(self, url: str, max_chars: int = 8000, offset: int = 0,
               format: str = "markdown") -> dict:
        return self._get("/scrape", {"url": url, "max_chars": max_chars,
                                     "offset": offset, "format": format})

    def probe(self, url: str) -> dict:
        return self._get("/probe", {"url": url})

    def health(self) -> dict:
        return self._get("/health", {})


def _default_client(base_url: str = "", api_key: str = "") -> WebSearchClient:
    import os
    base = base_url or os.environ.get("WEBSEARCH_API_URL", "http://127.0.0.1:8000")
    key = api_key or os.environ.get("WEBSEARCH_API_KEY", "")
    return WebSearchClient(base, key)


def web_search(q: str, num: int = 5, base_url: str = "", api_key: str = "") -> dict:
    return _default_client(base_url, api_key).search(q, num)


def web_search_ai(q: str, num: int = 5, ai_model: str = "openai",
                  base_url: str = "", api_key: str = "") -> dict:
    """Search + AI answer in one call."""
    return _default_client(base_url, api_key).search(q, num, ai=True, ai_model=ai_model)


def web_news(q: str, num: int = 5, base_url: str = "", api_key: str = "") -> dict:
    return _default_client(base_url, api_key).news(q, num)


def web_scrape(url: str, max_chars: int = 8000, base_url: str = "", api_key: str = "") -> dict:
    return _default_client(base_url, api_key).scrape(url, max_chars)
