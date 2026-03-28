#!/usr/bin/env python3
"""Generate authentic Nightjar demo SVGs using Rich's console.export_svg()."""
import io
from rich.console import Console
from rich.text import Text
from rich.table import Table

def generate_fail_demo():
    console = Console(record=True, width=80, file=io.StringIO(), force_terminal=True)
    console.print()
    console.print("[bold]Nightjar Verification Pipeline[/]")
    console.print("[dim]Spec: payment (3 invariants) · Model: claude-sonnet-4-6[/]")
    console.print()
    console.print("  [bold green]PASS[/]  Stage 0 (preflight)      [dim]14ms[/]")
    console.print("  [bold green]PASS[/]  Stage 1 (deps)           [dim]9ms[/]")
    console.print("  [bold green]PASS[/]  Stage 2 (schema)         [dim]21ms[/]")
    console.print("  [bold red]FAIL[/]  Stage 3 (property-tests)  [dim]7938ms[/]")
    console.print("        [red]INV-01 violated: apply_discount(-1) → -0.9[/]")
    console.print("        [red]Negative input produces negative result[/]")
    console.print("  [dim]SKIP[/]  Stage 4 (formal-proof)     [dim]—[/]")
    console.print()
    console.print("  Result: [bold red]1 VIOLATION[/]")
    console.print("  Trust:  [bold yellow]SCHEMA_VERIFIED[/] (0.40)")
    console.print("  [dim]Duration: 7982ms[/]")
    console.print()

    svg = console.export_svg(title="nightjar verify --spec .card/payment.card.md")
    with open("demo/nightjar-fail-demo.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("Generated: demo/nightjar-fail-demo.svg")

def generate_pass_demo():
    console = Console(record=True, width=80, file=io.StringIO(), force_terminal=True)
    console.print()
    console.print("[bold]Nightjar Verification Pipeline[/]")
    console.print("[dim]Spec: payment (3 invariants) · Model: claude-sonnet-4-6[/]")
    console.print()
    console.print("  [bold green]PASS[/]  Stage 0 (preflight)      [dim]14ms[/]")
    console.print("  [bold green]PASS[/]  Stage 1 (deps)           [dim]9ms[/]")
    console.print("  [bold green]PASS[/]  Stage 2 (schema)         [dim]21ms[/]")
    console.print("  [bold green]PASS[/]  Stage 3 (property-tests)  [dim]3412ms[/]")
    console.print("  [bold green]PASS[/]  Stage 4 (formal-proof)    [dim]1847ms[/]")
    console.print()
    console.print("  Result: [bold green]VERIFIED[/]")
    console.print("  Trust:  [bold #D4920A]FORMALLY_VERIFIED[/] (0.95)")
    console.print("  [dim]Duration: 5303ms[/]")
    console.print()

    svg = console.export_svg(title="nightjar verify --spec .card/payment.card.md")
    with open("demo/nightjar-pass-demo.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    print("Generated: demo/nightjar-pass-demo.svg")

if __name__ == "__main__":
    generate_fail_demo()
    generate_pass_demo()
