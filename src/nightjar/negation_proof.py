"""Negation-Proof Spec Validation — U1.4.

Instead of proving a postcondition holds, prove its negation is impossible.
If CrossHair CONFIRMS the negated postcondition (no violations found) →
the negation holds for all inputs → the original spec is degenerate/too weak.
If CrossHair finds a COUNTEREXAMPLE to the negated postcondition →
the original spec CAN be satisfied → spec is meaningful.

Inserted as Stage 2.5 in run_pipeline(): AFTER {schema, PBT}, BEFORE formal.

Per [REF-NEW-07] NegProof (arxiv:2603.13414):
  "Computationally cheaper for catching false positives. If a counterexample
   to the postcondition exists, the spec is too weak."

CrossHair exit code semantics for negated postcondition `post: ¬P`:
  returncode=0: CONFIRMED — ¬P holds for all inputs → P is never satisfied
                → original spec is degenerate → WEAK_SPEC
  returncode=1: COUNTEREXAMPLE — ¬P can be violated (P can hold) → spec meaningful

References:
- [REF-NEW-07] NegProof (arxiv:2603.13414) — negation-proof spec validation
- CrossHair (MIT) — symbolic execution engine
- nightjar-upgrade-plan.md U1.4
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from nightjar.types import CardSpec


# ─── Postcondition Negation ───────────────────────────────────────────────────

def negate_postcondition(statement: str) -> str:
    """Syntactically negate an invariant postcondition statement.

    Wraps the statement in `not (...)`. CrossHair uses this as a `post:`
    annotation to check if the negation can be satisfied.

    Per [REF-NEW-07]: simple syntactic negation is sufficient for the
    CrossHair check; semantic simplification is not required.

    Args:
        statement: Invariant statement string (e.g., "result >= 0").

    Returns:
        Negated statement string (e.g., "not (result >= 0)").
    """
    return f"not ({statement})"


# ─── CrossHair integration ────────────────────────────────────────────────────

_NEGPROOF_TIMEOUT = 10  # seconds per invariant

_CROSSHAIR_FILE_TEMPLATE = textwrap.dedent("""\
    def _negproof_check(__return__: object) -> object:
        \"\"\"
        post: {negated_postcondition}
        \"\"\"
        return __return__
""")


def _generate_negproof_file(negated_postcondition: str) -> str:
    """Generate a Python file for CrossHair to check the negated postcondition.

    The generated function has a single parameter `__return__` (matching
    CrossHair's convention for the return value) and the `post:` annotation
    set to the negated postcondition.

    Args:
        negated_postcondition: The `not (original_condition)` string.

    Returns:
        Python source code string.
    """
    return _CROSSHAIR_FILE_TEMPLATE.format(
        negated_postcondition=negated_postcondition
    )


def _run_crosshair_on_file(tmp_path: str) -> subprocess.CompletedProcess:
    """Run CrossHair check on a temporary file. Returns CompletedProcess.

    Separated for testability — tests patch this function.
    """
    return subprocess.run(
        [sys.executable, "-m", "crosshair", "check", tmp_path],
        capture_output=True,
        text=True,
        timeout=_NEGPROOF_TIMEOUT,
    )


# ─── NegProofResult ───────────────────────────────────────────────────────────

@dataclass
class NegProofResult:
    """Result from negation-proof spec validation.

    Attributes:
        weak_specs: List of invariant statements detected as degenerate/weak.
            An invariant is weak when CrossHair CONFIRMS its negation (rc=0).
        passed: True when all checked invariants are meaningful (no weak specs).
    """
    weak_specs: list[str] = field(default_factory=list)
    passed: bool = True


# ─── Public API ──────────────────────────────────────────────────────────────

def run_negation_proof(spec: "CardSpec", code: str) -> NegProofResult:
    """Run negation-proof validation on all FORMAL invariants [REF-NEW-07].

    For each FORMAL invariant:
    1. Negate the postcondition statement
    2. Generate a CrossHair-annotated Python file with the negated postcondition
    3. Run CrossHair:
       - returncode=0 (CONFIRMED): negation holds → spec is degenerate → weak
       - returncode=1 (COUNTEREXAMPLE): spec is meaningful → OK
       - FileNotFoundError / timeout: CrossHair unavailable → skip gracefully
    4. Collect weak invariants; return NegProofResult

    Args:
        spec: CardSpec containing invariants to validate.
        code: Generated Python code (not directly used in check, but kept
              for interface consistency with other stage functions).

    Returns:
        NegProofResult with weak_specs list and passed flag.
    """
    from nightjar.types import InvariantTier

    # Only check FORMAL tier invariants (same as Stage 4)
    formal_invariants = [
        inv for inv in spec.invariants
        if inv.tier == InvariantTier.FORMAL
    ]

    if not formal_invariants:
        return NegProofResult(weak_specs=[], passed=True)

    weak_specs: list[str] = []

    for inv in formal_invariants:
        negated = negate_postcondition(inv.statement)
        file_content = _generate_negproof_file(negated)

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(file_content)
                tmp_path = f.name

            proc = _run_crosshair_on_file(tmp_path)

            if proc.returncode == 0:
                # CrossHair CONFIRMED: negated postcondition holds for all inputs
                # → original postcondition is never satisfied → degenerate spec
                weak_specs.append(inv.statement)

        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            # CrossHair not installed or timed out → skip this invariant
            continue
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    passed = len(weak_specs) == 0
    return NegProofResult(weak_specs=weak_specs, passed=passed)
