"""Free Web Search API — standalone HTTP service.

Wraps the (bug-fixed) websearch engine as a JSON API. No API keys needed
for the search backends themselves; an optional API_KEY env var protects
*this* service (X-API-Key header) if you expose it publicly.
"""
from __future__ import annotations

import asyncio
import os

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse

import websearch as engine
from websearch import FetchError, InputError

__version__ = "1.4.0"

API_KEY = os.environ.get("API_KEY", "").strip()


async def _require_key(x_api_key: str | None = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key.")


app = FastAPI(
    title="Free Web Search API",
    version=__version__,
    description="Keyless web/news search + article scraping. Web results are led by Yahoo, "
                "with fallback across 8 backends.",
    dependencies=[Depends(_require_key)],
)


def _bad_request(exc: InputError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@app.get("/health")
async def health():
    return {"ok": True, "version": __version__, "auth_required": bool(API_KEY)}


def _do_search(q: str, num: int, news: bool, freshness: str) -> dict:
    try:
        query = engine._query(q)
        count = engine._count(num)
        fresh = engine._freshness(freshness or "")
    except InputError as exc:
        raise _bad_request(exc)
    return engine._search_impl(query, count, news=news, freshness=fresh)


@app.get("/search")
async def search(
    q: str = Query(..., description="Search query"),
    num: int = Query(5, ge=1, le=50),
    freshness: str = Query("", description="hour|day|week|month (optional)"),
):
    """Web search. Response: {query, source_type, status, backend, message, results}.

    status is ok|empty|blocked|error — all HTTP 200; check `status` yourself.
    """
    def _run():
        res = _do_search(q, num, False, freshness)
        return res
    return await asyncio.to_thread(_run)


@app.get("/news")
async def news(
    q: str = Query(..., description="News query"),
    num: int = Query(5, ge=1, le=50),
    freshness: str = Query("", description="hour|day|week|month (optional)"),
):
    """News search, newest first. Same response shape as /search."""
    return await asyncio.to_thread(_do_search, q, num, True, freshness)


@app.get("/scrape")
async def scrape(
    url: str = Query(..., description="URL to extract readable text from"),
    max_chars: int = Query(8000, ge=50, le=100000),
    offset: int = Query(0, ge=0, le=100000),
    format: str = Query("markdown", description="markdown|txt|xml|json"),
):
    """Scrape one URL -> {url, final_url, content, content_chars,
    content_total_chars, truncated, next_char_offset, error}."""
    def _run():
        try:
            fmt = engine._output_format(format)
            limit = engine._max_chars(max_chars)
            off = engine._char_offset(offset)
        except InputError as exc:
            raise _bad_request(exc)
        try:
            return engine.scrape_url_impl(url, output_format=fmt,
                                          max_chars=limit, char_offset=off)
        except InputError as exc:
            raise _bad_request(exc)
        except FetchError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
    return await asyncio.to_thread(_run)


@app.get("/probe")
async def probe(url: str = Query(..., description="URL to check")):
    """Cheap pre-scrape check: {url, final_url, ok, status_code, content_type,
    content_length, is_binary, title, error}. Never raises for fetch problems."""
    def _run():
        try:
            return engine.probe_url_impl(url)
        except InputError as exc:
            raise _bad_request(exc)
    return await asyncio.to_thread(_run)


@app.exception_handler(HTTPException)
async def _http_exc(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
