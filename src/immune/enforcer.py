"""icontract runtime enforcement of verified invariants.

Takes verified invariants and generates icontract @require/@ensure decorators
that are injected into generated code as runtime guards. These decorators fire
in production and feed back into the immune system's collection loop when
violations occur.

The icontract library provides informative violation messages that include
the violated condition and the actual values, which makes them ideal for
feeding back into the invariant mining pipeline.

References:
- [REF-T10] icontract — Python Design by Contract (@require, @ensure, @invariant)
- [REF-C09] Immune System / Acquired Immunity — runtime enforcement stage
"""

import re
import textwrap
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class InvariantSpec:
    """Specification for a single invariant to enforce. [REF-T10]

    Attributes:
        expression: Python expression (e.g., 'result >= 0' or 'x > 0').
        explanation: Human-readable explanation.
        is_precondition: If True, becomes @require; if False, @ensure.
            Auto-detected if not explicitly set: expressions containing
            'result' are postconditions, others are preconditions.
    """
    expression: str
    explanation: str = ""
    _is_precondition: Optional[bool] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._is_precondition is None:
            # Auto-detect: 'result' in expression → postcondition
            self._is_precondition = not bool(
                re.search(r'\bresult\b', self.expression)
            )

    @property
    def is_precondition(self) -> bool:
        return self._is_precondition  # type: ignore[return-value]

    @is_precondition.setter
    def is_precondition(self, value: bool) -> None:
        self._is_precondition = value

    def __init__(
        self,
        expression: str,
        explanation: str = "",
        is_precondition: Optional[bool] = None,
    ) -> None:
        self.expression = expression
        self.explanation = explanation
        self._is_precondition = is_precondition
        self.__post_init__()


def parse_invariant_to_contract(
    expression: str,
    explanation: str = "",
) -> str:
    """Convert an invariant expression to an icontract decorator string.

    Determines whether the expression is a precondition (@require) or
    postcondition (@ensure) based on whether it references 'result'.

    For @ensure decorators, 'result' is mapped to icontract's 'result'
    parameter which captures the return value. [REF-T10]

    Args:
        expression: Python boolean expression.
        explanation: Optional human-readable description.

    Returns:
        A string containing the icontract decorator (e.g.,
        '@icontract.ensure(lambda result: result >= 0, "Non-negative")').
    """
    has_result = bool(re.search(r'\bresult\b', expression))

    if has_result:
        # Postcondition — use @ensure with result parameter [REF-T10]
        # Extract parameter names from expression (excluding 'result')
        params = _extract_lambda_params(expression, include_result=True)
        lambda_str = f"lambda {params}: {expression}"
        decorator_type = "ensure"
    else:
        # Precondition — use @require [REF-T10]
        params = _extract_lambda_params(expression, include_result=False)
        lambda_str = f"lambda {params}: {expression}"
        decorator_type = "require"

    if explanation:
        return f'@icontract.{decorator_type}({lambda_str}, "{explanation}")'
    return f"@icontract.{decorator_type}({lambda_str})"


def _extract_lambda_params(expression: str, include_result: bool = False) -> str:
    """Extract variable names from an expression for the lambda signature.

    Finds all identifiers in the expression that could be function parameters.
    Excludes Python builtins and common functions.
    """
    # Find all identifiers
    identifiers = set(re.findall(r'\b([a-zA-Z_]\w*)\b', expression))

    # Remove Python builtins, keywords, and common functions
    excluded = {
        'True', 'False', 'None', 'and', 'or', 'not', 'in', 'is',
        'len', 'abs', 'min', 'max', 'sum', 'int', 'float', 'str',
        'bool', 'list', 'dict', 'set', 'tuple', 'isinstance', 'type',
        'range', 'sorted', 'reversed', 'enumerate', 'zip', 'map',
        'filter', 'any', 'all', 'print', 'hasattr', 'getattr',
    }

    params = sorted(identifiers - excluded)

    if not include_result and 'result' in params:
        params.remove('result')

    return ", ".join(params) if params else "_"


def generate_enforced_source(
    func_source: str,
    func_name: str,
    invariants: list[InvariantSpec],
) -> str:
    """Generate source code with icontract decorators injected.

    Takes the original function source and a list of verified invariants,
    then produces new source with:
    1. An 'import icontract' statement at the top
    2. @icontract.require decorators for preconditions (before the def)
    3. @icontract.ensure decorators for postconditions (before the def)

    The function body remains unchanged. [REF-T10]

    Args:
        func_source: Original Python source code of the function.
        func_name: Name of the function to decorate.
        invariants: List of InvariantSpec objects to enforce.

    Returns:
        Modified source code with icontract decorators injected.
    """
    source = textwrap.dedent(func_source).rstrip()
    lines = source.split("\n")

    # Find the def line
    def_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith(f"def {func_name}(") or line.strip().startswith(f"def {func_name} ("):
            def_idx = i
            break

    if def_idx == -1:
        # Function not found — return with import only
        return f"import icontract\n\n{source}\n"

    # Determine indentation of the def line
    def_line = lines[def_idx]
    indent = def_line[:len(def_line) - len(def_line.lstrip())]

    # Build decorator lines — preconditions first, then postconditions [REF-T10]
    pre_decorators = []
    post_decorators = []

    for inv in invariants:
        decorator = parse_invariant_to_contract(inv.expression, inv.explanation)
        if inv.is_precondition:
            pre_decorators.append(f"{indent}{decorator}")
        else:
            post_decorators.append(f"{indent}{decorator}")

    # Insert decorators before the def line (preconditions first)
    all_decorators = pre_decorators + post_decorators
    new_lines = (
        ["import icontract", ""]
        + lines[:def_idx]
        + all_decorators
        + lines[def_idx:]
    )

    return "\n".join(new_lines) + "\n"


# ---------------------------------------------------------------------------
# U2.4 — Temporal Fact Supersession [Supermemory pattern]
# ---------------------------------------------------------------------------


@dataclass
class TemporalInvariant:
    """Invariant with temporal metadata for lifecycle management.

    Implements the dynamic layer of the Supermemory temporal fact model
    (https://github.com/supermemoryai/supermemory): runtime-observed invariants
    carry timestamps and confidence that decays exponentially over time without
    new observations. When system behavior legitimately evolves, old invariants
    are superseded rather than deleted, preserving audit history.

    Attributes:
        expression: Python boolean expression (e.g., 'x >= 0').
        explanation: Human-readable description.
        timestamp: Unix timestamp of the most recent confirming observation.
        observation_count: How many times this invariant has been confirmed.
        confidence: Base confidence score [0.0, 1.0] at time of last observation.
        superseded_by: Expression of the newer invariant that replaced this one,
            or None if still active.
        half_life: Seconds until confidence halves without new observations.
            Default: 86400 (one day).

    References:
        - Supermemory temporal fact model — static+dynamic layers, conflict resolution (MIT)
        - [REF-T10] icontract — runtime contract enforcement
    """

    expression: str
    explanation: str = ""
    timestamp: float = field(default_factory=time.time)
    observation_count: int = 1
    confidence: float = 1.0
    superseded_by: Optional[str] = None
    half_life: float = 86400.0  # seconds — default one day


class InvariantStore:
    """Manages temporal invariants with Supermemory-style supersession.

    Implements the Supermemory temporal fact model with two conceptual layers:

    - **Static layer**: formally verified invariants (confidence = 1.0, no decay
      expected — they are verified by the formal pipeline).
    - **Dynamic layer**: runtime-observed invariants that gain confidence via
      repeated observation and lose it via exponential decay when observations stop.

    New runtime observations can *supersede* old invariants when system behavior
    legitimately evolves, preventing stale contract enforcement.

    Decay formula (Supermemory exponential model):
        confidence(t) = base_confidence * 0.5 ^ (elapsed_seconds / half_life)

    After one half_life without a new observation, confidence halves.

    References:
        - Supermemory temporal fact model — https://github.com/supermemoryai/supermemory
        - [REF-T10] icontract
    """

    def __init__(self) -> None:
        # Keyed by expression string. Multiple entries may exist for the same
        # logical constraint when supersession has occurred (the old entry is
        # retained for audit, marked with superseded_by != None).
        self._invariants: dict[str, TemporalInvariant] = {}

    def add_observation(
        self,
        expression: str,
        explanation: str = "",
        timestamp: Optional[float] = None,
        confidence: float = 1.0,
    ) -> TemporalInvariant:
        """Add or update an invariant based on a new observation.

        If the expression already exists, increment its observation_count and
        update the timestamp to the latest observation time (reinforcing it).
        Otherwise, create a new TemporalInvariant.

        Args:
            expression: Python boolean expression.
            explanation: Human-readable description.
            timestamp: Unix time of the observation (defaults to now).
            confidence: Base confidence of this observation [0.0, 1.0].

        Returns:
            The updated or newly created TemporalInvariant.
        """
        if timestamp is None:
            timestamp = time.time()

        if expression in self._invariants:
            inv = self._invariants[expression]
            inv.observation_count += 1
            inv.timestamp = timestamp
            if explanation:
                inv.explanation = explanation
            return inv

        inv = TemporalInvariant(
            expression=expression,
            explanation=explanation,
            timestamp=timestamp,
            confidence=confidence,
        )
        self._invariants[expression] = inv
        return inv

    def supersede(
        self,
        old_expression: str,
        new_expression: str,
        explanation: str = "",
        timestamp: Optional[float] = None,
    ) -> TemporalInvariant:
        """Mark old_expression as superseded by new_expression.

        The old invariant is marked with superseded_by = new_expression so it
        is excluded from active enforcement but retained for audit.  A new
        TemporalInvariant is created (or updated) for new_expression.

        This implements the Supermemory conflict-resolution model: when new
        runtime observations contradict an old invariant, the old fact is
        superseded rather than deleted, preserving a traceable history of how
        system behaviour evolved.

        Args:
            old_expression: Expression of the invariant being replaced.
            new_expression: Expression of the superseding invariant.
            explanation: Why supersession occurred (stored on the new invariant).
            timestamp: Time of supersession (defaults to now).

        Returns:
            The new (superseding) TemporalInvariant.
        """
        if timestamp is None:
            timestamp = time.time()

        # Mark old invariant as superseded (retain for audit, not enforcement)
        if old_expression in self._invariants:
            self._invariants[old_expression].superseded_by = new_expression

        # Create or update the superseding invariant
        return self.add_observation(
            new_expression,
            explanation=explanation,
            timestamp=timestamp,
        )

    def get_active_invariants(
        self,
        current_time: Optional[float] = None,
    ) -> list[TemporalInvariant]:
        """Return all non-superseded invariants.

        Invariants with superseded_by != None are excluded — they represent
        stale facts that have been replaced by newer observations.

        Args:
            current_time: Reference time (unused here; provided for API
                symmetry with get_confidence).

        Returns:
            List of active TemporalInvariant objects.
        """
        return [
            inv for inv in self._invariants.values()
            if inv.superseded_by is None
        ]

    def get_confidence(
        self,
        expression: str,
        current_time: Optional[float] = None,
    ) -> float:
        """Return current confidence for an expression with exponential decay.

        Computes:
            confidence(t) = base_confidence * 0.5 ^ (elapsed_seconds / half_life)

        After one half_life without a new observation, confidence halves.
        After two half_lives, confidence is 0.25.  And so on.

        Args:
            expression: The invariant expression to query.
            current_time: Reference time for computing elapsed seconds
                (defaults to now).

        Returns:
            Decayed confidence in [0.0, 1.0], or 0.0 if expression not found.
        """
        if expression not in self._invariants:
            return 0.0

        inv = self._invariants[expression]
        if current_time is None:
            current_time = time.time()

        elapsed = current_time - inv.timestamp
        decayed = inv.confidence * (0.5 ** (elapsed / inv.half_life))
        return max(0.0, min(1.0, decayed))
