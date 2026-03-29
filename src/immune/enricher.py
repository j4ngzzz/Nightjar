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

import csv
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import litellm

from nightjar.config import DEFAULT_MODEL


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
    model = os.environ.get("NIGHTJAR_MODEL", DEFAULT_MODEL)

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


# ── Invariant Refinement Ratchet (AlphaEvolve style) ─────────────────────────


_REFINEMENT_PROMPT_TEMPLATE = """\
You are an invariant refinement agent. Given a Python invariant expression and its context, \
propose ONE targeted improvement using SEARCH/REPLACE format:

SEARCH: <exact substring to change>
REPLACE: <improved version>

Function: {function_sig}
Current invariant: {expression}
Current confidence: {confidence:.2f}

Propose a refinement that tightens the bound, adds an upper bound, \
or makes the constraint more specific. If no improvement is possible, return: NO_CHANGE
"""

_TSV_REFINEMENT_COLUMNS = (
    "timestamp",
    "function_sig",
    "expression_before",
    "expression_after",
    "score_before",
    "score_after",
    "action",
)


def _log_refinement_to_tsv(log_path: str, row: dict) -> None:
    """Append a refinement event row to the TSV log at log_path.

    Columns: timestamp, function_sig, expression_before, expression_after,
    score_before, score_after, action (KEEP/DISCARD/PLATEAU).

    Non-fatal: all I/O errors are silently suppressed so a missing or
    unwritable .card/ directory never crashes the verification pipeline.

    References:
        [REF-C06] LLM-Driven Invariant Enrichment
    """
    try:
        file_exists = os.path.isfile(log_path)
        with open(log_path, "a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=_TSV_REFINEMENT_COLUMNS,
                delimiter="\t",
                extrasaction="ignore",
            )
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
    except Exception:
        pass  # TSV logging is observability only — never fatal


def _propose_refinement(
    candidate: "CandidateInvariant",
    function_sig: str,
    model: Optional[str] = None,
) -> Optional["CandidateInvariant"]:
    """Propose a single targeted refinement for a candidate invariant.

    Uses AlphaEvolve-style SEARCH/REPLACE diff format: the LLM identifies
    one substring to change and provides the improved version.

    Args:
        candidate:    The invariant to refine.
        function_sig: Python function signature providing context.
        model:        Model override. Falls back to NIGHTJAR_MODEL env var.

    Returns:
        A new CandidateInvariant with the refined expression, or None if:
        - The LLM returns NO_CHANGE
        - The SEARCH string is not found in the original expression
        - Any LLM or parse error occurs

    References:
        [REF-C06] LLM-Driven Invariant Enrichment
    """
    effective_model = model or os.environ.get("NIGHTJAR_MODEL") or DEFAULT_MODEL
    prompt = _REFINEMENT_PROMPT_TEMPLATE.format(
        function_sig=function_sig,
        expression=candidate.expression,
        confidence=candidate.confidence,
    )

    try:
        response = litellm.completion(
            model=effective_model,
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
            temperature=0.2,
            max_tokens=256,
        )
        raw = response.choices[0].message.content or ""
    except Exception:
        return None

    raw = raw.strip()

    # Fast-path: LLM says no improvement possible
    if "NO_CHANGE" in raw:
        return None

    # Parse SEARCH / REPLACE lines
    search_match = re.search(r"SEARCH:\s*(.+)", raw)
    replace_match = re.search(r"REPLACE:\s*(.+)", raw)

    if not search_match or not replace_match:
        return None

    search_str = search_match.group(1).strip()
    replace_str = replace_match.group(1).strip()

    if search_str not in candidate.expression:
        return None

    new_expression = candidate.expression.replace(search_str, replace_str, 1)

    return CandidateInvariant(
        expression=new_expression,
        explanation=candidate.explanation,
        confidence=candidate.confidence,
    )


def refine_invariants_ratchet(
    candidates: list["CandidateInvariant"],
    function_sig: str,
    model: Optional[str] = None,
    max_rounds: int = 3,
    quality_threshold: float = 0.5,
    budget_seconds: float = 60.0,
) -> list["CandidateInvariant"]:
    """Iteratively refine low-quality invariants using an LLM ratchet loop.

    AlphaEvolve-inspired ratchet: accept a refinement only when it strictly
    improves the quality score (monotone improvement guarantee). Plateau
    detection stops early when two consecutive rounds yield no improvement.

    Activation gate: returns candidates unchanged unless the environment
    variable NIGHTJAR_ENABLE_EVOLUTION is set to "1".

    Args:
        candidates:         Invariant candidates to refine.
        function_sig:       Python function signature (context for the LLM).
        model:              Model override; defaults to NIGHTJAR_MODEL env var.
        max_rounds:         Maximum refinement rounds (default: 3).
        quality_threshold:  Candidates at or above this score are skipped
                            (default: 0.5).
        budget_seconds:     Wall-clock budget for the entire loop (default: 60s).

    Returns:
        List of CandidateInvariant with low-quality members replaced by their
        refined versions where refinement improved the quality score.

    References:
        [REF-C06] LLM-Driven Invariant Enrichment
    """
    # Activation gate — opt-in only
    if os.environ.get("NIGHTJAR_ENABLE_EVOLUTION", "0") != "1":
        return candidates

    # Lazy import to avoid circular dependency with quality_scorer
    from immune.quality_scorer import score_candidate  # noqa: PLC0415

    log_path = ".card/invariant_refinement.tsv"
    result = list(candidates)
    budget_start = time.monotonic()
    consecutive_no_improvement = 0

    for _round_idx in range(max_rounds):
        if time.monotonic() - budget_start >= budget_seconds:
            break

        improved_any = False

        for i, candidate in enumerate(result):
            # Budget check inside inner loop too
            if time.monotonic() - budget_start >= budget_seconds:
                break

            score_before = score_candidate(candidate).score

            # Skip candidates that already meet the quality bar
            if score_before >= quality_threshold:
                continue

            refined = _propose_refinement(candidate, function_sig, model)
            if refined is None:
                continue

            score_after = score_candidate(refined).score

            timestamp = datetime.now(tz=timezone.utc).isoformat()

            if score_after > score_before:
                result[i] = refined
                improved_any = True
                action = "KEEP"
            else:
                action = "DISCARD"

            _log_refinement_to_tsv(
                log_path,
                {
                    "timestamp": timestamp,
                    "function_sig": function_sig,
                    "expression_before": candidate.expression,
                    "expression_after": refined.expression,
                    "score_before": f"{score_before:.4f}",
                    "score_after": f"{score_after:.4f}",
                    "action": action,
                },
            )

        if not improved_any:
            consecutive_no_improvement += 1
        else:
            consecutive_no_improvement = 0

        # Plateau detection — stop after two consecutive no-improvement rounds
        if consecutive_no_improvement >= 2:
            break

    return result


def enrich_with_inspiration(
    candidate: "CandidateInvariant",
    inspirations: list["CandidateInvariant"],
    function_sig: str,
    model: Optional[str] = None,
) -> "CandidateInvariant":
    """Enrich a single invariant candidate using AlphaEvolve inspiration context.

    Injects high-quality invariant examples from similar functions into the
    enrichment prompt so the LLM understands the desired level of specificity.
    Falls back to the original enrich_invariants() behaviour when no
    inspirations are provided.

    Args:
        candidate:    The invariant candidate to enrich.
        inspirations: High-quality invariants from similar functions to use
                      as examples. The top 2 (by confidence) are injected.
        function_sig: Python function signature for context.
        model:        Model override; defaults to NIGHTJAR_MODEL env var.

    Returns:
        A refined CandidateInvariant. If enrichment produces no candidates,
        the original candidate is returned unchanged.

    References:
        [REF-C06] LLM-Driven Invariant Enrichment
    """
    # No inspirations — fall back to standard enrichment
    if not inspirations:
        result = enrich_invariants(
            function_signature=function_sig,
            observed_invariants=[candidate.expression],
        )
        if result.candidates:
            return result.candidates[0]
        return candidate

    # Sort inspirations by confidence and take the top 2
    top = sorted(inspirations, key=lambda c: c.confidence, reverse=True)[:2]
    inspiration_lines = "\n".join(
        f"  - {insp.expression}" + (f"  # {insp.explanation}" if insp.explanation else "")
        for insp in top
    )

    effective_model = model or os.environ.get("NIGHTJAR_MODEL") or DEFAULT_MODEL

    inspiration_suffix = (
        "\n\nHere are high-quality invariants from similar functions:\n"
        f"{inspiration_lines}\n"
        "Use these as examples of the level of specificity to aim for."
    )

    prompt = (
        build_enrichment_prompt(
            function_signature=function_sig,
            observed_invariants=[candidate.expression],
        )
        + inspiration_suffix
    )

    try:
        raw_response = litellm.completion(
            model=effective_model,
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
            temperature=0.3,
            max_tokens=512,
        ).choices[0].message.content or ""
    except Exception:
        return candidate

    parsed = _parse_assert_statements(raw_response, [candidate.expression])
    if parsed:
        return parsed[0]
    return candidate
