"""Tests for Hypothesis property-based testing verification of invariant candidates.

References:
- [REF-T03] Hypothesis — Property-Based Testing for Python
- [REF-C06] LLM-Driven Invariant Enrichment pipeline
"""

import pytest
from immune.verifier_pbt import (
    verify_invariant_pbt,
    PBTResult,
    PBTVerdict,
)


class TestPBTResult:
    """Test the PBTResult dataclass."""

    def test_pass_result(self):
        result = PBTResult(verdict=PBTVerdict.PASS, num_examples=1000)
        assert result.verdict == PBTVerdict.PASS
        assert result.num_examples == 1000
        assert result.counterexample is None
        assert result.error is None

    def test_fail_result(self):
        result = PBTResult(
            verdict=PBTVerdict.FAIL,
            counterexample={"x": -1},
            num_examples=42,
        )
        assert result.verdict == PBTVerdict.FAIL
        assert result.counterexample == {"x": -1}
        assert result.num_examples == 42

    def test_error_result(self):
        result = PBTResult(
            verdict=PBTVerdict.ERROR,
            error="Syntax error in invariant",
        )
        assert result.verdict == PBTVerdict.ERROR
        assert result.error == "Syntax error in invariant"


class TestVerifyInvariantPBT:
    """Test the main PBT verification function."""

    def test_true_invariant_passes(self):
        """An invariant that always holds should PASS."""
        func_source = '''
def abs_value(x: int) -> int:
    if x < 0:
        return -x
    return x
'''
        invariant = "result >= 0"
        result = verify_invariant_pbt(func_source, "abs_value", invariant)
        assert result.verdict == PBTVerdict.PASS
        assert result.num_examples >= 100  # should run many examples

    def test_false_invariant_fails_with_counterexample(self):
        """An invariant that can be violated should FAIL."""
        func_source = '''
def identity(x: int) -> int:
    return x
'''
        invariant = "result > 0"
        result = verify_invariant_pbt(func_source, "identity", invariant)
        assert result.verdict == PBTVerdict.FAIL
        assert result.counterexample is not None

    def test_precondition_narrows_search(self):
        """Preconditions should restrict the generated inputs."""
        func_source = '''
def successor(x: int) -> int:
    return x + 1
'''
        invariant = "result > 0"
        preconditions = ["x >= 0"]
        result = verify_invariant_pbt(
            func_source, "successor", invariant, preconditions=preconditions
        )
        assert result.verdict == PBTVerdict.PASS

    def test_invalid_function_source_gives_error(self):
        """Bad source code should return ERROR."""
        func_source = "this is not valid python"
        invariant = "result > 0"
        result = verify_invariant_pbt(func_source, "bad_func", invariant)
        assert result.verdict == PBTVerdict.ERROR
        assert result.error is not None

    def test_empty_invariant_gives_error(self):
        """Empty invariant string should return ERROR."""
        func_source = '''
def noop() -> None:
    pass
'''
        result = verify_invariant_pbt(func_source, "noop", "")
        assert result.verdict == PBTVerdict.ERROR

    def test_max_examples_parameter(self):
        """Should respect the max_examples parameter."""
        func_source = '''
def double(x: int) -> int:
    return x * 2
'''
        invariant = "result == x * 2"
        result = verify_invariant_pbt(
            func_source, "double", invariant, max_examples=50
        )
        assert result.verdict == PBTVerdict.PASS
        assert result.num_examples <= 55  # allow small overhead

    def test_multi_param_function(self):
        """Should handle functions with multiple parameters."""
        func_source = '''
def add(a: int, b: int) -> int:
    return a + b
'''
        invariant = "result == a + b"
        result = verify_invariant_pbt(func_source, "add", invariant)
        assert result.verdict == PBTVerdict.PASS

    def test_string_function(self):
        """Should handle functions with string parameters."""
        func_source = '''
def greet(name: str) -> str:
    return "Hello, " + name
'''
        invariant = "result.startswith('Hello, ')"
        result = verify_invariant_pbt(func_source, "greet", invariant)
        assert result.verdict == PBTVerdict.PASS

    def test_list_function(self):
        """Should handle functions with list parameters."""
        func_source = '''
def length(items: list) -> int:
    return len(items)
'''
        invariant = "result >= 0"
        result = verify_invariant_pbt(func_source, "length", invariant)
        assert result.verdict == PBTVerdict.PASS
