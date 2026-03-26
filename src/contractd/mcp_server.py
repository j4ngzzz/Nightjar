"""MCP server for CARD — exposes verification tools to AI coding assistants.

Protocol: [REF-T18] Model Context Protocol.
Tools defined in docs/ARCHITECTURE.md Section 7:
  1. verify_contract — run verification pipeline on generated code
  2. get_violations — get detailed violation report from last run
  3. suggest_fix — get LLM-suggested fix for a specific violation

BEFORE MODIFYING: Read docs/ARCHITECTURE.md Section 7 and [REF-T18] MCP SDK docs.
"""

import json
import os
from typing import Any

import litellm
from mcp.server.fastmcp import FastMCP

from .types import VerifyResult, StageResult, VerifyStatus


# -- In-memory violation store --
# Maps spec_path → list of violation dicts from the last verification run.
# This enables get_violations and suggest_fix to reference prior results.
_violation_store: dict[str, list[dict[str, Any]]] = {}

# Maps spec_path → last VerifyResult for reference
_result_store: dict[str, VerifyResult] = {}


# -- Internal helpers --


async def _run_verification(
    spec_path: str,
    code_path: str,
    stages: str = "all",
) -> VerifyResult:
    """Run the verification pipeline.

    This is a placeholder that will be replaced with the actual verifier
    once src/contractd/verifier.py is implemented by Builder 5 (T7).

    Args:
        spec_path: Path to .card.md spec file.
        code_path: Path to generated code file.
        stages: Which stages to run — "all", "fast" (0-3), or "formal" (4 only).

    Returns:
        VerifyResult from the verification pipeline.
    """
    # TODO: Import and call verifier.run_pipeline() once T7 is complete.
    # For now, this function is always mocked in tests.
    raise NotImplementedError(
        "Verification pipeline not yet integrated. "
        "Awaiting T7 (verifier.py) completion."
    )


def _extract_violations(result: VerifyResult) -> list[dict[str, Any]]:
    """Extract violation details from a VerifyResult.

    Collects all errors from failed stages into a flat list of
    violation dicts with stage, file, line, message, and counterexample.
    """
    violations: list[dict[str, Any]] = []
    for stage_result in result.stages:
        if stage_result.status == VerifyStatus.FAIL:
            for error in stage_result.errors:
                violation = {
                    "stage": stage_result.name,
                    "stage_num": stage_result.stage,
                    "file": error.get("file", ""),
                    "line": error.get("line", 0),
                    "message": error.get("message", ""),
                    "type": error.get("type", "unknown"),
                }
                if stage_result.counterexample:
                    violation["counterexample"] = stage_result.counterexample
                violations.append(violation)
    return violations


def _format_verify_response(result: VerifyResult) -> str:
    """Format a VerifyResult as JSON for MCP tool response.

    Response schema from ARCHITECTURE.md Section 7:
    { verified: boolean, stages: [...], errors: [...], duration_ms: number }
    """
    stages_data = []
    for sr in result.stages:
        stages_data.append({
            "stage": sr.stage,
            "name": sr.name,
            "status": sr.status.value,
            "duration_ms": sr.duration_ms,
        })

    errors = []
    for sr in result.stages:
        if sr.status == VerifyStatus.FAIL:
            for err in sr.errors:
                errors.append({
                    "stage": sr.name,
                    **err,
                })

    return json.dumps({
        "verified": result.verified,
        "stages": stages_data,
        "errors": errors,
        "duration_ms": result.total_duration_ms,
        "retry_count": result.retry_count,
    })


# -- Tool handlers --


async def handle_verify_contract(
    spec_path: str,
    code_path: str,
    stages: str = "all",
) -> str:
    """Run CARD verification pipeline on generated code against a .card.md spec.

    MCP tool 1 of 3 — see ARCHITECTURE.md Section 7.

    Args:
        spec_path: Path to .card.md file.
        code_path: Path to generated code.
        stages: Which stages to run — "all", "fast" (stages 0-3), "formal" (stage 4 only).

    Returns:
        JSON string with { verified, stages, errors, duration_ms }.
    """
    result = await _run_verification(spec_path, code_path, stages)

    # Store violations for get_violations and suggest_fix
    violations = _extract_violations(result)
    _violation_store[spec_path] = violations
    _result_store[spec_path] = result

    return _format_verify_response(result)


async def handle_get_violations(spec_path: str) -> str:
    """Get detailed violation report from last verification run.

    MCP tool 2 of 3 — see ARCHITECTURE.md Section 7.

    Args:
        spec_path: Path to .card.md file.

    Returns:
        JSON string with { violations: [{ stage, file, line, message, counterexample }] }.
    """
    violations = _violation_store.get(spec_path, [])
    return json.dumps({"violations": violations})


async def handle_suggest_fix(
    spec_path: str,
    violation_id: str,
) -> str:
    """Get LLM-suggested fix for a specific verification violation.

    MCP tool 3 of 3 — see ARCHITECTURE.md Section 7.
    Uses litellm [REF-T16] for the LLM call.

    Args:
        spec_path: Path to .card.md file.
        violation_id: Index of the violation in the violations list.

    Returns:
        JSON string with { suggested_code, explanation, confidence }.
    """
    violations = _violation_store.get(spec_path, [])

    try:
        idx = int(violation_id)
        if idx < 0 or idx >= len(violations):
            raise IndexError
        violation = violations[idx]
    except (ValueError, IndexError):
        return json.dumps({
            "error": f"Invalid violation_id '{violation_id}'. "
                     f"Available: 0-{len(violations) - 1}" if violations
                     else f"No violations stored for '{spec_path}'."
        })

    model = os.environ.get("CARD_MODEL", "claude-sonnet-4-6")

    prompt = (
        f"A verification violation was found:\n\n"
        f"Stage: {violation.get('stage', 'unknown')}\n"
        f"File: {violation.get('file', 'unknown')}\n"
        f"Line: {violation.get('line', '?')}\n"
        f"Message: {violation.get('message', 'unknown')}\n"
    )
    if "counterexample" in violation:
        prompt += f"Counterexample: {json.dumps(violation['counterexample'])}\n"
    prompt += (
        "\nSuggest a code fix that resolves this violation. "
        "Provide the fix as code and a brief explanation."
    )

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": (
                "You are a code repair assistant for the CARD verification system. "
                "Given a verification violation, suggest a minimal code fix."
            )},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=2048,
    )

    suggestion = response.choices[0].message.content or ""

    return json.dumps({
        "suggested_code": suggestion,
        "explanation": f"Fix for {violation.get('type', 'unknown')} violation "
                       f"at {violation.get('file', '?')}:{violation.get('line', '?')}",
        "confidence": 0.7,
    })


# -- MCP Server factory --


def create_mcp_server() -> FastMCP:
    """Create and configure the CARD MCP server with 3 tools.

    Tools follow the schemas defined in ARCHITECTURE.md Section 7 [REF-T18].

    Returns:
        Configured FastMCP server instance ready to run.
    """
    mcp = FastMCP("contractd")

    @mcp.tool()
    async def verify_contract(
        spec_path: str,
        code_path: str,
        stages: str = "all",
    ) -> str:
        """Run CARD verification pipeline on generated code against a .card.md spec.

        Args:
            spec_path: Path to .card.md file.
            code_path: Path to generated code.
            stages: Which stages — "all", "fast" (0-3), or "formal" (4 only).
        """
        return await handle_verify_contract(spec_path, code_path, stages)

    @mcp.tool()
    async def get_violations(spec_path: str) -> str:
        """Get detailed violation report from last verification run.

        Args:
            spec_path: Path to .card.md file.
        """
        return await handle_get_violations(spec_path)

    @mcp.tool()
    async def suggest_fix(spec_path: str, violation_id: str) -> str:
        """Get LLM-suggested fix for a specific verification violation.

        Args:
            spec_path: Path to .card.md file.
            violation_id: Index of the violation to fix.
        """
        return await handle_suggest_fix(spec_path, violation_id)

    return mcp


# -- Entry point --


if __name__ == "__main__":
    server = create_mcp_server()
    server.run(transport="stdio")
