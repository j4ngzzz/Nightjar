"""Dynamic invariant mining — MIT license reimplementation of the Daikon algorithm.

Reimplemented from the Daikon algorithm (Ernst et al., University of Washington, 1999).
Algorithm reference: [REF-T13] Fuzzingbook DynamicInvariants chapter.
This code is MIT-licensed. Do NOT copy from Fuzzingbook (CC-BY-NC-SA).

The algorithm:
1. Use sys.settrace to intercept function calls and returns
2. Record argument values at entry and return values at exit
3. Generate candidate invariants from templates applied to observed values
4. Falsify candidates against ALL observations — remove any that fail
5. Remaining candidates are discovered invariants

References:
- [REF-T13] Fuzzingbook DynamicInvariants — algorithm reference (NOT code)
- [REF-C05] Dynamic Invariant Mining — CARD immune system Stage 2
- [REF-P18] Self-Healing Software Systems — biological immune metaphor
"""

from __future__ import annotations

import inspect
import sys
import threading
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generator, Optional

from contractd.types import Invariant as CardInvariant, InvariantTier


class InvariantKind(str, Enum):
    """Classification of discovered invariants."""
    TYPE = "type"
    BOUND = "bound"
    NULLNESS = "nullness"
    RELATIONAL = "relational"
    LENGTH = "length"


@dataclass
class Invariant:
    """A single discovered invariant from runtime observation.

    Attributes:
        function: The function name this invariant applies to.
        variable: The variable name (or 'return' for return values).
        kind: The category of invariant (type, bound, nullness, etc.).
        expression: Human-readable invariant expression.
    """
    function: str
    variable: str
    kind: InvariantKind
    expression: str


@dataclass
class _FunctionTrace:
    """Internal: recorded values for a single function across all calls."""
    arg_names: list[str] = field(default_factory=list)
    # Each entry: dict mapping var_name -> value observed in one call
    call_records: list[dict[str, Any]] = field(default_factory=list)


class InvariantMiner:
    """Mines dynamic invariants from observed function executions.

    Uses sys.settrace to hook function calls, records argument and return
    values, then applies invariant templates to discover properties that
    hold across ALL observations.

    Usage:
        miner = InvariantMiner()
        with miner.trace():
            my_function(1, 2, 3)
            my_function(4, 5, 6)
        invariants = miner.get_invariants("my_function")

    References:
    - [REF-T13] Fuzzingbook DynamicInvariants — algorithm description
    - [REF-C05] Dynamic Invariant Mining
    """

    def __init__(
        self,
        include_modules: Optional[list[str]] = None,
        max_records: int = 10000,
    ) -> None:
        """Initialize the miner.

        Args:
            include_modules: If set, only trace functions from these modules.
                             If None, traces all non-stdlib functions.
            max_records: Maximum call records to keep per function.
        """
        self._traces: dict[str, _FunctionTrace] = defaultdict(_FunctionTrace)
        self._include_modules = include_modules
        self._max_records = max_records
        self._trace_count = 0
        self._lock = threading.Lock()
        # Track pending calls: thread_id -> list of (func_name, locals_at_entry)
        self._pending_calls: dict[int, list[tuple[str, dict[str, Any]]]] = defaultdict(list)

    @property
    def trace_count(self) -> int:
        """Number of function calls traced so far."""
        return self._trace_count

    @contextmanager
    def trace(self) -> Generator[None, None, None]:
        """Context manager that enables tracing via sys.settrace.

        Restores the previous trace function on exit.
        """
        old_trace = sys.gettrace()
        sys.settrace(self._trace_callback)
        try:
            yield
        finally:
            sys.settrace(old_trace)

    def _should_trace(self, frame) -> bool:
        """Decide whether to trace a given frame."""
        # Skip frames without code objects
        code = frame.f_code
        if not code:
            return False

        # Skip internal/private functions
        fname = code.co_filename
        func_name = code.co_name

        # Skip this module's own functions (but not test_daikon.py etc.)
        if fname.endswith("daikon.py") and "immune" in fname:
            return False

        # Skip stdlib and site-packages
        stdlib_markers = ("lib/python", "Lib\\", "site-packages",
                          "importlib", "<frozen", "<string>")
        if any(m in fname for m in stdlib_markers):
            return False

        # Skip dunder methods
        if func_name.startswith("__") and func_name.endswith("__"):
            return False

        # Apply module filter if set
        if self._include_modules is not None:
            module = frame.f_globals.get("__name__", "")
            if module not in self._include_modules:
                return False

        return True

    def _trace_callback(self, frame, event: str, arg: Any):
        """sys.settrace callback — intercepts call and return events."""
        if event == "call":
            if not self._should_trace(frame):
                return None
            # Record entry: capture argument values
            code = frame.f_code
            func_name = code.co_name
            # Get argument names and their values at entry
            arg_info = inspect.getargvalues(frame)
            arg_names = list(arg_info.args)
            entry_vals = {}
            for name in arg_names:
                try:
                    entry_vals[name] = frame.f_locals[name]
                except KeyError:
                    pass

            tid = threading.get_ident()
            with self._lock:
                self._pending_calls[tid].append((func_name, entry_vals))

                # Initialize arg_names if first time seeing this function
                trace = self._traces[func_name]
                if not trace.arg_names and arg_names:
                    trace.arg_names = arg_names

            # Return self._trace_callback so we get 'return' events too
            return self._trace_callback

        elif event == "return":
            tid = threading.get_ident()
            with self._lock:
                pending = self._pending_calls.get(tid, [])
                if not pending:
                    return
                func_name, entry_vals = pending.pop()

                # Build the complete record: args + return value
                record = dict(entry_vals)
                record["return"] = arg

                trace = self._traces[func_name]
                if len(trace.call_records) < self._max_records:
                    trace.call_records.append(record)
                self._trace_count += 1

        return None

    def get_invariants(self, function_name: str) -> list[Invariant]:
        """Get all discovered invariants for a function.

        Generates candidate invariants from templates, then retains only
        those that hold across ALL observed executions (falsification).

        Args:
            function_name: The function to get invariants for.

        Returns:
            List of Invariant objects that hold for all observations.
        """
        trace = self._traces.get(function_name)
        if not trace or not trace.call_records:
            return []

        candidates: list[Invariant] = []
        records = trace.call_records

        # Collect all variable names (args + return)
        all_vars = set()
        for rec in records:
            all_vars.update(rec.keys())

        for var_name in sorted(all_vars):
            values = [rec[var_name] for rec in records if var_name in rec]
            if not values:
                continue

            # Template 1: Type invariants
            candidates.extend(
                self._mine_type_invariants(function_name, var_name, values)
            )

            # Template 2: Nullness invariants
            candidates.extend(
                self._mine_nullness_invariants(function_name, var_name, values)
            )

            # Template 3: Value bound invariants (for numeric types)
            candidates.extend(
                self._mine_bound_invariants(function_name, var_name, values)
            )

            # Template 4: Length invariants (for sized types)
            candidates.extend(
                self._mine_length_invariants(function_name, var_name, values)
            )

        # Template 5: Relational invariants (binary, between pairs of vars)
        candidates.extend(
            self._mine_relational_invariants(function_name, records, all_vars)
        )

        return candidates

    def _mine_type_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Discover type invariants: isinstance(var, T) for all observations."""
        invariants = []
        if not values:
            return invariants

        # Check if all values are the same type
        types_seen = set()
        for v in values:
            types_seen.add(type(v).__name__)

        if len(types_seen) == 1:
            t = types_seen.pop()
            invariants.append(Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.TYPE,
                expression=f"isinstance({var}, {t})",
            ))

        return invariants

    def _mine_nullness_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Discover nullness invariants: var is not None."""
        invariants = []
        if all(v is not None for v in values):
            invariants.append(Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.NULLNESS,
                expression=f"{var} is not None",
            ))
        return invariants

    def _mine_bound_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Discover value bound invariants for numeric types.

        Templates: var > 0, var >= 0, var != 0, var > min, var < max.
        Only applies to int/float values.
        """
        invariants = []
        numeric_values = [v for v in values if isinstance(v, (int, float))
                          and not isinstance(v, bool)]
        if not numeric_values or len(numeric_values) != len(values):
            return invariants

        min_val = min(numeric_values)
        max_val = max(numeric_values)

        # var >= 0
        if min_val >= 0:
            invariants.append(Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.BOUND,
                expression=f"{var} >= 0",
            ))

        # var > 0
        if min_val > 0:
            invariants.append(Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.BOUND,
                expression=f"{var} > 0",
            ))

        # var <= 0
        if max_val <= 0:
            invariants.append(Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.BOUND,
                expression=f"{var} <= 0",
            ))

        # var < 0
        if max_val < 0:
            invariants.append(Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.BOUND,
                expression=f"{var} < 0",
            ))

        # var != 0 (all values are non-zero)
        if all(v != 0 for v in numeric_values):
            invariants.append(Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.BOUND,
                expression=f"{var} != 0",
            ))

        return invariants

    def _mine_length_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Discover length invariants for sized types (str, list, dict, etc.).

        Templates: len(var) >= 0, len(var) > 0.
        """
        invariants = []
        # Check if all values have len()
        lengths = []
        for v in values:
            try:
                lengths.append(len(v))
            except TypeError:
                return invariants  # Not all values are sized

        if not lengths:
            return invariants

        # len(var) >= 0 is always true for sized objects, but still useful
        invariants.append(Invariant(
            function=func,
            variable=var,
            kind=InvariantKind.LENGTH,
            expression=f"len({var}) >= 0",
        ))

        # len(var) > 0 (all non-empty)
        if all(l > 0 for l in lengths):
            invariants.append(Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.LENGTH,
                expression=f"len({var}) > 0",
            ))

        return invariants

    def _mine_relational_invariants(
        self,
        func: str,
        records: list[dict[str, Any]],
        all_vars: set[str],
    ) -> list[Invariant]:
        """Discover relational invariants between pairs of variables.

        Templates: x < y, x <= y, x == y, x != y, x > y, x >= y.
        Only for numeric pairs.
        """
        invariants = []
        numeric_vars = []

        # Identify which variables are consistently numeric
        for var in sorted(all_vars):
            values = [rec.get(var) for rec in records if var in rec]
            if values and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                              for v in values):
                numeric_vars.append(var)

        # Check all pairs
        for i, var_a in enumerate(numeric_vars):
            for var_b in numeric_vars[i + 1:]:
                vals_a = []
                vals_b = []
                for rec in records:
                    if var_a in rec and var_b in rec:
                        vals_a.append(rec[var_a])
                        vals_b.append(rec[var_b])

                if not vals_a:
                    continue

                # Check each relational template
                if all(a < b for a, b in zip(vals_a, vals_b)):
                    invariants.append(Invariant(
                        function=func, variable=f"{var_a},{var_b}",
                        kind=InvariantKind.RELATIONAL,
                        expression=f"{var_a} < {var_b}",
                    ))
                if all(a <= b for a, b in zip(vals_a, vals_b)):
                    invariants.append(Invariant(
                        function=func, variable=f"{var_a},{var_b}",
                        kind=InvariantKind.RELATIONAL,
                        expression=f"{var_a} <= {var_b}",
                    ))
                if all(a > b for a, b in zip(vals_a, vals_b)):
                    invariants.append(Invariant(
                        function=func, variable=f"{var_a},{var_b}",
                        kind=InvariantKind.RELATIONAL,
                        expression=f"{var_a} > {var_b}",
                    ))
                if all(a >= b for a, b in zip(vals_a, vals_b)):
                    invariants.append(Invariant(
                        function=func, variable=f"{var_a},{var_b}",
                        kind=InvariantKind.RELATIONAL,
                        expression=f"{var_a} >= {var_b}",
                    ))
                if all(a == b for a, b in zip(vals_a, vals_b)):
                    invariants.append(Invariant(
                        function=func, variable=f"{var_a},{var_b}",
                        kind=InvariantKind.RELATIONAL,
                        expression=f"{var_a} == {var_b}",
                    ))
                if all(a != b for a, b in zip(vals_a, vals_b)):
                    invariants.append(Invariant(
                        function=func, variable=f"{var_a},{var_b}",
                        kind=InvariantKind.RELATIONAL,
                        expression=f"{var_a} != {var_b}",
                    ))

        return invariants

    def export_card_invariants(self, function_name: str) -> list[CardInvariant]:
        """Export discovered invariants as CARD-compatible Invariant objects.

        Maps InvariantKind to InvariantTier:
        - All mined invariants map to PROPERTY tier (they're observed, not proved).

        Args:
            function_name: The function to export invariants for.

        Returns:
            List of contractd.types.Invariant objects.
        """
        invariants = self.get_invariants(function_name)
        card_invariants = []
        for i, inv in enumerate(invariants):
            card_inv = CardInvariant(
                id=f"DAIKON-{function_name}-{i:03d}",
                tier=InvariantTier.PROPERTY,
                statement=inv.expression,
                rationale=f"Mined by Daikon from {self._trace_count} observations "
                          f"[REF-C05, REF-T13]",
            )
            card_invariants.append(card_inv)
        return card_invariants

    def get_all_function_names(self) -> list[str]:
        """Return names of all functions that have been traced."""
        return [name for name, trace in self._traces.items()
                if trace.call_records]

    def clear(self, function_name: Optional[str] = None) -> None:
        """Clear recorded traces.

        Args:
            function_name: If set, only clear traces for this function.
                          If None, clear all traces.
        """
        if function_name:
            self._traces.pop(function_name, None)
        else:
            self._traces.clear()
            self._trace_count = 0
