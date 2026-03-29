---
name: nightjar-auto-verify
event: PostToolUse
description: Auto-verify Python files after AI writes them. Opt-in via NIGHTJAR_AUTO_VERIFY=1.
---

# nightjar-auto-verify Hook

This hook fires after any file-write tool completes. If the written file is a Python
file (`.py`) and the `NIGHTJAR_AUTO_VERIFY=1` environment variable is set, it checks
whether a matching `.card.md` spec exists in the `.card/` directory. If found, it
runs `nightjar verify --fast` against that spec and injects the result into the
conversation.

## Behavior

**Fires after:** `WriteFile`, `EditFile`, `CreateFile`, or any tool whose output
indicates a Python file was written or modified.

**Gate conditions (all must be true to trigger verification):**
1. `NIGHTJAR_AUTO_VERIFY=1` is set in the environment
2. The written file path ends in `.py`
3. A `.card/<module>.card.md` spec exists (where `<module>` is the stem of the
   written file, e.g. `payment.py` → `.card/payment.card.md`)

**If no spec exists:** The hook does nothing. It does not create specs automatically
(use `nightjar scan` or `nightjar init` for that).

**Verification command:**
```bash
nightjar verify --fast --spec .card/<module>.card.md --format=vscode
```

The `--format=vscode` flag produces structured JSON output that OpenClaw can parse
and annotate inline in the editor.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NIGHTJAR_AUTO_VERIFY` | Yes (opt-in gate) | Set to `1` to enable auto-verify |
| `NIGHTJAR_MODEL` | No | LLM model for `infer`/`retry` (not used in `--fast` mode) |

## Opt-In Rationale

Auto-verify is opt-in (not on by default) because:
- `nightjar verify --fast` takes 2–30 seconds depending on the spec complexity
- Not all Python files have specs; running on spec-less files would always no-op
  but adds overhead to every write
- Teams may prefer to run verification manually or in CI rather than on every save

To enable globally, add `NIGHTJAR_AUTO_VERIFY=1` to your shell profile or `.env`.
To enable for a single session:
```bash
export NIGHTJAR_AUTO_VERIFY=1
```

## Output Injection

When verification runs, the hook returns a structured result that OpenClaw injects
into the conversation as an assistant turn. The result includes:

- The verification stage summary (pass/fail per stage)
- The counterexample input if Stage 3 (PBT) fails
- A suggested fix if the failure is diagnosable
- The exit code for downstream processing

## Disabling Per-File

To skip auto-verify for a specific file, add a comment near the top of the file:
```python
# nightjar: skip
```

The hook checks for this marker before running verification.
