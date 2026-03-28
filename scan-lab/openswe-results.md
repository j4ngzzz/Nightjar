# open-swe Bug Scan Results

**Repository:** https://github.com/langchain-ai/open-swe
**Commit scanned:** depth-1 clone (latest master), 2026-03-28
**Method:** Static analysis + live Python execution + Hypothesis property-based testing
**Files scanned:** 55 Python files across `agent/`, `tests/`

---

## Summary

| ID | Severity | File | Description |
|----|----------|------|-------------|
| BUG-01 | HIGH | `agent/middleware/open_pr.py:87` | Safety-net middleware skips recovery when tool fails |
| BUG-02 | MEDIUM | `agent/utils/repo.py:30` | `extract_repo_from_text` returns repo name with embedded slash |
| BUG-03 | MEDIUM | `agent/utils/github.py:72` | `git checkout -B` force-resets existing branch on agent retry |
| BUG-04 | LOW | `agent/utils/repo.py:36-38` | GitHub URL with `.git` suffix produces invalid repo name |
| NOTE-01 | INFO | `agent/webapp.py:262` | Thread IDs generated from SHA-256 are not valid versioned UUIDs |

---

## BUG-01 — HIGH: Middleware safety net skips recovery on tool failure

**File:** `agent/middleware/open_pr.py`, line 87

**Code:**
```python
pr_payload = _extract_pr_params_from_messages(messages)

if not pr_payload:
    return None                          # tool was never called — correct

if "success" in pr_payload:             # BUG: also True when success=False!
    # Tool already handled commit/push/PR creation
    return None
```

**Root cause:** The `commit_and_open_pr` tool always returns a dict containing a `"success"` key, whether the operation succeeded or failed:

```python
# On failure the tool returns:
{"success": False, "error": "Git push failed: remote rejected", "pr_url": None}
```

The key `"success"` is present in both the success and failure payloads. The condition `"success" in pr_payload` evaluates to `True` in both cases, causing the middleware to unconditionally return `None` — abandoning the recovery attempt regardless of whether the tool actually succeeded.

**Correct fix:**
```python
if pr_payload.get("success"):   # only True when success=True
    return None
```

**Impact:** When `commit_and_open_pr` fails (push rejected, token expired, network error), the after-agent safety-net middleware that would retry the commit and PR creation silently does nothing. The agent ends the run without creating the PR and without any error escalation.

**Reproduced:**
```python
failed = {"success": False, "error": "Git push failed: remote rejected", "pr_url": None}
messages = [{"name": "commit_and_open_pr", "content": json.dumps(failed)}]
payload = _extract_pr_params_from_messages(messages)
assert "success" in payload        # True — BUG triggers, middleware returns None
assert not payload.get("success")  # True — correct check would catch this
```

---

## BUG-02 — MEDIUM: `extract_repo_from_text` returns repo name containing a slash

**File:** `agent/utils/repo.py`, line 30

**Code:**
```python
value = match.group(1).rstrip("/")
if "/" in value:
    owner, name = value.split("/", 1)   # maxsplit=1 — name can still contain "/"
```

**Root cause:** `str.split("/", 1)` with `maxsplit=1` splits only on the *first* slash. If the matched text contains multiple slashes (e.g. `repo:owner/name/extra`), the `name` portion retains the rest of the path: `"name/extra"`.

**Reproduced:**
```python
result = extract_repo_from_text("repo:owner/name/extra")
# Returns: {"owner": "owner", "name": "name/extra"}
```

**Hypothesis falsifier:**
`text = "repo:0/0/0"` → `{"owner": "0", "name": "0/0"}`

**Impact:** The malformed name propagates into:
- `git clone https://github.com/owner/name/extra.git` — GitHub rejects this URL with a 404
- GitHub API calls to `/repos/owner/name/extra` — HTTP 404 response
- All downstream git operations fail silently

**Fix:** Use `split("/")[0]` instead of `split("/", 1)[1]` for the name component, or reject inputs with more than one slash after the owner.

---

## BUG-03 — MEDIUM: `git checkout -B` force-resets existing branch on agent retry

**File:** `agent/utils/github.py`, line 72

**Code:**
```python
def git_checkout_branch(sandbox_backend, repo_dir, branch):
    safe_branch = shlex.quote(branch)
    checkout_result = _run_git(sandbox_backend, repo_dir, f"git checkout -B {safe_branch}")
    if checkout_result.exit_code == 0:
        return True
    # fallbacks only reached if -B fails (rare)
```

**Root cause:** `git checkout -B <branch>` is documented to "create or reset" the branch. If the branch already exists (e.g. from a previous agent run on the same `thread_id`), `-B` **force-resets** its tip to `HEAD` (the default branch), discarding all previous commits on that branch in the local sandbox.

**Scenario:**
1. Agent Run 1 on thread `abc123`: creates `open-swe/abc123`, commits work, pushes to remote.
2. Agent Run 2 (retry or interrupted run) on same thread `abc123`:
   - `git checkout -B open-swe/abc123` resets the local branch back to main's HEAD.
   - `git add -A && git commit` creates a new commit on top of the reset branch.
   - `git push origin open-swe/abc123` **fails** with "rejected — remote is ahead of local" because the remote still has Run 1's commits.
3. Due to **BUG-01**, the middleware does not attempt recovery.

**Fix:** Replace `git checkout -B` with a conditional: use `git checkout` if the branch already exists, `git checkout -b` only for new branches. The `else` path in `git_checkout_branch` already falls back to plain `git checkout`, but it's never reached because `-B` almost always exits 0.

---

## BUG-04 — LOW: GitHub URL with `.git` suffix produces invalid repo name

**File:** `agent/utils/repo.py`, line 36-38

**Code:**
```python
github_match = re.search(r"github\.com/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)", text)
if github_match:
    owner, name = github_match.group(1).split("/", 1)
```

**Root cause:** The regex character class `[a-zA-Z0-9_.-]` includes `.`, so `open-swe.git` matches in full. A URL like `https://github.com/langchain-ai/open-swe.git` produces:

```python
result = extract_repo_from_text("https://github.com/langchain-ai/open-swe.git")
# Returns: {"owner": "langchain-ai", "name": "open-swe.git"}
```

**Impact:**
- GitHub API call: `GET /repos/langchain-ai/open-swe.git` — HTTP 404
- `git clone` with the synthesized URL would attempt `open-swe.git.git`

**Fix:** Strip a trailing `.git` suffix from the extracted name:
```python
name = name.removesuffix(".git")
```

---

## NOTE-01 — INFO: Thread IDs are not valid versioned UUIDs

**File:** `agent/webapp.py`, lines 244-256

```python
def generate_thread_id_from_issue(issue_id: str) -> str:
    hash_bytes = hashlib.sha256(f"linear-issue:{issue_id}".encode()).hexdigest()
    return (
        f"{hash_bytes[:8]}-{hash_bytes[8:12]}-{hash_bytes[12:16]}-"
        f"{hash_bytes[16:20]}-{hash_bytes[20:32]}"
    )
```

These IDs have the correct `8-4-4-4-12` UUID hex format but do not set the version or variant bits. `uuid.UUID(tid).version` returns `None`. If LangGraph or any downstream system validates UUID version (v4 expected), these IDs will fail validation. LangGraph currently accepts arbitrary UUID-formatted strings, so this is latent rather than actively broken. The Slack variant (line 263) correctly uses `uuid.UUID(hex=md5_hex)` which produces a valid UUID object; the Linear/GitHub variants do not.

---

## Clean areas (no bugs found)

- `verify_github_signature`: correct constant-time comparison, correct empty-secret rejection
- `sanitize_github_comment_body`: idempotent, properly blocks tag injection
- `add_user_coauthor_trailer`: idempotent (does not double-add trailer)
- `get_recent_comments`: correct sorted-reverse logic, correct break-on-bot semantics
- `extract_image_urls` + `dedupe_urls`: correct deduplication, no duplicate URLs in output
- `_run_git` injection risk: low in practice because repo names are constrained by GitHub naming rules and the repo-extraction regex (`[a-zA-Z0-9_.\-/]+` excludes `;` and spaces)
- `_get_encryption_key`: raises `EncryptionKeyMissingError` if key unset rather than silently using weak fallback (a recent fix — old code derived from LANGSMITH_API_KEY)

---

## Test execution

```
23 passed, 2 failed (both failures due to missing langgraph_sdk in test env, not code bugs)
Hypothesis: 600+ examples, 1 falsifier found (BUG-02)
```
