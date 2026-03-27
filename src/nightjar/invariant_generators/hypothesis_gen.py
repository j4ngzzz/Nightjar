"""Hypothesis test strategy generator — @given + property test body.

Converts classified invariant candidates to Hypothesis property-based tests.
All code generation goes through litellm [REF-T16].

Reference: [REF-T03] Hypothesis (https://github.com/HypothesisWorks/hypothesis)
API:
  @given(st.integers(min_value=1))
  @settings(max_examples=100)
  def test_property_name(param):
      assert condition

License: MPL 2.0

[REF-P10] PGS (arxiv 2506.18315): LLMs are 20-47% more accurate generating
validation properties than generating implementations. This is why
property-based testing is the right verification approach for Stage 3.
"""

import re

import litellm

from nightjar.invariant_generators import InvariantCandidate


# ── Constants ─────────────────────────────────────────────────────────────────

_GENERATION_TEMPERATURE = 0.1
_MAX_TOKENS = 512

_SYSTEM_PROMPT = """\
You are an expert in Hypothesis property-based testing for Python.
Convert the given invariant statement to a Hypothesis property test.

RULES:
1. Import: from hypothesis import given, settings; from hypothesis import strategies as st
2. Use @given() with appropriate strategies based on the invariant type
3. Use @settings(max_examples=100) for numerical invariants
4. The test function name must start with test_
5. The test body must assert the invariant condition
6. Return ONLY the complete, runnable test function (imports + decorator + function)
7. Make the function self-contained — no external dependencies

Strategy selection guide:
- Integer bounds → st.integers(min_value=..., max_value=...)
- Positive floats → st.floats(min_value=0.01, allow_nan=False)
- Non-empty strings → st.text(min_size=1)
- Non-null objects → st.builds(...) or st.from_type(...)
- Booleans → st.booleans()

Example:
Invariant: "amount must be positive"
Output:
from hypothesis import given, settings
from hypothesis import strategies as st

@given(st.floats(min_value=0.01, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_amount_must_be_positive(amount):
    assert amount > 0
"""


def generate_hypothesis(
    candidate: InvariantCandidate,
    model: str,
) -> str:
    """Generate a Hypothesis property-based test for the given invariant.

    Calls litellm to convert the NL invariant statement to a complete,
    runnable Hypothesis test function with @given strategies.

    The generated code is validated for Python syntax. If invalid,
    a safe fallback test stub is returned.

    Args:
        candidate: Classified invariant candidate to generate test for.
        model: litellm model identifier (e.g. 'claude-sonnet-4-6').

    Returns:
        String containing complete Hypothesis test code.

    References:
        [REF-T03] Hypothesis property-based testing
        [REF-T16] litellm unified LLM API
        [REF-P10] PGS: LLMs accurate at generating validation properties
    """
    user_prompt = (
        f"Invariant type: {candidate.inv_class.value}\n"
        f"Statement: {candidate.statement}\n\n"
        "Generate the Hypothesis property test."
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
        # LLM unavailable — return safe fallback test stub
        return _fallback_test(candidate, reason=str(e))

    # Extract code (may be wrapped in markdown code block)
    code = _extract_code(raw)

    # Validate syntax; fall back to safe stub if invalid
    if not _is_valid_syntax(code):
        code = _fallback_test(candidate)

    return code


def _extract_code(raw: str) -> str:
    """Extract Python code from potentially markdown-wrapped LLM output."""
    # Try to unwrap markdown code block
    code_block = re.search(r"```(?:python)?\s*(.*?)```", raw, re.DOTALL)
    if code_block:
        return code_block.group(1).strip()
    return raw


def _is_valid_syntax(code: str) -> bool:
    """Check if the generated code is syntactically valid Python."""
    if not code.strip():
        return False
    try:
        compile(code, "<string>", "exec")
        return True
    except SyntaxError:
        return False


def _fallback_test(candidate: InvariantCandidate, reason: str = "") -> str:
    """Safe fallback Hypothesis test when LLM output is invalid or unavailable."""
    safe_name = re.sub(r"\W+", "_", candidate.statement.lower())[:40].strip("_")
    comment = f"    # LLM error: {reason}\n" if reason else ""
    return (
        "from hypothesis import given\n"
        "from hypothesis import strategies as st\n"
        "\n"
        f"@given(st.text())\n"
        f"def test_{safe_name}(x):\n"
        f"{comment}"
        f"    # TODO: implement property for: {candidate.statement}\n"
        f"    pass\n"
    )
