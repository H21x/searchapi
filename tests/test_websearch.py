"""Offline test suite for the websearch engine.

The upstream repo's README promised tests/test_websearch.py + fixtures but
shipped none; this suite covers the parsers, URL utilities, validators and
the bug fixes, all without network access.
"""
import sys
import os

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websearch as ws


# ---------------------------------------------------------------- fixtures

BING_WEB_HTML = """
<html><body><ol>
<li class="b_algo"><h2><a href="https://example.com/python">Python tutorial</a></h2>
<div class="b_caption"><p>Learn python programming basics here.</p></div></li>
<li class="b_algo"><h2><a href="https://example.org/snake">Snake facts</a></h2>
<div class="b_caption"><p>All about snakes.</p></div></li>
<li class="b_algo b_ad"><h2><a href="https://ads.example.com/x">Buy now</a></h2></li>
</ol></body></html>
"""

DDG_HTML = """
<html><body>
<div class="result__body"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fddg">DDG title</a>
<a class="result__snippet" href="#">a snippet about testing</a></div>
<div class="result__body"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fads.example.com%2F&ad_provider=x&ad_domain=y">Ad</a></div>
</body></html>
"""

BING_RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Item one</title><link>https://example.com/one</link>
<description>desc one</description><pubDate>Mon, 01 Jan 2024</pubDate></item>
<item foo="bar"><title>Item two</title><link>https://example.com/two</link>
<description>desc two</description><pubDate>Tue, 02 Jan 2024</pubDate></item>
</channel></rss>"""

BING_RSS_BOM = b"\xef\xbb\xbf" + BING_RSS

GNEWS_RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>News title - Source</title><link>https://news.google.com/rss/articles/abc</link>
<source>BBC</source><pubDate>Mon, 01 Jan 2024</pubDate></item>
</channel></rss>"""

MARGINALIA_JSON = b'{"results": [{"title": "T", "url": "https://example.com/m", "description": "d"}]}'

BLOCK_HTML = "<html><body>unusual traffic from your computer network</body></html>"


# ---------------------------------------------------------------- parsers

def test_parse_web_extracts_results_and_skips_ads():
    out = ws._parse_web(BING_WEB_HTML, 10)
    urls = [r["url"] for r in out]
    assert urls == ["https://example.com/python", "https://example.org/snake"]
    assert out[0]["title"] == "Python tutorial"
    assert "python" in out[0]["snippet"].lower()


def test_parse_web_empty():
    assert ws._parse_web("", 5) == []
    assert ws._parse_web("   ", 5) == []


def test_parse_ddg_unwraps_and_drops_ads():
    out = ws._parse_ddg(DDG_HTML, 10)
    assert len(out) == 1
    assert out[0]["url"] == "https://example.com/ddg"
    assert out[0]["title"] == "DDG title"


def test_parse_yahoo_unwraps_ru_and_strips_breadcrumb():
    html = """<html><body><div id="main"><div id="web">
<div class="dd algo"><div class="compTitle"><h3 class="title"><a href="https://r.search.yahoo.com/_ylt=abc/RU=https%3a%2f%2fexample.com%2fpage/RK=2/RS=x">Example Title<span class="cite">example.com › page</span></a></h3></div>
<div class="compText"><p>Example snippet.</p></div></div>
<div class="dd algo"><div class="compTitle"><h3 class="title"><a href="https://example.org/direct">Direct</a></h3></div></div>
<div class="dd"><div class="compTitle"><h3 class="title"><a href="https://search.yahoo.com/search?p=x">internal</a></h3></div></div>
</div></div></body></html>"""
    out = ws._parse_yahoo(html, 10)
    assert len(out) == 2  # internal yahoo link dropped
    assert out[0]["url"] == "https://example.com/page"
    assert out[0]["title"] == "Example Title"
    assert out[0]["snippet"] == "Example snippet."
    assert out[1]["url"] == "https://example.org/direct"


def test_yahoo_is_first_web_backend():
    names = [b[0] for b in ws._search_backends("q", 5, False, "")]
    assert names[0] == "yahoo"


def test_parse_bing_rss():
    out = ws._parse_bing_rss(BING_RSS, 10)
    assert len(out) == 2  # <item foo="bar"> must also match (bugfix)
    assert out[0]["title"] == "Item one"
    assert out[0]["age"] == "Mon, 01 Jan 2024"


def test_parse_google_news_rss():
    out = ws._parse_google_news_rss(GNEWS_RSS, 10)
    assert len(out) == 1
    assert out[0]["source"] == "BBC"
    assert out[0]["snippet"] == ""


def test_parse_marginalia():
    out = ws._parse_marginalia(MARGINALIA_JSON, 10)
    assert out[0] == {"title": "T", "url": "https://example.com/m",
                      "snippet": "d"}


def test_parse_marginalia_bad_json():
    assert ws._parse_marginalia(b"not json", 5) == []


# ------------------------------------------------------- block detection

def test_backend_blocked_html():
    assert ws._backend_blocked("bing_html", BLOCK_HTML.encode()) is True
    assert ws._backend_blocked("bing_html", b"<html>normal results</html>") is False


def test_backend_blocked_rss_bom_not_blocked():
    # BOM-prefixed real RSS must NOT be classified as blocked (bugfix).
    assert ws._backend_blocked("bing_rss", BING_RSS_BOM) is False
    assert ws._backend_blocked("bing_rss", b"<html>nope</html>") is True


def test_backend_blocked_ddg_challenge():
    html = b'<div class="anomaly-modal">select all images</div>'
    assert ws._backend_blocked("duckduckgo", html) is True


# ------------------------------------------------------------- url utils

def test_canonical_url_strips_tracking():
    u = ws._canonical_url("https://example.com/p?utm_source=x&fbclid=1&q=2")
    assert u == "https://example.com/p?q=2"


def test_usable_result_url_rejects_credentials():
    # bugfix: embedded userinfo must not leak into results
    assert ws._usable_result_url("https://user:pass@example.com/") is None
    assert ws._usable_result_url("https://example.com/ok") == "https://example.com/ok"


def test_usable_result_url_rejects_bing():
    assert ws._usable_result_url("https://www.bing.com/search?q=x") is None


def test_unwrap_ddg():
    assert ws._unwrap_ddg("//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2F") == \
        "https://example.com/"
    assert ws._unwrap_ddg("//duckduckgo.com/l/?uddg=x&ad_provider=y") is None


def test_resolve_for_no_brackets_on_ipv6():
    # bugfix: CURLOPT_RESOLVE needs bare IPv6, not [::1]
    entries = ws._resolve_for("example.com", 443, ("93.184.216.34", "::1"))
    assert entries == ("example.com:443:93.184.216.34", "example.com:443:::1")
    assert "[" not in entries[1]


# ------------------------------------------------- relevance / dedupe

def test_relevance_score_title_weighted():
    s1 = ws._relevance_score("python tutorial", "Python tutorial here", "")
    s2 = ws._relevance_score("python tutorial", "Unrelated", "python tutorial inside")
    assert s1 > s2 > 0


def test_relevance_score_empty_query():
    assert ws._relevance_score("", "t", "s") == 0.0


def test_near_dedupe():
    rs = [
        {"title": "Python tutorial", "snippet": "learn python basics"},
        {"title": "Python tutorial", "snippet": "learn python basics!"},
        {"title": "Different topic", "snippet": "something else entirely"},
    ]
    out = ws._near_dedupe(rs)
    assert len(out) == 2


def test_dedupe_by_url():
    rs = [{"title": "a", "url": "https://example.com/x?a=1&utm_x=2"},
          {"title": "b", "url": "https://example.com/x?a=1"}]
    out = ws._dedupe(rs, 10)
    assert len(out) == 1 and out[0]["title"] == "a"


# ------------------------------------------------------------- validators

def test_query_validator():
    assert ws._query("  hello ") == "hello"
    with pytest.raises(ws.InputError):
        ws._query("   ")
    with pytest.raises(ws.InputError):
        ws._query("x" * 1001)


def test_count_validator():
    assert ws._count(5) == 5
    assert ws._count(9999) == ws.MAX_RESULTS
    with pytest.raises(ws.InputError):
        ws._count(0)
    with pytest.raises(ws.InputError):
        ws._count(True)


def test_freshness_validator():
    assert ws._freshness("day") == "day"
    assert ws._freshness("") == ""
    with pytest.raises(ws.InputError):
        ws._freshness("year")


def test_binary_detection():
    assert ws._is_binary_content_type("image/png") is True
    assert ws._is_binary_content_type("text/html; charset=utf-8") is False
    assert ws._is_binary_content_type_or_magic("application/octet-stream", b"%PDF-1.4...") is True
    assert ws._is_binary_content_type_or_magic("application/octet-stream", b"<html>hi") is False


def test_paginate():
    page, truncated, nxt = ws._paginate("abcdefgh", 2, 3)
    assert (page, truncated, nxt) == ("cde", True, 5)
    page, truncated, nxt = ws._paginate("abcdefgh", 6, 10)
    assert (page, truncated, nxt) == ("gh", False, None)


def test_is_public_ip():
    import ipaddress
    assert ws._is_public_ip(ipaddress.ip_address("8.8.8.8")) is True
    assert ws._is_public_ip(ipaddress.ip_address("192.168.1.1")) is False
    assert ws._is_public_ip(ipaddress.ip_address("127.0.0.1")) is False
    # NAT64 wrapping loopback must be rejected
    assert ws._is_public_ip(ipaddress.ip_address("64:ff9b::7f00:1")) is False


def test_truncate_json_keeps_validity():
    import json
    big = json.dumps({"title": "t", "text": "x" * 5000})
    out = ws._truncate_json(big, 100)
    data = json.loads(out)
    assert data["truncated"] is True and len(data["text"]) <= 100
