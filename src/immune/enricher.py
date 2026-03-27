"""LLM-driven invariant enrichment for Nightjar's immune system.

Takes raw Daikon-mined invariants, function signatures, and error traces,
then uses an LLM (via litellm) to generate semantically richer Python
assert statements that would have caught observed failures.

The enrichment prompt follows the Agentic PBT pattern [REF-P15]: present
the LLM with observed invariants + failure context and ask it to propose
stronger properties as executable assert statements.

All LLM calls go through litellm [REF-T16] for model-agnosticism.

References:
- [REF-C06] LLM-Driven Invariant Enrichment
- [REF-P15] Agentic PBT — LLM proposes properties, writes tests
- [REF-P14] NL2Contract — LLM generates formal contracts from NL
- [REF-T16] litellm — model-agnostic LLM interface
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

import litellm


# Enrichment prompt template following [REF-P15] Agentic PBT pattern
_ENRICHMENT_PROMPT_TEMPLATE = """\
You are a formal verification expert. Given a Python function signature, \
observed runtime invariants, and optionally an error trace, generate Python \
assert statements that capture properties the function should satisfy.

## Function
```python
{function_signature}
```

## Observed Invariants (from dynamic analysis)
{observed_invariants_block}

{error_trace_block}

## Instructions
Generate Python assert statements that:
1. Would have caught the observed failure (if error trace is provided)
2. Strengthen the observed invariants with semantic understanding
3. Cover preconditions (valid inputs) and postconditions (valid outputs)
4. Use 'result' to refer to the function's return value
5. Use parameter names from the function signature for inputs

Format each assertion as:
```
assert <condition>, "<brief explanation>"
```

Output ONLY the assert statements, one per line. No other text.
"""


@dataclass
class CandidateInvariant:
    """A candidate invariant proposed by the LLM. [REF-C06]

    Attributes:
        expression: Python expression (e.g., 'result >= 0').
        explanation: Human-readable explanation of the invariant.
        confidence: Confidence score (0.0 to 1.0). Higher if corroborated
            by observed invariants.
    """
    expression: str
    explanation: str = ""
    confidence: float = 0.5


@dataclass
class EnrichmentResult:
    """Result of LLM invariant enrichment. [REF-C06]

    Attributes:
        candidates: List of candidate invariants proposed by the LLM.
        raw_response: The raw LLM response text.
        error: Error message if the enrichment failed.
    """
    candidates: list[CandidateInvariant] = field(default_factory=list)
    raw_response: str = ""
    error: Optional[str] = None


def build_enrichment_prompt(
    function_signature: str,
    observed_invariants: list[str],
    error_trace: Optional[str] = None,
) -> str:
    """Build the enrichment prompt for the LLM.

    Follows [REF-P15] Agentic PBT pattern: present observed invariants
    and failure context, ask for executable assert statements.

    Args:
        function_signature: Python function def line or full signature.
        observed_invariants: List of invariant expressions from Daikon mining.
        error_trace: Optional error/exception trace from production failure.

    Returns:
        Formatted prompt string ready for the LLM.
    """
    if observed_invariants:
        inv_block = "\n".join(f"- {inv}" for inv in observed_invariants)
    else:
        inv_block = "(none observed yet)"

    if error_trace:
        error_block = f"## Error Trace (from production failure)\n```\n{error_trace}\n```"
    else:
        error_block = ""

    return _ENRICHMENT_PROMPT_TEMPLATE.format(
        function_signature=function_signature,
        observed_invariants_block=inv_block,
        error_trace_block=error_block,
    )


def _parse_assert_statements(
    response: str,
    observed_invariants: Optional[list[str]] = None,
) -> list[CandidateInvariant]:
    """Parse LLM response into CandidateInvariant objects.

    Extracts assert statements from the response, handling various
    formatting quirks (code blocks, extra text, etc.).
    """
    observed = set(observed_invariants or [])
    candidates = []

    for line in response.split("\n"):
        line = line.strip()

        # Skip empty lines, comments, code fences
        if not line or line.startswith("#") or line.startswith("```"):
            continue

        # Match assert statements: assert <expr>, "<explanation>"
        # or assert <expr>
        match = re.match(
            r'^assert\s+(.+?)(?:,\s*["\'](.+?)["\'])?\s*$',
            line,
        )
        if not match:
            continue

        expression = match.group(1).strip()
        explanation = match.group(2) or ""

        # Skip trivially empty expressions
        if not expression:
            continue

        # Assign confidence: higher if corroborated by observed invariants
        confidence = 0.5
        if expression in observed:
            confidence = 0.8  # Direct match with observed
        elif any(obs in expression or expression in obs for obs in observed):
            confidence = 0.7  # Partial overlap

        candidates.append(CandidateInvariant(
            expression=expression,
            explanation=explanation,
            confidence=confidence,
        ))

    return candidates


def _call_llm(prompt: str) -> str:
    """Call the LLM via litellm. [REF-T16]

    Uses NIGHTJAR_MODEL env var for model selection, falling back to a default.
    All LLM calls MUST go through litellm — never call provider APIs directly.
    """
    model = os.environ.get("NIGHTJAR_MODEL", "deepseek/deepseek-chat")

    response = litellm.completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a formal verification expert specializing in "
                    "Python runtime invariants and contract generation."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,  # Lower temperature for more precise assertions
        max_tokens=1000,
    )

    return response.choices[0].message.content or ""


def enrich_invariants(
    function_signature: str,
    observed_invariants: list[str],
    error_trace: Optional[str] = None,
) -> EnrichmentResult:
    """Enrich raw invariants using LLM-driven analysis.

    Takes observed invariants (from Daikon mining [REF-C05]) and optionally
    an error trace, then uses the LLM to propose stronger, more semantically
    meaningful invariants as Python assert statements.

    Args:
        function_signature: Python function def line or full signature.
        observed_invariants: Invariant expressions from dynamic analysis.
        error_trace: Optional error/exception trace from production failure.

    Returns:
        EnrichmentResult with candidate invariants and metadata.

    References:
        [REF-C06] LLM-Driven Invariant Enrichment
        [REF-P15] Agentic PBT — LLM property proposal pattern
        [REF-T16] litellm — model-agnostic LLM calls
    """
    prompt = build_enrichment_prompt(
        function_signature=function_signature,
        observed_invariants=observed_invariants,
        error_trace=error_trace,
    )

    try:
        raw_response = _call_llm(prompt)
    except Exception as e:
        return EnrichmentResult(
            error=f"LLM call failed: {type(e).__name__}: {e}",
        )

    candidates = _parse_assert_statements(raw_response, observed_invariants)

    return EnrichmentResult(
        candidates=candidates,
        raw_response=raw_response,
    )
