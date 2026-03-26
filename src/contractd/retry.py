"""Clover-pattern retry loop for CARD verification.

Implements the closed-loop: generate → verify → repair → re-verify.
On verification failure, collects structured error context, builds a
repair prompt, calls LLM via litellm, and re-runs the full pipeline.

References:
- [REF-C02] Closed-loop verification (Clover pattern)
- [REF-P03] Clover paper — 87% correct acceptance, 0% false positives.
  The cycle: generate → verify → if fail, feed structured error back
  to LLM → regenerate → re-verify. Repeat up to N times.
- [REF-P06] DafnyPro — structured error format: file, line, message,
  assertion batch ID, resource units. Repair prompt includes all context.
- [REF-T16] litellm — all LLM calls go through litellm for model-agnosticism.
- ARCHITECTURE.md Section 4 — retry loop design, max N=5, temperature 0.2

Design per ARCHITECTURE.md Section 4:
  1. COLLECT FAILURE CONTEXT from failing stage
  2. BUILD REPAIR PROMPT with spec + failed code + structured errors
  3. CALL LLM (via litellm) at temperature 0.2 for deterministic repair
  4. RE-RUN FULL PIPELINE from Stage 0
  5. RETRY CAP: N=5 → if still failing, ESCALATE to human
"""

import json
import os
from typing import Any

import litellm

from contractd.types import CardSpec, StageResult, VerifyResult, VerifyStatus
from contractd.verifier import run_pipeline


# Default retry settings per ARCHITECTURE.md Section 4
DEFAULT_MAX_RETRIES = 5
REPAIR_TEMPERATURE = 0.2  # Deterministic repair [ARCHITECTURE.md]
REPAIR_MAX_TOKENS = 2048  # Output cap per ARCHITECTURE.md


def _collect_failure_context(verify_result: VerifyResult) -> list[dict]:
    """Collect structured error context from all failing stages.

    Per [REF-P06] DafnyPro, the repair prompt needs:
    - Failing stage name and number
    - Error messages with file, line, type
    - Counterexamples if available
    """
    failures = []
    for stage in verify_result.stages:
        if stage.status == VerifyStatus.FAIL:
            failure = {
                "stage": stage.stage,
                "stage_name": stage.name,
                "errors": stage.errors,
            }
            if stage.counterexample:
                failure["counterexample"] = stage.counterexample
            failures.append(failure)
    return failures


def build_repair_prompt(
    spec: CardSpec,
    failed_code: str,
    verify_result: VerifyResult,
    attempt: int,
) -> str:
    """Build a structured repair prompt for the LLM.

    Per [REF-P06] DafnyPro and [REF-P03] Clover:
    - System context: original .card.md spec
    - Failed code with structured error block
    - Prior attempt count for context
    - Specific instructions to fix the identified issues

    Args:
        spec: Original .card.md specification.
        failed_code: The code that failed verification.
        verify_result: The failed VerifyResult with error details.
        attempt: Current retry attempt number (1-based).

    Returns:
        Formatted repair prompt string.
    """
    failures = _collect_failure_context(verify_result)

    # Format failure context per [REF-P06] structured error format
    failure_block = json.dumps(failures, indent=2, default=str)

    # Format invariants from spec
    invariants_text = "\n".join(
        f"  - {inv.id} ({inv.tier.value}): {inv.statement}"
        for inv in spec.invariants
    )

    return f"""## Repair Request — Attempt {attempt}

### Original Specification
Module: {spec.id} — {spec.title}
Invariants:
{invariants_text}

### Failed Code
```
{failed_code}
```

### Verification Errors (structured)
```json
{failure_block}
```

### Instructions
Fix the code above so that it satisfies ALL invariants from the specification.
The verification pipeline reported the errors shown above.
Focus on the specific failing assertions — do not rewrite unrelated code.
Return ONLY the corrected code, no explanations.
"""


def _call_repair_llm(
    spec: CardSpec,
    failed_code: str,
    verify_result: VerifyResult,
    attempt: int,
) -> str:
    """Call LLM via litellm to repair failed code.

    Per [REF-T16], all LLM calls go through litellm for model-agnosticism.
    Model selected from CARD_MODEL env var. Temperature 0.2 for
    deterministic repair per ARCHITECTURE.md Section 4.

    Args:
        spec: Original .card.md specification.
        failed_code: Code that failed verification.
        verify_result: Failed verification result with errors.
        attempt: Current attempt number.

    Returns:
        Repaired code string from LLM.
    """
    model = os.environ.get("CARD_MODEL", "claude-sonnet-4-6")
    repair_prompt = build_repair_prompt(spec, failed_code, verify_result, attempt)

    response = litellm.completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a code repair agent for CARD "
                    "(Contract-Anchored Regenerative Development). "
                    "Fix verification failures in generated code. "
                    "Return ONLY the corrected code."
                ),
            },
            {"role": "user", "content": repair_prompt},
        ],
        temperature=REPAIR_TEMPERATURE,
        max_tokens=REPAIR_MAX_TOKENS,
    )

    return response.choices[0].message.content


def run_with_retry(
    spec: CardSpec,
    code: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> VerifyResult:
    """Run verification with Clover-pattern retry loop [REF-C02, REF-P03].

    1. Run full verification pipeline
    2. If PASS → return success
    3. If FAIL → collect error context → build repair prompt →
       call LLM → get repaired code → re-run pipeline
    4. Repeat up to max_retries times
    5. If still failing after max_retries → return failure (human escalation)

    Args:
        spec: Parsed .card.md specification.
        code: Initial generated code to verify.
        max_retries: Maximum repair attempts (default 5 per ARCHITECTURE.md).

    Returns:
        VerifyResult with verified status and retry_count.
    """
    current_code = code

    # First attempt — no retry yet
    result = run_pipeline(spec, current_code)

    if result.verified:
        result.retry_count = 0
        return result

    # Retry loop per [REF-P03] Clover pattern
    for attempt in range(1, max_retries + 1):
        # Step 1: Call LLM for repair [REF-T16]
        repaired_code = _call_repair_llm(spec, current_code, result, attempt)

        # Step 2: Re-run full pipeline from Stage 0 [REF-P03]
        current_code = repaired_code
        result = run_pipeline(spec, current_code)

        if result.verified:
            result.retry_count = attempt
            return result

    # Exhausted retries — human escalation needed
    result.retry_count = max_retries
    return result
