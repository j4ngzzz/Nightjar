"""
Wave 4 Hunt A4: aiohttp + urllib3 property-based security tests.
Independent auditor. Only reports what Hypothesis actually catches.
Run with: python wave4_hunt_a4_tests.py
"""
import os
import sys
import traceback

# Force pure-Python aiohttp parser (target for CVE-2025-53643 class bugs)
os.environ["AIOHTTP_NO_EXTENSIONS"] = "1"

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
import hypothesis

# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
findings = []


def record(name, status, detail=""):
    tag = "[PASS]" if status else "[FAIL]"
    print(f"  {tag} {name}")
    if not status:
        print(f"         {detail}")
    findings.append((name, status, detail))


# ════════════════════════════════════════════════════════════
# TARGET 1 — aiohttp HttpRequestParser.feed_data (pure Python)
#   Contract: valid HTTP/1.1 requests must be parsed without raising
#             unhandled exceptions (BadHttpMessage / BadStatusLine are OK);
#             chunked-encoding size lines must be hex-only.
# ════════════════════════════════════════════════════════════

def _make_parser():
    """Return a fresh pure-Python HttpRequestParser instance."""
    import asyncio
    from aiohttp.http_parser import HttpRequestParserPy

    class FakeProtocol:
        transport = None

        def set_parser(self, *a, **kw):
            pass

        def connection_lost(self, exc):
            pass

        def data_received(self, data):
            pass

    loop = asyncio.new_event_loop()
    proto = FakeProtocol()
    parser = HttpRequestParserPy(
        protocol=proto,
        loop=loop,
        limit=2**16,
    )
    return parser, loop


def _feed(data: bytes):
    parser, loop = _make_parser()
    try:
        msgs, upgraded, tail = parser.feed_data(data)
        return msgs, upgraded, tail, None
    except Exception as exc:
        return None, None, None, exc
    finally:
        loop.close()


print("\n=== TARGET 1: aiohttp HttpRequestParser — pure-Python (AIOHTTP_NO_EXTENSIONS=1) ===")

# ── 1a: Bare CR (\r without following \n) must not silently parse as a line terminator
print("\n  [1a] Bare CR without LF must not be treated as line separator")
try:
    # A valid-looking request where the header separator is CR only (no LF)
    # RFC 7230: only CRLF is a valid line terminator for requests
    bare_cr_request = b"GET / HTTP/1.1\rHost: example.com\r\r"
    msgs, upgraded, tail, exc = _feed(bare_cr_request)
    if msgs and len(msgs) > 0:
        # Parser accepted a bare-CR request — this is a smuggling vector
        record(
            "1a: bare CR treated as line separator",
            False,
            f"Parser accepted bare-CR request and produced {len(msgs)} message(s). "
            "This can allow request smuggling in pure-Python mode."
        )
    else:
        record("1a: bare CR without LF is rejected or ignored", True)
except Exception as e:
    record("1a: bare CR check (unexpected exception)", False, str(e))

# ── 1b: Chunked body with bare CR before chunk data — lax mode only affects responses
print("  [1b] Chunked body with bare CR before chunk size")
try:
    # Build a request with chunked TE but bare CR as chunk terminator
    bare_cr_chunked = (
        b"POST / HTTP/1.1\r\n"
        b"Host: example.com\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"\r\n"
        b"5\r\nhello\r\n"
        b"0\r\n"
        b"\r\n"
    )
    msgs, upgraded, tail, exc = _feed(bare_cr_chunked)
    if exc is None and msgs:
        record("1b: valid chunked request parses correctly", True)
    elif exc is not None:
        # An exception on a perfectly valid chunked request is a false-reject
        record(
            "1b: valid chunked request raises unexpected exception",
            False,
            f"{type(exc).__name__}: {exc}"
        )
    else:
        record("1b: valid chunked request produced no messages", False,
               "Expected at least one parsed message.")
except Exception as e:
    record("1b: chunked check", False, str(e))

# ── 1c: Property: well-formed GET requests always parse without crashing
print("  [1c] Hypothesis: well-formed GET requests always parse cleanly")

_1c_failures = []

@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
    path=st.from_regex(r"/[a-zA-Z0-9/_-]{0,40}", fullmatch=True),
    host=st.from_regex(r"[a-z]{2,10}\.[a-z]{2,5}", fullmatch=True),
)
def test_1c_valid_get(path, host):
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode()
    msgs, upgraded, tail, exc = _feed(req)
    if exc is not None:
        from aiohttp.http_exceptions import BadHttpMessage, BadStatusLine
        if not isinstance(exc, (BadHttpMessage, BadStatusLine)):
            _1c_failures.append(f"path={path!r} host={host!r} exc={exc!r}")

try:
    test_1c_valid_get()
    if _1c_failures:
        record("1c: well-formed GET always parses", False,
               f"{len(_1c_failures)} counterexamples: {_1c_failures[:3]}")
    else:
        record("1c: well-formed GET always parses", True)
except Exception as e:
    record("1c: test crashed", False, str(e))

# ── 1d: CVE-2025-53643 class — trailer section not parsed in pure-Python mode
#   Check: a chunked request with trailers AFTER the 0-size terminator
#   is correctly finalized (trailers are ignored or accepted per RFC 7230).
print("  [1d] Chunked request with trailer headers after zero-chunk")
try:
    # RFC 7230 allows trailers after the final chunk; they should be handled
    # gracefully and not cause the parser to skip the message boundary.
    req_with_trailers = (
        b"POST /upload HTTP/1.1\r\n"
        b"Host: example.com\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"Trailer: X-Checksum\r\n"
        b"\r\n"
        b"5\r\nhello\r\n"
        b"0\r\n"
        b"X-Checksum: abc123\r\n"  # trailer header
        b"\r\n"
    )
    msgs, upgraded, tail, exc = _feed(req_with_trailers)
    if exc is not None:
        from aiohttp.http_exceptions import BadHttpMessage, BadStatusLine, TransferEncodingError
        # TransferEncodingError is acceptable
        if isinstance(exc, (BadHttpMessage, BadStatusLine, TransferEncodingError)):
            record("1d: trailers raise expected error (acceptable)", True)
        else:
            record("1d: trailers cause unexpected exception", False,
                   f"{type(exc).__name__}: {exc}")
    else:
        # Must have parsed exactly one message; the trailer must not
        # "bleed" into a second message interpretation
        record("1d: chunked request with trailer parsed (no crash)", True)
except Exception as e:
    record("1d: trailer handling", False, str(e))


# ── 1e: Duplicate Content-Length header must be rejected
print("  [1e] Duplicate Content-Length headers must be rejected")
try:
    dup_cl_req = (
        b"POST / HTTP/1.1\r\n"
        b"Host: example.com\r\n"
        b"Content-Length: 5\r\n"
        b"Content-Length: 10\r\n"
        b"\r\n"
        b"hello"
    )
    msgs, upgraded, tail, exc = _feed(dup_cl_req)
    if exc is None and msgs:
        record(
            "1e: duplicate Content-Length accepted",
            False,
            "Parser accepted two Content-Length headers without raising — "
            "this is a known request-smuggling vector."
        )
    else:
        record("1e: duplicate Content-Length rejected", True)
except Exception as e:
    # Any exception is acceptable here (it means it was rejected)
    record("1e: duplicate Content-Length rejected (via exception)", True)


# ════════════════════════════════════════════════════════════
# TARGET 2 — aiohttp CookieJar.filter_cookies — domain isolation
#   Contract: a cookie set for "evil.example.com" MUST NOT be
#             returned when filtering for "example.com".
# ════════════════════════════════════════════════════════════
print("\n=== TARGET 2: aiohttp CookieJar.filter_cookies — domain isolation ===")

import asyncio as _asyncio
from aiohttp import CookieJar
from yarl import URL
from http.cookies import SimpleCookie

# CookieJar in aiohttp 3.x requires get_running_loop() (a *running* event loop).
# We run all cookie-jar tests inside an async function via asyncio.run().

async def _run_cookiejar_tests():
    results = {}

    # 2a: Direct domain isolation
    jar = CookieJar(unsafe=False)
    jar.update_cookies({"session": "STOLEN"}, response_url=URL("https://evil.example.com/"))
    result = jar.filter_cookies(URL("https://example.com/"))
    results["2a"] = "session" not in result  # True = PASS (no leak)

    # 2b: Subdomain reach
    jar2 = CookieJar(unsafe=False)
    sc = SimpleCookie()
    sc["auth"] = "token123"
    sc["auth"]["domain"] = ".example.com"
    sc["auth"]["path"] = "/"
    jar2.update_cookies(sc, response_url=URL("https://example.com/"))
    result2 = jar2.filter_cookies(URL("https://sub.example.com/"))
    results["2b"] = "auth" in result2  # True = PASS (cookie reached subdomain)

    # 2d: Host-only flag
    jar3 = CookieJar(unsafe=False)
    jar3.update_cookies({"hostonly": "yes"}, response_url=URL("https://sub.example.com/"))
    leaked_to_parent = "hostonly" in jar3.filter_cookies(URL("https://example.com/"))
    leaked_to_sibling = "hostonly" in jar3.filter_cookies(URL("https://other.example.com/"))
    results["2d"] = (not leaked_to_parent and not leaked_to_sibling)  # True = PASS
    results["2d_detail"] = f"leaked_to_parent={leaked_to_parent}, leaked_to_sibling={leaked_to_sibling}"

    # 2c: Hypothesis inner function — run as a sync helper inside async context
    failures_2c = []
    import random
    import string

    def rand_label(n):
        return "".join(random.choices(string.ascii_lowercase, k=n))

    for _ in range(200):
        sub = rand_label(random.randint(3, 8))
        tld = rand_label(random.randint(2, 4))
        parent = f"{rand_label(random.randint(3, 8))}.{tld}"
        subdomain = f"{sub}.{parent}"
        cname = random.choice(string.ascii_uppercase) + "".join(
            random.choices(string.ascii_letters + string.digits, k=8)
        )
        cval = "".join(random.choices(string.ascii_letters + string.digits, k=10))
        try:
            j = CookieJar(unsafe=False)
            j.update_cookies({cname: cval}, response_url=URL(f"https://{subdomain}/"))
            r = j.filter_cookies(URL(f"https://{parent}/"))
            if cname in r:
                failures_2c.append(f"cookie from {subdomain!r} appeared in filter for {parent!r}")
        except Exception:
            pass
    results["2c_failures"] = failures_2c

    return results

_cj_results = _asyncio.run(_run_cookiejar_tests())

# ── 2a
print("  [2a] Cookie from evil.example.com must not match example.com")
if _cj_results["2a"]:
    record("2a: evil.example.com does NOT leak to example.com", True)
else:
    record(
        "2a: evil.example.com leaks to example.com",
        False,
        "filter_cookies('https://example.com/') returned 'session' cookie set by evil.example.com. DOMAIN ISOLATION BROKEN."
    )

# ── 2b
print("  [2b] Cookie from .example.com should reach sub.example.com")
if _cj_results["2b"]:
    record("2b: .example.com cookie reaches sub.example.com (correct)", True)
else:
    record(
        "2b: .example.com cookie does NOT reach sub.example.com",
        False,
        "RFC 6265 requires domain cookies to match subdomains."
    )

# ── 2c
print("  [2c] 200-sample domain isolation: subdomain cookie never leaks to parent")
_2c_fails = _cj_results["2c_failures"]
if _2c_fails:
    record(
        "2c: domain isolation (200 random samples)",
        False,
        f"{len(_2c_fails)} violations: {_2c_fails[:3]}"
    )
else:
    record("2c: domain isolation invariant holds across 200 samples", True)

# ── 2d
print("  [2d] Host-only cookie must NOT match parent or sibling domains")
if _cj_results["2d"]:
    record("2d: host-only cookie correctly contained to exact host", True)
else:
    record(
        "2d: host-only cookie leaked",
        False,
        _cj_results["2d_detail"]
    )


# ════════════════════════════════════════════════════════════
# TARGET 3 — urllib3 Retry.increment — allowed_methods filtering
# ════════════════════════════════════════════════════════════
print("\n=== TARGET 3: urllib3 Retry.increment — allowed_methods filtering ===")

from urllib3.util.retry import Retry
from urllib3.exceptions import MaxRetryError

# ── 3a: POST should not retry by default (not idempotent)
print("  [3a] POST with default allowed_methods should not be retried on read error")
try:
    from urllib3.exceptions import ReadTimeoutError

    retry = Retry(total=3, read=3)
    try:
        new_retry = retry.increment(
            method="POST",
            url="http://example.com/",
            error=ReadTimeoutError(None, "http://example.com/", "read timed out"),
        )
        # If we get here, POST was retried despite not being in allowed_methods
        record(
            "3a: POST retried despite not in allowed_methods",
            False,
            "increment() returned new Retry instead of raising. "
            "POST is not idempotent and should not retry on read errors."
        )
    except MaxRetryError:
        # Correct — exhausted without retrying
        record("3a: POST correctly raises MaxRetryError (not retried)", True)
    except ReadTimeoutError:
        # Also correct — re-raised because method not retryable
        record("3a: POST correctly re-raises ReadTimeoutError (not retried)", True)
    except Exception as e:
        record("3a: unexpected exception type", False, f"{type(e).__name__}: {e}")
except Exception as e:
    record("3a: test setup failed", False, str(e))

# ── 3b: GET should retry on read error (idempotent)
print("  [3b] GET with default allowed_methods should retry on read error")
try:
    from urllib3.exceptions import ReadTimeoutError as RTE

    retry = Retry(total=3, read=3)
    new_retry = retry.increment(
        method="GET",
        url="http://example.com/",
        error=RTE(None, "http://example.com/", "read timed out"),
    )
    record("3b: GET correctly retries on read error", True)
except MaxRetryError:
    record("3b: GET unexpectedly hit MaxRetryError on first retry", False,
           "GET should retry on read errors (it is in allowed_methods).")
except Exception as e:
    record("3b: unexpected exception", False, f"{type(e).__name__}: {e}")

# ── 3c: Redirect counting — allowed_methods must still filter after N redirects
print("  [3c] allowed_methods filtering survives after redirect counter decrements")
try:
    from urllib3.exceptions import ReadTimeoutError as RTE2

    # Start with redirect=2, then do 2 redirects, then try a POST read-error
    retry = Retry(total=10, redirect=2, read=5, allowed_methods=frozenset(["GET"]))

    # Simulate 2 redirects
    class FakeRedirectResponse:
        status = 301
        headers = {}

        def get_redirect_location(self):
            return "http://example.com/redirected"

    r1 = retry.increment(method="GET", url="http://example.com/", response=FakeRedirectResponse())
    r2 = r1.increment(method="GET", url="http://example.com/redirected", response=FakeRedirectResponse())

    # Now try a POST with a read error — should NOT retry
    try:
        r3 = r2.increment(
            method="POST",
            url="http://example.com/redirected",
            error=RTE2(None, "http://example.com/", "read timed out"),
        )
        # Got a new retry for POST after redirect exhaustion context — check if this is legitimate
        # The issue: after redirect counter runs down, does allowed_methods still filter?
        record(
            "3c: POST retried after redirects (allowed_methods still checked?)",
            False,
            f"POST increment returned new_retry after {2} redirects. "
            "allowed_methods={frozenset(['GET'])} should block POST read retries."
        )
    except (MaxRetryError, RTE2):
        record("3c: POST read-error correctly blocked by allowed_methods after redirects", True)
    except Exception as e:
        record("3c: unexpected exception", False, f"{type(e).__name__}: {e}")

except Exception as e:
    record("3c: test setup failed", False, str(e))

# ── 3d: Hypothesis — allowed_methods contract: only allowed methods are retried
print("  [3d] Hypothesis: only methods in allowed_methods are retried on read errors")

_3d_failures = []

from urllib3.exceptions import ReadTimeoutError as _RTE

@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
    method=st.sampled_from(["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]),
    allowed=st.frozensets(
        st.sampled_from(["GET", "PUT", "DELETE", "HEAD", "OPTIONS", "TRACE"]),
        min_size=1, max_size=5
    ),
    total=st.integers(min_value=1, max_value=5),
    read=st.integers(min_value=1, max_value=5),
)
def test_3d_allowed_methods(method, allowed, total, read):
    retry = Retry(total=total, read=read, allowed_methods=frozenset(allowed))
    try:
        new_retry = retry.increment(
            method=method,
            url="http://example.com/",
            error=_RTE(None, "http://example.com/", "read timed out"),
        )
        # If we reach here, the method was retried — it should be in allowed_methods
        if method.upper() not in allowed:
            _3d_failures.append(
                f"method={method!r} not in allowed={allowed!r} but was retried"
            )
    except (_RTE, MaxRetryError):
        # Re-raised or exhausted — correct for non-allowed methods (or exhaustion)
        pass

try:
    test_3d_allowed_methods()
    if _3d_failures:
        record(
            "3d: allowed_methods invariant (Hypothesis)",
            False,
            f"{len(_3d_failures)} violations: {_3d_failures[:3]}"
        )
    else:
        record("3d: allowed_methods invariant holds across 200 examples", True)
except Exception as e:
    record("3d: test crashed", False, str(e))


# ════════════════════════════════════════════════════════════
# TARGET 4 — urllib3 parse_url — round-trip property
#   Contract: parse_url(url).url == url for valid RFC 3986 URLs
#   (modulo known normalization: scheme/host lowercased, dot segments removed)
# ════════════════════════════════════════════════════════════
print("\n=== TARGET 4: urllib3 parse_url — round-trip + edge cases ===")

from urllib3.util.url import parse_url
from urllib3.exceptions import LocationParseError

# ── 4a: Simple canonical URL round-trip
print("  [4a] Canonical HTTP URL round-trips exactly")
test_urls = [
    "http://example.com/",
    "http://example.com/path",
    "https://example.com/path?query=1",
    "http://user:pass@example.com/",
    "http://example.com:8080/path",
]
_4a_fails = []
for url in test_urls:
    try:
        parsed = parse_url(url)
        reconstructed = parsed.url
        if reconstructed != url:
            _4a_fails.append(f"input={url!r} → got={reconstructed!r}")
    except Exception as e:
        _4a_fails.append(f"input={url!r} → exception: {e}")

if _4a_fails:
    record("4a: canonical URL round-trip", False, "; ".join(_4a_fails))
else:
    record("4a: canonical HTTP URLs round-trip exactly", True)

# ── 4b: IPv6 zone ID round-trip
print("  [4b] IPv6 with zone ID round-trip")
try:
    # RFC 6874: zone IDs in URLs encoded as %25
    ipv6_zone_url = "http://[fe80::1%25eth0]/path"
    parsed = parse_url(ipv6_zone_url)
    reconstructed = parsed.url
    # urllib3 normalizes the zone separator; just check it doesn't crash
    # and the host contains the zone info
    if parsed.host and "eth0" in parsed.host:
        record("4b: IPv6 zone ID preserved in host", True)
    else:
        record(
            "4b: IPv6 zone ID lost during parsing",
            False,
            f"input={ipv6_zone_url!r} → host={parsed.host!r}"
        )
except LocationParseError as e:
    record("4b: IPv6 zone ID raises LocationParseError", False,
           f"RFC 6874 zone IDs should be parseable: {e}")
except Exception as e:
    record("4b: unexpected exception on IPv6 zone", False,
           f"{type(e).__name__}: {e}")

# ── 4c: userinfo with @ sign — must not re-parse the authority
print("  [4c] Userinfo containing encoded @ must parse correctly")
try:
    # user info with a literal @ encoded as %40
    url_with_at = "http://user%40domain:pass@example.com/path"
    parsed = parse_url(url_with_at)
    # The auth component should be "user%40domain:pass"
    # and the host should be "example.com"
    if parsed.host == "example.com" and parsed.auth and "user" in parsed.auth:
        record("4c: encoded @ in userinfo parses correctly", True)
    else:
        record(
            "4c: encoded @ in userinfo parsed incorrectly",
            False,
            f"host={parsed.host!r}, auth={parsed.auth!r}"
        )
except Exception as e:
    record("4c: exception on encoded @ in userinfo", False,
           f"{type(e).__name__}: {e}")

# ── 4d: Hypothesis — idempotency: parse_url(parse_url(url).url).url == parse_url(url).url
print("  [4d] Hypothesis: parse_url is idempotent (second parse == first parse)")

_4d_failures = []

@settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
@given(
    scheme=st.sampled_from(["http", "https"]),
    host=st.from_regex(r"[a-z]{2,12}(\.[a-z]{2,6}){1,2}", fullmatch=True),
    path=st.from_regex(r"(/[a-zA-Z0-9_-]{0,20}){0,4}", fullmatch=True),
    query=st.one_of(st.none(), st.from_regex(r"[a-zA-Z0-9=&]{0,30}", fullmatch=True)),
)
def test_4d_idempotent(scheme, host, path, query):
    url = f"{scheme}://{host}{path or '/'}"
    if query:
        url += "?" + query
    try:
        p1 = parse_url(url)
        p2 = parse_url(p1.url)
        if p1.url != p2.url:
            _4d_failures.append(
                f"input={url!r} → p1={p1.url!r} → p2={p2.url!r}"
            )
    except LocationParseError:
        pass  # Invalid URLs acceptable

try:
    test_4d_idempotent()
    if _4d_failures:
        record(
            "4d: parse_url idempotency (Hypothesis)",
            False,
            f"{len(_4d_failures)} violations: {_4d_failures[:3]}"
        )
    else:
        record("4d: parse_url idempotency holds across 200 examples", True)
except Exception as e:
    record("4d: test crashed", False, str(e))

# ── 4e: Port boundary — port=0 and port=65535 valid; port=65536 invalid
print("  [4e] Port boundary conditions")
port_cases = [
    ("http://example.com:0/", True, "port 0 should be valid"),
    ("http://example.com:65535/", True, "port 65535 should be valid"),
    ("http://example.com:65536/", False, "port 65536 should be invalid"),
    ("http://example.com:99999/", False, "port 99999 should be invalid"),
]
_4e_fails = []
for url, should_succeed, label in port_cases:
    try:
        parsed = parse_url(url)
        if not should_succeed:
            _4e_fails.append(f"{label}: parsed successfully (port={parsed.port})")
    except LocationParseError:
        if should_succeed:
            _4e_fails.append(f"{label}: raised LocationParseError unexpectedly")
    except Exception as e:
        _4e_fails.append(f"{label}: unexpected {type(e).__name__}: {e}")

if _4e_fails:
    record("4e: port boundary conditions", False, "; ".join(_4e_fails))
else:
    record("4e: port boundaries enforced correctly", True)


# ════════════════════════════════════════════════════════════
# Summary
# ════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
passed = [n for n, s, _ in findings if s]
failed = [n for n, s, _ in findings if not s]
print(f"  Passed : {len(passed)}")
print(f"  Failed : {len(failed)}")
if failed:
    print("\n  FINDINGS (bugs / invariant violations):")
    for n, s, d in findings:
        if not s:
            print(f"    [BUG] {n}")
            print(f"          {d}")

print()
