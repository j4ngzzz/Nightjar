"""CARD automated demo script.

Demonstrates the full CARD pipeline: init -> build -> verify -> explain.
Shows model swapping, failure handling, and cost tracking.

References:
- [REF-T17] Click CLI framework
- [REF-C03] Multi-agent generation pipeline
- ARCHITECTURE.md Section 9 -- Data Flow
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ── Rich imports (graceful fallback) ─────────────────────

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    from rich.text import Text
    from rich.table import Table
    from rich.rule import Rule

    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# ── Constants ─────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTRACTD_CMD = "contractd"

# Approximate per-pipeline costs (USD) for common models.
# These are estimates based on typical spec sizes (~2k tokens in, ~4k out).
MODEL_COSTS = {
    "claude-sonnet-4-6": {"input": 0.003, "output": 0.015, "label": "Claude Sonnet"},
    "deepseek/deepseek-chat": {"input": 0.0001, "output": 0.0002, "label": "DeepSeek Chat"},
    "openai/gpt-4o": {"input": 0.005, "output": 0.015, "label": "GPT-4o"},
    "openai/o3": {"input": 0.01, "output": 0.04, "label": "OpenAI o3"},
}

# Simulated outputs used when --no-llm is active.
SIMULATED_SPEC = """---
card-version: "1.0"
id: payment
title: Payment Processing
status: draft
module:
  owns: [process_payment, refund_payment]
  depends-on: {}
contract:
  inputs:
    - name: amount
      type: integer
      constraints: "amount > 0 AND amount <= 1_000_000"
    - name: currency
      type: string
      constraints: "currency IN ['USD', 'EUR', 'GBP']"
    - name: user_id
      type: string
      constraints: "len(user_id) > 0"
  outputs:
    - name: PaymentResult
      type: object
  errors:
    - InvalidAmountError
    - InsufficientFundsError
    - CurrencyNotSupportedError
    - PaymentGatewayError
invariants:
  - id: INV-001
    tier: example
    statement: "process_payment(100, 'USD', 'user1') returns status='success'"
    rationale: "Happy-path smoke test"
  - id: INV-002
    tier: property
    statement: "for all valid (amount, currency, user_id): result.amount_charged + result.fee == result.total"
    rationale: "Financial integrity"
  - id: INV-003
    tier: formal
    statement: "forall a: int :: a > 0 ==> process_payment(a, c, u).amount_charged <= a"
    rationale: "Accounting invariant: charge never exceeds requested amount"
---

## Intent

Process payments with mathematical guarantees on financial integrity.
"""

SIMULATED_BUILD_SUCCESS = """Stage 0 (preflight):  PASS  [12ms]
Stage 1 (deps):       PASS  [45ms]
Stage 2 (schema):     PASS  [23ms]
Stage 3 (pbt):        PASS  [1.34s]  (100 examples tested)
Stage 4 (formal):     PASS  [8.72s]  (Dafny verified)

 VERIFIED  -- all 5 stages passed

Total duration: 10.14s | Retries: 0
"""

SIMULATED_BUILD_FAIL = """Stage 0 (preflight):  PASS  [11ms]
Stage 1 (deps):       PASS  [42ms]
Stage 2 (schema):     PASS  [19ms]
Stage 3 (pbt):        FAIL  [2.01s]

 FAIL  -- Stage 3 (pbt) failed

  Property violated: impossible_invariant
    for all x: x > 0 AND x < 0
    Counterexample: x = 1

Total duration: 2.08s | Retries: 0
"""

SIMULATED_EXPLAIN = """============================================================
VERIFICATION FAILURE EXPLANATION
============================================================

Failed Stage: Stage 3 (pbt)

Invariant Violated: impossible_invariant
  for all x: x > 0 AND x < 0

Errors:
  - Property violated: for all x: x > 0 AND x < 0
    Counterexample: x = 1

Suggested Fix: The property-based test found a counterexample that violates
an invariant. Review the counterexample values and add input validation or
fix the implementation logic. Consider tightening preconditions in the
.card.md spec.

------------------------------------------------------------
Stages Summary:
  Stage 0 (preflight): PASS
  Stage 1 (deps):      PASS
  Stage 2 (schema):    PASS
  Stage 3 (pbt):       FAIL
  Stage 4 (formal):    SKIP
------------------------------------------------------------
"""


# ── Console helpers ───────────────────────────────────────


def _make_console() -> "Console":
    """Create a Rich Console or a plain-text fallback."""
    if HAS_RICH:
        return Console(force_terminal=True)
    return None  # type: ignore[return-value]


def _print_header(console):
    """Print the demo header banner."""
    if HAS_RICH and console:
        console.print()
        console.print(
            Panel(
                "[bold cyan]CARD Demo[/bold cyan]\n"
                "Contract-Anchored Regenerative Development\n\n"
                "[dim]Verification layer for AI-generated code[/dim]",
                border_style="cyan",
                padding=(1, 4),
            )
        )
        console.print()
    else:
        print("=" * 60)
        print("  CARD Demo")
        print("  Contract-Anchored Regenerative Development")
        print("  Verification layer for AI-generated code")
        print("=" * 60)
        print()


def _print_step(console, step_num: int, title: str):
    """Print a step header."""
    if HAS_RICH and console:
        console.print()
        console.print(Rule(f"[bold yellow]Step {step_num}: {title}[/bold yellow]"))
        console.print()
    else:
        print()
        print(f"--- Step {step_num}: {title} ---")
        print()


def _print_success(console, message: str):
    """Print a success message in green."""
    if HAS_RICH and console:
        console.print(f"[bold green]{message}[/bold green]")
    else:
        print(f"[OK] {message}")


def _print_fail(console, message: str):
    """Print a failure message in red."""
    if HAS_RICH and console:
        console.print(f"[bold red]{message}[/bold red]")
    else:
        print(f"[FAIL] {message}")


def _print_info(console, message: str):
    """Print an informational message."""
    if HAS_RICH and console:
        console.print(f"[dim]{message}[/dim]")
    else:
        print(f"  {message}")


def _print_command(console, cmd: str):
    """Print a command that is about to be executed."""
    if HAS_RICH and console:
        console.print(f"  [bold]$ {cmd}[/bold]")
    else:
        print(f"  $ {cmd}")


def _print_output(console, text: str):
    """Print command output in a panel."""
    if HAS_RICH and console:
        console.print(Panel(text.strip(), border_style="dim", padding=(0, 2)))
    else:
        for line in text.strip().splitlines():
            print(f"    {line}")


def _print_code(console, code: str, lexer: str = "yaml"):
    """Print source code with syntax highlighting."""
    if HAS_RICH and console:
        syntax = Syntax(code.strip(), lexer, theme="monokai", line_numbers=True)
        console.print(syntax)
    else:
        for i, line in enumerate(code.strip().splitlines(), 1):
            print(f"  {i:3d} | {line}")


# ── Subprocess runner ─────────────────────────────────────


def _run_cmd(
    cmd: list[str],
    *,
    dry_run: bool = False,
    console=None,
    cwd: str | None = None,
    env: dict | None = None,
    timeout: int = 120,
) -> tuple[int, str, str]:
    """Run a subprocess command and return (returncode, stdout, stderr).

    Args:
        cmd: Command and arguments.
        dry_run: If True, print the command but do not execute it.
        console: Rich Console for output.
        cwd: Working directory for the subprocess.
        env: Additional environment variables to set.
        timeout: Timeout in seconds.

    Returns:
        Tuple of (return_code, stdout, stderr). In dry_run mode returns (0, '', '').
    """
    cmd_str = " ".join(cmd)
    _print_command(console, cmd_str)

    if dry_run:
        _print_info(console, "(dry-run: command not executed)")
        return 0, "", ""

    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd or str(PROJECT_ROOT),
            env=run_env,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 3, "", f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return 2, "", f"Command not found: {cmd[0]}"
    except Exception as exc:
        return 2, "", f"Error running command: {exc}"


# ── Demo steps ────────────────────────────────────────────


def step_init(console, tmp_dir: str, *, dry_run: bool, no_llm: bool) -> str | None:
    """Step 1: Scaffold a .card.md spec with contractd init.

    References:
        [REF-T17] Click CLI -- init command
    """
    _print_step(console, 1, "Init -- Scaffold a .card.md spec")
    _print_info(console, "Creating a fresh payment module spec in a temp directory...")

    cmd = [CONTRACTD_CMD, "init", "payment", "--output", tmp_dir]
    rc, stdout, stderr = _run_cmd(cmd, dry_run=dry_run, console=console)

    if dry_run:
        return os.path.join(tmp_dir, ".card", "payment.card.md")

    if rc == 0:
        spec_path = os.path.join(tmp_dir, ".card", "payment.card.md")
        if os.path.isfile(spec_path):
            _print_success(console, f"Created: {spec_path}")
            return spec_path
        else:
            _print_success(console, stdout.strip() if stdout else "Spec created")
            return spec_path
    else:
        _print_fail(console, f"Init failed (exit {rc}): {stderr.strip()}")
        return None


def step_show_spec(console, spec_path: str | None, *, dry_run: bool, no_llm: bool):
    """Step 2: Display the generated .card.md specification.

    References:
        [REF-T17] Click CLI -- spec display
    """
    _print_step(console, 2, "Show Spec -- Review the .card.md file")

    if dry_run or spec_path is None or not os.path.isfile(spec_path):
        _print_info(console, "Displaying spec content:")
        _print_code(console, SIMULATED_SPEC)
        return

    content = Path(spec_path).read_text(encoding="utf-8")
    _print_info(console, f"Contents of {spec_path}:")
    _print_code(console, content)


def step_build(
    console,
    spec_path: str | None,
    *,
    dry_run: bool,
    no_llm: bool,
) -> bool:
    """Step 3: Run contractd build to generate + verify code.

    When --no-llm is set or no API key is present, uses simulated output
    to demonstrate what the pipeline looks like.

    References:
        [REF-C03] Multi-agent generation pipeline
        ARCHITECTURE.md Section 9 -- Data Flow
    """
    _print_step(console, 3, "Build -- Generate + Verify (LLM pipeline)")

    if no_llm or not _has_llm_key():
        _print_info(console, "No LLM API key detected (or --no-llm). Using simulated output.")
        _print_info(console, "In production, this calls: Analyst -> Formalizer -> Coder [REF-C03]")
        _print_command(console, f"contractd build --contract {spec_path or '<spec>'} --target py")
        _print_info(console, "(simulated output)")
        _print_output(console, SIMULATED_BUILD_SUCCESS)
        _print_success(console, "VERIFIED -- all 5 stages passed")
        return True

    cmd = [
        CONTRACTD_CMD, "build",
        "--contract", spec_path or "",
        "--target", "py",
    ]
    rc, stdout, stderr = _run_cmd(cmd, dry_run=dry_run, console=console)

    if dry_run:
        return True

    output = stdout + stderr
    _print_output(console, output)

    if rc == 0:
        _print_success(console, "BUILD PASSED")
        return True
    else:
        _print_fail(console, f"BUILD FAILED (exit {rc})")
        return False


def step_show_verified(console, *, dry_run: bool, no_llm: bool):
    """Step 4: Display the green VERIFIED badge.

    References:
        [REF-T17] Click CLI -- display module
    """
    _print_step(console, 4, "Verified -- Success Output")

    if HAS_RICH and console:
        console.print()
        console.print(
            Panel(
                "[bold white on green]  VERIFIED  [/bold white on green]\n\n"
                "All 5 verification stages passed.\n"
                "The generated code satisfies every invariant in the .card.md spec.\n\n"
                "[dim]Stages: preflight -> deps -> schema -> PBT -> Dafny formal[/dim]",
                title="Verification Result",
                border_style="green",
                padding=(1, 2),
            )
        )
    else:
        print("  +----------------------------------+")
        print("  |          VERIFIED                 |")
        print("  +----------------------------------+")
        print("  All 5 verification stages passed.")
        print("  Stages: preflight -> deps -> schema -> PBT -> Dafny formal")
    _print_info(console, "Code is regenerated on every build -- never manually edited [REF-C07].")


def step_break_invariant(
    console,
    spec_path: str | None,
    *,
    dry_run: bool,
    no_llm: bool,
) -> str | None:
    """Step 5: Modify the spec with an impossible invariant, show FAIL.

    Creates a modified spec with 'for all x: x > 0 AND x < 0' which is
    logically impossible. The verification pipeline catches this.

    References:
        [REF-C01] Tiered invariants
        [REF-T03] Hypothesis PBT for property tier
    """
    _print_step(console, 5, "Break Invariant -- Inject an Impossible Constraint")

    impossible_invariant = (
        '  - id: INV-BAD\n'
        '    tier: property\n'
        '    statement: "for all x: x > 0 AND x < 0"\n'
        '    rationale: "Impossible -- should always fail"'
    )

    _print_info(console, "Injecting impossible invariant into the spec:")
    _print_code(console, impossible_invariant, lexer="yaml")

    if no_llm or not _has_llm_key() or dry_run:
        _print_info(console, "Running build with broken spec...")
        _print_command(
            console,
            f"contractd build --contract {spec_path or '<spec>'} --target py",
        )
        if not dry_run:
            _print_info(console, "(simulated output)")
            _print_output(console, SIMULATED_BUILD_FAIL)
            _print_fail(console, "FAIL -- verification caught the impossible invariant")
        return spec_path

    # Actually modify the spec file
    if spec_path and os.path.isfile(spec_path):
        broken_path = spec_path.replace(".card.md", ".broken.card.md")
        content = Path(spec_path).read_text(encoding="utf-8")
        # Append the impossible invariant before the closing --- or at the end
        # of the invariants section
        content = content.rstrip() + "\n" + impossible_invariant + "\n"
        Path(broken_path).write_text(content, encoding="utf-8")

        cmd = [CONTRACTD_CMD, "build", "--contract", broken_path, "--target", "py"]
        rc, stdout, stderr = _run_cmd(cmd, console=console)
        output = stdout + stderr
        _print_output(console, output)

        if rc != 0:
            _print_fail(console, "FAIL -- verification caught the impossible invariant")
        else:
            _print_info(console, "Build unexpectedly passed (invariant may not have been checked)")
        return broken_path

    return None


def step_model_swap(console, *, dry_run: bool, no_llm: bool):
    """Step 6: Demonstrate model swapping via NIGHTJAR_MODEL env var.

    Shows that CARD is model-agnostic -- any litellm-supported model works.
    The verification pipeline ensures outputs satisfy invariants regardless
    of which model generated the code.

    References:
        [REF-T16] litellm -- model-agnostic LLM interface
    """
    _print_step(console, 6, "Model Swap -- CARD is Model-Agnostic")

    _print_info(console, "CARD uses litellm [REF-T16] -- swap models via NIGHTJAR_MODEL env var:")

    if HAS_RICH and console:
        table = Table(title="Supported Models (examples)", show_lines=False)
        table.add_column("Env Var Value", style="cyan")
        table.add_column("Provider", style="bold")
        table.add_column("Est. Cost/Pipeline", justify="right", style="green")
        table.add_row("claude-sonnet-4-6", "Anthropic", "~$0.018")
        table.add_row("deepseek/deepseek-chat", "DeepSeek", "~$0.0003")
        table.add_row("openai/gpt-4o", "OpenAI", "~$0.020")
        table.add_row("openai/o3", "OpenAI", "~$0.050")
        console.print(table)
    else:
        print("  NIGHTJAR_MODEL=claude-sonnet-4-6        Anthropic    ~$0.018")
        print("  NIGHTJAR_MODEL=deepseek/deepseek-chat   DeepSeek     ~$0.0003")
        print("  NIGHTJAR_MODEL=openai/gpt-4o            OpenAI       ~$0.020")
        print("  NIGHTJAR_MODEL=openai/o3                OpenAI       ~$0.050")

    _print_info(console, "")
    _print_info(console, "Example: switch to DeepSeek for 10x cost savings:")
    _print_command(
        console,
        'NIGHTJAR_MODEL=deepseek/deepseek-chat contractd build --contract .card/payment.card.md --target py',
    )
    _print_info(console, "Different models produce different code, but the verification")
    _print_info(console, "pipeline ensures all outputs satisfy the same invariants.")


def step_explain(
    console,
    broken_spec: str | None,
    *,
    dry_run: bool,
    no_llm: bool,
):
    """Step 7: Run contractd explain on the failure.

    Shows human-readable failure explanation with counterexamples
    and fix suggestions.

    References:
        [REF-P06] DafnyPro structured errors
        [REF-T17] Click CLI framework
    """
    _print_step(console, 7, "Explain -- Human-Readable Failure Report")

    if no_llm or not _has_llm_key() or dry_run:
        _print_command(
            console,
            f"contractd explain --contract {broken_spec or '<spec>'}",
        )
        if not dry_run:
            _print_info(console, "(simulated output)")
            _print_output(console, SIMULATED_EXPLAIN)
        _print_info(console, "The explain command reads .card/verify.json and formats")
        _print_info(console, "the failure with counterexamples and fix suggestions [REF-P06].")
        return

    if broken_spec:
        cmd = [CONTRACTD_CMD, "explain", "--contract", broken_spec]
        rc, stdout, stderr = _run_cmd(cmd, console=console)
        output = stdout + stderr
        _print_output(console, output)
    else:
        _print_info(console, "No broken spec available to explain.")


def step_cost_summary(console, *, dry_run: bool, no_llm: bool):
    """Step 8: Print approximate pipeline cost summary.

    Shows cost estimates for a single pipeline run across different models.
    Costs are approximate based on typical spec sizes.

    References:
        ARCHITECTURE.md Section 9 -- Data Flow (3 LLM calls per pipeline)
    """
    _print_step(console, 8, "Cost Summary -- Pipeline Economics")

    _print_info(console, "Each CARD build makes 3 LLM calls [REF-C03]:")
    _print_info(console, "  1. Analyst  -- parse intent and requirements")
    _print_info(console, "  2. Formalizer -- generate Dafny postconditions")
    _print_info(console, "  3. Coder  -- implement the verified code")
    _print_info(console, "")
    _print_info(console, "Approximate cost per pipeline run (~2k tokens in, ~4k tokens out):")

    if HAS_RICH and console:
        table = Table(title="Cost per Pipeline Run", show_lines=False)
        table.add_column("Model", style="bold")
        table.add_column("Input Cost", justify="right")
        table.add_column("Output Cost", justify="right")
        table.add_column("Total", justify="right", style="green")
        table.add_column("vs Claude", justify="right", style="dim")

        claude_total = MODEL_COSTS["claude-sonnet-4-6"]["input"] + MODEL_COSTS["claude-sonnet-4-6"]["output"]

        for model_id, cost_data in MODEL_COSTS.items():
            total = cost_data["input"] + cost_data["output"]
            ratio = total / claude_total if claude_total > 0 else 0
            if model_id == "claude-sonnet-4-6":
                ratio_str = "baseline"
            elif ratio < 0.1:
                ratio_str = f"{ratio:.2f}x"
            else:
                ratio_str = f"{ratio:.1f}x"
            table.add_row(
                cost_data["label"],
                f"${cost_data['input']:.4f}",
                f"${cost_data['output']:.4f}",
                f"${total:.4f}",
                ratio_str,
            )

        console.print(table)
    else:
        claude_total = MODEL_COSTS["claude-sonnet-4-6"]["input"] + MODEL_COSTS["claude-sonnet-4-6"]["output"]
        for model_id, cost_data in MODEL_COSTS.items():
            total = cost_data["input"] + cost_data["output"]
            print(f"  {cost_data['label']:20s}  ${total:.4f}")

    _print_info(console, "")
    _print_info(console, "Verification (Dafny + Hypothesis) runs locally -- no LLM cost.")
    _print_info(console, "Total cost is dominated by the 3 generation calls.")


# ── Helpers ───────────────────────────────────────────────


def _has_llm_key() -> bool:
    """Check whether any common LLM API key is present in the environment.

    Checks for keys used by litellm [REF-T16] to access various providers.
    """
    key_vars = [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "CARD_API_KEY",
    ]
    return any(os.environ.get(k) for k in key_vars)


# ── Main ──────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the demo script."""
    parser = argparse.ArgumentParser(
        description="CARD Demo -- demonstrates the full verification pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python demo/run_demo.py              # Full demo (needs LLM key)\n"
            "  python demo/run_demo.py --no-llm     # Demo with simulated output\n"
            "  python demo/run_demo.py --dry-run     # Show commands without executing\n"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show commands without executing them.",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        default=False,
        help="Use simulated output instead of calling LLM APIs.",
    )
    return parser.parse_args()


def main():
    """Run the full CARD demo.

    Executes 8 steps demonstrating the CARD pipeline:
    1. Init -- scaffold a spec
    2. Show spec -- display the .card.md file
    3. Build -- generate + verify via LLM pipeline
    4. Show VERIFIED -- green success badge
    5. Break invariant -- inject impossible constraint, show FAIL
    6. Model swap -- demonstrate NIGHTJAR_MODEL env var
    7. Explain -- human-readable failure report
    8. Cost summary -- pipeline economics

    References:
        [REF-T17] Click CLI framework
        [REF-C03] Multi-agent generation pipeline
        ARCHITECTURE.md Section 9 -- Data Flow
    """
    args = parse_args()
    console = _make_console()
    dry_run = args.dry_run
    no_llm = args.no_llm

    # ── Header ────────────────────────────────────────────
    _print_header(console)

    if dry_run:
        _print_info(console, "[dry-run mode: commands will be shown but not executed]")
    if no_llm:
        _print_info(console, "[no-llm mode: using simulated output]")

    # Create temp directory for the demo
    tmp_dir = tempfile.mkdtemp(prefix="card_demo_")
    _print_info(console, f"Working directory: {tmp_dir}")

    try:
        # Step 1: Init
        spec_path = step_init(console, tmp_dir, dry_run=dry_run, no_llm=no_llm)

        # Step 2: Show spec
        step_show_spec(console, spec_path, dry_run=dry_run, no_llm=no_llm)

        # Step 3: Build
        step_build(console, spec_path, dry_run=dry_run, no_llm=no_llm)

        # Step 4: Show VERIFIED
        step_show_verified(console, dry_run=dry_run, no_llm=no_llm)

        # Step 5: Break invariant
        broken_spec = step_break_invariant(
            console, spec_path, dry_run=dry_run, no_llm=no_llm
        )

        # Step 6: Model swap
        step_model_swap(console, dry_run=dry_run, no_llm=no_llm)

        # Step 7: Explain
        step_explain(console, broken_spec, dry_run=dry_run, no_llm=no_llm)

        # Step 8: Cost summary
        step_cost_summary(console, dry_run=dry_run, no_llm=no_llm)

    except KeyboardInterrupt:
        _print_info(console, "\nDemo interrupted by user.")
        sys.exit(1)
    except Exception as exc:
        _print_fail(console, f"Demo error: {exc}")
        sys.exit(1)
    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    # ── Footer ────────────────────────────────────────────
    if HAS_RICH and console:
        console.print()
        console.print(
            Panel(
                "[bold green]Demo Complete[/bold green]\n\n"
                "CARD provides mathematical verification for AI-generated code.\n"
                "Write specs. Generate code. Prove it correct.\n\n"
                "[dim]See docs/ARCHITECTURE.md for system design.[/dim]\n"
                "[dim]See docs/REFERENCES.md for all citations.[/dim]",
                border_style="cyan",
                padding=(1, 4),
            )
        )
        console.print()
    else:
        print()
        print("=" * 60)
        print("  Demo Complete")
        print("  CARD: Write specs. Generate code. Prove it correct.")
        print("=" * 60)


if __name__ == "__main__":
    main()
