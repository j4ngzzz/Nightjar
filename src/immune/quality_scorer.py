"""Wonda-inspired invariant quality scoring.

Task U2.1: Quality gate between miner output and enricher input.

Wonda (arxiv 2603.15510): AST normalization + semantic quality filter.
4B model matches 120B with proper curation. Key insight: most mined
invariants are trivially true or semantically vacuous. Filtering them
before LLM enrichment saves tokens and improves output quality.

Quality criteria:
  - Minimality: not a tautology (True, x == x)
  - Provability: syntactically valid Python expression
  - Semantic meaningfulness: base specificity × LLM confidence factor

Wire: miner.py → quality_scorer.py → enricher.py

References:
  REF-NEW-05: Wonda (arxiv 2603.15510)
  [REF-C05] Dynamic Invariant Mining
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from immune.enricher import CandidateInvariant


# ── Constants ─────────────────────────────────────────────────────────────────

QUALITY_THRESHOLD: float = 0.5
"""Minimum quality score for an invariant to pass the filter."""

_BASE_SPECIFICITY: float = 0.7
"""Base specificity for any non-trivial syntactically valid invariant."""


# ── QualityScore ──────────────────────────────────────────────────────────────


@dataclass
class QualityScore:
    """Quality assessment of a single invariant candidate.

    Wonda (REF-NEW-05): AST normalization + semantic quality filter.
    """

    candidate: CandidateInvariant
    score: float           # [0.0, 1.0]
    is_trivial: bool       # tautology or semantically vacuous
    is_valid_syntax: bool  # parses as a valid Python expression
    reason: str            # human-readable explanation


# ── Internal helpers ──────────────────────────────────────────────────────────


def _is_trivial(tree: ast.Expression) -> tuple[bool, str]:
    """Detect tautologies and vacuous expressions via AST inspection.

    Wonda (REF-NEW-05): AST normalization catches trivially true invariants
    that dynamic miners (Daikon, etc.) emit at high frequency. Filtering
    these before enrichment saves LLM tokens and improves output quality.

    Patterns detected:
      - Literal True  → tautology
      - Literal False → trivially false (useless as an invariant)
      - x == x / x is x → identity comparison (always true)
    """
    node = tree.body

    # Literal True / False constants
    if isinstance(node, ast.Constant):
        if node.value is True:
            return True, "tautology: literal True"
        if node.value is False:
            return True, "trivially false: literal False"

    # Identity comparison: x == x, x is x (both sides identical AST)
    if isinstance(node, ast.Compare):
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.Eq, ast.Is)):
            if ast.dump(node.left) == ast.dump(node.comparators[0]):
                return True, "tautology: identity comparison"

    return False, ""


def _confidence_factor(confidence: float) -> float:
    """Map LLM confidence [0, 1] → scaling factor [0.5, 1.0].

    Higher miner/LLM confidence boosts the final quality score without
    ever sending a valid, non-trivial invariant below 0 or above 1.
    """
    return 0.5 + 0.5 * max(0.0, min(1.0, confidence))


# ── Public API ────────────────────────────────────────────────────────────────


def score_candidate(candidate: CandidateInvariant) -> QualityScore:
    """Score a single invariant candidate for quality.

    Implements Wonda (REF-NEW-05) quality criteria:
      1. Provability    — syntactically valid Python expression
      2. Minimality     — not a tautology or vacuous literal
      3. Semantic score — base specificity × confidence factor

    Args:
        candidate: Mined invariant candidate from miner.py output.

    Returns:
        QualityScore with score in [0.0, 1.0].
    """
    expr = candidate.expression.strip()

    # Empty expression — neither valid nor trivial in a useful sense
    if not expr:
        return QualityScore(
            candidate=candidate,
            score=0.0,
            is_trivial=True,
            is_valid_syntax=False,
            reason="empty expression",
        )

    # Syntax validity check
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return QualityScore(
            candidate=candidate,
            score=0.0,
            is_trivial=False,
            is_valid_syntax=False,
            reason="invalid syntax",
        )

    # Triviality check (Wonda AST normalization)
    is_trivial, trivial_reason = _is_trivial(tree)
    if is_trivial:
        return QualityScore(
            candidate=candidate,
            score=0.0,
            is_trivial=True,
            is_valid_syntax=True,
            reason=trivial_reason,
        )

    # Semantic quality: base specificity scaled by miner confidence
    score = _BASE_SPECIFICITY * _confidence_factor(candidate.confidence)
    score = max(0.0, min(1.0, score))

    return QualityScore(
        candidate=candidate,
        score=score,
        is_trivial=False,
        is_valid_syntax=True,
        reason="",
    )


def score_candidates(candidates: list[CandidateInvariant]) -> list[QualityScore]:
    """Score a batch of invariant candidates.

    Args:
        candidates: List of mined invariant candidates.

    Returns:
        List of QualityScore objects, same length and order as input.
    """
    return [score_candidate(c) for c in candidates]


def filter_by_quality(
    candidates: list[CandidateInvariant],
    threshold: float = QUALITY_THRESHOLD,
) -> list[CandidateInvariant]:
    """Filter invariants below the quality threshold.

    Wires miner.py output → quality gate → enricher.py input.
    Trivial and low-quality invariants are dropped before LLM enrichment,
    saving tokens and improving enrichment quality (REF-NEW-05).

    Args:
        candidates: Mined invariant candidates from miner.py.
        threshold:  Minimum score to survive (default: QUALITY_THRESHOLD).

    Returns:
        Filtered list of CandidateInvariant, original order preserved.
    """
    return [
        qs.candidate
        for qs in score_candidates(candidates)
        if qs.score >= threshold
    ]
