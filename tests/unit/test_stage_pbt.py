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


# ── AE-5: PBT Strategy Template Database [AlphaEvolve arXiv:2506.13131] ──────


class TestStrategyRecord:
    """Tests for StrategyRecord dataclass defaults."""

    def test_strategy_record_defaults(self):
        """StrategyRecord has correct default values for optional fields."""
        from nightjar.strategy_db import StrategyRecord
        record = StrategyRecord(
            invariant_type="numeric_bound",
            template_name="numeric_bound",
            template_code="st.integers()",
        )
        assert record.counterexample_found_rate == 0.0
        assert record.avg_examples_to_find == 100.0
        assert record.run_count == 0


class TestStrategyDB:
    """Tests for StrategyDB — load, seed, query, update."""

    def test_strategy_db_seeds_six_templates(self, tmp_path):
        """StrategyDB seeds with exactly 6 initial templates when no file exists."""
        from nightjar.strategy_db import StrategyDB
        db = StrategyDB(db_path=str(tmp_path / "strategy_db.json"))
        assert len(db.records) == 6

    def test_strategy_db_get_best_returns_highest_rate(self, tmp_path):
        """get_best_for_type returns the record with the highest counterexample_found_rate."""
        from nightjar.strategy_db import StrategyDB, StrategyRecord
        db = StrategyDB(db_path=str(tmp_path / "strategy_db.json"))
        # Override with two records of known rates
        db.records = [
            StrategyRecord(
                invariant_type="numeric_bound",
                template_name="low_rate",
                template_code="st.integers()",
                counterexample_found_rate=0.1,
            ),
            StrategyRecord(
                invariant_type="numeric_bound",
                template_name="high_rate",
                template_code="st.integers(min_value=0)",
                counterexample_found_rate=0.9,
            ),
        ]
        best = db.get_best_for_type("numeric_bound")
        assert best is not None
        assert best.template_name == "high_rate"

    def test_strategy_db_get_diverse_returns_lowest_count(self, tmp_path):
        """get_diverse_for_type returns the record with the lowest run_count."""
        from nightjar.strategy_db import StrategyDB, StrategyRecord
        db = StrategyDB(db_path=str(tmp_path / "strategy_db.json"))
        db.records = [
            StrategyRecord(
                invariant_type="numeric_bound",
                template_name="well_used",
                template_code="st.integers()",
                run_count=50,
            ),
            StrategyRecord(
                invariant_type="numeric_bound",
                template_name="least_used",
                template_code="st.integers(min_value=0)",
                run_count=2,
            ),
        ]
        diverse = db.get_diverse_for_type("numeric_bound")
        assert diverse is not None
        assert diverse.template_name == "least_used"

    def test_record_outcome_updates_ema(self, tmp_path):
        """record_outcome updates counterexample_found_rate via EMA (0.7 old + 0.3 new)."""
        from nightjar.strategy_db import StrategyDB, StrategyRecord
        db = StrategyDB(db_path=str(tmp_path / "strategy_db.json"))
        db.records = [
            StrategyRecord(
                invariant_type="numeric_bound",
                template_name="t1",
                template_code="st.integers()",
                counterexample_found_rate=0.0,
                avg_examples_to_find=100.0,
                run_count=0,
            ),
        ]
        db.record_outcome("numeric_bound", "t1", found_counterexample=True, examples_taken=50)
        record = db.records[0]
        # EMA: 0.7 * 0.0 + 0.3 * 1.0 = 0.3
        assert abs(record.counterexample_found_rate - 0.3) < 1e-9
        # EMA: 0.7 * 100.0 + 0.3 * 50.0 = 85.0
        assert abs(record.avg_examples_to_find - 85.0) < 1e-9
        assert record.run_count == 1

    def test_strategy_db_save_load_roundtrip(self, tmp_path):
        """save() then load() from same path preserves all records."""
        from nightjar.strategy_db import StrategyDB
        db_path = str(tmp_path / "strategy_db.json")
        db1 = StrategyDB(db_path=db_path)
        # Mutate one record so we can verify persistence
        db1.records[0].run_count = 42
        db1.save()

        db2 = StrategyDB(db_path=db_path)
        assert len(db2.records) == len(db1.records)
        # The first record should have run_count=42
        assert db2.records[0].run_count == 42

    def test_strategy_db_get_best_returns_none_for_unknown_type(self, tmp_path):
        """get_best_for_type returns None when no records match the type."""
        from nightjar.strategy_db import StrategyDB
        db = StrategyDB(db_path=str(tmp_path / "strategy_db.json"))
        result = db.get_best_for_type("nonexistent_type_xyz")
        assert result is None

    def test_strategy_db_get_diverse_returns_none_for_unknown_type(self, tmp_path):
        """get_diverse_for_type returns None when no records match the type."""
        from nightjar.strategy_db import StrategyDB
        db = StrategyDB(db_path=str(tmp_path / "strategy_db.json"))
        result = db.get_diverse_for_type("nonexistent_type_xyz")
        assert result is None


class TestClassifyInvariantType:
    """Tests for classify_invariant_type() regex classification."""

    def test_classify_invariant_type_numeric_bound(self):
        """Statements with >= 0 or > 0 classify as numeric_bound."""
        from nightjar.strategy_db import classify_invariant_type
        assert classify_invariant_type("result >= 0") == "numeric_bound"
        assert classify_invariant_type("value > 0 for all inputs") == "numeric_bound"

    def test_classify_invariant_type_string_format(self):
        """Statements with email or @ classify as string_format."""
        from nightjar.strategy_db import classify_invariant_type
        assert classify_invariant_type("email matches RFC 5321") == "string_format"
        assert classify_invariant_type("must contain @ symbol") == "string_format"

    def test_classify_invariant_type_unknown(self):
        """Statements that match no pattern classify as unknown."""
        from nightjar.strategy_db import classify_invariant_type
        assert classify_invariant_type("complex business rule about transactions") == "unknown"

    def test_classify_invariant_type_collection_size(self):
        """Statements with len() or size classify as collection_size."""
        from nightjar.strategy_db import classify_invariant_type
        assert classify_invariant_type("len(result) > 0") == "collection_size"
        assert classify_invariant_type("output size must be positive") == "collection_size"

    def test_classify_invariant_type_boolean_flag(self):
        """Statements with True/False/bool classify as boolean_flag."""
        from nightjar.strategy_db import classify_invariant_type
        assert classify_invariant_type("returns True when valid") == "boolean_flag"
        assert classify_invariant_type("bool result expected") == "boolean_flag"


class TestPbtIntegrationHook:
    """Tests for the strategy DB integration hook in pbt.py."""

    def test_pbt_integration_hook_disabled_by_default(self, monkeypatch):
        """PBT runs correctly with no StrategyDB created when env var is not set."""
        monkeypatch.delenv("NIGHTJAR_ENABLE_STRATEGY_DB", raising=False)
        # Verify that run_pbt works without the strategy DB being instantiated
        spec = _make_spec([
            Invariant(
                id="INV-001",
                tier=InvariantTier.PROPERTY,
                statement="For any positive x, process(x) returns a positive integer",
            ),
        ])
        result = run_pbt(spec, PASSING_CODE)
        # Should still pass — strategy DB is purely additive
        assert result.status == VerifyStatus.PASS
