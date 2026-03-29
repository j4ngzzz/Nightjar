# Nightjar Immune System — User Guide

The immune system is Nightjar's self-improvement engine. It watches your running code, mines invariant patterns from real execution, proves those patterns hold, and appends the survivors back into your `.card.md` specs. Your specs get stronger every time code runs — without you writing a single invariant by hand.

This guide covers what to type, what to expect, and how to interpret the results. For internal architecture and academic references, see `docs/ARCHITECTURE.md` Section 6.

---

## The Big Picture

```
Run your code
     |
     v
Collect traces  ─────────────────────────────────────────────────────────┐
(MonkeyType type traces, OTel spans, Sentry error payloads)              |
     |                                                                    |
     v                                                                    |
Mine invariants (3 tiers run in parallel)                                |
  Tier 1: LLM reads source → hypothesizes invariants                    |
  Tier 2: Daikon watches execution → infers value/type patterns         |
  Tier 3: MINES reads OTel spans → discovers API contracts              |
     |                                                                    |
     v                                                                    |
Score quality (Wonda filter — remove tautologies and vacuous claims)     |
     |                                                                    |
     v                                                                    |
Adversarial debate (two LLMs argue; judge accepts or rejects)            |
     |                                                                    |
     v                                                                    |
Verify (CrossHair symbolic + Hypothesis property-based, 1000 examples)  |
     |                                                                    |
     v                                                                    |
Append to .card.md spec (append-only, git-tracked)                      |
     |                                                                    |
     v                                                                    |
Enforce at runtime (icontract @require / @ensure decorators)  ──────────┘
     |
     v
Runtime violations → new trace candidates → cycle continues
```

The loop closes: production failures become spec improvements.

---

## Installation

The immune system is an optional dependency group:

```bash
pip install "nightjar[immune]"
# or with uv:
uv pip install "nightjar[immune]"
```

If you run an immune command without it installed, Nightjar will tell you exactly which package is missing and how to install it.

---

## Three-Tier Mining

The three mining tiers run independently and their results are deduplicated by expression. When multiple tiers produce the same invariant, confidence scores are merged (max is taken) and the source is labelled as the combined tools (e.g., `daikon+llm`).

| Tier | Name | What It Finds | Mechanism | Overhead |
|------|------|---------------|-----------|----------|
| 1 | Semantic | Pre/postconditions, behavioral contracts, edge-case properties | LLM reads the function source and hypothesizes invariants (base confidence: 0.75) | Zero — no instrumentation |
| 2 | Runtime | Value ranges, type invariants, state relationships, sequence properties | Daikon algorithm (19 Ernst templates) via `sys.monitoring` (Python 3.12+) or `sys.settrace` (3.11) (base confidence: 0.85) | Low — up to 20x less than `sys.settrace` alone |
| 3 | API-Level | HTTP contract patterns, latency bounds, status code invariants | MINES pipeline from OpenTelemetry spans | None — post-hoc analysis of existing spans |

### The 19 Daikon Templates (Tier 2)

When Tier 2 runs, it checks your execution traces against 19 pattern templates derived from Ernst et al. (1999/2007):

| Category | Templates |
|----------|-----------|
| Unary Scalar | Constant, NonZero, IsNull/NonNull, Range, OneOf, IsType |
| Binary Relations | Equality, Ordering, LinearRelation, Membership, NonEquality |
| Sequence | SeqIndexComparison, Sorted, SeqOneOf, SeqLength |
| State | Unchanged, Changed, Increased, Decreased |
| Conditional | Implication |

A template that holds across all observed call traces becomes an invariant candidate.

---

## CLI Commands

### `nightjar immune run` — Full Mining Cycle

Runs all three tiers, verifies the merged candidates, and optionally appends survivors to a `.card.md` spec.

```bash
# Full cycle — mine, verify, and append to spec
nightjar immune run src/payment.py --card .card/payment.card.md

# Run only Tier 1 (LLM semantic) on a specific function
nightjar immune run src/auth.py --tier 1 --function validate_token

# Mine without appending to a spec (inspect results first)
nightjar immune run src/payment.py
```

**Expected output:**

```
Nightjar Immune — mining invariants from src/payment.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tier 1 SEMANTIC:       3 invariants  (LLM hypothesis)
Tier 2 RUNTIME:        5 invariants  (Daikon+Houdini)
Tier 3 API-LEVEL:      2 invariants  (MINES spans)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Verified: 6/10 candidates | Appended to spec: 6
```

The green "Verified" line means at least one candidate passed. Yellow means no candidates survived verification — this is normal for a first run with sparse traces.

**Options:**

| Flag | Description |
|------|-------------|
| `--card <path>` | `.card.md` file to append verified invariants into. Omit to mine without writing. |
| `--tier 1\|2\|3` | Run a single tier instead of all three. Useful for debugging or speed. |
| `--function <name>` | Restrict mining to one function in the source file. |
| `--db <path>` | Path to the immune trace database (default: `.card/immune.db`). |

> **Open task:** The output format above is derived directly from the format strings in `src/nightjar/immune_commands.py`. The exact numbers, column widths, and Unicode separator characters are correct. However, the Tier 2 and Tier 3 counts will be 0 on a first run if no trace database has been populated yet — run `nightjar immune collect` first (see below) to seed Tier 2 data, and connect OpenTelemetry to seed Tier 3.

---

### `nightjar immune collect` — Collect Traces Only

Imports your module, exercises it (via `__main__`, a `main()` function, or the first public callable it finds), and saves runtime type traces to the immune database for later Tier 2 mining. Use this to build up a trace corpus before running `immune run`.

```bash
# Collect traces from the whole module
nightjar immune collect src/payment.py

# Collect traces for a specific function
nightjar immune collect src/auth.py --function validate_token
```

**Expected output:**

```
Nightjar Immune — collecting traces from src/payment.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Traced functions : 4
  Total call events: 1,247
  Saved 12 type trace(s) -> .card/immune.db
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If the module raises an exception during tracing, the command prints a warning and saves whatever traces were captured up to the point of failure.

**Options:**

| Flag | Description |
|------|-------------|
| `--function <name>` | Trace a specific function (default: trace all). |
| `--db <path>` | Trace database path (default: `.card/immune.db`). |

---

### `nightjar immune status` — Check What's Been Collected

Shows a summary of the immune database: how many traces exist, where candidates are in their lifecycle, and an overall health assessment.

```bash
nightjar immune status

# Check a custom database location
nightjar immune status --db .card/custom-immune.db
```

**Expected output:**

```
Nightjar Immune — status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Trace database:
    ✓ Type traces (MonkeyType)                   12
    ✓ Value traces (Daikon)                     247
      API traces (OTel)                           0
      Error traces (Sentry)                       0
                   TOTAL                        259

  Invariant candidates:
    Pending                    3
    Verified                   6
    Rejected                   2
    Applied to spec            6
    TOTAL                     17

  Verified invariants: 6
  Applied to specs   : 6

  Health: OK — 6 verified invariant(s) available
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Health states:**

| Message | Meaning | Next step |
|---------|---------|-----------|
| `NO TRACES` | Database is empty | Run `nightjar immune collect <src>` |
| `traces collected, no candidates yet` | Traces exist but mining hasn't run | Run `nightjar immune run <src>` |
| `candidates mined but none verified yet` | Mining ran but all failed verification | Improve trace coverage or check spec |
| `OK — N verified invariant(s) available` | Healthy — invariants are ready | Optionally run with `--card` to apply |

---

## Quality Filtering

Not every mined candidate is useful. Before reaching the verification step, candidates pass through two quality gates.

### Wonda Filter (Phase 2)

The Wonda quality scorer (quality threshold: 0.5) rejects:

- **Tautologies** — expressions that are always true regardless of input (e.g., `x == x`, `True`)
- **Syntax errors** — expressions that are not valid Python
- **Vacuous claims** — very low specificity, meaning the invariant constrains almost nothing

Each surviving candidate gets three scores:

| Score | What it measures |
|-------|-----------------|
| `coverage_score` | Fraction of collected execution traces that satisfy the invariant |
| `specificity_score` | Inverse tautology-ness (0 = trivially true, 1 = tightly constrained) |
| `falsifiability_score` | Estimated probability that defective code would violate it |

The MAP-Elites archive maintains a 25-cell grid organized by coverage and specificity. This preserves diverse invariants — preventing the filter from only accepting the safest, most generic candidates while throwing away narrow but valuable ones.

### Adversarial Debate (Phase 2)

Candidates that pass Wonda scoring enter an adversarial debate:

1. A **Proposer LLM** argues that the invariant is correct and meaningful
2. An **Adversary LLM** challenges it with counterexamples and edge cases
3. A **Debate Judge** scores the exchange and accepts or rejects the invariant

The debate catches invariants that pass mechanical verification (CrossHair found no counterexample) but are semantically wrong or misleading. Failed debates are logged with the adversary's specific counterexamples so you can inspect them.

### Houdini Filter (Tier 2 only)

Tier 2 mining applies a Houdini filter (greatest-fixpoint elimination) before merging with the other tiers. Any candidate that is not inductive — meaning it could fail on an execution trace the Daikon tracing didn't cover — is removed. Only provably inductive candidates reach the main verification step.

---

## Verification

Surviving candidates are verified by two independent engines:

| Engine | Method | Default config |
|--------|--------|---------------|
| CrossHair | Symbolic execution — searches for inputs that violate the invariant | 30-second timeout per candidate |
| Hypothesis | Property-based testing — generates 1,000 random inputs | 1,000 examples per candidate |

By default, a candidate is verified if **either** engine passes (not both required). You can tighten this to require both:

```python
# Programmatic use only — not yet exposed as a CLI flag
from immune.pipeline import ImmuneCycleConfig, run_immune_cycle

config = ImmuneCycleConfig(require_both_verifiers=True)
result = run_immune_cycle(
    function_source=source,
    function_name="process_payment",
    card_path=".card/payment.card.md",
    config=config,
)
```

---

## Runtime Enforcement

After verified invariants are appended to your `.card.md` spec, the enforcer generates icontract decorators that guard the function at runtime:

- Expressions referencing `result` become `@ensure` (postcondition) decorators
- All other expressions become `@require` (precondition) decorators

When a decorator fires a violation in production, the violation is captured and fed back into the immune system's collection pipeline as a new trace candidate. This closes the feedback loop: production failures become the seed data for the next mining cycle.

### Temporal Supersession

Invariant confidence decays over time according to:

```
confidence(t) = base_confidence × 0.5^(elapsed / half_life)
```

When a new invariant contradicts an existing one, `supersede()` marks the older one as stale rather than deleting it — the full history is preserved for audit purposes. Security-critical invariants are configured with a longer half-life than general behavioral invariants.

---

## Typical Workflow

**First use on a new module:**

```bash
# Step 1: Run a full mining cycle (Tier 1 will run; Tier 2 needs traces)
nightjar immune run src/payment.py --card .card/payment.card.md

# Step 2: Collect traces by exercising the module
nightjar immune collect src/payment.py

# Step 3: Run again — now Tier 2 (Daikon) has trace data
nightjar immune run src/payment.py --card .card/payment.card.md

# Step 4: Check what was found
nightjar immune status
```

**Iterative improvement (run after each deployment):**

```bash
# Collect traces from the latest run (if your module has a main() or __main__ block)
nightjar immune collect src/payment.py

# Mine and apply new invariants
nightjar immune run src/payment.py --card .card/payment.card.md
```

**Targeting a specific function:**

```bash
nightjar immune run src/auth.py \
  --function validate_token \
  --card .card/auth.card.md
```

**Only running LLM-based mining (fast, no tracing required):**

```bash
nightjar immune run src/payment.py --tier 1 --card .card/payment.card.md
```

---

## Network Effect (Planned)

The immune system is designed for a future multi-tenant network effect:

- **Structural abstraction** strips PII and converts invariants to type-level patterns before any sharing
- **Differential privacy** (Laplace mechanism via OpenDP) protects tenant counts
- **Herd immunity**: invariants confirmed by 50+ independent tenants at >95% confidence are promoted to the universal pattern library and applied to all new projects automatically
- **Cross-tenant sharing** means common API patterns (e.g., `amount > 0` for payment functions) are discovered faster than any single tenant could mine them alone

This is not yet active. The groundwork (structural abstraction, confidence tracking) is in place.

---

## Troubleshooting

**"Immune system dependency not installed"**
Install the optional dependency group: `pip install "nightjar[immune]"`

**"Could not import a callable from source"**
The collect and run commands need to import your module. Ensure the module's directory is importable (no missing deps, no import-time side effects that fail). Use `--function <name>` to target a specific function if the module lacks a `main()` entry point.

**Tier 2 always shows 0 invariants**
Tier 2 requires runtime traces. Run `nightjar immune collect <src>` first to populate the trace database, then re-run `nightjar immune run`.

**All candidates rejected**
This is normal on sparse traces. More diverse call patterns produce better invariants. Try calling your function with edge-case inputs, or use `--tier 1` for LLM-only mining which requires no traces.

**Verified count is much lower than merged count**
CrossHair or Hypothesis found a counterexample for the rejected candidates. This is the system working correctly — it means those candidates were not actually invariants of your function. Inspect the rejected candidates in `.card/immune.db` for debugging hints.
