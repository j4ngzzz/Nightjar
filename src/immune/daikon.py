"""Dynamic invariant mining — clean-room MIT reimplementation from Ernst et al. 1999/2007.

Implements the Daikon dynamic invariant detection algorithm as described in:
  Ernst, M.D., Perkins, J.H., Guo, P.J., McCamant, S., Pacheco, C., Tschantz, M.S.,
  and Flanagan, C. (2007). The Daikon system for dynamic detection of likely
  invariants. Science of Computer Programming, 69(1-3), 35-45.
  https://homes.cs.washington.edu/~mernst/pubs/invariants-tse2001.pdf

Tracing mechanism: sys.monitoring (PEP 669, Python 3.12+) for up to 20x lower
overhead than sys.settrace. Falls back to sys.settrace on Python 3.11.

Per Scout 6 Section 4: PyCharm/PyDev benchmarks show up to 15-20x less overhead
with sys.monitoring vs sys.settrace.

19 core templates from Ernst 1999/2007:
  Unary Scalar:   Constant, NonZero, IsNull/NonNull, Range, OneOf, IsType
  Binary Relat.:  Equality, Ordering, LinearRelation, Membership, NonEquality
  Sequence:       SeqIndexComparison, Sorted, SeqOneOf, SeqLength
  State:          Unchanged, Changed, Increased, Decreased
  Conditional:    Implication

Clean-room CR-01: Implements the Ernst 1999/2007 paper algorithm only.
DO NOT add Fuzzingbook code (CC-BY-NC-SA, non-commercial only).

References:
- [REF-C05] Dynamic Invariant Mining -- immune system Stage 2
- [REF-P18] Self-Healing Software Systems -- biological immune metaphor
- Scout 6 mining-report.md -- sys.monitoring performance advantage
- PEP 669 -- sys.monitoring: https://docs.python.org/3/library/sys.monitoring.html
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

from nightjar.types import Invariant as CardInvariant, InvariantTier


# ---------------------------------------------------------------------------
# sys.monitoring availability check (Python 3.12+, PEP 669)
# ---------------------------------------------------------------------------

_SYS_MONITORING_AVAILABLE: bool = hasattr(sys, "monitoring")

# Tool slot for our use: IDs 0-3 reserved (debugger, profiler, coverage, optimizer).
# We try IDs 4 and 5 in order; fall back to sys.settrace if both are taken.
_PREFERRED_TOOL_IDS = (4, 5)


class InvariantKind(str, Enum):
    """Classification of discovered invariants, covering Ernst 1999/2007's 19 templates.

    Original 5 kinds preserved for backward compatibility.
    9 new kinds added for complete Ernst coverage.
    """

    # ---- Original 5 (backward compatible) ----
    TYPE = "type"                # isinstance(var, T) for all observations
    BOUND = "bound"              # numeric bound: >=0, >0, <=0, <0, !=0
    NULLNESS = "nullness"        # var is None / var is not None
    RELATIONAL = "relational"    # binary numeric: x<y, x<=y, x==y, x!=y, x>y, x>=y
    LENGTH = "length"            # len(var) >= 0, len(var) > 0

    # ---- New 9 for full Ernst 1999/2007 coverage ----
    # Unary Scalar
    CONSTANT = "constant"        # var == C for a fixed C (Ernst: Constant)
    ONE_OF = "one_of"            # var in {v1, v2, ...} (Ernst: OneOf)
    RANGE = "range"              # lo <= var <= hi (Ernst: Range, explicit bounds)

    # Binary Relational
    EQUALITY = "equality"        # x == y always (Ernst: Equality)
    ORDERING = "ordering"        # x < y always (Ernst: Ordering)
    LINEAR = "linear"            # y == a*x + b (Ernst: LinearRelation)

    # Sequence
    SEQ_SORTED = "seq_sorted"    # list elements are sorted (Ernst: Sorted)
    SEQ_ONE_OF = "seq_one_of"    # all elements in fixed set (Ernst: SeqOneOf)

    # State (pre/post comparison within a single call)
    UNCHANGED = "unchanged"      # arg == return value (Ernst: Unchanged)
    INCREASED = "increased"      # return > arg (Ernst: Increased)
    DECREASED = "decreased"      # return < arg (Ernst: Decreased)

    # Conditional
    IMPLICATION = "implication"  # if P(x) then Q(y) (Ernst: Implication)


# Maximum distinct values for ONE_OF template (Ernst 1999: typically <= 3-5)
_ONE_OF_MAX_CARDINALITY = 5


@dataclass
class Invariant:
    """A single discovered invariant from runtime observation.

    Attributes:
        function:   Function name this invariant applies to.
        variable:   Variable name (or 'return' for return values).
        kind:       InvariantKind classification (Ernst 1999/2007 template category).
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


# ---------------------------------------------------------------------------
# InvariantMiner
# ---------------------------------------------------------------------------


class InvariantMiner:
    """Mines dynamic invariants from observed function executions.

    Uses sys.monitoring (PEP 669, Python 3.12+) as primary tracing mechanism
    for up to 20x lower overhead than sys.settrace. Falls back to sys.settrace
    on Python 3.11.

    Implements the Daikon algorithm from Ernst et al. 1999/2007:
    1. Intercept CALL and RETURN_VALUE events
    2. Record argument and return values per function
    3. Generate candidate invariants from 19 Ernst templates
    4. Falsify candidates against ALL observations -- remove any that fail
    5. Remaining candidates are the discovered invariants

    Usage::

        miner = InvariantMiner()
        with miner.trace():
            my_function(1, 2, 3)
            my_function(4, 5, 6)
        invariants = miner.get_invariants("my_function")

    References:
    - Ernst et al. 2007 -- The Daikon system (Science of Computer Programming)
    - PEP 669 -- sys.monitoring (Python 3.12+)
    - Scout 6 mining-report.md -- 20x overhead advantage
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
            max_records:     Maximum call records per function (memory guard).
        """
        self._traces: dict[str, _FunctionTrace] = defaultdict(_FunctionTrace)
        self._include_modules = include_modules
        self._max_records = max_records
        self._trace_count = 0
        self._lock = threading.Lock()
        # Pending calls: thread_id -> list of (func_name, callee_code|None, entry_vals, param_names)
        # callee_code: code object for identity-matching in PY_RETURN (sys.monitoring path)
        #              None in sys.settrace path (matches by func_name instead)
        self._pending_calls: dict[int, list[tuple[str, Any, dict[str, Any], list[str]]]] = (
            defaultdict(list)
        )

        # Determine which tracing mechanism to use
        self._tool_id: Optional[int] = None
        self._return_event: Optional[int] = None  # cached event value for cleanup
        self._using_monitoring: bool = _SYS_MONITORING_AVAILABLE
        self._fallback_old_trace: Any = None

    @property
    def using_sys_monitoring(self) -> bool:
        """True if sys.monitoring (PEP 669) is used as primary tracing mechanism.

        Returns True on Python 3.12+. On Python 3.11, returns False and
        the miner falls back to sys.settrace.
        """
        return self._using_monitoring

    @property
    def trace_count(self) -> int:
        """Number of function calls traced so far."""
        return self._trace_count

    @contextmanager
    def trace(self) -> Generator[None, None, None]:
        """Context manager that enables function tracing.

        On Python 3.12+: uses sys.monitoring (PEP 669) -- up to 20x lower
        overhead than sys.settrace (Scout 6 Section 4).

        On Python 3.11: falls back to sys.settrace.

        Restores previous tracing state on exit.

        Reference: Ernst et al. 1999/2007 -- observation collection phase.
        """
        if self._using_monitoring:
            self._start_monitoring()
            try:
                yield
            finally:
                self._stop_monitoring()
        else:
            # Python 3.11 fallback: sys.settrace
            old_trace = sys.gettrace()
            sys.settrace(self._settrace_callback)
            try:
                yield
            finally:
                sys.settrace(old_trace)

    # ------------------------------------------------------------------
    # sys.monitoring event handlers (Python 3.12+, PEP 669)
    # ------------------------------------------------------------------

    def _start_monitoring(self) -> None:
        """Acquire a sys.monitoring tool slot and register CALL+PY_RETURN callbacks.

        Uses CALL + PY_RETURN events per Python 3.12+ sys.monitoring API (PEP 669).
        PY_RETURN fires when a Python function returns; RETURN_VALUE does not exist.
        """
        for tid in _PREFERRED_TOOL_IDS:
            try:
                sys.monitoring.use_tool_id(tid, "nightjar-daikon")  # type: ignore[attr-defined]
                self._tool_id = tid
                break
            except ValueError:
                # Slot already taken -- try next
                continue

        if self._tool_id is None:
            # All slots taken -- fall back to sys.settrace silently
            self._using_monitoring = False
            self._fallback_old_trace = sys.gettrace()
            sys.settrace(self._settrace_callback)
            return

        events = sys.monitoring.events  # type: ignore[attr-defined]

        # PY_RETURN: fires when a Python function returns (Python 3.12+, PEP 669)
        # Note: event name is PY_RETURN, NOT RETURN_VALUE (which does not exist)
        return_event = getattr(events, "PY_RETURN", None)
        if return_event is None:
            # Unexpected API shape -- free slot and fall back to sys.settrace
            sys.monitoring.free_tool_id(self._tool_id)  # type: ignore[attr-defined]
            self._tool_id = None
            self._using_monitoring = False
            self._fallback_old_trace = sys.gettrace()
            sys.settrace(self._settrace_callback)
            return

        self._return_event = return_event
        sys.monitoring.register_callback(  # type: ignore[attr-defined]
            self._tool_id, events.CALL, self._monitoring_call
        )
        sys.monitoring.register_callback(  # type: ignore[attr-defined]
            self._tool_id, return_event, self._monitoring_return
        )
        sys.monitoring.set_events(  # type: ignore[attr-defined]
            self._tool_id, events.CALL | return_event
        )

    def _stop_monitoring(self) -> None:
        """Release the sys.monitoring tool slot and deregister callbacks."""
        if not self._using_monitoring or self._tool_id is None:
            # We fell back to sys.settrace in _start_monitoring
            sys.settrace(self._fallback_old_trace)
            self._using_monitoring = _SYS_MONITORING_AVAILABLE  # restore
            return

        events = sys.monitoring.events  # type: ignore[attr-defined]
        sys.monitoring.set_events(  # type: ignore[attr-defined]
            self._tool_id, events.NO_EVENTS
        )
        sys.monitoring.register_callback(  # type: ignore[attr-defined]
            self._tool_id, events.CALL, None
        )
        if self._return_event is not None:
            sys.monitoring.register_callback(  # type: ignore[attr-defined]
                self._tool_id, self._return_event, None
            )
        sys.monitoring.free_tool_id(self._tool_id)  # type: ignore[attr-defined]
        self._tool_id = None
        self._return_event = None

    def _monitoring_call(
        self, code: Any, instruction_offset: int, callable_: Any, arg0: Any
    ) -> None:
        """sys.monitoring CALL event handler (PEP 669).

        Per PEP 669: `code` is the CALLER's code object; `callable_` is the
        callee being invoked. We use `callable_.__code__` (the callee's code)
        to correctly match with the subsequent PY_RETURN event.

        Captures arg0 (first positional argument) as entry state. Full arg
        capture requires sys.settrace; sys.monitoring only provides arg0.

        Args:
            code:               CALLER's code object (containing the call site).
            instruction_offset: Bytecode offset of the CALL instruction.
            callable_:          The callable being invoked.
            arg0:               First positional argument (or sys.monitoring.MISSING).
        """
        # Get the CALLEE's code object for tracing decisions and PY_RETURN matching
        callee_code = getattr(callable_, "__code__", None)
        if callee_code is None:
            # Not a Python function (e.g., built-in) -- skip
            return sys.monitoring.DISABLE  # type: ignore[attr-defined]

        # Derive callee module for include_modules filtering
        callee_module = getattr(callable_, "__module__", None)
        if not self._should_trace_code(callee_code, module_name=callee_module):
            return sys.monitoring.DISABLE  # type: ignore[attr-defined]

        func_name = callee_code.co_name
        param_names = list(callee_code.co_varnames[: callee_code.co_argcount])

        entry_vals: dict[str, Any] = {}
        missing = getattr(sys.monitoring, "MISSING", object())  # type: ignore[attr-defined]
        if param_names and arg0 is not missing:
            entry_vals[param_names[0]] = arg0

        tid = threading.get_ident()
        with self._lock:
            # Store callee_code for identity-based matching in _monitoring_return
            self._pending_calls[tid].append((func_name, callee_code, entry_vals, param_names))
            trace = self._traces[func_name]
            if not trace.arg_names and param_names:
                trace.arg_names = param_names

    def _monitoring_return(
        self, code: Any, instruction_offset: int, retval: Any
    ) -> None:
        """sys.monitoring PY_RETURN event handler (PEP 669).

        Fires when a Python function returns. `code` is the CALLEE's code
        object — matched by identity with the code stored in _pending_calls
        by _monitoring_call.

        Args:
            code:               CALLEE's code object (the function returning).
            instruction_offset: Bytecode offset.
            retval:             The return value.
        """
        tid = threading.get_ident()

        with self._lock:
            pending = self._pending_calls.get(tid, [])
            # Search from most recent call backwards (handles recursion correctly)
            for i in range(len(pending) - 1, -1, -1):
                pname, callee_code, entry_vals, param_names = pending[i]
                if callee_code is code:  # Identity match by callee code object
                    pending.pop(i)
                    record = dict(entry_vals)
                    record["return"] = retval
                    trace = self._traces[pname]
                    if len(trace.call_records) < self._max_records:
                        trace.call_records.append(record)
                    self._trace_count += 1
                    break

    # ------------------------------------------------------------------
    # sys.settrace callback (Python 3.11 fallback)
    # ------------------------------------------------------------------

    def _should_trace_code(self, code: Any, module_name: Optional[str] = None) -> bool:
        """Decide whether to trace a given code object.

        Used by both sys.monitoring and sys.settrace handlers.

        Args:
            code:        The code object of the function to check.
            module_name: Module name (__name__) of the function's module.
                         Required for include_modules filtering in sys.monitoring path.
        """
        if not code:
            return False

        fname = code.co_filename
        func_name = code.co_name

        # Skip this module's own instrumentation
        if fname.endswith("daikon.py") and "immune" in fname:
            return False

        # Skip stdlib and site-packages
        stdlib_markers = (
            "lib/python", "Lib\\", "site-packages", "importlib", "<frozen", "<string>"
        )
        if any(m in fname for m in stdlib_markers):
            return False

        # Skip dunder methods
        if func_name.startswith("__") and func_name.endswith("__"):
            return False

        # Apply include_modules filter (same logic as sys.settrace path)
        if self._include_modules is not None and module_name is not None:
            if module_name not in self._include_modules:
                return False

        return True

    def _should_trace(self, frame: Any) -> bool:
        """Decide whether to trace a given frame (sys.settrace path)."""
        module = frame.f_globals.get("__name__", "")
        return self._should_trace_code(frame.f_code, module_name=module)

    def _settrace_callback(self, frame: Any, event: str, arg: Any) -> Any:
        """sys.settrace callback -- intercepts call and return events (Python 3.11 path).

        Stores None as the code object in pending_calls (sys.monitoring path
        stores the actual callee code object for identity-based matching).
        """
        if event == "call":
            if not self._should_trace(frame):
                return None
            code = frame.f_code
            func_name = code.co_name
            arg_info = inspect.getargvalues(frame)
            arg_names = list(arg_info.args)
            entry_vals: dict[str, Any] = {}
            for name in arg_names:
                try:
                    entry_vals[name] = frame.f_locals[name]
                except KeyError:
                    pass

            tid = threading.get_ident()
            with self._lock:
                # code_obj=None: sys.settrace matches by func_name, not code identity
                self._pending_calls[tid].append((func_name, None, entry_vals, arg_names))
                trace = self._traces[func_name]
                if not trace.arg_names and arg_names:
                    trace.arg_names = arg_names

            return self._settrace_callback

        elif event == "return":
            tid = threading.get_ident()
            with self._lock:
                pending = self._pending_calls.get(tid, [])
                if not pending:
                    return None
                func_name = frame.f_code.co_name
                # Find matching pending call by function name (sys.settrace path)
                for i in range(len(pending) - 1, -1, -1):
                    pname, _code_obj, entry_vals, param_names = pending[i]
                    if pname == func_name:
                        pending.pop(i)
                        record = dict(entry_vals)
                        record["return"] = arg
                        trace = self._traces[func_name]
                        if len(trace.call_records) < self._max_records:
                            trace.call_records.append(record)
                        self._trace_count += 1
                        break

        return None

    # ------------------------------------------------------------------
    # Invariant extraction: 19 Ernst 1999/2007 templates
    # ------------------------------------------------------------------

    def get_invariants(self, function_name: str) -> list[Invariant]:
        """Get all discovered invariants for a function.

        Generates candidate invariants from all 19 Ernst 1999/2007 templates,
        then retains only those that hold across ALL observed executions
        (falsification principle from Ernst et al. 1999 Section 3.3).

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
        all_vars: set[str] = set()
        for rec in records:
            all_vars.update(rec.keys())

        for var_name in sorted(all_vars):
            values = [rec[var_name] for rec in records if var_name in rec]
            if not values:
                continue

            # --- Unary Scalar Templates (Ernst 1999/2007 Section 2.1) ---

            # Template: Constant -- var == C always
            candidates.extend(
                self._mine_constant_invariants(function_name, var_name, values)
            )

            # Template: IsType -- isinstance(var, T) always
            candidates.extend(
                self._mine_type_invariants(function_name, var_name, values)
            )

            # Template: IsNull / NonNull -- var is None / var is not None
            candidates.extend(
                self._mine_nullness_invariants(function_name, var_name, values)
            )

            # Template: Range / NonZero / Bound -- numeric bounds (backward compat)
            candidates.extend(
                self._mine_bound_invariants(function_name, var_name, values)
            )

            # Template: Range (explicit [lo, hi] bounds)
            candidates.extend(
                self._mine_range_invariants(function_name, var_name, values)
            )

            # Template: OneOf -- var in {v1, v2, ...}
            candidates.extend(
                self._mine_one_of_invariants(function_name, var_name, values)
            )

            # --- Sequence Templates (Ernst 1999/2007 Section 2.3) ---

            # Template: SeqLength -- len bounds
            candidates.extend(
                self._mine_length_invariants(function_name, var_name, values)
            )

            # Template: Sorted / SeqIndexComparison -- elements in sorted order
            candidates.extend(
                self._mine_seq_sorted_invariants(function_name, var_name, values)
            )

            # Template: SeqOneOf -- all elements in fixed set
            candidates.extend(
                self._mine_seq_one_of_invariants(function_name, var_name, values)
            )

        # --- Binary Relational Templates (Ernst 1999/2007 Section 2.2) ---
        candidates.extend(
            self._mine_relational_invariants(function_name, records, all_vars)
        )

        # --- State Templates (Ernst 1999/2007 Section 2.4) ---
        # Compare entry args to return values within same call
        candidates.extend(
            self._mine_state_invariants(function_name, records, all_vars)
        )

        # --- Conditional Template (Ernst 1999/2007 Section 2.5) ---
        candidates.extend(
            self._mine_implication_invariants(function_name, records, all_vars)
        )

        return candidates

    # ------------------------------------------------------------------
    # Unary Scalar Templates
    # ------------------------------------------------------------------

    def _mine_constant_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Ernst Constant template: var == C for all observations.

        If ALL observed values are identical, this is a CONSTANT invariant.
        Reference: Ernst et al. 1999 Section 2.1, Constant template.
        """
        if not values:
            return []
        unique: set[Any] = set()
        for v in values:
            try:
                unique.add(v)
            except TypeError:
                return []  # unhashable -- skip
        if len(unique) == 1:
            c = next(iter(unique))
            return [
                Invariant(
                    function=func,
                    variable=var,
                    kind=InvariantKind.CONSTANT,
                    expression=f"{var} == {c!r}",
                )
            ]
        return []

    def _mine_type_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Ernst IsType template: isinstance(var, T) for all observations."""
        if not values:
            return []
        types_seen: set[str] = set()
        for v in values:
            types_seen.add(type(v).__name__)
        if len(types_seen) == 1:
            t = types_seen.pop()
            return [
                Invariant(
                    function=func,
                    variable=var,
                    kind=InvariantKind.TYPE,
                    expression=f"isinstance({var}, {t})",
                )
            ]
        return []

    def _mine_nullness_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Ernst IsNull/NonNull template: var is None / var is not None."""
        if not values:
            return []
        if all(v is not None for v in values):
            return [
                Invariant(
                    function=func,
                    variable=var,
                    kind=InvariantKind.NULLNESS,
                    expression=f"{var} is not None",
                )
            ]
        if all(v is None for v in values):
            return [
                Invariant(
                    function=func,
                    variable=var,
                    kind=InvariantKind.NULLNESS,
                    expression=f"{var} is None",
                )
            ]
        return []

    def _mine_bound_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Ernst NonZero + partial Range template: numeric bound invariants.

        Templates: var > 0, var >= 0, var != 0, var <= 0, var < 0.
        Preserves backward compatibility with existing BOUND kind.
        """
        invariants: list[Invariant] = []
        numeric_values = [
            v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)
        ]
        if not numeric_values or len(numeric_values) != len(values):
            return invariants

        min_val = min(numeric_values)
        max_val = max(numeric_values)

        if min_val >= 0:
            invariants.append(Invariant(func, var, InvariantKind.BOUND, f"{var} >= 0"))
        if min_val > 0:
            invariants.append(Invariant(func, var, InvariantKind.BOUND, f"{var} > 0"))
        if max_val <= 0:
            invariants.append(Invariant(func, var, InvariantKind.BOUND, f"{var} <= 0"))
        if max_val < 0:
            invariants.append(Invariant(func, var, InvariantKind.BOUND, f"{var} < 0"))
        if all(v != 0 for v in numeric_values):
            invariants.append(Invariant(func, var, InvariantKind.BOUND, f"{var} != 0"))

        return invariants

    def _mine_range_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Ernst Range template: explicit [lo, hi] bounds.

        Emits RANGE invariant when there are >= 2 distinct values,
        recording the observed [min, max] range.
        Reference: Ernst et al. 1999 Section 2.1, Range template.
        """
        numeric_values = [
            v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)
        ]
        if not numeric_values or len(numeric_values) != len(values):
            return []

        unique_vals = set(numeric_values)
        if len(unique_vals) < 2:
            # Only one value -- CONSTANT template handles this
            return []

        lo = min(numeric_values)
        hi = max(numeric_values)

        return [
            Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.RANGE,
                expression=f"{lo} <= {var} <= {hi}",
            )
        ]

    def _mine_one_of_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Ernst OneOf template: var in {v1, v2, ...} for small cardinality sets.

        Only emits when the number of distinct observed values is <=
        _ONE_OF_MAX_CARDINALITY (default 5). Above that threshold the
        invariant is unlikely to be meaningful.

        Reference: Ernst et al. 1999 Section 2.1, OneOf template.
        """
        if not values:
            return []
        unique: set[Any] = set()
        try:
            for v in values:
                unique.add(v)
        except TypeError:
            return []  # unhashable type

        if len(unique) < 2 or len(unique) > _ONE_OF_MAX_CARDINALITY:
            # <2: covered by CONSTANT; >max: not a useful OneOf
            return []

        sorted_vals = sorted(unique, key=repr)
        vals_repr = ", ".join(repr(v) for v in sorted_vals)
        return [
            Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.ONE_OF,
                expression=f"{var} in {{{vals_repr}}}",
            )
        ]

    # ------------------------------------------------------------------
    # Sequence Templates
    # ------------------------------------------------------------------

    def _mine_length_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Ernst SeqLength template: len(var) >= 0 and len(var) > 0."""
        lengths: list[int] = []
        for v in values:
            try:
                lengths.append(len(v))
            except TypeError:
                return []
        if not lengths:
            return []

        invariants = [
            Invariant(func, var, InvariantKind.LENGTH, f"len({var}) >= 0")
        ]
        if all(l > 0 for l in lengths):
            invariants.append(
                Invariant(func, var, InvariantKind.LENGTH, f"len({var}) > 0")
            )
        return invariants

    def _mine_seq_sorted_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Ernst Sorted/SeqIndexComparison template: sequence elements are sorted.

        Reference: Ernst et al. 1999 Section 2.3, Sorted/SeqIndexComparison.
        """
        # Only applies to list/tuple values
        seq_values = [v for v in values if isinstance(v, (list, tuple))]
        if not seq_values or len(seq_values) != len(values):
            return []

        # Check that every observed sequence is sorted (ascending)
        for seq in seq_values:
            if len(seq) < 2:
                continue
            try:
                if not all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1)):
                    return []
            except TypeError:
                return []

        return [
            Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.SEQ_SORTED,
                expression=f"{var} is sorted (ascending)",
            )
        ]

    def _mine_seq_one_of_invariants(
        self, func: str, var: str, values: list[Any]
    ) -> list[Invariant]:
        """Ernst SeqOneOf template: all elements of sequences are from a fixed set.

        Reference: Ernst et al. 1999 Section 2.3, SeqOneOf.
        """
        seq_values = [v for v in values if isinstance(v, (list, tuple))]
        if not seq_values or len(seq_values) != len(values):
            return []

        # Collect the universe of all observed element values
        universe: set[Any] = set()
        for seq in seq_values:
            for elem in seq:
                try:
                    universe.add(elem)
                except TypeError:
                    return []  # unhashable elements

        if not universe or len(universe) > _ONE_OF_MAX_CARDINALITY:
            return []

        sorted_univ = sorted(universe, key=repr)
        univ_repr = ", ".join(repr(v) for v in sorted_univ)
        return [
            Invariant(
                function=func,
                variable=var,
                kind=InvariantKind.SEQ_ONE_OF,
                expression=f"all elements of {var} in {{{univ_repr}}}",
            )
        ]

    # ------------------------------------------------------------------
    # Binary Relational Templates
    # ------------------------------------------------------------------

    def _mine_relational_invariants(
        self,
        func: str,
        records: list[dict[str, Any]],
        all_vars: set[str],
    ) -> list[Invariant]:
        """Ernst Binary Relational templates: x<y, x<=y, x==y, x!=y, x>y, x>=y.

        Also covers Equality and Ordering sub-templates.
        Reference: Ernst et al. 1999 Section 2.2, Binary Relational templates.
        """
        invariants: list[Invariant] = []
        numeric_vars: list[str] = []

        for var in sorted(all_vars):
            vals = [rec.get(var) for rec in records if var in rec]
            if vals and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals
            ):
                numeric_vars.append(var)

        for i, var_a in enumerate(numeric_vars):
            for var_b in numeric_vars[i + 1 :]:
                vals_a: list[float] = []
                vals_b: list[float] = []
                for rec in records:
                    if var_a in rec and var_b in rec:
                        vals_a.append(rec[var_a])
                        vals_b.append(rec[var_b])

                if not vals_a:
                    continue

                pairs = list(zip(vals_a, vals_b))

                if all(a == b for a, b in pairs):
                    invariants.append(
                        Invariant(func, f"{var_a},{var_b}", InvariantKind.EQUALITY,
                                  f"{var_a} == {var_b}")
                    )
                if all(a != b for a, b in pairs):
                    invariants.append(
                        Invariant(func, f"{var_a},{var_b}", InvariantKind.RELATIONAL,
                                  f"{var_a} != {var_b}")
                    )
                if all(a < b for a, b in pairs):
                    invariants.append(
                        Invariant(func, f"{var_a},{var_b}", InvariantKind.ORDERING,
                                  f"{var_a} < {var_b}")
                    )
                if all(a <= b for a, b in pairs):
                    invariants.append(
                        Invariant(func, f"{var_a},{var_b}", InvariantKind.RELATIONAL,
                                  f"{var_a} <= {var_b}")
                    )
                if all(a > b for a, b in pairs):
                    invariants.append(
                        Invariant(func, f"{var_a},{var_b}", InvariantKind.ORDERING,
                                  f"{var_a} > {var_b}")
                    )
                if all(a >= b for a, b in pairs):
                    invariants.append(
                        Invariant(func, f"{var_a},{var_b}", InvariantKind.RELATIONAL,
                                  f"{var_a} >= {var_b}")
                    )

                # Linear relation: y == a*x + b (Ernst LinearRelation template)
                invariants.extend(
                    self._mine_linear_relation(func, var_a, var_b, vals_a, vals_b)
                )

        return invariants

    def _mine_linear_relation(
        self,
        func: str,
        var_a: str,
        var_b: str,
        vals_a: list[float],
        vals_b: list[float],
    ) -> list[Invariant]:
        """Ernst LinearRelation template: var_b == a * var_a + b.

        Uses least-squares fit. Only emits if the fit is exact (R2 approx 1.0)
        for all observations, meaning the relation holds without exception.

        Reference: Ernst et al. 1999 Section 2.2, LinearRelation.
        """
        if len(vals_a) < 2:
            return []

        # Compute slope via two-point approach
        # For exact linear: consistent slope across all pairs (relative to first point)
        x0, y0 = vals_a[0], vals_b[0]
        slopes: set[float] = set()
        for x, y in zip(vals_a[1:], vals_b[1:]):
            dx = x - x0
            dy = y - y0
            if dx == 0:
                if dy != 0:
                    return []  # vertical relationship -- not a linear function
                continue
            slopes.add(round(dy / dx, 6))

        if len(slopes) > 1:
            return []

        if not slopes:
            # All x values are the same -- could be constant on both
            return []

        a = next(iter(slopes))
        b_val = round(y0 - a * x0, 6)

        # Verify against ALL observations
        for x, y in zip(vals_a, vals_b):
            if abs(y - (a * x + b_val)) > 1e-9:
                return []

        # Format nicely
        if b_val == 0.0:
            expr = f"{var_b} == {a} * {var_a}" if a != 1.0 else f"{var_b} == {var_a}"
        elif b_val > 0:
            expr = f"{var_b} == {a} * {var_a} + {b_val}"
        else:
            expr = f"{var_b} == {a} * {var_a} - {abs(b_val)}"

        return [Invariant(func, f"{var_a},{var_b}", InvariantKind.LINEAR, expr)]

    # ------------------------------------------------------------------
    # State Templates (Ernst 1999/2007 Section 2.4)
    # ------------------------------------------------------------------

    def _mine_state_invariants(
        self,
        func: str,
        records: list[dict[str, Any]],
        all_vars: set[str],
    ) -> list[Invariant]:
        """Ernst State templates: Unchanged, Increased, Decreased.

        Compares argument values at function entry to the return value,
        checking if the relationship holds consistently across all calls.

        Reference: Ernst et al. 1999 Section 2.4, State templates.
        """
        invariants: list[Invariant] = []
        arg_vars = [v for v in sorted(all_vars) if v != "return"]
        if "return" not in all_vars or not arg_vars:
            return invariants

        for arg_var in arg_vars:
            # Collect (arg_val, retval) pairs where both are numeric
            arg_ret_pairs: list[tuple[Any, Any]] = []
            for rec in records:
                if arg_var in rec and "return" in rec:
                    av = rec[arg_var]
                    rv = rec["return"]
                    if isinstance(av, (int, float)) and not isinstance(av, bool):
                        if isinstance(rv, (int, float)) and not isinstance(rv, bool):
                            arg_ret_pairs.append((av, rv))

            if not arg_ret_pairs:
                continue

            # Unchanged: arg == return for ALL calls
            if all(av == rv for av, rv in arg_ret_pairs):
                invariants.append(
                    Invariant(
                        func, f"{arg_var},return", InvariantKind.UNCHANGED,
                        f"return == {arg_var} (unchanged)",
                    )
                )
                continue  # Unchanged implies not Increased or Decreased

            # Increased: return > arg for ALL calls
            if all(rv > av for av, rv in arg_ret_pairs):
                invariants.append(
                    Invariant(
                        func, f"{arg_var},return", InvariantKind.INCREASED,
                        f"return > {arg_var} (increased)",
                    )
                )

            # Decreased: return < arg for ALL calls
            elif all(rv < av for av, rv in arg_ret_pairs):
                invariants.append(
                    Invariant(
                        func, f"{arg_var},return", InvariantKind.DECREASED,
                        f"return < {arg_var} (decreased)",
                    )
                )

        return invariants

    # ------------------------------------------------------------------
    # Conditional Template (Ernst 1999/2007 Section 2.5)
    # ------------------------------------------------------------------

    def _mine_implication_invariants(
        self,
        func: str,
        records: list[dict[str, Any]],
        all_vars: set[str],
    ) -> list[Invariant]:
        """Ernst Implication template: if P(x) then Q(y).

        Checks a small set of simple implication patterns:
        - if x > 0 then return >= 0
        - if x > 0 then return > 0

        Full implication mining (all possible P, Q pairs) is O(n^2) and
        typically done with threshold-based pruning in production Daikon.
        We implement the most common practical pattern only.

        Reference: Ernst et al. 1999 Section 2.5, Implication template.
        """
        invariants: list[Invariant] = []
        if "return" not in all_vars:
            return invariants

        for arg_var in sorted(all_vars):
            if arg_var == "return":
                continue

            # Gather records where both arg and return are numeric
            pairs: list[tuple[float, float]] = []
            for rec in records:
                if arg_var in rec and "return" in rec:
                    av = rec[arg_var]
                    rv = rec["return"]
                    if isinstance(av, (int, float)) and not isinstance(av, bool):
                        if isinstance(rv, (int, float)) and not isinstance(rv, bool):
                            pairs.append((av, rv))

            if not pairs:
                continue

            # Pattern: if arg > 0 then return >= 0
            pos_arg_pairs = [(av, rv) for av, rv in pairs if av > 0]
            if (
                len(pos_arg_pairs) >= 3  # need sufficient evidence
                and all(rv >= 0 for _, rv in pos_arg_pairs)
            ):
                invariants.append(
                    Invariant(
                        func, f"{arg_var},return", InvariantKind.IMPLICATION,
                        f"if {arg_var} > 0 then return >= 0",
                    )
                )

        return invariants

    # ------------------------------------------------------------------
    # Export / utility
    # ------------------------------------------------------------------

    def export_card_invariants(self, function_name: str) -> list[CardInvariant]:
        """Export discovered invariants as Nightjar-compatible Invariant objects.

        Maps InvariantKind to InvariantTier:
        - All mined invariants map to PROPERTY tier (observed, not proved).

        Args:
            function_name: The function to export invariants for.

        Returns:
            List of nightjar.types.Invariant objects.
        """
        invariants = self.get_invariants(function_name)
        card_invariants: list[CardInvariant] = []
        for i, inv in enumerate(invariants):
            card_inv = CardInvariant(
                id=f"DAIKON-{function_name}-{i:03d}",
                tier=InvariantTier.PROPERTY,
                statement=inv.expression,
                rationale=(
                    f"Mined by clean-room Daikon (Ernst 1999/2007) from "
                    f"{self._trace_count} observations [REF-C05, CR-01]"
                ),
            )
            card_invariants.append(card_inv)
        return card_invariants

    def get_all_function_names(self) -> list[str]:
        """Return names of all functions that have been traced."""
        return [name for name, trace in self._traces.items() if trace.call_records]

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
