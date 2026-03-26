"""Tests for U1.3 — LP Dual Root-Cause Diagnosis.

When Z3 says UNSAT, relax Boolean formulas to a continuous LP. Use dual
variables (shadow prices) to rank which invariant constraint is the binding
root cause. Turns "verification failed" into "constraint X is the problem."

Per [REF-NEW-09] duality-verification: LP relaxation + shadow prices via
scipy.optimize.linprog. Highest shadow price = most binding = root cause.

References:
- [REF-NEW-09] duality-verification (github.com/mellowyellow71/duality-verification)
- nightjar-upgrade-plan.md U1.3
- scipy.optimize.linprog (BSD) — HiGHS LP solver
"""

import pytest

scipy = pytest.importorskip("scipy", reason="scipy required for LP diagnosis")

from nightjar.types import (
    CardSpec, Contract, Invariant, InvariantTier, ModuleBoundary,
)


def _make_spec(invariants=None) -> CardSpec:
    return CardSpec(
        card_version="1.0", id="test", title="Test", status="draft",
        module=ModuleBoundary(owns=["f()"]),
        contract=Contract(),
        invariants=invariants or [],
    )


class TestDiagnosisModuleImports:
    """diagnosis module has expected public API."""

    def test_module_importable(self):
        from nightjar import diagnosis
        assert diagnosis is not None

    def test_diagnose_failure_importable(self):
        from nightjar.diagnosis import diagnose_failure
        assert callable(diagnose_failure)

    def test_diagnosis_result_importable(self):
        from nightjar.diagnosis import DiagnosisResult
        assert DiagnosisResult is not None

    def test_diagnosis_result_has_binding_constraint(self):
        from nightjar.diagnosis import DiagnosisResult
        result = DiagnosisResult(
            binding_constraint="result >= 0",
            ranked_constraints=[("result >= 0", 1.0)],
            diagnosis_available=True,
        )
        assert result.binding_constraint == "result >= 0"

    def test_diagnosis_result_has_ranked_constraints(self):
        from nightjar.diagnosis import DiagnosisResult
        result = DiagnosisResult(
            binding_constraint="result >= 0",
            ranked_constraints=[("result >= 0", 1.0), ("result >= -100", 0.0)],
            diagnosis_available=True,
        )
        assert len(result.ranked_constraints) == 2


class TestConstraintParsing:
    """Internal constraint parser handles numeric bounds."""

    def test_parse_lower_bound(self):
        from nightjar.diagnosis import _parse_constraint_bound
        lb, ub = _parse_constraint_bound("result >= 0")
        assert lb == 0.0
        assert ub is None

    def test_parse_upper_bound(self):
        from nightjar.diagnosis import _parse_constraint_bound
        lb, ub = _parse_constraint_bound("result <= 100")
        assert lb is None
        assert ub == 100.0

    def test_parse_strict_lower_bound(self):
        from nightjar.diagnosis import _parse_constraint_bound
        lb, ub = _parse_constraint_bound("result > 0")
        assert lb is not None
        assert lb >= 0.0

    def test_parse_equality(self):
        from nightjar.diagnosis import _parse_constraint_bound
        lb, ub = _parse_constraint_bound("result == 5")
        assert lb == 5.0
        assert ub == 5.0

    def test_parse_negative_bound(self):
        from nightjar.diagnosis import _parse_constraint_bound
        lb, ub = _parse_constraint_bound("result >= -100")
        assert lb == -100.0

    def test_parse_unparseable_returns_none_none(self):
        from nightjar.diagnosis import _parse_constraint_bound
        lb, ub = _parse_constraint_bound("invariant is complex")
        assert lb is None
        assert ub is None


class TestDiagnoseFailureRanking:
    """diagnose_failure ranks constraints by binding shadow price."""

    def test_identifies_most_violated_as_binding(self):
        """Constraint violated by 100 units is more binding than violated by 5."""
        from nightjar.diagnosis import diagnose_failure
        constraints = [
            "result >= 100",   # hugely violated when result = -5
            "result >= 0",     # slightly violated when result = -5
            "result >= -100",  # not violated when result = -5
        ]
        result = diagnose_failure(constraints, result_value=-5.0)
        # binding_constraint must be "result >= 100" (most violated)
        assert result.diagnosis_available
        assert result.binding_constraint == "result >= 100"

    def test_ranked_constraints_sorted_descending(self):
        """ranked_constraints is sorted by shadow price descending."""
        from nightjar.diagnosis import diagnose_failure
        constraints = ["result >= 100", "result >= 0", "result >= -100"]
        result = diagnose_failure(constraints, result_value=-5.0)
        prices = [sp for _, sp in result.ranked_constraints]
        assert prices == sorted(prices, reverse=True), (
            "ranked_constraints must be sorted by shadow price (descending)"
        )

    def test_unviolated_constraint_has_lower_shadow_price(self):
        """Unviolated constraint has shadow price ≤ violated constraint."""
        from nightjar.diagnosis import diagnose_failure
        constraints = ["result >= 10", "result >= -100"]
        result = diagnose_failure(constraints, result_value=5.0)
        # result >= 10 is violated (value 5 < 10), result >= -100 is fine
        violated_price = dict(result.ranked_constraints).get("result >= 10", 0.0)
        unviolated_price = dict(result.ranked_constraints).get("result >= -100", 0.0)
        assert violated_price >= unviolated_price

    def test_empty_constraints_returns_unavailable(self):
        """Empty constraint list → diagnosis_available=False."""
        from nightjar.diagnosis import diagnose_failure
        result = diagnose_failure([], result_value=0.0)
        assert result.diagnosis_available is False
        assert result.binding_constraint == ""

    def test_all_satisfied_constraints_have_zero_shadow_price(self):
        """When result satisfies all constraints, shadow prices are zero."""
        from nightjar.diagnosis import diagnose_failure
        constraints = ["result >= 0", "result <= 100"]
        result = diagnose_failure(constraints, result_value=50.0)
        for _, price in result.ranked_constraints:
            assert price == pytest.approx(0.0, abs=1e-6), (
                "No constraint violated — all shadow prices should be 0"
            )


class TestDiagnoseFailureNoCounterexample:
    """diagnose_failure without result_value uses LP to find conflicting constraints."""

    def test_conflicting_constraints_detected(self):
        """Contradictory constraints (result >= 10 AND result <= 5) are diagnosable."""
        from nightjar.diagnosis import diagnose_failure
        constraints = ["result >= 10", "result <= 5"]
        result = diagnose_failure(constraints)
        # At least one constraint should have nonzero shadow price
        assert result.diagnosis_available
        max_price = max(sp for _, sp in result.ranked_constraints)
        assert max_price > 0, "Conflicting constraints must have nonzero shadow price"

    def test_non_conflicting_constraints_have_zero_price(self):
        """Compatible constraints: result >= 0, result <= 100 — no conflict."""
        from nightjar.diagnosis import diagnose_failure
        constraints = ["result >= 0", "result <= 100"]
        result = diagnose_failure(constraints)
        assert result.diagnosis_available
        # Compatible: optimizer can find x=50, all satisfied → zero total violation
        for _, price in result.ranked_constraints:
            assert price == pytest.approx(0.0, abs=1e-6)


class TestDiagnoseFromSpec:
    """diagnose_from_spec extracts invariant statements and diagnoses."""

    def test_importable(self):
        from nightjar.diagnosis import diagnose_from_spec
        assert callable(diagnose_from_spec)

    def test_diagnose_from_spec_returns_diagnosis_result(self):
        from nightjar.diagnosis import diagnose_from_spec, DiagnosisResult
        spec = _make_spec(invariants=[
            Invariant(id="INV-1", tier=InvariantTier.FORMAL,
                      statement="result >= 0"),
            Invariant(id="INV-2", tier=InvariantTier.FORMAL,
                      statement="result <= 100"),
        ])
        result = diagnose_from_spec(spec, result_value=50.0)
        assert isinstance(result, DiagnosisResult)

    def test_diagnose_from_empty_spec(self):
        from nightjar.diagnosis import diagnose_from_spec
        spec = _make_spec()
        result = diagnose_from_spec(spec)
        assert result.diagnosis_available is False


class TestExplainIntegration:
    """explain.py is extended with LP diagnosis output."""

    def test_explain_output_has_root_cause_field(self):
        """ExplainOutput has a root_cause field after U1.3 extension."""
        from nightjar.explain import ExplainOutput
        # The field should exist (may be empty string initially)
        ex = ExplainOutput(
            failed_stage=4,
            stage_name="formal",
            invariant_violated="result >= 0",
            error_messages=["postcondition fails"],
            counterexamples=[],
            suggested_fix="fix the code",
            all_stages_summary=[],
            root_cause="",
        )
        assert hasattr(ex, "root_cause")

    def test_format_explanation_includes_root_cause_when_present(self):
        """format_explanation() includes root cause section when available."""
        from nightjar.explain import ExplainOutput, format_explanation
        ex = ExplainOutput(
            failed_stage=4,
            stage_name="formal",
            invariant_violated="result >= 0",
            error_messages=["postcondition fails"],
            counterexamples=[],
            suggested_fix="fix the code",
            all_stages_summary=[],
            root_cause="result >= 100 (shadow price: 5.0)",
        )
        text = format_explanation(ex)
        assert "result >= 100" in text or "root cause" in text.lower()
