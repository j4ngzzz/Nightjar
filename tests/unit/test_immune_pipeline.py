"""Tests for the immune system orchestrator pipeline.

The orchestrator wires all immune components together:
collect → mine → enrich → verify → append → enforce.

References:
- [REF-C09] Immune System / Acquired Immunity
- [REF-C05] Dynamic Invariant Mining
- [REF-P18] Self-Healing Software Systems
"""

import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from immune.pipeline import (
    run_immune_cycle,
    ImmuneCycleResult,
    ImmuneCycleConfig,
)
from immune.types import ErrorTrace, InvariantStatus


SAMPLE_CARD_MD = """\
---
card-version: "1.0"
id: test-module
title: Test Module
status: draft
invariants:
  - id: INV-001
    tier: example
    statement: "Basic test"
    rationale: "Smoke test"
---

## Intent

Test module for immune pipeline testing.
"""


class TestImmuneCycleConfig:
    """Test configuration dataclass."""

    def test_default_config(self):
        config = ImmuneCycleConfig()
        assert config.max_pbt_examples == 1000
        assert config.symbolic_timeout_sec == 30
        assert config.require_both_verifiers is False

    def test_custom_config(self):
        config = ImmuneCycleConfig(
            max_pbt_examples=500,
            symbolic_timeout_sec=10,
            require_both_verifiers=True,
        )
        assert config.max_pbt_examples == 500
        assert config.require_both_verifiers is True


class TestImmuneCycleResult:
    """Test result dataclass."""

    def test_empty_result(self):
        result = ImmuneCycleResult()
        assert result.candidates_proposed == 0
        assert result.candidates_verified == 0
        assert result.candidates_appended == 0
        assert result.errors == []

    def test_result_with_data(self):
        result = ImmuneCycleResult(
            candidates_proposed=10,
            candidates_verified=7,
            candidates_appended=5,
        )
        assert result.candidates_proposed == 10
        assert result.candidates_verified == 7


class TestRunImmuneCycle:
    """Test the full immune cycle orchestration."""

    @patch("immune.pipeline._call_enricher")
    @patch("immune.pipeline._call_pbt_verifier")
    @patch("immune.pipeline._call_symbolic_verifier")
    def test_full_cycle_with_mocked_components(
        self, mock_symbolic, mock_pbt, mock_enricher
    ):
        """Full cycle should enrich → verify → return results."""
        from immune.enricher import CandidateInvariant, EnrichmentResult
        from immune.verifier_pbt import PBTResult, PBTVerdict
        from immune.verifier_symbolic import SymbolicResult, SymbolicVerdict

        mock_enricher.return_value = EnrichmentResult(
            candidates=[
                CandidateInvariant("result >= 0", "Non-negative", 0.8),
                CandidateInvariant("result < 1000", "Bounded", 0.6),
            ]
        )
        mock_pbt.return_value = PBTResult(
            verdict=PBTVerdict.PASS, num_examples=1000
        )
        mock_symbolic.return_value = SymbolicResult(
            verdict=SymbolicVerdict.VERIFIED
        )

        result = run_immune_cycle(
            function_source='def f(x: int) -> int:\n    return abs(x)',
            function_name="f",
            error_trace="ValueError: unexpected",
            observed_invariants=["x != 0"],
        )

        assert isinstance(result, ImmuneCycleResult)
        assert result.candidates_proposed == 2
        assert result.candidates_verified >= 1

    @patch("immune.pipeline._call_enricher")
    def test_cycle_with_enrichment_failure(self, mock_enricher):
        """Should handle enrichment failures gracefully."""
        from immune.enricher import EnrichmentResult

        mock_enricher.return_value = EnrichmentResult(
            error="LLM API rate limit"
        )

        result = run_immune_cycle(
            function_source='def f(x: int) -> int:\n    return x',
            function_name="f",
        )

        assert result.candidates_proposed == 0
        assert len(result.errors) > 0

    @patch("immune.pipeline._call_enricher")
    @patch("immune.pipeline._call_pbt_verifier")
    @patch("immune.pipeline._call_symbolic_verifier")
    def test_cycle_filters_out_failed_verifications(
        self, mock_symbolic, mock_pbt, mock_enricher
    ):
        """Only verified invariants should be counted."""
        from immune.enricher import CandidateInvariant, EnrichmentResult
        from immune.verifier_pbt import PBTResult, PBTVerdict
        from immune.verifier_symbolic import SymbolicResult, SymbolicVerdict

        mock_enricher.return_value = EnrichmentResult(
            candidates=[
                CandidateInvariant("result >= 0", "good", 0.8),
                CandidateInvariant("result > 100", "bad", 0.3),
            ]
        )
        # First call succeeds, second fails
        mock_pbt.side_effect = [
            PBTResult(verdict=PBTVerdict.PASS, num_examples=1000),
            PBTResult(verdict=PBTVerdict.FAIL, counterexample={"x": 1}),
        ]
        mock_symbolic.side_effect = [
            SymbolicResult(verdict=SymbolicVerdict.VERIFIED),
            SymbolicResult(verdict=SymbolicVerdict.COUNTEREXAMPLE, counterexample={"x": "1"}),
        ]

        result = run_immune_cycle(
            function_source='def f(x: int) -> int:\n    return abs(x)',
            function_name="f",
        )

        assert result.candidates_proposed == 2
        assert result.candidates_verified == 1

    @patch("immune.pipeline._call_enricher")
    @patch("immune.pipeline._call_pbt_verifier")
    @patch("immune.pipeline._call_symbolic_verifier")
    def test_cycle_with_card_path_appends_invariants(
        self, mock_symbolic, mock_pbt, mock_enricher
    ):
        """When card_path is provided, verified invariants should be appended."""
        from immune.enricher import CandidateInvariant, EnrichmentResult
        from immune.verifier_pbt import PBTResult, PBTVerdict
        from immune.verifier_symbolic import SymbolicResult, SymbolicVerdict

        mock_enricher.return_value = EnrichmentResult(
            candidates=[CandidateInvariant("result >= 0", "Non-neg", 0.9)]
        )
        mock_pbt.return_value = PBTResult(verdict=PBTVerdict.PASS, num_examples=100)
        mock_symbolic.return_value = SymbolicResult(verdict=SymbolicVerdict.VERIFIED)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".card.md", delete=False, encoding="utf-8"
        ) as f:
            f.write(SAMPLE_CARD_MD)
            tmp_path = f.name

        try:
            result = run_immune_cycle(
                function_source='def f(x: int) -> int:\n    return abs(x)',
                function_name="f",
                card_path=tmp_path,
            )
            assert result.candidates_appended >= 1

            content = open(tmp_path, encoding="utf-8").read()
            assert "result >= 0" in content
        finally:
            os.unlink(tmp_path)

    def test_cycle_with_empty_function_source(self):
        """Should handle empty function source gracefully."""
        result = run_immune_cycle(
            function_source="",
            function_name="f",
        )
        assert len(result.errors) > 0

    @patch("immune.pipeline._call_enricher")
    @patch("immune.pipeline._call_pbt_verifier")
    @patch("immune.pipeline._call_symbolic_verifier")
    def test_require_both_verifiers(
        self, mock_symbolic, mock_pbt, mock_enricher
    ):
        """When require_both_verifiers=True, both must pass."""
        from immune.enricher import CandidateInvariant, EnrichmentResult
        from immune.verifier_pbt import PBTResult, PBTVerdict
        from immune.verifier_symbolic import SymbolicResult, SymbolicVerdict

        mock_enricher.return_value = EnrichmentResult(
            candidates=[CandidateInvariant("result >= 0", "test", 0.8)]
        )
        # PBT passes but CrossHair returns error (not installed)
        mock_pbt.return_value = PBTResult(verdict=PBTVerdict.PASS, num_examples=100)
        mock_symbolic.return_value = SymbolicResult(
            verdict=SymbolicVerdict.ERROR, error="CrossHair not installed"
        )

        config = ImmuneCycleConfig(require_both_verifiers=True)
        result = run_immune_cycle(
            function_source='def f(x: int) -> int:\n    return abs(x)',
            function_name="f",
            config=config,
        )
        # Should NOT count as verified since symbolic failed
        assert result.candidates_verified == 0
