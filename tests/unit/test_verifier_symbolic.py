"""Tests for CrossHair symbolic verification of invariant candidates.

References:
- [REF-T09] CrossHair — Python symbolic execution via Z3
- [REF-C06] LLM-Driven Invariant Enrichment pipeline
"""

import pytest

pytest.importorskip("crosshair", reason="crosshair-tool not installed; skipping symbolic verification tests")

from immune.verifier_symbolic import (
    verify_invariant_symbolic,
    SymbolicResult,
    SymbolicVerdict,
)


class TestSymbolicResult:
    """Test the SymbolicResult dataclass."""

    def test_verified_result(self):
        result = SymbolicResult(verdict=SymbolicVerdict.VERIFIED)
        assert result.verdict == SymbolicVerdict.VERIFIED
        assert result.counterexample is None
        assert result.error is None

    def test_counterexample_result(self):
        result = SymbolicResult(
            verdict=SymbolicVerdict.COUNTEREXAMPLE,
            counterexample={"x": -1},
        )
        assert result.verdict == SymbolicVerdict.COUNTEREXAMPLE
        assert result.counterexample == {"x": -1}

    def test_error_result(self):
        result = SymbolicResult(
            verdict=SymbolicVerdict.ERROR,
            error="CrossHair not installed",
        )
        assert result.verdict == SymbolicVerdict.ERROR
        assert result.error == "CrossHair not installed"

    def test_timeout_result(self):
        result = SymbolicResult(verdict=SymbolicVerdict.TIMEOUT)
        assert result.verdict == SymbolicVerdict.TIMEOUT


class TestVerifyInvariantSymbolic:
    """Test the main verification function."""

    def test_simple_positive_invariant(self):
        """A true invariant should be VERIFIED."""
        func_source = '''
def abs_value(x: int) -> int:
    if x < 0:
        return -x
    return x
'''
        invariant = "result >= 0"
        result = verify_invariant_symbolic(func_source, "abs_value", invariant)
        assert result.verdict == SymbolicVerdict.VERIFIED

    def test_false_invariant_gives_counterexample(self):
        """A false invariant should return COUNTEREXAMPLE."""
        func_source = '''
def identity(x: int) -> int:
    return x
'''
        invariant = "result > 0"
        result = verify_invariant_symbolic(func_source, "identity", invariant)
        assert result.verdict == SymbolicVerdict.COUNTEREXAMPLE
        assert result.counterexample is not None

    def test_precondition_narrows_search(self):
        """Preconditions should restrict the search space."""
        func_source = '''
def divide(a: int, b: int) -> float:
    return a / b
'''
        invariant = "result == a / b"
        preconditions = ["b != 0"]
        result = verify_invariant_symbolic(
            func_source, "divide", invariant, preconditions=preconditions
        )
        assert result.verdict == SymbolicVerdict.VERIFIED

    def test_invalid_function_source_gives_error(self):
        """Bad source code should return ERROR, not crash."""
        func_source = "this is not valid python"
        invariant = "result > 0"
        result = verify_invariant_symbolic(func_source, "bad_func", invariant)
        assert result.verdict == SymbolicVerdict.ERROR
        assert result.error is not None

    def test_empty_invariant_gives_error(self):
        """Empty invariant string should return ERROR."""
        func_source = '''
def noop() -> None:
    pass
'''
        result = verify_invariant_symbolic(func_source, "noop", "")
        assert result.verdict == SymbolicVerdict.ERROR

    def test_timeout_parameter_respected(self):
        """Should accept a timeout parameter."""
        func_source = '''
def simple(x: int) -> int:
    return x + 1
'''
        invariant = "result == x + 1"
        result = verify_invariant_symbolic(
            func_source, "simple", invariant, timeout_sec=5
        )
        # Should complete (either VERIFIED or TIMEOUT, but not crash)
        assert result.verdict in (
            SymbolicVerdict.VERIFIED,
            SymbolicVerdict.TIMEOUT,
        )

    def test_multiple_preconditions(self):
        """Multiple preconditions should all be applied."""
        func_source = '''
def bounded_add(x: int, y: int) -> int:
    return x + y
'''
        invariant = "result > 0"
        preconditions = ["x > 0", "y > 0"]
        result = verify_invariant_symbolic(
            func_source, "bounded_add", invariant, preconditions=preconditions
        )
        assert result.verdict == SymbolicVerdict.VERIFIED
