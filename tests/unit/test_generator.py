"""Tests for the code generation pipeline.

Tests the Analyst → Formalizer → Coder pipeline [REF-C03, REF-P07].
All LLM calls go through litellm [REF-T16].

BEFORE MODIFYING: Read docs/ARCHITECTURE.md Section 5.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from contractd.types import (
    CardSpec, Contract, ContractInput, ContractOutput,
    ModuleBoundary, Invariant, InvariantTier,
)
from contractd.generator import (
    generate_code,
    run_analyst,
    run_formalizer,
    run_coder,
    get_model,
    GenerationResult,
)


# -- Fixtures --


def make_spec() -> CardSpec:
    """Create a minimal CardSpec for testing."""
    return CardSpec(
        card_version="1.0",
        id="user-auth",
        title="User Authentication",
        status="draft",
        module=ModuleBoundary(
            owns=["login()", "logout()", "validate_token()"],
            depends_on={"postgres": "approved", "bcrypt": "^4.x"},
        ),
        contract=Contract(
            inputs=[
                ContractInput(name="email", type="string"),
                ContractInput(name="password", type="string"),
            ],
            outputs=[
                ContractOutput(name="session_token", type="string"),
            ],
            errors=["AuthError"],
        ),
        invariants=[
            Invariant(
                id="INV-001",
                tier=InvariantTier.PROPERTY,
                statement="A valid token always corresponds to exactly one active user session",
                rationale="Security requirement",
            ),
        ],
        intent="Let users log in with email/password and get a session token.",
        acceptance_criteria=(
            "Given valid credentials, When login() is called, Then a JWT is returned\n"
            "Given invalid password, When login() is called, Then AuthError is raised"
        ),
    )


def mock_llm_response(content: str) -> MagicMock:
    """Create a mock litellm response object."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    return response


# -- Model selection tests --


class TestGetModel:
    """Test model selection from CARD_MODEL env var [REF-T16]."""

    def test_default_model(self):
        """Default model when CARD_MODEL is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove CARD_MODEL if present
            os.environ.pop("CARD_MODEL", None)
            model = get_model()
            assert model == "claude-sonnet-4-6"

    def test_custom_model_from_env(self):
        """Model from CARD_MODEL env var."""
        with patch.dict(os.environ, {"CARD_MODEL": "deepseek/deepseek-chat"}):
            model = get_model()
            assert model == "deepseek/deepseek-chat"

    def test_model_override_parameter(self):
        """Explicit model parameter overrides env var."""
        with patch.dict(os.environ, {"CARD_MODEL": "deepseek/deepseek-chat"}):
            model = get_model(override="openai/o3")
            assert model == "openai/o3"


# -- Analyst stage tests --


class TestAnalyst:
    """Test the Analyst agent — LLM call 1 [REF-C03, REF-P07]."""

    @patch("contractd.generator.litellm.completion")
    def test_analyst_returns_analysis(self, mock_completion):
        """Analyst reads spec and produces structured requirements analysis."""
        mock_completion.return_value = mock_llm_response(
            "## Requirements Analysis\n"
            "1. Email/password authentication\n"
            "2. JWT token generation\n"
            "3. Edge cases: empty email, empty password\n"
        )
        spec = make_spec()
        result = run_analyst(spec)
        assert isinstance(result, str)
        assert len(result) > 0
        # Verify litellm.completion was called
        mock_completion.assert_called_once()
        call_kwargs = mock_completion.call_args
        # Should have system + user messages
        messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs.kwargs["messages"]
        assert any(m["role"] == "system" for m in messages)
        assert any(m["role"] == "user" for m in messages)

    @patch("contractd.generator.litellm.completion")
    def test_analyst_includes_intent_and_criteria(self, mock_completion):
        """Analyst prompt includes spec intent and acceptance criteria."""
        mock_completion.return_value = mock_llm_response("Analysis output")
        spec = make_spec()
        run_analyst(spec)
        call_kwargs = mock_completion.call_args
        messages = call_kwargs.kwargs.get("messages", [])
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "email" in user_msg["content"].lower() or "login" in user_msg["content"].lower()


# -- Formalizer stage tests --


class TestFormalizer:
    """Test the Formalizer agent — LLM call 2 [REF-C03, REF-P07]."""

    @patch("contractd.generator.litellm.completion")
    def test_formalizer_returns_dafny_skeleton(self, mock_completion):
        """Formalizer produces Dafny module with requires/ensures."""
        dafny_skeleton = (
            "module UserAuth {\n"
            "  method Login(email: string, password: string) returns (token: string)\n"
            "    requires |email| > 0\n"
            "    requires |password| > 0\n"
            "    ensures |token| > 0\n"
            "  {\n"
            "    // implementation placeholder\n"
            "  }\n"
            "}\n"
        )
        mock_completion.return_value = mock_llm_response(dafny_skeleton)
        spec = make_spec()
        analyst_output = "Requirements analysis text"
        result = run_formalizer(spec, analyst_output)
        assert isinstance(result, str)
        assert len(result) > 0
        mock_completion.assert_called_once()

    @patch("contractd.generator.litellm.completion")
    def test_formalizer_receives_analyst_output(self, mock_completion):
        """Formalizer prompt includes the analyst's analysis."""
        mock_completion.return_value = mock_llm_response("Dafny skeleton")
        spec = make_spec()
        analyst_output = "UNIQUE_ANALYST_MARKER_XYZ"
        run_formalizer(spec, analyst_output)
        call_kwargs = mock_completion.call_args
        messages = call_kwargs.kwargs.get("messages", [])
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "UNIQUE_ANALYST_MARKER_XYZ" in user_msg["content"]


# -- Coder stage tests --


class TestCoder:
    """Test the Coder agent — LLM call 3 [REF-C03, REF-P07]."""

    @patch("contractd.generator.litellm.completion")
    def test_coder_returns_complete_dafny(self, mock_completion):
        """Coder produces complete Dafny implementation."""
        complete_dafny = (
            "module UserAuth {\n"
            "  method Login(email: string, password: string) returns (token: string)\n"
            "    requires |email| > 0\n"
            "    requires |password| > 0\n"
            "    ensures |token| > 0\n"
            "  {\n"
            '    token := "jwt_" + email;\n'
            "  }\n"
            "}\n"
        )
        mock_completion.return_value = mock_llm_response(complete_dafny)
        spec = make_spec()
        formalizer_output = "Dafny skeleton with requires/ensures"
        result = run_coder(spec, formalizer_output)
        assert isinstance(result, str)
        assert len(result) > 0
        mock_completion.assert_called_once()

    @patch("contractd.generator.litellm.completion")
    def test_coder_receives_formalizer_output(self, mock_completion):
        """Coder prompt includes the formalizer's Dafny skeleton."""
        mock_completion.return_value = mock_llm_response("Complete Dafny")
        spec = make_spec()
        formalizer_output = "UNIQUE_FORMALIZER_MARKER_ABC"
        run_coder(spec, formalizer_output)
        call_kwargs = mock_completion.call_args
        messages = call_kwargs.kwargs.get("messages", [])
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "UNIQUE_FORMALIZER_MARKER_ABC" in user_msg["content"]


# -- Full pipeline tests --


class TestGenerateCode:
    """Test the full generation pipeline [REF-C03]."""

    @patch("contractd.generator.litellm.completion")
    def test_full_pipeline_produces_result(self, mock_completion):
        """Full pipeline: Analyst → Formalizer → Coder produces GenerationResult."""
        mock_completion.side_effect = [
            mock_llm_response("Requirements analysis"),
            mock_llm_response("Dafny skeleton with requires/ensures"),
            mock_llm_response(
                "module UserAuth {\n"
                "  method Login(email: string, password: string) returns (token: string)\n"
                "    requires |email| > 0\n"
                "    ensures |token| > 0\n"
                "  {\n"
                '    token := "jwt_" + email;\n'
                "  }\n"
                "}\n"
            ),
        ]
        spec = make_spec()
        result = generate_code(spec)
        assert isinstance(result, GenerationResult)
        assert result.dafny_code is not None
        assert len(result.dafny_code) > 0
        assert result.analyst_output is not None
        assert result.formalizer_output is not None
        # Three LLM calls: analyst, formalizer, coder
        assert mock_completion.call_count == 3

    @patch("contractd.generator.litellm.completion")
    def test_pipeline_uses_correct_model(self, mock_completion):
        """Pipeline uses model from CARD_MODEL env var [REF-T16]."""
        mock_completion.side_effect = [
            mock_llm_response("Analysis"),
            mock_llm_response("Skeleton"),
            mock_llm_response("Complete Dafny"),
        ]
        spec = make_spec()
        with patch.dict(os.environ, {"CARD_MODEL": "deepseek/deepseek-chat"}):
            generate_code(spec)
        # All three calls should use the same model
        for call in mock_completion.call_args_list:
            assert call.kwargs.get("model") == "deepseek/deepseek-chat"

    @patch("contractd.generator.litellm.completion")
    def test_pipeline_with_model_override(self, mock_completion):
        """Pipeline accepts explicit model override."""
        mock_completion.side_effect = [
            mock_llm_response("Analysis"),
            mock_llm_response("Skeleton"),
            mock_llm_response("Complete Dafny"),
        ]
        spec = make_spec()
        generate_code(spec, model="openai/o3")
        for call in mock_completion.call_args_list:
            assert call.kwargs.get("model") == "openai/o3"

    @patch("contractd.generator.litellm.completion")
    def test_pipeline_sequential_data_flow(self, mock_completion):
        """Each stage receives output from the previous stage."""
        analyst_text = "ANALYST_OUTPUT_12345"
        formalizer_text = "FORMALIZER_OUTPUT_67890"
        coder_text = "CODER_OUTPUT_FINAL"
        mock_completion.side_effect = [
            mock_llm_response(analyst_text),
            mock_llm_response(formalizer_text),
            mock_llm_response(coder_text),
        ]
        spec = make_spec()
        result = generate_code(spec)
        # Formalizer call (2nd) should include analyst output
        formalizer_call = mock_completion.call_args_list[1]
        formalizer_msgs = formalizer_call.kwargs.get("messages", [])
        formalizer_user = next(m for m in formalizer_msgs if m["role"] == "user")
        assert analyst_text in formalizer_user["content"]
        # Coder call (3rd) should include formalizer output
        coder_call = mock_completion.call_args_list[2]
        coder_msgs = coder_call.kwargs.get("messages", [])
        coder_user = next(m for m in coder_msgs if m["role"] == "user")
        assert formalizer_text in coder_user["content"]


# -- Edge cases --


class TestEdgeCases:
    """Test error handling in the generation pipeline."""

    @patch("contractd.generator.litellm.completion")
    def test_llm_returns_empty_content(self, mock_completion):
        """Handle LLM returning empty content gracefully."""
        mock_completion.return_value = mock_llm_response("")
        spec = make_spec()
        with pytest.raises(ValueError, match="empty"):
            run_analyst(spec)

    def test_generate_code_requires_spec(self):
        """generate_code raises TypeError without a CardSpec."""
        with pytest.raises(TypeError):
            generate_code(None)  # type: ignore

    @patch("contractd.generator.litellm.completion")
    def test_temperature_for_generation(self, mock_completion):
        """Generation uses appropriate temperature settings."""
        mock_completion.side_effect = [
            mock_llm_response("Analysis"),
            mock_llm_response("Skeleton"),
            mock_llm_response("Complete Dafny"),
        ]
        spec = make_spec()
        generate_code(spec)
        # All calls should use low temperature for deterministic output
        for call in mock_completion.call_args_list:
            temp = call.kwargs.get("temperature", 1.0)
            assert temp <= 0.3, f"Temperature {temp} too high for code generation"
