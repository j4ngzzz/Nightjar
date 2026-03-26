"""Tests for herd immunity threshold logic.

When pattern confidence > 0.95 across 50+ tenants (DP-protected count),
promote to UNIVERSAL — applied to all new CARD builds regardless of
whether that tenant experienced the failure.

References:
- [REF-C10] Herd immunity via differential privacy
- [REF-C09] Immune system acquired immunity — universal invariants
"""

import pytest

from immune.herd import (
    HerdConfig,
    HerdResult,
    check_herd_immunity,
    evaluate_patterns,
    promote_eligible_patterns,
)
from immune.pattern_library import PatternLibrary, InvariantPattern
from immune.privacy import dp_count, dp_mean


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "patterns.db")


@pytest.fixture
def library(db_path):
    return PatternLibrary(db_path)


@pytest.fixture
def config():
    return HerdConfig(
        confidence_threshold=0.95,
        tenant_count_threshold=50,
        epsilon=1.0,
    )


def _make_pattern(
    fingerprint: str = "fp1",
    tenant_count: float = 60.0,
    confidence: float = 0.97,
    is_universal: bool = False,
) -> InvariantPattern:
    return InvariantPattern(
        pattern_id="",
        fingerprint=fingerprint,
        abstract_form=f"Error on ({fingerprint})",
        abstract_invariant=f"assert {fingerprint} is valid",
        tenant_count_dp=tenant_count,
        confidence_dp=confidence,
        verification_method="crosshair",
        proof_hash="sha256:abc",
        is_universal=is_universal,
    )


class TestHerdConfig:
    """Tests for herd immunity configuration."""

    def test_default_config(self):
        config = HerdConfig()
        assert config.confidence_threshold == 0.95
        assert config.tenant_count_threshold == 50
        assert config.epsilon == 1.0

    def test_custom_config(self):
        config = HerdConfig(confidence_threshold=0.9, tenant_count_threshold=30)
        assert config.confidence_threshold == 0.9
        assert config.tenant_count_threshold == 30


class TestCheckHerdImmunity:
    """Tests for the herd immunity check on a single pattern."""

    def test_high_confidence_high_count_passes(self, config):
        pattern = _make_pattern(tenant_count=60.0, confidence=0.97)
        result = check_herd_immunity(pattern, config)
        assert result.eligible is True

    def test_low_confidence_fails(self, config):
        pattern = _make_pattern(tenant_count=60.0, confidence=0.80)
        result = check_herd_immunity(pattern, config)
        assert result.eligible is False

    def test_low_count_fails(self, config):
        pattern = _make_pattern(tenant_count=10.0, confidence=0.99)
        result = check_herd_immunity(pattern, config)
        assert result.eligible is False

    def test_boundary_confidence(self, config):
        pattern = _make_pattern(tenant_count=60.0, confidence=0.95)
        result = check_herd_immunity(pattern, config)
        assert result.eligible is True

    def test_boundary_count(self, config):
        pattern = _make_pattern(tenant_count=50.0, confidence=0.96)
        result = check_herd_immunity(pattern, config)
        assert result.eligible is True

    def test_already_universal_is_eligible(self, config):
        pattern = _make_pattern(
            tenant_count=100.0, confidence=0.99, is_universal=True
        )
        result = check_herd_immunity(pattern, config)
        assert result.eligible is True

    def test_result_has_details(self, config):
        pattern = _make_pattern(tenant_count=60.0, confidence=0.97)
        result = check_herd_immunity(pattern, config)
        assert isinstance(result, HerdResult)
        assert result.tenant_count_dp == 60.0
        assert result.confidence_dp == 0.97


class TestEvaluatePatterns:
    """Tests for evaluating all patterns in the library."""

    def test_evaluate_returns_results(self, library, config):
        library.add_pattern(_make_pattern("fp1", 60.0, 0.97))
        library.add_pattern(_make_pattern("fp2", 10.0, 0.50))

        results = evaluate_patterns(library, config)
        assert len(results) == 2

    def test_evaluate_identifies_eligible(self, library, config):
        library.add_pattern(_make_pattern("fp1", 60.0, 0.97))
        library.add_pattern(_make_pattern("fp2", 10.0, 0.50))

        results = evaluate_patterns(library, config)
        eligible = [r for r in results if r.eligible]
        assert len(eligible) == 1

    def test_evaluate_empty_library(self, library, config):
        results = evaluate_patterns(library, config)
        assert results == []


class TestPromoteEligiblePatterns:
    """Tests for promoting eligible patterns to universal."""

    def test_promotes_eligible(self, library, config):
        pid = library.add_pattern(_make_pattern("fp1", 60.0, 0.97))
        library.add_pattern(_make_pattern("fp2", 10.0, 0.50))

        promoted = promote_eligible_patterns(library, config)
        assert len(promoted) == 1

        # Check the pattern is now universal
        pattern = library.get_pattern(promoted[0])
        assert pattern.is_universal is True

    def test_does_not_promote_ineligible(self, library, config):
        library.add_pattern(_make_pattern("fp1", 10.0, 0.50))

        promoted = promote_eligible_patterns(library, config)
        assert promoted == []

    def test_skips_already_universal(self, library, config):
        pid = library.add_pattern(_make_pattern("fp1", 60.0, 0.97, is_universal=True))

        promoted = promote_eligible_patterns(library, config)
        # Already universal — not in the "newly promoted" list
        assert promoted == []

    def test_promotes_multiple(self, library, config):
        library.add_pattern(_make_pattern("fp1", 60.0, 0.97))
        library.add_pattern(_make_pattern("fp2", 80.0, 0.99))
        library.add_pattern(_make_pattern("fp3", 5.0, 0.30))

        promoted = promote_eligible_patterns(library, config)
        assert len(promoted) == 2
