# Bugs found & fixed

Upstream: https://github.com/digitalninjanv/free-web-search (cloned 2026-10-01).
Method: full code read + a new offline test suite (26 tests) + one live smoke test.
The repo's README promised `tests/` + CI; they were never shipped, so the
suite below was written from scratch against the documented output contract.

## B1 — Promised test suite does not exist
- **Finding:** README documents `tests/test_websearch.py`, fixture files and a
  CI workflow running pytest. None of them exist in the repo.
- **Fix:** wrote `tests/test_websearch.py` (26 offline tests: all parsers,
  block detection, URL utils, validators, relevance/dedupe, pagination).
  Result: **26/26 pass**.

## B2 — Dead "fast path → escalate" fallback in trafilatura extraction
- **Root cause:** `_extract_with_trafilatura()` builds kwargs *without* ever
  setting `fast` (trafilatura defaults `fast=False`), then the fallback does
  `fallback_kwargs.pop("fast", None)` — a guaranteed no-op — and re-runs the
  **identical** slow call. The comment claiming "Fast is the normal hot path"
  was false.
- **Fix:** set `fast=True` in the initial call; the fallback now genuinely
  escalates (`fast=False` + drops the custom `MAX_TREE_SIZE` config cap).

## B3 — IPv6 addresses bracketed in CURLOPT_RESOLVE entries
- **Root cause:** `_resolve_for()` produced `host:port:[::1]`. libcurl's
  RESOLVE format requires a **bare** IPv6 address (`host:port:::1`); the
  bracketed form is unparseable, so DNS pinning silently failed for every
  IPv6 target (connection failure / pinning bypass).
- **Fix:** emit the address bare: `f"{hostname}:{port}:{ip}"`.
- Covered by `test_resolve_for_no_brackets_on_ipv6`.

## B4 — BOM-prefixed RSS misclassified as blocked
- **Root cause:** `_backend_blocked()` sniffed `raw.lstrip()[:5]`; a feed
  starting with a UTF-8 BOM (`\xef\xbb\xbf<?xml`) failed the `<?xml`/`<rss`
  check and was reported as a captcha/block page.
- **Fix:** strip the BOM before sniffing.
- Covered by `test_backend_blocked_rss_bom_not_blocked`.

## B5 — URLs with embedded credentials leaked into results
- **Root cause:** `_usable_result_url()` never checked for userinfo, so a
  result like `https://user:pass@host/` passed canonicalization into output.
- **Fix:** reject any result URL containing a username/password.
- Covered by `test_usable_result_url_rejects_credentials`.

## B6 — RSS `<item>` regex missed items with attributes
- **Root cause:** both RSS parsers used `<item>(.*?)</item>`; an item written
  as `<item foo="bar">` was silently skipped.
- **Fix:** `<item[^>]*>(.*?)</item>` in both parsers.
- Covered by `test_parse_bing_rss` (second item has an attribute).

## Live smoke test (2026-10-01, one query only)
`search "python programming" --num 2` from this sandbox returned structured
`status=error`: the sandbox's DNS sinkholes `www.bing.com` to `198.18.131.11`
(RFC 2544 benchmarking range, not globally routable), which the SSRF guard
**correctly rejected**. No crash, contract shape intact (`query`,
`source_type`, `status`, `backend`, `message`, `results`). Live backend
success could not be verified from this network; verify from Render/your
machine with: `python websearch.py search "test" --num 2 --urls-only`.
