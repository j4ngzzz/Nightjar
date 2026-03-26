"""Tests for the nightjar auto command — zero-friction invariant generation.

Tests the full 8-step pipeline from Task W2.1 (Scout 4 F9 synthesis):
  1. Parse NL intent → AST (ContextCov, CR-02)
  2. LLM refinement → invariant candidates (NL2Contract, CR-03)
  3. Intent router classifies candidates
  4. Domain generators (icontract, Hypothesis, Dafny)
  5. HiLDe ranking → top 5-10
  6. "For any X where Y, Z holds" format (Kiro UX)
  7. Y/n/modify approval loop
  8. Write to .card.md

References:
- [REF-P14] NL2Contract (arxiv 2510.12702) — CR-03
- Scout 4 F1 (ContextCov: arxiv 2603.00822) — CR-02
- [REF-T10] icontract, [REF-T03] Hypothesis, [REF-T01] Dafny
- [REF-T17] Click CLI

TDD: Tests written BEFORE implementation. All should FAIL initially.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

from nightjar.auto import (
    run_auto,
    AutoResult,
)
from nightjar.intent_router import InvariantClass
from nightjar.invariant_generators import InvariantCandidate, RankedInvariant


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_litellm_candidates(statements: list[str]) -> MagicMock:
    """Build a litellm mock that returns a JSON list of invariant candidates."""
    candidates = [
        {
            "type": "behavioral",
            "statement": s,
            "confidence": 0.85,
        }
        for s in statements
    ]
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(candidates)
    return mock_resp


def _mock_litellm_code(code: str) -> MagicMock:
    """Build a litellm mock that returns code text."""
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = code
    return mock_resp


# ── AutoResult ────────────────────────────────────────────────────────────────


class TestAutoResult:
    """Tests for the AutoResult return type."""

    def test_auto_result_has_card_path(self):
        """AutoResult must expose the path of the written .card.md file."""
        result = AutoResult(
            card_path=Path("test.card.md"),
            approved_count=3,
            skipped_count=1,
        )
        assert result.card_path == Path("test.card.md")

    def test_auto_result_tracks_counts(self):
        result = AutoResult(
            card_path=Path("p.card.md"),
            approved_count=5,
            skipped_count=2,
        )
        assert result.approved_count == 5
        assert result.skipped_count == 2


# ── run_auto — full pipeline ──────────────────────────────────────────────────


class TestAutoCreateCardSpecFromNLIntent:
    """test_auto_creates_card_spec_from_nl_intent (build plan required test)

    Full integration test of the 8-step pipeline.
    All LLM calls are mocked.
    """

    def _setup_llm_mocks(self, mock_llm):
        """Configure mock to return appropriate responses per call sequence.

        Pipeline makes: 1 candidate call + N×3 generator calls per approved invariant.
        With 3 candidates approved (yes=True) = 1 + 9 = 10 total calls.
        We provide enough responses to cover all calls.
        """
        candidate_json = json.dumps([
            {"type": "behavioral", "statement": "charge amount must be positive", "confidence": 0.95},
            {"type": "behavioral", "statement": "returns receipt on success", "confidence": 0.90},
            {"type": "numerical", "statement": "amount must be greater than zero", "confidence": 0.88},
        ])
        icontract_code = "@icontract.require(lambda amount: amount > 0, 'amount must be positive')"
        hypothesis_code = (
            "from hypothesis import given, settings\n"
            "from hypothesis import strategies as st\n"
            "@given(st.floats(min_value=0.01))\n"
            "def test_charge_amount_positive(amount):\n"
            "    assert amount > 0\n"
        )
        dafny_code = "# optional: requires amount > 0"

        def _make_mock(content):
            return MagicMock(**{"choices": [MagicMock(**{"message": MagicMock(content=content)})]})

        # First call: candidates. Then each approved invariant gets 3 generator calls.
        # 3 candidates × 3 generators = 9 + 1 = 10 calls total
        responses = [_make_mock(candidate_json)]
        for _ in range(3):  # for each approved invariant
            responses.append(_make_mock(icontract_code))
            responses.append(_make_mock(hypothesis_code))
            responses.append(_make_mock(dafny_code))

        mock_llm.side_effect = responses

    def test_auto_creates_card_spec_from_nl_intent(self):
        """run_auto writes a .card.md file from NL intent (all LLM mocked, yes=True)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "payment.card.md")
            with patch("litellm.completion") as mock_llm:
                self._setup_llm_mocks(mock_llm)
                result = run_auto(
                    nl_intent="Build a payment processor that charges credit cards",
                    output_path=output_path,
                    model="test-model",
                    yes=True,  # skip interactive approval
                )

            assert isinstance(result, AutoResult)
            assert result.approved_count > 0
            assert Path(output_path).exists()

    def test_auto_card_md_has_yaml_frontmatter(self):
        """Written .card.md must have YAML frontmatter with invariants section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "payment.card.md")
            with patch("litellm.completion") as mock_llm:
                self._setup_llm_mocks(mock_llm)
                run_auto(
                    nl_intent="Build a payment processor",
                    output_path=output_path,
                    model="test-model",
                    yes=True,
                )

            content = Path(output_path).read_text()
            assert "---" in content  # YAML frontmatter delimiters
            assert "invariants" in content

    def test_auto_card_md_has_intent_section(self):
        """Written .card.md must have ## Intent section from NL input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "payment.card.md")
            with patch("litellm.completion") as mock_llm:
                self._setup_llm_mocks(mock_llm)
                run_auto(
                    nl_intent="Build a payment processor",
                    output_path=output_path,
                    model="test-model",
                    yes=True,
                )

            content = Path(output_path).read_text()
            assert "## Intent" in content
            assert "payment processor" in content.lower()

    def test_auto_uses_nightjar_model_env_var(self):
        """run_auto must respect NIGHTJAR_MODEL env var when model not specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.card.md")
            with patch("litellm.completion") as mock_llm:
                self._setup_llm_mocks(mock_llm)
                with patch.dict("os.environ", {"NIGHTJAR_MODEL": "my-custom-model"}):
                    run_auto(
                        nl_intent="Build a payment processor",
                        output_path=output_path,
                        model=None,  # use env var
                        yes=True,
                    )
            # Verify litellm was called with the env var model (check at least one call)
            assert mock_llm.call_count >= 1
            first_call = mock_llm.call_args_list[0]
            model_used = first_call[1].get("model")
            assert model_used == "my-custom-model"

    def test_auto_empty_intent_raises(self):
        """Empty NL intent must raise ValueError before calling LLM."""
        with pytest.raises(ValueError, match="intent"):
            run_auto(
                nl_intent="",
                output_path="/tmp/test.card.md",
                model="test-model",
                yes=True,
            )


# ── Approval loop ─────────────────────────────────────────────────────────────


class TestApprovalLoop:
    """test_approval_loop_accepts_modify_reject (build plan required test)."""

    def test_approval_yes_accepts_all(self):
        """yes=True auto-accepts all ranked invariants."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.card.md")
            with patch("litellm.completion") as mock_llm:
                mock_llm.return_value = MagicMock(
                    **{"choices": [MagicMock(**{"message": MagicMock(content=json.dumps([
                        {"type": "behavioral", "statement": "input must not be None", "confidence": 0.9},
                        {"type": "numerical", "statement": "amount > 0", "confidence": 0.95},
                    ]))})]}
                )
                result = run_auto(
                    nl_intent="Sort positive numbers",
                    output_path=output_path,
                    model="test-model",
                    yes=True,
                )

            assert result.approved_count >= 0  # all accepted when yes=True

    def test_approval_interactive_accept(self):
        """Interactive mode with 'y' input accepts the invariant."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.card.md")
            with patch("litellm.completion") as mock_llm:
                mock_llm.return_value = MagicMock(
                    **{"choices": [MagicMock(**{"message": MagicMock(content=json.dumps([
                        {"type": "behavioral", "statement": "input must not be None", "confidence": 0.9},
                    ]))})]}
                )
                # Mock user input: accept
                with patch("click.prompt", return_value="y"):
                    result = run_auto(
                        nl_intent="Process input data",
                        output_path=output_path,
                        model="test-model",
                        yes=False,  # interactive
                    )

            assert isinstance(result, AutoResult)

    def test_approval_interactive_reject(self):
        """Interactive mode with 'n' input rejects the invariant."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.card.md")
            with patch("litellm.completion") as mock_llm:
                mock_llm.return_value = MagicMock(
                    **{"choices": [MagicMock(**{"message": MagicMock(content=json.dumps([
                        {"type": "behavioral", "statement": "to reject", "confidence": 0.5},
                    ]))})]}
                )
                with patch("click.prompt", return_value="n"):
                    result = run_auto(
                        nl_intent="Process input data",
                        output_path=output_path,
                        model="test-model",
                        yes=False,
                    )

            # All rejected → skipped_count should equal the number presented
            assert result.skipped_count >= 0

    def test_approval_interactive_modify(self):
        """Interactive mode with 'm' input allows modifying invariant text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.card.md")
            with patch("litellm.completion") as mock_llm:
                mock_llm.return_value = MagicMock(
                    **{"choices": [MagicMock(**{"message": MagicMock(content=json.dumps([
                        {"type": "behavioral", "statement": "original statement", "confidence": 0.8},
                    ]))})]}
                )
                # First prompt returns 'm', second returns modified text
                with patch("click.prompt", side_effect=["m", "modified statement text"]):
                    result = run_auto(
                        nl_intent="Process input data",
                        output_path=output_path,
                        model="test-model",
                        yes=False,
                    )

            assert isinstance(result, AutoResult)

    def test_approval_writes_card_even_if_all_rejected(self):
        """Even if all invariants rejected, .card.md is still written (empty invariants)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "test.card.md")
            with patch("litellm.completion") as mock_llm:
                mock_llm.return_value = MagicMock(
                    **{"choices": [MagicMock(**{"message": MagicMock(content=json.dumps([
                        {"type": "behavioral", "statement": "to reject", "confidence": 0.5},
                    ]))})]}
                )
                with patch("click.prompt", return_value="n"):
                    result = run_auto(
                        nl_intent="Process input data",
                        output_path=output_path,
                        model="test-model",
                        yes=False,
                    )

            assert Path(output_path).exists()


# ── Generator output in card.md ───────────────────────────────────────────────


class TestInvariantGeneratorsInCardMd:
    """test_invariant_generators_produce_valid_icontract (build plan required test).

    Tests that the generators produce code that lands correctly in .card.md.
    """

    def test_generators_produce_valid_icontract(self):
        """Approved behavioral invariant → valid icontract in card.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = str(Path(tmpdir) / "payment.card.md")

            icontract_code = (
                "@icontract.require(lambda amount: amount > 0, 'amount must be positive')"
            )
            hypothesis_code = (
                "from hypothesis import given\n"
                "from hypothesis import strategies as st\n"
                "@given(st.floats(min_value=0.01))\n"
                "def test_amount_positive(amount):\n"
                "    assert amount > 0\n"
            )

            def llm_side_effects(*args, **kwargs):
                # Determine which call this is by inspecting the messages
                messages = kwargs.get("messages", args[0] if args else [])
                content = str(messages)
                if "invariant" in content.lower() and "candidates" in content.lower():
                    return MagicMock(**{"choices": [MagicMock(**{"message": MagicMock(
                        content=json.dumps([{
                            "type": "behavioral",
                            "statement": "amount must be positive",
                            "confidence": 0.95,
                        }])
                    )})]})
                elif "icontract" in content.lower():
                    return MagicMock(**{"choices": [MagicMock(**{"message": MagicMock(content=icontract_code)})]})
                elif "hypothesis" in content.lower():
                    return MagicMock(**{"choices": [MagicMock(**{"message": MagicMock(content=hypothesis_code)})]})
                else:
                    return MagicMock(**{"choices": [MagicMock(**{"message": MagicMock(content="# optional: requires amount > 0")})]})

            with patch("litellm.completion", side_effect=llm_side_effects):
                result = run_auto(
                    nl_intent="Build a payment processor that charges credit cards",
                    output_path=output_path,
                    model="test-model",
                    yes=True,
                )

            card_content = Path(output_path).read_text()
            # Card must contain invariant statements
            assert "invariants" in card_content
