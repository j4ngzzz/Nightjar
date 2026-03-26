"""MonkeyType-style runtime type trace collection.

Uses sys.setprofile to intercept function calls and returns, recording
argument types and return types. Inspired by Instagram's MonkeyType
but reimplemented for CARD's immune system pipeline.

References:
- [REF-T12] MonkeyType — runtime type collection via sys.setprofile
- [REF-C05] Dynamic Invariant Mining — type traces as input to mining
"""

from __future__ import annotations

import inspect
import sys
import threading
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator, Optional

from immune.types import TypeTrace


@dataclass
class CallTrace:
    """A single observed function call with type information.

    Attributes:
        module: Python module name.
        function: Function name.
        arg_types: Mapping from argument name to type name.
        return_type: Type name of the return value.
    """
    module: str
    function: str
    arg_types: dict[str, str] = field(default_factory=dict)
    return_type: str = ""


class TypeCollector:
    """Collects runtime type information using sys.setprofile.

    Uses Python's profiling hook to intercept function calls and returns,
    recording the types of arguments and return values without modifying
    the traced code.

    Usage:
        collector = TypeCollector()
        with collector.trace():
            my_function(1, "hello")
        traces = collector.get_call_traces("my_function")

    References:
    - [REF-T12] MonkeyType — sys.setprofile pattern
    """

    def __init__(
        self,
        include_modules: Optional[list[str]] = None,
        max_records: int = 10000,
    ) -> None:
        """Initialize the collector.

        Args:
            include_modules: If set, only trace functions from these modules.
            max_records: Maximum call traces per function.
        """
        self._call_traces: dict[str, list[CallTrace]] = defaultdict(list)
        self._include_modules = include_modules
        self._max_records = max_records
        self._trace_count = 0
        self._lock = threading.Lock()
        # Pending calls: thread_id -> list of (func_name, module, arg_types)
        self._pending: dict[int, list[tuple[str, str, dict[str, str]]]] = defaultdict(list)

    @property
    def trace_count(self) -> int:
        """Number of function calls traced."""
        return self._trace_count

    @contextmanager
    def trace(self) -> Generator[None, None, None]:
        """Context manager that enables type tracing via sys.setprofile."""
        old_profile = sys.getprofile()
        sys.setprofile(self._profile_callback)
        try:
            yield
        finally:
            sys.setprofile(old_profile)

    def _should_trace(self, frame) -> bool:
        """Decide whether to trace a given frame."""
        code = frame.f_code
        fname = code.co_filename
        func_name = code.co_name

        # Skip this module
        if fname.endswith("collector.py") and "immune" in fname:
            return False

        # Skip stdlib and site-packages
        stdlib_markers = ("lib/python", "Lib\\", "site-packages",
                          "importlib", "<frozen", "<string>",
                          "contextlib", "threading")
        if any(m in fname for m in stdlib_markers):
            return False

        # Skip dunder methods
        if func_name.startswith("__") and func_name.endswith("__"):
            return False

        # Apply module filter
        if self._include_modules is not None:
            module = frame.f_globals.get("__name__", "")
            if module not in self._include_modules:
                return False

        return True

    def _profile_callback(self, frame, event: str, arg: Any) -> None:
        """sys.setprofile callback — intercepts call and return events."""
        if event == "call":
            if not self._should_trace(frame):
                return

            code = frame.f_code
            func_name = code.co_name
            module = frame.f_globals.get("__name__", "")

            # Extract argument types
            try:
                arg_info = inspect.getargvalues(frame)
            except Exception:
                return
            arg_types = {}
            for name in arg_info.args:
                if name == "self":
                    continue
                try:
                    val = frame.f_locals[name]
                    arg_types[name] = type(val).__name__
                except KeyError:
                    pass

            tid = threading.get_ident()
            with self._lock:
                self._pending[tid].append((func_name, module, arg_types))

        elif event == "return":
            tid = threading.get_ident()
            with self._lock:
                pending = self._pending.get(tid, [])
                if not pending:
                    return
                func_name, module, arg_types = pending.pop()

                return_type = type(arg).__name__
                ct = CallTrace(
                    module=module,
                    function=func_name,
                    arg_types=arg_types,
                    return_type=return_type,
                )

                traces = self._call_traces[func_name]
                if len(traces) < self._max_records:
                    traces.append(ct)
                self._trace_count += 1

    def get_call_traces(self, function_name: str) -> list[CallTrace]:
        """Get all recorded call traces for a function."""
        return list(self._call_traces.get(function_name, []))

    def get_unique_signatures(self, function_name: str) -> list[CallTrace]:
        """Get deduplicated type signatures for a function.

        Multiple calls with the same argument and return types are
        consolidated into a single signature.
        """
        traces = self._call_traces.get(function_name, [])
        seen: set[str] = set()
        unique: list[CallTrace] = []
        for ct in traces:
            key = f"{ct.arg_types}:{ct.return_type}"
            if key not in seen:
                seen.add(key)
                unique.append(ct)
        return unique

    def export_type_traces(
        self, function_name: str, module: str = "",
    ) -> list[TypeTrace]:
        """Export collected types as immune system TypeTrace objects.

        Consolidates to unique signatures, then creates one TypeTrace
        per argument and return type.

        Args:
            function_name: Function to export traces for.
            module: Module name override (uses recorded module if empty).

        Returns:
            List of TypeTrace objects.
        """
        sigs = self.get_unique_signatures(function_name)
        type_traces: list[TypeTrace] = []
        for sig in sigs:
            mod = module or sig.module
            for arg_name, arg_type in sig.arg_types.items():
                type_traces.append(TypeTrace(
                    module=mod,
                    function=function_name,
                    arg_name=arg_name,
                    observed_type=arg_type,
                ))
            if sig.return_type:
                type_traces.append(TypeTrace(
                    module=mod,
                    function=function_name,
                    arg_name="return",
                    observed_type=sig.return_type,
                ))
        return type_traces

    def get_all_function_names(self) -> list[str]:
        """Return names of all functions that have been traced."""
        return [name for name, traces in self._call_traces.items() if traces]

    def clear(self, function_name: Optional[str] = None) -> None:
        """Clear recorded traces."""
        if function_name:
            self._call_traces.pop(function_name, None)
        else:
            self._call_traces.clear()
            self._trace_count = 0
