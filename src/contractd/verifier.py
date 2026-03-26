"""Verification pipeline orchestrator.

Runs the 5-stage CARD verification pipeline in order:
  Stage 0 → Stage 1 → (Stage 2 ∥ Stage 3) → Stage 4

Short-circuits on failure at any sequential stage. Stages 2 and 3 run
in parallel (both execute even if one fails), but Stage 4 only runs
if both 2 and 3 pass/skip.

References:
- ARCHITECTURE.md Section 3 — pipeline design and parallelization
- [REF-P06] DafnyPro — cheapest/fastest stages first, short-circuit on failure
- [REF-C02] Closed-loop verification — pipeline feeds into retry loop
"""

import time
from concurrent.futures import ThreadPoolExecutor

from contractd.types import CardSpec, StageResult, VerifyResult, VerifyStatus


def _run_stage_0(spec: CardSpec, code: str) -> StageResult:
    """Stage 0: Pre-flight checks. Delegates to stages.preflight."""
    from contractd.stages.preflight import run_preflight
    return run_preflight(spec.id)


def _run_stage_1(spec: CardSpec, code: str) -> StageResult:
    """Stage 1: Dependency check. Delegates to stages.deps."""
    from contractd.stages.deps import run_deps
    return run_deps(spec, code)


def _run_stage_2(spec: CardSpec, code: str) -> StageResult:
    """Stage 2: Schema validation. Delegates to stages.schema."""
    from contractd.stages.schema import run_schema
    return run_schema(spec, code)


def _run_stage_3(spec: CardSpec, code: str) -> StageResult:
    """Stage 3: Property-based testing. Delegates to stages.pbt."""
    from contractd.stages.pbt import run_pbt
    return run_pbt(spec, code)


def _run_stage_4(spec: CardSpec, code: str) -> StageResult:
    """Stage 4: Formal verification (Dafny). Delegates to stages.formal."""
    from contractd.stages.formal import run_formal
    return run_formal(spec, code)


def _stage_ok(result: StageResult) -> bool:
    """Check if a stage result allows the pipeline to continue.

    PASS and SKIP both allow continuation.
    FAIL and TIMEOUT block the pipeline.
    """
    return result.status in (VerifyStatus.PASS, VerifyStatus.SKIP)


def run_pipeline(spec: CardSpec, code: str) -> VerifyResult:
    """Run the full 5-stage verification pipeline.

    Execution order per ARCHITECTURE.md Section 3:
      Stage 0 (preflight)    — sequential
      Stage 1 (deps)         — sequential
      Stage 2 (schema)  ┐
                         ├── parallel [ARCHITECTURE.md Section 3]
      Stage 3 (pbt)     ┘
      Stage 4 (formal)       — sequential (heaviest, runs last)

    Short-circuit: any sequential stage failing stops the pipeline.
    Stages 2+3 are parallel — both run even if one fails, but Stage 4
    only runs if both 2 and 3 pass/skip.

    Args:
        spec: Parsed .card.md specification.
        code: Generated source code string to verify.

    Returns:
        VerifyResult with verified=True if all stages pass/skip.
    """
    start = time.monotonic()
    stages: list[StageResult] = []

    # Stage 0: Pre-flight — sequential
    result_0 = _run_stage_0(spec, code)
    stages.append(result_0)
    if not _stage_ok(result_0):
        return _build_result(stages, start, verified=False)

    # Stage 1: Dependency check — sequential
    result_1 = _run_stage_1(spec, code)
    stages.append(result_1)
    if not _stage_ok(result_1):
        return _build_result(stages, start, verified=False)

    # Stages 2 + 3: Schema + PBT — parallel per ARCHITECTURE.md
    # Both run regardless of individual failures, but both must pass
    # for Stage 4 to proceed.
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_2 = executor.submit(_run_stage_2, spec, code)
        future_3 = executor.submit(_run_stage_3, spec, code)
        result_2 = future_2.result()
        result_3 = future_3.result()

    stages.append(result_2)
    stages.append(result_3)

    if not (_stage_ok(result_2) and _stage_ok(result_3)):
        return _build_result(stages, start, verified=False)

    # Stage 4: Formal verification — sequential (heaviest)
    result_4 = _run_stage_4(spec, code)
    stages.append(result_4)

    verified = _stage_ok(result_4)
    return _build_result(stages, start, verified=verified)


def _build_result(
    stages: list[StageResult], start: float, verified: bool
) -> VerifyResult:
    """Build a VerifyResult from accumulated stage results."""
    total_ms = int((time.monotonic() - start) * 1000)
    # Also sum individual stage durations for accurate accounting
    stage_sum = sum(s.duration_ms for s in stages)
    return VerifyResult(
        verified=verified,
        stages=stages,
        total_duration_ms=max(total_ms, stage_sum),
    )
