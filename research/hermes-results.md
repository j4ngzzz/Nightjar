# NousResearch/hermes-agent — Bug Scan Results

Scan date: 2026-03-28
Repository: https://github.com/NousResearch/hermes-agent
Clone depth: 1 (HEAD)
Files scanned: 579 Python files
Method: Static analysis + live code execution

---

## Confirmed Bugs

### BUG-1 — Duplicate `close()` method silently discards WAL checkpoint
**File:** `hermes_state.py`
**Lines:** 238 and 352
**Severity:** Medium — Data integrity (WAL file grows unbounded; sessions may not be flushed on exit)

**Description:**
`SessionDB` defines `close()` twice inside the same class body. Python class bodies execute top-to-bottom and the second definition silently overwrites the first. The first `close()` (line 238) performs a `PRAGMA wal_checkpoint(PASSIVE)` before closing the connection so WAL frames are flushed back into the main database file. The second `close()` (line 352) simply closes the connection without the checkpoint.

Because Python always uses the last definition, the WAL checkpoint code is unreachable and never executes. The WAL file grows unbounded under concurrent multi-process usage (gateway + CLI + worktree agents), and on-disk data may not be committed to the main database file when the process exits.

**Reproduction:**

```python
import ast
with open("hermes_state.py") as f:
    tree = ast.parse(f.read())
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef) and node.name == "SessionDB":
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == "close":
                print(f"close() at line {item.lineno}")
# Output:
# close() at line 238    <- has WAL checkpoint; DEAD CODE
# close() at line 352    <- no checkpoint; the one Python uses
```

**Fix:** Remove the redundant definition at line 352. The correct implementation with the WAL checkpoint is at line 238.

---

### BUG-2 — `fuzzy_find_and_replace` with `replace_all=True` corrupts unrelated code via `_strategy_context_aware` false positives
**File:** `tools/fuzzy_match.py`
**Function:** `_strategy_context_aware` (line 315), `fuzzy_find_and_replace` (line 50)
**Severity:** High — Data corruption (wrong source code sections overwritten)

**Description:**
`_strategy_context_aware` (Strategy 8) accepts a block as a match if ≥ 50% of its lines have SequenceMatcher similarity ≥ 0.80 with the corresponding pattern lines. For short patterns (2–4 lines) this threshold is easily met by structurally similar but semantically different code — for example two methods with identical bodies but different names.

When `fuzzy_find_and_replace` is called with `replace_all=True`, all positions returned by the first matching strategy are replaced. If `_strategy_context_aware` is the first strategy to match (strategies 1–7 all fail, e.g., because `old_string` has different whitespace or a slightly different first-line comment), it can return multiple matches across entirely different functions or blocks. All of them get overwritten.

**Reproduction (live-verified):**

```python
from tools.fuzzy_match import fuzzy_find_and_replace

content = (
    "    def foo(self, x):  # helper\n"
    "        # first implementation\n"
    "        return x * 2\n"
    "    \n"
    "    def bar(self, y):  # helper\n"
    "        # first implementation\n"
    "        return y * 2\n"
)
# old_string has no comment on first line — exact/trimmed/ws/indent/trimmed-boundary
# all fail because first lines differ. block_anchor fails (first lines differ after strip).
# Only context_aware matches, and it matches BOTH methods.
old = "    def foo(self, x):\n        # first implementation\n        return x * 2"
new = "    def foo(self, x):\n        # PATCHED\n        return x * 2"

result, count, err = fuzzy_find_and_replace(content, old, new, replace_all=True)
assert count == 2          # BOTH methods replaced
assert "def bar" not in result  # bar() was overwritten and renamed to foo()
```

**Output:**
```
    def foo(self, x):
        # PATCHED
        return x * 2

    def foo(self, x):      <-- bar() body corrupted, wrong name
        # PATCHED
        return x * 2
```

**Fix:** Raise the per-line similarity threshold in `_strategy_context_aware` from 0.80 to at least 0.95, and raise the block acceptance threshold from 50% to at least 80%. Alternatively, require all lines (not 50%) to meet the similarity requirement to reduce false positives.

---

### BUG-3 — `_suggest_similar_files` uses character-set intersection — returns semantically unrelated files
**File:** `tools/file_operations.py`
**Function:** `_suggest_similar_files` (line 621)
**Severity:** Low — UX / LLM misdirection

**Description:**
When a requested file does not exist, `_suggest_similar_files` ranks candidates by the ratio of shared _characters_ (not substrings):

```python
common = set(filename.lower()) & set(f.lower())
if len(common) >= len(filename) * 0.5:
    similar.append(...)
```

A character-set intersection is essentially meaningless for filenames. Most Python files share the characters `p`, `y`, `.` so almost any `.py` file will match any other `.py` file at or above the 50% threshold. The method returns up to 5 suggestions, any of which may be entirely unrelated to the missing file.

**Reproduction (live-verified):**

```python
filename = "main.py"
candidates = ["train.py", "brain.py", "pain.py", "gain.py", "unrelated_file.py"]
for f in candidates:
    common = set(filename.lower()) & set(f.lower())
    ratio = len(common) / len(filename)
    print(f"{f}: ratio={ratio:.2f}, suggested={ratio >= 0.5}")
# train.py: 0.86, suggested=True   <-- unrelated
# brain.py: 0.86, suggested=True   <-- unrelated
# unrelated_file.py: 0.86, suggested=True  <-- unrelated
```

An LLM receiving these suggestions may read a wrong file and act on wrong content.

**Fix:** Replace character-set intersection with a proper fuzzy-name algorithm such as difflib `SequenceMatcher` on the full filename string, or use an edit-distance threshold.

---

### BUG-4 — `choose_cheap_model_route` keyword detection misses common derivations of complex-work terms
**File:** `agent/smart_model_routing.py`
**Function:** `choose_cheap_model_route` (line 66)
**Severity:** Low — Incorrect model routing (complex tasks sent to cheap/weak model)

**Description:**
The function guards complex-work routing by checking whether the user message contains any word from `_COMPLEX_KEYWORDS`. The check strips trailing punctuation from each token but does not apply stemming or prefix matching. As a result, inflected forms of every keyword in the set are not caught:

| Input word | In `_COMPLEX_KEYWORDS` | Routed to cheap? |
|---|---|---|
| `testing` | No (`test` is) | Yes (bug) |
| `implementing` | No (`implement` is) | Yes (bug) |
| `refactored` | No (`refactor` is) | Yes (bug) |
| `analyzing` | No (`analyze` is) | Yes (bug) |
| `optimization` | No (`optimize` is) | Yes (bug) |
| `retest` | No | Yes (bug) |

**Reproduction (live-verified):**

```python
from agent.smart_model_routing import choose_cheap_model_route

cfg = {"enabled": True, "cheap_model": {"provider": "openai", "model": "gpt-4o-mini"},
       "max_simple_chars": 160, "max_simple_words": 28}

result = choose_cheap_model_route("can you do some testing", cfg)
assert result is not None   # routed to cheap — BUG; should be blocked
```

**Fix:** Either expand `_COMPLEX_KEYWORDS` to include common inflections, or apply a simple stemming pass (e.g., strip common suffixes `-ing`, `-ed`, `-tion`, `-er`) before the intersection check.

---

## Not Bugs (Investigated and Cleared)

- **V4A patch path traversal** (`tools/patch_parser.py`): `parse_v4a_patch` does not sanitize file paths (e.g., `../../etc/passwd`). However the downstream `write_file` call in `file_operations.py` applies `os.path.realpath` + `_is_write_denied` which resolves traversal sequences and blocks writes to protected system paths. Mitigated at the write layer.

- **`_expand_path` shell injection via `~username/suffix`** (`tools/file_operations.py` line 428): The username portion is validated with `re.fullmatch(r'[a-zA-Z0-9._-]+', username)`. The suffix is never passed to `_exec` directly; it is concatenated as a string and only reaches the shell after `_escape_shell_arg` wraps it in single-quotes. Safe.

- **`_search_files_rg` glob pattern wrapping** (`tools/file_operations.py` line 931): The `*{pattern}` prefix added to bare names is correct for `rg --files -g` and produces expected results.

- **`_init_schema` migration chain** (`hermes_state.py` line 253): All migration guards use `if current_version < N` (not `elif`), so a database at version 1 correctly runs all migrations in a single `_init_schema` call. The in-memory `current_version` variable is never updated but this is intentional — each block independently tests the original version. Correct.

- **`normalize_usage` negative token count** (`agent/usage_pricing.py` line 420): The formula `max(0, input_total - cache_read - cache_write)` correctly clamps to zero for malformed API responses where cached tokens exceed the total. Correct.

- **`redact_sensitive_text` double-redaction ordering** (`agent/redact.py`): `_PREFIX_RE` runs first and replaces known key prefixes. The `_ENV_ASSIGN_RE` then runs on already-redacted text. The value field is already replaced, so both patterns produce full redaction. Correct (though the ENV pattern becomes a no-op for known-prefix keys — this is harmless).

---

## Summary Table

| ID | File | Line | Severity | Description |
|---|---|---|---|---|
| BUG-1 | `hermes_state.py` | 238, 352 | Medium | Duplicate `close()` — WAL checkpoint silently dead |
| BUG-2 | `tools/fuzzy_match.py` | 315, 50 | High | `context_aware` + `replace_all=True` corrupts wrong code |
| BUG-3 | `tools/file_operations.py` | 621 | Low | `_suggest_similar_files` char-set heuristic returns irrelevant files |
| BUG-4 | `agent/smart_model_routing.py` | 66 | Low | Keyword set misses inflected forms; complex tasks routed to cheap model |
