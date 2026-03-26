"""Invariant generators — shared types and HiLDe-inspired ranking.

Exports:
  InvariantCandidate  — raw candidate from LLM (Step 2)
  RankedInvariant     — candidate with ranking score (Step 5)
  ApprovedInvariant   — user-approved, with generated code (post Step 7)
  rank_candidates()   — HiLDe-inspired ranking, surfaces top 5-10
  format_invariant()  — Kiro UX format: "For any X where Y, Z holds"

HiLDe ranking (UC San Diego PL, Nadia Polikarpova, arxiv 2505.22906):
  Surface the top N most "interesting" invariants from potentially 50+
  candidates. Ranking factors:
    - LLM-provided confidence
    - Specificity (penalise vague terms: valid, correct, proper)
    - Boundary bonus (reward edge-case coverage: null, zero, max, min)

Clean-room implementation — algorithm derived from paper description,
no code copied from HiLDe repository.

References:
  Scout 4 F9: HiLDe ranking → surface top 5-10 (not all 50)
  [REF-T10] icontract, [REF-T03] Hypothesis, [REF-T01] Dafny
"""

import re
from dataclasses import dataclass, field

from nightjar.intent_router import InvariantClass, VAGUE_TERMS, BOUNDARY_TERMS


# ── Types ─────────────────────────────────────────────────────────────────────


@dataclass
class InvariantCandidate:
    """Raw invariant candidate from LLM generation (Step 2).

    NL2Contract (CR-03, arxiv 2510.12702): LLMs generate full
    functional contracts (pre+postconditions) from NL intent.
    """

    statement: str
    """Natural language invariant statement."""

    confidence: float
    """LLM-provided confidence score [0.0, 1.0]."""

    inv_class: InvariantClass
    """Domain classification from intent router (Step 3)."""


@dataclass
class RankedInvariant:
    """Invariant candidate with HiLDe-inspired ranking score (Step 5)."""

    candidate: InvariantCandidate
    rank_score: float
    """Composite ranking score (higher = more interesting/useful)."""

    formatted: str
    """Kiro UX format: 'For any X where Y, Z holds' (Step 6)."""


@dataclass
class ApprovedInvariant:
    """User-approved invariant with generated code artifacts (after Step 7)."""

    statement: str
    """Final approved invariant text (may be user-modified)."""

    inv_class: InvariantClass

    icontract_code: str = ""
    """@icontract.require / @ensure decorator string [REF-T10]."""

    hypothesis_code: str = ""
    """Hypothesis @given test strategy code [REF-T03]."""

    dafny_code: str = ""
    """Optional Dafny requires/ensures clause [REF-T01].
    Scout 4: Dafny tier is OPTIONAL — auto-suggested only."""


# ── HiLDe-inspired ranking ────────────────────────────────────────────────────

# Default maximum candidates to surface (Scout 4: "top 5-10, not all 50")
_DEFAULT_TOP_N = 7

# Penalty per vague term found in the statement
_VAGUE_PENALTY = 0.15

# Bonus per boundary-condition term found
_BOUNDARY_BONUS = 0.10

# Optimal statement length range (in words) for specificity scoring
_OPTIMAL_WORDS_MIN = 5
_OPTIMAL_WORDS_MAX = 20


def rank_candidates(
    candidates: list[InvariantCandidate],
    top_n: int = _DEFAULT_TOP_N,
) -> list[RankedInvariant]:
    """Rank invariant candidates and return the top N.

    HiLDe-inspired ranking (arxiv 2505.22906, UC San Diego PL):
    Surfaces the top N most "interesting" invariants from the candidate
    pool. Score = confidence × specificity_factor × boundary_bonus_factor.

    Args:
        candidates: All generated invariant candidates (may be 50+).
        top_n: Maximum candidates to return. Default 7 (per Scout 4 F9:
               "surface top 5-10, not all 50").

    Returns:
        Ranked list of RankedInvariant, highest score first,
        limited to top_n entries.
    """
    if not candidates:
        return []

    scored = [
        RankedInvariant(
            candidate=c,
            rank_score=_compute_rank_score(c),
            formatted=format_invariant(c),
        )
        for c in candidates
    ]

    # Sort descending by rank score
    scored.sort(key=lambda r: r.rank_score, reverse=True)

    return scored[:top_n]


def _compute_rank_score(candidate: InvariantCandidate) -> float:
    """Compute HiLDe-inspired rank score for one candidate.

    Score = confidence × specificity × boundary_factor

    All factors clamped to [0.01, 1.0] to prevent zero/negative scores.
    """
    # Base: LLM confidence
    confidence = max(0.01, min(1.0, candidate.confidence))

    # Specificity factor: penalise vague terms
    specificity = _specificity_factor(candidate.statement)

    # Boundary factor: reward edge-case coverage
    boundary = _boundary_factor(candidate.statement)

    return confidence * specificity * boundary


def _specificity_factor(statement: str) -> float:
    """Compute specificity: penalise vague generic terms.

    Vague terms (valid, correct, proper, appropriate) reduce specificity
    because they are hard to operationalize as executable invariants.
    """
    lower = statement.lower()
    tokens = re.findall(r"\b\w+\b", lower)
    if not tokens:
        return 0.5

    vague_count = sum(1 for t in tokens if t in VAGUE_TERMS)
    word_count = len(tokens)

    # Length factor: penalise too-short (too vague) and too-long (too complex)
    if word_count < _OPTIMAL_WORDS_MIN:
        length_factor = 0.8
    elif word_count > _OPTIMAL_WORDS_MAX:
        length_factor = 0.9
    else:
        length_factor = 1.0

    vague_penalty = min(0.5, vague_count * _VAGUE_PENALTY)
    return max(0.1, (1.0 - vague_penalty) * length_factor)


def _boundary_factor(statement: str) -> float:
    """Compute boundary bonus: reward edge-case coverage terms."""
    lower = statement.lower()
    tokens = set(re.findall(r"\b\w+\b", lower))
    boundary_count = len(tokens & BOUNDARY_TERMS)
    bonus = min(0.3, boundary_count * _BOUNDARY_BONUS)
    return 1.0 + bonus


# ── Kiro UX formatter ─────────────────────────────────────────────────────────


def format_invariant(candidate: InvariantCandidate) -> str:
    """Format invariant in Kiro UX pattern: 'For any X where Y, Z holds'.

    Kiro spec-driven IDE UX pattern (kiro.dev/docs/specs/correctness/):
    Invariants are presented in natural language as:
      "For any [subject] where [precondition], [postcondition] holds."

    This format makes invariants readable and reviewable for non-experts.

    Args:
        candidate: InvariantCandidate to format.

    Returns:
        Human-readable string in Kiro UX format.
    """
    statement = candidate.statement.strip()
    inv_class = candidate.inv_class

    # Attempt to extract subject/condition from statement
    # Fallback: wrap the whole statement in the Kiro template
    if _is_conditional(statement):
        # Statement already has conditional structure
        formatted = f"Invariant [{inv_class.value}]: {statement}"
    else:
        # Wrap in "For any ... holds" pattern
        formatted = f"For any input where applicable: {statement} (holds)"

    return formatted


def _is_conditional(statement: str) -> bool:
    """Check if statement already has conditional structure."""
    lower = statement.lower()
    return any(
        marker in lower
        for marker in ("when", "if ", "given ", "for any", "for all", "where", "after", "before")
    )
