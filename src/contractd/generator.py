"""Code generation pipeline — Analyst → Formalizer → Coder.

Architecture: [REF-C03] Three-agent pipeline from [REF-P07] ReDeFo (NTU Singapore).
Intermediate language: [REF-C04] Dafny as IL from [REF-P12] Amazon AWS.
LLM interface: [REF-T16] litellm for model-agnostic calls.

Pipeline stages:
  1. Analyst: reads intent + acceptance criteria → structured requirements analysis
  2. Formalizer: reads analysis + contract + invariants → Dafny module with specs
  3. Coder: reads Dafny skeleton → complete Dafny implementation

All LLM calls use litellm.completion(). Model selected via CARD_MODEL env var.

BEFORE MODIFYING: Read docs/ARCHITECTURE.md Section 5 and docs/REFERENCES.md
entries [REF-C03], [REF-P07], [REF-C04], [REF-P12], [REF-T16].
"""

import os
from dataclasses import dataclass, field

import litellm

from .types import CardSpec


# -- Constants --

DEFAULT_MODEL = "claude-sonnet-4-6"
# Low temperature for deterministic code generation, per [REF-P06] DafnyPro
GENERATION_TEMPERATURE = 0.2
MAX_TOKENS = 4096


# -- Result type --


@dataclass
class GenerationResult:
    """Result from the full generation pipeline.

    Contains outputs from all three stages plus the final Dafny code.
    """
    dafny_code: str
    analyst_output: str
    formalizer_output: str
    model_used: str = ""
    spec_id: str = ""


# -- Model selection --


def get_model(override: str | None = None) -> str:
    """Get the LLM model to use for generation.

    Priority: explicit override > CARD_MODEL env var > default.
    All models go through litellm [REF-T16] for provider-agnosticism.

    Args:
        override: Explicit model name, takes highest priority.

    Returns:
        Model identifier string compatible with litellm.
    """
    if override:
        return override
    return os.environ.get("CARD_MODEL", DEFAULT_MODEL)


# -- Prompt builders --


def _build_spec_context(spec: CardSpec) -> str:
    """Build a text summary of the CardSpec for LLM prompts.

    Extracts the key information from the spec that all pipeline
    stages need: module boundary, contract, invariants, intent.
    """
    lines = [
        f"Module: {spec.id} — {spec.title}",
        f"Status: {spec.status}",
        "",
        "## Module Boundary",
        f"Owns: {', '.join(spec.module.owns)}",
    ]
    if spec.module.depends_on:
        deps = ", ".join(f"{k}: {v}" for k, v in spec.module.depends_on.items())
        lines.append(f"Depends on: {deps}")
    if spec.module.excludes:
        lines.append(f"Excludes: {', '.join(spec.module.excludes)}")

    lines.append("")
    lines.append("## Contract")
    lines.append("### Inputs")
    for inp in spec.contract.inputs:
        constraint_str = f" (constraints: {inp.constraints})" if inp.constraints else ""
        lines.append(f"- {inp.name}: {inp.type}{constraint_str}")
    lines.append("### Outputs")
    for out in spec.contract.outputs:
        lines.append(f"- {out.name}: {out.type}")
    if spec.contract.errors:
        lines.append(f"### Errors: {', '.join(spec.contract.errors)}")

    lines.append("")
    lines.append("## Invariants")
    for inv in spec.invariants:
        lines.append(f"- [{inv.id}] (tier: {inv.tier.value}): {inv.statement}")
        if inv.rationale:
            lines.append(f"  Rationale: {inv.rationale}")

    if spec.constraints:
        lines.append("")
        lines.append("## Constraints")
        for k, v in spec.constraints.items():
            lines.append(f"- {k}: {v}")

    return "\n".join(lines)


# -- Pipeline stages --


def run_analyst(spec: CardSpec, model: str | None = None) -> str:
    """Run the Analyst agent — LLM call 1 of 3.

    The Analyst reads the spec's intent, acceptance criteria, and edge cases,
    then produces a structured requirements analysis.

    Architecture: [REF-C03] Analyst stage from [REF-P07] ReDeFo.

    Args:
        spec: Parsed .card.md specification.
        model: Optional model override.

    Returns:
        Structured requirements analysis text.

    Raises:
        ValueError: If LLM returns empty content.
    """
    resolved_model = get_model(model)
    spec_context = _build_spec_context(spec)

    system_prompt = (
        "You are a requirements analyst for the CARD verification system. "
        "Your role is to analyze a module specification and produce a structured "
        "requirements analysis that identifies:\n"
        "1. Core functional requirements\n"
        "2. Input/output contracts and their constraints\n"
        "3. Edge cases and error conditions\n"
        "4. Invariants that must be preserved\n"
        "5. Dependencies and their implications\n\n"
        "Be thorough and precise. Your analysis feeds into formal specification generation."
    )

    user_prompt = (
        f"Analyze the following module specification and produce a structured "
        f"requirements analysis.\n\n"
        f"# Specification\n\n{spec_context}\n\n"
    )
    if spec.intent:
        user_prompt += f"## Intent\n{spec.intent}\n\n"
    if spec.acceptance_criteria:
        user_prompt += f"## Acceptance Criteria\n{spec.acceptance_criteria}\n\n"
    if spec.functional_requirements:
        user_prompt += f"## Functional Requirements\n{spec.functional_requirements}\n\n"

    response = litellm.completion(
        model=resolved_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=GENERATION_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError(
            f"Analyst returned empty content for spec '{spec.id}'. "
            "Check model availability and API key configuration."
        )
    return content


def run_formalizer(spec: CardSpec, analyst_output: str, model: str | None = None) -> str:
    """Run the Formalizer agent — LLM call 2 of 3.

    The Formalizer reads the analyst's output plus the contract and invariants,
    then generates a Dafny module skeleton with requires/ensures/invariants.

    Architecture: [REF-C03] Formalizer stage from [REF-P07] ReDeFo.
    Output format: [REF-C04] Dafny as intermediate language from [REF-P12].

    Args:
        spec: Parsed .card.md specification.
        analyst_output: Text output from the Analyst stage.
        model: Optional model override.

    Returns:
        Dafny module skeleton with formal specifications.

    Raises:
        ValueError: If LLM returns empty content.
    """
    resolved_model = get_model(model)
    spec_context = _build_spec_context(spec)

    system_prompt = (
        "You are a formal methods engineer for the CARD verification system. "
        "Your role is to translate requirements into a Dafny module with formal "
        "specifications. You MUST:\n"
        "1. Define method signatures matching the contract inputs/outputs\n"
        "2. Add 'requires' clauses for preconditions from contract constraints\n"
        "3. Add 'ensures' clauses for postconditions from invariants\n"
        "4. Add loop invariants where needed\n"
        "5. Add data type definitions for complex outputs\n\n"
        "Output ONLY valid Dafny code. The Coder agent will fill in implementations."
    )

    user_prompt = (
        f"Based on the following specification and requirements analysis, "
        f"generate a Dafny module skeleton with formal specifications "
        f"(requires/ensures/invariants).\n\n"
        f"# Specification\n\n{spec_context}\n\n"
        f"# Requirements Analysis\n\n{analyst_output}\n\n"
        f"Generate the Dafny module for '{spec.id}' with complete formal annotations."
    )

    response = litellm.completion(
        model=resolved_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=GENERATION_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError(
            f"Formalizer returned empty content for spec '{spec.id}'. "
            "Check model availability and API key configuration."
        )
    return content


def run_coder(spec: CardSpec, formalizer_output: str, model: str | None = None) -> str:
    """Run the Coder agent — LLM call 3 of 3.

    The Coder reads the Dafny skeleton from the Formalizer and produces
    a complete Dafny implementation that satisfies all specifications.

    Architecture: [REF-C03] Coder stage from [REF-P07] ReDeFo.
    Target: [REF-C04] Complete Dafny program from [REF-P12].

    Args:
        spec: Parsed .card.md specification.
        formalizer_output: Dafny skeleton from the Formalizer stage.
        model: Optional model override.

    Returns:
        Complete Dafny implementation ready for verification.

    Raises:
        ValueError: If LLM returns empty content.
    """
    resolved_model = get_model(model)
    spec_context = _build_spec_context(spec)

    system_prompt = (
        "You are a Dafny programmer for the CARD verification system. "
        "Your role is to complete a Dafny module implementation so that it "
        "satisfies ALL formal specifications (requires/ensures/invariants). "
        "You MUST:\n"
        "1. Implement all method bodies\n"
        "2. Ensure all 'ensures' postconditions are provably satisfied\n"
        "3. Maintain all loop invariants\n"
        "4. Handle all error cases specified in the contract\n"
        "5. Do NOT modify the formal specifications — only add implementations\n\n"
        "Output ONLY valid, complete Dafny code ready for 'dafny verify'."
    )

    user_prompt = (
        f"Complete the following Dafny module implementation so that all "
        f"formal specifications are satisfied.\n\n"
        f"# Original Specification\n\n{spec_context}\n\n"
        f"# Dafny Skeleton (with formal specs)\n\n{formalizer_output}\n\n"
        f"Provide the complete Dafny implementation for '{spec.id}'."
    )

    response = litellm.completion(
        model=resolved_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=GENERATION_TEMPERATURE,
        max_tokens=MAX_TOKENS,
    )

    content = response.choices[0].message.content
    if not content or not content.strip():
        raise ValueError(
            f"Coder returned empty content for spec '{spec.id}'. "
            "Check model availability and API key configuration."
        )
    return content


# -- Full pipeline --


def generate_code(spec: CardSpec, model: str | None = None) -> GenerationResult:
    """Run the full Analyst → Formalizer → Coder generation pipeline.

    This is the main entry point for code generation. It executes three
    sequential LLM calls following the ReDeFo architecture [REF-C03, REF-P07]:

    1. Analyst: analyzes spec → structured requirements
    2. Formalizer: requirements + contract → Dafny skeleton with specs
    3. Coder: Dafny skeleton → complete verified implementation

    All LLM calls go through litellm [REF-T16] for model-agnosticism.
    The generated Dafny code is ready for the verification pipeline.

    Args:
        spec: Parsed .card.md specification.
        model: Optional model override. If None, uses CARD_MODEL env var
               or falls back to default model.

    Returns:
        GenerationResult with Dafny code and intermediate outputs.

    Raises:
        TypeError: If spec is not a CardSpec instance.
        ValueError: If any LLM call returns empty content.
    """
    if not isinstance(spec, CardSpec):
        raise TypeError(
            f"Expected CardSpec, got {type(spec).__name__}. "
            "Parse a .card.md file first using contractd.parser.parse_card_spec()."
        )

    resolved_model = get_model(model)

    # Stage 1: Analyst [REF-C03]
    analyst_output = run_analyst(spec, model=resolved_model)

    # Stage 2: Formalizer [REF-C03]
    formalizer_output = run_formalizer(spec, analyst_output, model=resolved_model)

    # Stage 3: Coder [REF-C03]
    dafny_code = run_coder(spec, formalizer_output, model=resolved_model)

    return GenerationResult(
        dafny_code=dafny_code,
        analyst_output=analyst_output,
        formalizer_output=formalizer_output,
        model_used=resolved_model,
        spec_id=spec.id,
    )
