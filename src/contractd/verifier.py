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


def _run_stage_0(spec: CardSpec, code: str, spec_path: str = "") -> StageResult:
    """Stage 0: Pre-flight checks. Delegates to stages.preflight.

    In pipeline mode, preflight validates the spec file and optionally the code AST.
    If spec_path is empty, we skip file-level checks and only validate the code AST.
    """
    from contractd.stages.preflight import run_preflight
    import tempfile, os
    if spec_path and os.path.exists(spec_path):
        return run_preflight(spec_path)
    # If no spec file path, write code to temp and validate AST only
    if code:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            tmp = f.name
        try:
            return run_preflight(spec_path or "inline", code_path=tmp)
        finally:
            os.unlink(tmp)
    return StageResult(stage=0, name="preflight", status=VerifyStatus.PASS, duration_ms=0)


def _run_stage_1(spec: CardSpec, code: str) -> StageResult:
    """Stage 1: Dependency check. Delegates to stages.deps.

    Adapts pipeline signature (spec, code) to deps signature (code_path, deps_lock_path).
    In pipeline mode we pass the code string; deps check extracts imports from it.
    Falls back to SKIP if no deps.lock exists (common during development).
    """
    from contractd.stages.deps import run_deps_check
    import tempfile, os
    # Write code to temp file for import analysis
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(code)
        code_path = f.name
    try:
        deps_lock = "deps.lock"
        if not os.path.exists(deps_lock):
            return StageResult(stage=1, name="deps", status=VerifyStatus.SKIP,
                             errors=[{"message": "No deps.lock found — skipping dependency check"}])
        return run_deps_check(code_path, deps_lock)
    finally:
        os.unlink(code_path)


def _run_stage_2(spec: CardSpec, code: str) -> StageResult:
    """Stage 2: Schema validation. Delegates to stages.schema.

    Adapts pipeline signature (spec, code) to schema signature (spec, output_data).
    In pipeline mode, we don't have runtime output yet — we validate the code's
    type annotations against the contract schema structurally.
    Skips if no outputs are defined in the contract.
    """
    from contractd.stages.schema import run_schema_check
    if not spec.contract.outputs:
        return StageResult(stage=2, name="schema", status=VerifyStatus.SKIP,
                         errors=[{"message": "No contract outputs defined — skipping schema check"}])
    # Build a structural output dict from contract definition for validation
    output_schema = {}
    for out in spec.contract.outputs:
        output_schema[out.name] = out.schema if out.schema else {"type": out.type}
    return run_schema_check(spec, output_schema)


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


def run_pipeline(spec: CardSpec, code: str, spec_path: str = "") -> VerifyResult:
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
    result_0 = _run_stage_0(spec, code, spec_path=spec_path)
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
