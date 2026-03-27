# W3-2 Report — CLI & User Interface Specs

**Agent**: W3-2
**Date**: 2026-03-27
**Wave**: 3

## Summary

All 6 `.card.md` specs written and validated. Every spec was derived from reading the actual source code — no aspirational invariants.

## Specs Produced

| Module ID | File | Invariants | Status |
|-----------|------|-----------|--------|
| cli | `.card/cli.card.md` | 7 | OK |
| display | `.card/display.card.md` | 7 | OK |
| tui | `.card/tui.card.md` | 5 | OK |
| explain | `.card/explain.card.md` | 6 | OK |
| watch | `.card/watch.card.md` | 6 | OK |
| mcp-server | `.card/mcp-server.card.md` | 6 | OK |

**Total**: 37 invariants across 6 modules. All parsed with `nightjar.parser.parse_card_spec`.

## Key Findings Per Module

**cli**: 12 subcommands under a Click group. Exit codes 0–5 as named constants. Model resolution chain: `--model` flag > `NIGHTJAR_MODEL` env > config > default. `init` refuses to overwrite existing specs. `retry` exits 5 (not 1) on exhaustion to signal human escalation. `build --target` uses `click.Choice` constrained to `{py, js, ts, go, java, cs}`.

**display**: `DisplayCallback` is a `@runtime_checkable` Protocol with 3 hooks. `NullDisplay` is a true no-op (safe for tests/`--quiet`). `RichStreamingDisplay` always renders 5 stage rows even before stages start. Duration formatting: `< 1000ms → "Xms"`, `>= 1000ms → "X.XXs"`. Full plain-text fallback when Rich is absent.

**tui**: `NightjarTUI` is a Textual `App` implementing `DisplayCallback` via `post_message` (thread-safe). `compose()` yields exactly `Header + 5×StagePanel + ProgressBar + Static banner + Footer`. `StagePanel.render()` uses fixed-width format `"{icon} Stage {N}: {name:<16} {dur:<12} {status}"`. Confidence bar updates only when `result.confidence` is not None (guarded try/except).

**explain**: `explain_failure` returns `ExplainOutput(failed_stage=-1)` on passing reports. `load_report` silently returns `None` on any I/O or JSON error (two search paths: spec dir, then `.card/`). `explain_with_llm` never raises — falls back to `suggested_fix` on any LLM exception. Model from `NIGHTJAR_MODEL` env var only.

**watch**: `DEBOUNCE_SECONDS = 0.5` (Dafny LSP pattern from Scout 5 F2). `CardChangeHandler` filters to `.card.md` files only, ignores directory events. Tiers run 0→1→2→3 with short-circuit on first failure. Tiers 2 and 3 emit `status='skip'` when no generated code found in audit dir.

**mcp-server**: Exactly 3 tools registered: `verify_contract`, `get_violations`, `suggest_fix`. `verify_contract` response always contains `{verified, stages, errors, duration_ms, retry_count}`. `get_violations` returns `{"violations": []}` for unknown paths. `suggest_fix` returns `{"error": ...}` for invalid `violation_id`. In-memory stores persist violations between calls within a session.

## Validation

```
cli: 7 invariants OK
display: 7 invariants OK
tui: 5 invariants OK
explain: 6 invariants OK
watch: 6 invariants OK
mcp-server: 6 invariants OK
```

Screenshot: `.card/w3-cli-results.html`
