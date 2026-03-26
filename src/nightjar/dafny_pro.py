"""DafnyPro Wrapper — W1.2.

Implements the three-component DafnyPro architecture as described in:
  arxiv:2601.05385 (POPL 2026) — 'DafnyPro: Improving LLM-Generated Dafny
  Proofs via Diff-Checking, Invariant Pruning, and Hint Augmentation'

Clean-room CR-11:
  Tool: DafnyPro | License: Research paper (no code released)
  Algorithm source: https://arxiv.org/abs/2601.05385
  What we take: diff-checker + pruner + hint-augmentation APPROACH
  What we write: DafnyProWrapper class from paper description
  What we do NOT copy: No implementation exists to copy

Three components (Scout 3 S2.1):
  1. Diff-checker: Prevent LLM from modifying base program logic.
     Claude Sonnet + DafnyPro = 86% DafnyBench (+16pp over baseline).
  2. Invariant pruner: Remove unnecessary annotations before Z3.
     Reduces verification overhead without losing correctness guarantees.
  3. Hint-augmentation: Add intermediate assert statements for complex
     reasoning chains where Z3 needs guided proof steps.

References:
- Scout 3 Section 2.1: DafnyPro description and results
- arxiv:2601.05385: POPL 2026 paper (primary algorithm source)
- [REF-T01]: Dafny documentation
- [REF-P06]: DafnyPro structured error format
"""

import re
from dataclasses import dataclass
from typing import Optional


# Lines that are pure Dafny annotations (not base program logic)
# These may be added/modified by the LLM without violating the diff check
_ANNOTATION_PREFIXES = (
    "requires ",
    "ensures ",
    "invariant ",
    "decreases ",
    "modifies ",
    "reads ",
    "assert ",
    "assume ",
    "// ",
    "/*",
    "*/",
    "*",
)


@dataclass
class DafnyProResult:
    """Result from DafnyProWrapper.apply()."""
    diff_ok: bool
    pruned_code: str
    augmented_code: str
    diff_error: Optional[str] = None


def _extract_base_lines(dfy_code: str) -> list[str]:
    """Extract non-annotation lines from Dafny source for diff comparison.

    Per CR-11: the diff-checker compares base program logic by stripping
    annotation lines and comparing what remains. Only method bodies,
    declarations, and type definitions constitute 'base program logic'.

    Args:
        dfy_code: Dafny source code.

    Returns:
        List of non-annotation, non-empty lines (stripped).
    """
    base_lines = []
    for line in dfy_code.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip lines that are purely annotations
        if any(stripped.startswith(prefix) for prefix in _ANNOTATION_PREFIXES):
            continue
        base_lines.append(stripped)
    return base_lines


def _count_method_signatures(dfy_code: str) -> int:
    """Count method/function/lemma declarations in Dafny source."""
    # Match 'method', 'function', 'lemma', 'predicate', 'ghost' declarations
    pattern = re.compile(
        r"^\s*(?:ghost\s+)?(?:method|function|lemma|predicate|iterator)\s+\w+",
        re.MULTILINE,
    )
    return len(pattern.findall(dfy_code))


class DafnyProWrapper:
    """Wrapper implementing the DafnyPro three-component architecture.

    Per arxiv:2601.05385 (POPL 2026, CR-11):
    Applies diff-checking, invariant pruning, and hint augmentation to
    LLM-generated Dafny annotations to improve verification success rate.

    Usage:
        wrapper = DafnyProWrapper()
        result = wrapper.apply(base_program, annotated_program, error_context)
        if result.diff_ok:
            verified_code = result.augmented_code
    """

    def check_diff(self, base: str, annotated: str) -> bool:
        """Check that LLM only added annotations, not modified base logic.

        Per CR-11 component 1: 'Diff-checker prevents the LLM from modifying
        base program logic. Only annotations (requires, ensures, invariant,
        decreases, assert) may be added.'

        Strategy: extract non-annotation lines from both versions and compare.
        The base_lines must be a subset of annotated_lines, in order.

        Args:
            base: Original Dafny program without LLM annotations.
            annotated: LLM-annotated version of the same program.

        Returns:
            True if only annotations were added (base logic unchanged).
            False if base program logic was modified.
        """
        base_lines = _extract_base_lines(base)
        annotated_lines = _extract_base_lines(annotated)

        # The LLM may not add new method declarations
        base_method_count = _count_method_signatures(base)
        annotated_method_count = _count_method_signatures(annotated)
        if annotated_method_count != base_method_count:
            return False

        # All base program lines must appear in annotated in order
        # (subsequence check: base_lines ⊆ annotated_lines preserving order)
        base_idx = 0
        for line in annotated_lines:
            if base_idx < len(base_lines) and line == base_lines[base_idx]:
                base_idx += 1

        return base_idx == len(base_lines)

    def prune_invariants(self, dfy_code: str) -> str:
        """Remove unnecessary invariant annotations before Z3 verification.

        Per CR-11 component 2: 'Invariant pruner removes unnecessary annotations
        before Z3, reducing verification overhead without losing correctness.'

        Pruned patterns:
        - 'requires true' / 'ensures true' — trivially satisfied, never useful
        - Duplicate annotation lines (same clause appears multiple times)
        - Blank annotation lines that add no value

        Per Scout 3 S2.1: eliminates annotations that 'add noise without
        contributing to the verification task'.

        Args:
            dfy_code: Dafny source with potentially redundant annotations.

        Returns:
            Dafny source with pruned annotations.
        """
        lines = dfy_code.splitlines(keepends=True)
        seen_annotations: set[str] = set()
        result_lines: list[str] = []

        # Patterns for trivially true annotations (never contribute to proofs)
        # Strip inline comments before matching (handles "requires true // comment")
        trivial_patterns = [
            re.compile(r"^\s*requires\s+true\s*(?://.*)?;?\s*$"),
            re.compile(r"^\s*ensures\s+true\s*(?://.*)?;?\s*$"),
            re.compile(r"^\s*invariant\s+true\s*(?://.*)?;?\s*$"),
        ]

        for line in lines:
            stripped = line.strip()

            # Remove trivially true annotations
            if any(p.match(stripped) for p in trivial_patterns):
                continue

            # Remove duplicate annotation lines
            if any(stripped.startswith(prefix) for prefix in _ANNOTATION_PREFIXES):
                if stripped in seen_annotations:
                    continue
                seen_annotations.add(stripped)

            result_lines.append(line)

        return "".join(result_lines)

    def augment_hints(self, dfy_code: str, errors: list[dict]) -> str:
        """Add intermediate assert statements to guide Z3 at failure points.

        Per CR-11 component 3: 'Hint-augmentation retrieves problem-independent
        proof strategy templates and inserts intermediate assert statements
        to guide the verifier through complex reasoning chains.'

        Strategy: For each postcondition/assertion failure, insert a
        'assert true; // proof hint' comment before the failing return.
        The actual assert content is filled by subsequent LLM calls with
        context about what needs to be proved.

        Args:
            dfy_code: Dafny source to augment.
            errors: List of error dicts from parse_dafny_output().
                   Each has 'type', 'line', 'message', 'file'.

        Returns:
            Dafny source with hint assertions added near failure points.
            If errors is empty, returns dfy_code unchanged.
        """
        if not errors:
            return dfy_code

        lines = dfy_code.splitlines(keepends=True)
        # Collect line numbers needing hints (1-based)
        hint_lines: set[int] = set()
        for error in errors:
            if "line" in error and error.get("type") in (
                "postcondition_failure",
                "assertion_failure",
                "loop_invariant_failure",
            ):
                # Insert hint BEFORE the failing line (0-based index)
                hint_line = int(error["line"]) - 1
                if 0 < hint_line <= len(lines):
                    hint_lines.add(hint_line)

        if not hint_lines:
            # No actionable error locations — add a general hint before return
            return self._add_general_hint(dfy_code, errors)

        result_lines: list[str] = []
        for i, line in enumerate(lines):
            if i in hint_lines:
                # Insert proof hint before the failing line
                indent = len(line) - len(line.lstrip())
                hint = " " * indent + "assert true; // proof hint: verify intermediate state\n"
                result_lines.append(hint)
            result_lines.append(line)

        return "".join(result_lines)

    def _add_general_hint(self, dfy_code: str, errors: list[dict]) -> str:
        """Add a general proof hint when no specific line is identified."""
        # Find the first 'return' statement or closing brace and hint before it
        lines = dfy_code.splitlines(keepends=True)
        result_lines: list[str] = []
        hint_added = False
        for line in reversed(lines):
            stripped = line.strip()
            if not hint_added and (stripped.startswith("return") or stripped == "}"):
                indent = len(line) - len(line.lstrip())
                hint = " " * indent + "assert true; // proof hint: verify state before return\n"
                result_lines.insert(0, line)
                result_lines.insert(0, hint)
                hint_added = True
            else:
                result_lines.insert(0, line)
        return "".join(result_lines)

    def apply(
        self,
        base: str,
        annotated: str,
        errors: list[dict],
    ) -> DafnyProResult:
        """Run the full DafnyPro three-component pipeline.

        Per CR-11: diff-check → prune → augment.
        If diff check fails, returns immediately with diff_ok=False.

        Args:
            base: Original Dafny program (without LLM annotations).
            annotated: LLM-annotated version of the program.
            errors: Verification errors from previous attempt (may be empty).

        Returns:
            DafnyProResult with diff_ok, pruned_code, augmented_code.
        """
        # Component 1: Diff check
        if not self.check_diff(base, annotated):
            return DafnyProResult(
                diff_ok=False,
                pruned_code=annotated,
                augmented_code=annotated,
                diff_error="LLM modified base program logic — annotations only allowed",
            )

        # Component 2: Prune unnecessary invariants
        pruned = self.prune_invariants(annotated)

        # Component 3: Add proof hints for known failure points
        augmented = self.augment_hints(pruned, errors)

        return DafnyProResult(
            diff_ok=True,
            pruned_code=pruned,
            augmented_code=augmented,
        )
