"""LLM-powered contract inference with CrossHair verification loop.

Implements the generate → CrossHair verify → repair loop pattern for inferring
Python function contracts (preconditions + postconditions as assert expressions).

References:
- [REF-NEW-08] NL2Contract: "Beyond Postconditions: Can LLMs infer Formal Contracts?"
  URL: https://arxiv.org/abs/2510.12702
  Key: Prompt template, CrossHair soundness, mutation completeness
- [REF-NEW-09] "Automatic Generation of Formal Specification and Verification Annotations"
  URL: https://arxiv.org/abs/2601.12845
  Key: 98.2%/8 iterations, multimodel approach, repair prompts
- [REF-NEW-11] Clover: "Closed-Loop Verifiable Code Generation"
  URL: https://arxiv.org/abs/2310.17807
  Key: GEN_SPEC_FROM_DOC prompt pattern, consistency checker
- [REF-T09] CrossHair: symbolic execution for Python
- [REF-T16] litellm for model-agnostic LLM calls
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass
from typing import Any, Optional


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class InferredContract:
    """A contract inferred for a Python function.

    Preconditions and postconditions are Python assert expression strings.
    Postconditions use the variable name 'result' for the function return value.

    verification_status values:
      "verified"       — CrossHair symbolically confirmed all contracts
      "unverified"     — CrossHair not run (use_crosshair=False) or LLM produced nothing
      "counterexample" — CrossHair found a counterexample
      "timeout"        — CrossHair timed out during verification
      "not_installed"  — CrossHair binary not found
    """

    function_name: str
    preconditions: list[str]
    postconditions: list[str]
    confidence: float
    verification_status: str
    counterexample: Optional[dict[str, Any]]
    iterations_used: int


# ── Public API ─────────────────────────────────────────────────────────────────


def infer_contracts(
    source: str,
    function_name: str,
    model: str,
    max_iterations: int = 5,
    use_crosshair: bool = True,
    retrieved_examples: Optional[list[str]] = None,
) -> InferredContract:
    """Infer contracts for a Python function via generate → verify → repair loop.

    Pattern from NL2Contract (arxiv:2510.12702) and the 98.2% paper
    (arxiv:2601.12845): LLM generates candidate contracts, CrossHair
    symbolically verifies them, and on failure the error is fed back to
    the LLM for repair. Repeats up to max_iterations times.

    This function never raises. All errors are caught and returned as an
    InferredContract with appropriate verification_status.

    Args:
        source:            Python source code string containing the function.
        function_name:     Name of the function to infer contracts for.
        model:             litellm model string (e.g. "claude-sonnet-4-6").
                           Empty string or None uses NIGHTJAR_MODEL env var.
        max_iterations:    Maximum repair iterations (default 5, per §7.9 of
                           research: success rate drops sharply after iter 3).
        use_crosshair:     If False, skip CrossHair verification (fast mode).
        retrieved_examples: Optional few-shot example expressions from
                           contract_library.retrieve_examples(), as strings
                           without the "assert " prefix.

    Returns:
        InferredContract with generated/verified contracts and metadata.
        Always returns an InferredContract — never raises.
    """
    try:
        resolved_model = _resolve_model(model or "")
        examples = retrieved_examples or []

        # Extract the target function source for focused LLM prompting.
        # Fall back to full source if function not found (e.g. function_name="").
        func_source = _get_function_source(source, function_name)
        if not func_source:
            func_source = source

        # ── Iteration 0: Generate ─────────────────────────────────────────────
        messages = _build_generate_prompt(func_source, examples)
        raw_response = _call_llm(messages, resolved_model)
        preconditions, postconditions = _parse_llm_contracts(raw_response)

        if not preconditions and not postconditions:
            # LLM produced nothing usable — return unverified empty contract
            return InferredContract(
                function_name=function_name,
                preconditions=[],
                postconditions=[],
                confidence=0.0,
                verification_status="unverified",
                counterexample=None,
                iterations_used=0,
            )

        # ── Skip CrossHair if disabled ────────────────────────────────────────
        if not use_crosshair:
            return InferredContract(
                function_name=function_name,
                preconditions=preconditions,
                postconditions=postconditions,
                confidence=0.7,
                verification_status="unverified",
                counterexample=None,
                iterations_used=1,
            )

        # ── Generate → verify → repair loop ──────────────────────────────────
        iteration = 1
        last_status = "unverified"
        last_info: dict[str, Any] = {}

        for _ in range(max(1, max_iterations)):
            crosshair_source = _build_crosshair_source(
                func_source, preconditions, postconditions
            )
            status, info = _run_crosshair(crosshair_source)
            last_status = status
            last_info = info

            if status == "verified":
                return InferredContract(
                    function_name=function_name,
                    preconditions=preconditions,
                    postconditions=postconditions,
                    confidence=0.95,
                    verification_status="verified",
                    counterexample=None,
                    iterations_used=iteration,
                )

            if status in ("not_installed", "timeout", "error"):
                # Cannot verify — return what we have with appropriate status
                return InferredContract(
                    function_name=function_name,
                    preconditions=preconditions,
                    postconditions=postconditions,
                    confidence=0.5,
                    verification_status=status,
                    counterexample=None,
                    iterations_used=iteration,
                )

            # status == "counterexample" → repair
            if iteration >= max_iterations:
                break

            all_contracts = preconditions + postconditions
            crosshair_output = info.get("output", "")
            repair_messages = _build_repair_prompt(func_source, all_contracts, crosshair_output)
            repair_response = _call_llm(repair_messages, resolved_model)
            new_pre, new_post = _parse_llm_contracts(repair_response)

            if new_pre or new_post:
                preconditions = new_pre
                postconditions = new_post

            iteration += 1

        # Exhausted iterations with counterexample
        counterexample = _parse_crosshair_output(last_info.get("output", ""))
        return InferredContract(
            function_name=function_name,
            preconditions=preconditions,
            postconditions=postconditions,
            confidence=0.3,
            verification_status=last_status,
            counterexample=counterexample if counterexample else None,
            iterations_used=iteration,
        )

    except Exception:
        # Absolute safety net — infer_contracts must never raise
        return InferredContract(
            function_name=function_name,
            preconditions=[],
            postconditions=[],
            confidence=0.0,
            verification_status="unverified",
            counterexample=None,
            iterations_used=0,
        )


# ── Private helpers ───────────────────────────────────────────────────────────


def _resolve_model(model: str) -> str:
    """Return model string, falling back to NIGHTJAR_MODEL env var or default.

    Args:
        model: Caller-supplied model string. Empty string triggers fallback.

    Returns:
        Non-empty model string. Never returns empty string.
    """
    if model:
        return model
    env_model = os.environ.get("NIGHTJAR_MODEL", "")
    if env_model:
        return env_model
    return "claude-sonnet-4-6"


def _get_function_source(source: str, function_name: str) -> str:
    """Extract source text of a named function from a Python source string.

    Uses the AST to locate the function definition and returns the lines
    of source code that make up that function.

    Args:
        source:        Full Python source code string.
        function_name: Name of the function to extract.

    Returns:
        Source text of the function, or "" if not found.
    """
    if not function_name or not source:
        return ""

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ""

    lines = source.splitlines(keepends=True)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                start = node.lineno - 1
                # end_lineno is available in Python 3.8+
                end = getattr(node, "end_lineno", None)
                if end is not None:
                    func_lines = lines[start:end]
                else:
                    # Fallback: collect until next non-indented line
                    func_lines = [lines[start]]
                    for line in lines[start + 1:]:
                        if line.strip() and not line[0].isspace():
                            break
                        func_lines.append(line)
                return "".join(func_lines)

    return ""


def _build_generate_prompt(
    function_source: str,
    retrieved_examples: list[str],
) -> list[dict[str, str]]:
    """Build the LLM messages for initial contract generation.

    Follows the NL2Contract prompt pattern (arxiv:2510.12702):
    system prompt describes the task and output format; user prompt
    provides the function source and few-shot examples.

    Args:
        function_source:    Python source of the function to analyze.
        retrieved_examples: Few-shot example expressions (without "assert " prefix)
                            from contract_library.retrieve_examples().

    Returns:
        List of {"role": str, "content": str} message dicts for litellm.
    """
    system = textwrap.dedent("""\
        You are a software contract expert analyzing Python functions.
        Given a Python function, generate executable preconditions and
        postconditions as Python assert statements.

        Rules:
        - Each contract is a single Python assert statement
        - Preconditions: assert <condition about parameters>, checked at function entry
        - Postconditions: assert <condition about 'result'>, where 'result' is the return value
        - Be specific: prefer 'age >= 0 and age <= 150' over 'isinstance(age, int)'
        - Infer domain constraints from parameter names, type hints, and docstrings
        - Do NOT generate tautologies like 'assert True' or 'assert result == result'
        - Do NOT generate contracts that are trivially satisfied by the type system

        Return ONLY valid JSON with this exact structure:
        {"preconditions": ["assert ...", ...], "postconditions": ["assert ...", ...]}
    """)

    examples_section = ""
    if retrieved_examples:
        examples_section = "\n\nSimilar contract examples (for reference):\n" + "\n".join(
            f"- {ex}" for ex in retrieved_examples
        )

    user = (
        f"Function to analyze:\n```python\n{function_source}\n```"
        f"{examples_section}\n\n"
        "Generate precondition and postcondition contracts as JSON."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _build_repair_prompt(
    source: str,
    failed_contracts: list[str],
    crosshair_output: str,
) -> list[dict[str, str]]:
    """Build the LLM messages for contract repair after CrossHair failure.

    Pattern from the 98.2% paper (arxiv:2601.12845): feed the counterexample
    back to the LLM with instruction to fix the contract.

    Args:
        source:            Python source of the function.
        failed_contracts:  List of contract assert strings that failed verification.
        crosshair_output:  Raw CrossHair output including counterexample details.

    Returns:
        List of {"role": str, "content": str} message dicts for litellm.
    """
    system = textwrap.dedent("""\
        You are a software contract expert. A contract you generated for a
        Python function failed symbolic verification by CrossHair.

        You will receive:
        1. The function source code
        2. The contracts that failed
        3. The CrossHair output (possibly including a counterexample)

        Your task: generate corrected contracts that:
        - Are satisfied by valid inputs
        - Correctly capture the function's behavior
        - Avoid the failure shown in the CrossHair output

        Return ONLY valid JSON:
        {"preconditions": ["assert ...", ...], "postconditions": ["assert ...", ...]}
    """)

    contracts_block = "\n".join(failed_contracts) if failed_contracts else "(none)"
    user = (
        f"Function:\n```python\n{source}\n```\n\n"
        f"Contracts that failed verification:\n{contracts_block}\n\n"
        f"CrossHair output:\n{crosshair_output or '(no output)'}\n\n"
        "Generate corrected contracts as JSON."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _call_llm(
    messages: list[dict[str, str]],
    model: str,
) -> str:
    """Call litellm with the given messages and return the response content.

    Per project convention (scanner.py enhance_with_llm): this function
    NEVER raises. Returns "" on any error.

    Args:
        messages: List of role/content message dicts.
        model:    litellm model string.

    Returns:
        Response content string, or "" on any error (including no API key,
        network failure, import error, or any other exception).
    """
    try:
        import litellm

        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return ""


def _parse_llm_contracts(raw: str) -> tuple[list[str], list[str]]:
    """Parse LLM response into (preconditions, postconditions) lists.

    Handles:
    - Clean JSON responses
    - JSON wrapped in markdown code fences (```json ... ```)
    - Partial JSON with only one key present
    - Invalid JSON (returns empty lists)

    Args:
        raw: Raw LLM response string.

    Returns:
        Tuple of (preconditions, postconditions) — each a list of assert
        expression strings. Returns ([], []) on any parse failure.
    """
    if not raw or not raw.strip():
        return [], []

    text = raw.strip()

    # Strip markdown code fences if present
    code_fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if code_fence:
        text = code_fence.group(1)
    else:
        # Try to find the first {...} block in the response
        brace_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if brace_match:
            text = brace_match.group(0)

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return [], []

    if not isinstance(data, dict):
        return [], []

    def _clean_list(raw_list: Any) -> list[str]:
        if not isinstance(raw_list, list):
            return []
        return [s for s in raw_list if isinstance(s, str) and s.strip()]

    preconditions = _clean_list(data.get("preconditions", []))
    postconditions = _clean_list(data.get("postconditions", []))
    return preconditions, postconditions


def _build_crosshair_source(
    function_source: str,
    preconditions: list[str],
    postconditions: list[str],
) -> str:
    """Build a Python source string with contracts embedded for CrossHair.

    Embeds preconditions at the start of the function body and postconditions
    just before the return statement (or at the end using a wrapper approach).

    For CrossHair compatibility, we use the inline assertion approach:
    preconditions as assert statements at the top of the function body,
    postconditions checked by wrapping the return value.

    Args:
        function_source: Source of the function (def ... block).
        preconditions:   List of "assert <expr>" strings for input validation.
        postconditions:  List of "assert <expr>" strings using 'result'.

    Returns:
        Valid Python source string with contracts embedded.
        Returns function_source unchanged if embedding fails.
    """
    if not preconditions and not postconditions:
        return function_source

    try:
        tree = ast.parse(function_source)
    except SyntaxError:
        return function_source

    # Find the function def node
    func_node = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_node = node
            break

    if func_node is None:
        return function_source

    # Build the modified source by inserting assertions
    # Strategy: reconstruct the function with injected assertions
    lines = function_source.splitlines(keepends=True)

    # Find the function signature end (first line of body)
    # The body starts at func_node.body[0].lineno
    body_start_line = func_node.body[0].lineno - 1  # 0-indexed
    body_start_col = func_node.body[0].col_offset

    indent = " " * body_start_col

    pre_lines = [f"{indent}{stmt}\n" for stmt in preconditions]

    if postconditions:
        # Wrap return values to check postconditions
        # Replace return statements with result = ...; check; return result
        post_checks = "\n".join(f"{indent}    {stmt}" for stmt in postconditions)
        # For simplicity, use a wrapper that captures result and checks postconditions
        # Insert preconditions then wrap with a nested helper approach
        # Simple approach: insert pre-assertions at top, post-assertions checked inline

        # Reconstruct lines with pre-assertions inserted before first body line
        output_lines = list(lines[:body_start_line]) + pre_lines

        # Process remaining body lines to intercept return statements
        for line in lines[body_start_line:]:
            stripped = line.lstrip()
            if stripped.startswith("return "):
                # Extract return expression
                ret_expr = stripped[len("return "):].rstrip("\n")
                current_indent = line[: len(line) - len(line.lstrip())]
                output_lines.append(f"{current_indent}result = {ret_expr}\n")
                for stmt in postconditions:
                    output_lines.append(f"{current_indent}{stmt}\n")
                output_lines.append(f"{current_indent}return result\n")
            else:
                output_lines.append(line)
        return "".join(output_lines)
    else:
        # Only preconditions — insert before first body line
        output_lines = list(lines[:body_start_line]) + pre_lines + list(lines[body_start_line:])
        return "".join(output_lines)


def _run_crosshair(source: str, timeout: int = 60) -> tuple[str, dict[str, Any]]:
    """Run CrossHair symbolically on the given source string.

    Writes source to a temp file, runs CrossHair as a subprocess, and
    returns the verification result.

    Args:
        source:  Python source code to verify (complete function definition).
        timeout: Subprocess timeout in seconds (default 60).

    Returns:
        Tuple of (status, info) where:
          status: "verified" | "counterexample" | "timeout" | "error" | "not_installed"
          info:   Dict with at least "output" key (raw CrossHair stdout+stderr).
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(source)
            tmp_path = f.name

        result = subprocess.run(
            [sys.executable, "-m", "crosshair", "check", tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = (result.stdout or "") + (result.stderr or "")

        if result.returncode == 0:
            return "verified", {"output": output}

        # Non-zero return: check if it's a counterexample
        output_lower = output.lower()
        if "counterexample" in output_lower or "error:" in output_lower:
            return "counterexample", {"output": output}

        return "error", {"output": output}

    except subprocess.TimeoutExpired:
        return "timeout", {"output": "CrossHair timed out"}
    except FileNotFoundError:
        return "not_installed", {"output": "CrossHair not installed"}
    except Exception as e:
        return "error", {"output": str(e)}
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _parse_crosshair_output(output: str) -> dict[str, Any]:
    """Parse CrossHair output to extract counterexample information.

    CrossHair counterexample output typically looks like:
      <filename>:<line>: error: counterexample for 'func': arg=value, ...

    Args:
        output: Raw CrossHair stdout + stderr string.

    Returns:
        Dict with extracted information. May contain "raw" key with the
        original output. Returns {} for empty input.
    """
    if not output or not output.strip():
        return {}

    result: dict[str, Any] = {"raw": output.strip()}

    # Try to extract key=value pairs from counterexample lines
    # CrossHair format: "counterexample for 'func': x=0, y=-1"
    ce_match = re.search(
        r"counterexample[^:]*:\s*([^\n]+)", output, re.IGNORECASE
    )
    if ce_match:
        ce_text = ce_match.group(1).strip()
        result["counterexample_text"] = ce_text

        # Try to parse key=value pairs
        pairs: dict[str, str] = {}
        for pair in re.findall(r"(\w+)\s*=\s*([^,\n]+)", ce_text):
            key, val = pair
            pairs[key.strip()] = val.strip()
        if pairs:
            result["inputs"] = pairs

    return result
