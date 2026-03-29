# Nightjar Architecture

> **Contract-Anchored Regenerative Development**
>
> Every section in this document cites specific entries from [REFERENCES.md](./REFERENCES.md).

---

## 1. System Overview

Nightjar is a verification layer for AI-generated code. Developers write specs. AI generates code. Nightjar verifies the code satisfies the specs mathematically. Code is regenerated from scratch on every build — it is never manually edited.

The system has 5 layers executed in sequence:

```
LAYER 1: SPEC (.card.md file)
  Developer writes: intent + contracts + invariants + tests
  Format: YAML frontmatter + Markdown body [REF-T24]
         ↓
LAYER 2: GENERATION (LLM via litellm)
  Analyst → Formalizer → Coder pipeline [REF-C03, REF-P07]
  LLM generates Dafny code from spec [REF-C04, REF-P12]
         ↓
LAYER 3: VERIFICATION (6-stage pipeline with Phase 2 extensions)
  Stage 0: Pre-flight (AST parse)
  Stage 1: Dependency check (sealed manifest) [REF-C08, REF-P27]
  Stage 2: Schema validation (Pydantic) [REF-T08]
  Stage 3: Property-based testing (Hypothesis) [REF-T03, REF-P10]
  Stage 2.5: Negation-proof spec validation [REF-NEW-07]
  Stage 4: Formal verification — complexity-routed [REF-T01, REF-P02]
           CrossHair (simple) or Dafny (complex) per SafePilot [REF-NEW-08]
  Retry loop on failure — CEGIS counterexample-guided [REF-C02, REF-P03, REF-P06]
         ↓
LAYER 4: OUTPUT
  Dafny compiles to target language (Python/JS/Go/Java/C#) [REF-T01]
  Binary/artifact shipped
  Code committed to read-only audit branch (never edited)
         ↓
LAYER 5: IMMUNE SYSTEM
  Production monitoring → invariant mining → verification → spec update
  Wonda quality scoring [REF-NEW-05]
  Test oracle lifting [REF-NEW-06]
  Adversarial debate validation [REF-NEW-10]
  Temporal fact supersession with exponential decay
  [REF-C09, REF-T12, REF-T13, REF-T09, REF-T10]
```

### Core Architectural Principle

**"Don't Round-Trip"** [REF-C07, REF-P29]

Generated code is NEVER manually edited. All changes go through the `.card.md` spec. This is enforced architecturally, not by convention. The round-trip engineering death spiral that killed MDD [REF-P30] is structurally impossible in Nightjar.

---

## 2. The `.card.md` Format Specification

**Based on:** [REF-T24] Agent Skills Open Standard (YAML frontmatter + Markdown body)
**Acceptance criteria from:** [REF-T25] GitHub Spec Kit (Given/When/Then, FR-NNN, NEEDS CLARIFICATION markers)
**Novel contribution:** [REF-C01] Tiered invariants (example/property/formal)

### File Location

```
.card/
├── constitution.card.md     # Project-level invariants [REF-T25 constitution pattern]
├── auth.card.md             # Module spec
├── payment.card.md          # Module spec
└── user-profile.card.md     # Module spec
```

### Format Structure

```yaml
---
# ── Nightjar Spec Frontmatter ──────────────────────────────
card-version: "1.0"
id: module-name
title: Human-Readable Module Title
status: draft | review | approved | frozen

# ── Module Boundary ────────────────────────────────────────
module:
  owns: [function_a(), function_b(), EntityX, EntityY]
  depends-on:
    - other-module: "approved"     # internal Nightjar module
    - external-service: "^3.x"    # external dependency
  excludes:
    - "feature explicitly out of scope"

# ── Interface Contract ─────────────────────────────────────
contract:
  inputs:
    - name: param_name
      type: integer
      constraints: "param_name > 0 AND param_name <= 1_000_000"
  outputs:
    - name: ResultType
      type: object
      schema:
        field_a: string
        field_b: integer
  errors:
    - SpecificError
  events-emitted:
    - event.name

# ── Invariants (Tiered) [REF-C01] ─────────────────────────
# tier: 'example' → unit test only
# tier: 'property' → Hypothesis/fast-check PBT auto-generated [REF-T03]
# tier: 'formal' → Dafny mathematical proof required [REF-T01]
invariants:
  - id: INV-001
    tier: property
    statement: "Natural language description of what must always be true"
    rationale: "Why this matters"

  - id: INV-002
    tier: formal
    statement: "Critical safety property requiring mathematical proof"
    rationale: "Business/safety justification"

# ── Nonfunctional Constraints ──────────────────────────────
constraints:
  performance: "p95 latency < 2000ms"
  security: "compliance requirement"
  idempotency: "retry safety description"
---

## Intent

Natural language description of what this module does and why it exists.

## Acceptance Criteria

### Story 1 — Description (Priority)

**As a** persona, **I want** capability, **so that** benefit.

1. **Given** precondition, **When** action, **Then** expected outcome
2. **Given** precondition, **When** action, **Then** expected outcome

### Edge Cases

- What happens when X? → Expected behavior
- What happens when Y? → Expected behavior
- [NEEDS CLARIFICATION: What about Z?]

## Functional Requirements

- **FR-001**: System MUST do X
- **FR-002**: System SHOULD do Y
- **FR-003**: System MAY do Z
```

### Minimum Viable `.card.md` (~30 lines)

A developer writes this in 5 minutes:

```yaml
---
card-version: "1.0"
id: user-auth
title: User Authentication
status: draft
module:
  owns: [login(), logout(), validate_token()]
  depends-on: [postgres, bcrypt]
contract:
  inputs:
    - name: email
      type: string
    - name: password
      type: string
  outputs:
    - name: session_token
      type: string
invariants:
  - id: INV-001
    tier: property
    statement: "A valid token always corresponds to exactly one active user session"
---

## Intent
Let users log in with email/password and get a session token.

## Acceptance Criteria

### Story 1 — Login (P1)
1. **Given** valid credentials, **When** login() is called, **Then** a JWT is returned
2. **Given** invalid password, **When** login() is called, **Then** AuthError is raised
```

### Tier Escalation Path

The same `.card.md` file serves different rigor levels:

| Tier | Who writes it | What it generates | Tool |
|------|--------------|-------------------|------|
| `example` | Vibecoder | Unit tests from Given/When/Then | pytest |
| `property` | Senior dev | Property-based tests auto-generated from invariant statement | Hypothesis [REF-T03] |
| `formal` | Security/finance | Dafny mathematical proof | Dafny CLI [REF-T01] |

---

## 3. Verification Pipeline

**Pattern:** Cheapest/fastest stages first, short-circuit on failure [REF-P06]

```
┌─────────────────────────────────────────────────────────┐
│ STAGE 0: PRE-FLIGHT  [~0.5s, $0.00]                    │
│ • Python AST well-formedness check                      │
│ • .card.md YAML schema self-validation                  │
│ SHORT-CIRCUIT: malformed → FAIL                         │
├─────────────────────────────────────────────────────────┤
│ STAGE 1: DEPENDENCY CHECK  [~1-2s, $0.00]  [REF-C08]   │
│ • Compare imports against deps.lock allowlist           │
│ • uv pip sync --require-hashes --dry-run [REF-T05]     │
│ • pip-audit CVE scan [REF-T06]                          │
│ SHORT-CIRCUIT: unknown package or CVE → FAIL            │
├─────────────────────────────────────────────────────────┤
│ STAGE 2: SCHEMA VALIDATION  [~0.5-1s, $0.00]           │
│ • Pydantic v2 model parse [REF-T08]              ─┐    │
│ • OpenAPI contract validation                     │par  │
├───────────────────────────────────────────────────┤     │
│ STAGE 3: PROPERTY-BASED TESTING  [~3-8s, $0.00]  │     │
│ • Hypothesis: max_examples=200, derandomize=True  ─┘    │
│ • Properties auto-generated from invariants [REF-P10]   │
│ SHORT-CIRCUIT: property violation → FAIL + counterex    │
├─────────────────────────────────────────────────────────┤
│ STAGE 2.5: NEGATION-PROOF VALIDATION  [~2-5s, $0.00]   │
│ • Negate postconditions of FORMAL invariants [REF-NEW-07]│
│ • CrossHair checks negated spec — trivially true? FAIL  │
│ • Guards against degenerate/vacuously-true invariants   │
│ SKIP: no FORMAL invariants present                      │
│ SHORT-CIRCUIT: weak spec detected → FAIL                │
├─────────────────────────────────────────────────────────┤
│ STAGE 4: FORMAL VERIFICATION  [~5-20s, $0.00]          │
│ Complexity-discriminated routing [REF-NEW-08]:          │
│  complexity ≤ 5 → CrossHair symbolic [REF-T09]         │
│  complexity > 5 → Dafny [REF-T01]                      │
│   --verification-time-limit 15                          │
│   --isolate-assertions                                  │
│   --boogie /vcsCores:4                                  │
│ • Only for invariants with tier: formal                 │
│ SHORT-CIRCUIT: proof failure → FAIL + error context     │
└─────────────────────────────────────────────────────────┘
         │
    ALL PASS → Ship artifact
    ANY FAIL → CEGIS Retry Loop [Section 4]
```

### Stage 2+3 Parallelization

Stages 2 and 3 have no dependency and run in parallel:

```python
async def verify_pipeline(module_path, contract_path):
    await run_stage(0, preflight_check)        # sequential
    await run_stage(1, dependency_check)        # sequential
    schema_result, pbt_result = await asyncio.gather(
        run_stage(2, schema_validation),        # parallel
        run_stage(3, property_based_tests)      # parallel
    )
    if not (schema_result.ok and pbt_result.ok):
        return FAIL(schema_result, pbt_result)
    neg_result = await run_stage(2.5, negation_proof)  # sequential gate
    if not neg_result.ok:
        return FAIL(neg_result)
    return await run_stage(4, formal_verification)  # sequential (heaviest)
```

### Complexity-Discriminated Routing (SafePilot)

Stage 4 routes code based on cyclomatic complexity and AST depth, per SafePilot [REF-NEW-08]:

```
complexity score = cyclomatic_complexity + floor(ast_depth / 3)

score ≤ 5 → CrossHair symbolic execution (~13s avg, saves ~70% wall-time)
score > 5 → Full Dafny formal verification
```

Syntax errors route to Dafny for safety (unknown complexity = assume worst case).

### Graceful Degradation Ladder

When Dafny times out or is unavailable, the pipeline falls back gracefully:

```
1. Dafny verification (primary, complex functions)
2. CrossHair symbolic (timeout/unavailable fallback, ~80% coverage)
3. Hypothesis extended (10K+ examples, final fallback)
4. Confidence-scored partial result (never blocks the user)
```

### Cost Summary

| Stage | Latency | Cost | Tool |
|-------|---------|------|------|
| 0: Pre-flight | ~0.5s | $0.000 | Python AST |
| 1: Dep check | ~1-2s | $0.000 | uv + pip-audit [REF-T05, REF-T06] |
| 2: Schema | ~0.5-1s | $0.000 | Pydantic [REF-T08] |
| 3: PBT | ~3-8s | $0.000 | Hypothesis [REF-T03] |
| 2.5: Negation-proof | ~2-5s | $0.000 | CrossHair [REF-T09] |
| 4: Formal (simple) | ~5-13s | $0.000 | CrossHair [REF-T09] |
| 4: Formal (complex) | ~5-20s | $0.000 | Dafny [REF-T01] |
| **Total (0 retries)** | **~12-49s** | **~$0.001** | |
| Per retry (LLM call) | ~3-8s | ~$0.01-0.03 | litellm [REF-T16] |
| **Total (3 retries)** | **~30-65s** | **~$0.03-0.10** | |

---

## 4. The Retry Loop

**Pattern:** [REF-C02] Closed-Loop Verification (Clover Pattern) [REF-P03]
**Error format:** [REF-P06] DafnyPro structured errors
**Counterexample guidance:** [REF-NEW-02] CEGIS (Counterexample-Guided Inductive Synthesis)
**Success rate:** 86% pass@10 with Claude 3.5 Sonnet [REF-P06]

Phase 2 extended the retry loop with CEGIS: counterexamples from Stage 3 (PBT) and Stage 4 (formal) are parsed into structured repair prompts that guide the LLM toward the specific invariant violation.

```
On FAIL from any stage:

1. COLLECT FAILURE CONTEXT
   Stage 1 fail → disallowed packages + lock diff
   Stage 2 fail → schema diff (Pydantic error trace)
   Stage 2.5 fail → weak spec identification + negated invariant text
   Stage 3 fail → counterexample (input, output, property text) [CEGIS]
   Stage 4 fail → Dafny error lines + assertion batch ID + resource units
                  OR CrossHair counterexample trace

2. BUILD REPAIR PROMPT (CEGIS-guided)
   System: original .card.md spec
   User: failed code + structured error block + counterexample + prior failed attempts

3. CALL LLM (via litellm [REF-T16])
   Temperature: 0.2 (deterministic repair)
   Max tokens: 2048 output

4. RE-RUN FULL PIPELINE from Stage 0

5. RETRY CAP: N=5 → if still failing, ESCALATE to human
   LP dual root-cause diagnosis provided to human [Section 10]
```

### Spec Rewriting (Pre-Retry)

Before regenerating code, the Proven rewrite rules [REF-NEW-01] are applied to the spec itself:

- 5 rule groups covering 19 normalization patterns transform ambiguous or underspecified invariants
- `spec_rewriter.py` runs as a pre-processing step before each generation attempt
- Catches common spec patterns that lead to Dafny proof failures

### Structured Error Format (for LLM repair prompt)

```yaml
# repair_context.yml — from [REF-P06] DafnyPro design
attempt: 3
prior_attempts: [attempt_1.dfy, attempt_2.dfy]
failing_stage: dafny_formal
errors:
  - file: module.dfy
    line: 47
    message: "postcondition might not hold"
    assertion_batch: "method_sort_postcondition"
    resource_units: 8420
    type: postcondition_failure
counterexample:
  input: {arr: [3, 1, 2]}
  expected_property: "sorted(output) AND multiset(output)==multiset(input)"
```

---

## 5. Code Generation Pipeline

**Architecture:** [REF-C03] Analyst → Formalizer → Coder (from [REF-P07] ReDeFo)
**Intermediate language:** [REF-C04] Dafny as IL (from [REF-P12] Amazon AWS)
**LLM interface:** [REF-T16] litellm (model-agnostic)

```
.card.md spec
     ↓
SPEC REWRITER (pre-processing)
  Applies 5 Proven rule groups (19 normalization patterns) [REF-NEW-01]
  Normalizes ambiguous invariants before generation
     ↓
ANALYST AGENT (LLM call 1)
  Reads: intent + acceptance criteria + edge cases
  Outputs: structured requirements analysis
  Prompt role: "You are a requirements analyst..."
     ↓
FORMALIZER AGENT (LLM call 2)
  Reads: analyst output + contract + invariants
  Outputs: Dafny module with requires/ensures/invariants
  Prompt role: "You are a formal methods engineer..."
     ↓
CODER AGENT (LLM call 3)
  Reads: Dafny skeleton from formalizer
  Outputs: Complete Dafny implementation satisfying all specs
  Prompt role: "You are a Dafny programmer..."
     ↓
dafny verify → dafny compile --target {py|js|go|java|cs}
     ↓
Verified artifact in target language
```

### Model Selection

All LLM calls go through litellm [REF-T16]. Model is configurable via environment variable:

```bash
NIGHTJAR_MODEL=claude-sonnet-4-6     # default — best balance
NIGHTJAR_MODEL=deepseek/deepseek-chat  # budget — 10x cheaper
NIGHTJAR_MODEL=openai/o3               # premium — highest success rate
```

For Dafny-specific repair calls, Re:Form fine-tuned models [REF-P32] can be used on-premise at $0.001/retry vs $0.01/retry for Claude.

---

## 6. Immune System Design

**Concept:** [REF-C09] Acquired Immunity
**Biological reference:** [REF-P18] Self-Healing Software
**Trace collection:** [REF-T12] MonkeyType, [REF-T15] OpenTelemetry
**Mining engine:** Reimplemented Daikon algorithm (CC-BY-NC-SA safe — see REFERENCES.md)
**Verification:** [REF-T09] CrossHair, [REF-T03] Hypothesis
**Enforcement:** [REF-T10] icontract
**LLM enrichment:** [REF-P15] Agentic PBT, [REF-P14] NL2Contract

### 5-Stage Invariant Mining Pipeline

```
STAGE 1: SIGNAL COLLECTION
  OpenTelemetry [REF-T15] → API-level spans (auto-instrumented)
  MonkeyType [REF-T12] → function-level type traces
  Sentry webhook payloads → semantic fingerprinting [Section 11]

STAGE 2: INVARIANT CANDIDATE GENERATION
  Reimplemented DynamicInvariants algorithm → value invariants
  MonkeyType → type invariants
  LLM enrichment [REF-P15] → semantic invariants from error context

STAGE 3: INVARIANT VERIFICATION
  CrossHair [REF-T09] → symbolic verification
  Hypothesis [REF-T03] → PBT with 1000+ random inputs
  Passing invariants = verified candidates

STAGE 4: QUALITY SCORING (Phase 2 — Wonda [REF-NEW-05])
  4-criteria quality filter:
    • Precision: does the invariant hold for all known-good traces?
    • Recall: does it catch known-bad traces?
    • Specificity: not vacuously true
    • Stability: consistent across multiple verification runs
  Threshold: score ≥ 0.8 to proceed

STAGE 5: SPEC INTEGRATION
  Verified, quality-scored invariants appended to .card.md invariants: block
  Git commit to invariant history (append-only)
  Next build incorporates new invariants
```

### Adversarial Debate Validation (Phase 2)

Before a candidate invariant is committed to the spec, it passes through adversarial debate validation [REF-NEW-10]:

- Proposer LLM argues the invariant is correct and meaningful
- Adversary LLM challenges it with counterexamples and edge cases
- Debate judge scores the exchange and accepts/rejects the invariant
- Failed debates are logged with the adversary's counterexamples for developer review

This catches invariants that pass mechanical verification but are semantically wrong.

### Temporal Fact Supersession (Phase 2)

The immune system's `enforcer.py` implements temporal fact supersession [Supermemory pattern]:

```
confidence(t) = base_confidence * 0.5^(elapsed / half_life)
```

Older invariants decay in confidence over time. When a new invariant contradicts an existing one:
- `supersede()` marks the old invariant as stale (not deleted — audit trail preserved)
- The new invariant takes effect immediately
- Decay rate is configurable per invariant type (security invariants: longer half-life)

### Test Oracle Lifting (Phase 2)

`oracle_lifter.py` extracts test oracles from existing test suites [REF-NEW-06]:

```
Input: existing pytest/unittest test files
Output: structured invariants in .card.md format
Accuracy: 98.2% on standard Python test patterns
```

This provides a migration path: existing test-covered code gains machine-checkable invariants without rewriting specs from scratch.

### Network Effect (Long-term)

```
STAGE 6: NETWORK EFFECT
  Structural abstraction (no PII, type-level patterns only)
  Differential privacy via OpenDP [REF-T20]
  Shared pattern library across tenants
  Herd immunity threshold: confidence > 0.95 across 50+ tenants → universal
```

---

## 7. LP Dual Root-Cause Diagnosis

**Reference:** [REF-NEW-03] Linear programming duality for constraint diagnosis

When the retry loop exhausts its budget (N=5 attempts), the LP dual diagnosis engine provides a human-readable root cause:

```
diagnosis.py:
  Input: failed verification result + all counterexamples
  Method: LP relaxation of invariant constraints
          Shadow prices (dual variables) identify binding constraints
  Output: ranked list of "most likely violated root causes"
          with natural-language explanation per constraint
```

This replaces the unhelpful "verification failed after 5 retries" message with something actionable: which invariant constraint is structurally infeasible given the spec, and why.

---

## 8. MCP Server Interface

**Protocol:** [REF-T18] Model Context Protocol

Nightjar ships as an MCP server with 3 tools:

### Tool 1: `verify_contract`

```json
{
  "name": "verify_contract",
  "description": "Run Nightjar verification pipeline on generated code against a .card.md spec",
  "inputSchema": {
    "type": "object",
    "properties": {
      "spec_path": { "type": "string", "description": "Path to .card.md file" },
      "code_path": { "type": "string", "description": "Path to generated code" },
      "stages": { "type": "string", "enum": ["all", "fast", "formal"], "default": "all" }
    },
    "required": ["spec_path", "code_path"]
  }
}
```

Returns: `{ verified: boolean, stages: [...], errors: [...], duration_ms: number }`

### Tool 2: `get_violations`

```json
{
  "name": "get_violations",
  "description": "Get detailed violation report from last verification run",
  "inputSchema": {
    "type": "object",
    "properties": {
      "spec_path": { "type": "string" }
    }
  }
}
```

Returns: `{ violations: [{ stage, file, line, message, counterexample }] }`

### Tool 3: `suggest_fix`

```json
{
  "name": "suggest_fix",
  "description": "Get LLM-suggested fix for a specific verification violation",
  "inputSchema": {
    "type": "object",
    "properties": {
      "spec_path": { "type": "string" },
      "violation_id": { "type": "string" }
    }
  }
}
```

Returns: `{ suggested_code: string, explanation: string, confidence: number }`

---

## 9. CLI Design

**Framework:** [REF-T17] Click

```
nightjar — Contract-Anchored Regenerative Development CLI

COMMANDS:
  nightjar init [module-name]     Scaffold .card.md + deps.lock + tests/
  nightjar generate [--model]     LLM generates code from .card.md
  nightjar verify                 Run full verification pipeline
  nightjar verify --fast          Stages 0-3 only (skip Stage 2.5 + Dafny)
  nightjar verify --stage N       Run only stage N (0-4)
  nightjar build                  generate + verify + compile to target
  nightjar ship                   build + sign artifact
  nightjar retry [--max N]        Force retry with LLM repair loop
  nightjar lock                   Freeze deps into deps.lock with hashes
  nightjar explain                Show last failure with LP dual diagnosis
  nightjar optimize               Run LLM prompt optimization (hill-climbing) [REF-T26]
  nightjar auto                   Generate .card.md specs from natural language intent
  nightjar watch                  File-watching daemon with tiered verification
  nightjar badge                  Print shields.io badge URL for last verification run
  nightjar scan <file|dir>        Extract invariants from existing Python code
                                    --smart-sort: security-critical file prioritization
                                    --workers N: parallel file workers
  nightjar infer <file>           LLM + CrossHair contract inference loop
                                    Generates preconditions/postconditions automatically
  nightjar audit <package>        PyPI package scanner with terminal report card
                                    Letter grades A-F; CVE check via OSV API
  nightjar benchmark <path>       Academic benchmark runner (vericoding POPL 2026, DafnyBench)
                                    Reports pass@k scoring

FLAGS:
  --contract PATH       Path to .card.md (default: ./.card/*.card.md)
  --target LANG         Compile target: py | js | ts | go | java | cs
  --model NAME          LLM model (default: from NIGHTJAR_MODEL env var)
  --retries N           Max repair attempts (default: 5)
  --output DIR          Output directory for artifacts
  --tui                 Launch Textual TUI dashboard [Section 12]
  --ci                  CI mode (strict, no prompts, exit code on fail)
  --format=vscode       VS Code problem matcher output format
  --output-sarif FILE   Write SARIF 2.1.0 file for GitHub Code Scanning

EXIT CODES:
  0   All stages PASS
  1   Verification FAIL
  2   Configuration error
  3   Timeout exceeded
  4   LLM API error
  5   Max retries exceeded (human escalation required)
```

---

## 10. Data Flow (End-to-End)

```
DEVELOPER writes .card.md
        ↓
nightjar build
        ↓
SPEC REWRITER applies 5 Proven rule groups (19 patterns)
        ↓
PARSE .card.md → extract contract + invariants + acceptance criteria
        ↓
GENERATE (via litellm [REF-T16])
  Analyst → Formalizer → Coder [REF-C03]
  Output: module.dfy (Dafny source)
        ↓
VERIFY (6-stage pipeline)
  Stage 0-4 + Stage 2.5 [Section 3]
  On fail: CEGIS retry loop [Section 4] up to N times
  On exhaustion: LP dual diagnosis report [Section 7]
        ↓
COMPILE (Dafny → target language)
  dafny compile --target py module.dfy [REF-T01]
  Output: module.py (verified Python)
        ↓
OUTPUT
  dist/module.py → deployable artifact
  .card/audit/module.py → read-only audit branch
  .card/verify.json → verification report
        ↓
IMMUNE SYSTEM monitors production [Section 6]
  Sentry webhook payloads → candidate invariants [Section 11]
  Failures → Wonda quality scoring → adversarial debate → .card.md updated
  Next build is safer
```

---

## 11. Observability

### Sentry Webhook Payload Parser

`sentry_integration.py` parses Sentry-format JSON payloads into immune system invariant candidates. It does not use the sentry_sdk and does not connect to Sentry directly — it only processes webhook payloads your server receives.

```python
sentry_event_to_candidate(event)  # extract invariant candidate from error
sentry_feed(events)                # batch with deduplication
process_webhook_payload(payload)   # handle Sentry webhook callbacks
get_sentry_dsn()                   # DSN management
```

Sentry error payloads become invariant candidates. The immune system verifies them, scores them with Wonda, and — if they pass adversarial debate — commits them to the spec. Production failures directly improve future verification coverage.

### GitNexus Blast Radius Hooks

`gitnexus_hooks.py` integrates with the GitNexus code intelligence graph to warn before regeneration:

```python
check_blast_radius(symbol)             # query impact graph
warn_before_regeneration(module)       # issue warning if HIGH/CRITICAL
format_blast_radius_warning(result)    # human-readable warning text
```

When `nightjar build` would regenerate a module, blast radius analysis runs first. If the impacted call graph is HIGH or CRITICAL risk, the developer is warned before proceeding.

### Playwright E2E Tests

`tests/e2e/` contains Playwright browser tests for web-facing components:

- Badge server SVG rendering
- PR comment HTML rendering
- Tests auto-skip when no browser is available (CI-safe)

---

## 12. Developer Experience

### Textual TUI Dashboard

`src/nightjar/tui.py` provides a real-time terminal dashboard built with Textual:

- `NightjarTUI` — top-level App, thread-safe via `post_message`
- `StagePanel` — reactive widgets, one per pipeline stage
- Live stage status: pending → running → pass/fail/skip
- Activated with `--tui` flag: `nightjar verify --tui`
- Implements the `DisplayCallback` protocol — wired to `run_pipeline(display=tui)`

### Rich Streaming Display

`src/nightjar/display.py` provides the `DisplayCallback` protocol:

```python
class DisplayCallback(Protocol):
    def on_stage_start(self, stage: int, name: str) -> None: ...
    def on_stage_complete(self, result: StageResult) -> None: ...
    def on_pipeline_complete(self, result: VerifyResult) -> None: ...
```

- `RichStreamingDisplay` — streaming output with Rich formatting (colours, tables, progress)
- `NullDisplay` — silent no-op default (used in library mode and tests)

### VHS Demo Recording

`demo/nightjar-demo.tape` is a VHS declarative demo script:

```bash
vhs demo/nightjar-demo.tape    # generates nightjar-demo.gif
vhs demo/nightjar-tui.tape     # generates tui screenshot
```

The demo tape records a complete `nightjar build` session including the TUI dashboard. The output GIF is embedded in the README.

---

## 13. Directory Structure

```
project/
├── .card/
│   ├── constitution.card.md        # Project-level invariants
│   ├── auth.card.md                # Module specs
│   ├── payment.card.md
│   ├── audit/                      # Read-only generated code (git-tracked)
│   │   ├── auth.py
│   │   └── payment.py
│   ├── cache/                      # Verification cache (hash → verified)
│   └── verify.json                 # Last verification report
├── deps.lock                       # Sealed dependency manifest [REF-C08]
├── dist/                           # Compiled verified artifacts
│   ├── auth.py
│   └── payment.py
├── tests/
│   ├── generated/                  # Auto-generated PBT tests
│   ├── manual/                     # Human-written example tests
│   └── e2e/                        # Playwright browser tests [Section 11]
├── demo/
│   ├── nightjar-demo.tape          # VHS declarative demo recording
│   └── nightjar-tui.tape           # TUI screenshot recording
├── src/
│   ├── nightjar/
│   │   ├── cli.py                  # Click commands [REF-T17]
│   │   ├── parser.py               # .card.md parser
│   │   ├── generator.py            # LLM generation pipeline [REF-C03]
│   │   ├── verifier.py             # Verification pipeline orchestrator
│   │   ├── spec_rewriter.py        # 5 rule groups / 19 normalization patterns [REF-NEW-01]
│   │   ├── retry.py                # CEGIS retry loop [REF-NEW-02, REF-C02]
│   │   ├── diagnosis.py            # LP dual root-cause diagnosis [REF-NEW-03]
│   │   ├── negation_proof.py       # Negation-proof validation [REF-NEW-07]
│   │   ├── oracle_lifter.py        # Test oracle lifting [REF-NEW-06]
│   │   ├── tui.py                  # Textual TUI dashboard
│   │   ├── display.py              # Rich streaming DisplayCallback
│   │   ├── sentry_integration.py   # Sentry webhook payload parser [Section 11]
│   │   ├── gitnexus_hooks.py       # Blast radius warnings [Section 11]
│   │   ├── mcp_server.py           # MCP server [REF-T18]
│   │   └── stages/
│   │       ├── preflight.py        # Stage 0
│   │       ├── deps.py             # Stage 1 [REF-C08]
│   │       ├── schema.py           # Stage 2 [REF-T08]
│   │       ├── pbt.py              # Stage 3 [REF-T03]
│   │       └── formal.py           # Stage 4 [REF-T01]
│   └── immune/
│       ├── collector.py            # Trace collection [REF-T12, REF-T15]
│       ├── miner.py                # Invariant mining [REF-C05]
│       ├── enricher.py             # LLM enrichment [REF-C06]
│       ├── enforcer.py             # Runtime enforcement + temporal supersession [REF-T10]
│       ├── quality_scorer.py       # Wonda quality scoring [REF-NEW-05]
│       └── debate.py               # Adversarial debate [REF-NEW-10]
└── docs/
    ├── REFERENCES.md               # Citation library
    ├── ARCHITECTURE.md             # This document
    └── POSITIONING.md              # Strategy and positioning
```

---

## 14. Key Design Decisions

| Decision | Choice | Rationale | Reference |
|----------|--------|-----------|-----------|
| Spec format | YAML frontmatter + Markdown | De-facto standard across 16+ AI tools | [REF-T24] |
| Verification language | Dafny | 82-96% LLM success rate, compiles to 5 languages | [REF-P02] |
| PBT framework | Hypothesis (Python) / fast-check (JS) | Industry standard, well-documented | [REF-T03, REF-T04] |
| LLM interface | litellm | Model-agnostic, 100+ providers | [REF-T16] |
| CLI framework | Click | Python-native, composable | [REF-T17] |
| IDE integration | MCP server | Universal bus for all vibe coding tools | [REF-T18] |
| Retry pattern | Clover + CEGIS | 87% correct acceptance, counterexample-guided repair | [REF-P03, REF-NEW-02] |
| Error format | DafnyPro structured | Enables targeted LLM repair | [REF-P06] |
| Spec preprocessing | 5 rule groups (19 normalization patterns) | Normalises ambiguous specs before generation | [REF-NEW-01] |
| Negation validation | Stage 2.5 CrossHair | Catches degenerate specs before expensive Dafny | [REF-NEW-07] |
| Complexity routing | SafePilot cyclomatic | ~70% wall-time savings on typical codebases | [REF-NEW-08] |
| Root-cause diagnosis | LP duality shadow prices | Replaces "5 retries failed" with actionable root cause | [REF-NEW-03] |
| Invariant quality gate | Wonda 4-criteria | Precision + recall + specificity + stability | [REF-NEW-05] |
| Adversarial validation | Debate judge pattern | Catches semantically wrong but mechanically passing invariants | [REF-NEW-10] |
| Temporal supersession | Exponential decay | Old invariants decay; supersede() preserves audit trail | Supermemory |
| Oracle migration | Test oracle lifter | 98.2% accuracy migrating tests → .card.md invariants | [REF-NEW-06] |
| Dependency security | Sealed manifest + hash verification | 19.7% of AI deps are hallucinated | [REF-P27] |
| Architecture principle | Don't round-trip | MDD died from this; enforce architecturally | [REF-P29] |
| Immune system mining | Reimplemented Daikon algorithm | Fuzzingbook is CC-BY-NC-SA (non-commercial) | [REF-T13] |
| Immune system enforcement | icontract decorators | Runtime DBC for Python | [REF-T10] |
| TUI framework | Textual | Reactive widgets, thread-safe, terminal-native | [REF-T27] |
| Streaming output | Rich DisplayCallback | Protocol-based, NullDisplay default for library use | [REF-T28] |
| Error observability | Sentry webhook payload parser | Parses Sentry-format payloads into invariant candidates (no sentry_sdk) | |
| Impact analysis | GitNexus blast radius | Warns before regenerating high-impact modules | |
| Output formats | SARIF 2.1.0 + VS Code | GitHub Code Scanning integration; IDE inline errors | |
| Docker image | Multi-stage, Dafny bundled | Hermetic CI environment, ~300MB | |

---

## 15. Phase 6 Extensions

### Verification Canvas

`docs/web/nightjar-canvas/` — a Next.js 15 frontend for visual verification exploration.

```
Technology: Next.js 15, React Flow, shadcn/ui, Tremor
Realtime:   Server-Sent Events (SSE) for live stage updates
Features:   Pipeline replay, playground, invariant explorer, compare runs
Sharing:    Shareable run URLs, achievement badges, history
Deployment: Cloudflare Pages (Functions for SSE endpoints)
```

Key components:
- `VerificationLayout` — top-level layout with SSE connection and stage panels
- Pipeline replay with step-by-step scrubbing
- Invariant explorer: filter by tier, search, sort by confidence
- Run comparison: diff two verification runs side-by-side
- Achievement system: gamified milestones surfaced on first-pass verifications

### AlphaEvolve Integration

Five features behind the `NIGHTJAR_ENABLE_EVOLUTION=1` environment variable:

| Feature | Description |
|---------|-------------|
| MAP-Elites strategy DB | Quality-diversity archive of successful repair strategies |
| Strategy scoring | Tracks which repair prompts succeed per error-class |
| Wave-based bug hunt | Automated multi-package scanning with wave coordination |
| Ratchet loop | Prevents regression — verified confidence can only increase |
| Scanner evolution | AlphaEvolve mutates scan heuristics toward higher bug-find rate |

Enable with:
```bash
NIGHTJAR_ENABLE_EVOLUTION=1 nightjar verify
```

### SARIF Output

`nightjar verify --output-sarif results.sarif` produces SARIF 2.1.0 compatible output:

```
Consumers:  GitHub Code Scanning (upload via actions/upload-sarif)
            VS Code SARIF Viewer extension
            Azure DevOps Code Scanning
Schema:     https://docs.oasis-open.org/sarif/sarif/v2.1.0/
Rules:      One SARIF rule per Nightjar stage (NJ-S0 through NJ-S4)
Results:    Each invariant violation becomes a SARIF result with region info
```

### Docker Image Architecture

`ghcr.io/j4ngzzz/nightjar` — multi-stage build, ~300MB:

```dockerfile
# Stage 1: Dafny installer (downloads Dafny 4.8.0 binary)
# Stage 2: Python deps (pip install nightjar-verify)
# Stage 3: Final image (copies both, sets entrypoint to nightjar CLI)

# Usage:
docker run --rm -v $(pwd):/workspace ghcr.io/j4ngzzz/nightjar \
  verify --spec /workspace/.card/payment.card.md
```

The image pins Dafny 4.8.0 and the nightjar-verify release version together, ensuring reproducible verification results in CI without requiring Dafny to be installed on the host.
