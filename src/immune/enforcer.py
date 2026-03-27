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

import copy
import inspect
import re
import textwrap
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Optional


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


# ---------------------------------------------------------------------------
# U2.4-B — icontract @snapshot OLD-State Transition Postconditions [REF-T10]
# ---------------------------------------------------------------------------
# icontract's @snapshot decorator (Parquery/icontract _decorators.py) captures
# argument state *before* function execution and makes it available in
# postconditions via an OLD parameter:
#   @snapshot(lambda items: items.copy())
#   @ensure(lambda result, OLD: len(OLD['items']) + 1 == len(items))
#
# This section implements the same pattern natively (no icontract import at
# runtime) so state-transition invariants like "balance after >= balance before"
# can be checked directly by the immune system's enforcement loop.
# ---------------------------------------------------------------------------


class TransitionViolationError(Exception):
    """Raised when a state-transition postcondition (OLD pattern) is violated.

    Contains the violated expression and the pre/post states for diagnostics.
    """


class _OldState:
    """Proxy for the OLD dict in transition postconditions.

    icontract passes OLD as a keyword argument to postcondition lambdas.
    Supports both OLD['name'] (dict-style) and OLD.name (attribute-style)
    access so expressions can be written either way.
    """

    def __init__(self, state: dict) -> None:
        object.__setattr__(self, "_state", state)

    def __getitem__(self, key: str) -> Any:
        return self._state[key]

    def __getattr__(self, key: str) -> Any:
        try:
            return object.__getattribute__(self, "_state")[key]
        except KeyError:
            raise AttributeError(f"OLD has no snapshot named '{key}'") from None

    def __repr__(self) -> str:
        return f"OLD({self._state!r})"


def _extract_old_references(expression: str) -> set:
    """Extract argument names referenced via OLD in a postcondition expression.

    Recognises both OLD['name'] / OLD["name"] and OLD.name patterns,
    matching icontract's two access styles. [REF-T10]

    Args:
        expression: A Python boolean expression that may contain OLD references.

    Returns:
        Set of argument name strings referenced through OLD.
    """
    names: set = set()
    names.update(re.findall(r"\bOLD\[['\"](\w+)['\"]\]", expression))
    names.update(re.findall(r"\bOLD\.(\w+)", expression))
    return names


def capture_pre_state(
    func: Any,
    args: tuple,
    kwargs: dict,
    referenced_args: Optional[set] = None,
) -> dict:
    """Snapshot argument values before function execution (icontract @snapshot).

    Implements the icontract @snapshot pattern: for each argument that a
    transition postcondition references via OLD, capture its value before the
    function runs so the postcondition can compare pre/post state. [REF-T10]

    Only snapshots arguments listed in ``referenced_args`` to keep deep-copy
    overhead proportional to what is actually needed.

    Args:
        func: The function about to be called (used to bind positional args
            to parameter names via inspect.signature).
        args: Positional arguments tuple.
        kwargs: Keyword arguments dict.
        referenced_args: Set of argument names to snapshot. If None, all
            bound arguments are snapshotted.

    Returns:
        Dict mapping argument name → deep-copied (or copied) value.
        Arguments that cannot be copied are silently skipped with a warning.
    """
    try:
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
    except Exception:
        return {}

    pre_state: dict = {}
    for name, value in bound.arguments.items():
        if referenced_args is not None and name not in referenced_args:
            continue
        try:
            if isinstance(value, (list, dict, set, bytearray)):
                pre_state[name] = copy.deepcopy(value)
            else:
                try:
                    pre_state[name] = copy.copy(value)
                except Exception as copy_exc:
                    warnings.warn(
                        f"capture_pre_state: copy.copy failed for '{name}' "
                        f"({type(value).__name__}) — using live reference. {copy_exc}",
                        stacklevel=3,
                    )
                    pre_state[name] = value  # primitives / immutables are safe
        except Exception as exc:
            warnings.warn(
                f"capture_pre_state: could not snapshot argument '{name}' "
                f"({type(value).__name__}) — skipping. {exc}",
                stacklevel=3,
            )
    return pre_state


def check_transition_postcondition(
    pre_state: dict,
    post_state: dict,
    result: Any,
    invariant: dict,
) -> bool:
    """Evaluate a state-transition postcondition using captured OLD state.

    Provides the icontract OLD mechanism for expressions like:
        "result >= OLD['balance']"
        "len(items) == OLD['len_items'] + 1"
        "OLD.count <= result"

    The expression is evaluated in a controlled namespace containing OLD (the
    pre-call state proxy), result (the return value), and current post_state
    argument values. [REF-T10]

    Args:
        pre_state: Dict of argument values captured *before* the call
            (from capture_pre_state).
        post_state: Dict of argument values *after* the call (for mutable
            objects whose values changed in-place).
        result: The function's return value.
        invariant: Dict with at least an 'expression' key. Must contain 'OLD'
            to be treated as a transition postcondition; returns True otherwise.

    Returns:
        True if the postcondition holds (or is not a transition postcondition).
        Returns True on evaluation errors (fail-open) — a warning is emitted.
    """
    expression = invariant.get("expression", "")
    if not expression or "OLD" not in expression:
        return True  # Not a transition postcondition — nothing to check here

    OLD = _OldState(pre_state)

    namespace: dict = {
        "result": result,
        "OLD": OLD,
        # Safe builtins only — no __import__, no exec
        "len": len,
        "abs": abs,
        "min": min,
        "max": max,
        "sum": sum,
        "isinstance": isinstance,
        "bool": bool,
        "int": int,
        "float": float,
        "str": str,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "sorted": sorted,
        "reversed": reversed,
        "enumerate": enumerate,
        "zip": zip,
        "any": any,
        "all": all,
    }
    namespace.update(post_state)

    try:
        return bool(eval(expression, {"__builtins__": {}}, namespace))  # noqa: S307
    except Exception as exc:
        warnings.warn(
            f"check_transition_postcondition: could not evaluate "
            f"'{expression}': {exc}",
            stacklevel=2,
        )
        return True  # Fail-open: don't crash production on unevaluable invariants


def enforce_with_transitions(
    func: Any,
    invariants: list,
    args: tuple,
    kwargs: dict,
) -> Any:
    """Call func enforcing state-transition postconditions (OLD pattern).

    Integrates the icontract @snapshot + @ensure(OLD) workflow into the immune
    system's runtime enforcement loop, without requiring icontract as a runtime
    import:

    1. Identify postconditions that reference OLD.
    2. Collect the argument names they reference.
    3. Deep-copy only those arguments (capture_pre_state).
    4. Call func(*args, **kwargs).
    5. Evaluate each transition postcondition via check_transition_postcondition.
    6. Raise TransitionViolationError listing all violations.

    Static preconditions / postconditions (those without OLD) are handled by
    icontract decorators in the generated source — this layer complements that
    enforcement with the transition-aware OLD pattern. [REF-T10]

    Args:
        func: The function to call.
        invariants: List of InvariantSpec objects to enforce.
        args: Positional arguments for func.
        kwargs: Keyword arguments for func.

    Returns:
        The function's return value.

    Raises:
        TransitionViolationError: If any transition postcondition is violated.
    """
    # Identify transition postconditions (postconditions referencing OLD)
    transition_posts = [
        inv for inv in invariants
        if not inv.is_precondition and "OLD" in inv.expression
    ]

    if not transition_posts:
        return func(*args, **kwargs)

    # Collect arg names needed for snapshots
    referenced_args: set = set()
    for inv in transition_posts:
        referenced_args.update(_extract_old_references(inv.expression))

    # Capture pre-state (only the args referenced in postconditions)
    pre_state = capture_pre_state(func, args, kwargs, referenced_args or None)

    # Call the target function
    result = func(*args, **kwargs)

    # Build post-state (mutable args may have changed in-place)
    try:
        sig = inspect.signature(func)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        post_state = dict(bound.arguments)
    except Exception:
        post_state = {}

    # Evaluate all transition postconditions
    violations = []
    for inv in transition_posts:
        holds = check_transition_postcondition(
            pre_state=pre_state,
            post_state=post_state,
            result=result,
            invariant={"expression": inv.expression, "explanation": inv.explanation},
        )
        if not holds:
            violations.append(inv)

    if violations:
        msgs = "; ".join(f"'{v.expression}'" for v in violations)
        raise TransitionViolationError(
            f"Transition postcondition(s) violated: {msgs}"
        )

    return result
