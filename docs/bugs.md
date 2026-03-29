# Nightjar Bug Hunt — 74 Confirmed Findings

> **Campaign period:** 2026-03-28 – 2026-03-29
> **Packages scanned:** 32+
> **Functions inspected:** ~5,000+
> **Total findings:** 74
> **False positives:** 0

---

## Methodology

Nightjar's bug-hunt campaign used property-based testing (Hypothesis) combined with direct source-code analysis to find real defects in widely-used Python packages — packages whose bugs would directly affect AI pipelines, authentication flows, and production back-ends. The pipeline operated in two phases. In the first phase, Nightjar's invariant scanner extracted function contracts from installed package source using AST analysis, docstrings, and type annotations, then drove each candidate through up to 500 Hypothesis examples to find counterexamples. In the second phase, human-reviewable reproduction scripts confirmed each finding by running the exact failing input against the installed package version — no fuzzing approximations, no synthetic environments.

Every finding in this list was reproduced at least three times against a pinned package version before being included. Findings marked CONFIRMED were verified using standalone scripts in `scan-lab/repro-scripts.py` and `scan-lab/repro-scripts-v2.py`. Wave 4 findings were confirmed by independent agents each required to produce a 3x reproduction with exact output. The campaign enforced a zero-false-positive policy: anything that could not be reproduced on the actual installed package, or that matched documented by-design behavior without a plausible attack scenario, was excluded. Fourteen packages (listed at the bottom) were scanned and reported as clean — an honest signal that the scanner does not generate findings on demand.

---

## Summary Table — All 74 Findings

| # | Package | Version | Bug Type | Severity | Status | Details |
|---|---------|---------|----------|----------|--------|---------|
| 1 | httpx | 0.28.1 | `unquote("")` raises `IndexError` — reachable via Digest auth header with empty value | MEDIUM | CONFIRMED | [scan-lab/tier1-results.md](../scan-lab/tier1-results.md) |
| 2 | fastapi | 0.135.1 | `decimal_encoder(Decimal("sNaN"))` raises `ValueError` — signaling NaN not handled | MEDIUM | CONFIRMED | [scan-lab/tier1-results.md](../scan-lab/tier1-results.md) |
| 3 | fastmcp | 2.14.5 | JWT `verify_token`: `if exp and ...` skips expiry when `exp=None` (falsy check) | HIGH | CONFIRMED | [scan-lab/tier2-results.md](../scan-lab/tier2-results.md) |
| 4 | fastmcp | 2.14.5 | JWT `exp=0` (Unix epoch) bypasses expiry — integer `0` is falsy in Python | HIGH | CONFIRMED | [scan-lab/tier2-results.md](../scan-lab/tier2-results.md) |
| 5 | fastmcp | 2.14.5 | `fnmatch` OAuth redirect URI allows query-param injection and fake-port attacks | HIGH | CONFIRMED | [scan-lab/tier2-results.md](../scan-lab/tier2-results.md) |
| 6 | fastmcp | 2.14.5 | `OAuthProxyProvider(allowed_client_redirect_uris=None)` allows ALL redirect URIs; docs say "localhost-only" | MEDIUM | CONFIRMED | [scan-lab/tier2-results.md](../scan-lab/tier2-results.md) |
| 7 | fastmcp | 2.14.5 | `compress_schema` mutates input dict in-place despite docstring claiming "immutable design" | MEDIUM | CONFIRMED | [scan-lab/tier2-results.md](../scan-lab/tier2-results.md) |
| 8 | litellm | 1.82.6 | `create_budget(created_at=time.time())` — mutable default frozen at import; 24h+ servers reset newly created daily budgets immediately | HIGH | CONFIRMED | [scan-lab/tier2-results.md](../scan-lab/tier2-results.md) |
| 9 | litellm | 1.82.6 | `getattr(dict_response, "ended", time.time())` always returns `time.time()` — `ended` key in dict ignored | MEDIUM | CONFIRMED | [scan-lab/tier2-results.md](../scan-lab/tier2-results.md) |
| 10 | litellm | 1.82.6 | `X-Forwarded-For` header used as raw string; multi-hop format `"1.2.3.4, 10.0.0.1"` fails exact-match allowlist | MEDIUM | CONFIRMED | [scan-lab/tier2-results.md](../scan-lab/tier2-results.md) |
| 11 | python-jose | 3.5.0 | `jwt.decode(token, key, algorithms=None)` skips algorithm allowlist — algorithm confusion attack possible | HIGH | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 12 | python-jose | 3.5.0 | Empty string `""` accepted as HMAC secret key — no warning, no error | MEDIUM | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 13 | python-jose | 3.5.0 | `jwt.decode(None, ...)` raises `AttributeError` not `JWTError` — callers catching `JWTError` miss this | LOW | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 14 | passlib | 1.7.4 | Broken with bcrypt 4.x/5.x — `bcrypt.__about__` removed; bcrypt 5.0 `detect_wrap_bug` probe raises uncaught `ValueError` | HIGH | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 15 | passlib | 1.7.4 | `pbkdf2_sha256.hash("")` succeeds — no minimum password length enforcement | MEDIUM | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 16 | passlib | 1.7.4 | Inconsistent null-byte handling: `pbkdf2_sha256` accepts `\x00`, `sha256_crypt` raises `PasswordValueError` | LOW | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 17 | itsdangerous | 2.2.0 | `loads(token, max_age=0)` does NOT expire tokens — comparison is `age > max_age`, not `age >= max_age` | LOW | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 18 | itsdangerous | 2.2.0 | `URLSafeSerializer("")` accepted — empty string creates HMAC-less tokens | MEDIUM | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 19 | itsdangerous | 2.2.0 | Tokens created without `salt` are cross-context usable — password-reset token valid as session token | LOW | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 20 | PyJWT | 2.11.0 | 3-byte key accepted with `InsecureKeyLengthWarning` only; `enforce_minimum_key_length` defaults to `False` | MEDIUM | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 21 | authlib | 1.6.9 | `OctKey.import_key(b"short")` (5 bytes) accepted without warning for HS256 — no minimum key length enforcement | MEDIUM | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 22 | authlib | 1.6.9 | `JWTClaims.validate()` skips `iss` and `aud` validation by default — wrong issuer/audience silently accepted | MEDIUM | CONFIRMED | [scan-lab/tier45-results.md](../scan-lab/tier45-results.md) |
| 23 | minbpe | HEAD | `train()` crashes with `ValueError: max() argument is empty` when `vocab_size` exceeds mergeable pairs | HIGH | CONFIRMED | [scan-lab/karpathy-results.md](../scan-lab/karpathy-results.md) |
| 24 | minbpe | HEAD | `load()` crashes with `ValueError: too many values to unpack` when special token name contains a space | MEDIUM | CONFIRMED | [scan-lab/karpathy-results.md](../scan-lab/karpathy-results.md) |
| 25 | MiroFish | HEAD | Infinite loop in `split_text_into_chunks` when `overlap >= chunk_size` — hangs server forever | HIGH | CONFIRMED | [scan-lab/mirofish-results.md](../scan-lab/mirofish-results.md) |
| 26 | MiroFish | HEAD | Full Python tracebacks returned in HTTP error responses across all API endpoints | MEDIUM | CONFIRMED | [scan-lab/mirofish-results.md](../scan-lab/mirofish-results.md) |
| 27 | MiroFish | HEAD | Hardcoded `SECRET_KEY='mirofish-secret-key'` and `DEBUG=True` defaults — session forgery possible | HIGH | CONFIRMED | [scan-lab/mirofish-results.md](../scan-lab/mirofish-results.md) |
| 28 | MiroFish | HEAD | Path traversal via unsanitized `platform` query parameter in `get_profiles` | HIGH | CONFIRMED | [scan-lab/mirofish-results.md](../scan-lab/mirofish-results.md) |
| 29 | MiroFish | HEAD | `_generate_username` passes CJK characters through `isalnum()` — invalid usernames downstream | MEDIUM | CONFIRMED | [scan-lab/mirofish-results.md](../scan-lab/mirofish-results.md) |
| 30 | MiroFish | HEAD | Path traversal via unsanitized `simulation_id` — `os.makedirs` called on attacker-controlled path | MEDIUM | CONFIRMED | [scan-lab/mirofish-results.md](../scan-lab/mirofish-results.md) |
| 31 | hermes-agent | HEAD | Duplicate `close()` definition in `SessionDB` — WAL checkpoint silently dead; WAL file grows unbounded | MEDIUM | CONFIRMED | [scan-lab/hermes-results.md](../scan-lab/hermes-results.md) |
| 32 | hermes-agent | HEAD | `fuzzy_find_and_replace` with `replace_all=True` overwrites semantically unrelated code via `_strategy_context_aware` false positives | HIGH | CONFIRMED | [scan-lab/hermes-results.md](../scan-lab/hermes-results.md) |
| 33 | hermes-agent | HEAD | `_suggest_similar_files` uses character-set intersection — returns irrelevant file suggestions to LLM | LOW | CONFIRMED | [scan-lab/hermes-results.md](../scan-lab/hermes-results.md) |
| 34 | hermes-agent | HEAD | `choose_cheap_model_route` keyword set misses inflected forms (`testing`, `implementing`, `refactored`) | LOW | CONFIRMED | [scan-lab/hermes-results.md](../scan-lab/hermes-results.md) |
| 35 | DeerFlow | HEAD | `asyncio.Lock()` created at module import causes deadlock across threads during concurrent MCP initialization | MEDIUM | CONFIRMED | [scan-lab/deerflow-results.md](../scan-lab/deerflow-results.md) |
| 36 | DeerFlow | HEAD | `_UPLOAD_SENTENCE_RE` `\b` word-boundary before `/mnt/` prevents path-sentence matching — upload paths never stripped from memory | MEDIUM | CONFIRMED | [scan-lab/deerflow-results.md](../scan-lab/deerflow-results.md) |
| 37 | DeerFlow | HEAD | `_UPLOAD_SENTENCE_RE` stops at file extensions — leaves garbled fragments like `"pdf. They asked about Python."` in long-term memory | LOW | CONFIRMED | [scan-lab/deerflow-results.md](../scan-lab/deerflow-results.md) |
| 38 | DeerFlow | HEAD | `str_replace_tool` returns `"OK"` for empty files without checking `old_str` — agent believes replacement succeeded | LOW | CONFIRMED | [scan-lab/deerflow-results.md](../scan-lab/deerflow-results.md) |
| 39 | DeerFlow | HEAD | `UploadsMiddleware` discards non-text content blocks (images) in multi-modal messages | LOW | CONFIRMED | [scan-lab/deerflow-results.md](../scan-lab/deerflow-results.md) |
| 40 | open-swe | HEAD | Middleware safety net skips PR recovery when `commit_and_open_pr` fails — `"success" in dict` checks key presence, not value | HIGH | CONFIRMED | [scan-lab/openswe-results.md](../scan-lab/openswe-results.md) |
| 41 | open-swe | HEAD | `extract_repo_from_text` returns repo name with embedded slash when input has multiple slashes | MEDIUM | CONFIRMED | [scan-lab/openswe-results.md](../scan-lab/openswe-results.md) |
| 42 | open-swe | HEAD | `git checkout -B` force-resets existing branch on agent retry — discards prior work, causes push rejection | MEDIUM | CONFIRMED | [scan-lab/openswe-results.md](../scan-lab/openswe-results.md) |
| 43 | open-swe | HEAD | GitHub URL with `.git` suffix produces repo name `"open-swe.git"` — all API calls 404 | LOW | CONFIRMED | [scan-lab/openswe-results.md](../scan-lab/openswe-results.md) |
| 44 | pydantic | 2.12.5 | `model_validator(mode='before')` raises raw `TypeError` on string inputs — causes 500 in FastAPI instead of 422 | HIGH | CONFIRMED | [scan-lab/agent-framework-results.md](../scan-lab/agent-framework-results.md) |
| 45 | pydantic | 2.12.5 | `model_copy()` is shallow by default — mutating copy mutates original model | MEDIUM | CONFIRMED | [scan-lab/agent-framework-results.md](../scan-lab/agent-framework-results.md) |
| 46 | pydantic | 2.12.5 | `model_copy(update=...)` bypasses ALL validators including type and field validators | HIGH | CONFIRMED | [scan-lab/agent-framework-results.md](../scan-lab/agent-framework-results.md) |
| 47 | click | 8.3.1 | `required=True` option accepts empty string and whitespace-only values without error | MEDIUM | CONFIRMED | [scan-lab/agent-framework-results.md](../scan-lab/agent-framework-results.md) |
| 48 | llm | 0.29 | `truncate_string(text, max_length=N)` produces output **longer** than `max_length` when `N < 3` | LOW | CONFIRMED | [scan-lab/willison-trending-results.md](../scan-lab/willison-trending-results.md) |
| 49 | watchfiles | 1.1.1 | `BaseFilter` splits paths on `os.sep` — forward-slash paths not filtered on Windows | LOW | CONFIRMED | [scan-lab/willison-trending-results.md](../scan-lab/willison-trending-results.md) |
| 50 | langgraph | 1.1.3 | Silent routing failure when `add_conditional_edges()` used without `path_map` — graph returns success with target node never executed | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-a1-results.md](../scan-lab/wave4-hunt-a1-results.md) |
| 51 | browser-use | 0.12.5 | `_filter_sensitive_data_from_string` iterates secrets in insertion order — shorter prefix replaces first, leaving unique suffix as plaintext | LOW | CONFIRMED | [scan-lab/wave4-hunt-a2-results.md](../scan-lab/wave4-hunt-a2-results.md) |
| 52 | openai-agents | 0.13.2 | `_parse_function_tool_json_input` returns non-dict for valid JSON scalars (`1`, `true`, `[1,2]`) — violates `dict[str, Any]` return type | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-a3a-results.md](../scan-lab/wave4-hunt-a3a-results.md) |
| 53 | openai-agents | 0.13.2 | `json.loads("null")` → `None` → falsy → tool called with all default args silently ignoring LLM intent | LOW | CONFIRMED | [scan-lab/wave4-hunt-a3a-results.md](../scan-lab/wave4-hunt-a3a-results.md) |
| 54 | openai-agents | 0.13.2 | Handoff `<CONVERSATION HISTORY>` marker injection — user-controlled content parsed as real history, enabling `developer`-role spoofing | HIGH | CONFIRMED | [scan-lab/wave4-hunt-a3a-results.md](../scan-lab/wave4-hunt-a3a-results.md) |
| 55 | google-adk | 1.28.0 | `create_session(session_id=' id')` silently overwrites existing session `'id'` — duplicate check uses raw ID, storage uses stripped ID | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-a3b-results.md](../scan-lab/wave4-hunt-a3b-results.md) |
| 56 | google-adk | 1.28.0 | `BashToolPolicy` prefix validation bypassed — `ls; rm -rf /` passes a policy of `allowed_command_prefixes=('ls',)` | LOW | CONFIRMED | [scan-lab/wave4-hunt-a3b-results.md](../scan-lab/wave4-hunt-a3b-results.md) |
| 57 | docling-core | HEAD | `resolve_source_to_stream()` reads arbitrary filesystem paths — no base-directory guard, no path normalization | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-a6-results.md](../scan-lab/wave4-hunt-a6-results.md) |
| 58 | crewai | HEAD | `_execute_single_listener()` state divergence — `asyncio.gather(return_exceptions=True)` swallows listener exceptions, producing non-deterministic flow state | LOW | CONFIRMED | [scan-lab/wave4-hunt-a6-results.md](../scan-lab/wave4-hunt-a6-results.md) |
| 59 | web3.py (ens) | 7.14.1 | ENS `normalize_name()` folds all 62 fullwidth Unicode codepoints (U+FF10–U+FF5A) to ASCII — `vit\uff41lik.eth` normalizes to `vitalik.eth`, enabling ETH address hijacking | CRITICAL | CONFIRMED | [scan-lab/wave4-hunt-b2-results.md](../scan-lab/wave4-hunt-b2-results.md) |
| 60 | eth-abi (web3.py) | 5.2.0 | `ABICodec.decode()` silently ignores trailing garbage bytes — payload integrity not enforced on decode | LOW | CONFIRMED | [scan-lab/wave4-hunt-b2-results.md](../scan-lab/wave4-hunt-b2-results.md) |
| 61 | cryptography | 46.0.5 | `HKDF(length=0).derive(ikm)` returns `b""` without raising — violates RFC 5869 (L must be > 0) | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-b2-results.md](../scan-lab/wave4-hunt-b2-results.md) |
| 62 | cryptography | 46.0.5 | `Fernet.decrypt(token, ttl=0)` accepts same-second tokens — off-by-one in TTL check (`<` not `<=`) | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-b2-results.md](../scan-lab/wave4-hunt-b2-results.md) |
| 63 | mlflow | 3.10.1 | `log_metric()` silently stores `NaN`, `inf`, `-inf` — `_validate_metric` performs no `math.isfinite()` check | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-b3-results.md](../scan-lab/wave4-hunt-b3-results.md) |
| 64 | celery | 5.6.2 | `set_chord_size(group_id, 0)` stores zero without raising — chord body fires spuriously when no tasks have completed | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-b3-results.md](../scan-lab/wave4-hunt-b3-results.md) |
| 65 | mcp SDK | 1.26.0 | Tool `description` field stored verbatim with no sanitization — LLM prompt injection payloads preserved in wire JSON | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-b5-results.md](../scan-lab/wave4-hunt-b5-results.md) |
| 66 | mcp SDK | 1.26.0 | Per-parameter `description` fields injected via `Field(description=...)` also preserved verbatim in `inputSchema.properties` | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-b5-results.md](../scan-lab/wave4-hunt-b5-results.md) |
| 67 | mcp SDK | 1.26.0 | `validate_and_warn_tool_name` return value ignored — invalid names (`<script>`, `\x00`, 200+ chars) register without error | LOW | CONFIRMED | [scan-lab/wave4-hunt-b5-results.md](../scan-lab/wave4-hunt-b5-results.md) |
| 68 | mcp SDK | 1.26.0 | `pre_parse_json` coerces string `"42"` to int `42` — schema type annotations advisory rather than enforced | INFO | CONFIRMED | [scan-lab/wave4-hunt-b5-results.md](../scan-lab/wave4-hunt-b5-results.md) |
| 69 | RestrictedPython | 8.1 | Sandbox integrity fully caller-dependent — providing `__import__` + plain `getattr` achieves confirmed filesystem RCE | HIGH | CONFIRMED | [scan-lab/wave4-hunt-b5-results.md](../scan-lab/wave4-hunt-b5-results.md) |
| 70 | RestrictedPython | 8.1 | `compile_restricted()` returns code object for `import os; os.system(...)` without raising — runtime-only blocking silently bypassed by misconfigured caller environments | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-b5-results.md](../scan-lab/wave4-hunt-b5-results.md) |
| 71 | ragas | 0.4.3 | 9+ metric functions return `np.nan` instead of raising on LLM failure, empty input, or zero-denominator — silently poisons aggregation | HIGH | CONFIRMED | [scan-lab/wave4-hunt-b6-results.md](../scan-lab/wave4-hunt-b6-results.md) |
| 72 | ragas | 0.4.3 | `DataCompyScore._single_turn_ascore` raises `ZeroDivisionError` when both precision and recall are zero | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-b6-results.md](../scan-lab/wave4-hunt-b6-results.md) |
| 73 | ragas | 0.4.3 | `AnswerAccuracy.average_scores(nan, nan)` returns `nan` — retry exhaustion silently discards any partial valid score | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-b6-results.md](../scan-lab/wave4-hunt-b6-results.md) |
| 74 | opik | 1.10.54 | `factuality/parser.py` raises raw `ZeroDivisionError` when LLM returns empty claims list — should raise `MetricComputationError` | MEDIUM | CONFIRMED | [scan-lab/wave4-hunt-b6-results.md](../scan-lab/wave4-hunt-b6-results.md) |

---

## Severity Distribution

| Severity | Count |
|----------|-------|
| CRITICAL | 1 |
| HIGH | 17 |
| MEDIUM | 37 |
| LOW | 18 |
| INFO | 1 |
| **Total** | **74** |

---

## Coverage by Wave

| Wave | Packages | Findings |
|------|----------|----------|
| Original Campaign — Tier 1 | httpx, fastapi | 2 |
| Original Campaign — Tier 2 | fastmcp, litellm | 8 |
| Original Campaign — Tier 4/5 | python-jose, passlib, itsdangerous, PyJWT, authlib | 12 |
| Karpathy repos | minbpe | 2 |
| MiroFish | MiroFish | 6 |
| hermes-agent | hermes-agent | 4 |
| DeerFlow | DeerFlow | 5 |
| open-swe | open-swe | 4 |
| Agent frameworks | pydantic, click, llm, watchfiles | 6 |
| Wave 4 A1 | langgraph | 1 |
| Wave 4 A2 | browser-use | 1 |
| Wave 4 A3a | openai-agents | 3 |
| Wave 4 A3b | google-adk | 2 |
| Wave 4 A6 | docling-core, crewai | 2 |
| Wave 4 B2 | web3.py/ens, eth-abi, cryptography | 4 |
| Wave 4 B3 | mlflow, celery | 2 |
| Wave 4 B5 | mcp SDK, RestrictedPython | 6 |
| Wave 4 B6 | ragas, opik | 4 |
| **Total** | **32+ packages** | **74** |

---

## Verified Clean (14 packages)

The following packages were scanned and no bugs were found in the tested contracts. They are reported here as an honest signal — Nightjar does not generate findings on demand.

| Package | Version | Functions Scanned | Result |
|---------|---------|-------------------|--------|
| datasette | 0.65.2 | ~1,129 | Clean — layered SQL injection defense, parameterized values throughout |
| rich | 14.3.3 | ~705 | Clean — markup escape function correct, no injection paths |
| hypothesis | 6.151.9 | — | Clean — `InvalidArgument` correctly raised for impossible strategy bounds |
| sqlite-utils | 3.39 | ~237 | Clean — consistent bracket quoting of identifiers |
| aiohttp | 3.13.3 | — | Clean — bare-CR rejection, duplicate Content-Length rejection, cookie domain isolation all correct (18/18 tests) |
| urllib3 | 2.6.3 | — | Clean — `allowed_methods` filtering and URL round-trip idempotency correct (18/18 tests) |
| marshmallow | 4.2.3 | — | Clean — Decimal, DateTime, UUID, and Nested round-trips all lossless (7/7 tests) |
| msgspec | 0.20.0 | — | Clean — integer boundary constraints enforced without silent truncation (12/12 tests) |
| paramiko | 4.0.0 | — | Clean — `get_string()` zero-padding is documented; SFTP path handling correct per protocol |
| Pillow | 12.1.1 | — | Clean — `crop()` and `resize()` dimension invariants hold across all resamplers and modes |
| protobuf | (HEAD) | — | Clean — CVE-2026-0994 (`Any` recursion depth bypass) patched in current HEAD |
| langchain-core | 1.2.23 | — | Clean — `dumps()`/`loads()` round-trip faithful; CVE-2025-68664 serialization injection guard confirmed effective |
| langsmith | 0.7.22 | — | Clean — framework delegates score range enforcement to caller evaluators by design |
| celery (jsonify) | 5.6.2 | — | Clean — `jsonify()` is correctly idempotent across all tested input types |

---

## Reproduction

All 48 findings from the original campaign (Tier 1, 2, 4/5, Karpathy, MiroFish, hermes-agent, DeerFlow, open-swe, pydantic/click/llm/watchfiles) were independently verified by standalone reproduction scripts:

- **Original 21 findings:** `scan-lab/repro-scripts.py`
- **Newer 27 findings:** `scan-lab/repro-scripts-v2.py` (27/27 CONFIRMED)
- **Wave 4 findings:** Individual reproduction scripts per result file; each finding reproduced 3× against pinned package version

Wave 4 test infrastructure:
- `scan-lab/wave4_a1_hypothesis_tests.py` — langgraph silent routing
- `scan-lab/wave4-hunt-a2-tests.py` — browser-use sensitive data filter
- `scan-lab/wave4-hunt-a3a-tests.py` — openai-agents
- `scan-lab/wave4-hunt-a3b-hypothesis-tests.py` — google-adk
- `scan-lab/wave4_hunt_a4_tests.py` — aiohttp/urllib3 (clean)
- `scan-lab/wave4-pbt-runner.py` — Wave 4 batch runner
- `scan-lab/repro_langgraph_silent_routing.py` — standalone langgraph repro

All reproduction scripts are offline (no LLM, no network required) and executable with `pip install hypothesis` plus the target package.
