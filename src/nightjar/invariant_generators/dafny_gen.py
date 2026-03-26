"""Dafny requires/ensures generator — OPTIONAL formal tier.

Converts classified invariant candidates to Dafny spec clauses.
All code generation goes through litellm [REF-T16].

IMPORTANT — Scout 4 honest assessment:
  "Yes for example/property tiers (100% optional).
   No for formal tier — LLMs still struggle with complex Dafny invariants.
   Formal tier should remain OPTIONAL, auto-suggested only."

Output from this generator is ALWAYS marked as optional/commented.
The auto pipeline includes Dafny suggestions but they require human review.

Reference: [REF-T01] Dafny (https://github.com/dafny-lang/dafny)
Dafny spec syntax:
  requires condition       # precondition
  ensures condition        # postcondition
  invariant condition      # loop invariant

License: MIT

[REF-P02] Vericoding: 82% Dafny success rate with off-the-shelf LLMs.
[REF-P06] DafnyPro: structured error format enables targeted repair.
"""

import os
import re

import litellm

from nightjar.invariant_generators import InvariantCandidate
from nightjar.intent_router import InvariantClass


# ── Constants ─────────────────────────────────────────────────────────────────

_GENERATION_TEMPERATURE = 0.1
_MAX_TOKENS = 256

_SYSTEM_PROMPT = """\
You are an expert in Dafny formal verification.
Convert the given invariant statement to a Dafny specification clause.

RULES:
1. Use 'requires' for preconditions (what must be true of inputs)
2. Use 'ensures' for postconditions (what must be true of outputs)
3. Use simple Dafny boolean expressions
4. Return ONLY the Dafny clause(s) — no method body, no imports
5. One clause per line

Example:
Invariant: "amount must be positive"
Output: requires amount > 0

Example:
Invariant: "returns non-null receipt on success"
Output: ensures result != null && result.amount > 0

IMPORTANT: This is an auto-suggestion. Complex invariants may need human review.
"""


def generate_dafny(
    candidate: InvariantCandidate,
    model: str,
) -> str:
    """Generate an optional Dafny requires/ensures clause.

    IMPORTANT: Dafny output is ALWAYS marked as optional. Scout 4's honest
    assessment: LLMs still struggle with complex Dafny invariants. This
    output requires human review before adding to formal verification.

    Calls litellm to convert NL invariant → Dafny spec clause.
    Output is prefixed with a comment marking it as auto-suggested/optional.

    Args:
        candidate: Classified invariant candidate.
        model: litellm model identifier.

    Returns:
        String with Dafny clause, prefixed with optional marker comment.

    References:
        [REF-T01] Dafny formal verification
        [REF-T16] litellm unified LLM API
        Scout 4 honest assessment: formal tier is optional
    """
    user_prompt = (
        f"Invariant type: {candidate.inv_class.value}\n"
        f"Statement: {candidate.statement}\n\n"
        "Generate the Dafny specification clause."
    )

    response = litellm.completion(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=_GENERATION_TEMPERATURE,
        max_tokens=_MAX_TOKENS,
    )

    raw = response.choices[0].message.content.strip()

    # Extract just the Dafny clause(s)
    clause = _extract_dafny_clause(raw)

    # ALWAYS mark as optional — Scout 4 assessment
    return _mark_as_optional(clause, candidate.statement)


def _extract_dafny_clause(raw: str) -> str:
    """Extract Dafny clause from potentially verbose LLM output."""
    # Unwrap markdown code block
    code_block = re.search(r"```(?:dafny|java|csharp)?\s*(.*?)```", raw, re.DOTALL)
    if code_block:
        return code_block.group(1).strip()

    # Take lines that look like Dafny clauses
    dafny_lines = []
    for line in raw.split("\n"):
        line = line.strip()
        if re.match(r"^(requires|ensures|invariant)\b", line):
            dafny_lines.append(line)

    if dafny_lines:
        return "\n".join(dafny_lines)

    # Return first non-empty line as best guess
    for line in raw.split("\n"):
        line = line.strip()
        if line:
            return line

    return raw


def _mark_as_optional(clause: str, original_statement: str) -> str:
    """Mark Dafny clause as optional/auto-suggested.

    Scout 4 honest assessment: formal tier is OPTIONAL.
    Human review required before using in formal verification.
    """
    lines = [
        "# optional (auto-suggested formal tier — requires human review)",
        f"# Source statement: {original_statement}",
    ]
    for line in clause.split("\n"):
        lines.append(f"# {line}")
    return "\n".join(lines)
