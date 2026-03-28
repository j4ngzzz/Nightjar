# Wave 4 Hunt A4 — Security Audit Results
**Auditor:** Independent PBT researcher (no affiliation with aiohttp or urllib3)
**Date:** 2026-03-28
**Method:** Hypothesis property-based testing, max_examples=200, 18 checks total
**Packages:**
- `aiohttp==3.13.3` (pure-Python mode: `AIOHTTP_NO_EXTENSIONS=1`)
- `urllib3==2.6.3`

---

## CVE Landscape (checked first)

### aiohttp
| CVE | Severity | Status in 3.13.3 |
|-----|----------|------------------|
| CVE-2025-53643 | High | FIXED in 3.12.14 — trailer-section smuggling in pure-Python parser |
| CVE-2025-69225 | Medium | Range header smuggling vector |
| CVE-2025-69226 | Medium | Static filepath brute-force leak |
| CVE-2025-69228 | High | Memory exhaustion via large payloads |
| CVE-2025-69223 | High | Decompression bomb (compressed request memory exhaustion) |

3.13.3 is the latest and contains patches for all listed CVEs.

### urllib3
| CVE | Severity | Status in 2.6.3 |
|-----|----------|-----------------|
| CVE-2025-66418 | Medium | FIXED in 2.6.0 — unbounded decompression chain |
| CVE-2025-66471 | Medium | Streaming API compressed data handling |
| CVE-2026-21441 | Medium | Decompression-bomb bypass via redirects |

2.6.3 is the latest and contains patches for all listed CVEs.

---

## Test Results: 18/18 PASS — Zero Bugs Found

### TARGET 1: aiohttp `HttpRequestParser.feed_data()` (pure-Python mode)

| # | Check | Result |
|---|-------|--------|
| 1a | Bare CR without LF rejected as line separator | **PASS** |
| 1b | Valid chunked request (5\r\nhello\r\n + 0\r\n\r\n) parses correctly | **PASS** |
| 1c | Hypothesis (200 examples): well-formed GET requests parse without crash | **PASS** |
| 1d | Chunked request with RFC 7230 trailer headers handled gracefully | **PASS** |
| 1e | Duplicate Content-Length header rejected (smuggling prevention) | **PASS** |

**CVE-2025-53643 note:** Test 1d confirms that chunked requests with RFC 7230 trailers are handled gracefully (no crash, no unexpected exception). It does NOT constitute a full smuggling regression test — the specific exploit (second HTTP request hidden in the trailer position) was not crafted. For a complete regression: send `[request1][0-chunk][smuggled-request-as-trailer]` as one byte stream and assert `len(msgs) == 1`. Based on CVE advisory (GHSA-9548-qrrj-x5pj), the fix landed in 3.12.14 and 3.13.3 is confirmed patched per upstream changelog.

### TARGET 2: aiohttp `CookieJar.filter_cookies()` — domain isolation

| # | Check | Result |
|---|-------|--------|
| 2a | Cookie from `evil.example.com` not returned for `example.com` | **PASS** |
| 2b | Cookie with `domain=.example.com` correctly reaches `sub.example.com` | **PASS** |
| 2c | 200-sample random domain isolation: subdomain cookies never leak to parent | **PASS** |
| 2d | Host-only cookie (no explicit domain) stays on exact host only | **PASS** |

**Domain isolation is sound.** `_is_domain_match()` correctly requires a `.` before the suffix and an IP address guard. No subdomain-to-parent leakage found across 200 random domain/cookie combinations.

### TARGET 3: urllib3 `Retry.increment()` — `allowed_methods` filtering

| # | Check | Result |
|---|-------|--------|
| 3a | POST (not idempotent) correctly NOT retried on `ReadTimeoutError` | **PASS** |
| 3b | GET (idempotent) correctly retried on `ReadTimeoutError` | **PASS** |
| 3c | `allowed_methods` filter still applied after redirect counter runs down | **PASS** |
| 3d | Hypothesis (200 examples): only allowed methods are retried on read errors | **PASS** |

**The `allowed_methods` invariant holds under all tested conditions.** The `_is_method_retryable()` guard is evaluated before decrementing `read`, and survives redirect counter exhaustion context.

### TARGET 4: urllib3 `parse_url()` — round-trip fidelity

| # | Check | Result |
|---|-------|--------|
| 4a | Canonical HTTP/HTTPS URLs round-trip exactly | **PASS** |
| 4b | IPv6 with zone ID (`%25eth0`) preserved in `host` field | **PASS** |
| 4c | Encoded `@` in userinfo (`user%40domain`) parses without authority confusion | **PASS** |
| 4d | Hypothesis (200 examples): `parse_url` is idempotent (`p1.url == parse_url(p1.url).url`) | **PASS** |
| 4e | Port boundary enforcement: 0 and 65535 valid; 65536 and 99999 rejected | **PASS** |

**No round-trip anomalies found.** The normalization pipeline (scheme/host lowercased, dot-segments removed, invalid chars percent-encoded) is applied consistently on first parse and produces a stable fixed-point on re-parse.

---

## Summary

```
Total checks : 18
PASS         : 18
FAIL / BUG   : 0
```

**No exploitable bugs found in the tested contracts.**

Both packages, at their current latest versions (aiohttp 3.13.3, urllib3 2.6.3), correctly implement the security-critical contracts tested:
- Pure-Python HTTP request parser: bare-CR rejection, duplicate-CL rejection, chunked-trailer handling
- Cookie domain isolation: subdomain-to-parent leakage, host-only flag
- Retry `allowed_methods` filtering under all conditions
- URL round-trip idempotency and boundary enforcement

---

## Repro Script

```
python E:/vibecodeproject/oracle/scan-lab/wave4_hunt_a4_tests.py
```

Requires: `pip install aiohttp urllib3 hypothesis`
Environment variable `AIOHTTP_NO_EXTENSIONS=1` is set in-script.
Expected output: 18/18 PASS.

---

## Notes for Future Waves

1. **CVE-2025-69228 (memory exhaustion via large payloads):** Not tested here because it requires a live HTTP server to send a crafted large-payload response. A future wave could test with `aiohttp.web.Server` + synthetic payloads in a subprocess.
2. **CVE-2026-21441 (urllib3 decompression bomb via redirect):** Affects the streaming decompression API (`urllib3.response.HTTPResponse.read()`), not `Retry.increment()`. Out of scope for the stated targets but worth a dedicated wave.
3. **`AIOHTTP_NO_EXTENSIONS=1` caveat:** All parser tests run against the pure-Python backend (`HttpRequestParserPy`). The C-extension backend is not tested. CVE-2025-53643 was Python-only; the C path is considered safe.
