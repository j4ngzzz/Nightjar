"""OpenDP-inspired differential privacy for cross-tenant invariant sharing.

Applies the Laplace mechanism to invariant confidence counts.
When aggregating 'how many tenants hit this pattern,' DP noise is added.
The invariant statement itself is NOT perturbed — only frequency metadata.

This implements the core DP primitives needed for the network effect
layer. When OpenDP is available as a dependency, these can be swapped
for opendp.measurements.make_base_laplace.

References:
- [REF-T20] OpenDP — differential privacy library
- [REF-C10] Herd immunity via differential privacy
- [REF-P18] Self-healing software — privacy-preserving sharing
"""

import random
import math
from dataclasses import dataclass


@dataclass
class DPConfig:
    """Differential privacy configuration.

    Args:
        epsilon: Privacy budget. Higher = less privacy, more accuracy.
                 Must be strictly positive.
        delta: Probability of privacy failure. Usually 0 for pure DP.

    References:
    - [REF-T20] OpenDP epsilon/delta parameters
    """

    epsilon: float = 1.0
    delta: float = 0.0

    def __post_init__(self) -> None:
        if self.epsilon <= 0:
            raise ValueError(
                f"epsilon must be strictly positive, got {self.epsilon}"
            )
        if self.delta < 0:
            raise ValueError(
                f"delta must be non-negative, got {self.delta}"
            )


def _sample_laplace(scale: float) -> float:
    """Sample from the Laplace distribution with location 0.

    Uses the inverse CDF method: X = -scale * sign(U) * ln(1 - 2|U|)
    where U ~ Uniform(-0.5, 0.5).

    References:
    - [REF-T20] OpenDP Laplace mechanism
    """
    u = random.random() - 0.5
    return -scale * math.copysign(1, u) * math.log(1 - 2 * abs(u))


def add_laplace_noise(
    value: float, sensitivity: float, epsilon: float
) -> float:
    """Add Laplace noise to a value for differential privacy.

    noise ~ Laplace(0, sensitivity / epsilon)

    Args:
        value: The true value to protect.
        sensitivity: The maximum change in the value when one
                     individual's data is added/removed.
        epsilon: Privacy budget. Higher = less noise.

    Returns:
        The noised value.

    References:
    - [REF-T20] OpenDP make_base_laplace
    - [REF-C10] Privacy mechanism for cross-tenant sharing
    """
    scale = sensitivity / epsilon
    noise = _sample_laplace(scale)
    return value + noise


def dp_count(true_count: int, epsilon: float = 1.0) -> float:
    """Differentially private count.

    Adds Laplace noise with sensitivity=1 (adding/removing one tenant
    changes the count by at most 1). Result is clamped to >= 0.

    Args:
        true_count: The true count of tenants.
        epsilon: Privacy budget.

    Returns:
        The noised count, clamped to non-negative.

    References:
    - [REF-T20] OpenDP counting mechanism
    - [REF-C10] DP-protected tenant counts
    """
    noised = add_laplace_noise(float(true_count), sensitivity=1.0, epsilon=epsilon)
    return max(0.0, noised)


def dp_mean(
    true_mean: float, count: int, epsilon: float = 1.0
) -> float:
    """Differentially private mean confidence.

    Adds Laplace noise scaled by 1/count (sensitivity of the mean).
    Result is clamped to [0, 1] since it represents a confidence score.

    Args:
        true_mean: The true mean confidence (0-1).
        count: Number of observations.
        epsilon: Privacy budget.

    Returns:
        The noised mean, clamped to [0, 1].

    References:
    - [REF-T20] OpenDP mean mechanism
    - [REF-C10] DP-protected confidence scores
    """
    sensitivity = 1.0 / max(count, 1)
    noised = add_laplace_noise(true_mean, sensitivity=sensitivity, epsilon=epsilon)
    return max(0.0, min(1.0, noised))


def is_count_significant(
    dp_count_value: float, threshold: int = 50
) -> bool:
    """Check if a DP-protected count exceeds the significance threshold.

    Used to determine if enough tenants have hit a pattern to make
    it worth sharing as a universal invariant.

    Args:
        dp_count_value: The DP-protected count.
        threshold: Minimum count to consider significant.

    Returns:
        True if the count exceeds or equals the threshold.

    References:
    - [REF-C10] Herd immunity threshold
    """
    return dp_count_value >= threshold
