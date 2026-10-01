# Free Web Search API

Standalone HTTP API for **keyless web search, news search, and article scraping**.
Ported from [digitalninjanv/free-web-search](https://github.com/digitalninjanv/free-web-search)
with real bugs fixed (see `BUGS_FIXED.md`) and wrapped as a deployable service.

Completely independent project — push as its own GitHub repo, deploy as its
own Render service. Your Telegram bot (or anything else) calls it over HTTP
via `client.py`.

## How it works

No search API keys. An 8-backend chain is tried in order — first backend with
usable results wins:

| # | Backend | For |
|---|---|---|
| 1 | `yahoo` — Yahoo search (primary, best quality) | web |
| 2 | `bing_html` — Bing results page | web |
| 3 | `bing_rss` — Bing RSS feed | web |
| 4 | `duckduckgo` — DDG HTML endpoint | web |
| 5 | `marginalia` — keyless JSON API | web |
| 6 | `google_news_rss` | news |
| 7 | `bing_news_html` | news |
| 8 | `bing_news_rss` | news |

Requests impersonate Chrome TLS fingerprints (`curl_cffi`) so they look like a
real browser. Results are relevance re-ranked and near-deduplicated. An SSRF
guard only ever fetches public IPs (DNS pinning via CURLOPT_RESOLVE).

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | `{"ok": true, ...}` |
| GET | `/search?q=...&num=5&freshness=` | Web search |
| GET | `/news?q=...&num=5&freshness=` | News search, newest first |
| GET | `/scrape?url=...&max_chars=8000&offset=0&format=markdown` | Extract article text |
| GET | `/probe?url=...` | Cheap pre-scrape check (status/type/size/title) |

`/search` and `/news` always return HTTP 200 with the contract shape:

```json
{
  "query": "python",
  "source_type": "web",
  "status": "ok",
  "backend": "bing_rss",
  "message": "",
  "results": [
    {"title": "...", "url": "...", "snippet": "...", "backend": "bing_rss", "score": 1.234}
  ]
}
```

`status` is `ok` | `empty` | `blocked` | `error` — **check it yourself**; a
blocked search engine is a normal outcome, not an HTTP error.

Auth: if the `API_KEY` env var is set, every request needs the `X-API-Key`
header (401 otherwise). Empty = open.

## Calling it from Python (e.g. your bot)

`client.py` is stdlib-only — copy it anywhere, no install needed:

```python
from client import WebSearchClient

api = WebSearchClient("https://free-websearch-api.onrender.com", api_key="...")

resp = api.search("Mohanlal new movie 2026", num=5)
if resp["status"] == "ok":
    for r in resp["results"]:
        print(r["title"], r["url"])

# or the one-liners (WEBSEARCH_API_URL / WEBSEARCH_API_KEY env vars work too)
from client import web_search, web_scrape
web_search("query")
web_scrape("https://example.com/article")
```

## Run locally

```powershell
pip install -r requirements.txt
uvicorn api:app --host 127.0.0.1 --port 8000
# curl "http://127.0.0.1:8000/search?q=hello&num=3"
```

The engine also still works as a CLI: `python websearch.py search "query" --num 5 --json`

Run the offline tests: `python -m pytest tests/ -q` (26 tests, no network).

## Deploy on Render

```powershell
git init; git add -A; git commit -m "free websearch api"
git remote add origin https://github.com/<you>/free-websearch-api.git
git push -u origin main
```

Then Render → New → Web Service → point at the repo (Docker runtime, free
plan). Or `render.yaml` blueprint deploy. Set `API_KEY` in Environment if you
want auth. Health check path: `/health`.

## Deploy on AlwaysData (free, no sleep)

AlwaysData serves Python via **WSGI**, so `wsgi.py` (FastAPI → WSGI through
`a2wsgi`, already in `requirements.txt`) is the entry point.

```powershell
# 1. Push to GitHub (same as above), then SSH into your account:
ssh <account>@ssh-<account>.alwaysdata.net

# 2. On the server:
git clone https://github.com/<you>/free-websearch-api.git
cd free-websearch-api
python -m venv venv
./venv/bin/python -m pip install -r requirements.txt
```

3. Admin panel → **Web > Sites** → add a site, Type = **Python WSGI**:
   - **Addresses**: e.g. `websearch-<account>.alwaysdata.net`
     (free plan = `*.alwaysdata.net` only)
   - **Application path**: `/home/<account>/free-websearch-api/wsgi.py`
   - **Working directory**: `/home/<account>/free-websearch-api`
   - **Virtualenv directory**: `/home/<account>/free-websearch-api/venv`
   - **Environment variables**: `API_KEY=<redacted>` (optional, recommended)
   - Check **Environment > Python** is 3.10+ first.

4. Test: `https://websearch-<account>.alwaysdata.net/health` → `{"ok": true, ...}`

Logs if something breaks: admin panel → Logs, or
`/home/<account>/admin/logs/uwsgi/<site-id>.log` over SSH.

Free-plan quotas: 1 GB disk / 256 MB RAM — plenty for this app.

## Honest limits

- **This is scraping, not an official API.** Search engines fight scrapers:
  expect occasional `status=blocked` (challenge/captcha), especially from
  datacenter IPs. The chain degrades gracefully — that is the design.
- **Use it as a fallback, not primary.** For production-critical search,
  prefer an official API (Brave Search: 2000 queries/month free) and fall
  back to this when the quota runs out.
- New data-center IPs (like a fresh Render deploy) get challenged more often
  in the first days; it usually settles.
- Respect robots/ToS of the sites you scrape; keep query volume reasonable.
