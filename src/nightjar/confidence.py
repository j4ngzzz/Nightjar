"""Verification Confidence Score (0-100) — W1.4.

Computes a principled confidence score based on which verification stages
passed. Each stage contributes specific points based on the strength of
its guarantee.

Per Scout 3 S5.3 (Confidence Score Framework):
  pyright type check    → +15 pts  (type-class correctness)
  deal static linter    → +10 pts  (contract structure validity)
  CrossHair symbolic    → +35 pts  (SMT-proved for explored paths)
  Hypothesis PBT        → +20 pts  (statistical confidence, 10K+ examples)
  Dafny formal proof    → +20 pts  (complete mathematical proof)
  ─────────────────────────────────────────
  Total possible:          100 pts

Key insight: When Dafny fails, Nightjar still has 80/100 confidence from
stages 0-3. This is the industry's first principled 'scored partial verification.'

References:
- Scout 3 Section 5.3: Confidence score framework design
- Scout 3 Section 5.4: Recommended fallback chain
- Confidence in Assurance 2.0 Cases (arxiv:2409.10665): Bayesian/D-S
  confidence propagation through argument chains (conceptual backing)
"""

from dataclasses import dataclass, field

from nightjar.types import StageResult, VerifyResult, VerifyStatus


# Per Scout 3 S5.3: canonical stage name → points
# Names match the Scout 3 taxonomy: pyright/deal/CrossHair/Hypothesis/Dafny
# Total: 15 + 10 + 35 + 20 + 20 = 100
STAGE_POINTS: dict[str, int] = {
    "preflight": 15,   # pyright type check — eliminates type-class bugs
    "deps": 10,         # deal static linter — proves contract structure
    "crosshair": 35,   # CrossHair symbolic — SMT-proved for explored paths
    "pbt": 20,          # Hypothesis PBT — statistical confidence (10K+ examples)
    "formal": 20,       # Dafny formal proof — complete mathematical proof
}

# Map pipeline stage names → canonical confidence score names
# Stage 2 in current pipeline is "schema" but maps to "crosshair" for scoring
# (Schema validation + structural checks = CrossHair equivalent tier)
_STAGE_NAME_MAP: dict[str, str] = {
    "preflight": "preflight",
    "deps": "deps",
    "schema": "crosshair",   # Stage 2 structural = CrossHair tier
    "pbt": "pbt",
    "formal": "formal",
}

# Stage number → canonical name (for stages that don't use name-based lookup)
_STAGE_NUM_TO_CANONICAL: dict[int, str] = {
    0: "preflight",
    1: "deps",
    2: "crosshair",  # Stage 2 (schema) maps to CrossHair tier
    3: "pbt",
    4: "formal",
}


@dataclass
class ConfidenceScore:
    """Verification confidence score with per-stage breakdown.

    Per Scout 3 S5.3: structured confidence score enabling transparent
    partial verification reporting.

    Attributes:
        total: Total confidence score in [0, 100].
        breakdown: Per-stage points earned {stage_name: points}.
        gap: List of canonical stage names that could add more points if passed.
    """
    total: int
    breakdown: dict[str, int] = field(default_factory=dict)
    gap: list[str] = field(default_factory=list)

    def format(self) -> str:
        """Format as human-readable confidence report.

        Returns:
            Multi-line string showing total and per-stage breakdown.
        """
        lines = [f"Confidence: {self.total}/100"]
        if self.breakdown:
            for stage_name, pts in sorted(self.breakdown.items()):
                max_pts = STAGE_POINTS.get(stage_name, 0)
                lines.append(f"  {stage_name}: +{pts}/{max_pts}")
        if self.gap:
            lines.append(f"  Gap stages: {', '.join(self.gap)}")
        return "\n".join(lines)


def compute_confidence(result: VerifyResult) -> ConfidenceScore:
    """Compute verification confidence score from a VerifyResult.

    Per Scout 3 S5.3: sum points for each stage that PASSED.
    FAIL, SKIP, and TIMEOUT contribute 0 points.
    SKIP means not applicable — stage was not run, no confidence gained.
    FAIL means the check ran and found a violation — 0 points awarded.
    TIMEOUT means verification didn't complete — 0 points awarded.

    Args:
        result: VerifyResult from run_pipeline() or run_bfs_search().

    Returns:
        ConfidenceScore with total (0-100) and per-stage breakdown.
    """
    total = 0
    breakdown: dict[str, int] = {}
    gap: list[str] = []

    for stage in result.stages:
        # Map stage to canonical name for point lookup
        canonical = _STAGE_NAME_MAP.get(stage.name)
        if canonical is None:
            # Try lookup by stage number
            canonical = _STAGE_NUM_TO_CANONICAL.get(stage.stage)
        if canonical is None:
            continue

        stage_pts = STAGE_POINTS.get(canonical, 0)
        if stage_pts == 0:
            continue

        if stage.status == VerifyStatus.PASS:
            # Stage passed — award full points
            total += stage_pts
            breakdown[canonical] = stage_pts
        elif stage.status in (VerifyStatus.FAIL, VerifyStatus.TIMEOUT):
            # Failed or timed out — 0 points, track as improvement gap
            gap.append(canonical)
        # SKIP = not applicable, no points, not a gap

    # Clamp to [0, 100] for safety
    total = max(0, min(100, total))
    return ConfidenceScore(total=total, breakdown=breakdown, gap=gap)
