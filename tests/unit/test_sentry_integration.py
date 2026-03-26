"""Tests for Sentry error tracking → immune system feed.

TDD: Tests written FIRST before implementation.

Pipeline:
    Sentry production error
    → sentry_integration.py (capture + convert)
    → immune/collector.py (CallTrace format)
    → immune/daikon.py (invariant templates)
    → CandidateInvariant (invariant proposal)

References:
- nightjar-upgrade-plan.md U5.1 (lines 616-638)
- Sentry Python SDK: https://docs.sentry.io/platforms/python/
- immune/pipeline.py — run_mining_tiers() Tier 2 entry point
- immune/collector.py — CallTrace dataclass
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass
from typing import Optional


class TestSentryEventConversion:
    """Tests for converting Sentry events to immune system candidates."""

    def test_sentry_event_converts_to_invariant_candidate(self):
        """A Sentry error event is converted to a CandidateInvariant.

        The key insight: 'this function threw ValueError with input X'
        → candidate invariant: 'input X must be validated'
        """
        from nightjar.sentry_integration import sentry_event_to_candidate

        # Sentry event dict (subset of actual Sentry event structure)
        event = {
            "event_id": "abc123",
            "level": "error",
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "amount must be positive",
                        "stacktrace": {
                            "frames": [
                                {
                                    "module": "payment",
                                    "function": "deduct",
                                    "vars": {"amount": "-50", "balance": "100"},
                                }
                            ]
                        },
                    }
                ]
            },
            "tags": {"module": "payment"},
        }

        candidate = sentry_event_to_candidate(event)

        assert candidate is not None
        assert candidate.expression  # Must have a proposed invariant expression
        assert "amount" in candidate.expression or "positive" in candidate.expression

    def test_sentry_event_with_no_frames_returns_none(self):
        """Events with no stacktrace frames return None gracefully."""
        from nightjar.sentry_integration import sentry_event_to_candidate

        event = {
            "event_id": "xyz789",
            "level": "error",
            "exception": {"values": [{"type": "RuntimeError", "value": "unknown"}]},
        }

        # No frames → no invariant to propose
        candidate = sentry_event_to_candidate(event)
        assert candidate is None

    def test_sentry_event_extracts_function_name(self):
        """sentry_event_to_candidate extracts the function name from the frame."""
        from nightjar.sentry_integration import sentry_event_to_candidate

        event = {
            "event_id": "e1",
            "level": "error",
            "exception": {
                "values": [
                    {
                        "type": "TypeError",
                        "value": "expected int, got str",
                        "stacktrace": {
                            "frames": [
                                {
                                    "module": "auth",
                                    "function": "validate_token",
                                    "vars": {"token": "None"},
                                }
                            ]
                        },
                    }
                ]
            },
        }

        candidate = sentry_event_to_candidate(event)

        assert candidate is not None
        # Function context should appear in the candidate
        assert "validate_token" in candidate.expression or candidate.function_name == "validate_token"

    def test_sentry_error_non_null_invariant_for_none_args(self):
        """TypeError with None arg generates a non-null precondition invariant."""
        from nightjar.sentry_integration import sentry_event_to_candidate

        event = {
            "event_id": "e2",
            "level": "error",
            "exception": {
                "values": [
                    {
                        "type": "AttributeError",
                        "value": "'NoneType' object has no attribute 'strip'",
                        "stacktrace": {
                            "frames": [
                                {
                                    "module": "parser",
                                    "function": "parse_spec",
                                    "vars": {"content": "None"},
                                }
                            ]
                        },
                    }
                ]
            },
        }

        candidate = sentry_event_to_candidate(event)
        assert candidate is not None
        # Should propose a non-null precondition
        expr = candidate.expression.lower()
        assert "none" in expr or "is not" in expr or "content" in expr


class TestSentryFeed:
    """Tests for the Sentry → immune pipeline feed."""

    def test_sentry_feed_triggers_mining_pipeline(self):
        """sentry_feed() processes an event and returns a list of candidates.

        Full pipeline: Sentry event → conversion → immune candidate list.
        """
        from nightjar.sentry_integration import sentry_feed

        events = [
            {
                "event_id": "f1",
                "level": "error",
                "exception": {
                    "values": [
                        {
                            "type": "ValueError",
                            "value": "balance cannot be negative",
                            "stacktrace": {
                                "frames": [
                                    {
                                        "module": "payment",
                                        "function": "withdraw",
                                        "vars": {"balance": "-100"},
                                    }
                                ]
                            },
                        }
                    ]
                },
            }
        ]

        candidates = sentry_feed(events)

        assert isinstance(candidates, list)
        assert len(candidates) >= 1
        assert all(hasattr(c, "expression") for c in candidates)

    def test_sentry_feed_empty_events_returns_empty(self):
        """sentry_feed() with empty event list returns empty candidates list."""
        from nightjar.sentry_integration import sentry_feed

        candidates = sentry_feed([])
        assert candidates == []

    def test_sentry_feed_skips_non_error_events(self):
        """sentry_feed() skips info/warning events — only errors become candidates."""
        from nightjar.sentry_integration import sentry_feed

        events = [
            {
                "event_id": "w1",
                "level": "info",  # Not an error
                "message": "User logged in",
            },
            {
                "event_id": "w2",
                "level": "warning",
                "message": "Slow query",
            },
        ]

        candidates = sentry_feed(events)
        assert candidates == []

    def test_sentry_feed_deduplicates_same_error(self):
        """sentry_feed() deduplicates identical errors from the same function."""
        from nightjar.sentry_integration import sentry_feed

        same_event = {
            "event_id": "dup",
            "level": "error",
            "exception": {
                "values": [
                    {
                        "type": "ValueError",
                        "value": "x must be positive",
                        "stacktrace": {
                            "frames": [{"module": "m", "function": "f", "vars": {"x": "-1"}}]
                        },
                    }
                ]
            },
        }

        # 3 identical events → 1 candidate (deduplication)
        candidates = sentry_feed([same_event, same_event, same_event])
        assert len(candidates) == 1


class TestSentryWebhookServer:
    """Tests for the Sentry webhook integration."""

    def test_process_webhook_payload_valid_json(self):
        """process_webhook_payload() accepts valid Sentry webhook JSON."""
        from nightjar.sentry_integration import process_webhook_payload

        payload = json.dumps({
            "action": "created",
            "data": {
                "error": {
                    "event_id": "e1",
                    "level": "error",
                    "exception": {
                        "values": [
                            {
                                "type": "ValueError",
                                "value": "bad input",
                                "stacktrace": {
                                    "frames": [
                                        {"module": "m", "function": "f", "vars": {}}
                                    ]
                                },
                            }
                        ]
                    },
                }
            },
        })

        result = process_webhook_payload(payload)
        assert result is not None

    def test_process_webhook_payload_invalid_json_returns_none(self):
        """process_webhook_payload() returns None for invalid JSON."""
        from nightjar.sentry_integration import process_webhook_payload

        result = process_webhook_payload("not valid json {{")
        assert result is None

    def test_dsn_from_env_var(self):
        """get_sentry_dsn() reads DSN from SENTRY_DSN env var."""
        import os
        from nightjar.sentry_integration import get_sentry_dsn
        from unittest.mock import patch

        with patch.dict(os.environ, {"SENTRY_DSN": "https://key@sentry.io/12345"}):
            dsn = get_sentry_dsn()

        assert dsn == "https://key@sentry.io/12345"

    def test_dsn_missing_returns_none(self):
        """get_sentry_dsn() returns None if SENTRY_DSN not configured."""
        import os
        from nightjar.sentry_integration import get_sentry_dsn
        from unittest.mock import patch

        with patch.dict(os.environ, {}, clear=True):
            # Ensure SENTRY_DSN is not set
            os.environ.pop("SENTRY_DSN", None)
            dsn = get_sentry_dsn()

        assert dsn is None
