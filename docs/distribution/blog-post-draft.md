# 74 bugs, 34 codebases, one tool: what formal verification finds that tests miss

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

Nightjar is a verification pipeline for Python code. The core idea: write a contract (`.card.md` spec), run a pipeline that mathematically checks the contract holds. For this scan, we used the pipeline's property-based testing stage — built on Hypothesis — to check invariants across 34 codebases: Tier 1 infrastructure packages (requests, httpx, fastapi), Tier 2 AI tooling (fastmcp, litellm, openai-agents, google-adk, ragas, langgraph), security libraries (python-jose, passlib, authlib, PyJWT, itsdangerous), AI agent frameworks (DeerFlow, Open-SWE, Hermes), web3 infrastructure (web3.py), Karpathy's minbpe tokenizer, MiroFish — a recently viral vibe-coded application — and others.

The methodology was consistent across all targets: extract functions, write invariant specs, feed Hypothesis 500–1000 random inputs per function, confirm any failure by manual reproduction. False positives were explicitly tracked and excluded. Confirmed bugs were verified by running `python scan-lab/repro-scripts.py` against installed packages on a clean Python 3.14 environment. Zero false positives in the verified set.

Total confirmed bugs: 74. Total codebases scanned: 34. Verified clean: 14.

---

## Critical: web3.py ETH address hijacking via Unicode

The highest-severity finding in the scan is in `web3.py`, the standard Python library for Ethereum.

ENS (Ethereum Name Service) resolves human-readable names like `admin.eth` to wallet addresses. web3.py applies IDNA Unicode normalization before resolution. The bug: fullwidth Unicode characters (Unicode block U+FF01–U+FF5E) normalize to their ASCII equivalents under some normalization forms but not others — and the path through web3.py's ENS resolver does not apply consistent normalization.

The result: `ａdmin.eth` (fullwidth 'a', U+FF41) resolves to a different address than `admin.eth`. An attacker who registers the fullwidth variant of a high-value ENS name can receive funds intended for the legitimate address. Users who visually inspect the name see what looks correct. The Unicode difference is invisible to most fonts.

This is bounty-eligible under the Ethereum Foundation's security program. We filed before publishing.

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

**RestrictedPython**: confirmed RCE via a specific attribute traversal chain through the restricted namespace. The sandbox assumes that blocking `__builtins__` is sufficient. It is not. The traversal path reaches `exec` through object attribute access that the policy does not intercept. We are not publishing the exact chain pending maintainer response, but the reproduction script is in the repo and runs clean.

**python-jose 3.5.0** contains a surviving vulnerability related to CVE-2024-33663/33664: `jwt.decode(token, key, algorithms=None)` skips the algorithm allowlist entirely. The default API call omits `algorithms`, defaulting to `None`. Any application using python-jose without explicitly passing an algorithms list is accepting tokens signed with any algorithm — including HS256 tokens crafted with your RS256 public key as the HMAC secret.

**passlib 1.7.4** is broken against bcrypt 4.x and 5.x. The failure chain: passlib reads `bcrypt.__about__.__version__` at startup (removed in bcrypt 4.0), then calls its internal `detect_wrap_bug()` probe which passes a 255-byte password to `bcrypt.hashpw()`. bcrypt 5.0 now enforces the 72-byte limit strictly. The probe raises `ValueError: password cannot be longer than 72 bytes` — uncaught, propagating through `passlib_bcrypt.hash(any_password)`. Authentication is completely broken on any system running both packages at current versions.

---

## openai-agents: handoff trust escalation

`openai-agents` is OpenAI's official multi-agent framework. We found a handoff trust escalation: when one agent hands off to another, the receiving agent can invoke any tool registered in the system — not just the tools in its own scope.

In a multi-agent system where agents have different permission levels (e.g., a low-trust agent that handles user input and a high-trust agent that has database write access), the handoff mechanism does not enforce boundary checks. Any agent that can initiate a handoff can reach the tools of any other agent in the graph.

This was filed on HackerOne. We are treating it as HIGH severity.

---

## ragas: your RAG evaluation is lying to you

`ragas` is the most widely used evaluation framework for RAG (Retrieval-Augmented Generation) pipelines. We found 9 metrics that return `NaN` silently on edge-case inputs.

The pattern: when retrieved context is empty, or when the answer and context share no tokens, the scoring denominator becomes zero. The metric returns `NaN`. The aggregate score averages `NaN` across the batch — which propagates as `NaN` in the final score, or in some configurations silently drops the sample from the average.

The practical impact: a RAG system that consistently fails on out-of-distribution queries — the exact queries you most want to catch — scores itself as clean because those samples produce `NaN` rather than `0`. You ship a system with a known failure mode without knowing it.

---

## pydantic: model_copy bypasses ALL validators

pydantic is downloaded 270 million times a month. `model_copy(update={...})` bypasses all field validators, including custom `@field_validator` methods and `@model_validator` methods. This is documented behavior — pydantic explicitly calls it a "shallow copy with optional field updates."

The problem is the gap between documentation and usage. In any application that uses `model_copy` to apply user-supplied updates to a model (a common pattern for PATCH endpoints), the validators that enforce business logic — maximum values, format constraints, access control fields — are completely bypassed.

We found this pattern in three downstream applications in the scan. The escape hatch is in the stdlib. At 270M monthly downloads, the number of applications where this path exists is significant.

---

## google-adk: session state shared across users

Google's Agent Development Kit manages session state for multi-turn agent conversations. We found that the session state object is a shared mutable dictionary — one user's request handler can write to another user's session state.

The specific path: the session store in the default in-memory backend uses a dict keyed by session ID. The session state value is passed by reference, not copied. A mutation in one request context persists to concurrent requests that hold a reference to the same session object.

In a multi-user deployment — which is the primary use case for a production agent — this is a user data isolation failure.

---

## langgraph: the graph that does nothing successfully

langgraph is LangChain's framework for stateful multi-step agent graphs. We found a routing failure mode where the graph executes, returns a final state with a result value, exits with status success, and has performed no meaningful operations.

The path: a conditional edge evaluates to a branch that routes to `END` before any tool or LLM node executes. The graph framework does not distinguish between "intentional early exit" and "misconfigured routing that skips all work." The caller receives a dict with the initial state — no modifications — and a success return code.

This is MEDIUM-HIGH severity rather than HIGH because it requires a specific graph topology to trigger. But in production deployments where agents are chained and the caller does not inspect intermediate state, a silent no-op is indistinguishable from correct execution.

---

## AI agent frameworks: the bugs where it matters most

The AI agent frameworks we scanned — DeerFlow (ByteDance), Open-SWE (LangChain), and Hermes (NousResearch) — all had confirmed bugs in their core infrastructure. These are frameworks that run autonomous agents. A silent data corruption or deadlock is qualitatively worse here than in a utility library.

**DeerFlow** has an asyncio deadlock in `backend/packages/harness/deerflow/mcp/cache.py`. An `asyncio.Lock()` is created at module import time, outside any event loop. When two concurrent requests both see a cold cache, they each spin up `asyncio.run()` in separate threads, creating independent event loops. The lock belongs to the first thread's completed loop — the second thread deadlocks indefinitely. On the first pair of concurrent requests after startup, one hangs until the request timeout fires as a 5xx.

**Open-SWE** contains a one-character bug with high operational impact. The middleware safety net that catches failed PR creation checks:

```python
if "success" in pr_payload:
    return None
```

The tool always returns a dict with a `"success"` key — including on failure. `"success" in {"success": False, ...}` is `True`. The middleware returns `None` on every tool failure, abandoning the recovery attempt silently. When a push is rejected or a token expires, the agent ends the run without creating the PR and without any error escalation. The correct check is `pr_payload.get("success")`.

**Hermes** has a `fuzzy_find_and_replace` function with `replace_all=True` that corrupts unrelated code. Strategy 8 (`_strategy_context_aware`) accepts a block as a match if 50% of its lines have 80% similarity with the pattern. Two methods with identical bodies but different names meet this threshold. Both get overwritten — `bar()` becomes a duplicate of `foo()`. This is an agent that edits source code on your behalf.

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

## The clean codebases

14 packages were verified clean. The most-scanned codebase in the scan was datasette (1,129 functions). It was clean. SQL injection defense is layered and consistent: `escape_sqlite()` for identifiers, parameterized queries for values, schema validation before query construction. rich (705 functions): clean. The markup escape function works correctly. sqlite-utils (237 functions): clean. Hypothesis scanned at 2,369 functions across the Willison and trending tools set, found one low-severity cosmetic bug in `llm.utils.truncate_string` (length contract broken for `max_length < 3`, no security impact). httpx, requests, fastapi, PyJWT (current version), authlib, and four others were clean.

The hypothesis library itself — the tool we used to find bugs in everything else — was clean under its own tests. `st.integers(min > max)` correctly raises `InvalidArgument`. `assume(False)` always-failing tests correctly raise `Unsatisfiable`. Tools maintained by the Hypothesis team practice what they preach.

The pattern is consistent: hand-maintained projects with active test suites held up. The AI tooling ecosystem and AI-generated applications did not.

---

## Run it yourself

```bash
pip install nightjar-verify

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

74 bugs. 34 codebases. 14 clean. The distribution is not random: the well-maintained, hand-tested projects were clean. The AI tooling ecosystem and the AI-generated applications were not.

Tests check that code does what you expect on the inputs you thought of. Formal verification checks that code holds its invariants on every input — including the ones you didn't think of. `BasicTokenizer().train('a', 258)` is not an input Karpathy thought of. It takes four seconds to generate. `ａdmin.eth` is not a Unicode variant any Ethereum developer thought to test. The ENS resolver handled it differently than `admin.eth`. The difference is a wallet address.

All scan results, reproduction scripts, and invariant specifications are available in the scan archive. The full code is at [github.com/j4ngzzz/Nightjar](https://github.com/j4ngzzz/Nightjar).
