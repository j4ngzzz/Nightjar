"""Tests for OpenDP differential privacy integration.

Laplace mechanism on invariant confidence counts. When aggregating
'how many tenants hit this pattern,' add DP noise. The invariant
statement itself is NOT perturbed — only the frequency metadata.

References:
- [REF-T20] OpenDP — differential privacy library
- [REF-C10] Herd immunity via differential privacy
"""

import pytest

from immune.privacy import (
    DPConfig,
    add_laplace_noise,
    dp_count,
    dp_mean,
    is_count_significant,
)


class TestDPConfig:
    """Tests for DP configuration."""

    def test_default_config(self):
        config = DPConfig()
        assert config.epsilon > 0
        assert config.delta >= 0

    def test_custom_epsilon(self):
        config = DPConfig(epsilon=0.5)
        assert config.epsilon == 0.5

    def test_epsilon_must_be_positive(self):
        with pytest.raises(ValueError):
            DPConfig(epsilon=0.0)

    def test_epsilon_must_not_be_negative(self):
        with pytest.raises(ValueError):
            DPConfig(epsilon=-1.0)


class TestAddLaplaceNoise:
    """Tests for the Laplace noise mechanism."""

    def test_returns_float(self):
        result = add_laplace_noise(100.0, sensitivity=1.0, epsilon=1.0)
        assert isinstance(result, float)

    def test_noise_is_bounded_statistically(self):
        """With high epsilon (low privacy), noise should be small."""
        values = [add_laplace_noise(100.0, sensitivity=1.0, epsilon=10.0)
                  for _ in range(100)]
        mean_val = sum(values) / len(values)
        # With epsilon=10, noise scale=0.1, mean should be very close to 100
        assert 99.0 < mean_val < 101.0

    def test_higher_epsilon_less_noise(self):
        """Higher epsilon → less noise (less privacy)."""
        high_eps_vals = [add_laplace_noise(50.0, 1.0, epsilon=10.0) for _ in range(200)]
        low_eps_vals = [add_laplace_noise(50.0, 1.0, epsilon=0.1) for _ in range(200)]

        high_eps_var = sum((v - 50.0) ** 2 for v in high_eps_vals) / len(high_eps_vals)
        low_eps_var = sum((v - 50.0) ** 2 for v in low_eps_vals) / len(low_eps_vals)

        # Lower epsilon should have higher variance
        assert low_eps_var > high_eps_var

    def test_sensitivity_scales_noise(self):
        """Higher sensitivity → more noise."""
        low_sens = [add_laplace_noise(50.0, sensitivity=1.0, epsilon=1.0) for _ in range(200)]
        high_sens = [add_laplace_noise(50.0, sensitivity=10.0, epsilon=1.0) for _ in range(200)]

        low_var = sum((v - 50.0) ** 2 for v in low_sens) / len(low_sens)
        high_var = sum((v - 50.0) ** 2 for v in high_sens) / len(high_sens)

        assert high_var > low_var


class TestDPCount:
    """Tests for differentially private counting."""

    def test_dp_count_returns_float(self):
        result = dp_count(100, epsilon=1.0)
        assert isinstance(result, float)

    def test_dp_count_approximately_correct(self):
        """DP count should be approximately correct over many samples."""
        results = [dp_count(100, epsilon=5.0) for _ in range(100)]
        mean_result = sum(results) / len(results)
        assert 95.0 < mean_result < 105.0

    def test_dp_count_non_negative(self):
        """DP count should be clamped to non-negative."""
        # Even with heavy noise, result should be >= 0
        for _ in range(100):
            result = dp_count(1, epsilon=0.1)
            assert result >= 0.0


class TestDPMean:
    """Tests for differentially private mean."""

    def test_dp_mean_returns_float(self):
        result = dp_mean(0.85, count=100, epsilon=1.0)
        assert isinstance(result, float)

    def test_dp_mean_approximately_correct(self):
        results = [dp_mean(0.85, count=100, epsilon=5.0) for _ in range(100)]
        mean_result = sum(results) / len(results)
        assert 0.75 < mean_result < 0.95

    def test_dp_mean_clamped_to_01(self):
        """DP mean should be clamped to [0, 1] range."""
        for _ in range(100):
            result = dp_mean(0.5, count=10, epsilon=0.1)
            assert 0.0 <= result <= 1.0


class TestIsCountSignificant:
    """Tests for significance threshold checking."""

    def test_high_count_is_significant(self):
        assert is_count_significant(100.0, threshold=50) is True

    def test_low_count_not_significant(self):
        assert is_count_significant(10.0, threshold=50) is False

    def test_threshold_boundary(self):
        assert is_count_significant(50.0, threshold=50) is True

    def test_default_threshold(self):
        # Default threshold should be reasonable (50)
        assert is_count_significant(51.0) is True
        assert is_count_significant(10.0) is False
