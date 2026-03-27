"""icontract decorator generator — @require / @ensure / @invariant.

Converts classified invariant candidates to icontract decorators.
All code generation goes through litellm [REF-T16].

Reference: [REF-T10] icontract (https://github.com/Parquery/icontract)
API:
  @icontract.require(lambda param: condition, "description")
  @icontract.ensure(lambda result: condition, "description")
  @icontract.invariant(lambda self: condition)

License: MIT

NL2Contract (CR-03, arxiv 2510.12702): Generates sound contracts
(pre + postconditions) from natural language invariant statements.
"""

import re

import litellm

from nightjar.invariant_generators import InvariantCandidate
from nightjar.intent_router import InvariantClass


# ── Constants ─────────────────────────────────────────────────────────────────

# Low temperature for deterministic code generation [REF-P06]
_GENERATION_TEMPERATURE = 0.1
_MAX_TOKENS = 256

_SYSTEM_PROMPT = """\
You are an expert Python programmer specializing in design-by-contract with icontract.
Convert the given invariant statement to an icontract decorator.

RULES:
1. Use @icontract.require for PRECONDITIONS (what must be true of inputs)
2. Use @icontract.ensure for POSTCONDITIONS (what must be true of outputs)
3. Use @icontract.invariant for STATE invariants (always true for objects)
4. The lambda must use simple Python expressions — no function calls unless necessary
5. Include a human-readable description string as the second argument
6. Return ONLY the decorator line (one line starting with @icontract.)
7. Do NOT include the function definition — just the decorator

Example:
Invariant: "amount must be positive"
Output: @icontract.require(lambda amount: amount > 0, "amount must be positive")

Example:
Invariant: "returns non-empty string on success"
Output: @icontract.ensure(lambda result: result is not None and len(result) > 0, "result must be non-empty")
"""


def generate_icontract(
    candidate: InvariantCandidate,
    model: str,
) -> str:
    """Generate an icontract decorator for the given invariant candidate.

    Calls litellm to convert the NL invariant statement to a Python
    icontract decorator (@require, @ensure, or @invariant).

    The generated code is validated for Python syntax before returning.
    If the LLM returns invalid syntax, a safe fallback decorator is used.

    Args:
        candidate: Classified invariant candidate to generate code for.
        model: litellm model identifier (e.g. 'claude-sonnet-4-6').

    Returns:
        String containing the icontract decorator line, syntactically valid.

    References:
        [REF-T10] icontract design-by-contract
        [REF-T16] litellm unified LLM API
        CR-03: NL2Contract (arxiv 2510.12702)
    """
    decorator_type = _select_decorator_type(candidate.inv_class)
    user_prompt = (
        f"Invariant type: {candidate.inv_class.value}\n"
        f"Decorator to use: {decorator_type}\n"
        f"Statement: {candidate.statement}\n\n"
        "Generate the icontract decorator line."
    )

    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=_GENERATION_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )
        raw = (response.choices[0].message.content or "").strip()
    except Exception as e:
        # LLM unavailable — return safe commented stub
        return _fallback_decorator(candidate, reason=str(e))

    # Extract just the decorator line (may include extra text)
    decorator = _extract_decorator(raw)

    # Validate Python syntax; fall back to safe stub if invalid
    if not _is_valid_syntax(decorator):
        decorator = _fallback_decorator(candidate)

    return decorator


def _select_decorator_type(inv_class: InvariantClass) -> str:
    """Select the appropriate icontract decorator type for the class."""
    if inv_class == InvariantClass.BEHAVIORAL:
        return "@icontract.require or @icontract.ensure"
    if inv_class == InvariantClass.STATE:
        return "@icontract.invariant"
    if inv_class == InvariantClass.NUMERICAL:
        return "@icontract.require"
    # FORMAL → require as approximation
    return "@icontract.require"


def _extract_decorator(raw: str) -> str:
    """Extract the decorator line from potentially verbose LLM output."""
    # Look for lines starting with @icontract.
    for line in raw.split("\n"):
        line = line.strip()
        if line.startswith("@icontract."):
            return line

    # Try to find it in a code block
    code_block = re.search(r"```(?:python)?\s*(.*?)```", raw, re.DOTALL)
    if code_block:
        for line in code_block.group(1).split("\n"):
            line = line.strip()
            if line.startswith("@icontract."):
                return line

    # Return raw if no decorator found (will fail syntax check → fallback)
    return raw.split("\n")[0] if raw else ""


def _is_valid_syntax(code: str) -> bool:
    """Check if the generated code is syntactically valid Python."""
    if not code.strip():
        return False
    try:
        # Wrap in a minimal function stub to make @decorator syntax valid
        compile(f"{code}\ndef _f(): pass", "<string>", "exec")
        return True
    except SyntaxError:
        return False


def _fallback_decorator(candidate: InvariantCandidate, reason: str = "") -> str:
    """Safe fallback decorator when LLM output is invalid or LLM unavailable.

    Produces a commented-out stub with the original statement so the
    .card.md can still be written and reviewed by the user.
    """
    escaped = candidate.statement.replace("'", "\\'")
    suffix = f"  # LLM error: {reason}" if reason else ""
    return f"# TODO: @icontract.require(lambda: True, '{escaped}'){suffix}"
