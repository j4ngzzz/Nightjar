"""Tests for Sentry-style error capture with semantic fingerprinting.

Validates PII stripping, semantic grouping, and error trace creation.

References:
- ARCHITECTURE.md Section 6, Stage 1 — third signal: error capture
"""

import pytest

from immune.error_capture import (
    capture_exception,
    compute_semantic_fingerprint,
    strip_pii,
    ErrorCapture,
)
from immune.types import ErrorTrace


# ---------------------------------------------------------------------------
# Test: PII stripping
# ---------------------------------------------------------------------------

class TestPiiStripping:
    def test_strips_email(self):
        msg = "User john.doe@example.com not found"
        stripped = strip_pii(msg)
        assert "john.doe@example.com" not in stripped
        assert "{EMAIL}" in stripped

    def test_strips_ip_address(self):
        msg = "Connection from 192.168.1.42 refused"
        stripped = strip_pii(msg)
        assert "192.168.1.42" not in stripped
        assert "{IP}" in stripped

    def test_strips_phone_number(self):
        msg = "SMS sent to +1-555-123-4567"
        stripped = strip_pii(msg)
        assert "555-123-4567" not in stripped
        assert "{PHONE}" in stripped

    def test_strips_uuid(self):
        msg = "User 550e8400-e29b-41d4-a716-446655440000 deleted"
        stripped = strip_pii(msg)
        assert "550e8400-e29b-41d4-a716-446655440000" not in stripped
        assert "{UUID}" in stripped

    def test_strips_numeric_ids(self):
        msg = "Order 123456789 not found"
        stripped = strip_pii(msg)
        assert "123456789" not in stripped
        assert "{ID}" in stripped

    def test_preserves_non_pii(self):
        msg = "invalid literal for int() with base 10"
        stripped = strip_pii(msg)
        assert stripped == msg

    def test_strips_multiple_patterns(self):
        msg = "User john@test.com at 10.0.0.1 failed with order 99999"
        stripped = strip_pii(msg)
        assert "john@test.com" not in stripped
        assert "10.0.0.1" not in stripped


# ---------------------------------------------------------------------------
# Test: Semantic fingerprinting
# ---------------------------------------------------------------------------

class TestSemanticFingerprinting:
    def test_same_error_different_values_same_fingerprint(self):
        """Two ValueError on int parse should group together."""
        fp1 = compute_semantic_fingerprint(
            exception_class="ValueError",
            message="invalid literal for int() with base 10: '42'",
            function="parse_id",
        )
        fp2 = compute_semantic_fingerprint(
            exception_class="ValueError",
            message="invalid literal for int() with base 10: 'abc'",
            function="parse_id",
        )
        assert fp1 == fp2

    def test_different_exception_class_different_fingerprint(self):
        fp1 = compute_semantic_fingerprint(
            exception_class="ValueError",
            message="bad value",
            function="parse",
        )
        fp2 = compute_semantic_fingerprint(
            exception_class="TypeError",
            message="bad value",
            function="parse",
        )
        assert fp1 != fp2

    def test_different_function_different_fingerprint(self):
        fp1 = compute_semantic_fingerprint(
            exception_class="ValueError",
            message="bad",
            function="func_a",
        )
        fp2 = compute_semantic_fingerprint(
            exception_class="ValueError",
            message="bad",
            function="func_b",
        )
        assert fp1 != fp2

    def test_fingerprint_is_deterministic(self):
        fp1 = compute_semantic_fingerprint("Err", "msg", "fn")
        fp2 = compute_semantic_fingerprint("Err", "msg", "fn")
        assert fp1 == fp2

    def test_fingerprint_is_string(self):
        fp = compute_semantic_fingerprint("Err", "msg", "fn")
        assert isinstance(fp, str)
        assert len(fp) > 0


# ---------------------------------------------------------------------------
# Test: capture_exception
# ---------------------------------------------------------------------------

class TestCaptureException:
    def test_captures_basic_exception(self):
        try:
            raise ValueError("bad input for user 'admin123'")
        except ValueError:
            trace = capture_exception()

        assert isinstance(trace, ErrorTrace)
        assert trace.exception_class == "ValueError"
        assert "admin123" not in trace.message_template  # quoted value stripped
        assert trace.stack_fingerprint != ""
        assert trace.function != ""

    def test_captures_type_error(self):
        try:
            raise TypeError("expected str, got int")
        except TypeError:
            trace = capture_exception()

        assert trace.exception_class == "TypeError"

    def test_captures_nested_exception(self):
        def inner():
            raise RuntimeError("inner error 12345")

        try:
            inner()
        except RuntimeError:
            trace = capture_exception()

        assert trace.exception_class == "RuntimeError"
        assert trace.function == "inner"

    def test_captures_module_info(self):
        try:
            raise KeyError("missing_key")
        except KeyError:
            trace = capture_exception()

        assert trace.module != ""


# ---------------------------------------------------------------------------
# Test: ErrorCapture context manager / decorator
# ---------------------------------------------------------------------------

class TestErrorCaptureContextManager:
    def test_context_manager_captures(self):
        ec = ErrorCapture()
        with ec.watch():
            raise ValueError("test error 999")

        assert len(ec.captured) == 1
        assert ec.captured[0].exception_class == "ValueError"

    def test_context_manager_suppresses_error(self):
        """Errors should be captured but not re-raised by default."""
        ec = ErrorCapture()
        with ec.watch():
            raise RuntimeError("suppressed")
        # Should not raise

    def test_context_manager_reraise_option(self):
        ec = ErrorCapture(reraise=True)
        with pytest.raises(RuntimeError):
            with ec.watch():
                raise RuntimeError("reraised")
        assert len(ec.captured) == 1

    def test_no_error_no_capture(self):
        ec = ErrorCapture()
        with ec.watch():
            pass  # no error
        assert len(ec.captured) == 0

    def test_multiple_captures(self):
        ec = ErrorCapture()
        for i in range(3):
            with ec.watch():
                raise ValueError(f"error {i}")
        assert len(ec.captured) == 3
