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

Multi-objective dimensions (AlphaEvolve MAP-Elites):
  - coverage_score: fraction of execution traces satisfying the invariant
  - specificity_score: inverse tautology-ness (0=tautology, 1=narrow)
  - falsifiability_score: estimated probability defective code violates it

Wire: miner.py → quality_scorer.py → enricher.py

References:
  REF-NEW-05: Wonda (arxiv 2603.15510)
  [REF-C05] Dynamic Invariant Mining
  AlphaEvolve MAP-Elites: Mouret & Clune 2015
"""

from __future__ import annotations

import ast
import dataclasses
import random
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

    Multi-objective dimensions are populated by score_candidate_multidim().
    They are NOT populated by score_candidate() — all default to 0.0/False
    to preserve backward compatibility with existing callers.
    """

    candidate: CandidateInvariant
    score: float           # [0.0, 1.0]
    is_trivial: bool       # tautology or semantically vacuous
    is_valid_syntax: bool  # parses as a valid Python expression
    reason: str            # human-readable explanation

    # New multi-objective dimensions (AlphaEvolve MAP-Elites)
    # All have defaults — existing callers need not change.
    coverage_score: float = 0.0       # fraction of traces satisfying this invariant
    specificity_score: float = 0.0    # inverse tautology-ness; 0=tautology, 1=narrow
    falsifiability_score: float = 0.0 # estimated P(defective code violates this)
    is_map_elite: bool = False         # True if this occupies a cell in the MAP-Elites archive


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


def _compute_specificity(tree: ast.Expression) -> float:
    """Measure how specific (non-tautological) an invariant AST is.

    AlphaEvolve MAP-Elites: specificity is one behavioural axis of the
    quality grid. Tautologies occupy the lowest bucket; narrow equality
    constraints occupy the highest.

    Patterns (highest-to-lowest specificity):
      - Literal comparison (x == constant)  → 0.9
      - Range comparison (x > 0 and x < N)  → 0.8
      - Membership test (x in set/list)      → 0.7
      - Single-sided bound (x > 0)           → 0.6
      - Unknown / complex expression         → 0.5
      - Tautology (True / identity)          → 0.0  (caught upstream)

    Args:
        tree: Parsed ast.Expression from the invariant text.

    Returns:
        Specificity score in [0.0, 1.0].
    """
    node = tree.body

    # Tautology guard (should be caught by _is_trivial first, but be safe)
    if isinstance(node, ast.Constant):
        return 0.0

    if isinstance(node, ast.Compare):
        ops = node.ops
        comparators = node.comparators

        # Literal equality: x == <constant>
        if (
            len(ops) == 1
            and isinstance(ops[0], ast.Eq)
            and isinstance(comparators[0], ast.Constant)
        ):
            return 0.9

        # Single-sided bound: x > 0, x < 100, x >= 0, x <= N
        if len(ops) == 1 and isinstance(ops[0], (ast.Gt, ast.Lt, ast.GtE, ast.LtE)):
            return 0.6

        # Membership test: x in <something>
        if len(ops) == 1 and isinstance(ops[0], ast.In):
            return 0.7

    # Boolean and: look for range pattern (x > A and x < B)
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
        bound_count = 0
        for value in node.values:
            if isinstance(value, ast.Compare) and len(value.ops) == 1:
                if isinstance(value.ops[0], (ast.Gt, ast.Lt, ast.GtE, ast.LtE)):
                    bound_count += 1
        if bound_count >= 2:
            return 0.8

    # Unknown / complex expression — conservative mid-point
    return 0.5


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


def score_candidate_multidim(
    candidate: CandidateInvariant,
    coverage_evidence: float | None = None,
) -> QualityScore:
    """Score a candidate invariant across multiple quality dimensions.

    Extends score_candidate() with AlphaEvolve MAP-Elites multi-objective
    dimensions. The base `score` field is unchanged; the new fields enable
    diversity-preserving selection in MapElitesArchive.

    Args:
        candidate:         Mined invariant candidate.
        coverage_evidence: Fraction of execution traces that satisfy this
                           invariant, if measured externally. Falls back to
                           candidate.confidence as a proxy when None.

    Returns:
        QualityScore with coverage_score, specificity_score, and
        falsifiability_score populated.
    """
    base = score_candidate(candidate)

    # Coverage: use external evidence if provided, else confidence as proxy
    coverage = coverage_evidence if coverage_evidence is not None else candidate.confidence

    # Specificity: AST pattern matching
    if base.is_valid_syntax and not base.is_trivial:
        try:
            tree = ast.parse(candidate.expression.strip(), mode="eval")
            specificity = _compute_specificity(tree)
        except SyntaxError:
            specificity = 0.0
    else:
        specificity = 0.0

    # Falsifiability: proxy — high specificity → more falsifiable
    falsifiability = specificity * 0.8

    return QualityScore(
        candidate=base.candidate,
        score=base.score,
        is_trivial=base.is_trivial,
        is_valid_syntax=base.is_valid_syntax,
        reason=base.reason,
        coverage_score=max(0.0, min(1.0, coverage)),
        specificity_score=specificity,
        falsifiability_score=max(0.0, min(1.0, falsifiability)),
        is_map_elite=False,
    )


# ── MapElitesArchive ──────────────────────────────────────────────────────────


class MapElitesArchive:
    """MAP-Elites style archive for invariant diversity.

    Grid: coverage_bucket (0-4) x specificity_bucket (0-4) = 25 cells.
    Each cell holds the highest-scoring QualityScore in that region.
    Prevents invariant population from converging to only one type.

    Reference: AlphaEvolve programs database, MAP-Elites (Mouret & Clune 2015).
    """

    def __init__(self) -> None:
        self._archive: dict[tuple[int, int], QualityScore] = {}

    @staticmethod
    def _bucket(score: float) -> int:
        """Map a score in [0.0, 1.0] to a bucket index in [0, 4].

        Uses min(4, int(score * 5)) so that exactly 1.0 maps to bucket 4
        (not 5).
        """
        return min(4, int(score * 5))

    def update(self, qs: QualityScore) -> bool:
        """Attempt to insert a QualityScore into the archive.

        Accepts the candidate if its cell is empty or if it scores higher
        than the current occupant. Marks accepted entries with is_map_elite=True.

        Args:
            qs: A QualityScore (typically from score_candidate_multidim).

        Returns:
            True if qs was accepted into (or updated) its cell; False otherwise.
        """
        cell = (self._bucket(qs.coverage_score), self._bucket(qs.specificity_score))
        current = self._archive.get(cell)
        if current is None or qs.score > current.score:
            # Store a copy with is_map_elite=True
            elite = dataclasses.replace(qs, is_map_elite=True)
            self._archive[cell] = elite
            return True
        return False

    def get_all_elites(self) -> list[QualityScore]:
        """Return all QualityScore entries currently in the archive."""
        return list(self._archive.values())

    def get_diverse_sample(self, n: int) -> list[QualityScore]:
        """Randomly sample up to n entries from distinct archive cells.

        Args:
            n: Maximum number of samples to return.

        Returns:
            Up to n QualityScore entries sampled without replacement from
            occupied cells. If fewer than n cells are occupied, all are returned.
        """
        elites = self.get_all_elites()
        if len(elites) <= n:
            return elites
        return random.sample(elites, n)

    def size(self) -> int:
        """Return the number of occupied cells in the archive."""
        return len(self._archive)
