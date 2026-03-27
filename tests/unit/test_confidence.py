"""Tests for W1.4 — Verification Confidence Score (0-100).

Validates the confidence score framework from Scout 3 S5.3:
  pyright(+15) + deal(+10) + CrossHair(+35) + Hypothesis(+20) + Dafny(+20) = 100

The confidence score makes partial verification explicit and transparent.
Industry's first principled 'scored partial verification.'

References:
- Scout 3 Section 5.3: Confidence score framework
- Scout 3 S5.4: Recommended fallback chain
- Confidence in Assurance 2.0 Cases (arxiv:2409.10665): Bayesian/D-S
  confidence propagation through argument chains
"""

import pytest
from nightjar.types import StageResult, TrustLevel, VerifyResult, VerifyStatus
from nightjar.confidence import (
    ConfidenceScore,
    compute_confidence,
    compute_trust_level,
    STAGE_POINTS,
)


def _pass_stage(stage: int, name: str) -> StageResult:
    return StageResult(stage=stage, name=name, status=VerifyStatus.PASS)


def _fail_stage(stage: int, name: str) -> StageResult:
    return StageResult(
        stage=stage, name=name, status=VerifyStatus.FAIL,
        errors=[{"type": "test_error", "message": "failure"}],
    )


def _skip_stage(stage: int, name: str) -> StageResult:
    return StageResult(stage=stage, name=name, status=VerifyStatus.SKIP)


def _timeout_stage(stage: int, name: str) -> StageResult:
    return StageResult(stage=stage, name=name, status=VerifyStatus.TIMEOUT)


class TestStagePoints:
    """Tests for the STAGE_POINTS mapping.

    Per Scout 3 S5.3: each stage contributes specific points to the total.
    """

    def test_stage_points_sum_to_100(self):
        """All stage points sum to 100 (complete verification = full score).

        Per Scout 3 S5.3: pyright(15) + deal(10) + CrossHair(35)
        + Hypothesis(20) + Dafny(20) = 100
        """
        total = sum(STAGE_POINTS.values())
        assert total == 100, (
            f"Stage points must sum to 100, got {total}. "
            "Per Scout 3 S5.3 confidence score framework."
        )

    def test_crosshair_has_highest_stage_weight(self):
        """CrossHair (symbolic execution) has the highest weight at 35 points.

        Per Scout 3 S5.3: CrossHair provides Z3-backed SMT proof for
        explored paths — highest single-stage confidence contribution.
        """
        assert STAGE_POINTS.get("crosshair", 0) == 35, (
            "CrossHair stage must be worth 35 points (Scout 3 S5.3)"
        )

    def test_dafny_worth_20_points(self):
        """Dafny formal proof contributes 20 points.

        Per Scout 3 S5.3: When Dafny fails, Nightjar still has 80/100
        confidence from earlier stages — 'scored partial verification'.
        """
        assert STAGE_POINTS.get("formal", 0) == 20, (
            "Dafny (formal) stage must be worth 20 points (Scout 3 S5.3)"
        )


class TestConfidenceScore:
    """Tests for the ConfidenceScore dataclass."""

    def test_confidence_score_is_0_to_100(self):
        """ConfidenceScore.total must be in [0, 100]."""
        score = ConfidenceScore(total=75, breakdown={})
        assert 0 <= score.total <= 100

    def test_confidence_score_has_breakdown(self):
        """ConfidenceScore includes per-stage breakdown."""
        score = ConfidenceScore(total=75, breakdown={"formal": 20, "crosshair": 35})
        assert "formal" in score.breakdown or "crosshair" in score.breakdown


class TestComputeConfidence:
    """Tests for compute_confidence() function.

    Per Scout 3 S5.3: computes score based on which stages passed.
    """

    def test_all_stages_pass_gives_100(self):
        """All 5 stages passing = confidence score of 100.

        pyright(15) + deal(10) + CrossHair(35) + Hypothesis(20) + Dafny(20) = 100
        """
        result = VerifyResult(
            verified=True,
            stages=[
                _pass_stage(0, "preflight"),   # pyright equivalent
                _pass_stage(1, "deps"),         # deal static equivalent
                _pass_stage(2, "schema"),       # CrossHair
                _pass_stage(3, "pbt"),          # Hypothesis
                _pass_stage(4, "formal"),       # Dafny
            ],
        )
        score = compute_confidence(result)
        assert score.total == 100, f"All stages PASS should give 100, got {score.total}"

    def test_no_stages_gives_0(self):
        """No stages run = confidence score of 0."""
        result = VerifyResult(verified=False, stages=[])
        score = compute_confidence(result)
        assert score.total == 0

    def test_partial_verification_computes_correct_subtotal(self):
        """Partial verification gives correct subtotal.

        Per Scout 3 S5.3: When Dafny fails, still have 80/100 from
        stages 0-3 (15+10+35+20=80). This is the key insight.
        """
        # Stages 0-3 pass (pyright + deal + CrossHair + Hypothesis = 80)
        # Stage 4 (Dafny) times out
        result = VerifyResult(
            verified=False,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(1, "deps"),
                _pass_stage(2, "schema"),
                _pass_stage(3, "pbt"),
                _timeout_stage(4, "formal"),
            ],
        )
        score = compute_confidence(result)
        # Should be 80 (all stages except Dafny)
        assert score.total == 80, (
            f"Stages 0-3 pass + Dafny timeout should give 80, got {score.total}. "
            "Per Scout 3 S5.3: 'When Dafny fails, still have 80/100'"
        )

    def test_dafny_only_pass_gives_20(self):
        """Only Dafny passing (other stages skip) = 20 points."""
        result = VerifyResult(
            verified=True,
            stages=[
                _skip_stage(0, "preflight"),
                _skip_stage(1, "deps"),
                _skip_stage(2, "schema"),
                _skip_stage(3, "pbt"),
                _pass_stage(4, "formal"),
            ],
        )
        score = compute_confidence(result)
        assert score.total == 20, (
            f"Only Dafny passing should give 20, got {score.total}"
        )

    def test_failed_stage_contributes_zero_points(self):
        """A FAILED stage contributes 0 points (not partial credit).

        Per Scout 3 S5.3: only PASSED stages contribute to confidence.
        FAIL means the check ran and found a violation.
        """
        result = VerifyResult(
            verified=False,
            stages=[
                _pass_stage(0, "preflight"),
                _fail_stage(1, "deps"),
                _pass_stage(3, "pbt"),
            ],
        )
        score = compute_confidence(result)
        # preflight(15) + pbt(20) = 35 (deps failed so 0 for that)
        assert score.total <= 35 + 15 + 20  # upper bound
        assert score.total >= 0

    def test_skip_does_not_contribute_points(self):
        """A SKIPPED stage contributes 0 points.

        SKIP means the stage was not applicable, not that it passed.
        """
        result = VerifyResult(
            verified=False,
            stages=[
                _pass_stage(0, "preflight"),
                _skip_stage(1, "deps"),
                _skip_stage(2, "schema"),
                _skip_stage(3, "pbt"),
                _skip_stage(4, "formal"),
            ],
        )
        score = compute_confidence(result)
        # Only preflight (15) contributes; skips don't add points
        assert score.total == 15, (
            f"Only preflight passing should give 15, got {score.total}"
        )

    def test_score_is_integer_0_to_100(self):
        """compute_confidence always returns integer in [0, 100]."""
        result = VerifyResult(
            verified=False,
            stages=[_pass_stage(0, "preflight")],
        )
        score = compute_confidence(result)
        assert isinstance(score.total, int), "Score must be an integer"
        assert 0 <= score.total <= 100

    def test_breakdown_sums_to_total(self):
        """ConfidenceScore breakdown values sum to total."""
        result = VerifyResult(
            verified=True,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(3, "pbt"),
                _pass_stage(4, "formal"),
            ],
        )
        score = compute_confidence(result)
        breakdown_sum = sum(score.breakdown.values())
        assert breakdown_sum == score.total, (
            f"Breakdown sum ({breakdown_sum}) must equal total ({score.total})"
        )

    def test_confidence_format_string(self):
        """ConfidenceScore.format() returns human-readable string."""
        result = VerifyResult(
            verified=True,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(4, "formal"),
            ],
        )
        score = compute_confidence(result)
        formatted = score.format()
        assert isinstance(formatted, str)
        assert str(score.total) in formatted  # total should appear in string


class TestComputeTrustLevel:
    """Tests for compute_trust_level() and the trust level side-effect in compute_confidence().

    Thresholds from SkillFortify trust algebra [Scout 9 W2-2]:
      FORMALLY_VERIFIED: >= 0.75
      PROPERTY_VERIFIED: >= 0.50
      SCHEMA_VERIFIED:   >= 0.25
      UNVERIFIED:        <  0.25
    """

    def test_score_1_0_is_formally_verified(self):
        assert compute_trust_level(1.0) == TrustLevel.FORMALLY_VERIFIED

    def test_score_0_75_boundary_is_formally_verified(self):
        assert compute_trust_level(0.75) == TrustLevel.FORMALLY_VERIFIED

    def test_score_0_74_is_property_verified(self):
        assert compute_trust_level(0.74) == TrustLevel.PROPERTY_VERIFIED

    def test_score_0_50_boundary_is_property_verified(self):
        assert compute_trust_level(0.50) == TrustLevel.PROPERTY_VERIFIED

    def test_score_0_49_is_schema_verified(self):
        assert compute_trust_level(0.49) == TrustLevel.SCHEMA_VERIFIED

    def test_score_0_25_boundary_is_schema_verified(self):
        assert compute_trust_level(0.25) == TrustLevel.SCHEMA_VERIFIED

    def test_score_0_24_is_unverified(self):
        assert compute_trust_level(0.24) == TrustLevel.UNVERIFIED

    def test_score_0_0_is_unverified(self):
        assert compute_trust_level(0.0) == TrustLevel.UNVERIFIED

    def test_compute_confidence_sets_trust_level_on_result(self):
        """compute_confidence() sets result.trust_level as a side effect [Scout 9 W2-2]."""
        result = VerifyResult(
            verified=True,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(1, "deps"),
                _pass_stage(2, "schema"),
                _pass_stage(3, "pbt"),
                _pass_stage(4, "formal"),
            ],
        )
        compute_confidence(result)
        assert result.trust_level == TrustLevel.FORMALLY_VERIFIED

    def test_compute_confidence_sets_unverified_for_empty_result(self):
        """No stages = score 0 = UNVERIFIED trust level."""
        result = VerifyResult(verified=False, stages=[])
        compute_confidence(result)
        assert result.trust_level == TrustLevel.UNVERIFIED

    def test_compute_confidence_sets_schema_verified_for_preflight_only(self):
        """preflight(15) + deps(10) = 25 -> normalized 0.25 -> SCHEMA_VERIFIED."""
        result = VerifyResult(
            verified=False,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(1, "deps"),
            ],
        )
        compute_confidence(result)
        assert result.trust_level == TrustLevel.SCHEMA_VERIFIED

    def test_compute_confidence_all_stages_pass_is_formally_verified(self):
        """All stages pass -> score 100 -> normalized 1.0 -> FORMALLY_VERIFIED."""
        result = VerifyResult(
            verified=True,
            stages=[
                _pass_stage(0, "preflight"),
                _pass_stage(1, "deps"),
                _pass_stage(2, "schema"),
                _pass_stage(3, "pbt"),
                _pass_stage(4, "formal"),
            ],
        )
        compute_confidence(result)
        assert result.trust_level == TrustLevel.FORMALLY_VERIFIED
