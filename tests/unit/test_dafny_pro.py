"""Tests for DafnyPro wrapper — W1.2.

Validates the three-component DafnyPro architecture:
  1. Diff-checker: prevents LLM from modifying base program logic
  2. Invariant pruner: removes unnecessary annotations before Z3
  3. Hint-augmentation: adds intermediate assert statements for complex reasoning

References:
- Scout 3 Section 2.1: DafnyPro framework description
- Clean-room CR-11: arxiv:2601.05385 (POPL 2026) — algorithm-only, no code released
- Scout 3 S2.1: Claude Sonnet + DafnyPro = 86% DafnyBench (+16pp over baseline)
"""

import pytest
from nightjar.dafny_pro import DafnyProWrapper


BASE_PROGRAM = """\
method Process(x: int) returns (r: int)
{
  r := x * 2;
}
"""

ANNOTATED_PROGRAM = """\
method Process(x: int) returns (r: int)
  requires x > 0
  ensures r > 0
{
  r := x * 2;
}
"""

# LLM modified the base method body — should be REJECTED
MODIFIED_BASE = """\
method Process(x: int) returns (r: int)
  requires x > 0
  ensures r > 0
{
  r := x * 3;  // changed from x*2 to x*3 — base modification!
}
"""

PRUNABLE_PROGRAM = """\
method Add(a: int, b: int) returns (r: int)
  requires a >= 0  // useful
  requires true    // trivially true — should be pruned
  ensures r == a + b
  ensures r >= 0   // redundant: follows from r == a + b and a >= 0, b implicit
{
  r := a + b;
}
"""

ERROR_CONTEXT = [
    {
        "type": "postcondition_failure",
        "line": 6,
        "message": "a postcondition could not be proved on this return path",
        "file": "module.dfy",
    }
]


class TestDiffChecker:
    """Tests for DafnyProWrapper.check_diff — component 1 of DafnyPro.

    Per CR-11 (arxiv:2601.05385): diff-checker prevents LLM from modifying
    base program logic. Only annotations (requires, ensures, invariant,
    decreases, assert) may be added.
    """

    def test_diff_checker_accepts_annotation_only_changes(self):
        """Diff-checker ACCEPTS when LLM only adds annotations.

        Adding requires/ensures/invariant/decreases clauses to a method
        without changing the body logic is a valid annotation.
        """
        wrapper = DafnyProWrapper()
        result = wrapper.check_diff(BASE_PROGRAM, ANNOTATED_PROGRAM)
        assert result is True, (
            "Diff-checker should accept pure annotation additions "
            "(requires/ensures added, body unchanged)"
        )

    def test_diff_checker_rejects_modified_base_program(self):
        """Diff-checker REJECTS when LLM modifies base program logic.

        Per CR-11: the key safety invariant of DafnyPro is that the base
        program logic must remain unchanged. Modifications to method bodies,
        types, or function calls indicate LLM hallucination.
        """
        wrapper = DafnyProWrapper()
        result = wrapper.check_diff(BASE_PROGRAM, MODIFIED_BASE)
        assert result is False, (
            "Diff-checker should reject when base program body is modified "
            "(x*2 changed to x*3)"
        )

    def test_diff_checker_accepts_identical_programs(self):
        """Diff-checker ACCEPTS when base and annotated are identical."""
        wrapper = DafnyProWrapper()
        result = wrapper.check_diff(BASE_PROGRAM, BASE_PROGRAM)
        assert result is True

    def test_diff_checker_rejects_added_method(self):
        """Diff-checker REJECTS when LLM adds a new method to the file."""
        wrapper = DafnyProWrapper()
        extra_method = ANNOTATED_PROGRAM + "\nmethod Extra() { }\n"
        result = wrapper.check_diff(BASE_PROGRAM, extra_method)
        assert result is False, "Adding new methods is not a valid annotation"

    def test_diff_checker_returns_bool(self):
        """check_diff always returns a bool."""
        wrapper = DafnyProWrapper()
        result = wrapper.check_diff(BASE_PROGRAM, ANNOTATED_PROGRAM)
        assert isinstance(result, bool)


class TestInvariantPruner:
    """Tests for DafnyProWrapper.prune_invariants — component 2 of DafnyPro.

    Per CR-11: invariant pruner removes unnecessary annotations before Z3.
    Unnecessary invariants increase verification overhead without contributing
    to correctness proofs.
    """

    def test_pruner_removes_trivially_true_requires(self):
        """Pruner removes 'requires true' — always satisfied, never useful.

        Per Scout 3 S2.1: pruner eliminates annotations that 'add noise
        without contributing to the verification task'.
        """
        wrapper = DafnyProWrapper()
        pruned = wrapper.prune_invariants(PRUNABLE_PROGRAM)
        assert "requires true" not in pruned, (
            "'requires true' is trivially true and should be pruned"
        )

    def test_pruner_retains_useful_preconditions(self):
        """Pruner keeps non-trivial requires clauses."""
        wrapper = DafnyProWrapper()
        pruned = wrapper.prune_invariants(PRUNABLE_PROGRAM)
        assert "requires a >= 0" in pruned, (
            "Non-trivial precondition 'requires a >= 0' must be retained"
        )

    def test_pruner_retains_postconditions(self):
        """Pruner keeps ensures clauses."""
        wrapper = DafnyProWrapper()
        pruned = wrapper.prune_invariants(PRUNABLE_PROGRAM)
        assert "ensures r == a + b" in pruned, (
            "ensures clause must be retained after pruning"
        )

    def test_pruner_removes_duplicate_invariants(self):
        """Pruner removes duplicate invariant lines."""
        wrapper = DafnyProWrapper()
        with_dupes = """\
method Foo(x: int) returns (r: int)
  requires x > 0
  requires x > 0
  ensures r > 0
{
  r := x;
}
"""
        pruned = wrapper.prune_invariants(with_dupes)
        # Count occurrences of 'requires x > 0' — should be exactly 1
        count = pruned.count("requires x > 0")
        assert count == 1, f"Duplicate 'requires x > 0' should be pruned, got {count}"

    def test_pruner_returns_string(self):
        """prune_invariants returns a string."""
        wrapper = DafnyProWrapper()
        result = wrapper.prune_invariants(ANNOTATED_PROGRAM)
        assert isinstance(result, str)

    def test_pruner_does_not_modify_method_bodies(self):
        """Pruner never changes method body logic."""
        wrapper = DafnyProWrapper()
        pruned = wrapper.prune_invariants(ANNOTATED_PROGRAM)
        assert "r := x * 2;" in pruned, "Method body must be unchanged after pruning"


class TestHintAugmentation:
    """Tests for DafnyProWrapper.augment_hints — component 3 of DafnyPro.

    Per CR-11: hint-augmentation adds intermediate assert statements for
    complex reasoning chains. These hints guide Z3 through non-obvious
    proof steps.
    """

    def test_hint_augmentation_adds_intermediate_asserts(self):
        """augment_hints adds assert statements near failure locations.

        Per Scout 3 S2.1: hint-augmentation 'retrieves problem-independent
        proof strategy templates' and inserts intermediate assertions to
        guide the verifier through complex reasoning chains.
        """
        wrapper = DafnyProWrapper()
        augmented = wrapper.augment_hints(ANNOTATED_PROGRAM, ERROR_CONTEXT)
        assert "assert" in augmented, (
            "Hint augmentation should add assert statements near failure points"
        )

    def test_hint_augmentation_returns_string(self):
        """augment_hints returns a string."""
        wrapper = DafnyProWrapper()
        result = wrapper.augment_hints(ANNOTATED_PROGRAM, ERROR_CONTEXT)
        assert isinstance(result, str)

    def test_hint_augmentation_with_no_errors_is_noop(self):
        """With no error context, augment_hints returns the input unchanged."""
        wrapper = DafnyProWrapper()
        result = wrapper.augment_hints(ANNOTATED_PROGRAM, [])
        assert result == ANNOTATED_PROGRAM, (
            "With no errors, hint augmentation should return input unchanged"
        )

    def test_hint_augmentation_preserves_method_structure(self):
        """Augmented code still has method signature and body."""
        wrapper = DafnyProWrapper()
        augmented = wrapper.augment_hints(ANNOTATED_PROGRAM, ERROR_CONTEXT)
        assert "method Process" in augmented
        assert "r := x * 2;" in augmented


class TestDafnyProWrapper:
    """Integration tests for the full DafnyProWrapper pipeline."""

    def test_wrapper_apply_returns_result_with_all_components(self):
        """apply() returns DafnyProResult with diff_ok, pruned_code, augmented_code.

        The full pipeline: check diff → prune → augment → return result.
        """
        from nightjar.dafny_pro import DafnyProResult
        wrapper = DafnyProWrapper()
        result = wrapper.apply(BASE_PROGRAM, ANNOTATED_PROGRAM, ERROR_CONTEXT)
        assert isinstance(result, DafnyProResult)
        assert hasattr(result, "diff_ok")
        assert hasattr(result, "pruned_code")
        assert hasattr(result, "augmented_code")

    def test_wrapper_rejects_pipeline_on_diff_failure(self):
        """apply() returns diff_ok=False when base is modified."""
        wrapper = DafnyProWrapper()
        result = wrapper.apply(BASE_PROGRAM, MODIFIED_BASE, [])
        assert result.diff_ok is False

    def test_wrapper_runs_full_pipeline_on_valid_input(self):
        """apply() runs pruning + augmentation when diff_ok."""
        wrapper = DafnyProWrapper()
        result = wrapper.apply(BASE_PROGRAM, ANNOTATED_PROGRAM, ERROR_CONTEXT)
        assert result.diff_ok is True
        assert isinstance(result.pruned_code, str)
        assert isinstance(result.augmented_code, str)
