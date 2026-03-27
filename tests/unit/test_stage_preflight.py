"""Tests for Stage 0: Pre-flight verification.

Stage 0 validates:
1. .card.md YAML frontmatter is well-formed and parseable
2. Required fields exist (card-version, id, title, status)
3. Invariant tiers are valid values
4. If generated code is provided, Python AST parses successfully

Reference: docs/ARCHITECTURE.md Section 3 (Stage 0)
"""

import pytest
from nightjar.stages.preflight import run_preflight, check_dead_constraints
from nightjar.types import StageResult, VerifyStatus


class TestPreflightValidSpec:
    """Pre-flight should PASS for well-formed .card.md specs."""

    def test_minimal_spec_passes(self):
        """Minimal valid spec should pass preflight."""
        result = run_preflight("tests/fixtures/minimal.card.md")
        assert isinstance(result, StageResult)
        assert result.stage == 0
        assert result.name == "preflight"
        assert result.status == VerifyStatus.PASS

    def test_full_spec_passes(self):
        """Full payment spec should pass preflight."""
        result = run_preflight("tests/fixtures/payment.card.md")
        assert result.status == VerifyStatus.PASS

    def test_duration_is_recorded(self):
        """Preflight should record duration in milliseconds."""
        result = run_preflight("tests/fixtures/minimal.card.md")
        assert result.duration_ms >= 0


class TestPreflightInvalidSpec:
    """Pre-flight should FAIL for malformed specs."""

    def test_malformed_yaml_fails(self):
        """Malformed YAML frontmatter should fail with error details."""
        result = run_preflight("tests/fixtures/invalid.card.md")
        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0
        assert any("yaml" in str(e).lower() or "parse" in str(e).lower()
                    for e in result.errors)

    def test_nonexistent_file_fails(self):
        """Missing file should fail with clear error."""
        result = run_preflight("tests/fixtures/nonexistent.card.md")
        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0

    def test_missing_required_fields_fails(self):
        """Spec missing card-version or id should fail."""
        result = run_preflight("tests/fixtures/missing_fields.card.md")
        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0
        assert any("required" in str(e).lower() or "missing" in str(e).lower()
                    for e in result.errors)


class TestPreflightCodeValidation:
    """Pre-flight should validate generated Python code AST if provided."""

    def test_valid_python_code_passes(self, tmp_path):
        """Valid Python code should pass AST check."""
        code_file = tmp_path / "valid.py"
        code_file.write_text("def hello():\n    return 'world'\n")
        result = run_preflight(
            "tests/fixtures/minimal.card.md",
            code_path=str(code_file),
        )
        assert result.status == VerifyStatus.PASS

    def test_invalid_python_code_fails(self, tmp_path):
        """Syntactically invalid Python should fail AST check."""
        code_file = tmp_path / "broken.py"
        code_file.write_text("def hello(\n    return 'world'\n")
        result = run_preflight(
            "tests/fixtures/minimal.card.md",
            code_path=str(code_file),
        )
        assert result.status == VerifyStatus.FAIL
        assert len(result.errors) > 0
        assert any("syntax" in str(e).lower() or "ast" in str(e).lower()
                    for e in result.errors)

    def test_empty_python_code_passes(self, tmp_path):
        """Empty Python file should pass AST check (valid empty module)."""
        code_file = tmp_path / "empty.py"
        code_file.write_text("")
        result = run_preflight(
            "tests/fixtures/minimal.card.md",
            code_path=str(code_file),
        )
        assert result.status == VerifyStatus.PASS


# ── W2-1: Dead constraint detection [deal linter pattern] ───────────────────


class TestDeadConstraints:
    """check_dead_constraints() catches trivially true/false invariants.

    Uses deal's linter pattern: exec expression against boundary values,
    skip undecidable inputs (NameError, SyntaxError). Natural language
    invariants always produce SyntaxError → skipped → no false positives.

    Source: life4/deal linter (_contract.py, _rules.py)
    """

    def test_natural_language_invariant_is_skipped(self):
        """Natural language statements cannot be compiled → fully undecidable → skip."""
        invariants = [{"id": "INV-NL", "statement": "always returns a positive integer"}]
        result = check_dead_constraints(invariants)
        assert result == []

    def test_always_true_expression_flagged_as_dead(self):
        """Expression that is always True for all boundary values is a dead constraint."""
        invariants = [{"id": "INV-DEAD", "statement": "True"}]
        result = check_dead_constraints(invariants)
        assert len(result) == 1
        assert result[0]["type"] == "dead_constraint"
        assert result[0]["invariant_id"] == "INV-DEAD"

    def test_always_false_expression_flagged_as_unsatisfiable(self):
        """Expression that is always False for all boundary values is unsatisfiable."""
        invariants = [{"id": "INV-UNSAT", "statement": "False"}]
        result = check_dead_constraints(invariants)
        assert len(result) == 1
        assert result[0]["type"] == "unsatisfiable_constraint"
        assert result[0]["invariant_id"] == "INV-UNSAT"

    def test_mixed_outcome_expression_not_flagged(self):
        """x >= 0 is False for x=-1, True for x=1 → mixed → not flagged."""
        invariants = [{"id": "INV-GOOD", "statement": "x >= 0"}]
        result = check_dead_constraints(invariants)
        assert result == []

    def test_external_name_silently_skipped(self):
        """Invariant referencing unknown name → NameError → UNKNOWN → skip."""
        invariants = [{"id": "INV-EXT", "statement": "some_external_func(x) > 0"}]
        result = check_dead_constraints(invariants)
        assert result == []

    def test_empty_invariant_list_returns_empty(self):
        """Empty invariant list produces no warnings."""
        assert check_dead_constraints([]) == []

    def test_invariant_without_statement_skipped(self):
        """Invariant dict with no 'statement' key is silently skipped."""
        invariants = [{"id": "INV-NOSTMT", "tier": "property"}]
        result = check_dead_constraints(invariants)
        assert result == []

    def test_run_preflight_flags_dead_constraint_in_spec(self, tmp_path):
        """run_preflight fails Stage 0 when spec contains a trivially-true invariant."""
        spec = tmp_path / "dead.card.md"
        spec.write_text(
            "---\ncard-version: '1.0'\nid: test\ninvariants:\n"
            "  - id: INV-DEAD\n    tier: property\n    statement: 'True'\n---\n"
        )
        result = run_preflight(str(spec))
        assert result.status == VerifyStatus.FAIL
        assert any(e.get("type") == "dead_constraint" for e in result.errors)
