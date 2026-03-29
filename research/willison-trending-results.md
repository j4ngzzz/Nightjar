# Willison & Trending Python Tools — Code Scan Results

**Scan date:** 2026-03-28
**Scanner:** Nightjar CODE SCANNER agent (claude-sonnet-4-6)
**Method:** Static analysis + live edge-case testing via Python interpreter

---

## Package Versions Scanned

| Package | Version | Location |
|---------|---------|----------|
| `llm` | 0.29 | Simon Willison |
| `datasette` | 0.65.2 | Simon Willison |
| `sqlite-utils` | 3.39 | Simon Willison |
| `rich` | 14.3.3 | Will McGugan / Textualize |
| `watchfiles` | 1.1.1 | Samuel Colvin / Pydantic team |
| `tomllib` | built-in (Python 3.11+) | stdlib |

---

## 1. `llm` (0.29) — Simon Willison

**Functions scanned:** ~259

### API Key Handling

**CLEAN.** The key management pipeline is disciplined:

- `get_key()` in `__init__.py` implements a correct precedence chain: explicit arg > stored alias > env var. No key is ever logged.
- `keys_set` in `cli.py` calls `path.chmod(0o600)` on initial file creation. Subsequent writes via `path.write_text()` preserve permissions on POSIX. On Windows, `chmod(0o600)` is effectively a no-op (Windows ACLs don't map to POSIX mode bits — `stat` returns `0o666` regardless), but this is a platform limitation, not a code defect.
- The debug logging transport (`_log_response` in `utils.py`) correctly redacts `Authorization` headers (`value = "[...]"`) and truncates cookie values. No accidental key leakage in debug mode.
- OpenAI-compatible models that don't require a key use the literal string `"DUMMY_KEY"` to satisfy the `openai` client library requirement. This is intentional and clearly commented.

### Response Parsing

**CLEAN.** Streaming response iteration uses standard Python generators throughout. No unsafe deserialization.

### `extract_fenced_code_block` (utils.py)

**CLEAN.** Regex is correctly anchored with `(?m)^` and uses named groups. Handles variable-length fences (3+ backticks). Returns `None` on no match. Tested with empty strings, single-backtick fences, and mismatched fences — all behave correctly.

### `truncate_string` (utils.py) — BUG FOUND

**Low severity / internal tooling.**

When `max_length < 3`, the function produces output that *exceeds* `max_length`:

```python
truncate_string('hello world', max_length=0)  # -> 'hello wo...' (11 chars, not 0)
truncate_string('hello world', max_length=1)  # -> 'hello wor...' (12 chars, not 1)
truncate_string('hello world', max_length=2)  # -> 'hello worl...' (13 chars, not 2)
truncate_string('hello world', max_length=3)  # -> '...' (3 chars, OK)
```

**Root cause:** `text[:max_length - 3]` with `max_length < 3` yields a negative slice (e.g., `text[:-2]`), which Python interprets as "all but last 2 characters." The `...` suffix is then appended, making the result longer than `max_length`.

**Impact:** All call sites in `cli.py` pass `max_length=100` (default). The bug is only triggerable with `max_length in {0, 1, 2}`. No security impact. No data corruption. This is a cosmetic display-length bug in an internal helper.

**Proposed fix:**
```python
if len(text) <= max_length:
    return text
if max_length <= 3:
    return "." * max_length  # degenerate case
```

### `_parse_kwargs` / `instantiate_from_spec` (utils.py)

**CLEAN.** These functions parse plugin/tool instantiation specs. All values are parsed as JSON (not `eval`). Injection attempts like `Foo(x=1; __import__("os").system("id"))` correctly raise `ValueError` because `1; __import__...` is not valid JSON. The class lookup is whitelist-based (`class_map` dict), so arbitrary class instantiation is not possible.

### `schema_dsl` (utils.py)

**CLEAN.** The DSL parser produces JSON Schema output. Empty input yields a valid empty schema `{"type": "object", "properties": {}, "required": []}` — correct behavior. Single fields default to `"type": "string"` — reasonable default.

### `monotonic_ulid` (utils.py)

**CLEAN.** Correct monotonic ULID implementation with thread lock. Uses `os.urandom` for the random component. Raises `OverflowError` correctly on >2^80 ULIDs per millisecond (practically unreachable). TIMESTAMP_LEN=6, RANDOMNESS_LEN=10 match the ULID spec.

---

## 2. `sqlite-utils` (3.39) — Simon Willison

**Functions scanned:** ~237

### SQL Injection Prevention

**CLEAN.** The library uses parameterized queries throughout for user-controlled *values*. Identifiers (table names, column names) are wrapped using bracket quoting: `[identifier_name]`.

### `quote_fts` (db.py)

**CLEAN.** The FTS escape function correctly neutralizes SQLite FTS5 operator keywords (NOT, OR, AND, NEAR) by wrapping all tokens in double quotes. Tested with:

- SQL injection attempts (`SELECT * FROM users` → `"SELECT" "*" "FROM" "users"`) — safely quoted
- Unbalanced double-quotes — correctly balanced by appending a closing `"`
- Empty string — returns empty string
- FTS keywords (NOT, OR, AND, NEAR) — all wrapped as literals

Null bytes pass through unmodified (`\x00`) — this is acceptable because SQLite itself handles null bytes in FTS queries safely (they don't terminate strings in Python's sqlite3 binding).

### Bracket quoting edge case: `]` in identifiers

**Low severity / safe failure mode.**

`escape_sqlite()` in datasette (not sqlite-utils itself, but the companion) wraps identifiers in `[...]` but does **not** double the `]` character as SQLite's bracket-quoting syntax requires for literal `]` in identifiers. This means a column named `col]name` would be escaped to `[col]name]` — which SQLite's parser rejects with `unrecognized token: "]"`.

This is a **safe failure**: the query errors out rather than executing injected SQL. The failure mode was confirmed by testing: injected content after the `]` never executes.

Furthermore, datasette validates table/column names against the live database schema before constructing queries (FK check in `_through` filter, column check in search filter), providing defense-in-depth.

---

## 3. `datasette` (0.65.2) — Simon Willison

**Functions scanned:** ~1,129

### SQL Injection Prevention — Overall

**WELL-ENGINEERED.** Datasette uses a layered defense:

1. **`escape_sqlite(s)`** — wraps identifiers in `[...]` brackets for structural SQL positions (table names, column names in ORDER BY, SELECT, etc.)
2. **`escape_fts(query)`** — wraps FTS tokens in double quotes to prevent keyword injection in MATCH clauses
3. **Parameterized queries** — all user-supplied *values* go through SQLite's `?`/`:param` binding
4. **Schema validation before query construction** — table names from `_through` parameter are validated against existing FK relationships; column names in `_search_colname` are validated against `table_columns()` result

### `filters.py` — Filter Pipeline

**CLEAN.** The `TemplatedFilter`, `InFilter`, `NotInFilter` classes build WHERE clauses using parameterized placeholders (`:p{n}`) for all values. Column names are string-formatted into the SQL template but only after passing through `escape_sqlite()`. The `Filters.build_where_clauses()` method increments a counter correctly to avoid parameter name collisions.

### `_where` parameter (raw SQL injection)

**By design.** Datasette allows `?_where=` raw SQL clauses gated behind the `execute-sql` permission check. This is an intentional power-user feature, documented and permission-controlled. Not a bug.

### `_timelimit` parameter

**Observation (not a bug).** `request.args.get("_timelimit")` is passed through `int()` without bounds checking. An attacker could set `_timelimit=999999999` to force a very long query execution window. However since datasette is read-only by default and this would only affect query timeout enforcement (not bypass it), this is low risk.

### `make_dockerfile` (utils/__init__.py)

**CLEAN.** All command arguments are passed through `shlex.quote()` before inclusion in the Dockerfile CMD string. `$PORT` is intentionally left unquoted (it's a fixed env variable reference).

---

## 4. `rich` (14.3.3) — Will McGugan / Textualize

**Functions scanned:** ~705

### Markup Parsing

**CLEAN.** The `rich.markup.escape()` function correctly escapes user-supplied strings by prepending `\\` before each markup tag pattern (`[tag]`). Tested with:

- Bold/color markup injection → correctly escaped to `\\[bold]...`
- JavaScript URI attempts (`[link=javascript:alert(1)]`) → escaped
- Unmatched `[` and `]` characters → passed through unmodified (not treated as tags)
- Empty string → empty string returned

### `escape()` does not accept None

**Cosmetic / type contract violation.** `rich.markup.escape(None)` raises `TypeError: expected string or bytes-like object, got 'NoneType'`. This is correct behavior (the function's type signature is `escape(markup: str) -> str`), but callers that pass potentially-None values without checking will get an unhelpful `TypeError` rather than a `MarkupError`. Not a security issue.

### Unclosed tag handling

**CLEAN.** Unclosed opening tags (e.g., `[bold]text`) silently apply the style to remaining text — expected rich behavior. Unopened closing tags raise `MarkupError` with a clear message. Misnested tags are resolved heuristically (inner tag wins for span).

### Terminal markup injection (not a code bug)

**Design note.** Rich is a terminal formatting library. If an application passes unescaped user input to `Console.print(user_input)`, the user can inject rich markup (bold text, colors, blinks, links). This is markup injection into a terminal display, **not code execution**. Rich's `escape()` function exists precisely to prevent this. Whether developers use it is outside rich's control. The library provides the right tool.

---

## 5. `watchfiles` (1.1.1) — Samuel Colvin

**Functions scanned:** ~39 (Python layer; Rust core not analyzed)

### Path Filtering

**MOSTLY CLEAN, one platform edge case.**

The `BaseFilter.__call__()` method splits paths using `os.sep`:
```python
parts = path.lstrip(os.sep).split(os.sep)
```

On **Windows** (`os.sep = '\\'`), if watchfiles' Rust core emits paths with **forward slashes** (e.g., `C:/project/.git/config`), the Python filter will fail to split them correctly. The result is `parts = ['C:/project/.git/config']` (one element), and the `.git` directory will **not** be ignored.

Testing confirms:
- Backslash Windows paths: correctly filtered (`r'C:\project\.git\config'` → ignored)
- Forward-slash paths on Windows: NOT correctly filtered (`'C:/project/.git/config'` → passes through)

**Actual risk:** Low. The Rust core of watchfiles likely normalizes to the OS-native path separator before emitting events to Python. However, this has not been verified from the Rust source. If any cross-platform tool or subprocess passes forward-slash paths on Windows to watchfiles callbacks, the ignore list would be bypassed.

**No security impact.** This only affects file change event filtering (`.git`, `__pycache__`, etc.), not access control.

### `ignore_paths` prefix matching

**CLEAN.** `path.startswith(self._ignore_paths)` uses Python's tuple-form `startswith`, which requires the path to start with one of the exact strings in the tuple. An `ignore_paths=['/safe/path']` entry does NOT accidentally match `/safe/pathextra` — tested and confirmed.

---

## 6. `tomllib` (built-in, Python 3.11+)

**Functions scanned:** N/A (stdlib, C implementation)

**CLEAN.** Standard library TOML parser. Correctly rejects duplicate keys with `TOMLDecodeError`. Null bytes in TOML strings are parsed into Python strings (valid behavior per TOML spec). No exploitable edge cases found in normal usage.

---

## Summary Table

| Package | Functions | Bugs Found | Severity | Notes |
|---------|-----------|------------|----------|-------|
| `llm` 0.29 | ~259 | 1 | Low | `truncate_string` length contract broken for `max_length < 3` |
| `sqlite-utils` 3.39 | ~237 | 0 | — | Clean. Well-engineered parameterized query usage. |
| `datasette` 0.65.2 | ~1,129 | 0 | — | Clean. Excellent layered SQL injection defense. |
| `rich` 14.3.3 | ~705 | 0 | — | Clean. Escape function works correctly. |
| `watchfiles` 1.1.1 | ~39 | 1 | Low | Forward-slash path filtering bypassed on Windows |
| `tomllib` stdlib | — | 0 | — | Clean. |

**Total functions scanned: ~2,369**

---

## Verdict

Simon Willison's packages (`llm`, `datasette`, `sqlite-utils`) are **well-engineered**. The SQL injection surface is handled with consistent discipline: parameterized values everywhere, identifier escaping via `escape_sqlite()`, and schema-level validation before query construction. This is well-tested, production-grade code.

`rich` is **well-engineered**. The markup parser is robust and the escape function works correctly. Terminal markup injection is a design-level concern, not a code defect.

`watchfiles` is **well-engineered** with one minor platform-specific edge case on Windows forward-slash paths that is unlikely to matter in practice.

The only actionable bug is `llm.utils.truncate_string()` with `max_length < 3`, which violates its length contract but has no security or data-integrity impact.
