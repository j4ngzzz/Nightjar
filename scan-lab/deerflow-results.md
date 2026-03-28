# DeerFlow Code Scan Results

**Repo:** `bytedance/deer-flow` (depth-1 clone, commit at scan time)
**Scan date:** 2026-03-28
**Scanned by:** Nightjar CODE SCANNER agent (claude-sonnet-4-6)
**Method:** Static analysis + live Python execution of invariants

---

## Summary

Five real bugs were found. None are exploitable for RCE or auth bypass. The most impactful is a potential deadlock under concurrent load (Bug 1). Three bugs relate to the memory system's regex-based upload scrubbing (Bugs 2 & 3) and one to a silent false positive in a tool (Bug 4).

---

## BUG 1 — MCP Cache Deadlock on Concurrent Initialization

**Severity:** MEDIUM-HIGH
**File:** `backend/packages/harness/deerflow/mcp/cache.py`, line 13
**Status:** Not tested in existing test suite

### Description

`_initialization_lock` is an `asyncio.Lock()` created at **module import time**, outside any event loop:

```python
_initialization_lock = asyncio.Lock()   # line 13
```

`get_cached_mcp_tools()` is a synchronous function that, when the cache is cold, runs `asyncio.run(initialize_mcp_tools())` inside a `ThreadPoolExecutor` worker (the `loop.is_running()` branch). Two concurrent requests both seeing `_cache_initialized = False` will each spin up their own `asyncio.run()` call in separate worker threads, each creating an independent event loop. The `asyncio.Lock` is not shared across these independent event loops — the second thread deadlocks indefinitely trying to acquire a lock that belongs to the first thread's completed event loop.

### Reproduction

```python
import asyncio, threading, time

_initialization_lock = asyncio.Lock()   # module-level, as in cache.py
results = []

def worker(name):
    async def initialize():
        async with asyncio.timeout(1.0):
            async with _initialization_lock:
                results.append(f'{name}: ACQUIRED')
                await asyncio.sleep(0.05)
    asyncio.run(initialize())

t1 = threading.Thread(target=worker, args=('T1',))
t2 = threading.Thread(target=worker, args=('T2',))
t1.start(); t2.start()
t1.join(3); t2.join(3)
print(results)
# Observed: ['T2: ACQUIRED', 'T2: released'] — T1 times out (deadlocks)
```

### Impact

On the first pair of concurrent requests after startup (or after a cache reset), one request will hang waiting for MCP tool initialization that never completes. LangGraph's request timeout will eventually surface this as a 5xx error, but the deadlocked thread leaks from the pool.

### Fix

Replace `asyncio.Lock()` with `threading.Lock()` as the outer initialization guard, keeping `asyncio.Lock` only for use within a single event loop:

```python
import threading
_init_threading_lock = threading.Lock()

def get_cached_mcp_tools() -> list[BaseTool]:
    global _cache_initialized
    if _is_cache_stale():
        reset_mcp_tools_cache()
    if not _cache_initialized:
        with _init_threading_lock:
            if not _cache_initialized:   # double-checked locking
                # ... run initialization ...
    return _mcp_tools_cache or []
```

---

## BUG 2 — `_UPLOAD_SENTENCE_RE` Word-Boundary Mismatch: `/mnt/` Paths Never Stripped

**Severity:** MEDIUM
**File:** `backend/packages/harness/deerflow/agents/memory/updater.py`, lines 70–77
**Status:** Not tested in existing test suite

### Description

The regex is intended to strip sentences that reference session-scoped upload paths from long-term memory, to prevent the agent searching for non-existent files in future sessions. One of its alternation branches is:

```python
_UPLOAD_SENTENCE_RE = re.compile(
    r"[^.!?]*\b(?:"
    r"upload(?:ed|ing)?(?:\s+\w+){0,3}\s+(?:file|files?|...)"
    r"|/mnt/user-data/uploads/"        # ← this branch
    r"|<uploaded_files>"
    r")[^.!?]*[.!?]?\s*",
    re.IGNORECASE,
)
```

The `\b` word-boundary assertion immediately precedes `/mnt/user-data/uploads/`. A `\b` fires only at a word↔non-word character transition. A forward slash `/` is a non-word character. In all realistic contexts the path is preceded by a space or colon (both non-word), so `\b` never fires and the `/mnt/` branch **never matches**.

### Reproduction

```python
import re
_UPLOAD_SENTENCE_RE = re.compile(...)   # as in source

# Typical format written by MemoryUpdater from LLM output:
test = "The user accessed a file at /mnt/user-data/uploads/report.pdf."
print(bool(_UPLOAD_SENTENCE_RE.search(test)))   # False — not stripped
test2 = "Path: /mnt/user-data/uploads/data.csv"
print(bool(_UPLOAD_SENTENCE_RE.search(test2)))  # False — not stripped
```

### Impact

LLM summaries that mention the upload path (e.g., "User analyzed /mnt/user-data/uploads/report.pdf") are not stripped before being saved to `memory.json`. In future sessions the agent sees these path references, tries to access the files, and produces confusing "file not found" errors.

### Fix

Remove the `\b` before the path alternation (slashes are already unambiguous delimiters):

```python
r"[^.!?]*(?:\b(?:upload(?:ed|ing)?...) | /mnt/user-data/uploads/ | ...)"
```

Or replace the branch with a non-`\b`-anchored match:
```python
r"/mnt/user-data/uploads/[^\s]*"
```

---

## BUG 3 — `_UPLOAD_SENTENCE_RE` Leaves Text Fragments When Filenames Contain Periods

**Severity:** LOW-MEDIUM
**File:** `backend/packages/harness/deerflow/agents/memory/updater.py`, lines 70–77
**Status:** Not tested in existing test suite

### Description

The `[^.!?]*` quantifiers in the regex stop at any period character, including the period in a file extension (`.pdf`, `.csv`, `.xlsx`). When the LLM summary mentions a file with an extension and the upload keyword precedes it, the match stops at the dot of the extension, leaving a fragment in the output.

### Reproduction

```python
import re
_UPLOAD_SENTENCE_RE = re.compile(...)   # as in source

text = "The user uploaded a file called report.pdf. They asked about Python."
result = _UPLOAD_SENTENCE_RE.sub("", text).strip()
print(repr(result))
# Output: 'pdf. They asked about Python.'  ← garbled fragment

text2 = "User uploaded file.csv and file2.json for analysis. The analysis was detailed."
result2 = _UPLOAD_SENTENCE_RE.sub("", text2).strip()
print(repr(result2))
# Output: 'csv and file2.json for analysis. The analysis was detailed.'
```

### Impact

Long-term memory accumulates garbled sentence fragments like `"pdf. They asked about Python."` — these can confuse the LLM when injected as context in future sessions, degrading response quality.

### Fix

Use a more complete sentence-splitter approach or widen the post-match quantifier to include word characters after a dot (file extensions):

```python
# Match through file extensions: allow \w after a . if not followed by space
r"[^.!?]*[.!?]?\s*"  →  r"[^!?]*(?:[.!?](?!\s))*[^!?]*[!?]?\s*"
```

Or use a simpler approach: strip the entire sentence when an upload keyword appears in it, using `re.split` on sentence boundaries first.

---

## BUG 4 — `str_replace_tool` Returns `OK` for Empty Files Without Checking `old_str`

**Severity:** LOW
**File:** `backend/packages/harness/deerflow/sandbox/tools.py`, line 879
**Status:** Not covered by existing tests

### Description

```python
content = sandbox.read_file(path)
if not content:
    return "OK"            # ← returns success even when old_str is non-empty
if old_str not in content:
    return f"Error: String to replace not found in file: {requested_path}"
```

When a file is empty, `str_replace_tool` immediately returns `"OK"` regardless of what `old_str` was. The documented contract says: "the substring to replace must appear **exactly once** in the file." For an empty file, this contract is violated silently.

### Impact

The agent requests `str_replace(path=empty_file, old_str="def main():", new_str="def main(args):")` and receives `OK`. It then believes the replacement succeeded and proceeds without error. The file remains empty. The bug is discovered later (if at all) when the file's content is needed.

### Fix

```python
content = sandbox.read_file(path)
if old_str not in (content or ""):
    return f"Error: String to replace not found in file: {requested_path}"
```

Remove the early `if not content: return "OK"` special case; the existing `if old_str not in content` already handles the empty-content case correctly when `old_str` is non-empty (and `"" not in ""` is `False`, so empty-old_str on empty-file would still succeed, which is correct).

---

## BUG 5 — `UploadsMiddleware` Destroys Non-Text Content Blocks in Multi-Modal Messages

**Severity:** LOW
**File:** `backend/packages/harness/deerflow/agents/middlewares/uploads_middleware.py`, lines 181–196
**Status:** Not covered by existing tests

### Description

When the last human message has list-type content (the LangChain format for multi-modal messages containing both text and images), `UploadsMiddleware` only extracts text blocks and discards everything else:

```python
elif isinstance(last_message.content, list):
    text_parts = []
    for block in last_message.content:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))   # ← only text blocks
    original_content = "\n".join(text_parts)           # ← images discarded

updated_message = HumanMessage(
    content=f"{files_message}\n\n{original_content}",  # ← string, not list
    ...
)
```

### Impact

If a user uploads a file AND includes an inline image in the same message (a natural workflow for vision-capable models like Claude Sonnet), the image is silently discarded. The agent receives the file upload context and the text query but never sees the image. This is most likely to occur with vision-enabled models.

### Fix

Prepend the `<uploaded_files>` block to the content list rather than flattening to a string:

```python
if isinstance(last_message.content, list):
    new_content = [{"type": "text", "text": files_message}] + list(last_message.content)
else:
    new_content = f"{files_message}\n\n{last_message.content}"
```

---

## Areas That Appear Correct

- **LoopDetectionMiddleware**: Thread-safe LRU tracking with correct warn/hard-stop logic. The `md5` hash is order-independent as intended.
- **DanglingToolCallMiddleware**: Correctly patches message history without duplication.
- **SubagentExecutor task lifecycle**: The `_background_tasks` dict mutations use the lock correctly. The apparent race on `result_holder` after `TIMED_OUT` is harmless because `task_tool` has already called `cleanup_background_task` and the execution thread only updates an object that's been removed from the dict.
- **MemoryUpdateQueue debounce**: The `_processing` flag and timer-reset logic are correct; concurrent callers are serialized correctly via the threading lock.
- **Skill installer security**: Zip bomb defense, path traversal checks, symlink rejection, and `is_relative_to` confirmation all implemented correctly.
- **Path traversal in sandbox tools**: `_reject_path_traversal` + `_validate_resolved_user_data_path` provide defense-in-depth.
- **make_lead_agent model resolution**: Short-circuit evaluation and fallback chain handle all edge cases correctly.
