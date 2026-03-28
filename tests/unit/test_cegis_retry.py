"""Tests for U1.2 — CEGIS Counterexample-Guided Retry.

Upgrade from generic error messages to CEGIS: parse Dafny counterexamples
and include concrete failing input values in the retry prompt.

Per SpecLoop (arxiv:2603.02895): including the counterexample is MORE
informative than raw error messages. LLM can reason about "why does
X=5, Y=-3 break my invariant?" rather than decode SMT output.

References:
- [REF-NEW-03] SpecLoop (arxiv:2603.02895) — CEGIS counterexample-guided retry
- nightjar-upgrade-plan.md U1.2
"""

import pytest
from unittest.mock import patch, MagicMock

from nightjar.types import (
    CardSpec, Contract, ContractInput,
    Invariant, InvariantTier, ModuleBoundary,
    StageResult, VerifyResult, VerifyStatus,
)


def _make_spec() -> CardSpec:
    return CardSpec(
        card_version="1.0", id="test", title="Test", status="draft",
        module=ModuleBoundary(owns=["f()"]),
        contract=Contract(inputs=[ContractInput(name="x", type="int")]),
        invariants=[
            Invariant(id="INV-1", tier=InvariantTier.FORMAL,
                      statement="result >= 0"),
        ],
    )


# ── Dafny counterexample output samples ──────────────────────────────────────

DAFNY_CE_OUTPUT_SINGLE = """\
module.dfy(10,4): Error: A postcondition might not hold on this return path.
  counterexample for 'charge':
    amount := -500
"""

DAFNY_CE_OUTPUT_MULTI = """\
module.dfy(15,4): Error: A postcondition might not hold on this return path.
  counterexample for 'transfer_funds':
    amount := -500
    balance := 1000
    fee := 0
"""

DAFNY_NO_CE_OUTPUT = """\
module.dfy(5,4): Error: A precondition might not hold.
  Related message: requires clause at line 3
"""

DAFNY_TIMEOUT_OUTPUT = "Verification timed out after 15 seconds."


class TestParseDafnyCounterexample:
    """Tests for parse_dafny_counterexample()."""

    def test_importable(self):
        from nightjar.retry import parse_dafny_counterexample
        assert callable(parse_dafny_counterexample)

    def test_extracts_single_variable_counterexample(self):
        """Parse single-variable counterexample from Dafny output."""
        from nightjar.retry import parse_dafny_counterexample
        result = parse_dafny_counterexample(DAFNY_CE_OUTPUT_SINGLE)
        assert result is not None
        assert "amount" in result
        assert result["amount"] == "-500"

    def test_extracts_multi_variable_counterexample(self):
        """Parse multi-variable counterexample with all variables."""
        from nightjar.retry import parse_dafny_counterexample
        result = parse_dafny_counterexample(DAFNY_CE_OUTPUT_MULTI)
        assert result is not None
        assert result["amount"] == "-500"
        assert result["balance"] == "1000"
        assert result["fee"] == "0"

    def test_returns_none_when_no_counterexample(self):
        """Returns None when Dafny output has no counterexample block."""
        from nightjar.retry import parse_dafny_counterexample
        result = parse_dafny_counterexample(DAFNY_NO_CE_OUTPUT)
        assert result is None

    def test_returns_none_for_timeout_output(self):
        """Timeout output has no counterexample — returns None."""
        from nightjar.retry import parse_dafny_counterexample
        result = parse_dafny_counterexample(DAFNY_TIMEOUT_OUTPUT)
        assert result is None

    def test_returns_none_for_empty_string(self):
        """Empty string → None."""
        from nightjar.retry import parse_dafny_counterexample
        result = parse_dafny_counterexample("")
        assert result is None


class TestBuildCegisRepairPrompt:
    """Tests for build_cegis_repair_prompt()."""

    def test_importable(self):
        from nightjar.retry import build_cegis_repair_prompt
        assert callable(build_cegis_repair_prompt)

    def test_prompt_includes_counterexample_values(self):
        """CEGIS prompt includes concrete failing input values."""
        from nightjar.retry import build_cegis_repair_prompt
        spec = _make_spec()
        counterexample = {"x": "-5", "result": "-10"}
        prompt = build_cegis_repair_prompt(
            spec=spec,
            failed_code="def f(x): return x * 2",
            verify_result=VerifyResult(
                verified=False,
                stages=[StageResult(
                    stage=4, name="formal", status=VerifyStatus.FAIL,
                    errors=[{"type": "postcondition_failure",
                              "message": "A postcondition might not hold"}],
                )],
                total_duration_ms=100,
            ),
            attempt=1,
            counterexample=counterexample,
        )
        # The counterexample values must appear in the prompt
        assert "x" in prompt
        assert "-5" in prompt

    def test_prompt_uses_cegis_framing(self):
        """CEGIS prompt frames the counterexample as 'fails on input X=5'."""
        from nightjar.retry import build_cegis_repair_prompt
        spec = _make_spec()
        prompt = build_cegis_repair_prompt(
            spec=spec,
            failed_code="def f(x): return x * 2",
            verify_result=VerifyResult(
                verified=False,
                stages=[StageResult(
                    stage=4, name="formal", status=VerifyStatus.FAIL,
                    errors=[{"type": "postcondition_failure",
                              "message": "postcondition fails"}],
                )],
                total_duration_ms=100,
            ),
            attempt=1,
            counterexample={"amount": "-500", "balance": "1000"},
        )
        # Must mention specific input values (CEGIS framing)
        assert "amount" in prompt
        assert "-500" in prompt
        assert "balance" in prompt
        assert "1000" in prompt

    def test_prompt_falls_back_gracefully_without_counterexample(self):
        """When counterexample is None, falls back to error-message prompt."""
        from nightjar.retry import build_cegis_repair_prompt
        spec = _make_spec()
        prompt = build_cegis_repair_prompt(
            spec=spec,
            failed_code="def f(x): return x * 2",
            verify_result=VerifyResult(
                verified=False,
                stages=[StageResult(
                    stage=4, name="formal", status=VerifyStatus.FAIL,
                    errors=[{"type": "postcondition_failure",
                              "message": "postcondition fails"}],
                )],
                total_duration_ms=100,
            ),
            attempt=1,
            counterexample=None,
        )
        # Should still produce a non-empty repair prompt
        assert len(prompt) > 50
        assert "postcondition" in prompt.lower() or "fail" in prompt.lower()

    def test_prompt_includes_spec_invariants(self):
        """Prompt always includes the spec invariants regardless of CE."""
        from nightjar.retry import build_cegis_repair_prompt
        spec = _make_spec()
        prompt = build_cegis_repair_prompt(
            spec=spec,
            failed_code="def f(x): return x",
            verify_result=VerifyResult(
                verified=False,
                stages=[StageResult(
                    stage=4, name="formal", status=VerifyStatus.FAIL,
                    errors=[],
                )],
                total_duration_ms=100,
            ),
            attempt=2,
            counterexample={"x": "0"},
        )
        # Spec invariant statement should appear
        assert "result >= 0" in prompt


class TestCegisIntegrationInRetry:
    """Tests that run_with_retry uses CEGIS counterexample context."""

    def test_run_with_retry_extracts_ce_from_formal_stage(self):
        """When formal stage has counterexample, it passes to LLM repair."""
        from nightjar.retry import run_with_retry

        fail_result = VerifyResult(
            verified=False,
            stages=[StageResult(
                stage=4, name="formal", status=VerifyStatus.FAIL,
                errors=[{
                    "type": "postcondition_failure",
                    "message": "counterexample for 'f':\n  x := -5\n",
                }],
            )],
            total_duration_ms=200,
        )

        spec = _make_spec()
        with patch("nightjar.retry.run_pipeline") as mock_pipeline, \
             patch("nightjar.retry._call_repair_llm") as mock_llm:
            mock_pipeline.side_effect = [fail_result, VerifyResult(
                verified=True,
                stages=[StageResult(stage=4, name="formal",
                                    status=VerifyStatus.PASS)],
                total_duration_ms=100,
            )]
            mock_llm.return_value = "def f(x): return abs(x)"

            result = run_with_retry(spec, "def f(x): return x", max_retries=1)

        assert result.verified is True
        # LLM was called — CEGIS used the counterexample in context
        mock_llm.assert_called_once()

    def test_cegis_prompt_used_when_ce_available(self):
        """When formal stage fails with CE, build_cegis_repair_prompt is called."""
        from nightjar.retry import run_with_retry

        fail_result = VerifyResult(
            verified=False,
            stages=[StageResult(
                stage=4, name="formal", status=VerifyStatus.FAIL,
                errors=[{
                    "type": "postcondition_failure",
                    "message": (
                        "module.dfy(5,0): Error: postcondition fails\n"
                        "  counterexample for 'f':\n"
                        "    x := -1\n"
                    ),
                }],
            )],
            total_duration_ms=200,
        )

        spec = _make_spec()
        with patch("nightjar.retry.run_pipeline") as mock_pipeline, \
             patch("nightjar.retry.build_cegis_repair_prompt") as mock_cegis, \
             patch("nightjar.retry._call_llm_with_prompt") as mock_llm_raw:
            mock_pipeline.return_value = fail_result
            mock_cegis.return_value = "CEGIS prompt"
            mock_llm_raw.return_value = "def f(x): return abs(x)"

            run_with_retry(spec, "def f(x): return x", max_retries=1)

        # CEGIS prompt builder was invoked
        assert mock_cegis.called, "build_cegis_repair_prompt should be called"

    def test_counterexample_stored_on_stage_result(self):
        """parse_dafny_counterexample is applied to formal stage error messages."""
        from nightjar.retry import extract_counterexample_from_stage

        stage = StageResult(
            stage=4, name="formal", status=VerifyStatus.FAIL,
            errors=[{
                "type": "postcondition_failure",
                "message": (
                    "  counterexample for 'transfer_funds':\n"
                    "    amount := -500\n"
                    "    balance := 1000\n"
                ),
            }],
        )
        ce = extract_counterexample_from_stage(stage)
        assert ce is not None
        assert ce["amount"] == "-500"
        assert ce["balance"] == "1000"

    def test_extract_counterexample_returns_none_for_non_formal_stage(self):
        """PBT/schema stages don't have Dafny CEs — returns None."""
        from nightjar.retry import extract_counterexample_from_stage

        stage = StageResult(
            stage=3, name="pbt", status=VerifyStatus.FAIL,
            errors=[{"type": "property_violation", "message": "assertion failed"}],
        )
        ce = extract_counterexample_from_stage(stage)
        assert ce is None


# ─── AE-2: AlphaEvolve Inspiration Injection ─────────────────────────────────
# Tests for _select_inspiration(), build_cegis_repair_prompt(inspirations=...),
# and _call_repair_llm(inspirations=...) added per alphaevolve-implementation-plan.md


def _make_bfs_node(code: str, score: float, error_hash: str, depth: int = 0):
    """Helper: construct a BFSNode without importing it at module level."""
    from nightjar.retry import BFSNode
    return BFSNode(code=code, score=score, depth=depth, error_hash=error_hash)


def _make_fail_result() -> VerifyResult:
    return VerifyResult(
        verified=False,
        stages=[StageResult(
            stage=4, name="formal", status=VerifyStatus.FAIL,
            errors=[{"type": "postcondition_failure", "message": "proof failed"}],
        )],
        total_duration_ms=100,
    )


class TestAlphaEvolveInspirationInjection:
    """AE-2 tests — inspiration selection and prompt augmentation."""

    # ── build_cegis_repair_prompt with inspirations ───────────────────────────

    def test_prompt_with_inspiration_includes_alternative_approach_section(self):
        """Prompt with inspirations contains 'Alternative Approach' section."""
        from nightjar.retry import build_cegis_repair_prompt

        spec = _make_spec()
        insp = _make_bfs_node(code="alt_code", score=0.3, error_hash="abc12345")
        prompt = build_cegis_repair_prompt(
            spec=spec,
            failed_code="def f(x): return x",
            verify_result=_make_fail_result(),
            attempt=1,
            counterexample=None,
            inspirations=[insp],
        )
        assert "Alternative Approach" in prompt

    def test_prompt_without_inspiration_unchanged(self):
        """Prompt with inspirations=None does NOT contain 'Alternative Approach'."""
        from nightjar.retry import build_cegis_repair_prompt

        spec = _make_spec()
        prompt = build_cegis_repair_prompt(
            spec=spec,
            failed_code="def f(x): return x",
            verify_result=_make_fail_result(),
            attempt=1,
            counterexample=None,
            inspirations=None,
        )
        assert "Alternative Approach" not in prompt

    def test_prompt_with_inspiration_truncates_long_code(self):
        """Inspiration code with > 40 lines is truncated to 40 lines in prompt."""
        from nightjar.retry import build_cegis_repair_prompt

        spec = _make_spec()
        # Build a 100-line inspiration code snippet
        long_code = "\n".join(f"line_{i} = {i}" for i in range(100))
        insp = _make_bfs_node(code=long_code, score=0.4, error_hash="def56789")
        prompt = build_cegis_repair_prompt(
            spec=spec,
            failed_code="def f(x): return x",
            verify_result=_make_fail_result(),
            attempt=1,
            counterexample=None,
            inspirations=[insp],
        )
        # Truncation marker must appear
        assert "# ... (truncated)" in prompt
        # Lines 40+ must NOT appear (line_40 up to line_99 should be cut)
        assert "line_40 = 40" not in prompt
        assert "line_99 = 99" not in prompt
        # The first 40 lines must be present
        assert "line_0 = 0" in prompt
        assert "line_39 = 39" in prompt

    # ── _select_inspiration ───────────────────────────────────────────────────

    def test_inspiration_selection_picks_different_error_type(self):
        """_select_inspiration returns the highest-scoring node with different error_hash."""
        from nightjar.retry import _select_inspiration

        parent = _make_bfs_node(code="parent_code", score=0.5, error_hash="aaa11111")
        node_same = _make_bfs_node(code="same_code", score=0.9, error_hash="aaa11111")
        node_diff = _make_bfs_node(code="diff_code", score=0.7, error_hash="bbb22222")

        # population contains two nodes: one with same hash, one different
        population = [
            (parent, _make_fail_result()),
            (node_same, _make_fail_result()),
            (node_diff, _make_fail_result()),
        ]
        result = _select_inspiration(population, parent)
        assert result is not None
        assert result.error_hash == "bbb22222"

    def test_inspiration_selection_returns_none_when_all_same_error_hash(self):
        """_select_inspiration returns None when all nodes share the parent's error_hash."""
        from nightjar.retry import _select_inspiration

        parent = _make_bfs_node(code="parent_code", score=0.5, error_hash="aaabbb11")
        node_a = _make_bfs_node(code="code_a", score=0.6, error_hash="aaabbb11")
        node_b = _make_bfs_node(code="code_b", score=0.4, error_hash="aaabbb11")

        population = [
            (parent, _make_fail_result()),
            (node_a, _make_fail_result()),
            (node_b, _make_fail_result()),
        ]
        result = _select_inspiration(population, parent)
        assert result is None

    def test_inspiration_selection_returns_none_for_single_element_population(self):
        """_select_inspiration returns None when population has only 1 entry."""
        from nightjar.retry import _select_inspiration

        parent = _make_bfs_node(code="only_node", score=0.5, error_hash="abc12345")
        population = [(parent, _make_fail_result())]
        result = _select_inspiration(population, parent)
        assert result is None

    # ── _call_repair_llm signature ────────────────────────────────────────────

    def test_call_repair_llm_accepts_inspirations_param(self):
        """_call_repair_llm has an 'inspirations' parameter with default None."""
        import inspect
        from nightjar.retry import _call_repair_llm

        sig = inspect.signature(_call_repair_llm)
        assert "inspirations" in sig.parameters, (
            "_call_repair_llm must have an 'inspirations' parameter"
        )
        default = sig.parameters["inspirations"].default
        assert default is None, (
            f"'inspirations' default must be None, got {default!r}"
        )
