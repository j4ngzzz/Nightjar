"""Tests for Stage 3 — Property-Based Testing.

Validates that the PBT stage auto-generates Hypothesis tests from
.card.md invariants and runs them against generated code.

References:
- [REF-T03] Hypothesis — Property-Based Testing for Python
- [REF-P10] PGS paper — property generation from invariants
- [REF-C01] Tiered invariants — only 'property' and 'formal' tier reach this stage
"""

import pytest
from contractd.types import (
    CardSpec, Contract, ContractInput, ContractOutput,
    Invariant, InvariantTier, ModuleBoundary,
    StageResult, VerifyStatus,
)
from contractd.stages.pbt import run_pbt


def _make_spec(invariants: list[Invariant]) -> CardSpec:
    """Helper to build a minimal CardSpec with given invariants."""
    return CardSpec(
        card_version="1.0",
        id="test-module",
        title="Test Module",
        status="draft",
        module=ModuleBoundary(owns=["func_a()"]),
        contract=Contract(
            inputs=[ContractInput(name="x", type="integer", constraints="x > 0")],
            outputs=[ContractOutput(name="Result", type="integer")],
        ),
        invariants=invariants,
    )


# --- Valid generated code that should PASS PBT ---

PASSING_CODE = '''
def process(x: int) -> int:
    """Process a positive integer, returning its double."""
    if x <= 0:
        raise ValueError("x must be positive")
    return x * 2
'''

# --- Buggy code that should FAIL the property ---

FAILING_CODE = '''
def process(x: int) -> int:
    """Process a positive integer — but has a bug for large values."""
    if x <= 0:
        raise ValueError("x must be positive")
    if x > 1000:
        return -1  # Bug: returns negative for large inputs
    return x * 2
'''


class TestRunPbt:
    """Tests for run_pbt function."""

    def test_returns_stage_result(self):
        """run_pbt returns a StageResult with stage=3 and name='pbt'."""
        spec = _make_spec([
            Invariant(
                id="INV-001",
                tier=InvariantTier.PROPERTY,
                statement="For any positive x, process(x) returns a positive integer",
            ),
        ])
        result = run_pbt(spec, PASSING_CODE)
        assert isinstance(result, StageResult)
        assert result.stage == 3
        assert result.name == "pbt"

    def test_pass_with_valid_code_and_property_invariant(self):
        """PBT passes when code satisfies the property invariant."""
        spec = _make_spec([
            Invariant(
                id="INV-001",
                tier=InvariantTier.PROPERTY,
                statement="For any positive x, process(x) returns a positive integer",
            ),
        ])
        result = run_pbt(spec, PASSING_CODE)
        assert result.status == VerifyStatus.PASS

    def test_fail_with_buggy_code(self):
        """PBT fails when code violates the property — provides counterexample."""
        spec = _make_spec([
            Invariant(
                id="INV-001",
                tier=InvariantTier.PROPERTY,
                statement="For any positive x, process(x) returns a positive integer",
            ),
        ])
        result = run_pbt(spec, FAILING_CODE)
        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0

    def test_skips_example_tier_invariants(self):
        """Stage 3 only runs for 'property' and 'formal' tier — skips 'example'."""
        spec = _make_spec([
            Invariant(
                id="INV-001",
                tier=InvariantTier.EXAMPLE,
                statement="process(5) returns 10",
            ),
        ])
        result = run_pbt(spec, PASSING_CODE)
        assert result.status == VerifyStatus.SKIP

    def test_includes_formal_tier_invariants(self):
        """Stage 3 also runs for 'formal' tier invariants (PBT is a subset of formal)."""
        spec = _make_spec([
            Invariant(
                id="INV-001",
                tier=InvariantTier.FORMAL,
                statement="For any positive x, process(x) returns a positive integer",
            ),
        ])
        result = run_pbt(spec, PASSING_CODE)
        assert result.status == VerifyStatus.PASS

    def test_multiple_invariants_all_pass(self):
        """Multiple property invariants all passing → overall PASS."""
        spec = _make_spec([
            Invariant(
                id="INV-001",
                tier=InvariantTier.PROPERTY,
                statement="For any positive x, process(x) returns a positive integer",
            ),
            Invariant(
                id="INV-002",
                tier=InvariantTier.PROPERTY,
                statement="For any positive x, process(x) equals x * 2",
            ),
        ])
        result = run_pbt(spec, PASSING_CODE)
        assert result.status == VerifyStatus.PASS

    def test_one_failing_invariant_causes_overall_fail(self):
        """If any property invariant fails, the overall result is FAIL."""
        spec = _make_spec([
            Invariant(
                id="INV-001",
                tier=InvariantTier.PROPERTY,
                statement="For any positive x, process(x) returns a positive integer",
            ),
            Invariant(
                id="INV-002",
                tier=InvariantTier.PROPERTY,
                statement="For any positive x, process(x) equals x * 2",
            ),
        ])
        result = run_pbt(spec, FAILING_CODE)
        assert result.status == VerifyStatus.FAIL

    def test_duration_is_recorded(self):
        """run_pbt records duration_ms > 0."""
        spec = _make_spec([
            Invariant(
                id="INV-001",
                tier=InvariantTier.PROPERTY,
                statement="For any positive x, process(x) returns a positive integer",
            ),
        ])
        result = run_pbt(spec, PASSING_CODE)
        assert result.duration_ms >= 0

    def test_no_applicable_invariants_skips(self):
        """When spec has no property/formal invariants, stage is SKIP."""
        spec = _make_spec([])
        result = run_pbt(spec, PASSING_CODE)
        assert result.status == VerifyStatus.SKIP

    def test_error_contains_invariant_id(self):
        """Failure errors reference the invariant ID that failed."""
        spec = _make_spec([
            Invariant(
                id="INV-042",
                tier=InvariantTier.PROPERTY,
                statement="For any positive x, process(x) returns a positive integer",
            ),
        ])
        result = run_pbt(spec, FAILING_CODE)
        assert result.status == VerifyStatus.FAIL
        assert any("INV-042" in str(e.get("invariant_id", "")) for e in result.errors)
