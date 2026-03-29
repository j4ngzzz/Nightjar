---
title: Nightjar vs Pyright — Type Correctness vs Behavioral Proof
description: Pyright is the fastest and most accurate Python type checker. Nightjar proves what types can't — that your code behaves correctly for all possible inputs, not just typed ones.
slug: vs-pyright
competitor: Pyright
competitor_version: "Pyright 1.1.x (Microsoft, 2025)"
version_checked: "2026-03-29"
---

# Nightjar vs Pyright

## Types guarantee shape. Proofs guarantee behavior.

Pyright (v1.1.x, Microsoft, 2025) is the state-of-the-art Python type checker — faster than mypy, more accurate for modern Python patterns, and deeply integrated into VS Code via Pylance. If you care about type safety in Python, Pyright is the right tool for the job.

Nightjar and Pyright solve different problems. Pyright verifies that your code handles values of the correct *type*. Nightjar verifies that your code produces correct *behavior* — that invariants hold across all possible values, not just correctly-typed ones.

> **The gap:** Pyright confirms that `process_payment(amount: Decimal) -> Receipt` receives a `Decimal` and returns a `Receipt`. Nightjar proves that the `Receipt.total` field always equals `amount * (1 + tax_rate)`, that `amount > 0` is enforced before any side effect, and that `tax_rate` is never negative — for every `Decimal` value, not just the ones in your tests.

---

## What Pyright Does Well

Pyright (1.1.x) is Microsoft's investment in making Python type-safe at scale, and it shows:

- **Speed**: Pyright is written in TypeScript/Node.js and is significantly faster than mypy on large codebases. Incremental analysis and language server mode provide sub-second feedback in VS Code.
- **Accuracy**: Pyright consistently scores higher than mypy on Python typing conformance suites. It handles complex generics, TypeVar bounds, ParamSpec, TypeGuard, and modern PEP-typed constructs that mypy still struggles with.
- **Pylance integration**: Pyright powers the Pylance VS Code extension, used by millions of Python developers. Type errors appear as squiggles in real time, not just at CI time.
- **Strict mode**: `typeCheckingMode: "strict"` enforces exhaustive type annotations and catches a wide class of type errors, including missing return type annotations, untyped function parameters, and implicit `Any` types.
- **Granular configuration**: `pyrightconfig.json` gives fine-grained control over which checks run — turn on specific rules per-directory, handle stubs, configure venv.
- **Type stubs**: Pyright uses `.pyi` stub files and lazy type inference to handle packages without inline type annotations.
- **Regular release cadence**: Monthly releases with new features and Python version support tracking closely behind PEP ratification.
- **Corporate backing**: Microsoft's dedicated team means sustained development, not community-dependent maintenance.

---

## Where Pyright Hits Its Limits

Pyright is excellent at what it does. What it does is type checking — verifying that values flow through your program with consistent types. This is one dimension of correctness, not all of it.

**Types don't describe behavior.** `def calculate_fee(amount: Decimal, rate: Decimal) -> Decimal` typechecks correctly whether it multiplies or divides. Whether it returns `amount * rate` or `amount / (1 - rate)` — both are type-correct. Which one is behaviorally correct depends on what the function is *supposed* to do, which is expressed in a behavioral contract, not a type signature.

**Type-correct code can be fundamentally wrong.** Every bug Nightjar found in its survey of 34 packages was type-correct. The litellm budget reset bug (`created_at: float = time.time()` evaluated once at import time) is perfectly typed. The ENS name collision bug in web3.py is type-correct. The JWT expiry bypass in fastmcp is type-correct. Pyright would pass all of them.

**Type `bool` is `True` or `False`, but behavioral bounds are richer.** Consider `def transfer(amount: Decimal) -> None`. Pyright knows `amount` is a `Decimal`. Nightjar can prove that `amount > 0` before the transfer executes, that the account balance never goes negative, and that the transaction is atomic. These are behavioral properties that no type system expresses.

**No property-based testing.** Pyright performs static analysis only — it never runs the code. It cannot discover that your function fails for `Decimal('NaN')` or `Decimal('Infinity')` because it doesn't generate test inputs.

**No formal proof.** Type narrowing is not proof. `isinstance(x, int)` narrows the type; it does not prove that `x > 0`. Dafny's `requires x > 0` is a formal precondition that the verifier checks at every call site and is part of the function's mathematical contract.

**No AI-generated code verification layer.** Pyright checks that LLM-generated code is correctly typed — a useful check that Nightjar does not replace. But LLMs reliably write type-correct code. The bugs they introduce are behavioral, not typographic.

---

## Feature Comparison

| Feature | Nightjar | Pyright |
|---------|----------|---------|
| **Type correctness** | Partial (Pydantic schema, Stage 2) | Yes — best-in-class |
| **Behavioral invariant proving** | Yes — all inputs, Stage 3 + 4 | No |
| **Property-based testing** | Yes — Hypothesis, Stage 3 | No |
| **Symbolic execution** | Yes — CrossHair, Stage 2.5 | No |
| **Formal proof (Dafny)** | Yes — Stage 4 | No |
| **CEGIS repair loop** | Yes | No |
| **Spec-as-source** | Yes — `.card.md` | No spec artifact |
| **LLM code generation from spec** | Yes | No |
| **IDE integration** | `--format=vscode`, SARIF | First-class VS Code (Pylance) |
| **Speed** | Minutes (full); fast (scan/schema) | Sub-second (Pylance) / seconds (CLI) |
| **Incremental / watch mode** | `nightjar watch` | Yes — native |
| **Strict mode** | Configurable invariant tiers | `typeCheckingMode: strict` |
| **Python 3.13 support** | Yes | Yes |
| **Complex generic handling** | N/A | Superior to mypy |
| **Dependency CVE audit** | Yes — Stage 1 | No |
| **Immune system** | Yes | No |
| **CI integration** | GitHub Actions, pre-commit | GitHub Actions, pre-commit |
| **SARIF output** | Yes — `--output-sarif` | Yes |
| **Learning curve** | Low — plain English specs | Low — standard Python annotations |
| **Language support** | Python (primary) | Python only |
| **Runtime** | Python | Node.js (TypeScript) |
| **License** | AGPL-3.0 | MIT |

---

## When to Use Pyright vs Nightjar

**Use Pyright for:**
- Enforcing type safety across your Python codebase — Pyright is best-in-class for this
- Real-time type feedback in VS Code via Pylance — irreplaceable for developer experience
- Catching missing type annotations, incorrect generic usage, and type narrowing errors
- Any project where type correctness is the primary concern (type-heavy libraries, data pipelines)
- Fast CI type checking — Pyright is the fastest option

**Use Nightjar for:**
- Proving behavioral invariants that types cannot capture
- AI-generated code verification — types pass, behavior needs proving
- Business-critical properties: financial invariants, security guarantees, data integrity
- Formal compliance audit trails
- Any function where "type-correct" is not enough and "behaviorally-correct for all inputs" is required

**The practical answer for most teams:** Use both. They are genuinely complementary — Pyright covers the type dimension, Nightjar covers the behavioral dimension. Neither replaces the other.

---

## Can They Work Together?

Yes — and this combination is the strongest Python quality baseline available for teams using AI coding tools.

**Recommended pre-commit setup:**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pyright
        name: Pyright type check
        entry: pyright
        language: system
        types: [python]
      - id: nightjar
        name: Nightjar behavioral proof
        entry: nightjar verify --fast
        language: system
        pass_filenames: false
```

**In CI:**

```yaml
# .github/workflows/verify.yml
- name: Type check (Pyright)
  run: pyright src/

- name: Behavioral proof (Nightjar)
  run: nightjar verify
  env:
    NIGHTJAR_MODEL: claude-sonnet-4-6
```

**The division of responsibilities:**

| Check | Tool | What it guarantees |
|-------|------|-------------------|
| `amount: Decimal` is actually a `Decimal` | Pyright | Type shape |
| `amount > 0` before debit | Nightjar | Behavioral precondition |
| `receipt.total == amount * (1 + rate)` always | Nightjar | Behavioral postcondition |
| Return type is `Receipt` | Pyright | Type shape |
| No negative balances in any code path | Nightjar | Invariant |

**A note on the new Python type checker landscape (2025):** Microsoft's `ty`, Astral's `refly`, and other new entrants are challenging Pyright's dominance. All of them are type checkers — faster, more accurate type checkers. None of them prove behavioral correctness. Nightjar's value proposition is independent of which type checker you use.

---

## Get Started with Nightjar

```bash
pip install nightjar-verify
nightjar scan app.py           # extract behavioral contracts from type-annotated code
nightjar verify                # prove behavioral invariants (Pyright handles types)
nightjar verify --format=vscode  # inline behavioral proof errors in VS Code
```

[Quickstart →](../docs/quickstart) · [VS Code integration →](../docs/tutorials/vscode) · [All comparisons →](../compare)
