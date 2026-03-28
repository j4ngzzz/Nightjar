"""Tests for inferrer.py — LLM contract generation + CrossHair verification loop.

TDD: tests written before implementation.

References:
- [REF-NEW-08] NL2Contract: "Beyond Postconditions: Can LLMs infer Formal Contracts?"
  URL: https://arxiv.org/abs/2510.12702
- [REF-NEW-09] "Automatic Generation of Formal Specification and Verification Annotations"
  URL: https://arxiv.org/abs/2601.12845
- [REF-NEW-11] Clover: "Closed-Loop Verifiable Code Generation"
  URL: https://arxiv.org/abs/2310.17807
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from nightjar.inferrer import (
    InferredContract,
    _build_crosshair_source,
    _build_generate_prompt,
    _build_repair_prompt,
    _get_function_source,
    _parse_crosshair_output,
    _parse_llm_contracts,
    _resolve_model,
    _run_crosshair,
    infer_contracts,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

SIMPLE_FUNCTION = '''\
def add(x: int, y: int) -> int:
    """Return the sum of x and y."""
    return x + y
'''

AGE_FUNCTION = '''\
def validate_age(age: int) -> bool:
    """Return True if age is a valid human age."""
    return 0 <= age <= 150
'''

MULTI_FUNCTION_SOURCE = '''\
def foo(x: int) -> int:
    return x + 1

def bar(y: str) -> str:
    """Return y uppercased."""
    return y.upper()
'''


# ── InferredContract dataclass ────────────────────────────────────────────────


class TestInferredContract:
    """Tests for the InferredContract dataclass."""

    def test_is_dataclass(self):
        import dataclasses
        assert dataclasses.is_dataclass(InferredContract)

    def test_has_required_fields(self):
        contract = InferredContract(
            function_name="my_func",
            preconditions=["assert x > 0"],
            postconditions=["assert result >= 0"],
            confidence=0.8,
            verification_status="verified",
            counterexample=None,
            iterations_used=2,
        )
        assert contract.function_name == "my_func"
        assert contract.preconditions == ["assert x > 0"]
        assert contract.postconditions == ["assert result >= 0"]
        assert contract.confidence == 0.8
        assert contract.verification_status == "verified"
        assert contract.counterexample is None
        assert contract.iterations_used == 2

    def test_counterexample_can_be_dict(self):
        contract = InferredContract(
            function_name="f",
            preconditions=[],
            postconditions=[],
            confidence=0.0,
            verification_status="counterexample",
            counterexample={"x": -1, "y": 0},
            iterations_used=1,
        )
        assert contract.counterexample == {"x": -1, "y": 0}

    def test_default_confidence_is_float(self):
        contract = InferredContract(
            function_name="f",
            preconditions=[],
            postconditions=[],
            confidence=0.5,
            verification_status="unverified",
            counterexample=None,
            iterations_used=0,
        )
        assert isinstance(contract.confidence, float)

    def test_verification_status_values(self):
        """verification_status should accept standard status strings."""
        for status in ("verified", "unverified", "counterexample"):
            contract = InferredContract(
                function_name="f",
                preconditions=[],
                postconditions=[],
                confidence=0.5,
                verification_status=status,
                counterexample=None,
                iterations_used=0,
            )
            assert contract.verification_status == status


# ── _resolve_model ────────────────────────────────────────────────────────────


class TestResolveModel:
    """Tests for _resolve_model helper."""

    def test_returns_provided_model_string(self):
        result = _resolve_model("gpt-4o")
        assert result == "gpt-4o"

    def test_returns_provided_model_string_variant(self):
        result = _resolve_model("claude-sonnet-4-6")
        assert result == "claude-sonnet-4-6"

    def test_falls_back_to_env_var(self, monkeypatch):
        monkeypatch.setenv("NIGHTJAR_MODEL", "claude-haiku-3-5")
        result = _resolve_model("")
        assert result == "claude-haiku-3-5"

    def test_default_fallback_without_env(self, monkeypatch):
        monkeypatch.delenv("NIGHTJAR_MODEL", raising=False)
        result = _resolve_model("")
        # Should return a non-empty default string
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_string(self):
        result = _resolve_model("any-model")
        assert isinstance(result, str)


# ── _get_function_source ──────────────────────────────────────────────────────


class TestGetFunctionSource:
    """Tests for _get_function_source helper."""

    def test_extracts_named_function(self):
        result = _get_function_source(SIMPLE_FUNCTION, "add")
        assert "def add" in result
        assert "return x + y" in result

    def test_extracts_function_from_multi_function_source(self):
        result = _get_function_source(MULTI_FUNCTION_SOURCE, "bar")
        assert "def bar" in result
        assert "y.upper()" in result

    def test_returns_empty_string_when_not_found(self):
        result = _get_function_source(SIMPLE_FUNCTION, "nonexistent_function")
        assert result == ""

    def test_returns_string(self):
        result = _get_function_source(SIMPLE_FUNCTION, "add")
        assert isinstance(result, str)

    def test_extracted_source_is_valid_python(self):
        import ast
        result = _get_function_source(MULTI_FUNCTION_SOURCE, "foo")
        # Should be parseable Python
        ast.parse(result)

    def test_function_name_not_in_module_returns_empty(self):
        source = "x = 1\ny = 2\n"
        result = _get_function_source(source, "x")
        assert result == ""


# ── _build_generate_prompt ────────────────────────────────────────────────────


class TestBuildGeneratePrompt:
    """Tests for _build_generate_prompt helper."""

    def test_returns_two_messages(self):
        messages = _build_generate_prompt(SIMPLE_FUNCTION, ["x > 0"])
        assert len(messages) == 2

    def test_first_message_is_system(self):
        messages = _build_generate_prompt(SIMPLE_FUNCTION, [])
        assert messages[0]["role"] == "system"

    def test_second_message_is_user(self):
        messages = _build_generate_prompt(SIMPLE_FUNCTION, [])
        assert messages[1]["role"] == "user"

    def test_source_code_in_user_message(self):
        messages = _build_generate_prompt(SIMPLE_FUNCTION, [])
        assert "def add" in messages[1]["content"]

    def test_retrieved_examples_in_user_message(self):
        examples = ["age >= 0", "age <= 150"]
        messages = _build_generate_prompt(SIMPLE_FUNCTION, examples)
        content = messages[1]["content"]
        assert "age >= 0" in content or "age <= 150" in content

    def test_system_message_mentions_preconditions(self):
        messages = _build_generate_prompt(SIMPLE_FUNCTION, [])
        system = messages[0]["content"].lower()
        assert "precondition" in system

    def test_system_message_mentions_postconditions(self):
        messages = _build_generate_prompt(SIMPLE_FUNCTION, [])
        system = messages[0]["content"].lower()
        assert "postcondition" in system

    def test_returns_list_of_dicts(self):
        messages = _build_generate_prompt(SIMPLE_FUNCTION, [])
        assert isinstance(messages, list)
        for m in messages:
            assert isinstance(m, dict)
            assert "role" in m
            assert "content" in m

    def test_system_mentions_json_output(self):
        messages = _build_generate_prompt(SIMPLE_FUNCTION, [])
        system = messages[0]["content"]
        assert "json" in system.lower() or "JSON" in system


# ── _build_repair_prompt ──────────────────────────────────────────────────────


class TestBuildRepairPrompt:
    """Tests for _build_repair_prompt helper."""

    def test_returns_two_messages(self):
        messages = _build_repair_prompt(
            source="def f(x): return x",
            failed_contracts=["assert x > 100"],
            crosshair_output="counterexample: x=0",
        )
        assert len(messages) == 2

    def test_first_message_is_system(self):
        messages = _build_repair_prompt("def f(x): return x", ["assert x > 0"], "error")
        assert messages[0]["role"] == "system"

    def test_second_message_is_user(self):
        messages = _build_repair_prompt("def f(x): return x", ["assert x > 0"], "error")
        assert messages[1]["role"] == "user"

    def test_failed_contract_in_user_message(self):
        messages = _build_repair_prompt(
            "def f(x): return x", ["assert x > 100"], "counterexample: x=50"
        )
        assert "assert x > 100" in messages[1]["content"]

    def test_crosshair_output_in_user_message(self):
        messages = _build_repair_prompt(
            "def f(x): return x", ["assert x > 0"], "counterexample: x=-1"
        )
        assert "counterexample" in messages[1]["content"].lower() or "x=-1" in messages[1]["content"]

    def test_source_in_user_message(self):
        messages = _build_repair_prompt("def my_func(x): return x", ["assert x > 0"], "error")
        assert "my_func" in messages[1]["content"]


# ── _parse_llm_contracts ──────────────────────────────────────────────────────


class TestParseLLMContracts:
    """Tests for _parse_llm_contracts helper."""

    def test_parses_valid_json_preconditions_postconditions(self):
        raw = json.dumps({
            "preconditions": ["assert x > 0"],
            "postconditions": ["assert result >= 0"],
        })
        pre, post = _parse_llm_contracts(raw)
        assert pre == ["assert x > 0"]
        assert post == ["assert result >= 0"]

    def test_returns_empty_lists_on_invalid_json(self):
        pre, post = _parse_llm_contracts("not json at all")
        assert pre == []
        assert post == []

    def test_returns_empty_lists_on_empty_string(self):
        pre, post = _parse_llm_contracts("")
        assert pre == []
        assert post == []

    def test_handles_missing_preconditions_key(self):
        raw = json.dumps({"postconditions": ["assert result > 0"]})
        pre, post = _parse_llm_contracts(raw)
        assert pre == []
        assert post == ["assert result > 0"]

    def test_handles_missing_postconditions_key(self):
        raw = json.dumps({"preconditions": ["assert x >= 0"]})
        pre, post = _parse_llm_contracts(raw)
        assert pre == ["assert x >= 0"]
        assert post == []

    def test_extracts_json_from_markdown_code_block(self):
        raw = '```json\n{"preconditions": ["assert x > 0"], "postconditions": []}\n```'
        pre, post = _parse_llm_contracts(raw)
        assert pre == ["assert x > 0"]
        assert post == []

    def test_returns_tuple_of_lists(self):
        raw = json.dumps({"preconditions": [], "postconditions": []})
        result = _parse_llm_contracts(raw)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert isinstance(result[1], list)

    def test_filters_empty_strings(self):
        raw = json.dumps({"preconditions": ["assert x > 0", "", "  "], "postconditions": []})
        pre, post = _parse_llm_contracts(raw)
        # Empty/whitespace-only strings should be filtered out
        assert "" not in pre
        assert all(s.strip() for s in pre)

    def test_multiple_contracts(self):
        raw = json.dumps({
            "preconditions": ["assert age >= 0", "assert age <= 150"],
            "postconditions": ["assert result is True or result is False"],
        })
        pre, post = _parse_llm_contracts(raw)
        assert len(pre) == 2
        assert len(post) == 1


# ── _build_crosshair_source ───────────────────────────────────────────────────


class TestBuildCrosshairSource:
    """Tests for _build_crosshair_source helper."""

    def test_returns_string(self):
        result = _build_crosshair_source(
            function_source=SIMPLE_FUNCTION,
            preconditions=["assert x >= 0"],
            postconditions=["assert result >= 0"],
        )
        assert isinstance(result, str)

    def test_includes_function_source(self):
        result = _build_crosshair_source(
            function_source=SIMPLE_FUNCTION,
            preconditions=[],
            postconditions=[],
        )
        assert "def add" in result

    def test_includes_crosshair_pre_decorator_or_inline(self):
        """CrossHair contracts should be present in output."""
        result = _build_crosshair_source(
            function_source=SIMPLE_FUNCTION,
            preconditions=["assert x >= 0"],
            postconditions=["assert result >= 0"],
        )
        # Either inline assertions or CrossHair decorator pattern
        assert "x >= 0" in result or "result >= 0" in result

    def test_valid_python_output(self):
        import ast
        result = _build_crosshair_source(
            function_source=SIMPLE_FUNCTION,
            preconditions=["assert x >= 0"],
            postconditions=["assert result >= 0"],
        )
        # Should be parseable Python
        ast.parse(result)

    def test_empty_contracts_produces_valid_python(self):
        import ast
        result = _build_crosshair_source(
            function_source=SIMPLE_FUNCTION,
            preconditions=[],
            postconditions=[],
        )
        ast.parse(result)


# ── _run_crosshair ────────────────────────────────────────────────────────────


class TestRunCrosshair:
    """Tests for _run_crosshair helper."""

    def test_returns_tuple_of_str_and_dict(self):
        """_run_crosshair returns (status_str, info_dict)."""
        status, info = _run_crosshair(SIMPLE_FUNCTION)
        assert isinstance(status, str)
        assert isinstance(info, dict)

    def test_status_is_known_value(self):
        status, _ = _run_crosshair(SIMPLE_FUNCTION)
        assert status in ("verified", "counterexample", "timeout", "error", "not_installed")

    def test_not_installed_when_crosshair_missing(self):
        """When CrossHair is not installed, returns not_installed gracefully."""
        import subprocess
        with patch("subprocess.run", side_effect=FileNotFoundError("crosshair not found")):
            status, info = _run_crosshair(SIMPLE_FUNCTION)
        assert status == "not_installed"

    def test_timeout_status_on_timeout(self):
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="crosshair", timeout=60)):
            status, info = _run_crosshair(SIMPLE_FUNCTION)
        assert status == "timeout"

    def test_returns_not_installed_when_subprocess_fails_with_file_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            status, info = _run_crosshair("def f(): return 1")
        assert status == "not_installed"

    def test_verified_on_zero_returncode(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            status, info = _run_crosshair(SIMPLE_FUNCTION)
        assert status == "verified"

    def test_counterexample_on_nonzero_returncode_with_counterexample_output(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "counterexample: x=0, y=-1"
        mock_result.stderr = ""
        with patch("subprocess.run", return_value=mock_result):
            status, info = _run_crosshair(SIMPLE_FUNCTION)
        assert status in ("counterexample", "error")


# ── _parse_crosshair_output ───────────────────────────────────────────────────


class TestParseCrosshairOutput:
    """Tests for _parse_crosshair_output helper."""

    def test_parses_counterexample_from_output(self):
        output = "counterexample for 'add': x=0, y=-5\ncheck found issue"
        result = _parse_crosshair_output(output)
        assert isinstance(result, dict)

    def test_returns_dict(self):
        result = _parse_crosshair_output("")
        assert isinstance(result, dict)

    def test_empty_output_returns_empty_dict(self):
        result = _parse_crosshair_output("")
        assert result == {} or isinstance(result, dict)

    def test_captures_raw_output(self):
        output = "some crosshair output text"
        result = _parse_crosshair_output(output)
        # At minimum, must capture the raw output string
        assert isinstance(result, dict)


# ── _call_llm (via infer_contracts with mock) ─────────────────────────────────


class TestCallLLM:
    """Tests for _call_llm through integration with infer_contracts."""

    def test_returns_empty_string_on_litellm_error(self):
        """_call_llm must never raise — return '' on any error."""
        from nightjar.inferrer import _call_llm
        with patch("litellm.completion", side_effect=Exception("API error")):
            result = _call_llm(
                messages=[{"role": "user", "content": "test"}],
                model="fake-model",
            )
        assert result == ""

    def test_returns_empty_string_on_import_error(self):
        """_call_llm must return '' when litellm not available."""
        from nightjar.inferrer import _call_llm
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "litellm":
                raise ImportError("litellm not installed")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = _call_llm(
                messages=[{"role": "user", "content": "test"}],
                model="fake-model",
            )
        assert result == ""

    def test_returns_string_on_success(self):
        """_call_llm returns the LLM response content string."""
        from nightjar.inferrer import _call_llm
        mock_response = MagicMock()
        mock_response.choices[0].message.content = '{"preconditions": [], "postconditions": []}'
        with patch("litellm.completion", return_value=mock_response):
            result = _call_llm(
                messages=[{"role": "user", "content": "test"}],
                model="claude-sonnet-4-6",
            )
        assert isinstance(result, str)
        assert len(result) > 0


# ── infer_contracts integration ───────────────────────────────────────────────


class TestInferContracts:
    """Integration tests for infer_contracts() public API."""

    def _make_llm_response(self, preconditions: list[str], postconditions: list[str]) -> MagicMock:
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "preconditions": preconditions,
            "postconditions": postconditions,
        })
        return mock_response

    def test_returns_inferred_contract(self):
        mock_resp = self._make_llm_response(["assert x >= 0"], ["assert result >= 0"])
        with patch("litellm.completion", return_value=mock_resp):
            with patch("subprocess.run", side_effect=FileNotFoundError()):
                result = infer_contracts(SIMPLE_FUNCTION, "add", "fake-model")
        assert isinstance(result, InferredContract)

    def test_function_name_set_correctly(self):
        mock_resp = self._make_llm_response([], [])
        with patch("litellm.completion", return_value=mock_resp):
            with patch("subprocess.run", side_effect=FileNotFoundError()):
                result = infer_contracts(SIMPLE_FUNCTION, "add", "fake-model")
        assert result.function_name == "add"

    def test_returns_contract_with_preconditions_list(self):
        mock_resp = self._make_llm_response(["assert x > 0"], [])
        with patch("litellm.completion", return_value=mock_resp):
            with patch("subprocess.run", side_effect=FileNotFoundError()):
                result = infer_contracts(SIMPLE_FUNCTION, "add", "fake-model")
        assert isinstance(result.preconditions, list)

    def test_returns_contract_with_postconditions_list(self):
        mock_resp = self._make_llm_response([], ["assert result >= 0"])
        with patch("litellm.completion", return_value=mock_resp):
            with patch("subprocess.run", side_effect=FileNotFoundError()):
                result = infer_contracts(SIMPLE_FUNCTION, "add", "fake-model")
        assert isinstance(result.postconditions, list)

    def test_llm_failure_returns_unverified_contract(self):
        """When LLM fails, returns an InferredContract with empty lists."""
        with patch("litellm.completion", side_effect=Exception("API error")):
            with patch("subprocess.run", side_effect=FileNotFoundError()):
                result = infer_contracts(SIMPLE_FUNCTION, "add", "fake-model")
        assert isinstance(result, InferredContract)
        assert result.verification_status in ("unverified", "counterexample", "not_installed")

    def test_crosshair_verified_sets_status(self):
        """When CrossHair passes, status is 'verified' or 'not_installed'."""
        mock_resp = self._make_llm_response(["assert x >= 0"], ["assert result >= 0"])
        mock_run = MagicMock()
        mock_run.returncode = 0
        mock_run.stdout = ""
        mock_run.stderr = ""
        with patch("litellm.completion", return_value=mock_resp):
            with patch("subprocess.run", return_value=mock_run):
                result = infer_contracts(SIMPLE_FUNCTION, "add", "fake-model")
        assert result.verification_status in ("verified", "not_installed", "unverified")

    def test_use_crosshair_false_skips_subprocess(self):
        """When use_crosshair=False, no subprocess.run is called."""
        mock_resp = self._make_llm_response(["assert x >= 0"], [])
        with patch("litellm.completion", return_value=mock_resp):
            with patch("subprocess.run") as mock_sub:
                result = infer_contracts(
                    SIMPLE_FUNCTION, "add", "fake-model", use_crosshair=False
                )
        mock_sub.assert_not_called()
        assert isinstance(result, InferredContract)

    def test_iterations_used_is_nonnegative_int(self):
        mock_resp = self._make_llm_response([], [])
        with patch("litellm.completion", return_value=mock_resp):
            with patch("subprocess.run", side_effect=FileNotFoundError()):
                result = infer_contracts(SIMPLE_FUNCTION, "add", "fake-model")
        assert isinstance(result.iterations_used, int)
        assert result.iterations_used >= 0

    def test_max_iterations_respected(self):
        """LLM is called at most max_iterations times."""
        mock_resp = self._make_llm_response([], [])
        call_count = {"n": 0}

        def counting_completion(*args, **kwargs):
            call_count["n"] += 1
            return mock_resp

        mock_run = MagicMock()
        mock_run.returncode = 1
        mock_run.stdout = "counterexample: x=-1"
        mock_run.stderr = ""
        with patch("litellm.completion", side_effect=counting_completion):
            with patch("subprocess.run", return_value=mock_run):
                result = infer_contracts(
                    SIMPLE_FUNCTION, "add", "fake-model", max_iterations=3
                )
        # LLM called at most max_iterations+1 times (1 generate + up to N repairs)
        assert call_count["n"] <= 4  # generous bound: 1 generate + 3 repairs

    def test_with_retrieved_examples_passed_through(self):
        """retrieved_examples are used in prompt building."""
        mock_resp = self._make_llm_response(["assert age >= 0"], [])
        with patch("litellm.completion", return_value=mock_resp) as mock_llm:
            with patch("subprocess.run", side_effect=FileNotFoundError()):
                result = infer_contracts(
                    AGE_FUNCTION,
                    "validate_age",
                    "fake-model",
                    retrieved_examples=["age >= 0", "age <= 150"],
                )
        assert isinstance(result, InferredContract)
        # LLM must have been called
        mock_llm.assert_called()

    def test_function_not_found_returns_contract(self):
        """If function_name not in source, still returns InferredContract (for whole source)."""
        mock_resp = self._make_llm_response([], [])
        with patch("litellm.completion", return_value=mock_resp):
            with patch("subprocess.run", side_effect=FileNotFoundError()):
                result = infer_contracts(SIMPLE_FUNCTION, "nonexistent", "fake-model")
        assert isinstance(result, InferredContract)

    def test_confidence_is_float_between_0_and_1(self):
        mock_resp = self._make_llm_response(["assert x >= 0"], ["assert result >= 0"])
        with patch("litellm.completion", return_value=mock_resp):
            with patch("subprocess.run", side_effect=FileNotFoundError()):
                result = infer_contracts(SIMPLE_FUNCTION, "add", "fake-model")
        assert 0.0 <= result.confidence <= 1.0

    def test_infer_contracts_never_raises(self):
        """infer_contracts must never propagate exceptions to caller."""
        with patch("litellm.completion", side_effect=RuntimeError("catastrophic failure")):
            with patch("subprocess.run", side_effect=OSError("also broken")):
                # Should not raise
                result = infer_contracts(SIMPLE_FUNCTION, "add", "fake-model")
        assert isinstance(result, InferredContract)
