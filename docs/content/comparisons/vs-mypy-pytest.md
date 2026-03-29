---
title: Nightjar vs mypy + pytest — The Standard Python Stack vs Behavioral Proof
description: mypy proves types. pytest proves behavior for inputs you thought of. Nightjar proves behavior for all inputs — including the ones you didn't.
slug: vs-mypy-pytest
competitor: mypy + pytest
competitor_version: "mypy 1.16 / pytest 8.x (2025)"
version_checked: "2026-03-29"
---

# Nightjar vs mypy + pytest

## Types are correct. Tests pass. The bug ships anyway.

mypy (v1.16, 2025) and pytest are the standard Python quality stack. If you write Python professionally, you almost certainly use both. mypy catches type errors without running your code. pytest runs your code against the inputs you thought of. Together, they're the closest thing Python has to an industry-standard quality baseline.

But Nightjar finds bugs that pass both. Not because mypy or pytest are bad — they're excellent — but because they answer different questions.

> **The gap:** mypy proves `transfer_funds(amount: float) -> None` receives the right type. pytest proves it works for the values in `test_transfer_funds.py`. Nightjar proves it works for every float — including `-0.001`, `float('inf')`, and `1e308`.

---

## What mypy + pytest Does Well

**mypy (1.16)** is the reference Python type checker, now on a rapid release cadence with 2025 updates including:
- Full support for Python 3.13 type statements
- Faster incremental type checking
- Improved inference for complex generics and TypeVar bounds
- Strict mode (`--strict`) that enforces exhaustive type annotations
- Integration with virtually every Python IDE, linter, and CI tool
- A 20+ year track record and 10M+ monthly downloads

**pytest (8.x)** is the dominant Python test framework:
- Declarative test discovery via naming conventions — no boilerplate
- Parametrize fixtures for data-driven tests
- Plugins ecosystem: `pytest-cov`, `pytest-xdist`, `pytest-asyncio`, hundreds more
- Excellent error messages with contextual diffs
- Compatible with `unittest`, `doctest`, and most testing approaches
- Used by virtually every major Python project

Together, mypy + pytest provide:
- Type-level correctness (catch `str` where `int` expected)
- Regression coverage for known-good and known-bad inputs
- Fast CI feedback (seconds for type checking, minutes for full test suite)
- Industry-standard toolchain that every Python developer knows

---

## Where mypy + pytest Hit Their Limits

Both tools share a fundamental limitation: they only know what you told them.

**mypy checks types, not behavior.** `def transfer(amount: float) -> None` typechecks correctly whether it adds or subtracts `amount`, whether it handles `NaN`, whether it clamps at zero or overflows. Types describe the *shape* of data, not what the function does with it. A function that violates its behavioral contract while passing all type checks is indistinguishable from a correct function to mypy.

**pytest tests the inputs you thought to test.** Your test suite covers the code paths you imagined. It does not cover the input space you didn't imagine — the off-by-one, the sign reversal, the empty list, the Unicode boundary, the concurrent modification. Tests are samples; they cannot prove absence of bugs.

**The coverage illusion.** 100% line coverage does not mean 100% behavioral correctness. It means every line executed at least once with your test inputs. A function with a subtle invariant violation on a narrow input range can have 100% coverage and still be wrong.

**AI-generated code breaks both assumptions.** LLMs write type-correct code (mypy passes) and structurally plausible code (casual test review is positive). The bugs that appear are logic-level invariant violations — the exact class of error that neither mypy nor pytest is designed to catch. In Nightjar's survey of 34 packages, every confirmed bug passed all type checks and all existing tests.

**No spec artifact.** Neither mypy nor pytest produces a machine-checkable artifact expressing what the code *should* do. Types express structure. Tests express behavior for specific inputs. Neither is a contract that can be formally verified.

**No formal proof.** Even a comprehensive pytest suite with Hypothesis integration is probabilistic — Hypothesis generates many inputs but cannot prove that no violating input exists. Formal proof (Dafny/CrossHair) can.

---

## Feature Comparison

| Feature | Nightjar | mypy + pytest |
|---------|----------|---------------|
| **Type correctness** | Partial (Pydantic schema, Stage 2) | Yes — mypy, full PEP 484 |
| **Regression testing (known inputs)** | No (separate concern) | Yes — pytest |
| **Property-based testing** | Yes — Hypothesis, Stage 3, 1000+ examples | Optional (`hypothesis` plugin) |
| **Symbolic execution (all inputs)** | Yes — CrossHair, Stage 2.5 | No |
| **Formal proof (unbounded)** | Yes — Dafny, Stage 4 | No |
| **CEGIS repair loop** | Yes — auto-fix on failure | No |
| **Spec-as-source** | Yes — `.card.md` | No spec artifact |
| **LLM code generation from spec** | Yes | No |
| **Behavioral invariant proving** | Yes | Tests sample; proof proves |
| **Dependency CVE audit** | Yes — Stage 1 | No (separate tools needed) |
| **AI-generated code verification** | Designed for it | Not designed for it |
| **IDE integration** | `--format=vscode`, `--output-sarif` | First-class (mypy), standard (pytest) |
| **Speed** | Fast scan; minutes for full proof | Seconds (mypy); fast to minutes (pytest) |
| **Learning curve** | Low — plain English specs | Low — standard Python |
| **Immune system** | Yes — grows invariants from runtime | No |
| **Confidence score** | Yes — graduated, with mathematical bounds | Pass/Fail |
| **EU CRA compliance trail** | Yes — `nightjar ship` generates cert | No |
| **License** | AGPL-3.0 | MIT (mypy) / MIT (pytest) |

---

## When to Use mypy + pytest vs Nightjar

**Keep using mypy + pytest for:**
- Type safety enforcement — mypy is best-in-class and irreplaceable for this
- Regression testing with human-authored examples — tests document expected behavior and prevent regressions
- Fast pre-commit checks — mypy runs in seconds
- Any language correctness concern that is fundamentally about types, not behavior

**Add Nightjar when:**
- You generate code with AI tools and need mathematical verification beyond type checking
- You have behavioral invariants that tests sample but cannot prove (financial bounds, security properties, data integrity)
- You need a compliance trail showing behavioral contracts were formally verified
- You want Hypothesis running at 1000+ examples automatically, without writing test functions by hand
- You want the confidence that a verified function has *no* counterexample, not just *none found so far*

**The practical answer:** Run mypy + pytest + Nightjar together. They are not competing — they are complementary layers. Types tell you the shape is right. Tests tell you the behavior matches your examples. Nightjar tells you the behavior matches the spec for all inputs.

---

## Can They Work Together?

Yes — this is the recommended Python quality stack for teams using AI codegen.

```
mypy     →  Type correctness (seconds)
pytest   →  Regression coverage (minutes)
nightjar →  Behavioral proof (minutes)
```

**In CI:**

```yaml
# .github/workflows/verify.yml
- name: Type check (mypy)
  run: mypy src/ --strict

- name: Unit tests (pytest)
  run: pytest tests/unit/ -v

- name: Behavioral proof (Nightjar)
  run: nightjar verify
```

**pytest integration:** Nightjar has a `--nightjar` flag for pytest that runs verification as a test phase:

```bash
pytest --nightjar tests/
# Verification stages appear as test results in pytest output
```

**mypy + Nightjar:** mypy checks that the generated code's type annotations are correct. Nightjar checks that the function body satisfies its behavioral contracts. The two checks are independent and non-redundant: a function can pass mypy and fail Nightjar (or vice versa).

**Hypothesis + Nightjar:** If you already use Hypothesis, Nightjar's Stage 3 runs Hypothesis internally. You don't need to write `@given` decorators — Nightjar generates and runs the property tests from your `.card.md` spec. Your existing Hypothesis tests still run in pytest and complement Nightjar's generated tests.

---

## Get Started with Nightjar

```bash
pip install nightjar-verify
nightjar scan app.py           # extract behavioral contracts from your code
nightjar verify                # run 6 verification stages
pytest --nightjar tests/       # integrate verification into your test run
```

[Quickstart →](../docs/quickstart) · [pytest integration guide →](../docs/tutorials/pytest-integration) · [All comparisons →](../compare)
