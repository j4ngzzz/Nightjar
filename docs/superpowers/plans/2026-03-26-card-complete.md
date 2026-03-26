# CARD Complete Vision — Swarm #2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete CARD to 100% of the designed vision — immune system, self-evolution, network effect infrastructure, and all MVP gaps. After this swarm, CARD is a fully self-improving verification layer that gets safer with every production failure.

**What Swarm #1 Built:** Parser, 5-stage verification pipeline, retry loop, generation pipeline, CLI (8 commands), MCP server (3 tools), 159 tests passing.

**What This Swarm Builds:** Everything else from ARCHITECTURE.md that isn't built yet.

**Tech Stack (additions):** python-dotenv, CrossHair [REF-T09], icontract [REF-T10], MonkeyType [REF-T12], OpenTelemetry [REF-T15], DSPy, OpenDP [REF-T20], SQLite (stdlib), Rich (CLI output)

---

## BridgeSwarm Configuration: 10 Opus Agents

| # | Name | Role | Model | Scope |
|---|------|------|-------|-------|
| 1 | **Coord-Setup** | Coordinator | opus | .env loading, Dafny setup, config loader, oversees all |
| 2 | **Coord-Demo** | Coordinator | opus | Rich CLI output, demo script, README update, integration tests |
| 3 | **Scout-Immune** | Scout | opus | Fetch [REF-T12] MonkeyType, [REF-T13] Daikon algorithm, [REF-T09] CrossHair, [REF-T10] icontract, [REF-T15] OTel, [REF-P15] Agentic PBT |
| 4 | **Scout-Evolution** | Scout | opus | Fetch [REF-T26] DSPy SIMBA docs, [REF-T20] OpenDP docs. Note: [REF-T19] EvoAgentX patterns are informational reference for future evolution — NOT implemented in this swarm |
| 5 | **Builder-MVPCore** | Builder | opus | Config loader, Dafny detect, `ship`, `lock`, cache system, audit branch |
| 6 | **Builder-MVPAdvanced** | Builder | opus | Constitution inheritance, multi-module deps, Dafny compile targets |
| 7 | **Builder-ImmuneCollect** | Builder | opus | Daikon reimplementation (MIT), MonkeyType integration, OTel integration, trace storage |
| 8 | **Builder-ImmuneVerify** | Builder | opus | LLM enrichment, CrossHair verify, Hypothesis verify, auto-append to .card.md, icontract inject |
| 9 | **Builder-Evolution** | Builder | opus | Tracking DB, experience replay, DSPy SIMBA, hill climbing, network effect infra (abstraction + OpenDP + pattern library + herd immunity) |
| 10 | **Reviewer** | Reviewer | opus | Reviews ALL code against REFERENCES.md + ARCHITECTURE.md Section 6 |

### Permissions & MCP

**All agents: `--dangerously-skip-permissions` enabled.**

| MCP Tool | Coordinators | Scouts | Builders | Reviewer |
|----------|-------------|--------|----------|----------|
| `sequential-thinking` | Yes | Yes | Yes | Yes |
| `context7` | Yes | Yes | Yes | Yes |
| `github` | Yes | Yes | Yes | Yes |
| `WebSearch` | Yes | Yes | No | No |
| `WebFetch` | Yes | Yes | No | No |
| `bridgemind` | Yes | No | No | No |

**EXCLUDED:** brave, exa, coingecko, ccxt, duckdb

---

## GROUP A: Complete MVP Gaps

### Task A1: .env + Config Loader

**Agent:** Coord-Setup (Opus)
**Files:**
- Create: `src/contractd/config.py`
- Modify: `src/contractd/cli.py` (add config loading at startup)
- Test: `tests/unit/test_config.py`

**Required Reading:** `contractd.toml` schema from Swarm #1 plan

```python
# src/contractd/config.py — loads .env + contractd.toml
"""Configuration loader. Reads .env for API keys, contractd.toml for project settings."""
import os
from pathlib import Path
from dotenv import load_dotenv
import tomllib  # Python 3.11+

def load_config(project_root: str = ".") -> dict:
    """Load .env + contractd.toml. Returns merged config dict."""
    load_dotenv(Path(project_root) / ".env")
    toml_path = Path(project_root) / "contractd.toml"
    if toml_path.exists():
        with open(toml_path, "rb") as f:
            return tomllib.load(f)
    return {}

def get_model() -> str:
    """Get the LLM model from CARD_MODEL env var or config."""
    return os.environ.get("CARD_MODEL", "deepseek/deepseek-chat")
```

- [ ] Write failing tests for config loading
- [ ] Implement config.py
- [ ] Wire into cli.py (call load_config at CLI startup)
- [ ] Verify .env keys are accessible to litellm
- [ ] Commit: `feat: config loader — .env + contractd.toml [REF-T16]`

### Task A2: Dafny Binary Detection + Setup Helper

**Agent:** Coord-Setup (Opus)
**Files:**
- Create: `src/contractd/dafny_setup.py`
- Test: `tests/unit/test_dafny_setup.py`

```python
# Detect Dafny binary, print instructions if missing
def find_dafny() -> str | None:
    """Find Dafny binary on PATH or in known locations."""
    import shutil
    return shutil.which("dafny")

def ensure_dafny() -> str:
    """Find Dafny or raise with installation instructions."""
    path = find_dafny()
    if path:
        return path
    raise RuntimeError(
        "Dafny not found. Install from: https://github.com/dafny-lang/dafny/releases\n"
        "Add to PATH, or set DAFNY_PATH environment variable."
    )
```

- [ ] TDD cycle
- [ ] Commit: `feat: Dafny binary detection + setup helper [REF-T01]`

### Task A3: `contractd lock` — Sealed Manifest Generation

**Agent:** Builder-MVPCore (Opus)
**Required Reading:** [REF-C08] Sealed Dependency Manifest, [REF-P27] Slopsquatting, [REF-T05] uv docs
**Files:**
- Modify: `src/contractd/cli.py` (implement lock command body)
- Create: `src/contractd/lock.py`
- Test: `tests/unit/test_lock.py`

Core: scan project imports → resolve versions → compute SHA-256 hashes → write deps.lock

- [ ] TDD cycle
- [ ] Commit: `feat: contractd lock — sealed dependency manifest [REF-C08, REF-P27]`

### Task A4: `contractd ship` — Build + Sign Artifact

**Agent:** Builder-MVPCore (Opus)
**Files:**
- Modify: `src/contractd/cli.py`
- Create: `src/contractd/ship.py`
- Test: `tests/unit/test_ship.py`

Core: run build → hash the output artifact → write .card/verify.json with provenance (model used, timestamp, verification results, artifact hash)

- [ ] TDD cycle
- [ ] Commit: `feat: contractd ship — artifact signing with provenance`

### Task A5: Verification Cache System

**Agent:** Builder-MVPCore (Opus)
**Files:**
- Create: `src/contractd/cache.py`
- Test: `tests/unit/test_cache.py`

Core: SHA-256(spec_content + invariant_hashes) → check .card/cache/{hash}.json → if exists, skip verification. Invalidate on any spec change.

- [ ] TDD cycle
- [ ] Commit: `feat: verification cache — skip re-verification when spec unchanged`

### Task A6: Audit Branch System

**Agent:** Builder-MVPCore (Opus)
**Files:**
- Create: `src/contractd/audit.py`
- Test: `tests/unit/test_audit.py`

Core: after successful build, copy generated code to .card/audit/{module}.{target} as read-only. Git-trackable for compliance.

- [ ] TDD cycle
- [ ] Commit: `feat: audit branch — read-only generated code archive`

### Task A7: constitution.card.md Inheritance

**Agent:** Builder-MVPAdvanced (Opus)
**Required Reading:** ARCHITECTURE.md Section 2 (constitution pattern), [REF-T25] Spec Kit constitution
**Files:**
- Modify: `src/contractd/parser.py` (add constitution loading)
- Create: `tests/fixtures/constitution.card.md`
- Test: `tests/unit/test_constitution.py`

Core: if `.card/constitution.card.md` exists, merge its `global-invariants` into every module's invariant set during parsing. Constitution invariants inherit to all modules.

- [ ] TDD cycle
- [ ] Commit: `feat: constitution.card.md — project-level invariants inherited by all modules [REF-T25]`

### Task A8: Multi-Module Dependency Resolution

**Agent:** Builder-MVPAdvanced (Opus)
**Files:**
- Create: `src/contractd/resolver.py`
- Test: `tests/unit/test_resolver.py`

Core: scan `.card/*.card.md` → build dependency graph from `module.depends-on` → topological sort → verify/build in dependency order. Detect circular deps.

- [ ] TDD cycle
- [ ] Commit: `feat: multi-module dependency resolution with topological sort`

### Task A9: Dafny Compile to Target Languages

**Agent:** Builder-MVPAdvanced (Opus)
**Required Reading:** [REF-T01] Dafny docs — `dafny compile --target`
**Files:**
- Create: `src/contractd/compiler.py`
- Test: `tests/unit/test_compiler.py`

Core: after verification passes, run `dafny compile module.dfy --target {py|js|go|java|cs}` → output to dist/. Handle compilation errors.

- [ ] TDD cycle
- [ ] Commit: `feat: Dafny compile to Python/JS/Go/Java/C# [REF-T01]`

### Task A10: Integration Tests (Real LLM + Real Dafny)

**Agent:** Coord-Demo (Opus)
**Files:**
- Create: `tests/integration/test_end_to_end.py`
- Create: `tests/integration/test_generation_live.py`

Core: requires CARD_MODEL + API key + Dafny binary. Tests marked with `@pytest.mark.integration`. Full pipeline: .card.md → generate → verify → compile → output.

- [ ] Write integration test that calls real LLM
- [ ] Write integration test that runs real Dafny
- [ ] Write integration test for full contractd build
- [ ] Commit: `test: integration tests with real LLM + Dafny`

---

## GROUP B: Immune System Pipeline [ARCHITECTURE.md Section 6]

### Task B1: Daikon Algorithm Reimplementation (MIT License)

**Agent:** Builder-ImmuneCollect (Opus)
**Required Reading:** [REF-T13] Fuzzingbook DynamicInvariants — READ the algorithm, do NOT copy the code (CC-BY-NC-SA license). Reimplement under MIT.
**Files:**
- Create: `src/immune/daikon.py` (~300 lines)
- Test: `tests/unit/test_daikon.py`

Core: `InvariantMiner` class. Uses `sys.settrace` to hook function calls. Records variable values at entry/exit. Applies invariant templates: type checks (`isinstance`), value bounds (`x > 0`), relational (`x < y`), nullness (`x is not None`), length (`len(x) > 0`). Retains invariants that hold across ALL observed executions.

```python
# src/immune/daikon.py — MIT license reimplementation
"""Dynamic invariant mining. Reimplemented from Daikon algorithm (UW, 1999).
Reference implementation: [REF-T13] Fuzzingbook DynamicInvariants.
This code is MIT-licensed. Do NOT copy from Fuzzingbook (CC-BY-NC-SA)."""
```

- [ ] TDD: test that mining from 100 calls to `abs(x)` discovers `result >= 0`
- [ ] TDD: test that mining from `sorted(lst)` discovers `result is sorted`
- [ ] TDD: test that mining from `len(s)` discovers `result >= 0`
- [ ] Implement InvariantMiner with 10+ invariant templates
- [ ] Commit: `feat: Daikon algorithm reimplementation — MIT license [REF-T13 reference, REF-C05, REF-P18]`

### Task B2: MonkeyType Integration for Type Traces

**Agent:** Builder-ImmuneCollect (Opus)
**Required Reading:** [REF-T12] MonkeyType docs
**Files:**
- Create: `src/immune/collector.py`
- Test: `tests/unit/test_collector.py`

Core: wrap MonkeyType's `sys.setprofile` collector for CARD's immune system. Collect type signatures from runtime. Store in SQLite alongside value traces from Daikon.

- [ ] TDD cycle
- [ ] Commit: `feat: MonkeyType type trace collection [REF-T12]`

### Task B3: OpenTelemetry Integration for API Traces

**Agent:** Builder-ImmuneCollect (Opus)
**Required Reading:** [REF-T15] OpenTelemetry docs, [REF-P17] MINES paper
**Files:**
- Create: `src/immune/otel_collector.py`
- Test: `tests/unit/test_otel_collector.py`

Core: auto-instrument FastAPI/Flask/Django endpoints. Capture HTTP method, URL, status, request/response shapes. Store spans for MINES-style API invariant mining [REF-P17].

- [ ] TDD cycle
- [ ] Commit: `feat: OpenTelemetry API trace collection [REF-T15, REF-P17]`

### Task B3b: Sentry-Style Error Capture + Semantic Fingerprinting

**Agent:** Builder-ImmuneCollect (Opus)
**Required Reading:** ARCHITECTURE.md Section 6, Stage 1 (third signal: "Sentry-style error capture")
**Files:**
- Create: `src/immune/error_capture.py`
- Test: `tests/unit/test_error_capture.py`

Core: capture unhandled exceptions with: exception class, message template (PII stripped via regex), stack trace with function signatures, input type-shape at crash point. Semantic fingerprinting groups identical error classes across different stack paths (e.g., two `null.field` crashes on `UserRecord` are the same bug class regardless of call stack). This is the third collection mechanism alongside MonkeyType (types) and OTel (API spans).

- [ ] TDD: test fingerprinting groups semantically similar errors
- [ ] TDD: test PII stripping from error messages
- [ ] Implement error_capture.py
- [ ] Commit: `feat: Sentry-style error capture with semantic fingerprinting [ARCHITECTURE.md Section 6]`

### Task B4: Trace Storage (SQLite)

**Agent:** Builder-ImmuneCollect (Opus)
**Files:**
- Create: `src/immune/store.py`
- Test: `tests/unit/test_store.py`

Core: SQLite database for traces. Tables: `type_traces`, `value_traces`, `api_traces`, `invariant_candidates`, `verified_invariants`. Append-only for audit trail.

- [ ] TDD cycle
- [ ] Commit: `feat: immune system trace storage — SQLite`

### Task B5: LLM-Driven Invariant Enrichment

**Agent:** Builder-ImmuneVerify (Opus)
**Required Reading:** [REF-C06] LLM enrichment, [REF-P15] Agentic PBT, [REF-P14] NL2Contract
**Files:**
- Create: `src/immune/enricher.py`
- Test: `tests/unit/test_enricher.py`

Core: takes raw Daikon invariants + function signature + error trace → LLM generates Python assert statements → returns candidate invariants as structured objects.

```python
# Prompt pattern from [REF-P15] Agentic PBT:
ENRICHMENT_PROMPT = """
Function: {function_signature}
Observed invariants: {daikon_output}
Failing call: {error_trace}
Generate Python assert statements that would have caught this failure.
Format: assert <condition>, "<explanation>"
"""
```

- [ ] TDD cycle
- [ ] Commit: `feat: LLM-driven invariant enrichment [REF-C06, REF-P15]`

### Task B6: CrossHair Symbolic Verification of Candidates

**Agent:** Builder-ImmuneVerify (Opus)
**Required Reading:** [REF-T09] CrossHair docs
**Files:**
- Create: `src/immune/verifier_symbolic.py`
- Test: `tests/unit/test_verifier_symbolic.py`

Core: takes candidate invariant (Python assert) + function under test → CrossHair explores all execution paths → returns VERIFIED or COUNTEREXAMPLE.

- [ ] TDD cycle
- [ ] Commit: `feat: CrossHair symbolic verification of invariant candidates [REF-T09]`

### Task B7: Hypothesis PBT Verification of Candidates

**Agent:** Builder-ImmuneVerify (Opus)
**Required Reading:** [REF-T03] Hypothesis docs
**Files:**
- Create: `src/immune/verifier_pbt.py`
- Test: `tests/unit/test_verifier_pbt.py`

Core: takes candidate invariant → generates Hypothesis test with 1000+ random inputs → returns PASS (holds) or FAIL (counterexample found).

- [ ] TDD cycle
- [ ] Commit: `feat: Hypothesis PBT verification of invariant candidates [REF-T03]`

### Task B8: Auto-Append Verified Invariants to .card.md

**Agent:** Builder-ImmuneVerify (Opus)
**Files:**
- Create: `src/immune/spec_updater.py`
- Test: `tests/unit/test_spec_updater.py`

Core: takes verified invariant → reads .card.md → appends new entry to `invariants:` YAML block with auto-generated ID, `tier: property`, origin metadata (failure_id, timestamp, verification_method). Git-commits the change.

- [ ] TDD cycle
- [ ] Commit: `feat: auto-append verified invariants to .card.md [REF-C09]`

### Task B9: icontract Runtime Enforcement

**Agent:** Builder-ImmuneVerify (Opus)
**Required Reading:** [REF-T10] icontract docs
**Files:**
- Create: `src/immune/enforcer.py`
- Test: `tests/unit/test_enforcer.py`

Core: takes verified invariants → generates icontract `@require`/`@ensure` decorators → injects into generated code as runtime guards. These fire in production and feed back into the collection loop.

- [ ] TDD cycle
- [ ] Commit: `feat: icontract runtime enforcement of invariants [REF-T10]`

### Task B10: Immune System Orchestrator

**Agent:** Builder-ImmuneVerify (Opus)
**Files:**
- Create: `src/immune/pipeline.py`
- Test: `tests/unit/test_immune_pipeline.py`

Core: wires all immune components together. `run_immune_cycle(error_trace, function_context)` → collect → mine → enrich → verify → append → enforce. The full closed loop.

- [ ] TDD cycle
- [ ] Commit: `feat: immune system orchestrator — full closed loop [REF-C09, REF-C05, REF-P18]`

---

## GROUP C: Self-Evolution Pipeline

### Task C1: Verification Tracking Database

**Agent:** Builder-Evolution (Opus)
**Files:**
- Create: `src/contractd/tracking.py`
- Test: `tests/unit/test_tracking.py`

Core: SQLite database tracking every verification run. Schema: `runs(id, spec_id, model, timestamp, verified, stage_results_json, retry_count, total_cost)`. Compute rolling pass rate per model, per spec.

- [ ] TDD cycle
- [ ] Commit: `feat: verification tracking database`

### Task C2: Experience Replay Store

**Agent:** Builder-Evolution (Opus)
**Files:**
- Create: `src/contractd/replay.py`
- Test: `tests/unit/test_replay.py`

Core: when generation + verification succeeds, store the (spec, prompt, generated_code, verification_result) tuple. On future generation for similar specs, retrieve top-K successful examples as few-shot context. Uses embedding similarity (simple TF-IDF for MVP, upgradeable).

- [ ] TDD cycle
- [ ] Commit: `feat: experience replay — successful rationales as few-shot [REF-C06]`

### Task C3: DSPy SIMBA Prompt Optimization

**Agent:** Builder-Evolution (Opus)
**Required Reading:** DSPy docs at dspy.ai, SIMBA optimizer
**Files:**
- Create: `src/contractd/optimizer.py`
- Test: `tests/unit/test_optimizer.py`

Core: use DSPy SIMBA to optimize the Analyst/Formalizer/Coder prompts. Metric: verification pass rate on a held-out set of specs. Run optimization periodically (triggered by `contractd optimize` command or after N verification failures).

- [ ] TDD cycle
- [ ] Commit: `feat: DSPy SIMBA prompt optimization [REF-T26]`

### Task C4: AutoResearch Hill Climbing

**Agent:** Builder-Evolution (Opus)
**Files:**
- Create: `src/contractd/hill_climb.py`
- Test: `tests/unit/test_hill_climb.py`

Core: Karpathy's AutoResearch pattern. Each run: try ONE variation (prompt tweak, temperature change, different few-shot selection). Measure verification pass rate. Keep if improved, discard if not. Track in git.

- [ ] TDD cycle
- [ ] Commit: `feat: AutoResearch hill climbing for pipeline optimization`

### Task C5: Prompt Version Control

**Agent:** Builder-Evolution (Opus)
**Files:**
- Create: `src/contractd/prompts/` directory with versioned prompt templates
- Create: `src/contractd/prompts/analyst_v1.py`
- Create: `src/contractd/prompts/formalizer_v1.py`
- Create: `src/contractd/prompts/coder_v1.py`
- Test: `tests/unit/test_prompts.py`

Core: externalize all LLM prompts into versioned files. Each prompt has metadata (version, pass_rate, last_optimized). Generator loads latest best-performing version.

- [ ] TDD cycle
- [ ] Commit: `feat: versioned prompt templates with performance tracking`

---

## GROUP D: Network Effect Infrastructure

### Task D1: Structural Abstraction Layer

**Agent:** Builder-Evolution (Opus)
**Files:**
- Create: `src/immune/abstraction.py`
- Test: `tests/unit/test_abstraction.py`

Core: convert concrete failure traces into PII-free structural signatures. `User{email: null}` → `ObjectType{optional_field: null} → NullAccess in notification_path`. No field names, no values, no customer identifiers. Only type-level patterns.

- [ ] TDD cycle
- [ ] Commit: `feat: structural abstraction — PII-free failure signatures [REF-C10]`

### Task D2: OpenDP Differential Privacy Integration

**Agent:** Builder-Evolution (Opus)
**Required Reading:** [REF-T20] OpenDP docs
**Files:**
- Create: `src/immune/privacy.py`
- Test: `tests/unit/test_privacy.py`

Core: Laplace mechanism on invariant confidence counts. When aggregating "how many tenants hit this pattern," add DP noise. The invariant statement itself is NOT perturbed — only the frequency metadata.

- [ ] TDD cycle
- [ ] Commit: `feat: OpenDP differential privacy for cross-tenant sharing [REF-T20]`

### Task D3: Shared Invariant Pattern Library

**Agent:** Builder-Evolution (Opus)
**Files:**
- Create: `src/immune/pattern_library.py`
- Test: `tests/unit/test_pattern_library.py`

Core: append-only library of abstracted invariant patterns. Each entry: pattern_id, abstract_form, abstract_invariant, tenant_confidence (DP-protected), verification_method, proof_artifact_hash.

- [ ] TDD cycle
- [ ] Commit: `feat: shared invariant pattern library — append-only [REF-C09]`

### Task D4: Herd Immunity Threshold Logic

**Agent:** Builder-Evolution (Opus)
**Files:**
- Create: `src/immune/herd.py`
- Test: `tests/unit/test_herd.py`

Core: when pattern confidence > 0.95 across 50+ tenants (DP-protected count), promote to UNIVERSAL — applied to all new CARD builds regardless of whether that tenant experienced the failure.

- [ ] TDD cycle
- [ ] Commit: `feat: herd immunity threshold — universal invariants [REF-C10]`

---

## GROUP E: Polish + Demo

### Task E1: Rich CLI Output

**Agent:** Coord-Demo (Opus)
**Files:**
- Create: `src/contractd/display.py`
- Test: `tests/unit/test_display.py`

Core: use Rich library for colored output. Green "VERIFIED" badge, red "FAIL" with counterexample, progress bars for each stage, timing display, cost counter.

- [ ] Implement display.py with Rich formatting
- [ ] Wire into cli.py verify/build output
- [ ] Commit: `feat: Rich CLI output — colored badges, progress bars, timing`

### Task E2: Demo Script

**Agent:** Coord-Demo (Opus)
**Files:**
- Create: `demo/run_demo.sh`
- Create: `demo/run_demo.py`

Core: automated demo that shows:
1. `contractd init payment` → scaffold
2. `contractd build --target py` → generate + verify + compile
3. Show green VERIFIED output
4. Intentionally break an invariant → show FAIL
5. `CARD_MODEL=deepseek/deepseek-chat contractd build` → model swap, same verification
6. Print cost summary

- [ ] Create demo script
- [ ] Test manually
- [ ] Commit: `feat: automated demo script`

### Task E3: Updated README

**Agent:** Coord-Demo (Opus)
**Files:**
- Modify: `README.md`

Core: update with immune system section, self-evolution section, architecture diagram, full feature list, installation (including Dafny), demo instructions.

- [ ] Update README
- [ ] Commit: `docs: comprehensive README with full feature set`

### Task E4: `contractd explain` Implementation

**Agent:** Coord-Demo (Opus)
**Files:**
- Create: `src/contractd/explain.py`
- Test: `tests/unit/test_explain.py`

Core: read .card/verify.json → format last failure as human-readable explanation with: what failed, which invariant, counterexample, suggested fix.

- [ ] TDD cycle
- [ ] Commit: `feat: contractd explain — human-readable failure reports`

---

## Execution Order

```
PHASE 0 — SETUP (Coord-Setup)
  Task A1 (config) → Task A2 (Dafny detect)

PHASE 1 — RESEARCH (2 Scouts in parallel)
  Scout-Immune: fetch [REF-T12, T13, T15, T09, T10, P15, P17]
  Scout-Evolution: fetch [REF-T26] DSPy SIMBA docs, [REF-T20] OpenDP docs

PHASE 2 — BUILD (6 Builders in parallel after Scouts complete)
  Builder-MVPCore:      [A3 lock] [A4 ship] [A5 cache] [A6 audit]
  Builder-MVPAdvanced:  [A7 constitution] [A8 multi-module] [A9 Dafny compile]
  Builder-ImmuneCollect:[B1 Daikon] [B2 MonkeyType] [B3 OTel] [B3b ErrorCapture] [B4 store]
  Builder-ImmuneVerify: [B6 CrossHair] [B7 Hypothesis] ──wait for B1── [B5 LLM enrich] [B8 append] [B9 icontract] ──wait for ALL B1-B9── [B10 orchestrator]
  Builder-Evolution:    [C1 tracking] [C2 replay] [C3 DSPy] [C4 hill climb] [C5 prompts] [D1 abstract] [D2 OpenDP] [D3 library] [D4 herd]
  (Builder-Evolution has the most tasks — 9 items — but they're all in the self-improvement domain)

PHASE 3 — REVIEW (Reviewer, continuous)
  Review each builder's output as it completes

PHASE 4 — INTEGRATION (Coord-Demo)
  [A10 integration tests] [E1 Rich CLI] [E2 demo script] [E3 README] [E4 explain]
```

### File Ownership (HARD ENFORCED)

| Builder | Owns |
|---------|------|
| Coord-Setup | `src/contractd/config.py`, `src/contractd/dafny_setup.py`, **`src/contractd/cli.py`** (sole owner — all CLI modifications go through Coord-Setup or require Coord-Setup approval) |
| Builder-MVPCore | `src/contractd/lock.py`, `src/contractd/ship.py`, `src/contractd/cache.py`, `src/contractd/audit.py` |
| Builder-MVPAdvanced | `src/contractd/resolver.py`, `src/contractd/compiler.py`, modifications to `parser.py` (constitution only) |
| Builder-ImmuneCollect | `src/immune/daikon.py`, `src/immune/collector.py`, `src/immune/otel_collector.py`, `src/immune/error_capture.py`, `src/immune/store.py`, `src/immune/types.py` |
| Builder-ImmuneVerify | `src/immune/enricher.py`, `src/immune/verifier_symbolic.py`, `src/immune/verifier_pbt.py`, `src/immune/spec_updater.py`, `src/immune/enforcer.py`, `src/immune/pipeline.py` |
| Builder-Evolution | `src/contractd/tracking.py`, `src/contractd/replay.py`, `src/contractd/optimizer.py`, `src/contractd/hill_climb.py`, `src/contractd/prompts/*`, `src/immune/abstraction.py`, `src/immune/privacy.py`, `src/immune/pattern_library.py`, `src/immune/herd.py` |
| Coord-Demo | `src/contractd/display.py`, `src/contractd/explain.py`, `demo/*`, `README.md`, `tests/integration/*`, `tests/unit/test_display.py`, `tests/unit/test_explain.py` |
| Reviewer | No file ownership — reads all |

### Critical Rules

1. **Scouts MUST complete before Builders start.**
2. **Builders NEVER use WebSearch.** context7 + github MCP only.
3. **File ownership is HARD.** See table above.
4. **`src/contractd/types.py` changes require Coord-Setup approval.** This file was created in Swarm #1 and defines shared interfaces. If new types are needed for immune/evolution modules, add them to `src/immune/types.py` (new file, owned by Builder-ImmuneCollect) instead.
5. **All agents: `--dangerously-skip-permissions`.**
6. **[REF-T13] Fuzzingbook code MUST NOT be copied.** Reimplement the Daikon algorithm from the paper description. Check MIT license on output.
7. **Reviewer checks every submission against REFERENCES.md citations.**
8. **All new files must have reference citations in docstrings.**
9. **`cli.py` is owned by Coord-Setup.** Other builders create their logic modules (lock.py, ship.py, display.py) and Coord-Setup wires them into cli.py. Builders do NOT modify cli.py directly.
10. **B10 (immune orchestrator) MUST NOT start until B1-B9 are ALL complete.** It imports from all of them.
11. **B5 (LLM enricher) MUST NOT start until B1 (Daikon) is complete.** It takes Daikon output as input.

---

## Swarm Mission Brief

```
SWARM #2: Complete CARD to 100% vision.

Swarm #1 built the core: parser, 5-stage verification, retry loop,
generation pipeline, CLI, MCP server. 159 tests passing.

THIS SWARM builds everything else:

GROUP A (MVP Gaps): config loader, Dafny setup, contractd lock/ship,
  verification cache, audit branch, constitution inheritance,
  multi-module deps, Dafny compile to target languages, integration tests

GROUP B (Immune System): Daikon reimplementation (MIT), MonkeyType
  integration, OpenTelemetry traces, LLM invariant enrichment,
  CrossHair + Hypothesis verification, auto-append to .card.md,
  icontract runtime enforcement, immune orchestrator

GROUP C (Self-Evolution): tracking DB, experience replay, DSPy SIMBA
  prompt optimization, AutoResearch hill climbing, versioned prompts

GROUP D (Network Effect): structural abstraction, OpenDP differential
  privacy, shared pattern library, herd immunity threshold

GROUP E (Polish): Rich CLI output, demo script, README, explain command

MANDATORY: Read CLAUDE.md first. Fetch [REF-XXX] references BEFORE coding.
All code must cite references in docstrings. File ownership is HARD.
```

## Swarm Skills to Enable

Same as Swarm #1:
- Incremental Commits: ON
- Test-Driven: ON
- Code Review: ON
- Documentation: ON
- Security Audit: ON
- DRY Principle: ON
- Keep CI Green: ON
- All others: OFF

## Supporting Context (attach these files)

1. CLAUDE.md
2. docs/ARCHITECTURE.md
3. docs/REFERENCES.md (full file this time — immune system refs needed)
4. This plan document
