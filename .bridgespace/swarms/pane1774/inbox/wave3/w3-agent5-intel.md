# W3-5 Agent Report — Intelligence & Config Module Specs

**Agent:** W3-5
**Wave:** 3
**Pane:** 1774
**Date:** 2026-03-27

---

## Task Completed

Wrote `.card.md` specification files for 6 Nightjar intelligence and configuration modules. All 6 specs passed YAML validation with all required fields present and all invariants well-formed.

---

## Specs Written

| File | Module ID | Title | Invariants | Status |
|------|-----------|-------|-----------|--------|
| `.card/confidence.card.md` | `confidence` | Verification Confidence Score | 7 | PASS |
| `.card/impact.card.md` | `impact` | Offline Blast-Radius Analysis | 6 | PASS |
| `.card/optimizer.card.md` | `optimizer` | DSPy SIMBA Prompt Optimizer | 6 | PASS |
| `.card/replay.card.md` | `replay` | Experience Replay Store | 6 | PASS |
| `.card/tracking.card.md` | `tracking` | Verification Tracking Database | 6 | PASS |
| `.card/config.card.md` | `config` | Nightjar Configuration Loader | 5 | PASS |

**Total:** 6 specs, 36 invariants, 0 failures

---

## Key Invariants Per Module

### confidence
- Score is always clamped to [0, 100] via `max(0, min(100, total))`
- Only `VerifyStatus.PASS` stages earn points; FAIL/SKIP/TIMEOUT contribute 0
- `STAGE_POINTS` values sum to exactly 100 (15+10+35+20+20)
- Pipeline stage `schema` maps to the `crosshair` canonical tier (35pts)
- `compute_confidence` sets `result.trust_level` as a side effect

### impact
- `blast_radius` never includes `changed_file` in its own result
- Returns sorted list of absolute paths (deterministic output)
- `_extract_imports` catches `SyntaxError`/`OSError` and returns empty set — never raises
- Relative imports (level > 0) are excluded from the reverse graph
- BFS uses a visited set to terminate on circular import graphs

### optimizer
- `optimize()` raises `ValueError` when no template found for `target_prompt`
- `iterations_run <= max_iterations` always holds
- Improvement gate is strict: `candidate_score > best_score + threshold` (not >=)
- LLM failures inside `_call_llm_for_variation` are caught, iteration skipped via `continue`
- All LLM calls use `litellm.completion` with model from `NIGHTJAR_MODEL` env var

### replay
- `store_success` returns positive AUTOINCREMENT integer ID
- `retrieve_similar` returns at most k results, ordered by cosine similarity descending
- Empty database returns `[]` from `retrieve_similar`, never raises
- `cosine_similarity` returns 0.0 when either vector norm is zero (no ZeroDivisionError)
- JSON round-trip preserves `verification_result` dict structure

### tracking
- `record_run` returns positive AUTOINCREMENT integer ID
- `get_pass_rate` returns 0.0 when no runs (zero-division guard present)
- Pass rate values are in [0.0, 1.0]
- `verified` stored as INTEGER 0/1; deserialized as `bool` in `get_recent_runs`
- Table is append-only — no UPDATE or DELETE operations exist

### config
- `get_model` follows strict 4-level precedence: cli > env > config > hardcoded default
- `load_config` returns a copy of `DEFAULT_CONFIG` when no `nightjar.toml` exists
- `.env` file is loaded into `os.environ` before returning (side effect)
- `get_model` always returns a non-empty string (hardcoded fallback guarantees this)
- `_load_dotenv_simple` falls back to manual parsing when `python-dotenv` not installed

---

## Validation Results

All specs parsed successfully:
- YAML frontmatter valid on all 6 files
- All required fields present (`card-version`, `id`, `title`, `status`, `invariants`)
- All invariants have required fields (`id`, `tier`, `statement`, `rationale`)
- HTML validation report: `.bridgespace/swarms/pane1774/inbox/wave3/w3-agent5-validation.html`
- Screenshot: `.bridgespace/swarms/pane1774/inbox/wave3/w3-agent5-screenshot.png`

---

## Source Files Read

All invariants are grounded in the actual source code:
- `src/nightjar/confidence.py` — `STAGE_POINTS`, `_STAGE_NAME_MAP`, `compute_confidence`, `compute_trust_level`
- `src/nightjar/impact.py` — `blast_radius`, `build_import_graph`, `_extract_imports`, BFS loop
- `src/nightjar/optimizer.py` — `PromptOptimizer.optimize`, `_call_llm_for_variation`, improvement gate
- `src/nightjar/replay.py` — `ReplayStore.store_success`, `retrieve_similar`, `_cosine_similarity`
- `src/nightjar/tracking.py` — `TrackingDB.record_run`, `get_pass_rate`, schema definition
- `src/nightjar/config.py` — `load_config`, `get_model`, `_load_dotenv_simple`
