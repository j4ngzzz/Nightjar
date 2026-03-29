"""Nightjar immune system CLI commands.

Wires the 3-tier invariant mining pipeline into the CLI as a ``nightjar immune``
command group.  All imports from ``immune.*`` are lazy (inside function bodies)
so this module loads even when the immune system's optional deps are absent.

Register the group in cli.py once Wave 2 is complete:
    from nightjar.immune_commands import immune_group
    main.add_command(immune_group)

References:
- [REF-C09] Immune System / Acquired Immunity
- [REF-C05] Dynamic Invariant Mining (Daikon)
- [REF-C06] LLM-Driven Invariant Enrichment
- [REF-T17] Click CLI framework
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import click

# Default path for the immune trace database
_DEFAULT_DB = str(Path(".card") / "immune.db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_error(package: str, extra: str = "") -> str:
    """Return a formatted install hint for a missing package."""
    hint = f"Run: pip install {package}"
    if extra:
        hint = extra
    return (
        f"Immune system dependency '{package}' is not installed.\n"
        f"{hint}\n"
        "If you are using uv: uv pip install nightjar[immune]"
    )


def _is_utf8_stdout() -> bool:
    """Return True when the current stdout encoding supports UTF-8 characters."""
    enc = (getattr(sys.stdout, "encoding", None) or "").lower()
    return "utf" in enc


def _fmt_separator() -> str:
    # Use Unicode heavy horizontal bar on UTF-8 terminals; plain dashes on
    # cp1252 / other narrow-codepage Windows terminals to avoid UnicodeEncodeError.
    return ("\u2501" if _is_utf8_stdout() else "-") * 54  # ━


def _fmt_tier_row(label: str, count: int, detail: str = "") -> str:
    base = f"{label:<20} {count:>3} invariant{'s' if count != 1 else ''}"
    if detail:
        base += f"  ({detail})"
    return base


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------

@click.group("immune")
def immune_group() -> None:
    """Immune system: runtime invariant mining and self-improving verification.

    The immune system watches running code, mines invariants from runtime
    behaviour, verifies them with CrossHair + Hypothesis, and appends the
    survivors back into your .card.md spec — closing the self-improvement loop.

    Typical workflow:

    \b
        nightjar immune run src/payment.py --card .card/payment.card.md
        nightjar immune collect src/payment.py
        nightjar immune status
    """


# ---------------------------------------------------------------------------
# immune run
# ---------------------------------------------------------------------------

@immune_group.command("run")
@click.argument("source_path", type=click.Path(exists=True))
@click.option(
    "--card",
    default=None,
    type=click.Path(),
    help="Path to .card.md file to append verified invariants into.",
)
@click.option(
    "--tier",
    default=None,
    type=click.Choice(["1", "2", "3"]),
    help=(
        "Run a specific mining tier only: "
        "1=SEMANTIC (LLM), 2=RUNTIME (Daikon), 3=API-LEVEL (MINES)."
    ),
)
@click.option(
    "--function",
    "function_name",
    default=None,
    help="Restrict mining to a single named function in the source file.",
)
@click.option(
    "--db",
    "db_path",
    default=_DEFAULT_DB,
    show_default=True,
    help="Path to the immune trace database.",
)
def immune_run(
    source_path: str,
    card: Optional[str],
    tier: Optional[str],
    function_name: Optional[str],
    db_path: str,
) -> None:
    """Run the full invariant mining cycle on a Python source file.

    Loads the source file, runs the 3-tier mining orchestrator, verifies
    candidates, and optionally appends survivors to the .card.md spec.

    \b
    Example:
        nightjar immune run src/payment.py --card .card/payment.card.md
        nightjar immune run src/auth.py --tier 1 --function validate_token
    """
    # --- lazy imports -------------------------------------------------------
    try:
        from immune.pipeline import (  # type: ignore[import]
            run_mining_tiers,
            MiningTier,
            MiningOrchestrationResult,
        )
    except ImportError as exc:
        raise click.ClickException(
            _import_error("nightjar[immune]", f"Missing: {exc}")
        ) from exc

    source_file = Path(source_path)
    click.echo(f"\nNightjar Immune — mining invariants from {source_path}")
    click.echo(_fmt_separator())

    # --- load source --------------------------------------------------------
    try:
        func_source = source_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise click.ClickException(f"Cannot read source file: {exc}") from exc

    # --- dynamically import the module to get a callable (Tier 2 needs it) --
    func_callable = None
    if tier in (None, "2"):
        func_callable = _load_callable(source_file, function_name)
        if func_callable is None and tier == "2":
            click.echo(
                click.style(
                    "  Warning: could not import a callable for Tier 2 runtime "
                    "tracing — Tier 2 will be skipped.",
                    fg="yellow",
                ),
                err=True,
            )

    # --- decide which tiers to activate ------------------------------------
    run_t1 = tier in (None, "1")
    run_t2 = tier in (None, "2") and func_callable is not None
    run_t3 = tier in (None, "3")

    # Build trace_args for Tier 2: a minimal single empty-args call so
    # run_mining_tiers does not skip Tier 2 entirely.
    trace_args: Optional[list[tuple]] = [()] if run_t2 else None
    spans: Optional[list] = [] if run_t3 else None

    # --- call orchestrator -------------------------------------------------
    result: MiningOrchestrationResult = run_mining_tiers(
        func=func_callable if run_t2 else None,
        trace_args=trace_args,
        spans=spans,
        run_tier1=run_t1,
        func_source=func_source if run_t1 else None,
    )

    # --- render tier counts ------------------------------------------------
    t1_count = result.tier_counts.get(MiningTier.SEMANTIC, 0)
    t2_count = result.tier_counts.get(MiningTier.RUNTIME, 0)
    t3_count = result.tier_counts.get(MiningTier.API_LEVEL, 0)
    total_merged = len(result.merged)

    if tier in (None, "1"):
        click.echo(_fmt_tier_row("Tier 1 SEMANTIC:", t1_count, "LLM hypothesis"))
    if tier in (None, "2"):
        click.echo(_fmt_tier_row("Tier 2 RUNTIME:", t2_count, "Daikon+Houdini"))
    if tier in (None, "3"):
        click.echo(_fmt_tier_row("Tier 3 API-LEVEL:", t3_count, "MINES spans"))

    click.echo(_fmt_separator())

    # --- verify merged candidates via run_immune_cycle ----------------------
    verified_count = 0
    appended_count = 0
    verify_errors: list[str] = []

    if total_merged > 0:
        try:
            from immune.pipeline import run_immune_cycle, ImmuneCycleConfig  # type: ignore[import]
        except ImportError as exc:
            raise click.ClickException(
                _import_error("nightjar[immune]", f"Missing: {exc}")
            ) from exc

        cfg = ImmuneCycleConfig()
        func_name_for_cycle = function_name or _guess_primary_function(func_source)

        cycle_result = run_immune_cycle(
            function_source=func_source,
            function_name=func_name_for_cycle,
            observed_invariants=[inv.expression for inv in result.merged],
            card_path=card,
            config=cfg,
        )

        verified_count = cycle_result.candidates_verified
        appended_count = cycle_result.candidates_appended
        verify_errors = cycle_result.errors

    # --- summary line -------------------------------------------------------
    summary = (
        f"Verified: {verified_count}/{total_merged} candidates"
    )
    if card:
        summary += f" | Appended to spec: {appended_count}"

    if verified_count > 0:
        click.echo(click.style(summary, fg="green"))
    else:
        click.echo(click.style(summary, fg="yellow"))

    # --- non-fatal errors ---------------------------------------------------
    for err_msg in result.errors + verify_errors:
        click.echo(click.style(f"  ! {err_msg}", fg="yellow"), err=True)

    # --- persist to trace DB ------------------------------------------------
    if total_merged > 0:
        _persist_candidates(db_path, result.merged, function_name or "")

    click.echo()


# ---------------------------------------------------------------------------
# immune collect
# ---------------------------------------------------------------------------

@immune_group.command("collect")
@click.argument("source_path", type=click.Path(exists=True))
@click.option(
    "--function",
    "function_name",
    default=None,
    help="Trace a specific function by name (default: trace all).",
)
@click.option(
    "--db",
    "db_path",
    default=_DEFAULT_DB,
    show_default=True,
    help="Path to the immune trace database.",
)
def immune_collect(
    source_path: str,
    function_name: Optional[str],
    db_path: str,
) -> None:
    """Collect runtime type traces from a Python module.

    Imports the module, runs any available ``__main__`` block or test
    functions, and records type signatures via the TypeCollector.  Results
    are saved to the immune trace database for later mining.

    \b
    Example:
        nightjar immune collect src/payment.py
        nightjar immune collect src/auth.py --function validate_token
    """
    try:
        from immune.collector import TypeCollector  # type: ignore[import]
    except ImportError as exc:
        raise click.ClickException(
            _import_error("nightjar[immune]", f"Missing: {exc}")
        ) from exc

    source_file = Path(source_path)
    click.echo(f"\nNightjar Immune — collecting traces from {source_path}")
    click.echo(_fmt_separator())

    collector = TypeCollector()
    func_callable = _load_callable(source_file, function_name)

    if func_callable is None:
        raise click.ClickException(
            f"Could not load a callable from '{source_path}'. "
            "Ensure the module is importable and use --function to target a "
            "specific function if the module has no __main__ block."
        )

    with collector.trace():
        try:
            func_callable()
        except Exception as exc:  # noqa: BLE001
            click.echo(
                click.style(
                    f"  Warning: callable raised {type(exc).__name__}: {exc} "
                    "(traces captured up to the exception)",
                    fg="yellow",
                ),
                err=True,
            )

    trace_count = collector.trace_count
    traced_names = collector.get_all_function_names()

    click.echo(f"  Traced functions : {len(traced_names)}")
    click.echo(f"  Total call events: {trace_count:,}")

    if function_name:
        sigs = collector.get_unique_signatures(function_name)
        click.echo(f"  Unique signatures for '{function_name}': {len(sigs)}")

    # persist type traces to DB
    if trace_count > 0:
        _ensure_db_dir(db_path)
        try:
            from immune.store import TraceStore  # type: ignore[import]
        except ImportError as exc:
            raise click.ClickException(
                _import_error("nightjar[immune]", f"Missing: {exc}")
            ) from exc

        store = TraceStore(db_path)
        try:
            saved = 0
            for fname in traced_names:
                for tt in collector.export_type_traces(fname):
                    store.insert_type_trace(tt)
                    saved += 1
        finally:
            store.close()

        click.echo(
            click.style(
                f"  Saved {saved} type trace(s) -> {db_path}", fg="green"
            )
        )
    else:
        click.echo(click.style("  No traces captured.", fg="yellow"))

    click.echo(_fmt_separator())
    click.echo()


# ---------------------------------------------------------------------------
# immune status
# ---------------------------------------------------------------------------

@immune_group.command("status")
@click.option(
    "--db",
    "db_path",
    default=_DEFAULT_DB,
    show_default=True,
    help="Path to the immune trace database.",
)
def immune_status(db_path: str) -> None:
    """Show immune system status — trace counts, mined invariants, verified candidates.

    Reads the immune trace database and displays a summary of all collected
    data: traces by type, invariant candidates by lifecycle stage, and
    verified invariants ready to be applied to specs.

    \b
    Example:
        nightjar immune status
        nightjar immune status --db .card/custom-immune.db
    """
    db_file = Path(db_path)

    click.echo(f"\nNightjar Immune — status")
    click.echo(_fmt_separator())

    if not db_file.exists():
        click.echo(click.style(
            f"  No trace database found at {db_path}.\n"
            "  Run 'nightjar immune run <source>' to populate it.",
            fg="yellow",
        ))
        click.echo()
        return

    try:
        from immune.store import TraceStore  # type: ignore[import]
        from immune.types import InvariantStatus  # type: ignore[import]
    except ImportError as exc:
        raise click.ClickException(
            _import_error("nightjar[immune]", f"Missing: {exc}")
        ) from exc

    store = TraceStore(db_path)
    try:
        trace_counts = store.get_trace_counts()
        candidate_counts = store.get_candidate_counts_by_status()
        verified_list = store.get_verified_invariants()
    finally:
        store.close()

    # --- trace table --------------------------------------------------------
    click.echo("  Trace database:")
    total_traces = sum(trace_counts.values())
    label_map = {
        "type_traces": "Type traces (MonkeyType)",
        "value_traces": "Value traces (Daikon)",
        "api_traces": "API traces (OTel)",
        "error_traces": "Error traces (Sentry)",
    }
    for table, label in label_map.items():
        count = trace_counts.get(table, 0)
        _check = "\u2713" if _is_utf8_stdout() else "+"  # ✓
        marker = click.style(_check, fg="green") if count > 0 else " "
        click.echo(f"    {marker} {label:<32} {count:>6,}")
    click.echo(f"    {'':>2} {'TOTAL':<32} {total_traces:>6,}")

    click.echo()

    # --- candidates table ---------------------------------------------------
    click.echo("  Invariant candidates:")
    status_labels = {
        InvariantStatus.CANDIDATE: ("Pending", "cyan"),
        InvariantStatus.VERIFIED: ("Verified", "green"),
        InvariantStatus.REJECTED: ("Rejected", "red"),
        InvariantStatus.APPLIED: ("Applied to spec", "bright_green"),
    }
    total_candidates = sum(candidate_counts.values())
    for status, (label, color) in status_labels.items():
        count = candidate_counts.get(status, 0)
        click.echo(
            f"    {click.style(f'{label:<18}', fg=color)} {count:>6,}"
        )
    click.echo(f"    {'TOTAL':<20} {total_candidates:>6,}")

    click.echo()

    # --- verified invariants table ------------------------------------------
    verified_total = len(verified_list)
    applied = sum(1 for v in verified_list if v.card_spec_id)
    click.echo(f"  Verified invariants: {verified_total}")
    if applied:
        click.echo(click.style(
            f"  Applied to specs   : {applied}", fg="bright_green"
        ))

    # --- quick health indicator ---------------------------------------------
    click.echo()
    if total_traces == 0:
        click.echo(click.style(
            "  Health: NO TRACES — run 'nightjar immune collect <src>'",
            fg="yellow",
        ))
    elif total_candidates == 0:
        click.echo(click.style(
            "  Health: traces collected, no candidates yet — "
            "run 'nightjar immune run <src>'",
            fg="yellow",
        ))
    elif verified_total == 0:
        click.echo(click.style(
            "  Health: candidates mined but none verified yet",
            fg="yellow",
        ))
    else:
        click.echo(click.style(
            f"  Health: OK — {verified_total} verified invariant(s) available",
            fg="green",
        ))

    click.echo(_fmt_separator())
    click.echo()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _ensure_db_dir(db_path: str) -> None:
    """Create parent directory for the database if it does not exist."""
    parent = Path(db_path).parent
    parent.mkdir(parents=True, exist_ok=True)


def _load_callable(source_file: Path, function_name: Optional[str]):
    """Attempt to dynamically load a callable from a source file.

    Inserts the file's parent directory into sys.path, imports the module
    by stem name, and (if function_name is provided) returns that specific
    attribute.  Returns None on any failure — callers must handle None.
    """
    module_dir = str(source_file.parent.resolve())
    module_stem = source_file.stem

    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)

    try:
        import importlib
        mod = importlib.import_module(module_stem)
    except Exception:  # noqa: BLE001
        return None

    if function_name:
        return getattr(mod, function_name, None)

    # Fall back to __main__ callable or the first public function found
    if hasattr(mod, "main"):
        return mod.main
    if hasattr(mod, "__main__"):
        return mod.__main__

    # Last resort: return the first public callable
    for attr_name in dir(mod):
        if attr_name.startswith("_"):
            continue
        attr = getattr(mod, attr_name)
        if callable(attr) and not isinstance(attr, type):
            return attr

    return None


def _guess_primary_function(source: str) -> str:
    """Heuristically pick the primary function name from source text.

    Scans for ``def`` lines and returns the first non-dunder function name,
    or 'unknown' if nothing is found.
    """
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("def "):
            name = stripped[4:].split("(")[0].strip()
            if not (name.startswith("__") and name.endswith("__")):
                return name
    return "unknown"


def _persist_candidates(
    db_path: str,
    merged: list,
    function_name: str,
) -> None:
    """Save mined invariant candidates to the trace store.

    Silently skips if the immune.store import fails (optional dependency).
    """
    _ensure_db_dir(db_path)
    try:
        from immune.store import TraceStore  # type: ignore[import]
        from immune.types import InvariantCandidate, InvariantStatus  # type: ignore[import]
    except ImportError:
        return

    store = TraceStore(db_path)
    try:
        for inv in merged:
            candidate = InvariantCandidate(
                function=function_name or "unknown",
                expression=inv.expression,
                kind=inv.tier.value,
                source=inv.source,
                confidence=inv.confidence,
                observation_count=0,
                status=InvariantStatus.CANDIDATE,
            )
            store.insert_candidate(candidate)
    except Exception:  # noqa: BLE001
        pass
    finally:
        store.close()
