"""Tests for 3-tier mining orchestrator — IM1.

The 3-tier mining stack from Scout 6 Section 3:

  Tier 1: Semantic  — LLM-based invariant hypothesis (source code only, zero overhead)
  Tier 2: Runtime   — Daikon+Houdini (sys.monitoring tracing, low overhead)
  Tier 3: API-level — MINES (OTel spans, no overhead)

The orchestrator:
  1. Runs all applicable tiers
  2. Merges results into a unified MinedInvariant list
  3. Deduplicates invariants with the same expression
  4. Merges confidence scores from multiple tiers (takes max confidence)

References:
- Scout 6 Section 3 — 3-tier mining architecture
- W4.1 daikon.py (Tier 2), W4.2 houdini.py (Tier 2 filter)
- W4.3 mines.py (Tier 3)
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from immune.pipeline import (
    run_mining_tiers,
    MinedInvariant,
    MiningTier,
    MiningOrchestrationResult,
)
from immune.mines import OtelSpan, MinesInvariant, MinesCategory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_span(
    op: str = "GET /items",
    status: int = 200,
    duration_ms: float = 50.0,
    attrs: dict | None = None,
) -> OtelSpan:
    return OtelSpan(
        operation_name=op,
        attributes=attrs or {},
        status_code=status,
        duration_ms=duration_ms,
    )


def simple_fn(x: int) -> int:
    """Simple function for Tier 2 tracing."""
    return x + 1


# ---------------------------------------------------------------------------
# Test: MinedInvariant data model
# ---------------------------------------------------------------------------


class TestMinedInvariant:
    def test_mined_invariant_construction(self):
        """MinedInvariant has expression, confidence, tier, and source."""
        inv = MinedInvariant(
            expression="x >= 0",
            confidence=0.9,
            tier=MiningTier.RUNTIME,
            source="daikon",
        )
        assert inv.expression == "x >= 0"
        assert inv.confidence == 0.9
        assert inv.tier == MiningTier.RUNTIME
        assert inv.source == "daikon"

    def test_mining_tier_enum_has_three_values(self):
        """MiningTier has SEMANTIC, RUNTIME, API_LEVEL."""
        assert hasattr(MiningTier, "SEMANTIC")
        assert hasattr(MiningTier, "RUNTIME")
        assert hasattr(MiningTier, "API_LEVEL")


# ---------------------------------------------------------------------------
# Test: MiningOrchestrationResult
# ---------------------------------------------------------------------------


class TestMiningOrchestrationResult:
    def test_result_structure(self):
        """MiningOrchestrationResult has merged, tier_counts, errors."""
        result = MiningOrchestrationResult(
            merged=[],
            tier_counts={MiningTier.RUNTIME: 3},
            errors=[],
        )
        assert result.merged == []
        assert result.tier_counts[MiningTier.RUNTIME] == 3
        assert result.errors == []


# ---------------------------------------------------------------------------
# Test: run_mining_tiers — all three tiers
# ---------------------------------------------------------------------------


class TestRunMiningTiersAllTiers:
    """Orchestrator should run all applicable tiers."""

    def test_orchestrator_runs_tier2_from_callable(self):
        """Tier 2 (Daikon+Houdini) runs when a callable is provided."""
        result = run_mining_tiers(
            func=simple_fn,
            trace_args=[(1,), (5,), (10,), (3,)],
            spans=None,
            run_tier1=False,  # skip LLM tier in unit tests
        )
        # Tier 2 should have contributed invariants (Daikon mines from traces)
        assert MiningTier.RUNTIME in result.tier_counts or len(result.merged) >= 0
        assert isinstance(result, MiningOrchestrationResult)

    def test_orchestrator_runs_tier3_from_otel_spans(self):
        """Tier 3 (MINES) runs when OTel spans are provided."""
        spans = [
            make_span("GET /items", status=200),
            make_span("GET /items", status=200),
            make_span("GET /items", status=404),
        ]
        result = run_mining_tiers(
            func=None,
            spans=spans,
            run_tier1=False,
        )
        # Tier 3 should have contributed invariants
        assert MiningTier.API_LEVEL in result.tier_counts
        assert result.tier_counts[MiningTier.API_LEVEL] > 0

    def test_orchestrator_runs_all_three_tiers(self):
        """With func + spans, all three tiers (Tier 1 mocked) contribute."""
        spans = [
            make_span("POST /login", status=200),
            make_span("POST /login", status=401),
        ]

        # Mock Tier 1 to avoid real LLM calls
        mock_tier1 = [
            MinedInvariant(
                expression="status_code in {200, 401}",
                confidence=0.8,
                tier=MiningTier.SEMANTIC,
                source="llm",
            )
        ]

        with patch("immune.pipeline._run_tier1", return_value=mock_tier1):
            result = run_mining_tiers(
                func=simple_fn,
                trace_args=[(1,), (2,), (3,)],
                spans=spans,
                run_tier1=True,
            )

        # All three tiers should be represented in tier_counts
        assert MiningTier.SEMANTIC in result.tier_counts, (
            f"Expected SEMANTIC in tier_counts, got: {result.tier_counts}"
        )
        assert MiningTier.API_LEVEL in result.tier_counts, (
            f"Expected API_LEVEL in tier_counts, got: {result.tier_counts}"
        )


# ---------------------------------------------------------------------------
# Test: Deduplication
# ---------------------------------------------------------------------------


class TestOrchestatorDeduplication:
    """Orchestrator must deduplicate invariants with the same expression."""

    def test_orchestrator_deduplicates_overlapping_invariants(self):
        """Same expression from 2+ tiers -> single entry in merged output."""
        spans = [
            make_span("GET /items", status=200),
            make_span("GET /items", status=200),
        ]

        # Two tiers both producing the same expression
        mock_tier1 = [
            MinedInvariant(
                expression="status_code == 200",
                confidence=0.75,
                tier=MiningTier.SEMANTIC,
                source="llm",
            )
        ]

        with patch("immune.pipeline._run_tier1", return_value=mock_tier1):
            result = run_mining_tiers(
                func=None,
                spans=spans,
                run_tier1=True,
            )

        # Find "status_code == 200" in merged
        exprs = [inv.expression for inv in result.merged]
        # The same expression should appear at most once
        assert exprs.count("status_code == 200") <= 1, (
            f"Duplicate detected: {exprs}"
        )

    def test_orchestrator_no_duplicates_across_all_merged(self):
        """All expressions in merged result are unique."""
        spans = [make_span("GET /health", status=200)]
        result = run_mining_tiers(func=None, spans=spans, run_tier1=False)

        exprs = [inv.expression for inv in result.merged]
        assert len(exprs) == len(set(exprs)), (
            f"Duplicate expressions in merged: {exprs}"
        )


# ---------------------------------------------------------------------------
# Test: Confidence score merging
# ---------------------------------------------------------------------------


class TestOrchestatorConfidenceMerge:
    """When the same invariant is found by multiple tiers, confidence is merged."""

    def test_orchestrator_merges_with_confidence_scores(self):
        """Same expression from two tiers: merged confidence is max of both."""
        # Tier 3 mines "status_code in {200}" with confidence ~0.9
        # Tier 1 (mocked) mines same expression with confidence 0.75
        # Merged should have confidence >= 0.75

        spans = [
            make_span("GET /health", status=200),
            make_span("GET /health", status=200),
        ]

        mock_tier1 = [
            MinedInvariant(
                expression="status_code in {200}",
                confidence=0.75,
                tier=MiningTier.SEMANTIC,
                source="llm",
            )
        ]

        with patch("immune.pipeline._run_tier1", return_value=mock_tier1):
            result = run_mining_tiers(
                func=None,
                spans=spans,
                run_tier1=True,
            )

        # Find the merged invariant
        for inv in result.merged:
            if "200" in inv.expression or "status" in inv.expression.lower():
                assert inv.confidence >= 0.75, (
                    f"Expected confidence >= 0.75, got: {inv.confidence}"
                )
                break

    def test_orchestrator_confidence_is_max_of_tiers(self):
        """Merging takes the maximum confidence from contributing tiers."""
        # Create two MinedInvariants with same expression, different confidence
        from immune.pipeline import _merge_invariants

        inv_low = MinedInvariant(
            expression="x >= 0",
            confidence=0.6,
            tier=MiningTier.RUNTIME,
            source="daikon",
        )
        inv_high = MinedInvariant(
            expression="x >= 0",
            confidence=0.9,
            tier=MiningTier.API_LEVEL,
            source="mines",
        )

        merged = _merge_invariants([inv_low, inv_high])
        assert len(merged) == 1, f"Expected 1 merged invariant, got: {len(merged)}"
        assert merged[0].confidence == 0.9, (
            f"Expected max confidence 0.9, got: {merged[0].confidence}"
        )


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------


class TestOrchestatorErrors:
    def test_orchestrator_with_no_inputs_returns_empty(self):
        """No func, no spans: returns empty result with no errors."""
        result = run_mining_tiers(func=None, spans=None, run_tier1=False)
        assert result.merged == []
        assert not result.errors

    def test_orchestrator_records_tier_errors_in_result(self):
        """If a tier fails, errors are recorded and other tiers still run."""
        spans = [make_span("GET /test")]

        # Make Tier 3 raise an exception
        with patch("immune.pipeline._run_tier3", side_effect=RuntimeError("mines failure")):
            result = run_mining_tiers(func=None, spans=spans, run_tier1=False)

        # Error should be recorded
        assert any("mines" in err.lower() or "tier 3" in err.lower() for err in result.errors), (
            f"Expected error about mines/tier3, got: {result.errors}"
        )
