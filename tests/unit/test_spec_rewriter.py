"""Tests for U1.1 — Spec Preprocessing Rewrite Rules.

19 deterministic rewrite rules applied to .card.md specs BEFORE LLM generation.
Based on Proven (https://github.com/melek/proven, MIT) which demonstrates these
rules double Dafny success rates (19%→41% on local models, 65%→78% on Claude).

References:
- Proven (MIT): github.com/melek/proven — 19 deterministic spec rewrite rules
- nightjar-upgrade-plan.md U1.1
"""

import pytest
from nightjar.types import (
    CardSpec, Contract, ContractInput, ContractOutput,
    Invariant, InvariantTier, ModuleBoundary,
)


def _make_spec(
    invariants=None, intent="", functional_requirements="",
    acceptance_criteria="", contract=None,
) -> CardSpec:
    return CardSpec(
        card_version="1.0",
        id="test-card",
        title="Test",
        status="draft",
        module=ModuleBoundary(owns=["process()"]),
        contract=contract or Contract(),
        invariants=invariants or [],
        intent=intent,
        acceptance_criteria=acceptance_criteria,
        functional_requirements=functional_requirements,
    )


class TestSpecRewriterImports:
    """spec_rewriter module is importable with expected API."""

    def test_module_importable(self):
        from nightjar import spec_rewriter
        assert spec_rewriter is not None

    def test_rewrite_spec_callable(self):
        from nightjar.spec_rewriter import rewrite_spec
        assert callable(rewrite_spec)

    def test_rewrite_result_importable(self):
        from nightjar.spec_rewriter import RewriteResult
        assert RewriteResult is not None

    def test_rules_applied_is_list(self):
        from nightjar.spec_rewriter import rewrite_spec
        spec = _make_spec()
        result = rewrite_spec(spec)
        assert isinstance(result.rules_applied, list)


class TestQuantifierNormalization:
    """Rule group 1: Quantifier scope normalization.

    Per Proven: ambiguous 'for all' / 'exists' in invariant statements
    are normalized to explicit bounded forms Z3 handles cleanly.
    'for all x, P(x)' → 'forall x: int :: P(x)'
    """

    def test_normalizes_forall_to_explicit_form(self):
        """'for all x' → 'forall x: int ::' in invariant statements."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec(invariants=[
            Invariant(
                id="INV-1", tier=InvariantTier.FORMAL,
                statement="for all x, result > x",
            ),
        ])
        result = rewrite_spec(spec)
        normalized = result.spec.invariants[0].statement
        # Should have explicit bounded form
        assert "for all" not in normalized or "forall" in normalized or "::" in normalized
        assert "quantifier_normalization" in result.rules_applied

    def test_normalizes_there_exists_to_explicit_form(self):
        """'there exists' → 'exists x: int ::' in invariant statements."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec(invariants=[
            Invariant(
                id="INV-2", tier=InvariantTier.FORMAL,
                statement="there exists n such that result == n * 2",
            ),
        ])
        result = rewrite_spec(spec)
        normalized = result.spec.invariants[0].statement
        assert "there exists" not in normalized or "exists" in normalized
        assert "quantifier_normalization" in result.rules_applied


class TestCompoundPostconditionDecomposition:
    """Rule group 2: Compound postcondition decomposition.

    Per Proven: 'A and B and C' postconditions are split into separate
    invariants. Z3 handles single predicates more efficiently.
    """

    def test_decomposes_and_postcondition_into_separate_invariants(self):
        """'result > 0 and result < 100' → two invariants."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec(invariants=[
            Invariant(
                id="INV-3", tier=InvariantTier.FORMAL,
                statement="result > 0 and result < 100",
            ),
        ])
        result = rewrite_spec(spec)
        # Should have 2 invariants from decomposed AND
        assert len(result.spec.invariants) >= 2
        assert "compound_decomposition" in result.rules_applied

    def test_single_postcondition_unchanged(self):
        """Single (non-compound) invariant is not split."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec(invariants=[
            Invariant(
                id="INV-4", tier=InvariantTier.FORMAL,
                statement="result > 0",
            ),
        ])
        result = rewrite_spec(spec)
        assert len(result.spec.invariants) == 1


class TestSyntacticSugarExpansion:
    """Rule group 3: Syntactic sugar expansion.

    Per Proven: shorthand like 'non-negative', 'positive', 'bounded' are
    expanded to explicit numeric predicates Z3 can directly reason about.
    """

    def test_expands_positive_to_greater_than_zero(self):
        """'positive' → 'result > 0'."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec(invariants=[
            Invariant(
                id="INV-5", tier=InvariantTier.PROPERTY,
                statement="result is positive",
            ),
        ])
        result = rewrite_spec(spec)
        rewritten = result.spec.invariants[0].statement
        assert "result > 0" in rewritten or "> 0" in rewritten
        assert "sugar_expansion" in result.rules_applied

    def test_expands_non_negative_to_gte_zero(self):
        """'non-negative' → 'result >= 0'."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec(invariants=[
            Invariant(
                id="INV-6", tier=InvariantTier.PROPERTY,
                statement="result is non-negative",
            ),
        ])
        result = rewrite_spec(spec)
        rewritten = result.spec.invariants[0].statement
        assert ">= 0" in rewritten or "result >= 0" in rewritten
        assert "sugar_expansion" in result.rules_applied

    def test_expands_bounded_to_range_predicate(self):
        """'bounded between A and B' → 'A <= result <= B'."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec(invariants=[
            Invariant(
                id="INV-7", tier=InvariantTier.PROPERTY,
                statement="result is bounded between 0 and 100",
            ),
        ])
        result = rewrite_spec(spec)
        rewritten = result.spec.invariants[0].statement
        assert "0" in rewritten and "100" in rewritten
        assert "sugar_expansion" in result.rules_applied


class TestContractConstraintNormalization:
    """Rule group 4: Contract input/output constraint normalization.

    Per Proven: input constraints like 'must be positive' become
    typed preconditions 'x > 0' for the LLM and Z3 to reason about.
    """

    def test_normalizes_positive_input_constraint(self):
        """'must be positive' → 'x > 0' in contract input constraints."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec(contract=Contract(
            inputs=[ContractInput(name="x", type="int", constraints="must be positive")],
        ))
        result = rewrite_spec(spec)
        normalized = result.spec.contract.inputs[0].constraints
        assert "x > 0" in normalized or "> 0" in normalized
        assert "constraint_normalization" in result.rules_applied

    def test_normalizes_non_empty_string_constraint(self):
        """'must not be empty' → 'len(s) > 0' for string inputs."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec(contract=Contract(
            inputs=[ContractInput(name="s", type="str", constraints="must not be empty")],
        ))
        result = rewrite_spec(spec)
        normalized = result.spec.contract.inputs[0].constraints
        assert "len(s) > 0" in normalized or "!= ''" in normalized or "len" in normalized
        assert "constraint_normalization" in result.rules_applied


class TestRewriteResult:
    """RewriteResult structure tests."""

    def test_rewrite_result_has_spec_field(self):
        """RewriteResult.spec holds the rewritten CardSpec."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec()
        result = rewrite_spec(spec)
        assert hasattr(result, "spec")
        assert isinstance(result.spec, CardSpec)

    def test_rewrite_result_has_rules_applied(self):
        """RewriteResult.rules_applied lists which rules fired."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec()
        result = rewrite_spec(spec)
        assert hasattr(result, "rules_applied")
        assert isinstance(result.rules_applied, list)

    def test_rewrite_result_has_original_spec(self):
        """RewriteResult.original holds unchanged original spec."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec(intent="original intent")
        result = rewrite_spec(spec)
        assert result.original.intent == "original intent"

    def test_empty_spec_passes_through_without_rules(self):
        """Spec with no invariants/constraints: rules_applied may be empty."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec()
        result = rewrite_spec(spec)
        assert result.spec is not None
        # No rules needed — spec is minimal
        assert isinstance(result.rules_applied, list)

    def test_rewrite_is_idempotent(self):
        """Applying rewrite_spec twice produces the same result as once."""
        from nightjar.spec_rewriter import rewrite_spec

        spec = _make_spec(invariants=[
            Invariant(id="INV-8", tier=InvariantTier.PROPERTY,
                      statement="result is positive"),
        ])
        once = rewrite_spec(spec)
        twice = rewrite_spec(once.spec)
        # Invariant count should not grow on second application
        assert len(twice.spec.invariants) == len(once.spec.invariants)

    def test_rewrite_does_not_mutate_original(self):
        """rewrite_spec does not modify the input spec in place."""
        from nightjar.spec_rewriter import rewrite_spec

        original_statement = "result is positive"
        spec = _make_spec(invariants=[
            Invariant(id="INV-9", tier=InvariantTier.PROPERTY,
                      statement=original_statement),
        ])
        rewrite_spec(spec)
        # Original spec invariants unchanged
        assert spec.invariants[0].statement == original_statement
