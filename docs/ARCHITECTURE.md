# CARD Architecture

> **Contract-Anchored Regenerative Development**
>
> Every section in this document cites specific entries from [REFERENCES.md](./REFERENCES.md).
> BridgeSwarm agents: fetch and read the cited references BEFORE implementing.

---

## 1. System Overview

CARD is a verification layer for AI-generated code. Developers write specs. AI generates code. CARD verifies the code satisfies the specs mathematically. Code is regenerated from scratch on every build — it is never manually edited.

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
LAYER 3: VERIFICATION (5-stage pipeline)
  Stage 0: Pre-flight (AST parse)
  Stage 1: Dependency check (sealed manifest) [REF-C08, REF-P27]
  Stage 2: Schema validation (Pydantic) [REF-T08]
  Stage 3: Property-based testing (Hypothesis) [REF-T03, REF-P10]
  Stage 4: Formal verification (Dafny) [REF-T01, REF-P02]
  Retry loop on failure [REF-C02, REF-P03, REF-P06]
         ↓
LAYER 4: OUTPUT
  Dafny compiles to target language (Python/JS/Go/Java/C#) [REF-T01]
  Binary/artifact shipped
  Code committed to read-only audit branch (never edited)
         ↓
LAYER 5: IMMUNE SYSTEM (month 2-3+)
  Production monitoring → invariant mining → verification → spec update
  [REF-C09, REF-T12, REF-T13, REF-T09, REF-T10]
```

### Core Architectural Principle

**"Don't Round-Trip"** [REF-C07, REF-P29]

Generated code is NEVER manually edited. All changes go through the `.card.md` spec. This is enforced architecturally, not by convention. The round-trip engineering death spiral that killed MDD [REF-P30] is structurally impossible in CARD.

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
# ── CARD Spec Frontmatter ──────────────────────────────
card-version: "1.0"
id: module-name
title: Human-Readable Module Title
status: draft | review | approved | frozen

# ── Module Boundary ────────────────────────────────────
module:
  owns: [function_a(), function_b(), EntityX, EntityY]
  depends-on:
    - other-module: "approved"     # internal CARD module
    - external-service: "^3.x"    # external dependency
  excludes:
    - "feature explicitly out of scope"

# ── Interface Contract ─────────────────────────────────
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

# ── Invariants (Tiered) [REF-C01] ─────────────────────
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

# ── Nonfunctional Constraints ──────────────────────────
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

A vibecoder writes this in 5 minutes:

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

**Designed from:** Agent 2 research findings
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
│ STAGE 4: FORMAL VERIFICATION  [~5-20s, $0.00]          │
│ • dafny verify module.dfy [REF-T01]                     │
│   --verification-time-limit 15                          │
│   --isolate-assertions                                  │
│   --boogie /vcsCores:4                                  │
│ • Only for invariants with tier: formal                 │
│ SHORT-CIRCUIT: proof failure → FAIL + error context     │
└─────────────────────────────────────────────────────────┘
         │
    ALL PASS → Ship artifact
    ANY FAIL → Retry Loop [Section 4]
```

### Stage 2+3 Parallelization

Stages 2 and 3 have no dependency and run in parallel:

```python
# Pseudocode from Agent 2 design
async def verify_pipeline(module_path, contract_path):
    await run_stage(0, preflight_check)        # sequential
    await run_stage(1, dependency_check)        # sequential
    schema_result, pbt_result = await asyncio.gather(
        run_stage(2, schema_validation),        # parallel
        run_stage(3, property_based_tests)      # parallel
    )
    if not (schema_result.ok and pbt_result.ok):
        return FAIL(schema_result, pbt_result)
    return await run_stage(4, dafny_verification)  # sequential (heaviest)
```

### Cost Summary

| Stage | Latency | Cost | Tool |
|-------|---------|------|------|
| 0: Pre-flight | ~0.5s | $0.000 | Python AST |
| 1: Dep check | ~1-2s | $0.000 | uv + pip-audit [REF-T05, REF-T06] |
| 2: Schema | ~0.5-1s | $0.000 | Pydantic [REF-T08] |
| 3: PBT | ~3-8s | $0.000 | Hypothesis [REF-T03] |
| 4: Formal | ~5-20s | $0.000 | Dafny [REF-T01] |
| **Total (0 retries)** | **~10-31s** | **~$0.001** | |
| Per retry (LLM call) | ~3-8s | ~$0.01-0.03 | litellm [REF-T16] |
| **Total (3 retries)** | **~30-55s** | **~$0.03-0.10** | |

---

## 4. The Retry Loop

**Pattern:** [REF-C02] Closed-Loop Verification (Clover Pattern) [REF-P03]
**Error format:** [REF-P06] DafnyPro structured errors
**Success rate:** 86% pass@10 with Claude 3.5 Sonnet [REF-P06]

```
On FAIL from any stage:

1. COLLECT FAILURE CONTEXT
   Stage 1 fail → disallowed packages + lock diff
   Stage 2 fail → schema diff (Pydantic error trace)
   Stage 3 fail → counterexample (input, output, property text)
   Stage 4 fail → Dafny error lines + assertion batch ID + resource units

2. BUILD REPAIR PROMPT
   System: original .card.md spec
   User: failed code + structured error block + prior failed attempts

3. CALL LLM (via litellm [REF-T16])
   Temperature: 0.2 (deterministic repair)
   Max tokens: 2048 output

4. RE-RUN FULL PIPELINE from Stage 0

5. RETRY CAP: N=5 → if still failing, ESCALATE to human
```

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
CARD_MODEL=claude-sonnet-4-6     # default — best balance
CARD_MODEL=deepseek/deepseek-chat  # budget — 10x cheaper
CARD_MODEL=openai/o3               # premium — highest success rate
```

For Dafny-specific repair calls, Re:Form fine-tuned models [REF-P32] can be used on-premise at $0.001/retry vs $0.01/retry for Claude.

---

## 6. Immune System Design (Month 2-3+)

**Concept:** [REF-C09] Acquired Immunity
**Biological reference:** [REF-P18] Self-Healing Software
**Trace collection:** [REF-T12] MonkeyType, [REF-T15] OpenTelemetry
**Mining engine:** [REF-T13] Fuzzingbook DynamicInvariants (MUST reimplement for commercial use — see license warning in REFERENCES.md)
**Verification:** [REF-T09] CrossHair, [REF-T03] Hypothesis
**Enforcement:** [REF-T10] icontract
**LLM enrichment:** [REF-P15] Agentic PBT, [REF-P14] NL2Contract

### 5-Stage Pipeline

```
STAGE 1: SIGNAL COLLECTION
  OpenTelemetry [REF-T15] → API-level spans (auto-instrumented)
  MonkeyType [REF-T12] → function-level type traces
  Sentry-style error capture → semantic fingerprinting

STAGE 2: INVARIANT CANDIDATE GENERATION
  Fuzzingbook DynamicInvariants algorithm → value invariants
  MonkeyType → type invariants
  LLM enrichment [REF-P15] → semantic invariants from error context

STAGE 3: INVARIANT VERIFICATION
  CrossHair [REF-T09] → symbolic verification
  Hypothesis [REF-T03] → PBT with 1000+ random inputs
  Passing invariants = verified candidates

STAGE 4: SPEC INTEGRATION
  Verified invariants appended to .card.md invariants: block
  Git commit to invariant history (append-only)
  Next build incorporates new invariants

STAGE 5: NETWORK EFFECT (Month 6+)
  Structural abstraction (no PII, type-level patterns only)
  Differential privacy via OpenDP [REF-T20]
  Shared pattern library across tenants
  Herd immunity threshold: confidence > 0.95 across 50+ tenants → universal
```

### Minimum Viable Immune System (Python)

Using EXISTING tools, the simplest version that works:

```python
# Step 1: Trace collection
from fuzzingbook.DynamicInvariants import InvariantAnnotator  # [REF-T13] reference only
annotator = InvariantAnnotator(function_to_monitor)

# Step 2: Get candidate invariants
preconditions = annotator.preconditions()    # "x > 0", "len(items) > 0"
postconditions = annotator.postconditions()  # "result IS_A float"

# Step 3: LLM enrichment [REF-P15 Agentic PBT pattern]
llm_prompt = f"""
Function: {function_signature}
Observed invariants: {preconditions + postconditions}
Failing call: {error_trace}
Generate Python assert statements that would have caught this failure.
"""

# Step 4: Verify with Hypothesis [REF-T03]
@given(st.from_type(function_type_hints))
def test_invariant(args):
    assert llm_generated_condition(args)

# Step 5: Enforce with icontract [REF-T10]
@icontract.require(lambda x: x > 0)
@icontract.ensure(lambda result: result is not None)
def my_function(x): ...
```

**NOTE:** For commercial use, reimplement the DynamicInvariants algorithm (~300 lines) under MIT. The algorithm itself (Daikon, 1999) is not patented.

---

## 7. MCP Server Interface

**Protocol:** [REF-T18] Model Context Protocol
**Strategy:** [Agent 3 adoption playbook] Ship as MCP server for universal IDE integration

CARD ships as an MCP server with 3 tools:

### Tool 1: `verify_contract`

```json
{
  "name": "verify_contract",
  "description": "Run CARD verification pipeline on generated code against a .card.md spec",
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

## 8. CLI Design

**Framework:** [REF-T17] Click

```
contractd — Contract-Anchored Regenerative Development CLI

COMMANDS:
  contractd init [module-name]     Scaffold .card.md + deps.lock + tests/
  contractd generate [--model]     LLM generates code from .card.md
  contractd verify                 Run full 5-stage verification pipeline
  contractd verify --fast          Stages 0-3 only (skip Dafny)
  contractd verify --stage N       Run only stage N (0-4)
  contractd build                  generate + verify + compile to target
  contractd ship                   build + sign artifact
  contractd retry [--max N]        Force retry with LLM repair loop
  contractd lock                   Freeze deps into deps.lock with hashes
  contractd explain                Show last failure in human-readable form
  contractd optimize               Run DSPy SIMBA prompt optimization [REF-T26]

FLAGS:
  --contract PATH    Path to .card.md (default: ./.card/*.card.md)
  --target LANG      Compile target: py | js | ts | go | java | cs
  --model NAME       LLM model (default: from CARD_MODEL env var)
  --retries N        Max repair attempts (default: 5)
  --output DIR       Output directory for artifacts
  --ci               CI mode (strict, no prompts, exit code on fail)

EXIT CODES:
  0   All stages PASS
  1   Verification FAIL
  2   Configuration error
  3   Timeout exceeded
  4   LLM API error
  5   Max retries exceeded (human escalation required)
```

---

## 9. Data Flow (End-to-End)

```
DEVELOPER writes .card.md
        ↓
contractd build
        ↓
PARSE .card.md → extract contract + invariants + acceptance criteria
        ↓
GENERATE (via litellm [REF-T16])
  Analyst → Formalizer → Coder [REF-C03]
  Output: module.dfy (Dafny source)
        ↓
VERIFY (5-stage pipeline)
  Stage 0-4 [Section 3]
  On fail: retry loop [Section 4] up to N times
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
(Month 2-3+) IMMUNE SYSTEM monitors production [Section 6]
  Failures → new invariants → .card.md updated → next build is safer
```

---

## 10. Directory Structure

```
project/
├── .card/
│   ├── constitution.card.md        # Project-level invariants
│   ├── auth.card.md                # Module specs
│   ├── payment.card.md
│   ��── audit/                      # Read-only generated code (git-tracked)
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
│   │   ├── test_auth_properties.py
│   │   └── test_payment_properties.py
│   └── manual/                     # Human-written example tests
├── contractd.toml                  # CLI configuration
├── CLAUDE.md                       # AI agent instructions
└── docs/
    ├── REFERENCES.md               # Citation library
    ├── ARCHITECTURE.md             # This document
    └── POSITIONING.md              # Strategy and positioning
```

---

## 11. Key Design Decisions

| Decision | Choice | Rationale | Reference |
|----------|--------|-----------|-----------|
| Spec format | YAML frontmatter + Markdown | De-facto standard across 16+ AI tools | [REF-T24] |
| Verification language | Dafny | 82-96% LLM success rate, compiles to 5 languages | [REF-P02] |
| PBT framework | Hypothesis (Python) / fast-check (JS) | Industry standard, well-documented | [REF-T03, REF-T04] |
| LLM interface | litellm | Model-agnostic, 100+ providers | [REF-T16] |
| CLI framework | Click | Python-native, composable | [REF-T17] |
| IDE integration | MCP server | Universal bus for all vibe coding tools | [REF-T18] |
| Retry pattern | Clover closed-loop | 87% correct acceptance, 0% false positive | [REF-P03] |
| Error format | DafnyPro structured | Enables targeted LLM repair | [REF-P06] |
| Dependency security | Sealed manifest + hash verification | 19.7% of AI deps are hallucinated | [REF-P27] |
| Architecture principle | Don't round-trip | MDD died from this; enforce architecturally | [REF-P29] |
| Immune system mining | Reimplemented Daikon algorithm | Fuzzingbook is CC-BY-NC-SA (non-commercial) | [REF-T13] |
| Immune system enforcement | icontract decorators | Runtime DBC for Python | [REF-T10] |
