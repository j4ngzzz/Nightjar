"""Herd immunity threshold logic — universal invariants.

When pattern confidence > 0.95 across 50+ tenants (DP-protected count),
the pattern is promoted to UNIVERSAL status. Universal invariants are
applied to all new CARD builds regardless of whether that specific
tenant experienced the failure.

This is the network effect: one customer's bug immunizes all.

References:
- [REF-C10] Herd immunity via differential privacy
- [REF-C09] Immune system acquired immunity — universal invariants
- [REF-P18] Self-healing software — herd immunity concept
"""

from dataclasses import dataclass

from immune.pattern_library import PatternLibrary, InvariantPattern


@dataclass
class HerdConfig:
    """Configuration for herd immunity threshold checking.

    Args:
        confidence_threshold: Minimum DP-protected confidence to promote.
        tenant_count_threshold: Minimum DP-protected tenant count to promote.
        epsilon: Privacy budget used for DP noise (for reference).

    References:
    - [REF-C10] Herd immunity thresholds
    """

    confidence_threshold: float = 0.95
    tenant_count_threshold: int = 50
    epsilon: float = 1.0


@dataclass
class HerdResult:
    """Result from evaluating a pattern against herd immunity thresholds.

    References:
    - [REF-C10] Herd immunity evaluation result
    """

    pattern_id: str
    fingerprint: str
    tenant_count_dp: float
    confidence_dp: float
    eligible: bool
    already_universal: bool = False


def check_herd_immunity(
    pattern: InvariantPattern, config: HerdConfig
) -> HerdResult:
    """Check if a single pattern meets herd immunity thresholds.

    A pattern is eligible for universal promotion when:
    1. DP-protected tenant count >= threshold (default 50)
    2. DP-protected confidence >= threshold (default 0.95)

    Args:
        pattern: The invariant pattern to evaluate.
        config: Herd immunity configuration.

    Returns:
        HerdResult with eligibility determination.

    References:
    - [REF-C10] Herd immunity threshold logic
    """
    count_ok = pattern.tenant_count_dp >= config.tenant_count_threshold
    confidence_ok = pattern.confidence_dp >= config.confidence_threshold
    eligible = count_ok and confidence_ok

    return HerdResult(
        pattern_id=pattern.pattern_id,
        fingerprint=pattern.fingerprint,
        tenant_count_dp=pattern.tenant_count_dp,
        confidence_dp=pattern.confidence_dp,
        eligible=eligible,
        already_universal=pattern.is_universal,
    )


def evaluate_patterns(
    library: PatternLibrary, config: HerdConfig
) -> list[HerdResult]:
    """Evaluate all patterns in the library against herd immunity thresholds.

    Returns a list of HerdResult for every pattern.

    References:
    - [REF-C10] Batch herd immunity evaluation
    """
    # Get all patterns from the library
    all_patterns = library.search("")  # Empty search returns all
    return [check_herd_immunity(p, config) for p in all_patterns]


def promote_eligible_patterns(
    library: PatternLibrary, config: HerdConfig
) -> list[str]:
    """Promote all eligible non-universal patterns to universal status.

    Returns list of pattern_ids that were newly promoted.

    References:
    - [REF-C10] Herd immunity promotion
    - [REF-C09] Universal invariant creation
    """
    results = evaluate_patterns(library, config)
    promoted = []

    for result in results:
        if result.eligible and not result.already_universal:
            library.promote_to_universal(result.pattern_id)
            promoted.append(result.pattern_id)

    return promoted
