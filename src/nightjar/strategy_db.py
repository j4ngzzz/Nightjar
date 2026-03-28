"""PBT strategy template database for adaptive test generation.

Maintains a history of which Hypothesis strategy templates have been
effective at finding counterexamples for specific invariant types.
When generating tests, retrieves the best-performing template as a
prompt "parent" to guide LLM fallback generation.

AlphaEvolve programs database concept applied to PBT strategy selection:
parent template (best performer) + diverse template (inspiration) are
provided to the LLM fallback as examples.

References:
- AlphaEvolve arXiv:2506.13131 — programs database, parent/inspiration selection
- [REF-T03] Hypothesis — strategy templates
- [REF-T16] litellm — LLM fallback
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class StrategyRecord:
    """A single strategy template with performance statistics."""

    invariant_type: str           # e.g., "numeric_bound", "string_format"
    template_name: str            # human-readable name
    template_code: str            # Hypothesis strategy snippet
    counterexample_found_rate: float = 0.0   # fraction of runs that found CE
    avg_examples_to_find: float = 100.0      # avg Hypothesis examples before CE
    run_count: int = 0            # total times this template was used


class StrategyDB:
    """Programs database for PBT strategy templates.

    Inspired by AlphaEvolve (arXiv:2506.13131) programs database:
    - Parent selection: highest counterexample_found_rate (exploit)
    - Inspiration selection: lowest run_count (explore)
    - EMA updates preserve historical signal while adapting to new data

    Seeded with 6 initial templates covering the most common invariant
    types encountered in real-world .card.md specs.
    """

    def __init__(self, db_path: str = ".card/cache/strategy_db.json") -> None:
        self.db_path = db_path
        self.records: list[StrategyRecord] = []
        self.load()
        if not self.records:
            self.records = self._seed_initial_templates()

    # ------------------------------------------------------------------
    # Seed
    # ------------------------------------------------------------------

    def _seed_initial_templates(self) -> list[StrategyRecord]:
        """Create 6 initial templates covering common invariant types."""
        return [
            StrategyRecord(
                invariant_type="numeric_bound",
                template_name="numeric_bound",
                template_code="st.integers(min_value=-1000, max_value=1000)",
            ),
            StrategyRecord(
                invariant_type="numeric_bound",
                template_name="numeric_nonneg",
                template_code="st.integers(min_value=0, max_value=10000)",
            ),
            StrategyRecord(
                invariant_type="string_format",
                template_name="string_nonempty",
                template_code="st.text(min_size=1, max_size=100)",
            ),
            StrategyRecord(
                invariant_type="string_format",
                template_name="string_format",
                template_code=(
                    "st.from_regex(r'[a-zA-Z0-9._%+-]+"
                    r"@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}')"
                ),
            ),
            StrategyRecord(
                invariant_type="collection_size",
                template_name="collection_size",
                template_code="st.lists(st.integers(), min_size=1, max_size=50)",
            ),
            StrategyRecord(
                invariant_type="boolean_flag",
                template_name="boolean_flag",
                template_code="st.booleans()",
            ),
        ]

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_best_for_type(self, invariant_type: str) -> StrategyRecord | None:
        """Return the record with the highest counterexample_found_rate.

        Returns None if no records match the given invariant_type.
        """
        matching = [r for r in self.records if r.invariant_type == invariant_type]
        if not matching:
            return None
        return max(matching, key=lambda r: r.counterexample_found_rate)

    def get_diverse_for_type(self, invariant_type: str) -> StrategyRecord | None:
        """Return the record with the lowest run_count (least explored).

        Encourages diversity by biasing selection toward under-tried templates.
        Returns None if no records match the given invariant_type.
        """
        matching = [r for r in self.records if r.invariant_type == invariant_type]
        if not matching:
            return None
        return min(matching, key=lambda r: r.run_count)

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        invariant_type: str,
        template_name: str,
        found_counterexample: bool,
        examples_taken: int,
    ) -> None:
        """Update stats for a template using exponential moving average.

        EMA weights: 0.7 * old + 0.3 * new — preserves historical signal
        while adapting to recent outcomes [AlphaEvolve fitness feedback].

        Creates a new record if no match exists.
        """
        # Find existing record
        record: StrategyRecord | None = None
        for r in self.records:
            if r.invariant_type == invariant_type and r.template_name == template_name:
                record = r
                break

        if record is None:
            # Create a new record for this type/template combo
            record = StrategyRecord(
                invariant_type=invariant_type,
                template_name=template_name,
                template_code="",
            )
            self.records.append(record)

        # EMA update: 0.7 * old + 0.3 * new
        record.counterexample_found_rate = (
            0.7 * record.counterexample_found_rate + 0.3 * float(found_counterexample)
        )
        record.avg_examples_to_find = (
            0.7 * record.avg_examples_to_find + 0.3 * float(examples_taken)
        )
        record.run_count += 1

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist records to JSON. Silently swallows all errors."""
        try:
            path = Path(self.db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            data = [asdict(r) for r in self.records]
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass  # DB failure must never crash PBT

    def load(self) -> None:
        """Load records from JSON. Silently continues with empty list on error."""
        try:
            path = Path(self.db_path)
            if not path.exists():
                return
            data: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
            self.records = [StrategyRecord(**item) for item in data]
        except Exception:  # noqa: BLE001
            self.records = []  # Fall back to seeds (caller will re-seed if empty)


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------

def classify_invariant_type(invariant_statement: str) -> str:
    """Classify an invariant statement into a strategy type via regex.

    Categories (in priority order):
    - "collection_size" — contains len() / size / count references (checked first)
    - "numeric_bound"   — contains numeric comparison operators or bound keywords
    - "string_format"   — contains email / @ / uuid format hints
    - "boolean_flag"    — contains True / False / bool keywords
    - "unknown"         — no pattern matched

    Args:
        invariant_statement: Natural-language invariant from .card.md.

    Returns:
        One of the category strings listed above.
    """
    s = invariant_statement

    # collection_size checked FIRST — "len(result) > 0" should be collection_size
    # not numeric_bound, because the distinguishing marker is len() / size / count.
    if re.search(r"len\s*\(|size|count", s, re.IGNORECASE):
        return "collection_size"

    # numeric_bound: comparison operators or bound keywords
    if re.search(r">=\s*0|>\s*0|<=\s*\d|>=\s*\d|<\s*\d", s):
        return "numeric_bound"

    # string_format: email, @-symbol, or UUID hints
    if re.search(r"email|@|uuid", s, re.IGNORECASE):
        return "string_format"

    # boolean_flag: True / False / bool keywords
    if re.search(r"\bTrue\b|\bFalse\b|\bbool\b", s):
        return "boolean_flag"

    return "unknown"
