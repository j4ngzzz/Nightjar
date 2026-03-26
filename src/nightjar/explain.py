"""Explanation module for verification failures.

Analyzes .card/verify.json reports and produces human-readable
explanations of what failed, why, and how to fix it.

Extended with LLM-enhanced explanations via litellm (Scout 7 N2):
  explain_with_llm() transforms cryptic Dafny SMT errors into:
  - What failed (plain English)
  - The counterexample input that triggered the failure
  - Which spec line was violated
  - Suggested fix

References:
- [REF-P06] DafnyPro structured errors — error formatting approach
- [REF-T16] litellm — all LLM calls go through litellm
- [REF-T17] Click CLI framework — integrates with CLI explain command
- Scout 7 N2 — natural language explanation of WHY verification failed
- ARCHITECTURE.md Section 8 — CLI design
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import litellm


@dataclass
class ExplainOutput:
    """Structured explanation of a verification failure.

    Produced by explain_failure() and consumed by format_explanation()
    or the CLI explain command [REF-T17].

    U1.3 extension: root_cause field added for LP dual diagnosis output.
    When populated, format_explanation() includes a root-cause section.
    """

    failed_stage: int
    stage_name: str
    invariant_violated: str
    error_messages: list[str]
    counterexamples: list[dict]
    suggested_fix: str
    all_stages_summary: list[dict]
    root_cause: str = ""  # LP dual diagnosis root cause [REF-NEW-09]


# ── Stage-specific fix suggestions ───────────────────────
# Heuristic suggestions keyed by stage name. Based on the structured
# error approach from [REF-P06] DafnyPro.

_FIX_SUGGESTIONS: dict[str, str] = {
    "preflight": (
        "Check your .card.md spec for missing required fields. "
        "Ensure the YAML frontmatter has card-version, id, title, status, "
        "module, contract, and invariants sections."
    ),
    "deps": (
        "Run 'nightjar lock' to regenerate deps.lock. "
        "Ensure all dependencies are pinned with SHA hashes [REF-C08]. "
        "Run 'pip-audit' to check for known vulnerabilities [REF-T06]."
    ),
    "schema": (
        "Validate your contract inputs/outputs against the Pydantic schema [REF-T08]. "
        "Check that all required fields are present and types match the spec."
    ),
    "pbt": (
        "The property-based test found a counterexample that violates an invariant. "
        "Review the counterexample values and add input validation or fix the "
        "implementation logic. Consider tightening preconditions in the .card.md spec."
    ),
    "formal": (
        "Dafny formal verification failed. Review the postconditions and loop "
        "invariants in the generated Dafny code. The LLM repair loop [REF-C02] "
        "may be able to fix this automatically — try 'nightjar retry'."
    ),
}

_TIMEOUT_FIX = (
    "Verification timed out. Try increasing the timeout in nightjar.toml "
    "(verification_timeout setting) or simplify the invariants. For Dafny "
    "timeouts, consider breaking the proof into smaller lemmas."
)


def load_report(contract_path: str) -> Optional[dict]:
    """Load the last verification report from .card/verify.json.

    Searches for verify.json in the same directory as the contract file,
    then falls back to .card/verify.json in the current working directory.

    Args:
        contract_path: Path to the .card.md spec file.

    Returns:
        Parsed verification report dict, or None if no report exists or
        if the JSON is malformed / unreadable (Reviewer 9: fix missing try/except).
    """
    spec_dir = Path(contract_path).parent
    report_path = spec_dir / "verify.json"

    if report_path.exists():
        try:
            with open(report_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    # Fallback: check .card/verify.json relative to CWD
    fallback_path = Path(".card") / "verify.json"
    if fallback_path.exists():
        try:
            with open(fallback_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    return None


def _build_stages_summary(stages: list[dict]) -> list[dict]:
    """Build a compact summary of all stages in the report.

    Args:
        stages: List of stage dicts from the verification report.

    Returns:
        List of dicts with stage, name, and status keys.
    """
    return [
        {
            "stage": s.get("stage", -1),
            "name": s.get("name", "unknown"),
            "status": s.get("status", "unknown"),
        }
        for s in stages
    ]


def _extract_invariant(error_messages: list[str]) -> str:
    """Extract the invariant description from error messages.

    Looks for patterns like 'Property violated: X' or 'postcondition: X'
    to identify which invariant was broken.

    Args:
        error_messages: List of error message strings.

    Returns:
        The extracted invariant string, or a generic description.
    """
    for msg in error_messages:
        # Pattern: "Property violated: <invariant>"
        if "Property violated:" in msg:
            return msg.split("Property violated:", 1)[1].strip()
        # Pattern: "postcondition might not hold" (Dafny)
        if "postcondition" in msg.lower():
            return msg
        # Pattern: "Assertion violation"
        if "assertion" in msg.lower():
            return msg
        # Pattern: "Schema validation failed: <details>"
        if "Schema validation failed:" in msg:
            return msg.split("Schema validation failed:", 1)[1].strip()

    # Fallback: use first error message if available
    if error_messages:
        return error_messages[0]
    return ""


def _get_suggested_fix(stage_name: str, status: str) -> str:
    """Get a heuristic fix suggestion based on stage and status.

    Uses structured error patterns from [REF-P06] DafnyPro to provide
    actionable suggestions for each failure type.

    Args:
        stage_name: Name of the failed stage (preflight, deps, schema, pbt, formal).
        status: Status of the stage (fail, timeout, etc.).

    Returns:
        A human-readable fix suggestion string.
    """
    if status == "timeout":
        return _TIMEOUT_FIX

    return _FIX_SUGGESTIONS.get(stage_name, (
        f"Stage '{stage_name}' failed. Review the error messages above "
        "and check the .card.md spec for issues."
    ))


def explain_failure(report: dict) -> ExplainOutput:
    """Analyze a verification failure report and produce a structured explanation.

    Finds the first failed stage (status == 'fail' or 'timeout'), extracts
    error details, counterexamples, and generates a heuristic fix suggestion
    based on the stage type.

    If the report shows all stages passed, returns an ExplainOutput with
    failed_stage == -1 indicating no failure.

    Args:
        report: Parsed verification report dict from .card/verify.json.

    Returns:
        ExplainOutput with failure analysis and fix suggestion.

    References:
        [REF-P06] DafnyPro structured errors — error categorization approach
    """
    stages = report.get("stages", [])
    all_stages_summary = _build_stages_summary(stages)

    # Find the first failed or timed-out stage
    failed_stage_data: Optional[dict] = None
    for stage_data in stages:
        status = stage_data.get("status", "unknown")
        if status in ("fail", "timeout"):
            failed_stage_data = stage_data
            break

    # No failure found — report passed
    if failed_stage_data is None:
        return ExplainOutput(
            failed_stage=-1,
            stage_name="",
            invariant_violated="",
            error_messages=[],
            counterexamples=[],
            suggested_fix="",
            all_stages_summary=all_stages_summary,
        )

    stage_num: int = failed_stage_data.get("stage", -1)
    stage_name: str = failed_stage_data.get("name", "unknown")
    stage_status: str = failed_stage_data.get("status", "fail")
    errors: list[dict] = failed_stage_data.get("errors", [])

    # Extract error messages
    error_messages: list[str] = [
        e.get("message", "unknown error") for e in errors
    ]

    # Extract counterexamples
    counterexamples: list[dict] = [
        e["counterexample"] for e in errors if "counterexample" in e
    ]

    # Identify the violated invariant
    invariant_violated = _extract_invariant(error_messages)

    # Generate fix suggestion
    suggested_fix = _get_suggested_fix(stage_name, stage_status)

    return ExplainOutput(
        failed_stage=stage_num,
        stage_name=stage_name,
        invariant_violated=invariant_violated,
        error_messages=error_messages,
        counterexamples=counterexamples,
        suggested_fix=suggested_fix,
        all_stages_summary=all_stages_summary,
    )


def format_explanation(explanation: ExplainOutput) -> str:
    """Format an ExplainOutput as plain text for terminal display.

    Produces a human-readable multi-section report. Rich/color formatting
    will be added later via display.py; this function returns plain text.

    Args:
        explanation: ExplainOutput from explain_failure().

    Returns:
        Multi-line plain text string.

    References:
        [REF-P06] DafnyPro structured errors — formatting approach
        [REF-T17] Click CLI framework — output conventions
    """
    lines: list[str] = []

    # Handle passing reports
    if explanation.failed_stage == -1:
        lines.append("All verification stages passed. No failures to explain.")
        return "\n".join(lines)

    # Header
    lines.append("=" * 60)
    lines.append("VERIFICATION FAILURE EXPLANATION")
    lines.append("=" * 60)
    lines.append("")

    # Failed stage
    lines.append(
        f"Failed Stage: Stage {explanation.failed_stage} ({explanation.stage_name})"
    )
    lines.append("")

    # Invariant violated
    if explanation.invariant_violated:
        lines.append(f"Invariant Violated: {explanation.invariant_violated}")
        lines.append("")

    # Error messages
    if explanation.error_messages:
        lines.append("Errors:")
        for msg in explanation.error_messages:
            lines.append(f"  - {msg}")
        lines.append("")

    # Counterexamples
    if explanation.counterexamples:
        lines.append("Counterexamples:")
        for i, ce in enumerate(explanation.counterexamples, 1):
            lines.append(f"  [{i}] {ce}")
        lines.append("")

    # LP dual root-cause [U1.3, REF-NEW-09]
    if explanation.root_cause:
        lines.append(f"Root Cause (LP diagnosis): {explanation.root_cause}")
        lines.append("")

    # Suggested fix
    if explanation.suggested_fix:
        lines.append(f"Suggested Fix: {explanation.suggested_fix}")
        lines.append("")

    # Stages summary
    lines.append("-" * 60)
    lines.append("Stages Summary:")
    for entry in explanation.all_stages_summary:
        stage_num = entry.get("stage", "?")
        name = entry.get("name", "unknown")
        status = entry.get("status", "unknown").upper()
        marker = "PASS" if status == "PASS" else status
        lines.append(f"  Stage {stage_num} ({name}): {marker}")
    lines.append("-" * 60)

    return "\n".join(lines)


# ── LLM-enhanced explanation (Scout 7 N2) ─────────────────


_DEFAULT_MODEL = "claude-sonnet-4-6"

_EXPLAIN_SYSTEM_PROMPT = """\
You are a formal verification expert. Transform raw verification errors into clear,
actionable developer explanations. Focus on:
1. What invariant or property was violated (plain English)
2. The specific input/counterexample that triggered it
3. Why the current code fails that invariant
4. A concrete, actionable suggested fix

Keep your explanation concise (3-5 sentences). Do not include SMT solver internals
or line numbers from generated code. Speak directly to the developer.
"""


def _build_explain_prompt(explanation: "ExplainOutput") -> str:
    """Build the user prompt for LLM explanation from an ExplainOutput.

    Args:
        explanation: Structured explanation from explain_failure().

    Returns:
        User prompt string for the LLM.
    """
    parts = [
        f"Failed Stage: Stage {explanation.failed_stage} ({explanation.stage_name})",
        "",
        "Error messages:",
    ]
    for msg in explanation.error_messages:
        parts.append(f"  - {msg}")

    if explanation.counterexamples:
        parts.append("")
        parts.append("Counterexamples found:")
        for ce in explanation.counterexamples:
            parts.append(f"  - {ce}")

    if explanation.invariant_violated:
        parts.append("")
        parts.append(f"Invariant violated: {explanation.invariant_violated}")

    parts.append("")
    parts.append("Please explain this verification failure to a developer.")

    return "\n".join(parts)


def explain_with_llm(explanation: "ExplainOutput") -> str:
    """Generate an LLM-enhanced human-readable explanation of a verification failure.

    Transforms cryptic Dafny/SMT errors into plain English: what failed,
    counterexample input, which invariant was violated, and a suggested fix.

    Falls back to the heuristic suggested_fix if the LLM call fails.

    Args:
        explanation: Structured explanation from explain_failure().

    Returns:
        Human-readable explanation string. Never raises — falls back on LLM error.

    References:
        Scout 7 N2 — natural language explanation of WHY verification failed.
        [REF-T16] litellm — all LLM calls go through litellm.
        Anti-pattern: DO NOT hardcode model names — use NIGHTJAR_MODEL env var.
    """
    model = os.environ.get("NIGHTJAR_MODEL", _DEFAULT_MODEL)
    prompt = _build_explain_prompt(explanation)

    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": _EXPLAIN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=512,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()

    except Exception:  # noqa: BLE001
        # Graceful fallback: return heuristic suggestion
        if explanation.suggested_fix:
            return explanation.suggested_fix
        return (
            f"Verification failed at stage {explanation.failed_stage} "
            f"({explanation.stage_name}). "
            "Review the error messages and invariants in your .card.md spec."
        )
