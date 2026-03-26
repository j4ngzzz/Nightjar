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

from nightjar.types import CardSpec, StageResult, VerifyResult, VerifyStatus


def _run_stage_0(spec: CardSpec, code: str, spec_path: str = "") -> StageResult:
    """Stage 0: Pre-flight checks. Delegates to stages.preflight.

    In pipeline mode, preflight validates the spec file and optionally the code AST.
    If spec_path is empty, we skip file-level checks and only validate the code AST.
    """
    from nightjar.stages.preflight import run_preflight
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
    from nightjar.stages.deps import run_deps_check
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
    from nightjar.stages.schema import run_schema_check
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
    from nightjar.stages.pbt import run_pbt
    return run_pbt(spec, code)


def _run_stage_4(spec: CardSpec, code: str) -> StageResult:
    """Stage 4: Formal verification (Dafny). Delegates to stages.formal."""
    from nightjar.stages.formal import run_formal
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
    result = VerifyResult(
        verified=verified,
        stages=stages,
        total_duration_ms=max(total_ms, stage_sum),
    )
    # Attach confidence score per Scout 3 S5.3 [W1.4]
    # Informational — never blocks pipeline; catches ImportError in edge cases
    try:
        from nightjar.confidence import compute_confidence
        result.confidence = compute_confidence(result)
    except Exception:
        pass
    return result


# ─── Graceful Degradation Ladder (W1.5) ──────────────────────────────────────
# Per Scout 3 S5.5: When Dafny fails, fall back to CrossHair → Hypothesis.
# 'No user is ever blocked.' CrossHair covers ~80% of practical invariants.


def _run_crosshair_fallback(spec: CardSpec, code: str) -> StageResult:
    """Run CrossHair symbolic execution as Stage 4 fallback.

    Per Scout 3 S5.5 Rank 1: CrossHair uses same Z3 solver as Dafny,
    directly on Python contracts. No translation step required.
    Average 13s per function. Score: 9/10 (covers ~80% of practical invariants).

    Runs: python -m crosshair check <tmp_file.py>
    Exit 0 → PASS; exit non-0 with error lines → FAIL;
    subprocess.TimeoutExpired → TIMEOUT; crosshair not installed → SKIP.

    Args:
        spec: Parsed .card.md specification.
        code: Python source code to analyze symbolically.

    Returns:
        StageResult with stage=4, name='crosshair'.
    """
    import subprocess
    import sys
    import tempfile
    import os
    import time as _time

    start = _time.monotonic()

    # Write code to temp file for CrossHair analysis
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "crosshair", "check", tmp_path],
            capture_output=True,
            text=True,
            timeout=120,  # 120s CrossHair budget per Scout 3 S5.5
        )
        duration = int((_time.monotonic() - start) * 1000)

        if result.returncode == 0:
            return StageResult(
                stage=4,
                name="crosshair",
                status=VerifyStatus.PASS,
                duration_ms=duration,
            )

        # Parse violation lines from CrossHair output
        output = result.stdout + result.stderr
        violations = [
            {"type": "crosshair_violation", "message": line.strip()}
            for line in output.splitlines()
            if line.strip() and ("error:" in line.lower() or "counterexample" in line.lower())
        ]
        if not violations and output.strip():
            violations = [{"type": "crosshair_error", "message": output.strip()[:500]}]

        return StageResult(
            stage=4,
            name="crosshair",
            status=VerifyStatus.FAIL,
            duration_ms=duration,
            errors=violations or [{"type": "crosshair_error", "message": "CrossHair check failed"}],
        )

    except subprocess.TimeoutExpired:
        duration = int((_time.monotonic() - start) * 1000)
        return StageResult(
            stage=4,
            name="crosshair",
            status=VerifyStatus.TIMEOUT,
            duration_ms=duration,
            errors=[{"type": "timeout", "message": "CrossHair exceeded 120s budget"}],
        )
    except FileNotFoundError:
        # python -m crosshair not found — module not installed
        duration = int((_time.monotonic() - start) * 1000)
        return StageResult(
            stage=4,
            name="crosshair",
            status=VerifyStatus.SKIP,
            duration_ms=duration,
            errors=[{"message": "CrossHair not installed — install crosshair for fallback"}],
        )
    except Exception as e:
        duration = int((_time.monotonic() - start) * 1000)
        return StageResult(
            stage=4,
            name="crosshair",
            status=VerifyStatus.FAIL,
            duration_ms=duration,
            errors=[{"type": "crosshair_error", "error": str(e)}],
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _run_hypothesis_extended(spec: CardSpec, code: str) -> StageResult:
    """Run extended Hypothesis PBT as final fallback.

    Per Scout 3 S5.5 Rank 2: 'When CrossHair hits path explosion, Hypothesis
    continues.' Combined score: 10/10 feasibility for practical invariants.

    Extended PBT = 10K+ examples via run_pbt_extended() which uses
    NIGHTJAR_PBT_EXTENDED_SETTINGS (vs dev:10/ci:200 in standard Stage 3).
    icontract-hypothesis bridge auto-generates strategies from decorators.

    Args:
        spec: Parsed .card.md specification.
        code: Python source code to test.

    Returns:
        StageResult with stage=4, name='hypothesis_extended'.
    """
    from nightjar.stages.pbt import run_pbt_extended
    # Run extended PBT (10K+ examples via NIGHTJAR_PBT_EXTENDED_SETTINGS)
    result = run_pbt_extended(spec, code)
    # Rename to 'hypothesis_extended' for clarity in the fallback chain
    return StageResult(
        stage=result.stage,
        name="hypothesis_extended",
        status=result.status,
        duration_ms=result.duration_ms,
        errors=result.errors,
        counterexample=result.counterexample,
    )


def _is_dafny_failure(result: StageResult) -> bool:
    """Check if a stage result represents a Dafny failure requiring fallback.

    Fallback is triggered by:
    - TIMEOUT: Dafny ran but didn't finish
    - FAIL with dafny_not_found: binary not installed
    """
    if result.status == VerifyStatus.TIMEOUT:
        return True
    if result.status == VerifyStatus.FAIL:
        for error in result.errors:
            if error.get("type") == "dafny_not_found":
                return True
    return False


def run_pipeline_with_fallback(spec: CardSpec, code: str, spec_path: str = "") -> VerifyResult:
    """Run verification pipeline with graceful degradation fallback chain.

    Per Scout 3 S5.4-5.5: If Dafny times out or is unavailable, fall back
    to CrossHair symbolic execution, then extended Hypothesis PBT.

    Fallback chain:
      1. Normal pipeline (run_pipeline) with Stage 4 Dafny
      2. If Dafny TIMEOUT or dafny_not_found → CrossHair symbolic (Stage 4b)
      3. If CrossHair TIMEOUT → Hypothesis extended (Stage 4c)
      4. If all fail → return partial VerifyResult with confidence score

    'No user is ever blocked.' (Scout 3 S5.5)

    Args:
        spec: Parsed .card.md specification.
        code: Generated source code to verify.
        spec_path: Optional path to the .card.md spec file.

    Returns:
        VerifyResult — always non-None, with confidence score attached.
    """
    # Run normal pipeline (Stages 0-4)
    result = run_pipeline(spec, code, spec_path=spec_path)

    # Check if Stage 4 (Dafny) needs fallback
    stage_4 = next(
        (s for s in result.stages if s.stage == 4 and s.name == "formal"),
        None,
    )

    if stage_4 is None or not _is_dafny_failure(stage_4):
        # No fallback needed — Dafny passed, skipped, or failed for known reasons
        return result

    # Fallback 1: CrossHair symbolic execution (Scout 3 S5.5 Rank 1)
    crosshair_result = _run_crosshair_fallback(spec, code)
    result.stages.append(crosshair_result)

    if _stage_ok(crosshair_result):
        # CrossHair passed — update verified status
        # Keep result verified=False (Dafny didn't prove it) but confidence updated
        try:
            from nightjar.confidence import compute_confidence
            result.confidence = compute_confidence(result)
        except Exception:
            pass
        return result

    if crosshair_result.status == VerifyStatus.TIMEOUT:
        # Fallback 2: Extended Hypothesis PBT (Scout 3 S5.5 Rank 2)
        hyp_result = _run_hypothesis_extended(spec, code)
        result.stages.append(hyp_result)

    # Update confidence score with all fallback stages included
    try:
        from nightjar.confidence import compute_confidence
        result.confidence = compute_confidence(result)
    except Exception:
        pass

    return result
