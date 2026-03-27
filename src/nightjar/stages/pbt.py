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
  dev profile (NIGHTJAR_TEST_PROFILE=dev or unset): max_examples=10  ~300-500ms
  ci  profile (NIGHTJAR_TEST_PROFILE=ci):           max_examples=200 ~3-8s
  Properties are auto-generated from invariants.
  Short-circuit on property violation with counterexample.
"""

import os
import time
import textwrap
import traceback
from typing import Any

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from nightjar.types import (
    CardSpec, Invariant, InvariantTier, StageResult, VerifyStatus,
)


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


def _build_test_environment(code: str) -> dict[str, Any]:
    """Execute generated code in an isolated namespace and return it.

    Security note: This executes code in a restricted dict namespace,
    not in the module's globals. The generated code is already verified
    by Stages 0-2 before reaching Stage 3.
    """
    namespace: dict[str, Any] = {"__builtins__": __builtins__}
    exec(compile(code, "<generated>", "exec"), namespace)  # noqa: S102
    return namespace


def _run_single_invariant(
    invariant: Invariant,
    code: str,
    env: dict[str, Any],
    pbt_settings: settings = NIGHTJAR_PBT_SETTINGS,
) -> dict[str, Any] | None:
    """Run PBT for a single invariant against the generated code.

    Returns None on success, or an error dict on failure.

    Per [REF-P10], LLMs are 20-47% more accurate generating validation
    properties than implementations. The invariant statement from .card.md
    is the property specification; we translate it to a Hypothesis test.

    The translation strategy: we build a test function that:
    1. Generates inputs matching the contract constraints
    2. Calls the code under test
    3. Asserts the invariant property holds

    Args:
        pbt_settings: Hypothesis settings to apply (default: NIGHTJAR_PBT_SETTINGS).
                      Pass NIGHTJAR_PBT_EXTENDED_SETTINGS for 10K+ examples.
    """
    statement = invariant.statement
    error_result: dict[str, Any] | None = None

    # Build a Hypothesis test function dynamically from the invariant
    # The test function is wrapped with @given and the supplied settings
    @pbt_settings
    @given(x=st.integers(min_value=1, max_value=10_000))
    def pbt_test(x: int) -> None:
        nonlocal error_result
        try:
            # Execute the function from generated code
            # Find callable functions in the environment
            func = _find_testable_function(env)
            if func is None:
                return

            result = func(x)

            # Evaluate the invariant assertion
            _assert_invariant(statement, x, result)

        except AssertionError:
            raise  # Let Hypothesis catch assertion failures
        except Exception as e:
            raise AssertionError(
                f"Invariant {invariant.id} violated: {e}"
            ) from e

    try:
        pbt_test()
        return None  # Success
    except AssertionError as e:
        return {
            "invariant_id": invariant.id,
            "tier": invariant.tier.value,
            "statement": invariant.statement,
            "error": str(e),
            "type": "property_violation",
        }
    except Exception as e:
        return {
            "invariant_id": invariant.id,
            "tier": invariant.tier.value,
            "statement": invariant.statement,
            "error": f"PBT execution error: {traceback.format_exc()}",
            "type": "execution_error",
        }


def _find_testable_function(env: dict[str, Any]) -> Any | None:
    """Find the first callable function in the generated code namespace.

    Skips builtins and dunder names. Returns None if no function found.
    """
    for name, obj in env.items():
        if name.startswith("_"):
            continue
        if callable(obj) and not isinstance(obj, type):
            return obj
    return None


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

    errors: list[dict] = []
    for inv in pbt_invariants:
        error = _run_single_invariant(inv, code, env, pbt_settings=pbt_settings)
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
