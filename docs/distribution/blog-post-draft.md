# 48 bugs, 20 codebases, one tool: what formal verification finds that tests miss

> **Note:** All security findings filed with maintainers before publication.

---

## The one-liner that crashes Karpathy's tokenizer

```python
BasicTokenizer().train('a', 258)
```

That call requests two BPE merges on a single character. There are zero consecutive pairs to merge. On the first iteration, `max(stats, key=stats.get)` raises `ValueError: max() iterable argument is empty`. No guard, no fallback, just a crash.

This is not a theoretical edge case. Any user who passes a short or repetitive training string with a `vocab_size` that requests more merges than the text can support hits this instantly. The one-liner `BasicTokenizer().train('a', 258)` is a valid API call to one of the most-forked ML repositories on GitHub. It crashes in every version of minbpe.

We found it in four seconds with Hypothesis.

---

## What we ran

Nightjar is a verification pipeline for Python code. The core idea: write a contract (`.card.md` spec), run a pipeline that mathematically checks the contract holds. For this scan, we used the pipeline's property-based testing stage — built on Hypothesis — to check invariants across 20 codebases: Tier 1 infrastructure packages (requests, httpx, fastapi), Tier 2 AI tooling (fastmcp, litellm), security libraries (python-jose, passlib, authlib, PyJWT, itsdangerous), AI agent frameworks (DeerFlow, Open-SWE, Hermes), Karpathy's minbpe tokenizer, and MiroFish — a recently viral vibe-coded application.

The methodology was consistent across all targets: extract functions, write invariant specs, feed Hypothesis 500–1000 random inputs per function, confirm any failure by manual reproduction. False positives were explicitly tracked and excluded. 21 of the bugs we found were verified by running `python scan-lab/repro-scripts.py` against installed packages on a clean Python 3.14 environment. Zero false positives in the verified set.

Total confirmed bugs: 48. Total codebases scanned: 20.

---

## Security findings: authentication infrastructure is fragile

The most consequential findings came from the JWT and OAuth ecosystem — packages that handle authentication for millions of Python applications.

**fastmcp 2.14.5** ships four high-severity authentication bugs in a single file. In `jwt_issuer.py`, the expiry check reads:

```python
exp = payload.get("exp")
if exp and exp < time.time():
    raise JoseError("Token has expired")
```

`if exp` is a Python truthiness check. When `exp=None` (no expiry field in the token), the check evaluates to `False` — token accepted, never expires. When `exp=0` (January 1, 1970, Unix epoch), `if 0` evaluates to `False` — a token from 1970 is accepted. Both confirmed with direct execution. In the same package, the OAuth redirect URI validator uses `fnmatch` on raw URL strings. `fnmatch` treats `*` as matching any characters, including `.`, `/`, `?`, and `=`. This means `https://evil.com/cb?legit.example.com/x` passes the pattern `https://*.example.com/*`. The OAuth authorization code goes to `evil.com`. Confirmed. A fourth bug: the docstring for `OAuthProxyProvider` states that `allowed_client_redirect_uris=None` defaults to "localhost-only." The actual code returns `True` for all URIs when the parameter is `None`. Developers who read the docs and rely on the default are fully exposed.

**python-jose 3.5.0** contains a surviving vulnerability related to CVE-2024-33663/33664: `jwt.decode(token, key, algorithms=None)` skips the algorithm allowlist entirely. The default API call omits `algorithms`, defaulting to `None`. Any application using python-jose without explicitly passing an algorithms list is accepting tokens signed with any algorithm — including HS256 tokens crafted with your RS256 public key as the HMAC secret.

**passlib 1.7.4** is broken against bcrypt 4.x and 5.x. The failure chain: passlib reads `bcrypt.__about__.__version__` at startup (removed in bcrypt 4.0), then calls its internal `detect_wrap_bug()` probe which passes a 255-byte password to `bcrypt.hashpw()`. bcrypt 5.0 now enforces the 72-byte limit strictly. The probe raises `ValueError: password cannot be longer than 72 bytes` — uncaught, propagating through `passlib_bcrypt.hash(any_password)`. Authentication is completely broken on any system running both packages at current versions.

---

## MiroFish: three HIGH-severity bugs in a billionaire-funded AI project

MiroFish is a social media simulation platform backed by significant investment. The backend is Flask. It appears to have been substantially AI-generated. We found six bugs; three are HIGH severity.

The config file contains:

```python
SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
```

Any deployment without a `.env` file uses the publicly-known secret key `'mirofish-secret-key'` to sign session cookies — trivially exploitable for session forgery. `DEBUG=True` enables Werkzeug's interactive debugger with PIN-based remote code execution.

The `platform` query parameter in `GET /api/simulation/<sim_id>/profiles?platform=...` is passed directly to `os.path.join` as a path component. No validation. `platform=../../../etc/passwd%00` reads arbitrary files; the `_profiles.json` suffix requirement limits but does not eliminate exploitability.

The third HIGH bug: `split_text_into_chunks` accepts user-supplied `chunk_size` and `chunk_overlap` parameters from the API with no server-side validation that `overlap < chunk_size`. When `overlap >= chunk_size`, `end - overlap <= start` and the loop never advances. `POST /api/graph/build` with `chunk_size=10, chunk_overlap=10` hangs the server process indefinitely.

These are not subtle. A single code review pass would have caught all three. They were caught by the pipeline in under two minutes.

---

## AI agent frameworks: the bugs where it matters most

The three AI agent frameworks we scanned — DeerFlow (ByteDance), Open-SWE (LangChain), and Hermes (NousResearch) — all had confirmed bugs in their core infrastructure. These are frameworks that run autonomous agents. A silent data corruption or deadlock is qualitatively worse here than in a utility library.

**DeerFlow** has an asyncio deadlock in `backend/packages/harness/deerflow/mcp/cache.py`. An `asyncio.Lock()` is created at module import time, outside any event loop. When two concurrent requests both see a cold cache, they each spin up `asyncio.run()` in separate threads, creating independent event loops. The lock belongs to the first thread's completed loop — the second thread deadlocks indefinitely. On the first pair of concurrent requests after startup, one hangs until the request timeout fires as a 5xx.

**Open-SWE** contains a one-character bug with high operational impact. The middleware safety net that catches failed PR creation checks:

```python
if "success" in pr_payload:
    return None
```

The tool always returns a dict with a `"success"` key — including on failure. `"success" in {"success": False, ...}` is `True`. The middleware returns `None` on every tool failure, abandoning the recovery attempt silently. When a push is rejected or a token expires, the agent ends the run without creating the PR and without any error escalation. The correct check is `pr_payload.get("success")`.

**Hermes** has a `fuzzy_find_and_replace` function with `replace_all=True` that corrupts unrelated code. Strategy 8 (`_strategy_context_aware`) accepts a block as a match if 50% of its lines have 80% similarity with the pattern. Two methods with identical bodies but different names meet this threshold. Both get overwritten — `bar()` becomes a duplicate of `foo()`. This is an agent that edits source code on your behalf.

---

## The clean codebases

Not everything was broken. The most-scanned codebase in the scan was datasette (1,129 functions). It was clean. SQL injection defense is layered and consistent: `escape_sqlite()` for identifiers, parameterized queries for values, schema validation before query construction. rich (705 functions): clean. The markup escape function works correctly. sqlite-utils (237 functions): clean. Hypothesis scanned at 2,369 functions across the Willison and trending tools set, found one low-severity cosmetic bug in `llm.utils.truncate_string` (length contract broken for `max_length < 3`, no security impact).

The hypothesis library itself — the tool we used to find bugs in everything else — was clean under its own tests. `st.integers(min > max)` correctly raises `InvalidArgument`. `assume(False)` always-failing tests correctly raise `Unsatisfiable`. Tools maintained by the Hypothesis team practice what they preach.

---

## Run it yourself

```bash
pip install nightjar

# Initialize a spec for your module
nightjar init mymodule

# Run the full verification pipeline
nightjar verify

# Skip Dafny (faster, PBT only)
nightjar verify --fast
```

The PBT stage runs Hypothesis with Nightjar's invariant engine. It generates counterexamples for your specifications and reports failures with exact inputs. The full pipeline adds schema validation (Stage 2), negation proofs (Stage 2.5), and formal Dafny verification (Stage 4).

The invariant specs live in `.card.md` files. Write `POST /login returns a valid JWT` as a contract, and the pipeline will try to find an input that violates it. If it does, you get the exact input before you ship.

---

## What this means

48 bugs. 20 codebases. The distribution is not random: the well-maintained, hand-tested projects (datasette, rich, hypothesis) were clean. The AI tooling ecosystem and the AI-generated application were not.

Tests check that code does what you expect on the inputs you thought of. Formal verification checks that code holds its invariants on every input — including the ones you didn't think of. `BasicTokenizer().train('a', 258)` is not an input Karpathy thought of. It takes four seconds to generate.

All scan results, reproduction scripts, and invariant specifications are available in the scan archive. The full code is at [github.com/your-org/nightjar].
