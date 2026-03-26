"""Immune system orchestrator — full closed-loop pipeline.

Wires all immune components together into a single cycle:
    collect → mine → enrich → verify → append → enforce

The ``run_immune_cycle`` function is the primary entry point. Given a function's
source code, an optional error trace, and optional observed invariants (from
Daikon mining), it:

1. **Enriches** raw invariants via LLM [REF-C06]
2. **Verifies** each candidate with CrossHair (symbolic) [REF-T09] and
   Hypothesis (PBT) [REF-T03]
3. **Appends** verified invariants to the .card.md spec [REF-C09]
4. **Generates** icontract-enforced source code [REF-T10]

This closes the immune system loop described in ARCHITECTURE.md Section 6:
production failure → mine invariant → enrich → verify → append to spec →
next build is safer.

References:
- [REF-C09] Immune System / Acquired Immunity
- [REF-C05] Dynamic Invariant Mining (Daikon)
- [REF-P18] Self-Healing Software Systems — biological immune model
- [REF-C06] LLM-Driven Invariant Enrichment
- [REF-T09] CrossHair — symbolic verification
- [REF-T03] Hypothesis — PBT verification
- [REF-T10] icontract — runtime enforcement
"""

from dataclasses import dataclass, field
from typing import Optional

from immune.enricher import (
    CandidateInvariant,
    EnrichmentResult,
    enrich_invariants,
)
from immune.enforcer import InvariantSpec, generate_enforced_source
from immune.spec_updater import append_invariant
from immune.verifier_pbt import PBTResult, PBTVerdict, verify_invariant_pbt
from immune.verifier_symbolic import (
    SymbolicResult,
    SymbolicVerdict,
    verify_invariant_symbolic,
)


@dataclass
class ImmuneCycleConfig:
    """Configuration for an immune cycle run.

    Attributes:
        max_pbt_examples: Number of Hypothesis examples to generate. [REF-T03]
        symbolic_timeout_sec: CrossHair analysis timeout. [REF-T09]
        require_both_verifiers: If True, both CrossHair and Hypothesis must
            pass for a candidate to be verified. If False (default), either
            passing is sufficient.
    """
    max_pbt_examples: int = 1000
    symbolic_timeout_sec: int = 30
    require_both_verifiers: bool = False


@dataclass
class ImmuneCycleResult:
    """Result of a full immune cycle run. [REF-C09]

    Attributes:
        candidates_proposed: Number of candidates from LLM enrichment.
        candidates_verified: Number that passed verification.
        candidates_appended: Number appended to .card.md.
        verified_expressions: The actual verified invariant expressions.
        enforced_source: Source code with icontract decorators (if generated).
        errors: List of non-fatal errors encountered during the cycle.
    """
    candidates_proposed: int = 0
    candidates_verified: int = 0
    candidates_appended: int = 0
    verified_expressions: list[str] = field(default_factory=list)
    enforced_source: str = ""
    errors: list[str] = field(default_factory=list)


def _call_enricher(
    function_signature: str,
    observed_invariants: list[str],
    error_trace: Optional[str] = None,
) -> EnrichmentResult:
    """Wrapper for enrich_invariants (mockable in tests). [REF-C06]"""
    return enrich_invariants(
        function_signature=function_signature,
        observed_invariants=observed_invariants,
        error_trace=error_trace,
    )


def _call_symbolic_verifier(
    func_source: str,
    func_name: str,
    invariant: str,
    preconditions: Optional[list[str]] = None,
    timeout_sec: int = 30,
) -> SymbolicResult:
    """Wrapper for verify_invariant_symbolic (mockable in tests). [REF-T09]"""
    return verify_invariant_symbolic(
        func_source=func_source,
        func_name=func_name,
        invariant=invariant,
        preconditions=preconditions,
        timeout_sec=timeout_sec,
    )


def _call_pbt_verifier(
    func_source: str,
    func_name: str,
    invariant: str,
    preconditions: Optional[list[str]] = None,
    max_examples: int = 1000,
) -> PBTResult:
    """Wrapper for verify_invariant_pbt (mockable in tests). [REF-T03]"""
    return verify_invariant_pbt(
        func_source=func_source,
        func_name=func_name,
        invariant=invariant,
        preconditions=preconditions,
        max_examples=max_examples,
    )


def _is_verified(
    symbolic_result: SymbolicResult,
    pbt_result: PBTResult,
    require_both: bool,
) -> bool:
    """Determine if a candidate passed verification.

    Args:
        symbolic_result: CrossHair symbolic verification result. [REF-T09]
        pbt_result: Hypothesis PBT verification result. [REF-T03]
        require_both: If True, both must pass. If False, either suffices.

    Returns:
        True if the candidate is considered verified.
    """
    sym_ok = symbolic_result.verdict == SymbolicVerdict.VERIFIED
    pbt_ok = pbt_result.verdict == PBTVerdict.PASS

    if require_both:
        return sym_ok and pbt_ok

    # Default: either passing is sufficient
    # But at least one must have actually run successfully
    sym_ran = symbolic_result.verdict != SymbolicVerdict.ERROR
    pbt_ran = pbt_result.verdict != PBTVerdict.ERROR

    if sym_ok or pbt_ok:
        return True

    return False


def _extract_function_signature(func_source: str, func_name: str) -> str:
    """Extract the function signature line from source code."""
    for line in func_source.strip().split("\n"):
        stripped = line.strip()
        if stripped.startswith(f"def {func_name}(") or stripped.startswith(f"def {func_name} ("):
            return stripped.rstrip(":")
    return f"def {func_name}(...)"


def run_immune_cycle(
    function_source: str,
    function_name: str,
    error_trace: Optional[str] = None,
    observed_invariants: Optional[list[str]] = None,
    card_path: Optional[str] = None,
    config: Optional[ImmuneCycleConfig] = None,
) -> ImmuneCycleResult:
    """Run a full immune system cycle for a function.

    This is the main entry point for the immune system. The cycle:
    1. Enriches observed invariants via LLM [REF-C06]
    2. Verifies each candidate with CrossHair [REF-T09] and Hypothesis [REF-T03]
    3. Optionally appends verified invariants to .card.md [REF-C09]
    4. Optionally generates icontract-enforced source [REF-T10]

    Args:
        function_source: Python source code of the function.
        function_name: Name of the function.
        error_trace: Optional error/exception trace from production.
        observed_invariants: Invariants from Daikon mining. [REF-C05]
        card_path: If provided, append verified invariants to this .card.md.
        config: Optional configuration overrides.

    Returns:
        ImmuneCycleResult with counts and verified invariant data.

    References:
        [REF-C09] Immune System — full closed loop
        [REF-P18] Self-Healing Software — biological immune model
    """
    config = config or ImmuneCycleConfig()
    observed = observed_invariants or []
    result = ImmuneCycleResult()

    # Validate inputs
    if not function_source or not function_source.strip():
        result.errors.append("Function source is empty")
        return result

    # Step 1: LLM Enrichment [REF-C06]
    func_sig = _extract_function_signature(function_source, function_name)
    enrichment = _call_enricher(
        function_signature=func_sig,
        observed_invariants=observed,
        error_trace=error_trace,
    )

    if enrichment.error:
        result.errors.append(f"Enrichment failed: {enrichment.error}")
        return result

    result.candidates_proposed = len(enrichment.candidates)

    if not enrichment.candidates:
        return result

    # Step 2: Verify each candidate [REF-T09, REF-T03]
    verified_candidates: list[CandidateInvariant] = []

    for candidate in enrichment.candidates:
        # Run both verifiers
        sym_result = _call_symbolic_verifier(
            func_source=function_source,
            func_name=function_name,
            invariant=candidate.expression,
            timeout_sec=config.symbolic_timeout_sec,
        )

        pbt_result = _call_pbt_verifier(
            func_source=function_source,
            func_name=function_name,
            invariant=candidate.expression,
            max_examples=config.max_pbt_examples,
        )

        if _is_verified(sym_result, pbt_result, config.require_both_verifiers):
            verified_candidates.append(candidate)
            result.verified_expressions.append(candidate.expression)

    result.candidates_verified = len(verified_candidates)

    # Step 3: Append to .card.md if path provided [REF-C09]
    if card_path and verified_candidates:
        for candidate in verified_candidates:
            verification_method = "crosshair+hypothesis"
            update_result = append_invariant(
                card_path=card_path,
                expression=candidate.expression,
                explanation=candidate.explanation,
                verification_method=verification_method,
            )
            if update_result.success:
                result.candidates_appended += 1
            else:
                result.errors.append(
                    f"Failed to append '{candidate.expression}': {update_result.error}"
                )

    # Step 4: Generate enforced source [REF-T10]
    if verified_candidates:
        specs = [
            InvariantSpec(
                expression=c.expression,
                explanation=c.explanation,
            )
            for c in verified_candidates
        ]
        result.enforced_source = generate_enforced_source(
            func_source=function_source,
            func_name=function_name,
            invariants=specs,
        )

    return result
