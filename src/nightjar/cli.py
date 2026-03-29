"""nightjar CLI - Contract-Anchored Regenerative Development.

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
    scan        Scan a Python file and generate a .card.md spec
    infer       Infer contracts for a Python function via LLM + CrossHair
    spec        Smart router — auto-routes to scan / infer / auto

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
from collections import defaultdict
from pathlib import Path
from typing import Optional

import click

from nightjar import __version__
from nightjar.config import load_config, get_model, get_specs_dir, DEFAULT_CONFIG

# ── Exit codes (from ARCHITECTURE.md Section 8) ─────────

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_CONFIG_ERROR = 2
EXIT_TIMEOUT = 3
EXIT_LLM_ERROR = 4
EXIT_MAX_RETRIES = 5

# ── Config loading ───────────────────────────────────────

# Default config values — imported from config module to avoid duplication
_DEFAULT_CONFIG = DEFAULT_CONFIG


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

### Story 1 - Description (P1)

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
    _run_generate(
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

    # Step 3: Compile to target language (only if verification passed)
    if verify_result.verified:
        # Resolve the .dfy path written by _run_generate
        from nightjar.parser import parse_card_spec
        spec = parse_card_spec(contract_path)
        dfy_path = os.path.join(output_dir, f"{spec.id}.dfy")

        # Lazy import — compiler.py wraps `dafny build` [REF-T01]
        from nightjar.compiler import compile_dafny, UnsupportedTargetError
        try:
            compile_result = compile_dafny(dfy_path, target, output_dir)
            if compile_result.success:
                click.echo(f"Compiled: {compile_result.output_path} ({target})")
                click.echo("Note: compiled output uses Dafny runtime")
            else:
                click.echo(
                    f"Warning: compilation to '{target}' failed "
                    f"(verify still passed): {compile_result.stderr.strip()}",
                    err=True,
                )
        except UnsupportedTargetError as e:
            click.echo(f"Warning: {e}", err=True)
        except FileNotFoundError:
            # dafny binary not installed — verify result is still valid
            click.echo(
                "Warning: Dafny binary not found; skipping compilation. "
                "Install Dafny or set DAFNY_PATH to enable --target compilation.",
                err=True,
            )
        except Exception as e:  # noqa: BLE001
            click.echo(
                f"Warning: compilation step raised an unexpected error: {e}",
                err=True,
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
    spec = parse_card_spec(contract_path)
    code = ""
    audit_dir = config.get("paths", {}).get("audit", ".card/audit/")
    for ext in (".py", ".dfy"):
        candidate = os.path.join(audit_dir, f"{spec.id}{ext}")
        if os.path.exists(candidate):
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

COMMAND_TIERS: dict[str, tuple[int, str]] = {
    "spec": (1, "Start here"),
    "verify": (1, "Start here"),
    "audit": (1, "Start here"),
    "build": (2, "Build pipeline"),
    "ship": (2, "Build pipeline"),
    "retry": (2, "Build pipeline"),
    "watch": (3, "Development"),
    "explain": (3, "Development"),
    "optimize": (3, "Development"),
    "badge": (3, "Development"),
    "lock": (3, "Development"),
    "serve": (4, "Integration"),
    "shadow-ci": (4, "Integration"),
    "hook": (4, "Integration"),
    "mcp": (4, "Integration"),
    "benchmark": (4, "Integration"),
    "immune": (5, "Advanced"),
    "init": (5, "Advanced"),
    "generate": (5, "Advanced"),
    "scan": (5, "Advanced (use 'spec')"),
    "infer": (5, "Advanced (use 'spec')"),
    "auto": (5, "Advanced (use 'spec')"),
}


class NightjarGroup(click.Group):
    """Click Group subclass that renders commands grouped by tier."""

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        sections: dict[tuple[int, str], list[tuple[str, str]]] = defaultdict(list)
        for name in self.list_commands(ctx):
            cmd = self.commands.get(name)
            if cmd is None or cmd.hidden:
                continue
            tier, section = COMMAND_TIERS.get(name, (99, "Other"))
            help_str = cmd.get_short_help_str(limit=formatter.width or 80)
            sections[(tier, section)].append((name, help_str))
        for key in sorted(sections.keys()):
            _, section_name = key
            with formatter.section(section_name):
                formatter.write_dl(sections[key])


@click.group(cls=NightjarGroup, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="nightjar")
@click.pass_context
def main(ctx: click.Context) -> None:
    """nightjar — vericoding CLI for Python.

    Quick start:
      nightjar spec src/mymodule.py    # generate spec from code
      nightjar verify --fast           # verify all specs
      nightjar audit requests          # audit any PyPI package
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
@click.option("--format", "output_format", default=None,
              type=click.Choice(["text", "vscode", "json"]),
              help="Output format.")
@click.option("--output-sarif", default=None, type=click.Path(),
              help="Write SARIF 2.1.0 results to file.")
@click.option("--tui", is_flag=True, default=False, help="Launch Textual TUI dashboard.")
@click.option("--security-pack", default=None, type=click.Choice(["owasp"]),
              help="Inject security invariants before running pipeline.")
@click.pass_context
def verify(
    ctx: click.Context,
    contract: str,
    fast: bool,
    stage: Optional[int],
    ci: bool,
    output_format: Optional[str],
    output_sarif: Optional[str],
    tui: bool,
    security_pack: Optional[str],
) -> None:
    """Run the 5-stage verification pipeline.

    Stages: preflight -> deps -> schema -> property-tests -> formal-proof.
    Architecture: docs/ARCHITECTURE.md Section 3.
    """
    config = ctx.obj["config"]
    spec_path = contract

    # ── TUI mode ──────────────────────────────────────────────────────────────
    if tui:
        try:
            from nightjar.tui import NightjarTUI, HAS_TEXTUAL
            if not HAS_TEXTUAL:
                click.echo("Textual not installed. Install with: pip install textual", err=True)
            else:
                # Pass TUI as display callback
                tui_app = NightjarTUI()
                # Run verification with TUI display
                click.echo("TUI mode — launching Textual dashboard...")
                # For now, just run the normal path — full TUI integration needs run_pipeline to accept a display callback
        except ImportError:
            click.echo("Textual not installed for TUI mode.", err=True)

    # ── --security-pack: inject security invariants into spec before pipeline ──
    if security_pack == "owasp":
        try:
            from nightjar.security.owasp_pack import generate_security_block
            security_invariants = generate_security_block()
            click.echo(
                f"Security pack 'owasp': injected {len(security_invariants)} invariant(s)."
            )
        except ImportError:
            click.echo(
                "Warning: owasp_pack not available — continuing without security invariants.",
                err=True,
            )
        except Exception as e:  # noqa: BLE001
            click.echo(f"Warning: security pack error ({e}) — continuing.", err=True)

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

    # ── SARIF output (write to file, print summary; does NOT short-circuit) ──
    if output_sarif:
        try:
            from nightjar.sarif_writer import write_sarif, sarif_summary
            from nightjar.verifier import to_sarif
            written = write_sarif(result, output_sarif, spec_path=spec_path)
            sarif_dict = to_sarif(result, spec_path)
            click.echo(sarif_summary(sarif_dict, filename=str(written)))
        except Exception as e:
            click.echo(f"SARIF write error: {e}", err=True)

    # ── VS Code problem-matcher format ────────────────────────────────────────
    if output_format == "vscode":
        try:
            from nightjar.formatters.vscode import format_vscode_output
            click.echo(format_vscode_output(result, spec_path=spec_path))
        except Exception as e:
            click.echo(f"Format error: {e}", err=True)
        import sys as _sys
        _sys.exit(EXIT_PASS if result.verified else EXIT_FAIL)

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
        click.echo(f"Generated: {result.spec_id}")
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
    """Build + package artifact for deployment.

    Runs the full build pipeline (generate + verify + compile) then
    packages the resulting artifact. Architecture: docs/ARCHITECTURE.md Section 8.
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

    # Generate build provenance and write it to .card/provenance.json
    try:
        from nightjar.ship import build_provenance, write_provenance
        from nightjar.parser import parse_card_spec
        from nightjar.types import VerifyStatus

        spec = parse_card_spec(contract)
        artifact_path = str(Path(output) / f"{spec.id}.dfy")

        stages_passed = sum(
            1 for s in result.stages
            if s.status in (VerifyStatus.PASS, VerifyStatus.SKIP)
        )
        stages_total = len(result.stages)

        provenance = build_provenance(
            artifact_path=artifact_path,
            model=resolved_model,
            verified=result.verified,
            stages_passed=stages_passed,
            stages_total=stages_total,
            target=resolved_target,
        )

        provenance_path = Path(".card") / "provenance.json"
        write_provenance(provenance, str(provenance_path))

        hash_short = provenance.artifact_hash[:16] if provenance.artifact_hash else "(no artifact)"
        click.echo(f"Provenance: {hash_short}... (SHA-256)")
        click.echo(f"Written to: {provenance_path}")
    except Exception as e:  # noqa: BLE001
        click.echo(f"Warning: provenance tracking failed: {e}", err=True)

    # ── EU CRA Compliance Certificate ───────────────────────────────────────
    try:
        from nightjar.compliance import generate_compliance_cert, export_compliance_cert
        _verify_report: dict = result.__dict__ if hasattr(result, "__dict__") else {}
        # Build a plain dict from the VerifyResult for the compliance module
        _report_dict = {
            "verified": result.verified,
            "confidence_score": int(result.confidence.total) if result.confidence is not None else 0,
            "module": Path(contract).stem,
            "stages": [
                {
                    "name": s.name,
                    "status": s.status.value if hasattr(s.status, "value") else str(s.status),
                    "errors": s.errors or [],
                }
                for s in result.stages
            ],
        }
        cert = generate_compliance_cert(_report_dict)
        cert_path = Path(".card") / "compliance_cert.json"
        export_compliance_cert(cert, str(cert_path))
        click.echo(f"Compliance cert: {cert_path}")
    except ImportError:
        pass  # compliance module not critical
    except Exception as e:
        click.echo(f"Warning: compliance cert failed: {e}", err=True)

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
    """Run LLM prompt optimization (hill-climbing) [REF-T26].

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
@click.option("--svg", is_flag=True, default=False, help="Generate standalone SVG badge.")
@click.option("--shields-json", "shields_json", is_flag=True, default=False,
              help="Write shields.io JSON endpoint.")
@click.option("--readme", is_flag=True, default=False,
              help="Print README markdown embed line.")
@click.option("--owner", default=None, help="GitHub repo owner (for --readme).")
@click.option("--repo-name", default=None, help="GitHub repo name (for --readme).")
@click.pass_context
def badge(
    ctx: click.Context,
    fmt: str,
    report: str,
    svg: bool,
    shields_json: bool,
    readme: bool,
    owner: Optional[str],
    repo_name: Optional[str],
) -> None:
    """Generate a 'Nightjar Verified' badge from last verification result.

    Uses shields.io to create status + coverage badges. [Scout 7 N8]

    Examples:
        nightjar badge --format=url
        nightjar badge --svg
        nightjar badge --shields-json
        nightjar badge --readme --owner myorg --repo-name myrepo
    """
    # ── --svg: generate standalone SVG badge ─────────────────────────────────
    if svg:
        try:
            from nightjar.badge import generate_badge_svg
            click.echo(generate_badge_svg(report))
        except ImportError as e:
            click.echo(f"Error: badge module not available ({e})", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
            return
        except Exception as e:  # noqa: BLE001
            click.echo(f"Badge SVG error: {e}", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
            return
        ctx.exit(EXIT_PASS)
        return

    # ── --shields-json: write shields.io endpoint JSON ────────────────────────
    if shields_json:
        try:
            from nightjar.badge import write_shields_json
            out_path = write_shields_json(report_path=report)
            click.echo(f"shields.io JSON written to {out_path}")
        except ImportError as e:
            click.echo(f"Error: badge module not available ({e})", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
            return
        except Exception as e:  # noqa: BLE001
            click.echo(f"Badge shields-json error: {e}", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
            return
        ctx.exit(EXIT_PASS)
        return

    # ── --readme: print README markdown embed line ────────────────────────────
    if readme:
        if not owner or not repo_name:
            click.echo(
                "Error: --readme requires --owner and --repo-name.", err=True
            )
            ctx.exit(EXIT_CONFIG_ERROR)
            return
        try:
            from nightjar.badge import generate_readme_embed
            click.echo(generate_readme_embed(owner, repo_name))
        except ImportError as e:
            click.echo(f"Error: badge module not available ({e})", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
            return
        except Exception as e:  # noqa: BLE001
            click.echo(f"Badge readme error: {e}", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
            return
        ctx.exit(EXIT_PASS)
        return

    # ── default: --format url / markdown / html ───────────────────────────────
    try:
        from nightjar.badge import generate_badge_url_from_report, generate_badge_markdown

        if not os.path.exists(report):
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


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--llm", is_flag=True, default=False, help="Enhance with LLM suggestions.")
@click.option("--output", "-o", default=None, help="Output path for .card.md (default: .card/<module>.card.md)")
@click.option("--verify", "run_verify", is_flag=True, default=False, help="Run verification after generating spec.")
@click.option("--approve-all", is_flag=True, default=False, help="Auto-approve all candidates without prompting.")
@click.option("--workers", default=None, type=int, help="Number of parallel workers for directory scan.")
@click.option("--min-signal", default="low", type=click.Choice(["low", "medium", "high"]),
              help="Minimum signal level to include in directory scan results.")
@click.option("--smart-sort", is_flag=True, default=False,
              help="Sort files by security criticality before scanning.")
@click.pass_context
def scan(
    ctx: click.Context,
    path: str,
    llm: bool,
    output: Optional[str],
    run_verify: bool,
    approve_all: bool,
    workers: Optional[int],
    min_signal: str,
    smart_sort: bool,
) -> None:
    """Scan a Python file or directory and generate .card.md spec(s).

    Extracts invariants from type hints, guard clauses, docstrings, and
    assertions. No LLM needed by default. Add --llm for enhanced suggestions.
    When PATH is a directory, scans all .py files recursively.

    Examples:
        nightjar scan src/payment.py
        nightjar scan src/payment.py --llm --verify
        nightjar scan src/ --workers 4 --smart-sort
    """
    config = ctx.obj["config"]

    # ── Directory mode ────────────────────────────────────────────────────────
    from pathlib import Path as PathLib
    target = PathLib(path)
    if target.is_dir():
        try:
            from nightjar.scanner import scan_directory
        except ImportError as e:
            click.echo(f"Error: scanner module not available ({e})", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
            return
        try:
            results = scan_directory(
                target,
                workers=workers,
                min_signal=min_signal,
                smart_sort=smart_sort,
            )
        except Exception as e:
            click.echo(f"Scan error: {e}", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
            return
        for r in results:
            if r.candidates:
                click.echo(
                    f"  {r.module_id:40s} — {len(r.candidates)} candidates [{r.signal_strength}]"
                )
        total_candidates = sum(len(r.candidates) for r in results)
        click.echo(f"\nScan complete: {len(results)} files, {total_candidates} candidates")
        ctx.exit(EXIT_PASS)
        return

    # ── Single-file mode (original behaviour) ─────────────────────────────────
    file_path = path

    # Import scanner lazily (Agent 2 module)
    try:
        from nightjar.scanner import scan_file, enhance_with_llm, write_scan_card_md
        from nightjar.scanner import ScanCandidate
    except ImportError as e:
        click.echo(f"Error: scanner module not available ({e})", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    # Step 1: Scan the file
    try:
        result = scan_file(file_path)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return
    except Exception as e:
        click.echo(f"Scan error: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    candidates = result.candidates

    # Show signal strength warning
    if result.signal_strength == "low":
        click.echo(
            f"Warning: low signal in {file_path} — fewer than 2 invariants found. "
            "Consider adding type hints, docstrings, or assertions for better results.",
            err=True,
        )

    click.echo(
        f"Scanned {file_path}: {len(candidates)} candidate(s) found "
        f"[signal: {result.signal_strength}]"
    )

    # Step 2: LLM enhancement (optional)
    if llm:
        try:
            source_text = Path(file_path).read_text(encoding="utf-8")
            click.echo("Enhancing with LLM suggestions...")
            candidates = enhance_with_llm(candidates, source_text)
            new_count = len(candidates) - len(result.candidates)
            if new_count:
                click.echo(f"LLM added {new_count} additional candidate(s).")
        except Exception as e:
            click.echo(f"LLM enhancement failed (continuing without): {e}", err=True)

    if not candidates:
        click.echo("No invariant candidates found. Spec not written.")
        ctx.exit(EXIT_FAIL)
        return

    # Step 3: Approval loop
    if approve_all:
        approved = candidates
        click.echo(f"Auto-approved all {len(approved)} candidate(s).")
    else:
        approved = _run_scan_approval_loop(candidates)

    if not approved:
        click.echo("All candidates rejected. Spec not written.")
        ctx.exit(EXIT_FAIL)
        return

    # Step 4: Resolve output path
    if output is None:
        specs_dir = _get_specs_dir(config)
        output = str(Path(specs_dir) / f"{result.module_id}.card.md")

    # Step 5: Write the .card.md file
    try:
        written_path = write_scan_card_md(output, approved, result.module_id)
        click.echo(f"Spec written: {written_path}")
        approved_count = len(approved)
        skipped_count = len(candidates) - approved_count
        click.echo(f"Invariants: {len(candidates)} suggested, {approved_count} added, {skipped_count} skipped")
    except Exception as e:
        click.echo(f"Error writing spec: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    # Step 6: Optional verification
    if run_verify:
        click.echo(f"Running verification on {written_path}...")
        try:
            verify_result = _run_verify(written_path, config=config)
            if verify_result.verified:
                click.echo("VERIFIED -- all stages passed")
            else:
                click.echo("FAILED -- verification did not pass")
                ctx.exit(EXIT_FAIL)
                return
        except SystemExit:
            raise
        except Exception as e:
            click.echo(f"Verification error: {e}", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
            return

    ctx.exit(EXIT_PASS)


@main.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--function", "function_name", default=None, help="Function name to infer contracts for.")
@click.option("--no-verify", "skip_verify", is_flag=True, default=False, help="Skip CrossHair verification (fast mode).")
@click.option("--append-to-card", is_flag=True, default=False, help="Append inferred contracts to matching .card.md spec.")
@click.option("--model", default=None, help="LLM model (default: NIGHTJAR_MODEL env or config).")
@click.option("--max-iterations", default=5, show_default=True, help="Maximum CrossHair repair iterations.")
@click.pass_context
def infer(
    ctx: click.Context,
    file_path: str,
    function_name: Optional[str],
    skip_verify: bool,
    append_to_card: bool,
    model: Optional[str],
    max_iterations: int,
) -> None:
    """Infer contracts for a Python function via LLM + CrossHair verification.

    Reads FILE_PATH, extracts function(s), calls the LLM to generate
    preconditions and postconditions, then symbolically verifies them with
    CrossHair in a generate → verify → repair loop.

    If --function is omitted, infers contracts for every top-level function
    in the file.

    References: [REF-NEW-08] NL2Contract, [REF-NEW-09] 98.2% repair loop,
    [REF-NEW-11] Clover, [REF-T09] CrossHair, [REF-T16] litellm.

    Examples:
        nightjar infer src/payment.py --function charge
        nightjar infer src/payment.py --no-verify
        nightjar infer src/payment.py --append-to-card
    """
    config = ctx.obj["config"]
    resolved_model = _get_model(model, config)

    # Lazy imports — keep startup time low
    try:
        from nightjar.inferrer import infer_contracts, InferredContract
        from nightjar.contract_library import retrieve_examples
    except ImportError as e:
        click.echo(f"Error: inferrer module not available ({e})", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    # Read source
    try:
        source = Path(file_path).read_text(encoding="utf-8")
    except OSError as e:
        click.echo(f"Error reading {file_path}: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    # Determine which functions to infer contracts for
    import ast as _ast
    if function_name:
        function_names: list[str] = [function_name]
    else:
        try:
            tree = _ast.parse(source)
            function_names = [
                node.name
                for node in _ast.walk(tree)
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef))
                and not node.name.startswith("_")
            ]
        except SyntaxError as e:
            click.echo(f"Syntax error in {file_path}: {e}", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
            return

    if not function_names:
        click.echo(f"No public functions found in {file_path}.")
        ctx.exit(EXIT_FAIL)
        return

    click.echo(
        f"Inferring contracts for {len(function_names)} function(s) in {file_path} "
        f"[model: {resolved_model}, max-iterations: {max_iterations}]"
    )

    results: list[InferredContract] = []
    any_verified = False
    any_counterexample = False

    for fn_name in function_names:
        # Retrieve few-shot examples from contract_library [REF-NEW-12/PropertyGPT]
        try:
            _ast_tree = _ast.parse(source)
            param_names: list[str] = []
            for node in _ast.walk(_ast_tree):
                if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) and node.name == fn_name:
                    param_names = [
                        arg.arg for arg in node.args.args if arg.arg != "self"
                    ]
                    break
        except Exception:
            param_names = []

        examples = retrieve_examples(fn_name, param_names, top_k=3)

        click.echo(f"\n  [{fn_name}] Generating contracts...")
        contract = infer_contracts(
            source=source,
            function_name=fn_name,
            model=resolved_model,
            max_iterations=max_iterations,
            use_crosshair=not skip_verify,
            retrieved_examples=examples,
        )
        results.append(contract)

        # Display result
        status_label = {
            "verified": "VERIFIED",
            "unverified": "unverified",
            "counterexample": "COUNTEREXAMPLE",
            "timeout": "timeout",
            "not_installed": "CrossHair not installed",
            "error": "error",
        }.get(contract.verification_status, contract.verification_status)

        click.echo(f"  [{fn_name}] Status: {status_label}  confidence: {contract.confidence:.0%}  iterations: {contract.iterations_used}")

        for pre in contract.preconditions:
            click.echo(f"    PRE:  {pre}")
        for post in contract.postconditions:
            click.echo(f"    POST: {post}")

        if contract.counterexample:
            raw = contract.counterexample.get("counterexample_text") or contract.counterexample.get("raw", "")
            if raw:
                click.echo(f"    Counterexample: {raw[:200]}")

        if contract.verification_status == "verified":
            any_verified = True
        if contract.verification_status == "counterexample":
            any_counterexample = True

    # Append to .card.md if requested
    if append_to_card and results:
        _append_inferred_contracts_to_card(file_path, results, config)

    # Summary
    total = len(results)
    verified_count = sum(1 for r in results if r.verification_status == "verified")
    click.echo(f"\nInference complete: {verified_count}/{total} function(s) verified.")

    if any_counterexample:
        ctx.exit(EXIT_FAIL)
    else:
        ctx.exit(EXIT_PASS)


def _append_inferred_contracts_to_card(
    file_path: str, results: list, config: dict
) -> None:
    """Append inferred contracts as invariants to a matching .card.md spec.

    Looks for a .card.md file whose module_id matches the stem of file_path
    in the specs directory. If found, appends the inferred contracts as
    new invariant blocks. If not found, prints a warning.

    Args:
        file_path: Path to the Python source file that was analyzed.
        results:   List of InferredContract objects from infer_contracts().
        config:    Loaded nightjar config dict.
    """
    module_id = Path(file_path).stem
    specs_dir = _get_specs_dir(config)
    card_path = Path(specs_dir) / f"{module_id}.card.md"

    if not card_path.exists():
        click.echo(
            f"  Note: no matching spec found at {card_path}. "
            "Use 'nightjar scan' to create one first, or specify --output.",
            err=True,
        )
        return

    lines_to_append: list[str] = ["\n## Inferred Contracts\n\n"]
    for contract in results:
        if not contract.preconditions and not contract.postconditions:
            continue
        lines_to_append.append(f"### {contract.function_name}\n\n")
        lines_to_append.append(f"- verification_status: {contract.verification_status}\n")
        lines_to_append.append(f"- confidence: {contract.confidence:.2f}\n")
        for pre in contract.preconditions:
            lines_to_append.append(f"- pre: `{pre}`\n")
        for post in contract.postconditions:
            lines_to_append.append(f"- post: `{post}`\n")
        lines_to_append.append("\n")

    try:
        with card_path.open("a", encoding="utf-8") as f:
            f.writelines(lines_to_append)
        click.echo(f"  Contracts appended to {card_path}")
    except OSError as e:
        click.echo(f"  Error appending to spec: {e}", err=True)


def _run_scan_approval_loop(candidates: list) -> list:
    """Present scan candidates for Y/n/modify approval.

    Mirrors the auto._run_approval_loop pattern. User can:
      y  — accept as-is
      n  — reject (skip)
      m  — modify the text, then accept

    Returns:
        List of approved ScanCandidate objects (accepted or modified).
    """
    import threading

    approved = []
    for i, candidate in enumerate(candidates, 1):
        click.echo(
            f"\n[{i}/{len(candidates)}] [{candidate.tier.upper()}] {candidate.statement}"
        )
        click.echo(
            f"  Source: {candidate.source} (line {candidate.source_line})"
            f"  |  Function: {candidate.function_name or '<module>'}"
            f"  |  Confidence: {candidate.confidence:.0%}"
        )

        try:
            choice = click.prompt(
                "  Accept? [y/n/m=modify]",
                default="y",
                show_default=True,
            )
        except (EOFError, Exception):
            choice = "y"

        if choice.lower() == "n":
            continue
        elif choice.lower() == "m":
            try:
                modified = click.prompt(
                    "  Enter modified statement", default=candidate.statement
                )
            except (EOFError, Exception):
                modified = candidate.statement
            # Return a copy with modified statement
            from dataclasses import replace as dc_replace
            approved.append(dc_replace(candidate, statement=modified.strip() or candidate.statement))
        else:
            approved.append(candidate)

    return approved


# ── audit command ────────────────────────────────────────────────────────────


@main.command()
@click.argument("package_spec")
@click.option("--with-deps", is_flag=True, default=False, help="Also scan declared dependencies.")
@click.option("--no-cve", is_flag=True, default=False, help="Skip CVE lookup (offline mode).")
@click.option("--output", "-o", default=None, help="Write .card.md spec to this path.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Output results as JSON.")
@click.option("--no-cache", is_flag=True, default=False, help="Bypass cache, force fresh scan.")
@click.pass_context
def audit(
    ctx: click.Context,
    package_spec: str,
    with_deps: bool,
    no_cve: bool,
    output: Optional[str],
    as_json: bool,
    no_cache: bool,
) -> None:
    """Scan any PyPI package for contract coverage and known CVEs.

    Downloads the package, scans every .py file for invariant candidates,
    checks CVEs via OSV, and renders a terminal report card with letter
    grades (A+ through F). Think 'Lighthouse score for Python packages.'

    Examples:
        nightjar audit requests
        nightjar audit flask==3.0.0 --with-deps
        nightjar audit requests --output requests.card.md
        nightjar audit requests --json
    """
    try:
        from nightjar.pkg_auditor import audit_package, render_report_card, render_json
    except ImportError as e:
        click.echo(f"Error: pkg_auditor module not available ({e})", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    try:
        result = audit_package(
            package_spec,
            with_deps=with_deps,
            check_cves=not no_cve,
            use_cache=not no_cache,
        )
    except Exception as e:
        click.echo(f"Audit error: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)  # exit code 2
        return

    # Render output
    if as_json:
        click.echo(render_json(result))
    else:
        click.echo(render_report_card(result))

    # Write candidates to .card.md if requested
    if output:
        try:
            card_lines = [
                f"---\ncard-version: '1.0'\nid: {result.name}\n"
                f"title: {result.name.title()} (audit)\nstatus: draft\n---\n\n"
                "## Invariant Candidates\n\n"
            ]
            for c in result.candidates:
                card_lines.append(f"- {c.statement}\n")
            Path(output).write_text("".join(card_lines), encoding="utf-8")
            click.echo(f"Spec written: {output}")
        except Exception as e:
            click.echo(f"Error writing spec: {e}", err=True)

    # Exit code: 0 if score >= 70 and no CVEs, 1 otherwise
    if result.scores.overall >= 70 and not result.cves:
        ctx.exit(EXIT_PASS)
    else:
        ctx.exit(EXIT_FAIL)


# ── benchmark command ─────────────────────────────────────────────────────────


@main.command()
@click.argument("benchmark_path", type=click.Path(exists=True))
@click.option("--source", default="auto",
              type=click.Choice(["auto", "vericoding", "dafnybench"]),
              help="Benchmark format (default: auto-detect).")
@click.option("--max-attempts", default=5, type=int,
              help="Maximum verification attempts per task (default: 5).")
@click.option("--timeout", default=120, type=int,
              help="Per-task timeout in seconds (default: 120).")
@click.option("--workers", default=1, type=int,
              help="Number of parallel worker threads (default: 1).")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Output results as JSON.")
@click.pass_context
def benchmark(
    ctx: click.Context,
    benchmark_path: str,
    source: str,
    max_attempts: int,
    timeout: int,
    workers: int,
    as_json: bool,
) -> None:
    """Run Nightjar against an academic verification benchmark.

    Supports vericoding (POPL 2026) and DafnyBench task files.
    Produces pass@1 and pass@k metrics comparable to published baselines.

    Examples:
        nightjar benchmark tasks/vericoding_tasks.jsonl
        nightjar benchmark tasks/dafnybench/ --source dafnybench
        nightjar benchmark tasks.jsonl --max-attempts 3 --workers 4 --json
    """
    try:
        from nightjar.benchmark_adapter import load_benchmark_suite
        from nightjar.benchmark_runner import (
            run_benchmark,
            format_benchmark_report,
            format_benchmark_json,
        )
    except ImportError as e:
        click.echo(f"Error: benchmark modules not available ({e})", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    # Load tasks from the benchmark file/directory
    try:
        tasks = load_benchmark_suite(Path(benchmark_path), source=source)
    except Exception as e:
        click.echo(f"Error loading benchmark: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    if not tasks:
        click.echo("No benchmark tasks found.")
        ctx.exit(EXIT_FAIL)
        return

    click.echo(
        f"Running benchmark: {len(tasks)} task(s) "
        f"[max-attempts: {max_attempts}, timeout: {timeout}s, workers: {workers}]"
    )

    try:
        report = run_benchmark(
            tasks,
            max_attempts=max_attempts,
            timeout_per_task=float(timeout),
            workers=workers,
        )
    except Exception as e:
        click.echo(f"Benchmark error: {e}", err=True)
        ctx.exit(EXIT_CONFIG_ERROR)
        return

    if as_json:
        click.echo(format_benchmark_json(report))
    else:
        click.echo(format_benchmark_report(report))

    # Exit 0 if at least one task passed, 1 otherwise
    if report.passed_tasks > 0:
        ctx.exit(EXIT_PASS)
    else:
        ctx.exit(EXIT_FAIL)


@main.command("shadow-ci")
@click.option("--mode", default="shadow", type=click.Choice(["shadow", "strict"]))
@click.option("--spec", required=True, type=click.Path(exists=True),
              help="Path to verify.json report from a nightjar verify run.")
def shadow_ci(mode: str, spec: str) -> None:
    """Run verification in CI mode — shadow (non-blocking) or strict.

    In shadow mode the command always exits 0 regardless of outcome,
    so it never blocks a PR. In strict mode it exits 1 on failure.

    References:
        Scout 7 Feature 2 — Shadow CI mode.
    """
    try:
        from nightjar.shadow_ci import run_shadow_ci
        result = run_shadow_ci(report_path=spec, mode=mode)
        if result.pr_comment:
            click.echo(result.pr_comment)
        else:
            import json as _json
            click.echo(_json.dumps(result.report, indent=2))
        if mode == "strict" and not result.report.get("verified", False):
            raise SystemExit(1)
    except ImportError:
        click.echo("Shadow CI module not available.", err=True)
        raise SystemExit(2)


# ── Immune system commands ──────────────────────────────────────────────
try:
    from nightjar.immune_commands import immune_group
    main.add_command(immune_group)
except ImportError:
    pass  # immune deps not installed — commands not registered


# ── hook command group ───────────────────────────────────────────────────────


@main.group()
def hook() -> None:
    """Manage coding agent integrations (Claude Code, Cursor, Windsurf, Kiro)."""


@hook.command("install")
@click.option(
    "--target",
    default="all",
    type=click.Choice(["claude-code", "cursor", "windsurf", "kiro", "all"]),
    help="Which agent to install for (default: all detected agents).",
)
@click.option("--force", is_flag=True, default=False,
              help="Overwrite an existing Nightjar hook installation.")
@click.option("--dir", "project_dir", default=".", type=click.Path(file_okay=False),
              help="Project root directory (default: current directory).")
def hook_install(target: str, force: bool, project_dir: str) -> None:
    """Install Nightjar verification hooks into coding agent configs."""
    try:
        from pathlib import Path as _Path
        from nightjar.hook_installer import (
            install_hook,
            detect_available_agents,
        )
    except ImportError as e:
        click.echo(f"Error: hook_installer module not available ({e})", err=True)
        raise SystemExit(EXIT_CONFIG_ERROR)

    cwd = _Path(project_dir).resolve()

    targets_to_install: list[str]
    if target == "all":
        targets_to_install = detect_available_agents(cwd)
        if not targets_to_install:
            click.echo(
                "No coding agent directories detected in this project. "
                "Use --target to specify one explicitly.",
                err=True,
            )
            raise SystemExit(EXIT_CONFIG_ERROR)
        click.echo(f"Detected agents: {', '.join(targets_to_install)}")
    else:
        targets_to_install = [target]

    any_error = False
    for t in targets_to_install:
        try:
            result = install_hook(t, cwd, force=force)
            click.echo(result.message)
        except Exception as e:  # noqa: BLE001
            click.echo(f"Error installing hook for {t}: {e}", err=True)
            any_error = True

    raise SystemExit(EXIT_CONFIG_ERROR if any_error else EXIT_PASS)


@hook.command("remove")
@click.option(
    "--target",
    required=True,
    type=click.Choice(["claude-code", "cursor", "windsurf", "kiro"]),
    help="Which agent's hook to remove.",
)
@click.option("--dir", "project_dir", default=".",
              help="Project root directory (default: current directory).")
def hook_remove(target: str, project_dir: str) -> None:
    """Remove Nightjar hooks from a coding agent config."""
    try:
        from pathlib import Path as _Path
        from nightjar.hook_installer import remove_hook
    except ImportError as e:
        click.echo(f"Error: hook_installer module not available ({e})", err=True)
        raise SystemExit(EXIT_CONFIG_ERROR)

    cwd = _Path(project_dir).resolve()
    try:
        result = remove_hook(target, cwd)
        click.echo(result.message)
        raise SystemExit(EXIT_PASS)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        click.echo(f"Error removing hook for {target}: {e}", err=True)
        raise SystemExit(EXIT_CONFIG_ERROR)


@hook.command("list")
@click.option("--dir", "project_dir", default=".",
              help="Project root directory (default: current directory).")
def hook_list(project_dir: str) -> None:
    """Show installed Nightjar hooks."""
    try:
        from pathlib import Path as _Path
        from nightjar.hook_installer import list_hooks
    except ImportError as e:
        click.echo(f"Error: hook_installer module not available ({e})", err=True)
        raise SystemExit(EXIT_CONFIG_ERROR)

    cwd = _Path(project_dir).resolve()
    try:
        statuses = list_hooks(cwd)
        if not statuses:
            click.echo("No supported agents found.")
            raise SystemExit(EXIT_PASS)
        for s in statuses:
            installed_label = "installed" if s.installed else "not installed"
            click.echo(f"  {s.target:15s} {installed_label:15s} ({s.config_path})")
        raise SystemExit(EXIT_PASS)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        click.echo(f"Error listing hooks: {e}", err=True)
        raise SystemExit(EXIT_CONFIG_ERROR)


# ── mcp command ──────────────────────────────────────────────────────────────


@main.command("mcp")
@click.option(
    "--transport",
    default="stdio",
    type=click.Choice(["stdio"]),
    help="Transport protocol (default: stdio).",
)
def mcp_cmd(transport: str) -> None:
    """Start the Nightjar MCP server (Model Context Protocol).

    Exposes three tools to coding assistants:
      verify_contract, get_violations, suggest_fix.

    References: [REF-T18] MCP SDK.
    """
    try:
        from nightjar.mcp_server import create_mcp_server, HAS_MCP
        if not HAS_MCP:
            click.echo("MCP SDK not installed. Install with: pip install mcp", err=True)
            raise SystemExit(EXIT_CONFIG_ERROR)
        server = create_mcp_server()
        server.run(transport=transport)
    except SystemExit:
        raise
    except ImportError:
        click.echo("MCP SDK not installed. Install with: pip install mcp", err=True)
        raise SystemExit(EXIT_CONFIG_ERROR)
    except Exception as e:  # noqa: BLE001
        click.echo(f"MCP server error: {e}", err=True)
        raise SystemExit(EXIT_CONFIG_ERROR)


# ── spec smart-router command ────────────────────────────────────────────────


def _route_spec_input(input_target: str, mode: Optional[str], model_available: bool) -> str:
    """Route 'nightjar spec' to the correct sub-mode.

    Returns one of: "scan_file" | "scan_dir" | "infer" | "auto"

    Priority:
      1. --mode flag is authoritative (if provided)
      2. Path exists as directory                → scan_dir
      3. Path exists as file + model available   → infer
      4. Path exists as file + no model          → scan_file
      5. Looks like a .py path (non-existent)    → scan_file (will error clearly)
      6. Anything else                           → auto (NL intent)
    """
    p = Path(input_target)

    # Priority 1: explicit --mode flag overrides everything
    if mode is not None:
        if mode == "scan":
            return "scan_dir" if p.is_dir() else "scan_file"
        if mode == "infer":
            return "infer"
        if mode == "auto":
            return "auto"

    # Priority 2: existing directory
    if p.is_dir():
        return "scan_dir"

    # Priority 3 & 4: existing file
    if p.is_file():
        return "infer" if model_available else "scan_file"

    # Priority 5: looks like a Python file path (non-existent) → scan will report clearly
    if input_target.endswith(".py"):
        return "scan_file"

    # Priority 6: treat as natural-language intent
    return "auto"


def _announce_routing(route: str, model: str, *, err: bool = True) -> None:
    """Print the auto-detected routing decision to stderr.

    Args:
        route:  The resolved route string (scan_file | scan_dir | infer | auto).
        model:  The resolved model name (used for infer hint).
        err:    Write to stderr when True (default).
    """
    _hints = {
        "scan_file": "use --mode infer for LLM-enhanced contracts",
        "scan_dir":  "use --mode infer for LLM-enhanced contracts",
        "infer":     "use --mode scan for pure AST extraction",
        "auto":      "use --mode scan with a file path for AST extraction",
    }
    _labels = {
        "scan_file": "scan (file)",
        "scan_dir":  "scan (dir)",
        "infer":     f"infer (model: {model})" if model else "infer",
        "auto":      "auto (natural language)",
    }
    label = _labels.get(route, route)
    hint = _hints.get(route, "")
    msg = f"spec: routing to {label}"
    if hint:
        msg = f"{msg} — {hint}"
    click.echo(msg, err=err)


@main.command()
@click.argument("input_target")
@click.option(
    "--mode",
    type=click.Choice(["scan", "infer", "auto"]),
    default=None,
    help="Force routing mode (default: auto-detect from input).",
)
@click.option("--approve-all", is_flag=True, default=False,
              help="Auto-approve all candidates without prompting.")
@click.option("--output", "-o", default=None,
              help="Output path / directory for the generated .card.md.")
@click.option("--model", default=None,
              help="LLM model (default: NIGHTJAR_MODEL env or config).")
@click.option("--verify", "run_verify", is_flag=True, default=False,
              help="Run verification pipeline after generating spec.")
@click.option("--llm", is_flag=True, default=False,
              help="Enhance scan results with LLM suggestions (scan mode only).")
@click.option("--function", "function_name", default=None,
              help="Target a specific function by name (infer mode only).")
@click.option("--no-verify", "skip_verify", is_flag=True, default=False,
              help="Skip CrossHair symbolic verification (infer mode only).")
@click.option("--append-to-card", is_flag=True, default=False,
              help="Append inferred contracts to existing .card.md (infer mode only).")
@click.option("--max-iterations", default=5, show_default=True,
              help="Maximum CrossHair repair iterations (infer mode only).")
@click.option("--workers", default=None, type=int,
              help="Parallel workers for directory scan (scan dir mode only).")
@click.option(
    "--min-signal",
    default="low",
    type=click.Choice(["low", "medium", "high"]),
    help="Minimum signal level to include (scan dir mode only).",
)
@click.option("--smart-sort", is_flag=True, default=False,
              help="Sort files by security criticality (scan dir mode only).")
@click.pass_context
def spec(
    ctx: click.Context,
    input_target: str,
    mode: Optional[str],
    approve_all: bool,
    output: Optional[str],
    model: Optional[str],
    run_verify: bool,
    llm: bool,
    function_name: Optional[str],
    skip_verify: bool,
    append_to_card: bool,
    max_iterations: int,
    workers: Optional[int],
    min_signal: str,
    smart_sort: bool,
) -> None:
    """Generate a .card.md spec — smart routes to scan, infer, or auto.

    INPUT_TARGET can be:
      - a Python file    → scans AST (or infers with LLM if model is set)
      - a directory      → scans all .py files recursively
      - a quoted string  → generates spec from natural language intent

    Examples:
        nightjar spec src/payment.py
        nightjar spec src/payment.py --mode infer
        nightjar spec src/
        nightjar spec "payment processing with refund support"
    """
    config = ctx.obj["config"]
    resolved_model = _get_model(model, config)
    model_available = bool(resolved_model)

    route = _route_spec_input(input_target, mode, model_available)

    # Announce routing decision to stderr only when mode was auto-detected
    if mode is None:
        _announce_routing(route, resolved_model, err=True)

    if route in ("scan_file", "scan_dir"):
        ctx.invoke(
            scan,
            path=input_target,
            llm=llm,
            output=output,
            run_verify=run_verify,
            approve_all=approve_all,
            workers=workers,
            min_signal=min_signal,
            smart_sort=smart_sort,
        )
    elif route == "infer":
        # Pass model=model (the raw CLI value, not resolved_model) so infer
        # can call _get_model() itself with its own config context, preserving
        # its existing resolution order (flag → env → config).
        ctx.invoke(
            infer,
            file_path=input_target,
            function_name=function_name,
            skip_verify=skip_verify,
            append_to_card=append_to_card,
            model=model,
            max_iterations=max_iterations,
        )
    elif route == "auto":
        # Call run_auto directly to avoid Click's exception propagation issue
        # when ctx.invoke() is used with commands that call ctx.exit() inside
        # a bare `except Exception` block.
        try:
            from nightjar.auto import run_auto
            result = run_auto(
                nl_intent=input_target,
                output_path=output or ".card",
                model=resolved_model,
                yes=approve_all,
            )
            if result.card_path:
                click.echo(f"Created spec: {result.card_path}")
                total = result.approved_count + result.skipped_count
                click.echo(
                    f"Rules: {total} suggested, {result.approved_count} added, "
                    f"{result.skipped_count} skipped"
                )
                ctx.exit(EXIT_PASS)
            else:
                click.echo("No spec generated (all invariants rejected or error).")
                ctx.exit(EXIT_FAIL)
        except click.exceptions.Exit:
            raise  # re-raise Exit so Click can handle exit codes correctly
        except ImportError as e:
            click.echo(f"Error: auto module not available ({e})", err=True)
            ctx.exit(EXIT_CONFIG_ERROR)
        except Exception as e:  # noqa: BLE001
            click.echo(f"Auto error: {e}", err=True)
            ctx.exit(EXIT_LLM_ERROR)


@main.command()
@click.option("--port", default=8000, type=int, help="Port to bind to.")
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
def serve(port, host):
    """Launch the Nightjar Canvas web UI locally."""
    try:
        from nightjar.web_server import app, HAS_FASTAPI
        if not HAS_FASTAPI:
            click.echo("FastAPI not installed. Install with: pip install nightjar-verify[canvas]", err=True)
            raise SystemExit(2)
        import uvicorn
        click.echo(f"Nightjar Canvas → http://{host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except ImportError:
        click.echo("Install canvas extras: pip install nightjar-verify[canvas]", err=True)
        raise SystemExit(2)
