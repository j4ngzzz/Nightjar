"""Tests for StepCache — method-level LLM reuse for retry loop.

StepCache reduces LLM latency 2.13s → 0.67s (69% reduction) by:
1. Breaking Dafny code into methods (steps)
2. Caching each method after successful verification
3. On retry: reusing cached methods, only regenerating failing ones

References:
- Scout 5 Finding 4 — StepCache step-level LLM reuse
- Paper: researchsquare.com/article/rs-9077245/v1
"""

import pytest

from nightjar.step_cache import (
    MethodStep,
    StepCache,
    extract_dafny_methods,
)


# ── Sample Dafny code ──────────────────────────────────────────────────────

DAFNY_TWO_METHODS = """\
method Add(x: int, y: int) returns (r: int)
  ensures r == x + y
{
  r := x + y;
}

method Multiply(x: int, y: int) returns (r: int)
  ensures r == x * y
{
  r := x * y;
}
"""

DAFNY_ONE_METHOD = """\
method Square(x: int) returns (r: int)
  ensures r == x * x
{
  r := x * x;
}
"""

DAFNY_THREE_METHODS = """\
method A(x: int) returns (r: int) { r := x; }
method B(x: int) returns (r: int) { r := x + 1; }
method C(x: int) returns (r: int) { r := x + 2; }
"""


# ── extract_dafny_methods ──────────────────────────────────────────────────


class TestExtractDafnyMethods:
    """Parse Dafny code into individual method steps."""

    def test_extracts_two_methods(self):
        """Two methods in Dafny code → two MethodStep objects."""
        methods = extract_dafny_methods(DAFNY_TWO_METHODS)
        assert len(methods) == 2

    def test_extracts_method_names(self):
        """Extracted methods have correct names."""
        methods = extract_dafny_methods(DAFNY_TWO_METHODS)
        names = [m.name for m in methods]
        assert "Add" in names
        assert "Multiply" in names

    def test_extracts_method_code(self):
        """Extracted MethodStep includes the method code."""
        methods = extract_dafny_methods(DAFNY_ONE_METHOD)
        assert len(methods) == 1
        assert "Square" in methods[0].code
        assert "x * x" in methods[0].code

    def test_extracts_three_methods(self):
        """Three methods → three MethodStep objects."""
        methods = extract_dafny_methods(DAFNY_THREE_METHODS)
        assert len(methods) == 3
        names = {m.name for m in methods}
        assert names == {"A", "B", "C"}

    def test_empty_code_returns_empty(self):
        """No methods in code → empty list."""
        methods = extract_dafny_methods("")
        assert methods == []

    def test_returns_method_step_objects(self):
        """Returns list of MethodStep instances."""
        methods = extract_dafny_methods(DAFNY_ONE_METHOD)
        for m in methods:
            assert isinstance(m, MethodStep)
            assert isinstance(m.name, str)
            assert isinstance(m.code, str)


# ── MethodStep ─────────────────────────────────────────────────────────────


class TestMethodStep:
    """MethodStep data structure."""

    def test_has_name_and_code(self):
        """MethodStep must have name and code fields."""
        step = MethodStep(name="Foo", code="method Foo() {}")
        assert step.name == "Foo"
        assert step.code == "method Foo() {}"


# ── StepCache ─────────────────────────────────────────────────────────────


class TestStepCache:
    """Method-level cache for Dafny retry loop [Scout 5 F4]."""

    def test_step_cache_reuses_passing_methods(self):
        """After methods pass, they are cached and can be retrieved [Scout 5 F4]."""
        cache = StepCache()
        methods = extract_dafny_methods(DAFNY_TWO_METHODS)

        # Store all passing methods
        cache.store_passing_methods(methods)

        # Both methods should be in cache now
        cached = cache.get_passing_methods()
        assert "Add" in cached
        assert "Multiply" in cached

    def test_cached_method_code_is_retrievable(self):
        """Cached method code can be retrieved by method name."""
        cache = StepCache()
        methods = extract_dafny_methods(DAFNY_ONE_METHOD)
        cache.store_passing_methods(methods)

        cached = cache.get_passing_methods()
        assert "Square" in cached
        assert "x * x" in cached["Square"]

    def test_step_cache_regenerates_only_failing_method(self):
        """Failing method identified from errors; passing methods remain cached [Scout 5 F4]."""
        cache = StepCache()
        methods = extract_dafny_methods(DAFNY_TWO_METHODS)

        # First run: both pass, cache them
        cache.store_passing_methods(methods)

        # On retry: 'Multiply' fails with a Dafny error
        errors = [
            {
                "stage": 4,
                "stage_name": "formal",
                "errors": [
                    {
                        "type": "dafny_error",
                        "message": "Error in method Multiply: postcondition might not hold",
                        "method": "Multiply",
                    }
                ],
            }
        ]

        failing = cache.identify_failing_method(errors)
        assert failing == "Multiply", (
            "Should identify 'Multiply' as the failing method from error message"
        )

        # 'Add' is still in cache (was passing)
        cached = cache.get_passing_methods()
        assert "Add" in cached

    def test_identify_failing_method_returns_none_on_no_match(self):
        """Returns None when no method name can be extracted from errors."""
        cache = StepCache()
        errors = [{"stage": 4, "errors": [{"message": "Unknown error"}]}]
        assert cache.identify_failing_method(errors) is None

    def test_empty_cache_returns_empty_dict(self):
        """Before any methods are stored, get_passing_methods returns empty dict."""
        cache = StepCache()
        assert cache.get_passing_methods() == {}

    def test_store_overwrites_previous_method(self):
        """Storing the same method name twice updates the cached code."""
        cache = StepCache()
        v1 = [MethodStep(name="Foo", code="method Foo() { r := 1; }")]
        v2 = [MethodStep(name="Foo", code="method Foo() { r := 2; }")]

        cache.store_passing_methods(v1)
        cache.store_passing_methods(v2)

        cached = cache.get_passing_methods()
        assert "r := 2;" in cached["Foo"]

    def test_cache_survives_multiple_methods_stored_separately(self):
        """Methods stored in separate calls are all retained."""
        cache = StepCache()
        m1 = [MethodStep(name="A", code="method A() {}")]
        m2 = [MethodStep(name="B", code="method B() {}")]

        cache.store_passing_methods(m1)
        cache.store_passing_methods(m2)

        cached = cache.get_passing_methods()
        assert "A" in cached
        assert "B" in cached
