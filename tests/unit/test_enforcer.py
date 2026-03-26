"""Tests for icontract runtime enforcement of verified invariants.

References:
- [REF-T10] icontract — Python Design by Contract
- [REF-C09] Immune System / Acquired Immunity
"""

import pytest
from immune.enforcer import (
    generate_enforced_source,
    InvariantSpec,
    parse_invariant_to_contract,
)


class TestParseInvariantToContract:
    """Test conversion from invariant expressions to icontract decorators."""

    def test_postcondition_with_result(self):
        """Invariants referencing 'result' become @ensure decorators."""
        decorator = parse_invariant_to_contract("result >= 0")
        assert "@icontract.ensure" in decorator
        assert "result >= 0" in decorator

    def test_precondition_without_result(self):
        """Invariants not referencing 'result' become @require decorators."""
        decorator = parse_invariant_to_contract("x > 0")
        assert "@icontract.require" in decorator
        assert "x > 0" in decorator

    def test_precondition_with_explanation(self):
        decorator = parse_invariant_to_contract(
            "x > 0", explanation="Input must be positive"
        )
        assert "Input must be positive" in decorator

    def test_postcondition_with_explanation(self):
        decorator = parse_invariant_to_contract(
            "result != None", explanation="Never returns None"
        )
        assert "Never returns None" in decorator


class TestInvariantSpec:
    """Test the InvariantSpec dataclass."""

    def test_basic_creation(self):
        spec = InvariantSpec(
            expression="result >= 0",
            explanation="Non-negative return",
            is_precondition=False,
        )
        assert spec.expression == "result >= 0"
        assert spec.is_precondition is False

    def test_auto_detect_precondition(self):
        spec = InvariantSpec(expression="x > 0")
        assert spec.is_precondition is True  # no 'result' = precondition

    def test_auto_detect_postcondition(self):
        spec = InvariantSpec(expression="result >= 0")
        assert spec.is_precondition is False  # has 'result' = postcondition


class TestGenerateEnforcedSource:
    """Test generating icontract-decorated source code."""

    def test_adds_import(self):
        """Generated source should import icontract."""
        func_source = '''\
def abs_value(x: int) -> int:
    if x < 0:
        return -x
    return x
'''
        invariants = [
            InvariantSpec(expression="result >= 0", explanation="Non-negative"),
        ]
        result = generate_enforced_source(func_source, "abs_value", invariants)
        assert "import icontract" in result

    def test_adds_ensure_decorator(self):
        """Postcondition invariants should add @icontract.ensure."""
        func_source = '''\
def abs_value(x: int) -> int:
    if x < 0:
        return -x
    return x
'''
        invariants = [
            InvariantSpec(expression="result >= 0", explanation="Non-negative"),
        ]
        result = generate_enforced_source(func_source, "abs_value", invariants)
        assert "@icontract.ensure" in result
        assert "result >= 0" in result

    def test_adds_require_decorator(self):
        """Precondition invariants should add @icontract.require."""
        func_source = '''\
def divide(a: int, b: int) -> float:
    return a / b
'''
        invariants = [
            InvariantSpec(expression="b != 0", explanation="Non-zero divisor", is_precondition=True),
        ]
        result = generate_enforced_source(func_source, "divide", invariants)
        assert "@icontract.require" in result
        assert "b != 0" in result

    def test_multiple_invariants(self):
        """Should handle multiple pre and postconditions."""
        func_source = '''\
def clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))
'''
        invariants = [
            InvariantSpec(expression="lo <= hi", explanation="Valid bounds", is_precondition=True),
            InvariantSpec(expression="result >= lo", explanation="Lower bound"),
            InvariantSpec(expression="result <= hi", explanation="Upper bound"),
        ]
        result = generate_enforced_source(func_source, "clamp", invariants)
        assert result.count("@icontract.require") == 1
        assert result.count("@icontract.ensure") == 2

    def test_preserves_function_body(self):
        """Function body should be unchanged."""
        func_source = '''\
def identity(x: int) -> int:
    return x
'''
        invariants = [
            InvariantSpec(expression="result == x"),
        ]
        result = generate_enforced_source(func_source, "identity", invariants)
        assert "return x" in result

    def test_empty_invariants_returns_original(self):
        """No invariants should return the original source unchanged (with import)."""
        func_source = '''\
def noop() -> None:
    pass
'''
        result = generate_enforced_source(func_source, "noop", [])
        assert "pass" in result
