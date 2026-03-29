"""Tests for nightjar watch daemon — sub-second verification feedback.

Validates the 4-tier streaming verification engine:
  Tier 0: SYNTAX    (<100ms)  — AST parse
  Tier 1: STRUCTURAL (<2s)    — deps, schema
  Tier 2: PROPERTY   (<10s)   — Hypothesis PBT
  Tier 3: FORMAL     (1-30s)  — Dafny

References:
- Scout 5 architecture diagram — 4-tier streaming verification
- Scout 5 F2 — Dafny LSP 500ms debounce pattern
- watchdog: https://github.com/gorakhargosh/watchdog (Apache-2.0)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("watchdog", reason="watchdog not installed — skip watch tests")

from nightjar.watch import (
    CardChangeHandler,
    run_tiered_verification,
    DEBOUNCE_SECONDS,
    TierEvent,
)


# ── constants ──────────────────────────────────────────────────────────────


class TestDebounceConstant:
    """Debounce constant must match Dafny LSP 500ms pattern [Scout 5 F2]."""

    def test_debounce_is_500ms(self):
        """Debounce must be 0.5s — matches Dafny LSP idle delay."""
        assert DEBOUNCE_SECONDS == 0.5, (
            "DEBOUNCE_SECONDS must be 0.5 (Scout 5 F2: Dafny LSP 500ms pattern)"
        )


# ── TierEvent ─────────────────────────────────────────────────────────────


class TestTierEvent:
    """TierEvent data structure carries tier result to the callback."""

    def test_tier_event_has_required_fields(self):
        """TierEvent must have tier, status, and duration_ms fields."""
        event = TierEvent(tier=0, status="pass", duration_ms=50)
        assert event.tier == 0
        assert event.status == "pass"
        assert event.duration_ms == 50

    def test_tier_event_all_status_values(self):
        """TierEvent status accepts 'pass', 'fail', and 'skip'."""
        for status in ("pass", "fail", "skip"):
            event = TierEvent(tier=1, status=status, duration_ms=10)
            assert event.status == status


# ── CardChangeHandler ──────────────────────────────────────────────────────


class TestCardChangeHandler:
    """Event handler for .card.md file changes with 500ms debouncing."""

    def _make_event(self, src_path: str, is_directory: bool = False):
        """Create a mock watchdog FileSystemEvent."""
        event = MagicMock()
        event.src_path = src_path
        event.is_directory = is_directory
        return event

    def test_detects_card_md_change(self):
        """Handler starts a debounce timer when a .card.md file is modified [Scout 5]."""
        callback = MagicMock()
        handler = CardChangeHandler(callback=callback)
        event = self._make_event(".card/auth.card.md")

        with patch("threading.Timer") as mock_timer_cls:
            mock_timer = MagicMock()
            mock_timer_cls.return_value = mock_timer
            handler.on_modified(event)

        # Timer should have been started (debounce set)
        mock_timer.start.assert_called_once()

    def test_ignores_non_card_md_files(self):
        """Handler ignores changes to files that are not .card.md."""
        callback = MagicMock()
        handler = CardChangeHandler(callback=callback)
        event = self._make_event(".card/README.md")

        with patch("threading.Timer") as mock_timer_cls:
            handler.on_modified(event)

        mock_timer_cls.assert_not_called()

    def test_ignores_directory_events(self):
        """Handler ignores directory modification events."""
        callback = MagicMock()
        handler = CardChangeHandler(callback=callback)
        event = self._make_event(".card/", is_directory=True)

        with patch("threading.Timer") as mock_timer_cls:
            handler.on_modified(event)

        mock_timer_cls.assert_not_called()

    def test_debounces_rapid_changes(self):
        """Rapid changes within debounce window: prior timer is cancelled [Scout 5 F2]."""
        callback = MagicMock()
        handler = CardChangeHandler(callback=callback)
        timers_created = []

        def make_timer(delay, fn, args=None, kwargs=None):
            t = MagicMock()
            timers_created.append(t)
            return t

        event = self._make_event(".card/auth.card.md")

        with patch("threading.Timer", side_effect=make_timer):
            handler.on_modified(event)  # creates timer[0], starts it
            handler.on_modified(event)  # cancels timer[0], creates timer[1]
            handler.on_modified(event)  # cancels timer[1], creates timer[2]

        # Three timers created total
        assert len(timers_created) == 3
        # First two were cancelled (debounce resets)
        assert timers_created[0].cancel.called
        assert timers_created[1].cancel.called

    def test_timer_uses_debounce_delay(self):
        """Timer delay must equal DEBOUNCE_SECONDS (0.5s) [Scout 5 F2]."""
        callback = MagicMock()
        handler = CardChangeHandler(callback=callback)
        event = self._make_event(".card/payment.card.md")

        captured_delay = {}

        def capture_timer(delay, fn, args=None, kwargs=None):
            captured_delay["delay"] = delay
            t = MagicMock()
            return t

        with patch("threading.Timer", side_effect=capture_timer):
            handler.on_modified(event)

        assert captured_delay["delay"] == DEBOUNCE_SECONDS


# ── run_tiered_verification ────────────────────────────────────────────────


def _make_tier_fn(tier_num: int, status: str = "pass"):
    """Build a tier function that fires a TierEvent and returns pass/fail."""
    def impl(card_path: str, callback) -> bool:
        callback(TierEvent(tier=tier_num, status=status, duration_ms=10))
        return status != "fail"
    return impl


class TestRunTieredVerification:
    """4-tier streaming verification with sequential tier ordering [Scout 5]."""

    def test_runs_tier0_before_tier1(self, tmp_path):
        """Tier 0 (syntax) must complete before Tier 1 (structural) starts [Scout 5]."""
        call_order = []

        def track(n):
            def impl(path, cb):
                call_order.append(n)
                cb(TierEvent(tier=n, status="pass", duration_ms=10))
                return True
            return impl

        card_file = tmp_path / "test.card.md"
        card_file.write_text("# spec\n", encoding="utf-8")

        with (
            patch("nightjar.watch._run_tier_0", side_effect=track(0)),
            patch("nightjar.watch._run_tier_1", side_effect=track(1)),
            patch("nightjar.watch._run_tier_2", side_effect=track(2)),
            patch("nightjar.watch._run_tier_3", side_effect=track(3)),
        ):
            run_tiered_verification(str(card_file), lambda e: None)

        assert call_order.index(0) < call_order.index(1), (
            "Tier 0 (syntax) must run before Tier 1 (structural)"
        )

    def test_tiers_run_sequentially_0_to_3(self, tmp_path):
        """All 4 tiers fire events in order 0→1→2→3 [Scout 5]."""
        tier_order = []

        card_file = tmp_path / "spec.card.md"
        card_file.write_text("# spec\n", encoding="utf-8")

        with (
            patch("nightjar.watch._run_tier_0", side_effect=_make_tier_fn(0)),
            patch("nightjar.watch._run_tier_1", side_effect=_make_tier_fn(1)),
            patch("nightjar.watch._run_tier_2", side_effect=_make_tier_fn(2)),
            patch("nightjar.watch._run_tier_3", side_effect=_make_tier_fn(3)),
        ):
            run_tiered_verification(str(card_file), lambda e: tier_order.append(e.tier))

        assert tier_order == [0, 1, 2, 3], (
            f"Tiers must fire 0→1→2→3, got {tier_order}"
        )

    def test_stops_on_tier_failure(self, tmp_path):
        """If a tier fails, subsequent tiers do NOT run [Scout 5 short-circuit]."""
        tiers_run = []

        card_file = tmp_path / "spec.card.md"
        card_file.write_text("# spec\n", encoding="utf-8")

        with (
            patch("nightjar.watch._run_tier_0", side_effect=_make_tier_fn(0, "fail")),
            patch("nightjar.watch._run_tier_1") as m1,
            patch("nightjar.watch._run_tier_2") as m2,
            patch("nightjar.watch._run_tier_3") as m3,
        ):
            run_tiered_verification(
                str(card_file),
                lambda e: tiers_run.append(e.tier),
            )

        assert tiers_run == [0], (
            f"Only tier 0 should have run on failure, got {tiers_run}"
        )
        m1.assert_not_called()
        m2.assert_not_called()
        m3.assert_not_called()
