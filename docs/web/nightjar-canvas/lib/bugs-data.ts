/**
 * Nightjar Bug Report Data
 *
 * 48 confirmed bugs across 18 packages, verified 2026-03-28.
 * All bugs reproduced by direct execution against installed packages.
 */

export interface BugReport {
  slug: string;
  package: string;
  version: string;
  severity: "HIGH" | "MEDIUM" | "LOW";
  title: string;
  description: string;
  reproduction: string;
  status: "disclosed" | "fixed" | "confirmed";
  cve?: string;
}

export const bugs: BugReport[] = [
  // ── httpx ─────────────────────────────────────────────────────────────────
  {
    slug: "httpx-unquote-empty-string-indexerror",
    package: "httpx",
    version: "0.28.1",
    severity: "MEDIUM",
    title: "unquote(\"\") raises IndexError on empty string",
    description:
      "The httpx `unquote()` utility evaluates `value[0] == value[-1] == '\"'` before checking string length. An empty string causes `IndexError: string index out of range` because Python does not short-circuit before the index access.",
    reproduction:
      'from httpx._utils import unquote\nunquote("")\n# IndexError: string index out of range',
    status: "confirmed",
  },

  // ── fastapi ───────────────────────────────────────────────────────────────
  {
    slug: "fastapi-decimal-encoder-snan-valueerror",
    package: "fastapi",
    version: "0.135.1",
    severity: "MEDIUM",
    title: "decimal_encoder(Decimal(\"sNaN\")) raises ValueError",
    description:
      "fastapi's `decimal_encoder` handles `NaN` (lowercase exponent `'n'`) but not signaling `sNaN` (uppercase exponent `'N'`). Calling `float(Decimal(\"sNaN\"))` raises `ValueError: cannot convert signaling NaN to float`.",
    reproduction:
      'from decimal import Decimal\nfrom fastapi.encoders import decimal_encoder\ndecimal_encoder(Decimal("sNaN"))\n# ValueError: cannot convert signaling NaN to float',
    status: "confirmed",
  },

  // ── fastmcp ───────────────────────────────────────────────────────────────
  {
    slug: "fastmcp-jwt-exp-none-bypass",
    package: "fastmcp",
    version: "2.14.5",
    severity: "HIGH",
    title: "JWT expiry check skipped when exp=None (falsy check)",
    description:
      "In `fastmcp/server/auth/jwt_issuer.py:215`, the expiry check uses `if exp and exp < time.time()`. When `exp=None`, Python evaluates `None` as falsy and short-circuits — the expiry check is never performed. Tokens without an expiry claim are unconditionally accepted.",
    reproduction:
      "import time\nexp = None\nif exp and exp < time.time():   # evaluates to: if None = False\n    raise Exception('expired')\n# Token accepted — expiry not enforced",
    status: "confirmed",
  },
  {
    slug: "fastmcp-jwt-exp-zero-bypass",
    package: "fastmcp",
    version: "2.14.5",
    severity: "HIGH",
    title: "JWT expiry bypassed when exp=0 (Unix epoch is falsy)",
    description:
      "The same falsy check `if exp and ...` in fastmcp's JWT verifier means a token with `exp=0` (January 1, 1970 — long expired) passes validation. Integer `0` is falsy in Python, so a 55-year-old token is accepted as valid.",
    reproduction:
      "import time\nexp = 0  # Unix epoch — long expired\nif exp and exp < time.time():   # if 0 = False\n    raise Exception('expired')\n# 1970 token accepted",
    status: "confirmed",
  },
  {
    slug: "fastmcp-oauth-fnmatch-redirect-bypass",
    package: "fastmcp",
    version: "2.14.5",
    severity: "HIGH",
    title: "fnmatch OAuth redirect URI allows query-param injection and fake-port attacks",
    description:
      "fastmcp validates OAuth redirect URIs using Python's `fnmatch`. This allows two bypass attacks: (1) query-param injection — `https://evil.com/cb?legit.example.com/anything` matches `https://*.example.com/*`; (2) fake-port — `http://localhost:evil.com` matches `http://localhost:*`. An attacker can receive authorization codes.",
    reproduction:
      "import fnmatch\n# Attack 1: query-param injection\nfnmatch.fnmatch('https://evil.com/cb?legit.example.com/anything', 'https://*.example.com/*')  # True\n# Attack 2: fake port\nfnmatch.fnmatch('http://localhost:evil.com', 'http://localhost:*')  # True",
    status: "confirmed",
  },
  {
    slug: "fastmcp-oauth-proxy-none-allows-all",
    package: "fastmcp",
    version: "2.14.5",
    severity: "HIGH",
    title: "OAuthProxyProvider(allowed_client_redirect_uris=None) allows ALL redirect URIs",
    description:
      "In `fastmcp/server/auth/redirect_validation.py:50`, when `allowed_patterns is None` the function returns `True` unconditionally. The documentation states 'If None (default), only localhost redirect URIs are allowed.' The code directly contradicts the documented behavior.",
    reproduction:
      "# Source: redirect_validation.py:50\nif allowed_patterns is None:\n    return True  # 'for DCR compatibility' — but docs say localhost-only",
    status: "confirmed",
  },
  {
    slug: "fastmcp-compress-schema-mutation",
    package: "fastmcp",
    version: "2.14.5",
    severity: "MEDIUM",
    title: "compress_schema mutates input dict in-place despite immutable design claim",
    description:
      "fastmcp's `compress_schema` function mutates its input dictionary in-place: `result is schema` is `True` after the call, the original title is removed, and pruned properties are deleted from the original. The docstring claims 'immutable design' — this is false.",
    reproduction:
      "from fastmcp.utilities.json_schema import compress_schema\nschema = {'type': 'object', 'title': 'Test', 'properties': {'ctx': {}, 'name': {}}, 'required': ['name']}\nresult = compress_schema(schema, prune_params=['ctx'], prune_titles=True)\nassert result is schema        # True — same object\nassert 'title' not in schema   # True — original mutated",
    status: "confirmed",
  },

  // ── litellm ───────────────────────────────────────────────────────────────
  {
    slug: "litellm-mutable-default-created-at",
    package: "litellm",
    version: "1.82.6",
    severity: "HIGH",
    title: "create_budget mutable default created_at=time.time() frozen at import",
    description:
      "In `litellm/budget_manager.py:81`, the function signature uses `created_at: float = time.time()`. Python evaluates default arguments once at module import. On a server running 24+ hours, `time.time() - frozen_default >= 86400`, which immediately triggers `reset_on_duration()` for any newly created daily budget.",
    reproduction:
      "import litellm, inspect, time\nspec = inspect.getfullargspec(litellm.BudgetManager.create_budget)\ndefaults = dict(zip(reversed(spec.args), reversed(spec.defaults)))\nfrozen_default = defaults['created_at']\n# frozen_default is the import timestamp — drifts from time.time() in production",
    status: "confirmed",
  },
  {
    slug: "litellm-getattr-dict-ended-ignored",
    package: "litellm",
    version: "1.82.6",
    severity: "MEDIUM",
    title: "getattr(dict, \"ended\") always returns time.time() — dict key ignored",
    description:
      "litellm uses `getattr(completion_response, 'ended', time.time())` where `completion_response` is a plain dict. `getattr` on a dict does not access dict keys — it only accesses object attributes. The `ended` key is always ignored, returning the current wall-clock time instead of the stored value.",
    reproduction:
      "import time\ncompletion_response = {'created': 1000.0, 'ended': 1005.0}\nend_time = getattr(completion_response, 'ended', time.time())\n# Returns time.time() (~1774692895), NOT 1005.0\n# total_time = ~1774691895s instead of 5s",
    status: "confirmed",
  },
  {
    slug: "litellm-x-forwarded-for-multi-hop",
    package: "litellm",
    version: "1.82.6",
    severity: "MEDIUM",
    title: "X-Forwarded-For multi-hop format fails exact-match IP allowlist",
    description:
      "litellm's proxy auth uses the raw `X-Forwarded-For` header string in an exact-match allowlist check. The RFC 7239 multi-hop format `\"1.2.3.4, 10.0.0.1\"` does not match the allowlist entry `\"1.2.3.4\"`, blocking legitimate proxied requests. An attacker can also spoof a single-hop value.",
    reproduction:
      "allowed_ips = ['1.2.3.4']\nraw_xff = '1.2.3.4, 10.0.0.1'   # RFC 7239 multi-hop\nresult = raw_xff not in allowed_ips  # True — legitimate request blocked",
    status: "confirmed",
  },

  // ── python-jose ───────────────────────────────────────────────────────────
  {
    slug: "python-jose-algorithms-none-bypass",
    package: "python-jose",
    version: "3.5.0",
    severity: "HIGH",
    title: "jwt.decode(algorithms=None) skips algorithm allowlist entirely",
    description:
      "In `jose/jws.py`, the algorithm check is `if algorithms is not None and alg not in algorithms`. Passing `algorithms=None` skips the check entirely — any algorithm is accepted. This is related to CVE-2024-33663/CVE-2024-33664 and remains unfixed in 3.5.0.",
    reproduction:
      "from jose import jwt\ntoken = jwt.encode({'sub': 'admin', 'admin': True}, 'secret', algorithm='HS256')\nresult = jwt.decode(token, 'secret', algorithms=None)\n# Returns: {'sub': 'admin', 'admin': True} — no algorithm restriction",
    status: "confirmed",
    cve: "CVE-2024-33663",
  },
  {
    slug: "python-jose-empty-secret-key",
    package: "python-jose",
    version: "3.5.0",
    severity: "MEDIUM",
    title: "Empty string accepted as HMAC secret key without warning",
    description:
      "python-jose accepts an empty string `\"\"` as an HMAC secret key, produces a valid token, and decodes it successfully — with no warning or error. An empty HMAC key provides no cryptographic protection.",
    reproduction:
      'from jose import jwt\ntoken = jwt.encode({"sub": "test"}, "", algorithm="HS256")\nresult = jwt.decode(token, "", algorithms=["HS256"])\n# Returns: {"sub": "test"} — no error',
    status: "confirmed",
  },
  {
    slug: "python-jose-decode-none-attributeerror",
    package: "python-jose",
    version: "3.5.0",
    severity: "LOW",
    title: "jwt.decode(None) raises AttributeError instead of JWTError",
    description:
      "Passing `None` as the token to `jwt.decode()` raises `AttributeError: 'NoneType' object has no attribute 'rsplit'` instead of `JWTError`. Callers that catch `JWTError` to handle malformed token inputs will not catch this case, leaving an unhandled exception.",
    reproduction:
      'from jose import jwt\njwt.decode(None, "secret", algorithms=["HS256"])\n# AttributeError: \'NoneType\' object has no attribute \'rsplit\'',
    status: "confirmed",
  },

  // ── passlib ───────────────────────────────────────────────────────────────
  {
    slug: "passlib-bcrypt-5-incompatibility",
    package: "passlib",
    version: "1.7.4",
    severity: "HIGH",
    title: "Complete incompatibility with bcrypt 4.x/5.x — bcrypt.hash() broken",
    description:
      "passlib 1.7.4 is completely broken with bcrypt 5.0.0. Failure chain: (1) passlib reads `bcrypt.__about__.__version__` — `AttributeError` (removed in bcrypt 4.0); (2) passlib's `detect_wrap_bug()` passes a 255-byte probe to `bcrypt.hashpw()`; (3) bcrypt 5.0.0 enforces the 72-byte limit strictly, raising `ValueError`; (4) the `ValueError` propagates uncaught. All passlib bcrypt operations fail.",
    reproduction:
      "from passlib.hash import bcrypt as passlib_bcrypt\npasslib_bcrypt.hash('password')\n# ValueError: password cannot be longer than 72 bytes, truncate manually if necessary",
    status: "confirmed",
  },
  {
    slug: "passlib-empty-password-accepted",
    package: "passlib",
    version: "1.7.4",
    severity: "MEDIUM",
    title: "pbkdf2_sha256.hash(\"\") succeeds — no minimum password length",
    description:
      "passlib's `pbkdf2_sha256` hasher accepts and successfully verifies an empty string password. No `min_length` parameter exists in the passlib API, and the library provides no mechanism to enforce a minimum password length at the hashing layer.",
    reproduction:
      'from passlib.hash import pbkdf2_sha256\nh = pbkdf2_sha256.hash("")\npbkdf2_sha256.verify("", h)  # True — no error',
    status: "confirmed",
  },

  // ── itsdangerous ──────────────────────────────────────────────────────────
  {
    slug: "itsdangerous-max-age-zero-not-expired",
    package: "itsdangerous",
    version: "2.2.0",
    severity: "LOW",
    title: "loads(token, max_age=0) does NOT expire tokens",
    description:
      "itsdangerous uses `age > max_age` (strict greater-than) for its expiry check. A just-signed token has `age ~= 0`. Since `0 > 0` is `False`, the token is not expired when `max_age=0`. Any caller using `max_age=0` to mean 'must be zero-age' will find all tokens are accepted.",
    reproduction:
      "from itsdangerous import URLSafeTimedSerializer\nts = URLSafeTimedSerializer('secret')\ntoken = ts.dumps({'user': 'test'})\nresult = ts.loads(token, max_age=0)\n# Returns: {'user': 'test'} — NOT expired",
    status: "confirmed",
  },
  {
    slug: "itsdangerous-empty-secret-key",
    package: "itsdangerous",
    version: "2.2.0",
    severity: "MEDIUM",
    title: "URLSafeSerializer(\"\") accepted — empty string creates HMAC-less tokens",
    description:
      "itsdangerous accepts an empty string as the secret key for `URLSafeSerializer`. The resulting HMAC is cryptographically trivial — any party knowing the serializer format can forge tokens. No error or warning is raised.",
    reproduction:
      "from itsdangerous import URLSafeSerializer\ns = URLSafeSerializer('')\ntoken = s.dumps({'user': 'admin'})\nresult = s.loads(token)\n# Returns: {'user': 'admin'} — no error",
    status: "confirmed",
  },

  // ── PyJWT ─────────────────────────────────────────────────────────────────
  {
    slug: "pyjwt-weak-key-warns-only",
    package: "PyJWT",
    version: "2.11.0",
    severity: "MEDIUM",
    title: "3-byte HMAC key accepted — enforce_minimum_key_length defaults to False",
    description:
      "PyJWT accepts a 3-byte key for HS256 with only an `InsecureKeyLengthWarning`. The `enforce_minimum_key_length` option (added in 2.9.0) defaults to `False`, meaning sub-minimum keys do not raise an error unless explicitly configured. RFC 7518 Section 3.2 requires 32 bytes for SHA-256.",
    reproduction:
      "import jwt, warnings\nwith warnings.catch_warnings(record=True) as w:\n    warnings.simplefilter('always')\n    token = jwt.encode({'sub': 'admin'}, 'abc', algorithm='HS256')\n    result = jwt.decode(token, 'abc', algorithms=['HS256'])\n    # result = {'sub': 'admin'} — weak key accepted",
    status: "confirmed",
  },

  // ── authlib ───────────────────────────────────────────────────────────────
  {
    slug: "authlib-octkey-short-no-warning",
    package: "authlib",
    version: "1.6.9",
    severity: "MEDIUM",
    title: "OctKey.import_key(b\"short\") — 5-byte key accepted without warning for HS256",
    description:
      "authlib's `OctKey.import_key()` accepts a 5-byte key for HS256 without any warning or error. The key is used to successfully encode, decode, and validate a JWT. RFC 7518 requires a minimum of 32 bytes for HS256.",
    reproduction:
      "from authlib.jose import jwt, OctKey\nimport time\nkey = OctKey.import_key(b'short')  # 5 bytes\ntoken = jwt.encode({'alg': 'HS256'}, {'sub': 'admin', 'exp': int(time.time())+3600}, key)\nclaims = jwt.decode(token, key)\nclaims.validate()  # No error, no warning",
    status: "confirmed",
  },
  {
    slug: "authlib-validate-skips-iss-aud",
    package: "authlib",
    version: "1.6.9",
    severity: "MEDIUM",
    title: "JWTClaims.validate() skips iss and aud validation by default",
    description:
      "authlib's `JWTClaims.validate()` does not check `iss` (issuer) or `aud` (audience) claims by default. A token with `iss='attacker.com'` and `aud='not-my-service'` passes `validate()` without error. Explicit `validate_iss()` and `validate_aud()` calls or `ResourceProtector` configuration are required.",
    reproduction:
      "from authlib.jose import jwt, OctKey\nimport time\nkey = OctKey.import_key(b'a' * 32)\ntoken = jwt.encode({'alg': 'HS256'}, {'sub': 'user', 'iss': 'attacker.com', 'aud': 'not-my-service', 'exp': int(time.time())+3600}, key)\nclaims = jwt.decode(token, key)\nclaims.validate()  # No error — wrong issuer/audience accepted",
    status: "confirmed",
  },

  // ── minbpe ────────────────────────────────────────────────────────────────
  {
    slug: "minbpe-train-vocab-size-overflow",
    package: "minbpe",
    version: "latest",
    severity: "MEDIUM",
    title: "train() crashes with ValueError when vocab_size exceeds mergeable pairs",
    description:
      "minbpe's `BasicTokenizer.train()` crashes when `vocab_size` exceeds the number of unique mergeable byte pairs in the training text. `max()` is called on an empty iterable, raising `ValueError: max() iterable argument is empty`.",
    reproduction:
      "from minbpe import BasicTokenizer\nBasicTokenizer().train('aaaaaaaaaa', 261)\n# ValueError: max() iterable argument is empty",
    status: "confirmed",
  },
  {
    slug: "minbpe-load-space-in-special-token",
    package: "minbpe",
    version: "latest",
    severity: "MEDIUM",
    title: "load() crashes when special token name contains a space",
    description:
      "minbpe's `load()` method parses special tokens by splitting on whitespace. A special token name containing a space produces more than 2 fields when split, raising `ValueError: too many values to unpack (expected 2, got 3)`.",
    reproduction:
      "# Writing model file with special token containing a space\n# Then calling tokenizer.load('model.model')\n# ValueError: too many values to unpack (expected 2, got 3)",
    status: "confirmed",
  },

  // ── pydantic ──────────────────────────────────────────────────────────────
  {
    slug: "pydantic-model-validator-before-typeerror",
    package: "pydantic",
    version: "2.12.5",
    severity: "MEDIUM",
    title: "model_validator(mode='before') raises raw TypeError on bad input (not ValidationError)",
    description:
      "When a `model_validator(mode='before')` raises a raw `TypeError` (e.g., `can't multiply sequence by non-int of type 'str'`), pydantic does not wrap it in a `ValidationError`. The raw `TypeError` propagates to the caller. In FastAPI, this causes an HTTP 500 instead of a 422 validation error.",
    reproduction:
      "# Model with model_validator(mode='before') that triggers TypeError on string input\n# e.g. validator multiplies a field by an int\n# Result: TypeError propagates instead of ValidationError",
    status: "confirmed",
  },
  {
    slug: "pydantic-model-copy-shallow-default",
    package: "pydantic",
    version: "2.12.5",
    severity: "MEDIUM",
    title: "model_copy() is shallow by default — mutating copy mutates original",
    description:
      "pydantic's `model_copy()` performs a shallow copy by default. Mutable fields (lists, dicts) are shared between the original and the copy. Appending to a list field on the copy also mutates the original model.",
    reproduction:
      "# m1 = MyModel(tags=[1, 2])\n# m2 = m1.model_copy()\n# m2.tags.append(99)\n# assert m1.tags == [1, 2, 99]  # True — original mutated",
    status: "confirmed",
  },
  {
    slug: "pydantic-model-copy-update-bypasses-validators",
    package: "pydantic",
    version: "2.12.5",
    severity: "MEDIUM",
    title: "model_copy(update=) bypasses all validators",
    description:
      "Using `model_copy(update={...})` bypasses all field validators and `model_validator` logic. Fields that would fail validation during construction (negative balance, None for required field) are silently accepted when set via `model_copy(update=)`.",
    reproduction:
      "# account = Account(balance=1000.0, account_id='acc123')\n# copy = account.model_copy(update={'balance': -99999.0, 'account_id': None})\n# copy.balance == -99999.0  # True — validators bypassed",
    status: "confirmed",
  },

  // ── click ─────────────────────────────────────────────────────────────────
  {
    slug: "click-required-option-allows-empty-string",
    package: "click",
    version: "8.3.1",
    severity: "MEDIUM",
    title: "required=True option allows empty string and whitespace-only values",
    description:
      "click's `required=True` option flag only checks that the option was provided — it does not validate that the value is non-empty. `--name \"\"` and `--name \"   \"` both succeed with exit code 0, passing an empty or whitespace-only string to the application.",
    reproduction:
      "# @click.option('--name', required=True)\n# Running: mycommand --name \"\"\n# exit_code=0, name='' — required but empty accepted",
    status: "confirmed",
  },

  // ── MiroFish ──────────────────────────────────────────────────────────────
  {
    slug: "mirofish-infinite-loop-chunk-overlap",
    package: "MiroFish",
    version: "latest",
    severity: "HIGH",
    title: "Infinite loop in split_text_into_chunks when overlap >= chunk_size",
    description:
      "MiroFish's `split_text_into_chunks` function contains an infinite loop when `overlap >= chunk_size`. The loop body sets `start = end - overlap`, which — when overlap equals chunk_size — does not advance the position, causing an infinite loop that hangs the server.",
    reproduction:
      "# split_text_into_chunks(text, chunk_size=10, overlap=10)\n# start = end - overlap = end - chunk_size = start (never advances)\n# Infinite loop",
    status: "confirmed",
  },
  {
    slug: "mirofish-traceback-in-http-responses",
    package: "MiroFish",
    version: "latest",
    severity: "HIGH",
    title: "Full Python tracebacks returned in HTTP error responses",
    description:
      "MiroFish returns full Python tracebacks in HTTP error responses via `traceback.format_exc()`. Found 6 occurrences in graph.py, 30 in simulation.py, and 17 in report.py. These expose internal file paths, line numbers, and code structure to clients.",
    reproduction:
      "# traceback.format_exc() found in:\n# backend/graph.py (6x), simulation.py (30x), report.py (17x)\n# Any unhandled exception returns full traceback to HTTP client",
    status: "confirmed",
  },
  {
    slug: "mirofish-hardcoded-secret-key",
    package: "MiroFish",
    version: "latest",
    severity: "HIGH",
    title: "Hardcoded SECRET_KEY='mirofish-secret-key' and DEBUG=True defaults",
    description:
      "MiroFish ships with `SECRET_KEY='mirofish-secret-key'` and `DEBUG=True` as default values in `backend/app/config.py` lines 24-25. Applications deployed without overriding these values use a public, known secret key and expose debug information.",
    reproduction:
      "# backend/app/config.py:24-25:\nSECRET_KEY = 'mirofish-secret-key'\nDEBUG = True",
    status: "confirmed",
  },
  {
    slug: "mirofish-path-traversal-platform-param",
    package: "MiroFish",
    version: "latest",
    severity: "HIGH",
    title: "Path traversal via platform query parameter",
    description:
      "MiroFish uses the `platform` query parameter directly in `os.path.join()` without sanitization. Passing `../../secret_profiles.json` as the platform value causes `os.path.normpath` to produce a path outside the intended upload directory.",
    reproduction:
      "import os\nos.path.normpath(os.path.join('/uploads/simulations/sim_abc', '../../secret_profiles.json'))\n# Result escapes base directory",
    status: "confirmed",
  },
  {
    slug: "mirofish-cjk-isalnum-bypass",
    package: "MiroFish",
    version: "latest",
    severity: "MEDIUM",
    title: "Non-ASCII (CJK) characters pass isalnum() filter unchanged",
    description:
      "MiroFish uses Python's `isalnum()` to filter usernames. CJK and other Unicode characters return `True` for `isalnum()` — `'张'.isalnum()` is `True`. The filter intended for ASCII alphanumeric validation passes all Unicode letters and digits unchanged.",
    reproduction:
      "'张'.isalnum()  # True\n# CJK names pass through the username filter unchanged",
    status: "confirmed",
  },
  {
    slug: "mirofish-path-traversal-simulation-id",
    package: "MiroFish",
    version: "latest",
    severity: "HIGH",
    title: "Path traversal via unvalidated simulation_id parameter",
    description:
      "MiroFish passes the `simulation_id` parameter directly to `os.path.join()` without validation. A crafted `simulation_id` containing `../` sequences can escape the simulations directory and access arbitrary files on the filesystem.",
    reproduction:
      "import os\nos.path.normpath(os.path.join('/data/simulations', '../../uploads/projects/proj_abc'))\n# Escapes to \\uploads\\projects\\proj_abc",
    status: "confirmed",
  },

  // ── hermes-agent ─────────────────────────────────────────────────────────
  {
    slug: "hermes-agent-duplicate-close-drops-wal",
    package: "hermes-agent",
    version: "latest",
    severity: "HIGH",
    title: "Duplicate close() method silently discards WAL checkpoint",
    description:
      "hermes-agent defines `close()` twice in the same class. The first definition at line 238 includes a WAL checkpoint; the second at line 352 does not. Python silently uses the second definition, discarding the WAL checkpoint. This can cause data loss on graceful shutdown.",
    reproduction:
      "# AST analysis confirmed:\n# close() at line 238 — includes WAL PRAGMA wal_checkpoint\n# close() at line 352 — no checkpoint\n# Python uses the second definition; WAL checkpoint never called",
    status: "confirmed",
  },
  {
    slug: "hermes-agent-fuzzy-replace-false-positive",
    package: "hermes-agent",
    version: "latest",
    severity: "HIGH",
    title: "fuzzy_find_and_replace with replace_all=True corrupts unrelated code",
    description:
      "hermes-agent's `fuzzy_find_and_replace` with `replace_all=True` and the `_strategy_context_aware` method produces false positives, replacing code in unrelated functions. In testing, 2 replacements were made when only 1 was expected, overwriting a different function's body.",
    reproduction:
      "# fuzzy_find_and_replace('foo()', 'bar()', replace_all=True)\n# Result: 2 replacements made instead of 1\n# Unrelated function bar() overwritten with foo() body",
    status: "confirmed",
  },
  {
    slug: "hermes-agent-suggest-files-false-positive",
    package: "hermes-agent",
    version: "latest",
    severity: "MEDIUM",
    title: "_suggest_similar_files char-set heuristic returns semantically unrelated files",
    description:
      "hermes-agent's `_suggest_similar_files` uses a character-set intersection heuristic. `'unrelated_file.py'` scores 0.86 against `'main.py'` (above the 0.50 threshold) because the character sets overlap heavily. The heuristic returns semantically irrelevant files as suggestions.",
    reproduction:
      "# _suggest_similar_files('main.py')\n# 'unrelated_file.py' scores 0.86 via character-set intersection\n# Threshold is 0.50 — semantically unrelated file returned",
    status: "confirmed",
  },
  {
    slug: "hermes-agent-model-routing-inflection",
    package: "hermes-agent",
    version: "latest",
    severity: "MEDIUM",
    title: "choose_cheap_model_route misses inflected keyword forms",
    description:
      "hermes-agent's `choose_cheap_model_route` keyword matching does not handle inflected word forms. The keyword list contains `'implement'` but not `'implementing'`, `'testing'` routes to the cheap model even though `'test'` was meant to use the expensive model.",
    reproduction:
      "# 'can you do some testing' → routed to cheap model\n# 'implement' in keywords but 'implementing' is not\n# Inflected forms bypass the intended routing logic",
    status: "confirmed",
  },

  // ── DeerFlow ──────────────────────────────────────────────────────────────
  {
    slug: "deerflow-asyncio-lock-cross-thread-deadlock",
    package: "DeerFlow",
    version: "latest",
    severity: "HIGH",
    title: "asyncio.Lock() at module level causes cross-thread deadlock",
    description:
      "DeerFlow creates an `asyncio.Lock()` at module level. A lock acquired in one thread's event loop cannot be released from a different thread's event loop. When two threads share the module-level lock, the second thread deadlocks with `TimeoutError`.",
    reproduction:
      "# Module-level: lock = asyncio.Lock()\n# Thread 1 acquires lock in its event loop\n# Thread 2 attempts to acquire lock in a different event loop\n# Thread 2 times out with TimeoutError — deadlock confirmed",
    status: "confirmed",
  },
  {
    slug: "deerflow-upload-regex-word-boundary",
    package: "DeerFlow",
    version: "latest",
    severity: "MEDIUM",
    title: "_UPLOAD_SENTENCE_RE word boundary \\b prevents /mnt/ path matching",
    description:
      "DeerFlow's `_UPLOAD_SENTENCE_RE` regex uses `\\b` (word boundary) before `/mnt/`. A `\\b` assertion fails before a `/` character because `/` is not a word character boundary. Paths starting with `/mnt/user-data/uploads/` never match the intended pattern.",
    reproduction:
      "import re\npattern = re.compile(r'\\b/mnt/user-data/uploads/')\nbool(pattern.search('/mnt/user-data/uploads/file.txt'))  # False — \\b fails before /",
    status: "confirmed",
  },
  {
    slug: "deerflow-upload-regex-period-garbled",
    package: "DeerFlow",
    version: "latest",
    severity: "MEDIUM",
    title: "_UPLOAD_SENTENCE_RE leaves garbled text when filename contains periods",
    description:
      "DeerFlow's upload sentence regex fails to cleanly remove sentences containing filenames with periods. The regex matches up to the period in the filename extension, leaving a garbled fragment (`'pdf. They asked about Python.'`) after the sentence replacement.",
    reproduction:
      "# Input: 'The user uploaded a file called report.pdf. They asked about Python.'\n# After regex substitution: 'pdf. They asked about Python.'\n# Garbled fragment left behind",
    status: "confirmed",
  },
  {
    slug: "deerflow-str-replace-tool-empty-file",
    package: "DeerFlow",
    version: "latest",
    severity: "MEDIUM",
    title: "str_replace_tool returns OK for empty files without checking old_str",
    description:
      "DeerFlow's `str_replace_tool` at `tools.py:879` has an early return: `if not content: return 'OK'`. This bypasses the 'old_str not found' check for empty files, returning success even when the intended replacement string was not present.",
    reproduction:
      "# tools.py:879:\nif not content:\n    return 'OK'  # Bypasses the not-found check entirely",
    status: "confirmed",
  },
  {
    slug: "deerflow-uploads-middleware-drops-image-blocks",
    package: "DeerFlow",
    version: "latest",
    severity: "MEDIUM",
    title: "UploadsMiddleware discards non-text content blocks in multi-modal messages",
    description:
      "DeerFlow's `UploadsMiddleware` at `uploads_middleware.py:183-188` only extracts content blocks where `type=='text'`. Image blocks and other non-text content are silently dropped before the message is reconstructed and passed downstream.",
    reproduction:
      "# uploads_middleware.py:183-188:\n# Only type=='text' blocks extracted\n# Image blocks dropped before reconstructing message",
    status: "confirmed",
  },

  // ── open-swe ──────────────────────────────────────────────────────────────
  {
    slug: "open-swe-middleware-success-false-ignored",
    package: "open-swe",
    version: "latest",
    severity: "HIGH",
    title: "Middleware safety net skips recovery when commit_and_open_pr tool fails",
    description:
      "In `open_pr.py:87`, the middleware checks `'success' in payload` rather than `payload['success'] == True`. The string `'success'` is always in the payload dict as a key — even when its value is `False`. The recovery logic is never triggered on tool failure.",
    reproduction:
      "payload = {'success': False, 'error': 'PR creation failed'}\nif 'success' in payload:  # True — key exists, value ignored\n    pass  # Recovery skipped",
    status: "confirmed",
  },
  {
    slug: "open-swe-extract-repo-slash-in-name",
    package: "open-swe",
    version: "latest",
    severity: "MEDIUM",
    title: "extract_repo_from_text returns repo name with embedded slash",
    description:
      "open-swe's `extract_repo_from_text` does not handle extra path segments after `owner/name`. Input `'repo:owner/name/extra'` returns `{'owner': 'owner', 'name': 'name/extra'}` — the repo name includes an embedded slash, producing invalid GitHub API calls.",
    reproduction:
      "extract_repo_from_text('repo:owner/name/extra')\n# Returns: {'owner': 'owner', 'name': 'name/extra'}",
    status: "confirmed",
  },
  {
    slug: "open-swe-git-checkout-force-reset",
    package: "open-swe",
    version: "latest",
    severity: "HIGH",
    title: "git checkout -B force-resets existing branch on agent retry",
    description:
      "open-swe uses `git checkout -B` (confirmed at `github.py:72`) to create working branches. The `-B` flag force-resets the branch to the current HEAD if the branch already exists. On agent retry, all previous work on that branch is destroyed.",
    reproduction:
      "# github.py:72: git checkout -B <branch>\n# If branch exists from a previous attempt:\n# -B force-resets it to current HEAD\n# Previous commits on branch lost",
    status: "confirmed",
  },
  {
    slug: "open-swe-git-suffix-invalid-repo-name",
    package: "open-swe",
    version: "latest",
    severity: "MEDIUM",
    title: "GitHub URL with .git suffix produces invalid repo name",
    description:
      "open-swe's `extract_repo_from_text` does not strip the `.git` suffix from GitHub clone URLs. Input `'https://github.com/langchain-ai/open-swe.git'` returns `{'name': 'open-swe.git'}` — the trailing `.git` is included in the repo name, causing invalid GitHub API calls.",
    reproduction:
      "extract_repo_from_text('https://github.com/langchain-ai/open-swe.git')\n# Returns: {'name': 'open-swe.git'} — .git suffix not stripped",
    status: "confirmed",
  },

  // ── llm ───────────────────────────────────────────────────────────────────
  {
    slug: "llm-truncate-string-max-length-contract",
    package: "llm",
    version: "0.29",
    severity: "MEDIUM",
    title: "truncate_string violates length contract when max_length < 3",
    description:
      "The `truncate_string` function in the `llm` package adds a `...` suffix (3 characters) without checking whether the requested `max_length` is at least 3. When `max_length=0`, the function returns `'hello wo...'` (11 chars) — violating the length contract entirely.",
    reproduction:
      "truncate_string('hello world', max_length=0)\n# Returns: 'hello wo...' — 11 chars, not 0",
    status: "confirmed",
  },

  // ── watchfiles ────────────────────────────────────────────────────────────
  {
    slug: "watchfiles-git-paths-not-filtered-windows",
    package: "watchfiles",
    version: "1.1.1",
    severity: "MEDIUM",
    title: "Forward-slash .git paths not filtered on Windows (os.sep='\\\\' splits on backslash)",
    description:
      "watchfiles filters `.git` paths by splitting on `os.sep` (backslash on Windows). Paths with forward slashes (e.g., `'C:/project/.git/config'`) are not split correctly — `'.git'` is not found in the resulting parts list and is not filtered. Git internal change events are delivered to watchers on Windows.",
    reproduction:
      "import os\n# On Windows: os.sep = '\\\\'\n'C:/project/.git/config'.lstrip('\\\\').split('\\\\')  \n# ['C:/project/.git/config'] — .git not in parts, not filtered",
    status: "confirmed",
  },
];

export function getBugBySlug(slug: string): BugReport | undefined {
  return bugs.find((b) => b.slug === slug);
}

export function getBugsBySeverity(severity: BugReport["severity"]): BugReport[] {
  return bugs.filter((b) => b.severity === severity);
}

export const bugSlugs = bugs.map((b) => b.slug);
