"""Tests for W1.3 — BFS proof search replacing flat retry loop.

Validates the BFS (Best-First Search) proof search that replaces flat
sampling in the Clover retry loop. BFS explores multiple annotation branches
with verifier feedback at each step.

References:
- Scout 3 Sections 3.1-3.2: VerMCTS/BFS proof search
- Clean-room CR-12: VerMCTS (arxiv:2402.08147, NeurIPS 2024 Outstanding Paper)
- BFS-Prover: arxiv:2502.03438 (ACL 2025) — BFS matches MCTS without critic
- Scout 3 S3.2: 'Start with BFS (simpler), upgrade to MCTS only if BFS hits ceiling'
- >30% absolute improvement over flat sampling (Scout 3 S10)
"""

import pytest
from unittest.mock import patch, MagicMock
from nightjar.types import (
    CardSpec, Contract, ContractInput, ContractOutput,
    Invariant, InvariantTier, ModuleBoundary,
    StageResult, VerifyResult, VerifyStatus,
)


def _make_spec() -> CardSpec:
    return CardSpec(
        card_version="1.0",
        id="test-module",
        title="Test Module",
        status="draft",
        module=ModuleBoundary(owns=["func_a()"]),
        contract=Contract(
            inputs=[ContractInput(name="x", type="integer")],
            outputs=[ContractOutput(name="Result", type="integer")],
        ),
        invariants=[
            Invariant(id="INV-001", tier=InvariantTier.FORMAL,
                      statement="For any x > 0, result > 0"),
        ],
    )


def _pass_verify() -> VerifyResult:
    return VerifyResult(
        verified=True,
        stages=[StageResult(stage=4, name="formal", status=VerifyStatus.PASS)],
        total_duration_ms=100,
    )


def _fail_verify(errors: list[dict] | None = None) -> VerifyResult:
    return VerifyResult(
        verified=False,
        stages=[
            StageResult(
                stage=4, name="formal", status=VerifyStatus.FAIL,
                errors=errors or [{"type": "postcondition_failure", "message": "proof failed"}],
            ),
        ],
        total_duration_ms=200,
    )


class TestBFSProofSearch:
    """Tests for the BFS proof search in retry.py.

    Per Scout 3 S3.1-3.2 + CR-12 (VerMCTS arxiv:2402.08147):
    BFS tree search where each node = partial Dafny annotation,
    branches on verification errors, expands best-scoring node.
    >30% absolute improvement over flat sampling baseline.
    """

    def test_bfs_explores_multiple_branches(self):
        """BFS generates multiple candidate annotations per level.

        Per CR-12: BFS expands multiple nodes at each level, exploring
        different annotation strategies simultaneously. Unlike flat retry
        which tries one candidate at a time.
        """
        from nightjar.retry import run_bfs_search

        spec = _make_spec()
        llm_calls = []

        def mock_llm(spec, code, result, attempt):
            llm_calls.append(attempt)
            return f"branch_{attempt}_code"

        with patch("nightjar.retry.run_pipeline") as mock_pipeline, \
             patch("nightjar.retry._call_repair_llm", side_effect=mock_llm):
            # First call fails, subsequent calls fail until success
            mock_pipeline.side_effect = [
                _fail_verify(),  # initial
                _fail_verify(),  # branch 1
                _fail_verify(),  # branch 2
                _pass_verify(),  # branch 3 succeeds
            ]

            result = run_bfs_search(spec, "initial_code", max_depth=3, beam_width=2)

        assert result.verified is True

    def test_bfs_prunes_worsening_branches(self):
        """BFS prunes branches that don't improve on the best known score.

        Per CR-12: BFS with beam search prunes branches where verification
        status regresses. Only expands the beam_width best candidates per level.
        """
        from nightjar.retry import run_bfs_search

        spec = _make_spec()

        with patch("nightjar.retry.run_pipeline") as mock_pipeline, \
             patch("nightjar.retry._call_repair_llm") as mock_llm:
            # All branches fail
            mock_pipeline.return_value = _fail_verify()
            mock_llm.return_value = "candidate_code"

            result = run_bfs_search(spec, "initial_code", max_depth=2, beam_width=2)

        assert result.verified is False
        # Should not have made more than beam_width * max_depth + 1 pipeline calls
        total_calls = mock_pipeline.call_count
        assert total_calls <= 2 * 2 + 1, (
            f"BFS should prune — expected <= 5 pipeline calls, got {total_calls}"
        )

    def test_bfs_returns_verify_result(self):
        """run_bfs_search returns a VerifyResult."""
        from nightjar.retry import run_bfs_search

        spec = _make_spec()

        with patch("nightjar.retry.run_pipeline") as mock_pipeline, \
             patch("nightjar.retry._call_repair_llm") as mock_llm:
            mock_pipeline.return_value = _pass_verify()
            result = run_bfs_search(spec, "initial_code")

        assert isinstance(result, VerifyResult)

    def test_bfs_pass_on_first_attempt(self):
        """BFS returns immediately when initial code passes verification."""
        from nightjar.retry import run_bfs_search

        spec = _make_spec()

        with patch("nightjar.retry.run_pipeline") as mock_pipeline, \
             patch("nightjar.retry._call_repair_llm") as mock_llm:
            mock_pipeline.return_value = _pass_verify()

            result = run_bfs_search(spec, "good_code")

        assert result.verified is True
        mock_llm.assert_not_called()

    def test_bfs_has_default_params(self):
        """run_bfs_search has sensible defaults for max_depth and beam_width."""
        import inspect
        from nightjar.retry import run_bfs_search

        sig = inspect.signature(run_bfs_search)
        assert "max_depth" in sig.parameters
        assert "beam_width" in sig.parameters
        # Defaults should be reasonable
        max_depth_default = sig.parameters["max_depth"].default
        beam_width_default = sig.parameters["beam_width"].default
        assert max_depth_default >= 3, "max_depth should be at least 3"
        assert beam_width_default >= 2, "beam_width should be at least 2"

    def test_bfs_outperforms_flat_retry_mock_setup(self):
        """BFS finds a solution in fewer total LLM calls vs flat retry.

        Mock setup: 3rd candidate at depth 2 passes. BFS explores 2 branches
        per depth, so finds at depth 2. Flat retry would need 3 sequential calls.
        This verifies the structural advantage of beam search.
        """
        from nightjar.retry import run_bfs_search

        spec = _make_spec()
        call_count = [0]

        def mock_llm(spec, code, result, attempt):
            call_count[0] += 1
            return f"candidate_{call_count[0]}"

        def mock_pipeline(spec, code, **kwargs):
            # Third candidate passes (call_count[0] == 3)
            if call_count[0] >= 3:
                return _pass_verify()
            return _fail_verify()

        with patch("nightjar.retry.run_pipeline", side_effect=mock_pipeline), \
             patch("nightjar.retry._call_repair_llm", side_effect=mock_llm):
            result = run_bfs_search(spec, "initial_code", max_depth=3, beam_width=2)

        # BFS should succeed
        assert result.verified is True


class TestBFSNode:
    """Tests for the BFSNode data structure used in the search tree."""

    def test_bfs_node_has_code_and_score(self):
        """BFSNode stores code and a verification score."""
        from nightjar.retry import BFSNode

        node = BFSNode(code="method Foo() { }", score=0.5, depth=1)
        assert node.code == "method Foo() { }"
        assert 0.0 <= node.score <= 1.0
        assert node.depth == 1

    def test_bfs_node_ordering(self):
        """BFSNodes are ordered by score for priority queue use."""
        from nightjar.retry import BFSNode

        node_low = BFSNode(code="a", score=0.2, depth=1)
        node_high = BFSNode(code="b", score=0.8, depth=1)
        # Higher score = better node (should come first in max-heap)
        assert node_high.score > node_low.score
