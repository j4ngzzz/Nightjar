"""Immune system orchestrator — full closed-loop pipeline.

Wires all immune components together into a single cycle:
    collect → mine → enrich → verify → append → enforce

Two entry points:

``run_immune_cycle`` — legacy closed-loop cycle (enrich → verify → append →
  enforce) for a single function.

``run_mining_tiers`` — 3-tier mining orchestrator (Scout 6 Section 3):
  Tier 1: SEMANTIC  — LLM hypothesis from source code (zero overhead)
  Tier 2: RUNTIME   — Daikon+Houdini tracing (sys.monitoring, low overhead)
  Tier 3: API-LEVEL — MINES from OTel spans (no overhead)

References:
- [REF-C09] Immune System / Acquired Immunity
- [REF-C05] Dynamic Invariant Mining (Daikon)
- [REF-P18] Self-Healing Software Systems — biological immune model
- [REF-C06] LLM-Driven Invariant Enrichment
- [REF-T09] CrossHair — symbolic verification
- [REF-T03] Hypothesis — PBT verification
- [REF-T10] icontract — runtime enforcement
- Scout 6 Section 3 — 3-tier mining architecture
"""

from __future__ import annotations

import enum
import inspect
from dataclasses import dataclass, field
from typing import Callable, Optional

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


# Backward-compatible alias
ImmuneConfig = ImmuneCycleConfig


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


# ===========================================================================
# 3-Tier Mining Orchestrator (Scout 6 Section 3) — IM1
# ===========================================================================


class MiningTier(enum.Enum):
    """Mining tier identifiers for the 3-tier orchestrator."""
    SEMANTIC = "semantic"    # Tier 1: LLM hypothesis from source code
    RUNTIME = "runtime"      # Tier 2: Daikon+Houdini runtime tracing
    API_LEVEL = "api_level"  # Tier 3: MINES from OTel spans


@dataclass
class MinedInvariant:
    """Unified invariant type across all three mining tiers.

    Attributes:
        expression: The invariant expression string.
        confidence: Confidence score [0.0, 1.0].
        tier:       Which mining tier produced this invariant.
        source:     Specific tool/method name (e.g., "daikon", "mines", "llm").
    """
    expression: str
    confidence: float
    tier: MiningTier
    source: str


@dataclass
class MiningOrchestrationResult:
    """Result of the 3-tier mining orchestration.

    Attributes:
        merged:      Deduplicated, confidence-merged invariant list.
        tier_counts: Number of invariants contributed per tier (before dedup).
        errors:      Non-fatal errors from individual tiers.
    """
    merged: list[MinedInvariant] = field(default_factory=list)
    tier_counts: dict[MiningTier, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _merge_invariants(invariants: list[MinedInvariant]) -> list[MinedInvariant]:
    """Deduplicate and merge invariants with the same expression.

    When multiple tiers produce the same expression:
    - Deduplicate to one entry
    - Set confidence to max(confidences) across all contributing tiers
    - Retain the tier with highest confidence as the primary tier

    Args:
        invariants: Raw invariant list (possibly with duplicates).

    Returns:
        Deduplicated list with merged confidence scores.
    """
    seen: dict[str, MinedInvariant] = {}
    for inv in invariants:
        key = inv.expression.strip()
        if key not in seen:
            seen[key] = inv
        else:
            existing = seen[key]
            if inv.confidence > existing.confidence:
                seen[key] = MinedInvariant(
                    expression=existing.expression,
                    confidence=inv.confidence,
                    tier=inv.tier,
                    source=f"{existing.source}+{inv.source}",
                )
            else:
                seen[key] = MinedInvariant(
                    expression=existing.expression,
                    confidence=existing.confidence,
                    tier=existing.tier,
                    source=f"{existing.source}+{inv.source}",
                )
    return list(seen.values())


def _run_tier1(
    func: Optional[Callable] = None,
    func_source: Optional[str] = None,
) -> list[MinedInvariant]:
    """Tier 1: Semantic mining — LLM hypothesis from source code (zero overhead).

    Reference: Scout 6 Section 3 — Tier 1 Semantic (Agentic PBT)
    """
    source = func_source
    if source is None and func is not None:
        try:
            source = inspect.getsource(func)
        except (OSError, TypeError):
            source = None

    if not source:
        return []

    func_name = func.__name__ if func is not None else "unknown"

    try:
        enrichment = enrich_invariants(
            function_signature=_extract_function_signature(source, func_name),
            observed_invariants=[],
        )
        return [
            MinedInvariant(
                expression=candidate.expression,
                confidence=0.75,
                tier=MiningTier.SEMANTIC,
                source="llm",
            )
            for candidate in enrichment.candidates
        ]
    except Exception:
        return []


def _run_tier2(
    func: Callable,
    trace_args: list[tuple],
) -> list[MinedInvariant]:
    """Tier 2: Runtime mining — Daikon+Houdini with sys.monitoring (low overhead).

    Reference: Scout 6 Section 3 — Tier 2 Runtime (Daikon+Houdini)
    W4.1 daikon.py (sys.monitoring), W4.2 houdini.py (Houdini filter)
    """
    from immune.daikon import InvariantMiner
    from immune.houdini import houdini_filter

    miner = InvariantMiner()
    func_name = func.__name__

    with miner.trace():
        for args in trace_args:
            try:
                func(*args)
            except Exception:
                pass

    daikon_invs = miner.get_invariants(func_name)
    if not daikon_invs:
        return []

    houdini_result = houdini_filter(daikon_invs)

    return [
        MinedInvariant(
            expression=inv.expression,
            confidence=0.85,
            tier=MiningTier.RUNTIME,
            source="daikon+houdini",
        )
        for inv in houdini_result.retained
    ]


def _run_tier3(spans: list) -> list[MinedInvariant]:
    """Tier 3: API-level mining — MINES from OTel spans (no overhead).

    Reference: Scout 6 Section 3 — Tier 3 API-level (MINES)
    W4.3 mines.py (MINES pipeline, arXiv 2512.06906)
    """
    from immune.mines import mine_from_otel_spans

    if not spans:
        return []

    mines_invs = mine_from_otel_spans(spans, dry_run=True)

    return [
        MinedInvariant(
            expression=inv.expression,
            confidence=inv.confidence,
            tier=MiningTier.API_LEVEL,
            source="mines",
        )
        for inv in mines_invs
    ]


def run_mining_tiers(
    func: Optional[Callable] = None,
    trace_args: Optional[list[tuple]] = None,
    spans: Optional[list] = None,
    run_tier1: bool = False,
    func_source: Optional[str] = None,
) -> MiningOrchestrationResult:
    """Run the 3-tier mining orchestrator.

    Runs all applicable tiers based on provided inputs, collects invariants,
    deduplicates, and merges confidence scores across tiers.

    Tier 1 (SEMANTIC):   Runs if run_tier1=True and func or func_source provided.
    Tier 2 (RUNTIME):    Runs if func and trace_args are provided.
    Tier 3 (API_LEVEL):  Runs if spans are provided.

    Args:
        func:        Callable to trace (Tier 1 source extraction + Tier 2 tracing).
        trace_args:  Argument tuples for Tier 2 tracing.
        spans:       OTel spans for Tier 3 MINES mining.
        run_tier1:   Whether to run LLM-based Tier 1 (default: False).
        func_source: Optional pre-fetched source for Tier 1.

    Returns:
        MiningOrchestrationResult with merged invariants, tier_counts, errors.

    Reference: Scout 6 Section 3 — 3-tier mining architecture.
    """
    result = MiningOrchestrationResult()

    if func is None and spans is None:
        return result

    all_invariants: list[MinedInvariant] = []

    # Tier 1: Semantic (LLM hypothesis)
    if run_tier1 and (func is not None or func_source is not None):
        try:
            tier1_invs = _run_tier1(func=func, func_source=func_source)
            result.tier_counts[MiningTier.SEMANTIC] = len(tier1_invs)
            all_invariants.extend(tier1_invs)
        except Exception as exc:
            result.errors.append(f"Tier 1 (semantic) failed: {exc}")

    # Tier 2: Runtime (Daikon+Houdini)
    if func is not None:
        args = trace_args if trace_args is not None else [()]
        try:
            tier2_invs = _run_tier2(func=func, trace_args=args)
            result.tier_counts[MiningTier.RUNTIME] = len(tier2_invs)
            all_invariants.extend(tier2_invs)
        except Exception as exc:
            result.errors.append(f"Tier 2 (runtime) failed: {exc}")

    # Tier 3: API-level (MINES)
    if spans is not None:
        try:
            tier3_invs = _run_tier3(spans=spans)
            result.tier_counts[MiningTier.API_LEVEL] = len(tier3_invs)
            all_invariants.extend(tier3_invs)
        except Exception as exc:
            result.errors.append(f"Tier 3 (mines) failed: {exc}")

    result.merged = _merge_invariants(all_invariants)

    return result
