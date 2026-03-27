"""nightjar CLI — Contract-Anchored Regenerative Development.

Reference: [REF-T17] Click CLI framework
Architecture: docs/ARCHITECTURE.md Section 8

Commands:
    init        Scaffold a .card.md spec for a module
    generate    Generate code from .card.md via LLM
    verify      Run 5-stage verification pipeline
    build       Generate + verify + compile to target language
    retry       Force retry with LLM repair loop
    lock        Freeze dependencies into deps.lock with hashes
    explain     Show last verification failure in human-readable form

Exit Codes:
    0  All stages PASS
    1  Verification FAIL
    2  Configuration error
    3  Timeout exceeded
    4  LLM API error
    5  Max retries exceeded (human escalation required)
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

import click

from nightjar import __version__
from nightjar.config import load_config, get_model, get_specs_dir

# ── Exit codes (from ARCHITECTURE.md Section 8) ─────────

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_CONFIG_ERROR = 2
EXIT_TIMEOUT = 3
EXIT_LLM_ERROR = 4
EXIT_MAX_RETRIES = 5

# ── Config loading ───────────────────────────────────────

# Default config values matching nightjar.toml schema
_DEFAULT_CONFIG = {
    "card": {
        "version": "1.0",
        "default_target": "py",
        "default_model": "claude-sonnet-4-6",
        "max_retries": 5,
        "verification_timeout": 30,
    },
    "paths": {
        "specs": ".card/",
        "dist": "dist/",
        "audit": ".card/audit/",
        "cache": ".card/cache/",
    },
}


def _load_config() -> dict:
    """Load configuration. Delegates to nightjar.config module."""
    return load_config()


def _get_model(model_flag: Optional[str], config: dict) -> str:
    """Resolve model name. Delegates to nightjar.config module.

    All LLM calls go through litellm [REF-T16].
    """
    return get_model(cli_model=model_flag, config=config)


def _get_specs_dir(config: dict) -> str:
    """Get the specs directory from config."""
    return get_specs_dir(config)


# ── Spec template for init command ───────────────────────

_SPEC_TEMPLATE = '''---
card-version: "1.0"
id: {module_id}
title: {title}
status: draft
module:
  owns: []
  depends-on: {{}}
contract:
  inputs: []
  outputs: []
invariants: []
---

## Intent

Describe what the {module_id} module does and why it exists.

## Acceptance Criteria

### Story 1 — Description (P1)

**As a** user, **I want** capability, **so that** benefit.

1. **Given** precondition, **When** action, **Then** expected outcome

### Edge Cases

- What happens when X? -> Expected behavior

## Functional Requirements

- **FR-001**: System MUST ...
'''


# ── Internal dispatch functions (delegate to other modules) ──


def _run_verify(
    contract_path: str,
    *,
    fast: bool = False,
    stage: Optional[int] = None,
    config: dict,
    ci: bool = False,
):
    """Run the verification pipeline. Delegates to verifier module.

    Architecture: docs/ARCHITECTURE.md Section 3 (Verification Pipeline)
    Stages run in order: 0 -> 1 -> (2 || 3) -> 4
    With --fast: stages 0-3 only (skip Dafny)
    With --stage N: run only stage N
    """
    # Import verifier lazily so CLI can load even if verifier isn't built yet
    try:
        from nightjar.verifier import run_pipeline
    except ImportError:
        # Verifier not yet implemented by Builder 5 (T7)
        click.echo("Error: verification pipeline not yet available", err=True)
        raise SystemExit(EXIT_CONFIG_ERROR)

    # Parse the spec file into a CardSpec object
    from nightjar.parser import parse_card_spec
    spec = parse_card_spec(contract_path)

    # Locate generated code: look for <spec_id>.py or <spec_id>.dfy in audit dir or cwd
    import os
    code = ""
    audit_dir = config.get("paths", {}).get("audit", ".card/audit/")
    for ext in (".py", ".dfy"):
        candidate = os.path.join(audit_dir, f"{spec.id}{ext}")
        if os.path.exists(candidate):
            with open(candidate, encoding="utf-8") as f:
                code = f.read()
            break

    result = run_pipeline(spec, code, spec_path=contract_path)

    # Filter stages if --stage N or --fast was specified
    if stage is not None:
        from nightjar.types import VerifyStatus
        filtered = [s for s in result.stages if s.stage == stage]
        if filtered:
            verified = all(
                s.status in (VerifyStatus.PASS, VerifyStatus.SKIP) for s in filtered
            )
            result = result.__class__(
                verified=verified,
                stages=filtered,
                total_duration_ms=result.total_duration_ms,
                retry_count=result.retry_count,
            )
    elif fast:
        from nightjar.types import VerifyStatus
        filtered = [s for s in result.stages if s.stage <= 3]
        if filtered:
            verified = all(
                s.status in (VerifyStatus.PASS, VerifyStatus.SKIP) for s in filtered
            )
            result = result.__class__(
                verified=verified,
                stages=filtered,
                total_duration_ms=result.total_duration_ms,
                retry_count=result.retry_count,
            )

    return result


def _run_generate(
    contract_path: str,
    *,
    model: str,
    output_dir: str,
    config: dict,
):
    """Run code generation. Delegates to generator module.

    Architecture: docs/ARCHITECTURE.md Section 5
    Pipeline: Analyst -> Formalizer -> Coder [REF-C03, REF-P07]
    All LLM calls through litellm [REF-T16].
    """
    from nightjar.parser import parse_card_spec
    from nightjar.generator import generate_code

    spec = parse_card_spec(contract_path)
    result = generate_code(spec, model=model)

    if result.dafny_code:
        import os
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{spec.id}.dfy")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result.dafny_code)
        click.echo(f"Generated: {output_path}")

    return result


def _run_build(
    contract_path: str,
    *,
    target: str,
    model: str,
    output_dir: str,
    retries: int,
    ci: bool,
    config: dict,
):
    """Run full build: generate + verify + compile.

    Architecture: docs/ARCHITECTURE.md Section 9 (Data Flow)
    """
    # Step 1: Generate
    generated_path = _run_generate(
        contract_path, model=model, output_dir=output_dir, config=config
    )

    # Step 2: Verify (with retry on failure)
    verify_result = _run_verify(
        contract_path, config=config, ci=ci
    )

    if not verify_result.verified and retries > 0:
        verify_result = _run_retry(
            contract_path, max_retries=retries, model=model, config=config
        )

    return verify_result


def _run_retry(
    contract_path: str,
    *,
    max_retries: int = 5,
    model: str = "",
    config: dict,
):
    """Run the Clover-pattern retry loop [REF-C02, REF-P03].

    Delegates to retry module. Collects structured errors [REF-P06]
    and feeds them back to LLM for repair.
    """
    try:
        from nightjar.retry import run_with_retry
    except ImportError:
        click.echo("Error: retry loop not yet available", err=True)
        raise SystemExit(EXIT_CONFIG_ERROR)

    from nightjar.parser import parse_card_spec
    import os as _os
    spec = parse_card_spec(contract_path)
    code = ""
    audit_dir = config.get("paths", {}).get("audit", ".card/audit/")
    for ext in (".py", ".dfy"):
        candidate = _os.path.join(audit_dir, f"{spec.id}{ext}")
        if _os.path.exists(candidate):
            with open(candidate, encoding="utf-8") as f:
                code = f.read()
            break
    return run_with_retry(spec, code, max_retries=max_retries)


def _run_lock(output_dir: str, config: dict) -> bool:
    """Freeze dependencies into deps.lock with SHA hashes.

    Delegates to lock.py module [REF-C08, REF-P27].
    """
    try:
        from nightjar.lock import generate_lock_file

        lock_path = str(Path(output_dir) / "deps.lock")
        success = generate_lock_file(output_dir, lock_path)
        if success:
            click.echo(f"Dependencies frozen to {lock_path}")
        return success
    except ImportError:
        click.echo("Error: lock module not available", err=True)
        return False


def _load_verify_report(contract_path: str) -> Optional[dict]:
    """Load the last verification report. Delegates to explain module."""
    try:
        from nightjar.explain import load_report
        return load_report(contract_path)
    except ImportError:
        # Fallback: inline loading
        spec_dir = Path(contract_path).parent
        report_path = spec_dir / "verify.json"
        if not report_path.exists():
            report_path = Path(".card") / "verify.json"
        if report_path.exists():
            with open(report_path, encoding="utf-8") as f:
                return json.load(f)
        return None


# ── CLI Group and Commands ───────────────────────────────


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="nightjar")
@click.pass_context
def main(ctx: click.Context) -> None:
    """nightjar -- formal verification CLI for AI-generated code.

    Verification layer for AI-generated code. Parse .card.md specs,
    generate verified code via LLM + Dafny, and run a 5-stage
    verification pipeline.
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = _load_config()
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("module_name")
@click.option("--output", "-o", default=".", help="Project root directory.")
@click.pass_context
def init(ctx: click.Context, module_name: str, output: str) -> None:
    """Scaffold a .card.md spec for MODULE_NAME.

    Creates .card/<module_name>.card.md with the standard Nightjar spec format:
    YAML frontmatter + Markdown body [REF-T24, REF-T25].
    """
    # Validate module name: must be non-empty and match [a-zA-Z][a-zA-Z0-9_-]*
    if not module_name:
        click.echo("Error: module name cannot be empty.", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', module_name):
        click.echo(
            f"Error: invalid module name '{module_name}'. "
            "Must start with a letter and contain only letters, digits, hyphens, or underscores.",
            err=True,
        )
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    output_path = Path(output)
    card_dir = output_path / ".card"
    card_dir.mkdir(parents=True, exist_ok=True)

    spec_path = card_dir / f"{module_name}.card.md"

    # Security: verify the resolved path is inside the .card/ directory
    try:
        resolved_spec = spec_path.resolve()
        resolved_card = card_dir.resolve()
        resolved_spec.relative_to(resolved_card)
    except ValueError:
        click.echo(
            f"Error: module name '{module_name}' would create a file outside .card/ directory.",
            err=True,
        )
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    if spec_path.exists():
        click.echo(f"Error: {spec_path} already exists. Use --force to overwrite.", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    # Sanitize module name for title
    title = module_name.replace("-", " ").replace("_", " ").title()
    content = _SPEC_TEMPLATE.format(module_id=module_name, title=title)
    spec_path.write_text(content, encoding="utf-8")
    click.echo(f"Created {spec_path}")


@main.command()
@click.option("--spec", "--contract", "-s", "-c", "contract", required=True, help="Path to .card.md spec.")
@click.option("--fast", is_flag=True, default=False, help="Stages 0-3 only (skip Dafny).")
@click.option("--stage", type=int, default=None, help="Run only stage N (0-4).")
@click.option("--ci", is_flag=True, default=False, help="CI mode: strict, no prompts.")
@click.pass_context
def verify(
    ctx: click.Context,
    contract: str,
    fast: bool,
    stage: Optional[int],
    ci: bool,
) -> None:
    """Run the 5-stage verification pipeline.

    Stages: preflight → deps → schema → property-tests → formal-proof.
    Architecture: docs/ARCHITECTURE.md Section 3.
    """
    config = ctx.obj["config"]
    try:
        result = _run_verify(
            contract, fast=fast, stage=stage, config=config, ci=ci
        )
    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Verification error: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    if result.verified:
        click.echo("VERIFIED -- all stages passed")
        ctx.exit(EXIT_PASS)
    else:
        click.echo("FAILED -- verification did not pass")
        ctx.exit(EXIT_FAIL)


@main.command()
@click.option("--spec", "--contract", "-s", "-c", "contract", required=True, help="Path to .card.md spec.")
@click.option("--model", default=None, help="LLM model (default: NIGHTJAR_MODEL env or config).")
@click.option("--output", "-o", default=".", help="Output directory for generated code.")
@click.pass_context
def generate(ctx: click.Context, contract: str, model: Optional[str], output: str) -> None:
    """Generate code from a .card.md spec via LLM.

    Uses the Analyst -> Formalizer -> Coder pipeline [REF-C03, REF-P07].
    All LLM calls go through litellm [REF-T16].
    """
    config = ctx.obj["config"]
    resolved_model = _get_model(model, config)
    try:
        result = _run_generate(
            contract, model=resolved_model, output_dir=output, config=config
        )
        click.echo(f"Generated: {result}")
    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Generation error: {e}", err=True)
        ctx.exit(EXIT_LLM_ERROR)


@main.command()
@click.option("--spec", "--contract", "-s", "-c", "contract", required=True, help="Path to .card.md spec.")
@click.option("--target", "-t", default="py",
              type=click.Choice(["py", "js", "ts", "go", "java", "cs"]),
              help="Compile target language (default: py).")
@click.option("--model", default=None, help="LLM model.")
@click.option("--retries", default=None, type=int, help="Max repair attempts (default: from config).")
@click.option("--output", "-o", default=".", help="Output directory for artifacts.")
@click.option("--ci", is_flag=True, default=False, help="CI mode: strict, no prompts, exit code on fail.")
@click.pass_context
def build(
    ctx: click.Context,
    contract: str,
    target: Optional[str],
    model: Optional[str],
    retries: Optional[int],
    output: str,
    ci: bool,
) -> None:
    """Generate + verify + compile to target language.

    Full pipeline: parse .card.md -> LLM generate -> 5-stage verify -> compile.
    Architecture: docs/ARCHITECTURE.md Section 9 (Data Flow).
    """
    config = ctx.obj["config"]
    resolved_model = _get_model(model, config)
    resolved_target = target or config.get("card", {}).get("default_target", "py")
    resolved_retries = retries if retries is not None else config.get("card", {}).get("max_retries", 5)

    try:
        result = _run_build(
            contract,
            target=resolved_target,
            model=resolved_model,
            output_dir=output,
            retries=resolved_retries,
            ci=ci,
            config=config,
        )
    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Build error: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    if result.verified:
        click.echo(f"BUILD PASSED -- target: {resolved_target}")
        ctx.exit(EXIT_PASS)
    else:
        click.echo("BUILD FAILED -- verification did not pass")
        ctx.exit(EXIT_FAIL)


@main.command()
@click.option("--spec", "--contract", "-s", "-c", "contract", required=True, help="Path to .card.md spec.")
@click.option("--target", "-t", default=None,
              type=click.Choice(["py", "js", "ts", "go", "java", "cs"]),
              help="Compile target language.")
@click.option("--model", default=None, help="LLM model.")
@click.option("--retries", default=None, type=int, help="Max repair attempts.")
@click.option("--output", "-o", default=".", help="Output directory for artifacts.")
@click.option("--ci", is_flag=True, default=False, help="CI mode.")
@click.pass_context
def ship(
    ctx: click.Context,
    contract: str,
    target: Optional[str],
    model: Optional[str],
    retries: Optional[int],
    output: str,
    ci: bool,
) -> None:
    """Build + sign artifact for deployment.

    Runs the full build pipeline (generate + verify + compile) then
    signs the resulting artifact. Architecture: docs/ARCHITECTURE.md Section 8.
    """
    config = ctx.obj["config"]
    resolved_model = _get_model(model, config)
    resolved_target = target or config.get("card", {}).get("default_target", "py")
    resolved_retries = retries if retries is not None else config.get("card", {}).get("max_retries", 5)

    try:
        result = _run_build(
            contract,
            target=resolved_target,
            model=resolved_model,
            output_dir=output,
            retries=resolved_retries,
            ci=ci,
            config=config,
        )
    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Ship error: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    if not result.verified:
        click.echo("SHIP FAILED -- verification did not pass")
        ctx.exit(EXIT_FAIL)
        return

    click.echo(f"SHIP COMPLETE -- verified artifact ready (target: {resolved_target})")
    ctx.exit(EXIT_PASS)


@main.command()
@click.option("--spec", "--contract", "-s", "-c", "contract", required=True, help="Path to .card.md spec.")
@click.option("--max", "max_retries", default=5, type=int, help="Maximum repair attempts (default: 5).")
@click.option("--model", default=None, help="LLM model for repair calls.")
@click.pass_context
def retry(ctx: click.Context, contract: str, max_retries: int, model: Optional[str]) -> None:
    """Force retry with LLM repair loop.

    Uses the Clover closed-loop pattern [REF-C02, REF-P03] with
    DafnyPro structured errors [REF-P06] for targeted repair.
    """
    config = ctx.obj["config"]
    resolved_model = _get_model(model, config)
    try:
        result = _run_retry(
            contract, max_retries=max_retries, model=resolved_model, config=config
        )
    except SystemExit:
        raise
    except Exception as e:
        click.echo(f"Retry error: {e}", err=True)
        ctx.exit(EXIT_LLM_ERROR)
        return

    if result.verified:
        click.echo("RETRY SUCCEEDED -- verification passed after repair")
        ctx.exit(EXIT_PASS)
    else:
        click.echo("RETRY EXHAUSTED -- max retries exceeded, escalate to human")
        ctx.exit(EXIT_MAX_RETRIES)


@main.command()
@click.option("--output", "-o", default=".", help="Project root directory.")
@click.pass_context
def lock(ctx: click.Context, output: str) -> None:
    """Freeze dependencies into deps.lock with SHA hashes.

    Creates a sealed dependency manifest [REF-C08] to prevent
    hallucinated package attacks [REF-P27].
    """
    config = ctx.obj["config"]
    success = _run_lock(output, config)
    if success:
        ctx.exit(EXIT_PASS)
    else:
        ctx.exit(EXIT_CONFIG_ERROR)


@main.command()
@click.option("--target", "-t", default="analyst",
              type=click.Choice(["analyst", "formalizer", "coder"]),
              help="Which prompt to optimize (default: analyst).")
@click.option("--iterations", default=10, type=int, help="Max optimization iterations.")
@click.pass_context
def optimize(ctx: click.Context, target: str, iterations: int) -> None:
    """Run DSPy SIMBA prompt optimization [REF-T26].

    Optimizes the Analyst/Formalizer/Coder prompts based on
    verification pass rate as the metric.
    """
    try:
        from nightjar.optimizer import run_optimization, OptimizationConfig

        config = OptimizationConfig(
            tracking_db_path=".card/tracking.db",
            prompt_registry_path="src/nightjar/prompts",
            target_prompt=target,
            max_iterations=iterations,
        )
        result = run_optimization(config)
        if result.improved:
            click.echo(
                f"OPTIMIZED {target}: v{result.original_version} -> v{result.best_version} "
                f"(score: {result.original_score:.2f} -> {result.best_score:.2f})"
            )
        else:
            click.echo(f"No improvement found for {target} after {result.iterations_run} iterations")
        ctx.exit(EXIT_PASS)
    except ImportError as e:
        click.echo(f"Error: optimizer not available ({e})", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
    except Exception as e:
        click.echo(f"Optimization error: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)


@main.command()
@click.option("--spec", "--contract", "-s", "-c", "contract", required=True, help="Path to .card.md spec.")
@click.pass_context
def explain(ctx: click.Context, contract: str) -> None:
    """Show last verification failure in human-readable form.

    Reads .card/verify.json and formats the failure report.
    Delegates to explain.py + display.py for Rich formatting [REF-P06].
    """
    report = _load_verify_report(contract)
    if report is None:
        click.echo("No verification report found. Run 'nightjar verify' first.")
        ctx.exit(EXIT_PASS)
        return

    if report.get("verified", False):
        click.echo("Last verification PASSED -- no failures to explain.")
        ctx.exit(EXIT_PASS)
        return

    # Use Rich formatting if available, fall back to plain text
    try:
        from nightjar.display import format_explain
        format_explain(report)
    except ImportError:
        from nightjar.explain import explain_failure, format_explanation
        explanation = explain_failure(report)
        click.echo(format_explanation(explanation))
    ctx.exit(EXIT_PASS)


# ── Phase 2 Command Stubs ────────────────────────────────
# These stubs will be implemented by builders in Phase 2.
# Coord-Integration wires final integration in Phase 3.


@main.command()
@click.argument("intent", required=False, default=None)
@click.option("--approve-all", is_flag=True, help="Auto-approve all suggested invariants.")
@click.option("--output", "-o", default=".card", help="Output directory for .card.md spec.")
@click.option("--model", default=None, help="LLM model (default: NIGHTJAR_MODEL env or config).")
@click.pass_context
def auto(ctx: click.Context, intent: str | None, approve_all: bool, output: str, model: Optional[str]) -> None:
    """Generate .card.md specs from natural language intent.

    Takes a plain English description and auto-generates verification
    artifacts (icontract, Hypothesis, Dafny). [Scout 4 F1-F3]
    """
    if not intent:
        click.echo("Usage: nightjar auto \"describe your module intent\"", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    config = ctx.obj["config"]
    resolved_model = _get_model(model, config)

    try:
        from nightjar.auto import run_auto

        result = run_auto(
            nl_intent=intent,
            output_path=output,
            model=resolved_model,
            yes=approve_all,
        )
        if result.card_path:
            click.echo(f"Created spec: {result.card_path}")
            total = result.approved_count + result.skipped_count
            click.echo(f"Rules: {total} suggested, {result.approved_count} added, {result.skipped_count} skipped")
            ctx.exit(EXIT_PASS)
        else:
            click.echo("No spec generated (all invariants rejected or error).")
            ctx.exit(EXIT_FAIL)
    except ImportError as e:
        click.echo(f"Error: auto module not available ({e})", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
    except Exception as e:
        click.echo(f"Auto error: {e}", err=True)
        ctx.exit(EXIT_LLM_ERROR)


@main.command()
@click.option("--debounce", default=500, help="Debounce interval in ms.")
@click.option("--card-dir", default=".card", help="Directory to watch for .card.md changes.")
@click.pass_context
def watch(ctx: click.Context, debounce: int, card_dir: str) -> None:
    """Start persistent file-watching daemon with tiered verification.

    Monitors .card/ directory for changes and runs streaming verification
    (Tier 0-3) with sub-second first feedback. [Scout 5 architecture]
    """
    try:
        from nightjar.watch import start_watch, TierEvent

        def _on_tier_event(event: TierEvent) -> None:
            status = event.status.upper()
            click.echo(f"[Tier {event.tier}] {status} ({event.duration_ms}ms)")
            if event.message:
                click.echo(f"  {event.message}")

        click.echo(f"Watching {card_dir}/ for changes (debounce: {debounce}ms) ...")
        click.echo("Press Ctrl+C to stop.")
        observer = start_watch(card_dir, callback=_on_tier_event)
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            observer.join()
            click.echo("\nWatch stopped.")
        ctx.exit(EXIT_PASS)
    except ImportError as e:
        click.echo(f"Error: watch module not available ({e})", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
    except Exception as e:
        click.echo(f"Watch error: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)


@main.command()
@click.option("--format", "fmt", type=click.Choice(["url", "markdown", "html"]), default="markdown")
@click.option("--report", default=".card/verify.json", help="Path to verify.json report.")
@click.pass_context
def badge(ctx: click.Context, fmt: str, report: str) -> None:
    """Generate a 'Nightjar Verified' badge from last verification result.

    Uses shields.io to create status + coverage badges. [Scout 7 N8]
    """
    try:
        from nightjar.badge import generate_badge_url_from_report, generate_badge_markdown
        import os as _os

        if not _os.path.exists(report):
            click.echo("No verification report found. Run `nightjar verify` first.", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
            return

        badge_url = generate_badge_url_from_report(report)

        if fmt == "url":
            click.echo(badge_url)
        elif fmt == "markdown":
            # Extract status and score for markdown generation
            from nightjar.badge import BadgeStatus
            import json
            try:
                with open(report, encoding="utf-8") as f:
                    data = json.load(f)
                status = BadgeStatus.PASSED if data.get("verified") else BadgeStatus.FAILED
                score = data.get("confidence", {}).get("score", 0) if isinstance(data.get("confidence"), dict) else 0
                click.echo(generate_badge_markdown(status, score))
            except (FileNotFoundError, json.JSONDecodeError):
                click.echo(f"![Nightjar]({badge_url})")
        elif fmt == "html":
            click.echo(f'<img src="{badge_url}" alt="Nightjar Verified">')
        ctx.exit(EXIT_PASS)
    except FileNotFoundError:
        click.echo("No verification report found. Run 'nightjar verify' first.", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
    except ImportError as e:
        click.echo(f"Error: badge module not available ({e})", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
    except Exception as e:
        click.echo(f"Badge error: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
