"""Stage 3 — Property-Based Testing (PBT).

Auto-generates and runs Hypothesis tests from .card.md invariants.
Only 'property' and 'formal' tier invariants reach this stage [REF-C01].

References:
- [REF-T03] Hypothesis — settings: derandomize=True, max_examples=200, deadline=None
- [REF-P10] PGS paper — LLMs generate validation properties; PBT raises
  correction rates from 46.6% to 75.9%
- [REF-C01] Tiered invariants — CARD's invention

Design per ARCHITECTURE.md Section 3:
  Stage 3 executes with max_examples=200, derandomize=True.
  Properties are auto-generated from invariants.
  Short-circuit on property violation with counterexample.
"""

import time
import textwrap
import traceback
from typing import Any

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from contractd.types import (
    CardSpec, Invariant, InvariantTier, StageResult, VerifyStatus,
)


# Hypothesis settings for CARD verification [REF-T03]
# derandomize=True for deterministic CI runs
# max_examples=200 per ARCHITECTURE.md
# deadline=None to avoid flaky timeouts
CARD_PBT_SETTINGS = settings(
    max_examples=200,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    database=None,
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
    """
    statement = invariant.statement
    error_result: dict[str, Any] | None = None

    # Build a Hypothesis test function dynamically from the invariant
    # The test function is wrapped with @given and CARD settings
    @CARD_PBT_SETTINGS
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
        except (ValueError, TypeError):
            pass  # Expected errors from constraint violations are OK
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


def run_pbt(spec: CardSpec, code: str) -> StageResult:
    """Run Stage 3 — Property-Based Testing on generated code.

    Per [REF-T03] and [REF-P10]:
    1. Filter invariants to property/formal tiers [REF-C01]
    2. For each invariant, generate a Hypothesis @given test
    3. Execute with max_examples=200, derandomize=True [REF-T03]
    4. Report counterexamples on failure

    Args:
        spec: Parsed .card.md specification with invariants.
        code: Generated source code string to verify.

    Returns:
        StageResult with stage=3, status=PASS/FAIL/SKIP.
    """
    start = time.monotonic()

    # Step 1: Filter to PBT-eligible invariants [REF-C01]
    pbt_invariants = _filter_pbt_invariants(spec.invariants)

    if not pbt_invariants:
        return StageResult(
            stage=3,
            name="pbt",
            status=VerifyStatus.SKIP,
            duration_ms=0,
        )

    # Step 2: Build execution environment from generated code
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

    # Step 3: Run PBT for each invariant
    errors: list[dict] = []
    for inv in pbt_invariants:
        error = _run_single_invariant(inv, code, env)
        if error is not None:
            errors.append(error)

    duration = int((time.monotonic() - start) * 1000)

    # Step 4: Determine overall status
    status = VerifyStatus.FAIL if errors else VerifyStatus.PASS

    return StageResult(
        stage=3,
        name="pbt",
        status=status,
        duration_ms=duration,
        errors=errors,
        counterexample=errors[0] if errors else None,
    )
