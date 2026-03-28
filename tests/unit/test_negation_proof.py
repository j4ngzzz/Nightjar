"""Tests for U1.4 — Negation-Proof Spec Validation.

Instead of verifying a spec is correct, prove its negation is impossible.
If CrossHair CONFIRMS the negated postcondition (no violations) → negation
holds for all inputs → original spec is degenerate/too weak.
If CrossHair finds a COUNTEREXAMPLE to the negated postcondition → the
original spec CAN be satisfied → spec is meaningful.

Inserted as Stage 2.5: AFTER schema+PBT, BEFORE Dafny formal.

Per [REF-NEW-07] NegProof (arxiv:2603.13414): computationally cheaper than
full formal verification for catching false positives and weak specs.

References:
- [REF-NEW-07] NegProof (arxiv:2603.13414) — negation-proof spec validation
- nightjar-upgrade-plan.md U1.4
"""

import pytest
from unittest.mock import patch, MagicMock

from nightjar.types import (
    CardSpec, Contract, Invariant, InvariantTier, ModuleBoundary,
    StageResult, VerifyStatus,
)


def _make_spec(invariants=None) -> CardSpec:
    return CardSpec(
        card_version="1.0", id="test", title="Test", status="draft",
        module=ModuleBoundary(owns=["f()"]),
        contract=Contract(),
        invariants=invariants or [],
    )


SIMPLE_CODE = "def charge(amount: int) -> int:\n    return amount * 2\n"


class TestNegationProofImports:
    """negation_proof module has expected public API."""

    def test_module_importable(self):
        from nightjar import negation_proof
        assert negation_proof is not None

    def test_negate_postcondition_importable(self):
        from nightjar.negation_proof import negate_postcondition
        assert callable(negate_postcondition)

    def test_run_negation_proof_importable(self):
        from nightjar.negation_proof import run_negation_proof
        assert callable(run_negation_proof)

    def test_neg_proof_result_importable(self):
        from nightjar.negation_proof import NegProofResult
        assert NegProofResult is not None


class TestNegatePostcondition:
    """negate_postcondition() syntactically negates invariant statements."""

    def test_negates_greater_equal(self):
        from nightjar.negation_proof import negate_postcondition
        neg = negate_postcondition("result >= 0")
        assert "not" in neg.lower() or "!" in neg
        assert "0" in neg

    def test_negates_equality(self):
        from nightjar.negation_proof import negate_postcondition
        neg = negate_postcondition("result == 5")
        assert "not" in neg.lower() or "!" in neg
        assert "5" in neg

    def test_negates_less_than(self):
        from nightjar.negation_proof import negate_postcondition
        neg = negate_postcondition("result < 100")
        assert "not" in neg.lower() or "!" in neg
        assert "100" in neg

    def test_negation_of_negation_contains_original(self):
        """Double negation wraps original expression."""
        from nightjar.negation_proof import negate_postcondition
        original = "result >= 0"
        neg = negate_postcondition(original)
        # The negation should contain the original expression
        assert "result" in neg
        assert "0" in neg

    def test_negates_non_parseable_statement(self):
        """Unparseable statement gets wrapped in not()."""
        from nightjar.negation_proof import negate_postcondition
        neg = negate_postcondition("invariant holds")
        assert isinstance(neg, str)
        assert len(neg) > 0


class TestNegProofResult:
    """NegProofResult dataclass structure."""

    def test_has_weak_specs(self):
        from nightjar.negation_proof import NegProofResult
        result = NegProofResult(weak_specs=["result >= 0"], passed=False)
        assert result.weak_specs == ["result >= 0"]

    def test_has_passed_field(self):
        from nightjar.negation_proof import NegProofResult
        result = NegProofResult(weak_specs=[], passed=True)
        assert result.passed is True

    def test_passed_true_when_no_weak_specs(self):
        from nightjar.negation_proof import NegProofResult
        result = NegProofResult(weak_specs=[], passed=True)
        assert result.passed is True

    def test_passed_false_when_weak_specs_present(self):
        from nightjar.negation_proof import NegProofResult
        result = NegProofResult(weak_specs=["weak invariant"], passed=False)
        assert result.passed is False


class TestRunNegationProof:
    """run_negation_proof() detects weak/strong postconditions via CrossHair."""

    def test_catches_weak_postcondition_when_crosshair_confirms_negation(self):
        """CrossHair CONFIRMS negated postcondition (rc=0) → spec is weak.

        When CrossHair confirms `not (result >= 0)` holds for all inputs,
        the original postcondition `result >= 0` is never satisfied → degenerate spec.
        """
        from nightjar.negation_proof import run_negation_proof

        spec = _make_spec(invariants=[
            Invariant(id="INV-1", tier=InvariantTier.FORMAL,
                      statement="result >= 0"),
        ])

        # CrossHair CONFIRMS negated postcondition (returncode=0, no violations)
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "No issues found."
        mock_proc.stderr = ""

        with patch("nightjar.negation_proof._run_crosshair_on_file",
                   return_value=mock_proc):
            result = run_negation_proof(spec, SIMPLE_CODE)

        assert not result.passed, "Spec should be flagged as weak"
        assert len(result.weak_specs) > 0

    def test_passes_strong_postcondition_when_crosshair_finds_counterexample(self):
        """CrossHair finds COUNTEREXAMPLE to negated postcondition → spec is strong.

        When CrossHair finds a counterexample to `not (result >= 0)`, it means
        there exist inputs where the original `result >= 0` holds → spec is meaningful.
        """
        from nightjar.negation_proof import run_negation_proof

        spec = _make_spec(invariants=[
            Invariant(id="INV-2", tier=InvariantTier.FORMAL,
                      statement="result >= 0"),
        ])

        # CrossHair finds counterexample to negated postcondition (returncode=1)
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = "counterexample: result=5"
        mock_proc.stderr = ""

        with patch("nightjar.negation_proof._run_crosshair_on_file",
                   return_value=mock_proc):
            result = run_negation_proof(spec, SIMPLE_CODE)

        assert result.passed, "Strong spec should pass negation proof"
        assert result.weak_specs == []

    def test_skips_when_no_formal_invariants(self):
        """No FORMAL invariants → no negation check needed → passed=True."""
        from nightjar.negation_proof import run_negation_proof

        spec = _make_spec(invariants=[
            Invariant(id="INV-3", tier=InvariantTier.PROPERTY,
                      statement="result is positive"),
        ])

        result = run_negation_proof(spec, SIMPLE_CODE)

        assert result.passed, "No formal invariants → trivially passes"
        assert result.weak_specs == []

    def test_skips_empty_spec(self):
        """Empty spec → passed=True (nothing to check)."""
        from nightjar.negation_proof import run_negation_proof

        spec = _make_spec()
        result = run_negation_proof(spec, SIMPLE_CODE)
        assert result.passed

    def test_crosshair_not_found_returns_pass(self):
        """If CrossHair is not installed, negation proof cannot run → SKIP (passes)."""
        from nightjar.negation_proof import run_negation_proof

        spec = _make_spec(invariants=[
            Invariant(id="INV-4", tier=InvariantTier.FORMAL,
                      statement="result >= 0"),
        ])

        with patch("nightjar.negation_proof._run_crosshair_on_file",
                   side_effect=FileNotFoundError("crosshair not found")):
            result = run_negation_proof(spec, SIMPLE_CODE)

        # When CrossHair is unavailable, skip gracefully (don't block pipeline)
        assert result.passed


class TestStageNegproof:
    """Stage 2.5 (negation_proof) integrates into the verifier pipeline."""

    def test_run_stage_negproof_importable(self):
        from nightjar.verifier import _run_stage_negproof
        assert callable(_run_stage_negproof)

    def test_stage_negproof_returns_skip_for_empty_spec(self):
        """Empty spec (no formal invariants) → SKIP immediately."""
        from nightjar.verifier import _run_stage_negproof

        spec = _make_spec()
        result = _run_stage_negproof(spec, SIMPLE_CODE)

        assert result.status == VerifyStatus.SKIP
        assert result.name == "negation_proof"

    def test_stage_negproof_returns_skip_for_non_formal_invariants(self):
        """PROPERTY/EXAMPLE tier invariants are skipped by negproof."""
        from nightjar.verifier import _run_stage_negproof

        spec = _make_spec(invariants=[
            Invariant(id="INV-5", tier=InvariantTier.PROPERTY,
                      statement="result is non-negative"),
        ])
        result = _run_stage_negproof(spec, SIMPLE_CODE)
        assert result.status == VerifyStatus.SKIP

    def test_stage_negproof_returns_fail_when_spec_is_weak(self):
        """Weak spec (CrossHair confirms negation) → FAIL with weak_spec error."""
        from nightjar.verifier import _run_stage_negproof

        spec = _make_spec(invariants=[
            Invariant(id="INV-6", tier=InvariantTier.FORMAL,
                      statement="result >= 0"),
        ])

        mock_proc = MagicMock()
        mock_proc.returncode = 0  # CrossHair confirms negation → weak spec
        mock_proc.stdout = "No issues found."
        mock_proc.stderr = ""

        with patch("nightjar.negation_proof._run_crosshair_on_file",
                   return_value=mock_proc):
            result = _run_stage_negproof(spec, SIMPLE_CODE)

        assert result.status == VerifyStatus.FAIL
        assert any(e.get("type") == "weak_spec" for e in result.errors)

    def test_stage_negproof_returns_pass_when_spec_is_strong(self):
        """Strong spec (CrossHair finds CE to negation) → PASS."""
        from nightjar.verifier import _run_stage_negproof

        spec = _make_spec(invariants=[
            Invariant(id="INV-7", tier=InvariantTier.FORMAL,
                      statement="result >= 0"),
        ])

        mock_proc = MagicMock()
        mock_proc.returncode = 1  # CrossHair finds CE → spec is strong
        mock_proc.stdout = "counterexample: result=5"
        mock_proc.stderr = ""

        with patch("nightjar.negation_proof._run_crosshair_on_file",
                   return_value=mock_proc):
            result = _run_stage_negproof(spec, SIMPLE_CODE)

        assert result.status == VerifyStatus.PASS

    def test_run_pipeline_calls_negproof_stage(self):
        """run_pipeline calls _run_stage_negproof between stages {2,3} and stage 4."""
        from nightjar.verifier import run_pipeline
        from nightjar.types import StageResult, VerifyStatus

        # Spec must have at least one invariant so the empty-spec guard does not
        # short-circuit before negproof runs (Bug 7 fix).
        spec = _make_spec(invariants=[
            Invariant(id="INV-1", tier=InvariantTier.FORMAL, statement="result >= 0"),
        ])
        pass_result = StageResult(stage=0, name="test", status=VerifyStatus.PASS)

        with patch("nightjar.verifier._run_stage_0", return_value=pass_result), \
             patch("nightjar.verifier._run_stage_1", return_value=pass_result), \
             patch("nightjar.verifier._run_stage_2", return_value=pass_result), \
             patch("nightjar.verifier._run_stage_3", return_value=pass_result), \
             patch("nightjar.verifier._run_stage_negproof") as mock_neg, \
             patch("nightjar.verifier._run_stage_4", return_value=pass_result):
            mock_neg.return_value = StageResult(
                stage=5, name="negation_proof", status=VerifyStatus.SKIP
            )
            run_pipeline(spec, SIMPLE_CODE)

        assert mock_neg.called, "_run_stage_negproof should be called by run_pipeline"

    def test_pipeline_stops_at_negproof_fail(self):
        """If negproof fails (weak spec), pipeline stops before stage 4."""
        from nightjar.verifier import run_pipeline
        from nightjar.types import StageResult, VerifyStatus

        # Spec must have at least one invariant so the empty-spec guard does not
        # short-circuit before negproof runs (Bug 7 fix).
        spec = _make_spec(invariants=[
            Invariant(id="INV-1", tier=InvariantTier.FORMAL, statement="result >= 0"),
        ])
        pass_result = StageResult(stage=0, name="test", status=VerifyStatus.PASS)
        fail_result = StageResult(
            stage=5, name="negation_proof", status=VerifyStatus.FAIL,
            errors=[{"type": "weak_spec", "message": "degenerate spec"}],
        )

        with patch("nightjar.verifier._run_stage_0", return_value=pass_result), \
             patch("nightjar.verifier._run_stage_1", return_value=pass_result), \
             patch("nightjar.verifier._run_stage_2", return_value=pass_result), \
             patch("nightjar.verifier._run_stage_3", return_value=pass_result), \
             patch("nightjar.verifier._run_stage_negproof", return_value=fail_result), \
             patch("nightjar.verifier._run_stage_4") as mock_formal:
            result = run_pipeline(spec, SIMPLE_CODE)

        assert not result.verified, "Pipeline should fail when negproof fails"
        mock_formal.assert_not_called(), "Stage 4 should not run after negproof fail"
