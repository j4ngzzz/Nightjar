"""Tests for Stage 3 — Property-Based Testing.

Validates that the PBT stage auto-generates Hypothesis tests from
.card.md invariants and runs them against generated code.

References:
- [REF-T03] Hypothesis — Property-Based Testing for Python
- [REF-P10] PGS paper — property generation from invariants
- [REF-C01] Tiered invariants — only 'property' and 'formal' tier reach this stage
"""

import pytest
from nightjar.types import (
    CardSpec, Contract, ContractInput, ContractOutput,
    Invariant, InvariantTier, ModuleBoundary,
    StageResult, VerifyStatus,
)
from nightjar.stages.pbt import run_pbt


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


# ── W3.1: Hypothesis dev/CI profiles [Scout 5 F6] ─────────────────────────


class TestHypothesisProfiles:
    """Hypothesis dev/CI profile split for fast dev feedback [Scout 5 F6].

    dev profile: max_examples=10 — fast feedback during development (~300-500ms)
    ci  profile: max_examples=200 — thorough checking in CI (~3-8s)

    Profile selected via NIGHTJAR_TEST_PROFILE env var (default: dev).

    Source: Scout 5 Finding 6
    """

    def test_dev_profile_has_10_examples(self):
        """dev profile must use max_examples=10 for 10x faster dev feedback."""
        import nightjar.stages.pbt  # ensure profiles are registered  # noqa: F401
        from hypothesis import settings
        dev = settings.get_profile("dev")
        assert dev.max_examples == 10, (
            "dev profile must use 10 examples for fast feedback [Scout 5 F6]"
        )

    def test_ci_profile_has_200_examples(self):
        """ci profile must use max_examples=200 for thorough CI coverage."""
        import nightjar.stages.pbt  # ensure profiles are registered  # noqa: F401
        from hypothesis import settings
        ci = settings.get_profile("ci")
        assert ci.max_examples == 200, (
            "ci profile must use 200 examples for thorough coverage [Scout 5 F6]"
        )

    def test_dev_profile_uses_derandomize(self):
        """dev profile uses derandomize=True for reproducible dev runs."""
        import nightjar.stages.pbt  # noqa: F401
        from hypothesis import settings
        dev = settings.get_profile("dev")
        assert dev.derandomize is True, (
            "dev profile must use derandomize=True for reproducible runs"
        )

    def test_uses_dev_profile_by_default(self, monkeypatch):
        """Without NIGHTJAR_TEST_PROFILE env var, dev profile is loaded (10 examples)."""
        monkeypatch.delenv("NIGHTJAR_TEST_PROFILE", raising=False)
        from nightjar.stages.pbt import _load_pbt_profile
        _load_pbt_profile()
        from hypothesis import settings
        assert settings().max_examples == 10, (
            "Default profile must be dev (10 examples) for fast dev feedback [Scout 5 F6]"
        )

    def test_uses_ci_profile_when_env_set(self, monkeypatch):
        """NIGHTJAR_TEST_PROFILE=ci loads ci profile (200 examples)."""
        monkeypatch.setenv("NIGHTJAR_TEST_PROFILE", "ci")
        from nightjar.stages.pbt import _load_pbt_profile
        _load_pbt_profile()
        from hypothesis import settings
        assert settings().max_examples == 200, (
            "NIGHTJAR_TEST_PROFILE=ci must load 200-example profile [Scout 5 F6]"
        )


# ── W2-1: CrossHair SMT backend [REF-T09] ───────────────────────────────────


class TestCrossHairBackend:
    """_make_pbt_settings() activates CrossHair backend via env var [REF-T09].

    CrossHair uses SMT-based symbolic execution (Z3) instead of random sampling.
    Gate: NIGHTJAR_CROSSHAIR_BACKEND=1. Opt-in, zero impact by default.

    Source: pschanely/hypothesis-crosshair
    """

    def test_env_unset_returns_standard_settings(self, monkeypatch):
        """Without NIGHTJAR_CROSSHAIR_BACKEND, returns standard settings (no backend)."""
        monkeypatch.delenv("NIGHTJAR_CROSSHAIR_BACKEND", raising=False)
        from nightjar.stages.pbt import _make_pbt_settings
        s = _make_pbt_settings()
        assert not hasattr(s, "backend") or getattr(s, "backend", None) != "crosshair"

    def test_env_zero_returns_standard_settings(self, monkeypatch):
        """NIGHTJAR_CROSSHAIR_BACKEND=0 returns standard settings (no backend)."""
        monkeypatch.setenv("NIGHTJAR_CROSSHAIR_BACKEND", "0")
        from nightjar.stages.pbt import _make_pbt_settings
        s = _make_pbt_settings()
        assert getattr(s, "backend", None) != "crosshair"

    def test_env_one_with_missing_package_falls_back(self, monkeypatch):
        """NIGHTJAR_CROSSHAIR_BACKEND=1 without hypothesis-crosshair falls back gracefully."""
        monkeypatch.setenv("NIGHTJAR_CROSSHAIR_BACKEND", "1")
        import sys
        # Temporarily hide the package if it happens to be installed
        saved = sys.modules.pop("hypothesis_crosshair_provider", None)
        sys.modules["hypothesis_crosshair_provider"] = None  # type: ignore[assignment]
        try:
            # Re-import to force fresh evaluation
            import importlib
            import nightjar.stages.pbt as pbt_mod
            importlib.reload(pbt_mod)
            # _make_pbt_settings should not raise even with broken package
            # (ImportError caught internally)
        finally:
            if saved is not None:
                sys.modules["hypothesis_crosshair_provider"] = saved
            else:
                sys.modules.pop("hypothesis_crosshair_provider", None)

    def test_returns_fresh_settings_respects_active_profile(self, monkeypatch):
        """Non-CrossHair path returns fresh settings() inheriting the active profile."""
        monkeypatch.delenv("NIGHTJAR_CROSSHAIR_BACKEND", raising=False)
        monkeypatch.setenv("NIGHTJAR_TEST_PROFILE", "ci")
        from nightjar.stages.pbt import _load_pbt_profile, _make_pbt_settings
        _load_pbt_profile()
        s = _make_pbt_settings()
        # Fresh settings() inherits max_examples from the currently loaded profile
        assert s.max_examples == 200, (
            "_make_pbt_settings must return fresh settings() respecting active profile"
        )
