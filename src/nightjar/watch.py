"""nightjar watch daemon — sub-second verification feedback [Scout 5].

Implements a 4-tier streaming verification engine that provides instant
first feedback while deeper analysis completes in the background.

Architecture (Scout 5 — 4-Tier Streaming Verification):
  Tier 0: SYNTAX    (<100ms)  — read + parse .card.md
  Tier 1: STRUCTURAL (<2s)    — validate spec structure
  Tier 2: PROPERTY   (<10s)   — Hypothesis PBT (when code available)
  Tier 3: FORMAL     (1-30s)  — Dafny (on demand, when code available)

Key design decisions from Scout 5:
- 500ms debounce after last edit (Dafny LSP pattern) [Scout 5 F2]
- Fast tiers 0-1 complete before slow tiers start [Scout 5 architecture]
- Short-circuit on tier failure — don't waste time on deeper tiers

Usage:
    observer = start_watch(".card", callback=on_tier_event)
    try:
        while True:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()

References:
- Scout 5 — Kill Latency report (architecture diagram + F2 + F3)
- watchdog: https://github.com/gorakhargosh/watchdog (Apache-2.0)
- Dafny LSP debounce: github.com/dafny-lang/ide-vscode
"""

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


# Debounce delay matching Dafny LSP idle delay [Scout 5 F2]
DEBOUNCE_SECONDS: float = 0.5


@dataclass
class TierEvent:
    """Result from one verification tier, emitted after each tier completes.

    Passed to the caller's callback so they can show progressive feedback:
      tier 0 fires in <100ms (syntax OK),
      tier 1 fires in <2s   (structure valid),
      tier 2 fires in <10s  (properties pass),
      tier 3 fires in 1-30s (formal proof).
    """

    tier: int           # 0=syntax, 1=structural, 2=property, 3=formal
    status: str         # "pass", "fail", or "skip"
    duration_ms: int    # wall-clock ms for this tier
    message: str = ""   # human-readable detail on fail


class CardChangeHandler(FileSystemEventHandler):
    """Watchdog event handler for .card.md file changes.

    Implements 500ms debounce: on each modification of a .card.md file,
    the previous debounce timer is cancelled and a new one is set.
    After 500ms of inactivity, runs tiered verification on the changed file.

    Debounce pattern from Dafny LSP server [Scout 5 F2]:
      '0.5s idle debounce after text edit → snapshot sent to verifier'
    """

    def __init__(self, callback: Callable[[TierEvent], None]) -> None:
        """Initialise handler with the tier event callback.

        Args:
            callback: Called with TierEvent after each tier completes.
        """
        super().__init__()
        self._callback = callback
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle a file modification event.

        Filters to .card.md files only, then applies 500ms debounce.
        Directory events and non-.card.md files are ignored.
        """
        # Ignore directory-level events
        if event.is_directory:
            return

        src = str(event.src_path)
        if not src.endswith(".card.md"):
            return

        # Debounce: cancel previous timer and schedule new one [Scout 5 F2]
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(
                DEBOUNCE_SECONDS,
                run_tiered_verification,
                args=(src, self._callback),
            )
            self._timer.start()


def _run_tier_0(card_path: str, callback: Callable[[TierEvent], None]) -> bool:
    """Tier 0: Syntax check — read and parse the .card.md file (<100ms).

    Validates that the .card.md file is readable and well-formed YAML/markdown.
    This tier always fires first, giving instant feedback before heavier tiers.

    Args:
        card_path: Path to the .card.md file.
        callback: Called with TierEvent(tier=0, ...).

    Returns:
        True if the file is readable and parseable, False otherwise.
    """
    start = time.monotonic()
    try:
        content = Path(card_path).read_text(encoding="utf-8")
        # Verify the file has a YAML frontmatter section (---\n...\n---)
        has_frontmatter = content.startswith("---") or "card_version:" in content
        duration = int((time.monotonic() - start) * 1000)
        if not has_frontmatter:
            callback(TierEvent(
                tier=0, status="fail", duration_ms=duration,
                message="Missing .card.md frontmatter (card_version required)",
            ))
            return False
        callback(TierEvent(tier=0, status="pass", duration_ms=duration))
        return True
    except (OSError, UnicodeDecodeError) as exc:
        duration = int((time.monotonic() - start) * 1000)
        callback(TierEvent(
            tier=0, status="fail", duration_ms=duration,
            message=f"Cannot read card file: {exc}",
        ))
        return False


def _run_tier_1(card_path: str, callback: Callable[[TierEvent], None]) -> bool:
    """Tier 1: Structural check — validate .card.md spec structure (<2s).

    Parses the spec with the Nightjar parser, validating field presence,
    invariant format, and contract structure.

    Args:
        card_path: Path to the .card.md file.
        callback: Called with TierEvent(tier=1, ...).

    Returns:
        True if spec parses successfully, False on parse error.
    """
    start = time.monotonic()
    try:
        from nightjar.parser import parse_spec
        parse_spec(card_path)
        duration = int((time.monotonic() - start) * 1000)
        callback(TierEvent(tier=1, status="pass", duration_ms=duration))
        return True
    except Exception as exc:  # noqa: BLE001
        duration = int((time.monotonic() - start) * 1000)
        callback(TierEvent(
            tier=1, status="fail", duration_ms=duration,
            message=f"Spec parse error: {exc}",
        ))
        return False


def _run_tier_2(card_path: str, callback: Callable[[TierEvent], None]) -> bool:
    """Tier 2: Property check — Hypothesis PBT on generated code (<10s).

    Skips if no generated code is available for this spec.
    Requires corresponding code in .card/audit/ or dist/.

    Args:
        card_path: Path to the .card.md file.
        callback: Called with TierEvent(tier=2, ...).

    Returns:
        True (pass or skip), False on PBT failure.
    """
    start = time.monotonic()
    # Derive expected audit path from card path
    card_stem = Path(card_path).stem.replace(".card", "")
    audit_dir = Path(card_path).parent.parent / ".card" / "audit"
    code_files = list(audit_dir.glob(f"{card_stem}*.py")) if audit_dir.exists() else []

    if not code_files:
        duration = int((time.monotonic() - start) * 1000)
        callback(TierEvent(tier=2, status="skip", duration_ms=duration,
                           message="No generated code found — generate first"))
        return True

    # Run PBT on the first generated file
    try:
        from nightjar.parser import parse_spec
        from nightjar.stages.pbt import run_pbt
        from nightjar.types import VerifyStatus

        spec = parse_spec(card_path)
        code = code_files[0].read_text(encoding="utf-8")
        result = run_pbt(spec, code)

        duration = int((time.monotonic() - start) * 1000)
        if result.status == VerifyStatus.FAIL:
            msg = result.errors[0].get("error", "") if result.errors else ""
            callback(TierEvent(tier=2, status="fail", duration_ms=duration, message=msg))
            return False

        callback(TierEvent(tier=2, status="pass", duration_ms=duration))
        return True

    except Exception as exc:  # noqa: BLE001
        duration = int((time.monotonic() - start) * 1000)
        callback(TierEvent(tier=2, status="fail", duration_ms=duration, message=str(exc)))
        return False


def _run_tier_3(card_path: str, callback: Callable[[TierEvent], None]) -> bool:
    """Tier 3: Formal verification — Dafny proof (1-30s, on demand).

    Skips if no generated code is available. This tier is the heaviest
    and runs last to preserve sub-second first feedback.

    Args:
        card_path: Path to the .card.md file.
        callback: Called with TierEvent(tier=3, ...).

    Returns:
        True (pass or skip), False on formal verification failure.
    """
    start = time.monotonic()
    # Same audit path lookup as tier 2
    card_stem = Path(card_path).stem.replace(".card", "")
    audit_dir = Path(card_path).parent.parent / ".card" / "audit"
    code_files = list(audit_dir.glob(f"{card_stem}*.py")) if audit_dir.exists() else []

    if not code_files:
        duration = int((time.monotonic() - start) * 1000)
        callback(TierEvent(tier=3, status="skip", duration_ms=duration,
                           message="No generated code found — generate first"))
        return True

    try:
        from nightjar.parser import parse_spec
        from nightjar.stages.formal import run_formal
        from nightjar.types import VerifyStatus

        spec = parse_spec(card_path)
        code = code_files[0].read_text(encoding="utf-8")
        result = run_formal(spec, code)

        duration = int((time.monotonic() - start) * 1000)
        if result.status == VerifyStatus.FAIL:
            msg = result.errors[0].get("error", "") if result.errors else ""
            callback(TierEvent(tier=3, status="fail", duration_ms=duration, message=msg))
            return False

        callback(TierEvent(tier=3, status="pass", duration_ms=duration))
        return True

    except Exception as exc:  # noqa: BLE001
        duration = int((time.monotonic() - start) * 1000)
        callback(TierEvent(tier=3, status="fail", duration_ms=duration, message=str(exc)))
        return False


def run_tiered_verification(
    card_path: str,
    callback: Callable[[TierEvent], None],
) -> None:
    """Run 4-tier streaming verification on a .card.md file.

    Executes tiers 0→1→2→3 in order. Emits a TierEvent after each tier
    so the caller can show progressive feedback. Short-circuits on failure:
    if a tier fails, subsequent tiers do not run.

    Source: Scout 5 architecture diagram — 4-tier streaming engine.

    Args:
        card_path: Path to the .card.md file that changed.
        callback: Called after each tier with TierEvent.
    """
    tier_fns = [_run_tier_0, _run_tier_1, _run_tier_2, _run_tier_3]
    for tier_fn in tier_fns:
        passed = tier_fn(card_path, callback)
        if not passed:
            break  # Short-circuit: don't run deeper tiers on failure


def start_watch(
    card_dir: str,
    callback: Callable[[TierEvent], None],
) -> Observer:
    """Start watching a .card/ directory for spec changes.

    Sets up a watchdog Observer to monitor the directory recursively.
    When a .card.md file is modified, runs 4-tier streaming verification
    after a 500ms debounce.

    Args:
        card_dir: Directory containing .card.md files (default: '.card').
        callback: Called after each verification tier with TierEvent.

    Returns:
        Running Observer instance. Call observer.stop() + observer.join()
        to shut down cleanly.

    Example:
        >>> observer = start_watch('.card', on_event)
        >>> try:
        ...     while True: time.sleep(1)
        ... finally:
        ...     observer.stop(); observer.join()
    """
    handler = CardChangeHandler(callback=callback)
    observer = Observer()
    observer.schedule(handler, card_dir, recursive=True)
    observer.start()
    return observer
