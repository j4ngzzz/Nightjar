"""Sentry-style error capture with semantic fingerprinting.

Captures unhandled exceptions with PII-stripped message templates and
semantic fingerprinting for grouping identical error classes across
different stack paths.

References:
- ARCHITECTURE.md Section 6, Stage 1 — third collection signal
- [REF-C05] Dynamic Invariant Mining — error-driven invariant discovery
"""

from __future__ import annotations

import hashlib
import re
import sys
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator, Optional

from immune.types import ErrorTrace

# PII patterns — ordered so more specific patterns match first
_PII_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Email addresses
    (re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"), "{EMAIL}"),
    # UUIDs
    (re.compile(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
        r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    ), "{UUID}"),
    # IPv4 addresses
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "{IP}"),
    # Phone numbers (international and US formats)
    (re.compile(r"\+?\d[\d\s\-]{8,}\d"), "{PHONE}"),
    # Long numeric IDs (6+ digits to avoid replacing small numbers)
    (re.compile(r"\b\d{6,}\b"), "{ID}"),
    # Quoted string values (single or double quotes) — normalizes error messages
    (re.compile(r"'[^']*'"), "'{VALUE}'"),
    (re.compile(r'"[^"]*"'), '"{VALUE}"'),
]


def strip_pii(message: str) -> str:
    """Remove PII from an error message using regex patterns.

    Replaces email addresses, IP addresses, phone numbers, UUIDs,
    and long numeric IDs with placeholder tokens.

    Args:
        message: The raw error message.

    Returns:
        Message with PII replaced by tokens like {EMAIL}, {IP}, etc.
    """
    result = message
    for pattern, replacement in _PII_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def compute_semantic_fingerprint(
    exception_class: str,
    message: str,
    function: str,
) -> str:
    """Compute a semantic fingerprint for error grouping.

    Groups identical error classes from the same function, regardless
    of the specific values in the error message. Two ValueError crashes
    on int parsing in the same function produce the same fingerprint.

    The fingerprint is computed from:
    1. Exception class name
    2. PII-stripped message template
    3. Function name where the error occurred

    Args:
        exception_class: The exception class name (e.g. "ValueError").
        message: The raw error message (will be PII-stripped).
        function: The function name where the error occurred.

    Returns:
        A hex digest string that groups semantically identical errors.
    """
    template = strip_pii(message)
    key = f"{exception_class}:{template}:{function}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def capture_exception() -> ErrorTrace:
    """Capture the current exception as an ErrorTrace.

    Must be called within an except block (uses sys.exc_info()).

    Returns:
        An ErrorTrace with PII-stripped message and semantic fingerprint.

    Raises:
        RuntimeError: If called outside an exception handler.
    """
    exc_type, exc_value, exc_tb = sys.exc_info()
    if exc_type is None or exc_value is None or exc_tb is None:
        raise RuntimeError("capture_exception() called outside except block")

    exception_class = exc_type.__name__
    raw_message = str(exc_value)
    message_template = strip_pii(raw_message)

    # Walk the traceback to find the innermost frame
    tb = exc_tb
    while tb.tb_next is not None:
        tb = tb.tb_next

    frame = tb.tb_frame
    function = frame.f_code.co_name
    module = frame.f_globals.get("__name__", "")

    # Build input shape from local variables at crash point
    input_shape = _extract_input_shape(frame.f_locals)

    fingerprint = compute_semantic_fingerprint(
        exception_class, raw_message, function
    )

    return ErrorTrace(
        exception_class=exception_class,
        message_template=message_template,
        stack_fingerprint=fingerprint,
        function=function,
        module=module,
        input_shape=input_shape,
    )


def _extract_input_shape(locals_dict: dict) -> str:
    """Extract type-shape of local variables at crash point.

    Returns a compact string like "x:int, y:str, items:list[3]".
    """
    parts = []
    for name, value in sorted(locals_dict.items()):
        if name.startswith("_"):
            continue
        type_name = type(value).__name__
        try:
            length = len(value)
            parts.append(f"{name}:{type_name}[{length}]")
        except TypeError:
            parts.append(f"{name}:{type_name}")
    return ", ".join(parts[:10])  # Limit to 10 variables


class ErrorCapture:
    """Collects error traces via context manager.

    Usage:
        ec = ErrorCapture()
        with ec.watch():
            risky_operation()
        for trace in ec.captured:
            store.insert_error_trace(trace)

    Args:
        reraise: If True, re-raise exceptions after capturing.
    """

    def __init__(self, reraise: bool = False) -> None:
        self.reraise = reraise
        self.captured: list[ErrorTrace] = []

    @contextmanager
    def watch(self) -> Generator[None, None, None]:
        """Context manager that captures exceptions as ErrorTraces."""
        try:
            yield
        except Exception:
            trace = capture_exception()
            self.captured.append(trace)
            if self.reraise:
                raise
