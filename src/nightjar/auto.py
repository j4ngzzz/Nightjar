"""nightjar auto — zero-friction invariant generation from NL intent.

Implements the 8-step pipeline from Task W2.1 (Scout 4 F9 synthesis):

  1. parse_nl_intent  — NL string → NLIntent (ContextCov path-aware slicing, CR-02)
  2. _generate_candidates — LLM → invariant candidates (NL2Contract, CR-03)
  3. classify_invariant    — route each candidate to a domain
  4. generate_icontract/hypothesis/dafny — domain generators
  5. rank_candidates       — HiLDe-inspired ranking → top 5-10
  6. format_invariant      — "For any X where Y, Z holds" (Kiro UX)
  7. _run_approval_loop    — Y/n/modify per invariant (30s timeout)
  8. _write_card_md        — write .card.md with approved invariants

Usage:
    from nightjar.auto import run_auto
    result = run_auto(
        nl_intent="Build a payment processor that charges credit cards",
        output_path=".card/payment.card.md",
        model="claude-sonnet-4-6",
        yes=False,  # interactive approval
    )

CLI stub (src/nightjar/cli.py wiring by Coord-Integration, Phase 3):
    nightjar auto "Build a payment processor" --output .card/payment.card.md

References:
- CR-02: ContextCov | CC-BY-4.0 | arxiv 2603.00822
- CR-03: NL2Contract | Research paper | arxiv 2510.12702
- [REF-T10] icontract, [REF-T03] Hypothesis, [REF-T01] Dafny
- [REF-T16] litellm unified LLM API
- [REF-T17] Click CLI framework
- Scout 4 F9: 8-step pipeline synthesis
- Scout 4 honest assessment: FORMAL tier optional only

Clean-room: CR-02 (CC-BY-4.0), CR-03 (research paper).
No code copied from ContextCov or NL2Contract repositories.
"""

import json
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import click
import litellm

from nightjar.intent_router import (
    NLIntent,
    InvariantClass,
    parse_nl_intent,
    classify_invariant,
)
from nightjar.invariant_generators import (
    InvariantCandidate,
    RankedInvariant,
    ApprovedInvariant,
    rank_candidates,
    format_invariant,
)
from nightjar.invariant_generators.icontract_gen import generate_icontract
from nightjar.invariant_generators.hypothesis_gen import generate_hypothesis
from nightjar.invariant_generators.dafny_gen import generate_dafny


# ── Constants ─────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "claude-sonnet-4-6"
_GENERATION_TEMPERATURE = 0.2
_CANDIDATE_MAX_TOKENS = 1024
_APPROVAL_TIMEOUT_SECONDS = 30


# ── Types ─────────────────────────────────────────────────────────────────────


@dataclass
class AutoResult:
    """Result from the nightjar auto pipeline."""

    card_path: Path
    """Path to the written .card.md file."""

    approved_count: int
    """Number of invariants the user accepted (including modifications)."""

    skipped_count: int
    """Number of invariants the user rejected."""


# ── Model selection ───────────────────────────────────────────────────────────


def _get_model(override: Optional[str]) -> str:
    """Resolve model. Priority: override > NIGHTJAR_MODEL env > DEFAULT.

    All LLM calls go through litellm [REF-T16] for provider-agnosticism.
    """
    if override:
        return override
    return os.environ.get("NIGHTJAR_MODEL", DEFAULT_MODEL)


# ── Public API ────────────────────────────────────────────────────────────────


def run_auto(
    nl_intent: str,
    output_path: str,
    model: Optional[str] = None,
    yes: bool = False,
) -> AutoResult:
    """Run the nightjar auto 8-step pipeline.

    Generates invariants from a natural language intent, presents them
    for approval, and writes a .card.md spec file.

    Args:
        nl_intent: Natural language description of the component.
            Example: "Build a payment processor that charges credit cards"
        output_path: Where to write the .card.md file.
        model: litellm model override (default: NIGHTJAR_MODEL env or claude-sonnet-4-6).
        yes: If True, auto-approve all ranked invariants (non-interactive).
            Use for automation/CI. Default: False (interactive).

    Returns:
        AutoResult with path to the written .card.md and approval counts.

    Raises:
        ValueError: If nl_intent is empty or whitespace-only.

    References:
        Scout 4 F9: 8-step pipeline synthesis
        CR-02: ContextCov (CC-BY-4.0, arxiv 2603.00822)
        CR-03: NL2Contract (arxiv 2510.12702)
    """
    # ── Step 1: Parse NL intent (ContextCov path-aware slicing, CR-02) ──
    intent = parse_nl_intent(nl_intent)  # Raises ValueError if empty

    resolved_model = _get_model(model)

    # ── Step 2: LLM refinement → invariant candidates (NL2Contract, CR-03) ──
    raw_candidates = _generate_candidates(intent, resolved_model)

    # ── Step 3: Classify each candidate via intent router ──
    classified = [
        InvariantCandidate(
            statement=c["statement"],
            confidence=float(c.get("confidence", 0.5)),
            inv_class=classify_invariant(c["statement"]),
        )
        for c in raw_candidates
        if c.get("statement", "").strip()
    ]

    # ── Step 5: HiLDe-inspired ranking → top 5-10 ──
    ranked = rank_candidates(classified)

    # ── Steps 6 + 7: Format + approval loop ──
    approved = _run_approval_loop(ranked, yes=yes)

    # ── Step 4 (for approved): Generate domain-specific code ──
    approved_with_code = _generate_code_for_approved(approved, resolved_model)

    # ── Step 8: Write .card.md ──
    card_path = _write_card_md(approved_with_code, output_path, intent)

    return AutoResult(
        card_path=card_path,
        approved_count=len(approved_with_code),
        skipped_count=len(ranked) - len(approved_with_code),
    )


# ── Step 2: LLM candidate generation ─────────────────────────────────────────

_CANDIDATE_SYSTEM_PROMPT = """\
You are an expert in formal verification and software contracts.
Given a natural language description of a software component, generate
invariant candidates covering:
  1. PRECONDITIONS (what must be true of inputs)
  2. POSTCONDITIONS (what must be true of outputs)
  3. STATE INVARIANTS (always true regardless of inputs)

Format: Return a JSON array of objects with these fields:
  - "type": one of "behavioral", "numerical", "state", "formal"
  - "statement": natural language invariant (specific, not vague)
  - "confidence": float 0.0-1.0 (how likely this invariant is correct)

Rules:
  - Be SPECIFIC not generic. Avoid: "input must be valid", "output must be correct"
  - Prefer: "amount must be greater than zero", "returns non-null receipt"
  - Generate 10-15 candidates covering different aspects
  - For numerical inputs, always include bounds invariants
  - For outputs, always include nullness/emptiness invariants
  - confidence >= 0.8 for obvious invariants, lower for speculative ones

Return ONLY the JSON array, no other text.
"""


def _generate_candidates(intent: NLIntent, model: str) -> list[dict]:
    """Generate invariant candidates via LLM (NL2Contract, CR-03).

    Step 2 of the pipeline: NL → structured invariant candidates.
    Uses litellm for provider-agnostic LLM calls [REF-T16].

    Args:
        intent: Parsed NLIntent from Step 1.
        model: litellm model identifier.

    Returns:
        List of dicts with 'statement', 'confidence', 'type' keys.
        Returns empty list on LLM failure (graceful degradation).
    """
    user_prompt = (
        f"Component: {intent.subject}\n"
        f"Full intent: {intent.raw}\n"
    )
    if intent.inferred_inputs:
        user_prompt += f"Inferred inputs: {', '.join(intent.inferred_inputs)}\n"
    if intent.inferred_outputs:
        user_prompt += f"Inferred outputs: {', '.join(intent.inferred_outputs)}\n"
    if intent.behaviors:
        user_prompt += f"Behavioral context: {', '.join(intent.behaviors)}\n"
    user_prompt += "\nGenerate invariant candidates as JSON array."

    try:
        response = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": _CANDIDATE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=_GENERATION_TEMPERATURE,
            max_tokens=_CANDIDATE_MAX_TOKENS,
        )
        raw = response.choices[0].message.content.strip()
    except Exception as e:
        click.echo(
            f"Warning: LLM candidate generation failed ({e}). "
            "Returning empty candidate list.",
            err=True,
        )
        return []

    return _parse_candidates_json(raw)


def _parse_candidates_json(raw: str) -> list[dict]:
    """Parse LLM JSON output into candidate list. Gracefully handles errors."""
    # Unwrap markdown code block if present
    code_block = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if code_block:
        raw = code_block.group(1).strip()

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [c for c in parsed if isinstance(c, dict) and "statement" in c]
        return []
    except (json.JSONDecodeError, ValueError):
        return []


# ── Step 7: Approval loop ─────────────────────────────────────────────────────


def _run_approval_loop(
    ranked: list[RankedInvariant],
    yes: bool,
) -> list[ApprovedInvariant]:
    """Present ranked invariants for Y/n/modify approval (Step 7).

    Kiro UX pattern: show each invariant in "For any X where Y, Z holds"
    format. User can:
      y       — accept as-is
      n       — reject (skip)
      m       — modify the text, then accept modified version

    With yes=True (--yes flag): auto-accept all ranked invariants.

    Each prompt has a 30-second timeout; defaults to 'y' on timeout
    (the auto pipeline is opt-in, so accepting is the friendly default).

    Args:
        ranked: HiLDe-ranked invariants to present for approval.
        yes: Auto-accept all if True.

    Returns:
        List of ApprovedInvariant (accepted or modified, not rejected).
    """
    approved = []

    for i, ranked_inv in enumerate(ranked, 1):
        candidate = ranked_inv.candidate
        formatted = ranked_inv.formatted

        if yes:
            # Non-interactive: auto-accept all
            approved.append(
                ApprovedInvariant(
                    statement=candidate.statement,
                    inv_class=candidate.inv_class,
                )
            )
            continue

        # Interactive: show invariant and prompt
        click.echo(f"\n[{i}/{len(ranked)}] {formatted}")
        click.echo(f"  Type: {candidate.inv_class.value}  |  Confidence: {candidate.confidence:.0%}")

        choice = _prompt_with_timeout(
            prompt="Accept? [y/n/m=modify]",
            default="y",
            timeout=_APPROVAL_TIMEOUT_SECONDS,
        )

        if choice.lower() == "n":
            continue
        elif choice.lower() == "m":
            modified = click.prompt("  Enter modified statement", default=candidate.statement)
            approved.append(
                ApprovedInvariant(
                    statement=modified.strip() or candidate.statement,
                    inv_class=candidate.inv_class,
                )
            )
        else:
            # 'y' or timeout default
            approved.append(
                ApprovedInvariant(
                    statement=candidate.statement,
                    inv_class=candidate.inv_class,
                )
            )

    return approved


def _prompt_with_timeout(prompt: str, default: str, timeout: int) -> str:
    """Prompt the user with a timeout. Returns default on expiry.

    Uses a background thread to implement the timeout. The default
    is returned if the user doesn't respond within `timeout` seconds.

    Args:
        prompt: Prompt text to display.
        default: Default value to return on timeout.
        timeout: Seconds before timeout.

    Returns:
        User input or default on timeout.
    """
    result: list[str] = []
    timed_out: list[bool] = [False]

    def _get_input() -> None:
        try:
            value = click.prompt(f"  {prompt} (timeout {timeout}s)", default=default)
            result.append(value)
        except Exception:
            result.append(default)

    thread = threading.Thread(target=_get_input, daemon=True)

    def _on_timeout() -> None:
        timed_out[0] = True
        click.echo(f"\n  (timeout — auto-accepting)")

    timer = threading.Timer(timeout, _on_timeout)
    timer.start()
    thread.start()
    thread.join(timeout + 1)
    timer.cancel()

    if timed_out[0] or not result:
        return default
    return result[0]


# ── Step 4: Generate code for approved invariants ─────────────────────────────


def _generate_code_for_approved(
    approved: list[ApprovedInvariant],
    model: str,
) -> list[ApprovedInvariant]:
    """Generate icontract, Hypothesis, and Dafny code for each approved invariant.

    Step 4 of the pipeline (executed after approval to avoid generating
    code for rejected invariants).

    Args:
        approved: User-approved invariants (may have modified statements).
        model: litellm model identifier.

    Returns:
        ApprovedInvariant list with code fields populated.
    """
    enriched = []
    for inv in approved:
        # Rebuild candidate from approved (possibly modified) statement
        candidate = InvariantCandidate(
            statement=inv.statement,
            confidence=1.0,  # User-approved — max confidence
            inv_class=inv.inv_class,
        )

        icontract_code = generate_icontract(candidate, model=model)
        hypothesis_code = generate_hypothesis(candidate, model=model)
        dafny_code = generate_dafny(candidate, model=model)  # always optional

        enriched.append(
            ApprovedInvariant(
                statement=inv.statement,
                inv_class=inv.inv_class,
                icontract_code=icontract_code,
                hypothesis_code=hypothesis_code,
                dafny_code=dafny_code,
            )
        )

    return enriched


# ── Step 8: Write .card.md ────────────────────────────────────────────────────

_CARD_TEMPLATE = """\
---
card-version: "1.0"
id: {module_id}
title: {title}
status: draft
generated-by: nightjar-auto
source-intent: "{raw_intent}"
module:
  owns: []
  depends-on: {{}}
contract:
  inputs: []
  outputs: []
invariants:
{invariants_yaml}
---

## Intent

{raw_intent}

## Generated Invariants

The following invariants were auto-generated by `nightjar auto` from the
natural language intent above. All invariants were reviewed and approved
by a human.

{invariant_list}

## Acceptance Criteria

<!-- Auto-generated from intent. Please review and refine. -->

### Story 1 — {title} (P1)

**As a** developer, **I want** {subject}, **so that** my code is verified.

1. **Given** valid inputs, **When** the operation is called, **Then** all invariants hold.

## Functional Requirements

<!-- TODO: Add specific functional requirements -->

- **FR-001**: System MUST satisfy all invariants listed above.
"""

_INVARIANT_YAML_ENTRY = """\
  - id: {inv_id}
    tier: {tier}
    statement: "{statement}"
    rationale: "Auto-generated by nightjar auto — human-approved"
    icontract: |
      {icontract_indented}"""

_INVARIANT_YAML_ENTRY_WITH_DAFNY = """\
  - id: {inv_id}
    tier: {tier}
    statement: "{statement}"
    rationale: "Auto-generated by nightjar auto — human-approved"
    icontract: |
      {icontract_indented}
    dafny-optional: |
      {dafny_indented}"""


def _write_card_md(
    approved: list[ApprovedInvariant],
    output_path: str,
    intent: NLIntent,
) -> Path:
    """Write approved invariants to a .card.md spec file (Step 8).

    Generates a .card.md with YAML frontmatter (machine-readable) and
    Markdown body (human-readable), following [REF-T24] Agent Skills
    Open Standard format.

    Args:
        approved: List of approved invariants with generated code.
        output_path: Where to write the .card.md file.
        intent: Parsed NLIntent for metadata.

    Returns:
        Path to the written .card.md file.

    References:
        [REF-T24] Agent Skills Open Standard: YAML frontmatter + MD body
        [REF-T25] GitHub Spec Kit: Given/When/Then format
    """
    # Derive module ID and title from subject
    module_id = re.sub(r"\s+", "-", intent.subject.lower())
    module_id = re.sub(r"[^\w-]", "", module_id)[:40]
    title = intent.subject.title()

    # Build YAML invariants block
    yaml_entries = []
    for i, inv in enumerate(approved, 1):
        inv_id = f"INV-{i:03d}"
        tier = _map_tier(inv.inv_class)
        statement = inv.statement.replace('"', '\\"')
        icontract_indented = _indent(inv.icontract_code, prefix="      ")

        if inv.dafny_code.strip():
            dafny_indented = _indent(inv.dafny_code, prefix="      ")
            entry = _INVARIANT_YAML_ENTRY_WITH_DAFNY.format(
                inv_id=inv_id,
                tier=tier,
                statement=statement,
                icontract_indented=icontract_indented,
                dafny_indented=dafny_indented,
            )
        else:
            entry = _INVARIANT_YAML_ENTRY.format(
                inv_id=inv_id,
                tier=tier,
                statement=statement,
                icontract_indented=icontract_indented,
            )
        yaml_entries.append(entry)

    invariants_yaml = "\n".join(yaml_entries) if yaml_entries else "  []"

    # Build Markdown invariant list for the body
    md_lines = []
    for i, inv in enumerate(approved, 1):
        md_lines.append(f"### INV-{i:03d} [{inv.inv_class.value}]")
        md_lines.append(f"**{inv.statement}**")
        md_lines.append("")
        if inv.icontract_code:
            md_lines.append("```python")
            md_lines.append(inv.icontract_code)
            md_lines.append("```")
            md_lines.append("")
        if inv.hypothesis_code:
            md_lines.append("```python")
            md_lines.append(inv.hypothesis_code)
            md_lines.append("```")
            md_lines.append("")

    invariant_list = "\n".join(md_lines) if md_lines else "_No invariants approved._"

    # Fill in the template
    content = _CARD_TEMPLATE.format(
        module_id=module_id or "auto-generated",
        title=title,
        raw_intent=intent.raw.replace('"', '\\"'),
        subject=intent.subject,
        invariants_yaml=invariants_yaml,
        invariant_list=invariant_list,
    )

    # Write the file
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")

    return out_path


def _map_tier(inv_class: InvariantClass) -> str:
    """Map InvariantClass to .card.md tier value [REF-C01]."""
    if inv_class == InvariantClass.FORMAL:
        return "formal"
    if inv_class == InvariantClass.NUMERICAL:
        return "property"
    if inv_class == InvariantClass.STATE:
        return "property"
    return "property"  # BEHAVIORAL → property (Hypothesis testable)


def _indent(text: str, prefix: str = "  ") -> str:
    """Indent multiline text with the given prefix."""
    if not text:
        return ""
    lines = text.split("\n")
    # First line has no extra indent (already at the key: | position)
    result = [lines[0]]
    for line in lines[1:]:
        result.append(f"{prefix}{line}" if line.strip() else "")
    return "\n".join(result)
