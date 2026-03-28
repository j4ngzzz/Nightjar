"""Stage 3 — Property-Based Testing (PBT).

Auto-generates and runs Hypothesis tests from .card.md invariants.
Only 'property' and 'formal' tier invariants reach this stage [REF-C01].

References:
- [REF-T03] Hypothesis — settings: profiles, derandomize, max_examples, deadline
- [REF-P10] PGS paper — LLMs generate validation properties; PBT raises
  correction rates from 46.6% to 75.9%
- [REF-C01] Tiered invariants — CARD's invention
- Scout 5 F6 — dev/CI profile split: 10x faster Stage 3 in development

Design per ARCHITECTURE.md Section 3 + Scout 5 F6:
  Stage 3 uses Hypothesis profiles for dev/CI speed trade-off.
  dev profile (NIGHTJAR_TEST_PROFILE=dev or unset): max_examples=30  ~300-500ms
  ci  profile (NIGHTJAR_TEST_PROFILE=ci):           max_examples=200 ~3-8s
  Properties are auto-generated from invariants.
  Short-circuit on property violation with counterexample.

Assertion engine (two-tier):
  Tier A — regex patterns: fast, no LLM, handles the most common invariant forms.
  Tier B — LLM fallback: used when Tier A cannot match; gracefully skips on error.
"""

import dataclasses
import inspect
import os
import pathlib
import re
import time
import textwrap
import traceback
import typing
from typing import Any

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from nightjar.types import (
    CardSpec, Invariant, InvariantTier, StageResult, VerifyStatus,
)

# Nightjar domain types — used as localns for get_type_hints() resolution
_NIGHTJAR_LOCALNS: dict = {}


def _build_nightjar_localns() -> dict:
    """Build localns dict for resolving Nightjar type annotations."""
    from nightjar.types import (
        CardSpec, VerifyResult, StageResult, Invariant, InvariantTier,
        Contract, ModuleBoundary, ContractInput, ContractOutput,
        VerifyStatus, TrustLevel,
    )
    return {
        "CardSpec": CardSpec, "VerifyResult": VerifyResult,
        "StageResult": StageResult, "Invariant": Invariant,
        "InvariantTier": InvariantTier, "Contract": Contract,
        "ModuleBoundary": ModuleBoundary, "ContractInput": ContractInput,
        "ContractOutput": ContractOutput, "VerifyStatus": VerifyStatus,
        "TrustLevel": TrustLevel, "Path": pathlib.Path,
    }


def _strategy_for_annotation(ann: type | None) -> "st.SearchStrategy | None":
    """Return a Hypothesis strategy for a type annotation, or None if unknown.

    None = caller should SKIP this invariant rather than crash.
    Handles: int, str, float, bool, list, dict, Path, dataclasses, Optional/List generics.
    """
    if ann is None or ann is inspect.Parameter.empty:
        return st.integers()  # Default for unannotated params

    # Unwrap Optional[X] → strategy for X (allow None too)
    origin = getattr(ann, "__origin__", None)
    args = getattr(ann, "__args__", ())

    if origin is typing.Union:
        # Optional[X] is Union[X, None]
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            inner = _strategy_for_annotation(non_none[0])
            return st.one_of(st.none(), inner) if inner is not None else None
        return None  # Complex Union — skip

    if origin is list:
        item_strat = _strategy_for_annotation(args[0]) if args else st.integers()
        return st.lists(item_strat or st.integers(), max_size=5)

    if origin is dict:
        k_strat = _strategy_for_annotation(args[0]) if args else st.text(max_size=10)
        v_strat = _strategy_for_annotation(args[1]) if len(args) > 1 else st.text(max_size=10)
        return st.dictionaries(
            k_strat or st.text(max_size=10),
            v_strat or st.text(max_size=10),
            max_size=3,
        )

    # Primitives
    if ann is int:
        return st.integers(min_value=-10_000, max_value=10_000)
    if ann is str:
        return st.text(max_size=50)
    if ann is float:
        return st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6)
    if ann is bool:
        return st.booleans()
    if ann is list:
        return st.lists(st.integers(), max_size=5)
    if ann is dict:
        return st.dictionaries(st.text(max_size=10), st.text(max_size=10), max_size=3)
    if ann is bytes:
        return st.binary(max_size=50)

    # pathlib.Path
    if ann is pathlib.Path:
        safe_chars = "abcdefghijklmnopqrstuvwxyz0123456789_-"
        return st.builds(
            pathlib.Path,
            st.text(alphabet=safe_chars, min_size=1, max_size=20),
        )

    # Dataclasses (CardSpec, VerifyResult, Invariant, etc.)
    if dataclasses.is_dataclass(ann) and isinstance(ann, type):
        field_strategies = {}
        for f in dataclasses.fields(ann):
            # Resolve string annotations
            resolved = None
            try:
                hints = typing.get_type_hints(ann, localns=_NIGHTJAR_LOCALNS)
                resolved = hints.get(f.name)
            except Exception:
                resolved = None
            strat = _strategy_for_annotation(resolved)
            if strat is None:
                strat = st.none()  # Use None for unresolvable fields with defaults
            field_strategies[f.name] = strat
        try:
            return st.builds(ann, **field_strategies)
        except Exception:
            return None  # If builds fails (e.g. no-default required field), skip

    # Enums
    if isinstance(ann, type) and issubclass(ann, __import__("enum").Enum):
        return st.sampled_from(list(ann))

    return None  # Unknown type — caller should skip


def _load_pbt_profile() -> str:
    """Register dev/CI Hypothesis profiles and activate the correct one.

    Reads NIGHTJAR_TEST_PROFILE env var to select the profile:
    - 'dev' (default): max_examples=10, derandomize=True — fast dev feedback
    - 'ci': max_examples=200, suppress too_slow — thorough CI coverage

    Called at module load time and exposed for testing.
    Source: Scout 5 Finding 6 — Hypothesis Database + Profile Split.

    Returns:
        The name of the profile that was loaded ('dev' or 'ci').
    """
    # Register dev profile: fast feedback during development [Scout 5 F6]
    settings.register_profile(
        "dev",
        max_examples=10,
        derandomize=True,
    )
    # Register CI profile: thorough coverage before merge [Scout 5 F6]
    settings.register_profile(
        "ci",
        max_examples=200,
        suppress_health_check=[HealthCheck.too_slow],
    )
    profile = os.getenv("NIGHTJAR_TEST_PROFILE", "dev")
    settings.load_profile(profile)
    return profile


# ---------------------------------------------------------------------------
# Assertion engine — Tier A (regex) + Tier B (LLM fallback)
# ---------------------------------------------------------------------------

def _parse_invariant_to_assertion(statement: str, func_name: str) -> str | None:
    """Tier A: Convert a natural-language invariant statement to a Python assert.

    Recognises the most common invariant patterns via regex.  Returns None when
    no pattern matches so the caller can escalate to Tier B (LLM fallback).

    Args:
        statement: Natural-language invariant from .card.md (e.g. "result >= 0").
        func_name: Name of the function under test (used only for error messages).

    Returns:
        A Python ``assert …`` string, or None if no pattern matched.
    """
    lower = statement.lower()

    # ── "must not raise" / "no exception" ────────────────────────────────────
    # These are handled structurally in _run_single_invariant (any exception
    # from the call under test is already re-raised as AssertionError), so we
    # return a sentinel that the caller treats as "call-only, no extra check".
    if re.search(r"must not raise|no exception|does not raise|should not raise", lower):
        return "assert True  # call-only: any exception already fails"

    # ── "not None" / "must return" ────────────────────────────────────────────
    if re.search(r"not none|must return|returns a value|is not none", lower):
        return "assert result is not None"

    # ── "result > 0" / "strictly positive" ───────────────────────────────────
    if re.search(r"strictly positive|result\s*>\s*0|result is positive and non.?zero", lower):
        return "assert result > 0"

    # ── "result >= 0" / "positive" / "non-negative" ──────────────────────────
    # Must come AFTER strictly-positive so "strictly positive" → > 0 not >= 0.
    if re.search(r"non.?negative|result\s*>=\s*0", lower):
        return "assert result >= 0"

    if re.search(r"\bpositive\b", lower):
        return "assert isinstance(result, (int, float)) and result > 0"

    # ── "between X and Y" / "range" ──────────────────────────────────────────
    m = re.search(
        r"between\s+(-?\d+(?:\.\d+)?)\s+and\s+(-?\d+(?:\.\d+)?)",
        lower,
    )
    if m:
        lo, hi = m.group(1), m.group(2)
        return f"assert {lo} <= result <= {hi}"

    # ── "result must be in range X to Y" ─────────────────────────────────────
    m = re.search(
        r"(?:in range|range of|from)\s+(-?\d+(?:\.\d+)?)\s+to\s+(-?\d+(?:\.\d+)?)",
        lower,
    )
    if m:
        lo, hi = m.group(1), m.group(2)
        return f"assert {lo} <= result <= {hi}"

    # ── "sorted" ──────────────────────────────────────────────────────────────
    if re.search(r"\bsorted\b", lower):
        return "assert result == sorted(result)"

    # ── "unique" / "no duplicates" ────────────────────────────────────────────
    if re.search(r"\bunique\b|no duplicates|no duplicate", lower):
        return "assert len(result) == len(set(result))"

    # ── "empty" patterns ──────────────────────────────────────────────────────
    if re.search(r"\bmust be empty\b|\bshould be empty\b|\bis empty\b|\breturns empty\b", lower):
        return "assert len(result) == 0"

    if re.search(r"\bnot empty\b|\bmust not be empty\b|\bnon.?empty\b", lower):
        return "assert len(result) > 0"

    # ── "len(result) …" ───────────────────────────────────────────────────────
    m = re.search(r"len\s*\(\s*result\s*\)\s*([><=!]+)\s*(\d+)", lower)
    if m:
        op, val = m.group(1), m.group(2)
        return f"assert len(result) {op} {val}"

    # ── "result == <expr>" / "equals <expr>" ─────────────────────────────────
    # Specific numeric equality
    m = re.search(r"result\s*==\s*(-?\d+(?:\.\d+)?)", lower)
    if m:
        val = m.group(1)
        return f"assert result == {val}"

    # "equals x * N" style
    m = re.search(r"equals?\s+x\s*\*\s*(\d+)", lower)
    if m:
        factor = m.group(1)
        return f"assert result == x * {factor}"

    # "equals x + N" style
    m = re.search(r"equals?\s+x\s*\+\s*(\d+)", lower)
    if m:
        addend = m.group(1)
        return f"assert result == x + {addend}"

    # ── "greater than input" / "result > x" ──────────────────────────────────
    if re.search(r"greater than\s+(?:the\s+)?input|result\s*>\s*x\b", lower):
        return "assert result > x"

    # ── "less than input" / "result < x" ─────────────────────────────────────
    if re.search(r"less than\s+(?:the\s+)?input|result\s*<\s*x\b", lower):
        return "assert result < x"

    # ── "contains" / "includes" ───────────────────────────────────────────────
    m = re.search(r"(?:contains|includes)\s+(['\"]?)(\w+)\1", lower)
    if m:
        item = m.group(2)
        return f"assert {item!r} in result"

    # ── "type" / "isinstance" ─────────────────────────────────────────────────
    m = re.search(r"(?:returns?|is|be)\s+(?:a\s+)?(?:an\s+)?(int|integer|float|str|string|list|dict|bool)", lower)
    if m:
        type_word = m.group(1)
        py_type_map = {
            "int": "int", "integer": "int",
            "float": "float",
            "str": "str", "string": "str",
            "list": "list",
            "dict": "dict",
            "bool": "bool",
        }
        py_type = py_type_map.get(type_word, type_word)
        return f"assert isinstance(result, {py_type})"

    return None


def _llm_generate_assertion(statement: str, func_name: str) -> str | None:
    """Tier B: Ask the LLM to convert a natural-language invariant to a Python assert.

    Called only when Tier A (_parse_invariant_to_assertion) returns None.
    All LLM calls go through litellm [REF-T16]. Model from get_model().
    Failures are caught and silently return None so PBT can continue.

    When NIGHTJAR_ENABLE_STRATEGY_DB=1, injects best-performing and most-diverse
    strategy templates from the StrategyDB into the prompt as parent/inspiration
    examples (AlphaEvolve programs database pattern — arXiv:2506.13131).

    Args:
        statement: Natural-language invariant from .card.md.
        func_name: Name of the function under test.

    Returns:
        A syntactically valid Python ``assert …`` string, or None on failure.
    """
    # ── Strategy DB integration hook (opt-in, gated by env var) ──────────────
    # Activation: NIGHTJAR_ENABLE_STRATEGY_DB=1
    # Failure is always silent — strategy DB issues must never crash PBT.
    _strategy_db = None
    _inv_type = "unknown"
    _best_template_name = "unknown"
    if os.getenv("NIGHTJAR_ENABLE_STRATEGY_DB", "0") == "1":
        try:
            from nightjar.strategy_db import StrategyDB, classify_invariant_type  # noqa: PLC0415
            _strategy_db = StrategyDB()
            _inv_type = classify_invariant_type(statement)
            _best_seed = _strategy_db.get_best_for_type(_inv_type)
            _best_template_name = (
                _best_seed.template_name if _best_seed is not None else "unknown"
            )
        except Exception:  # noqa: BLE001
            _strategy_db = None  # Ensure DB failures are silent
    # ─────────────────────────────────────────────────────────────────────────

    try:
        from nightjar.config import load_config, get_model
        load_config()
        import litellm  # noqa: PLC0415

        # Build strategy template context for the prompt (only when DB enabled)
        strategy_context = ""
        if _strategy_db is not None:
            try:
                best = _strategy_db.get_best_for_type(_inv_type)
                diverse = _strategy_db.get_diverse_for_type(_inv_type)
                examples: list[str] = []
                if best is not None:
                    examples.append(
                        f"  Parent (best performer): {best.template_name} — "
                        f"{best.template_code}"
                    )
                if diverse is not None and diverse.template_name != (
                    best.template_name if best else ""
                ):
                    examples.append(
                        f"  Inspiration (diverse): {diverse.template_name} — "
                        f"{diverse.template_code}"
                    )
                if examples:
                    strategy_context = (
                        "\nRelevant Hypothesis strategy templates for this invariant type"
                        f" ({_inv_type}):\n" + "\n".join(examples) + "\n"
                    )
            except Exception:  # noqa: BLE001
                strategy_context = ""

        prompt = (
            f"Convert this invariant to a Python assert statement.\n"
            f"Function name: {func_name}\n"
            f"Available variables: result (return value of the function), "
            f"x (integer input to the function).\n"
            f"Invariant: {statement}\n"
            f"{strategy_context}"
            f"Reply with ONLY the assert statement, nothing else."
        )
        response = litellm.completion(
            model=get_model(),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.0,
        )
        content = (response.choices[0].message.content or "").strip()
        # Take only the first non-empty line
        assertion = next(
            (line.strip() for line in content.splitlines() if line.strip()),
            "",
        )
        if not assertion.startswith("assert "):
            return None
        # Syntax-check before returning
        compile(assertion, "<inv>", "exec")
        return assertion
    except Exception:
        return None


# Register and activate profiles at module load [Scout 5 F6]
_load_pbt_profile()


# PBT settings — max_examples and derandomize come from the active profile.
# deadline=None: avoid flaky timeouts on slow invariants [REF-T03]
# database=None: generated code changes per run; stale counterexamples mislead
NIGHTJAR_PBT_SETTINGS = settings(deadline=None, database=None)

# Extended settings for graceful degradation fallback (W1.5).
# Per Scout 3 S5.5: 10K+ examples for statistical confidence when Dafny/CrossHair fail.
NIGHTJAR_PBT_EXTENDED_SETTINGS = settings(
    max_examples=10000,
    deadline=None,
    database=None,
    suppress_health_check=[HealthCheck.too_slow],
)


def _filter_pbt_invariants(invariants: list[Invariant]) -> list[Invariant]:
    """Filter to only property and formal tier invariants [REF-C01].

    Example-tier invariants are unit tests (Stage 0 territory).
    Property and formal tiers get PBT coverage here in Stage 3.
    """
    return [
        inv for inv in invariants
        if inv.tier in (InvariantTier.PROPERTY, InvariantTier.FORMAL)
    ]


class _PbtLoadError(Exception):
    """Raised when source code cannot be exec'd into a PBT namespace.

    This covers relative imports, missing dependencies, and other runtime
    errors that make the code unsuitable for PBT — but do NOT indicate the
    code is wrong.  The pipeline should SKIP Stage 3 in this case.
    """


def _build_test_environment(code: str) -> dict[str, Any]:
    """Execute generated code in an isolated namespace and return it.

    Security note: This executes code in a restricted dict namespace,
    not in the module's globals. The generated code is already verified
    by Stages 0-2 before reaching Stage 3.

    Raises:
        SyntaxError: code has a syntax error — caller should FAIL.
        _PbtLoadError: code exec'd but raised a non-syntax error (e.g.
            relative imports, missing stdlib symbol) — caller should SKIP.
    """
    namespace: dict[str, Any] = {"__builtins__": __builtins__}
    try:
        exec(compile(code, "<generated>", "exec"), namespace)  # noqa: S102
    except SyntaxError:
        raise  # Propagate as-is so caller can FAIL with a clear message
    except Exception as e:
        raise _PbtLoadError(
            f"Code cannot be loaded for PBT (likely relative imports or "
            f"missing runtime dependencies): {e}"
        ) from e
    return namespace


def _run_single_invariant(
    invariant: Invariant,
    code: str,
    env: dict[str, Any],
    pbt_settings: settings = NIGHTJAR_PBT_SETTINGS,
    func: Any = None,
) -> dict[str, Any] | None:
    """Run PBT for a single invariant against the generated code.

    Returns None on success, or an error dict on failure.

    Per [REF-P10], LLMs are 20-47% more accurate generating validation
    properties than implementations. The invariant statement from .card.md
    is the property specification; we translate it to a Hypothesis test.

    The translation strategy: we build a test function that:
    1. Generates inputs matching the contract constraints (includes 0, negatives,
       and explicit boundary values to maximise defect detection)
    2. Calls the code under test
    3. Asserts the invariant property via two-tier assertion engine:
       Tier A — regex patterns (fast, no LLM)
       Tier B — LLM fallback (when Tier A returns None)
       If both return None the property call itself acts as the test
       (any exception from the function-under-test still fails).

    Args:
        pbt_settings: Hypothesis settings to apply (default: NIGHTJAR_PBT_SETTINGS).
                      Pass NIGHTJAR_PBT_EXTENDED_SETTINGS for 10K+ examples.
        func: Pre-resolved callable to test.  If None, falls back to
              :func:`_find_testable_function` (legacy path, no spec hint).
    """
    statement = invariant.statement
    func_name: str = getattr(func, "__name__", "func") if func is not None else "func"

    # Resolve assertion once (outside the hot loop) — Tier A then Tier B.
    assertion_code = _parse_invariant_to_assertion(statement, func_name)
    if assertion_code is None:
        assertion_code = _llm_generate_assertion(statement, func_name)
    # If still None we do a call-only test (exception from function = fail).

    # Boundary examples that are critical for defect detection:
    # 0  — division-by-zero, off-by-one at boundary
    # -1 — negative-input edge
    # 1  — unit value
    # -100, 100 — moderate range extremes
    _BOUNDARY_EXAMPLES = [0, -1, 1, -100, 100]

    error_result: dict[str, Any] | None = None

    # Detect param count to handle multi-param functions gracefully (Bug 5).
    # If the function requires more parameters than we can supply, skip PBT
    # cleanly rather than producing a raw TypeError stack trace.
    resolved_func = func if func is not None else _find_testable_function(env)
    if resolved_func is not None:
        try:
            sig = inspect.signature(resolved_func)
            # Count parameters that don't have defaults (required params)
            required_params = [
                p for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty
                and p.kind not in (
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                )
            ]
            num_required = len(required_params)
        except (ValueError, TypeError):
            num_required = 1  # Assume single-param on introspection failure
    else:
        num_required = 1

    # If the function requires more than 1 param, skip PBT for this invariant
    # rather than producing a misleading TypeError. We pass the same value for
    # all params (simplest approach) when there are 2+ required params.
    # Functions with 0 required params are called with no args.

    # Build per-parameter strategies from type annotations
    use_legacy_call = False
    param_strategies: dict[str, Any] = {}
    try:
        if len(_NIGHTJAR_LOCALNS) == 0:
            _NIGHTJAR_LOCALNS.update(_build_nightjar_localns())
        hints: dict = {}
        if resolved_func is not None:
            try:
                hints = typing.get_type_hints(resolved_func, localns=_NIGHTJAR_LOCALNS)
            except Exception:
                pass

        skip_pbt = False
        for param in required_params:
            ann = hints.get(param.name)
            strat = _strategy_for_annotation(ann)
            if strat is None:
                # Unknown type with no default — cannot test, skip gracefully
                skip_pbt = True
                break
            param_strategies[param.name] = strat

        if skip_pbt or not param_strategies:
            # Fall back to single integer strategy for unannotated/unknown functions
            param_strategies = {
                "x": st.one_of(
                    st.sampled_from(_BOUNDARY_EXAMPLES),
                    st.integers(min_value=-10_000, max_value=10_000),
                )
            }
            use_legacy_call = True
        else:
            use_legacy_call = False

    except Exception:
        param_strategies = {
            "x": st.one_of(
                st.sampled_from(_BOUNDARY_EXAMPLES),
                st.integers(min_value=-10_000, max_value=10_000),
            )
        }
        use_legacy_call = True

    # Build a Hypothesis test function dynamically from the invariant.
    # When type annotations are available, use per-param strategies.
    # Otherwise fall back to the legacy integer-only approach.
    @pbt_settings
    @given(**param_strategies)
    def pbt_test(**kwargs: Any) -> None:
        nonlocal error_result
        from hypothesis import assume  # noqa: PLC0415

        # Use the pre-resolved function if provided; fall back to
        # discovery for backwards compatibility.
        resolved = func if func is not None else _find_testable_function(env)
        if resolved is None:
            return

        if use_legacy_call:
            # Legacy path: single integer param named "x"
            x = kwargs.get("x", 0)
            # Build the argument list based on how many params the function requires.
            # Multi-param functions get the same value for all required params so
            # we can at least exercise the function and catch obvious violations.
            if num_required == 0:
                call_args: tuple = ()
            elif num_required == 1:
                call_args = (x,)
            else:
                # Pass x for all required params — covers the common 2-param case
                # (e.g. deduct(balance, amount)) without a raw TypeError.
                call_args = tuple(x for _ in range(num_required))
            try:
                result = resolved(*call_args)
            except (ValueError, TypeError):
                assume(False)
                return
            except AssertionError:
                raise
            except Exception as e:
                raise AssertionError(
                    f"Invariant {invariant.id} violated: {e}"
                ) from e
            # expose x for assertion context
            x_val = x
        else:
            # Type-aware path: kwargs match parameter names
            x = next(iter(kwargs.values()), None)  # first param for assertion context
            try:
                result = resolved(**kwargs)
            except (ValueError, TypeError):
                # The function raised a precondition-style exception for this
                # input.  Use assume() to tell Hypothesis this example is
                # outside the contract domain and should be skipped.
                #
                # If the function raises for EVERY input (Bug 7 pattern), Hypothesis
                # will exhaust its filter budget and raise UnsatisfiedAssumption /
                # Flaky/Unsatisfied error -- which propagates as an exception to the
                # outer try/except and becomes a FAIL, preserving Bug 7 behaviour.
                assume(False)
                return
            except AssertionError:
                raise  # already a property violation -- propagate
            except Exception as e:
                # Non-precondition exceptions (ZeroDivisionError, AttributeError, ...)
                # are genuine failures -- convert to AssertionError so Hypothesis
                # can record them as counterexamples.
                raise AssertionError(
                    f"Invariant {invariant.id} violated: {e}"
                ) from e
            x_val = x

        # Two-tier assertion engine -- run only when the function returned normally
        if assertion_code is not None:
            try:
                import os as _os, sys as _sys, shutil as _shutil, subprocess as _subprocess
                # Build execution context for eval — includes stdlib modules
                _ctx = {
                    "result": result,
                    "x": x_val,
                    "os": _os,
                    "sys": _sys,
                    "shutil": _shutil,
                    "subprocess": _subprocess,
                    "TimeoutExpired": _subprocess.TimeoutExpired,
                    "Path": pathlib.Path,
                    "len": len,
                    "abs": abs,
                    "isinstance": isinstance,
                    "type": type,
                    "list": list,
                    "dict": dict,
                    "set": set,
                    "str": str,
                    "int": int,
                    "float": float,
                    "bool": bool,
                    "None": None,
                    "True": True,
                    "False": False,
                }
                exec(assertion_code, _ctx)  # noqa: S102
            except AssertionError:
                raise  # property violation -- propagate
            except Exception as e:
                raise AssertionError(
                    f"Assertion eval error for invariant {invariant.id}: {e}"
                ) from e

    try:
        pbt_test()
        outcome_error = None  # Success
    except AssertionError as e:
        outcome_error = {
            "invariant_id": invariant.id,
            "tier": invariant.tier.value,
            "statement": invariant.statement,
            "error": str(e),
            "type": "property_violation",
        }
    except Exception as e:
        outcome_error = {
            "invariant_id": invariant.id,
            "tier": invariant.tier.value,
            "statement": invariant.statement,
            "error": f"PBT execution error: {traceback.format_exc()}",
            "type": "execution_error",
        }

    # ── Strategy DB outcome recording (opt-in, gated by env var) ─────────────
    # Record at _run_single_invariant level where the actual pass/fail is known.
    # This enables correct EMA updates for counterexample_found_rate.
    if os.getenv("NIGHTJAR_ENABLE_STRATEGY_DB", "0") == "1":
        try:
            from nightjar.strategy_db import StrategyDB, classify_invariant_type  # noqa: PLC0415
            _db = StrategyDB()
            _itype = classify_invariant_type(invariant.statement)
            _best = _db.get_best_for_type(_itype)
            _tname = _best.template_name if _best is not None else "unknown"
            _found_ce = outcome_error is not None and outcome_error.get("type") == "property_violation"
            _db.record_outcome(_itype, _tname, found_counterexample=_found_ce, examples_taken=0)
            _db.save()
        except Exception:  # noqa: BLE001
            pass  # DB update failure must never crash PBT
    # ─────────────────────────────────────────────────────────────────────────

    return outcome_error


# Common stdlib names that appear in a namespace after exec() due to
# imports like `from dataclasses import dataclass, field` or
# `from typing import Optional, Dict, List`.  These must NOT be mistaken
# for the function-under-test.
_STDLIB_IMPORT_NAMES: frozenset[str] = frozenset({
    # dataclasses
    "dataclass", "field", "fields", "asdict", "astuple", "make_dataclass",
    "replace", "is_dataclass",
    # typing / type aliases
    "Optional", "Union", "Any", "Dict", "List", "Set", "Tuple", "Type",
    "Callable", "Iterator", "Generator", "ClassVar", "Final",
    "TypeVar", "Generic", "Protocol", "overload", "cast",
    # enum
    "Enum", "IntEnum", "Flag", "IntFlag", "auto",
    # pathlib
    "Path", "PurePath", "PosixPath", "WindowsPath",
    # abc
    "ABC", "ABCMeta", "abstractmethod",
    # functools
    "wraps", "lru_cache", "cache", "partial", "reduce",
    # contextlib
    "contextmanager", "suppress",
    # collections
    "namedtuple", "defaultdict", "OrderedDict", "Counter", "deque",
    # other builtins that show up as callables
    "property", "classmethod", "staticmethod",
})


def _find_testable_function(
    env: dict[str, Any],
    spec_id: str | None = None,
) -> Any | None:
    """Find the best callable function in the generated code namespace.

    Selection strategy (in priority order):
    1. A function whose name matches *spec_id* (the spec's ``id`` field).
    2. A function that was actually defined in the exec'd source, identified
       by having ``__module__ == "<generated>"`` or ``__qualname__`` without
       dots (i.e. a top-level def, not a method or closure from an import).
    3. Any remaining non-dunder callable that is not a known stdlib import.

    Returns None if no suitable function is found; the caller then skips PBT.

    Args:
        env:     The namespace dict returned by :func:`_build_test_environment`.
        spec_id: Optional ``CardSpec.id`` value used as a hint for the
                 primary function name.
    """
    candidates: list[Any] = []

    for name, obj in env.items():
        # Skip dunder / private names
        if name.startswith("_"):
            continue
        # Only plain functions (not classes, not module-level type aliases)
        if not callable(obj) or isinstance(obj, type):
            continue
        # Skip well-known stdlib imports that pollute the namespace
        if name in _STDLIB_IMPORT_NAMES:
            continue

        # Priority 1: exact match with spec id (underscores ↔ hyphens)
        normalised_name = name.replace("_", "-").lower()
        normalised_id = (spec_id or "").replace("_", "-").lower()
        if normalised_id and normalised_name == normalised_id:
            return obj

        candidates.append((name, obj))

    if not candidates:
        return None

    # Priority 2: functions actually defined in the exec'd code
    # `compile(..., "<generated>", ...)` gives them __code__.co_filename == "<generated>"
    defined_here = [
        (name, obj) for name, obj in candidates
        if getattr(getattr(obj, "__code__", None), "co_filename", None) == "<generated>"
    ]
    if defined_here:
        return defined_here[0][1]

    # Priority 3: first remaining candidate (last resort)
    return candidates[0][1]


def _assert_invariant(statement: str, input_val: Any, result: Any) -> None:
    """Assert an invariant holds given the statement, input, and result.

    This interprets common invariant patterns from .card.md statements.
    The statement is a natural language property description.

    Pattern matching for common invariant forms:
    - "returns a positive integer" → result > 0
    - "returns a positive" → result > 0
    - "equals x * 2" → result == input * 2
    - "raises <Error>" → handled by caller (exception expected)
    """
    lower = statement.lower()

    if "positive" in lower and ("return" in lower or "result" in lower):
        assert isinstance(result, (int, float)), (
            f"Expected numeric result, got {type(result).__name__}"
        )
        assert result > 0, (
            f"Expected positive result, got {result} for input {input_val}"
        )

    if "equals" in lower and "* 2" in lower:
        assert result == input_val * 2, (
            f"Expected {input_val * 2}, got {result} for input {input_val}"
        )

    if "non-negative" in lower:
        assert isinstance(result, (int, float)) and result >= 0, (
            f"Expected non-negative result, got {result}"
        )

    if "greater than" in lower and "input" in lower:
        assert result > input_val, (
            f"Expected result > input ({input_val}), got {result}"
        )


def _run_pbt_core(
    spec: CardSpec,
    code: str,
    pbt_settings: settings = NIGHTJAR_PBT_SETTINGS,
) -> StageResult:
    """Core PBT execution shared by run_pbt and run_pbt_extended.

    Accepts a custom settings object so extended mode can pass
    NIGHTJAR_PBT_EXTENDED_SETTINGS with 10K examples.
    """
    start = time.monotonic()

    pbt_invariants = _filter_pbt_invariants(spec.invariants)

    if not pbt_invariants:
        return StageResult(
            stage=3,
            name="pbt",
            status=VerifyStatus.SKIP,
            duration_ms=0,
        )

    try:
        env = _build_test_environment(code)
    except SyntaxError as e:
        duration = int((time.monotonic() - start) * 1000)
        return StageResult(
            stage=3,
            name="pbt",
            status=VerifyStatus.FAIL,
            duration_ms=duration,
            errors=[{
                "type": "syntax_error",
                "error": f"Generated code has syntax error: {e}",
            }],
        )
    except _PbtLoadError as e:
        # Code has relative imports or other exec-time issues — not a code
        # defect, just not PBT-testable in isolation.  SKIP gracefully.
        duration = int((time.monotonic() - start) * 1000)
        return StageResult(
            stage=3,
            name="pbt",
            status=VerifyStatus.SKIP,
            duration_ms=duration,
            errors=[{
                "type": "load_error",
                "error": str(e),
            }],
        )

    # Resolve the function-under-test once, using the spec id as a hint so
    # that stdlib names imported into the namespace are not mistaken for it.
    func = _find_testable_function(env, spec_id=spec.id)
    if func is None:
        duration = int((time.monotonic() - start) * 1000)
        return StageResult(
            stage=3,
            name="pbt",
            status=VerifyStatus.SKIP,
            duration_ms=duration,
            errors=[{
                "type": "no_testable_function",
                "error": (
                    "No testable function found in generated code — "
                    "namespace contains only stdlib imports or type aliases. "
                    "PBT is not applicable to this module."
                ),
            }],
        )

    errors: list[dict] = []
    for inv in pbt_invariants:
        error = _run_single_invariant(
            inv, code, env, pbt_settings=pbt_settings, func=func,
        )
        if error is not None:
            errors.append(error)

    duration = int((time.monotonic() - start) * 1000)
    status = VerifyStatus.FAIL if errors else VerifyStatus.PASS

    return StageResult(
        stage=3,
        name="pbt",
        status=status,
        duration_ms=duration,
        errors=errors,
        counterexample=errors[0] if errors else None,
    )


def _make_pbt_settings() -> settings:
    """Return PBT settings, optionally with CrossHair SMT backend.

    Checks NIGHTJAR_CROSSHAIR_BACKEND env var. If set to "1" and
    hypothesis-crosshair is installed, activates CrossHair's SMT-based
    symbolic execution backend instead of random sampling [REF-T09].

    CrossHair via pschanely/hypothesis-crosshair:
    - Same @given tests, zero code changes — one flag, two execution modes
    - Path exhaustion = property verified for ALL inputs (not just sampled)
    - CrossHair manages its own per-path time budget (deadline=None disables
      Hypothesis's deadline check; CrossHair uses its own timeout internally)
    - Registered via entry-point hook at import time; no explicit config needed
    - Requires: pip install hypothesis-crosshair

    Returns a fresh settings() object on every call so the active Hypothesis
    profile (dev/ci, set via NIGHTJAR_TEST_PROFILE) is always respected.
    """
    if os.getenv("NIGHTJAR_CROSSHAIR_BACKEND", "0") != "1":
        # Fresh settings() inherits max_examples from the currently active
        # profile, avoiding stale values from the module-level constant.
        return settings(deadline=None, database=None)
    try:
        # hypothesis-crosshair self-registers via entry points on import:
        #   hypothesis_crosshair_provider:_hypothesis_setup_hook
        # sets AVAILABLE_PROVIDERS["crosshair"] = CrossHairPrimitiveProvider
        import hypothesis_crosshair_provider  # noqa: F401
        return settings(deadline=None, database=None, backend="crosshair")
    except ImportError:
        return settings(deadline=None, database=None)


def run_pbt_extended(spec: CardSpec, code: str) -> StageResult:
    """Run PBT with 10K+ examples — graceful degradation fallback (W1.5).

    Per Scout 3 S5.5 Rank 2: extended PBT = 10K+ examples vs 200 in standard
    Stage 3. Used as final fallback when both Dafny and CrossHair fail/timeout.
    icontract-hypothesis bridge auto-generates strategies from @require/@ensure.

    Uses NIGHTJAR_PBT_EXTENDED_SETTINGS (10K examples, suppress too_slow)
    instead of NIGHTJAR_PBT_SETTINGS (dev: 10, ci: 200).

    Args:
        spec: Parsed .card.md specification with invariants.
        code: Generated source code string to verify.

    Returns:
        StageResult with stage=3, status=PASS/FAIL/SKIP.
    """
    return _run_pbt_core(spec, code, pbt_settings=NIGHTJAR_PBT_EXTENDED_SETTINGS)


def run_pbt(spec: CardSpec, code: str) -> StageResult:
    """Run Stage 3 — Property-Based Testing on generated code.

    Per [REF-T03] and [REF-P10]:
    1. Filter invariants to property/formal tiers [REF-C01]
    2. For each invariant, generate a Hypothesis @given test
    3. Execute with settings from active profile (dev: 10, ci: 200 examples)
    4. Report counterexamples on failure

    Args:
        spec: Parsed .card.md specification with invariants.
        code: Generated source code string to verify.

    Returns:
        StageResult with stage=3, status=PASS/FAIL/SKIP.
    """
    return _run_pbt_core(spec, code, pbt_settings=_make_pbt_settings())
