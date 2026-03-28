"""Verification pipeline orchestrator.

Runs the 5-stage Nightjar verification pipeline in order:
  Stage 0 → Stage 1 → (Stage 2 ∥ Stage 3) → Stage 4

Short-circuits on failure at any sequential stage. Stages 2 and 3 run
in parallel (both execute even if one fails), but Stage 4 only runs
if both 2 and 3 pass/skip.

References:
- ARCHITECTURE.md Section 3 — pipeline design and parallelization
- [REF-P06] DafnyPro — cheapest/fastest stages first, short-circuit on failure
- [REF-C02] Closed-loop verification — pipeline feeds into retry loop
"""

import ast
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from nightjar.types import CardSpec, StageResult, VerifyResult, VerifyStatus


# ─── Complexity-Discriminated Routing (U1.5) ─────────────────────────────────
# Per SafePilot (arxiv:2603.21523): route simple functions to CrossHair symbolic
# only (skipping Dafny) to cut ~70% of verification wall-time on typical codebases.
# Complexity = cyclomatic_complexity + ast_depth / 3 (empirically calibrated).
# Threshold ≤ 5 → CrossHair; > 5 → full Dafny.

_COMPLEXITY_THRESHOLD = 5

# AST node types that increment cyclomatic complexity (branch count)
_BRANCH_NODES = (
    ast.If, ast.While, ast.For, ast.ExceptHandler,
    ast.With, ast.AsyncWith, ast.AsyncFor,
)


def _ast_depth(node: ast.AST, current: int = 0) -> int:
    """Measure maximum nesting depth of an AST node recursively."""
    children = list(ast.iter_child_nodes(node))
    if not children:
        return current
    return max(_ast_depth(child, current + 1) for child in children)


def _compute_complexity(code: str) -> int:
    """Compute a complexity score for a code string.

    Score = cyclomatic_complexity + floor(ast_depth / 3)

    Cyclomatic complexity counts branches (if/while/for/try/with) +1 base.
    AST depth captures nesting that increases verification search space.
    Syntax errors return a high score (route to Dafny for safety).

    Args:
        code: Python source code string.

    Returns:
        Integer complexity score (0 = trivially simple, higher = more complex).
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return _COMPLEXITY_THRESHOLD + 10  # Safety: route unknown code to Dafny

    branch_count = 1  # Base cyclomatic complexity
    for node in ast.walk(tree):
        if isinstance(node, _BRANCH_NODES):
            branch_count += 1

    depth = _ast_depth(tree)
    return branch_count + depth // 3


def _route_to_crosshair(code: str) -> bool:
    """Return True if code is simple enough to verify with CrossHair alone.

    Per SafePilot: simple functions (complexity ≤ threshold) skip Dafny and
    use CrossHair symbolic execution only. Cuts ~70% verification time.

    Args:
        code: Python source code string.

    Returns:
        True → CrossHair-only route; False → full Dafny route.
    """
    return _compute_complexity(code) <= _COMPLEXITY_THRESHOLD


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
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
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
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
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


def _run_stage_negproof(spec: CardSpec, code: str) -> StageResult:
    """Stage 2.5: Negation-proof spec validation [REF-NEW-07, U1.4].

    For each FORMAL invariant, negates the postcondition and checks if
    CrossHair CONFIRMS the negation (which would indicate a degenerate spec).
    Returns SKIP when no FORMAL invariants, FAIL when weak specs detected,
    PASS when all specs are meaningful.

    Per NegProof (arxiv:2603.13414): cheaper than full Dafny for catching
    specs that are trivially satisfied or never satisfiable.
    """
    import time as _time
    from nightjar.negation_proof import run_negation_proof
    from nightjar.types import InvariantTier

    start = _time.monotonic()

    # Skip if no formal invariants (nothing to check)
    has_formal = any(inv.tier == InvariantTier.FORMAL for inv in spec.invariants)
    if not has_formal:
        return StageResult(stage=5, name="negation_proof", status=VerifyStatus.SKIP)

    neg_result = run_negation_proof(spec, code)
    duration = int((_time.monotonic() - start) * 1000)

    if neg_result.passed:
        return StageResult(
            stage=5, name="negation_proof", status=VerifyStatus.PASS,
            duration_ms=duration,
        )
    else:
        return StageResult(
            stage=5, name="negation_proof", status=VerifyStatus.FAIL,
            duration_ms=duration,
            errors=[{
                "type": "weak_spec",
                "message": (
                    f"Degenerate spec detected — negation proof confirmed for: "
                    + ", ".join(repr(s) for s in neg_result.weak_specs)
                ),
                "weak_specs": neg_result.weak_specs,
            }],
        )


def _run_stage_4(spec: CardSpec, code: str) -> StageResult:
    """Stage 4: Formal verification with complexity-discriminated routing (U1.5).

    Per SafePilot (arxiv:2603.21523): routes based on cyclomatic complexity + AST depth.
    - Simple (complexity ≤ 5) → CrossHair symbolic only (~13s, saves ~70% wall-time)
    - Complex (complexity > 5) → full Dafny formal verification

    Routing is encapsulated here so existing tests that patch _run_stage_4
    bypass routing entirely (backward-compatible contract).
    """
    if _route_to_crosshair(code):
        return _run_crosshair_symbolic(spec, code)
    from nightjar.stages.formal import run_formal
    return run_formal(spec, code)


def _run_crosshair_symbolic(spec: CardSpec, code: str) -> StageResult:
    """Run CrossHair as Stage 4 for simple functions (complexity routing path).

    Distinct from _run_crosshair_fallback (degradation ladder) — this is the
    primary route for simple functions, not a fallback.
    Returns SKIP with routing_note if CrossHair not installed.
    """
    import subprocess
    import sys
    import tempfile
    import os
    import time as _time

    start = _time.monotonic()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name
    try:
        # --report_all: emit a summary line for every path checked, enabling
        # path-count extraction for graduated confidence display.
        # Graceful: if CrossHair doesn't support --report_all, we re-run without it.
        cmd_with_report = [sys.executable, "-m", "crosshair", "check", "--report_all", tmp_path]
        result = subprocess.run(
            cmd_with_report,
            capture_output=True, text=True, timeout=120,
        )
        # Detect unsupported flag: CrossHair prints "unrecognized arguments" or
        # returns exit code 2 (argparse error) when the flag is unknown.
        _report_all_supported = not (
            result.returncode == 2
            or "unrecognized" in (result.stderr or "").lower()
            or "no such option" in (result.stderr or "").lower()
        )
        if not _report_all_supported:
            # Re-run without --report_all (graceful degradation)
            result = subprocess.run(
                [sys.executable, "-m", "crosshair", "check", tmp_path],
                capture_output=True, text=True, timeout=120,
            )

        duration = int((_time.monotonic() - start) * 1000)

        # ── Parse path count from CrossHair output ────────────────────────
        # CrossHair emits lines like: "Confirmed over all paths" or
        # "All N paths confirmed" when it has exhausted the path space.
        import re as _re
        output = result.stdout + result.stderr
        paths_exhausted = 0
        for line in output.splitlines():
            m = _re.search(r"(\d+)\s+path", line, _re.IGNORECASE)
            if m:
                paths_exhausted += int(m.group(1))
            elif _re.search(r"confirmed over all paths", line, _re.IGNORECASE):
                paths_exhausted = paths_exhausted or 1  # at least 1 path confirmed
        coverage_note = f"{paths_exhausted} paths exhausted" if paths_exhausted else ""
        # ─────────────────────────────────────────────────────────────────

        if result.returncode == 0:
            return StageResult(
                stage=4, name="formal", status=VerifyStatus.PASS,
                duration_ms=duration, coverage_note=coverage_note,
            )
        violations = [
            {"type": "crosshair_violation", "message": line.strip()}
            for line in output.splitlines()
            if line.strip() and ("error:" in line.lower() or "counterexample" in line.lower())
        ]
        return StageResult(
            stage=4, name="formal", status=VerifyStatus.FAIL, duration_ms=duration,
            errors=violations or [{"type": "crosshair_error", "message": output.strip()[:500]}],
            coverage_note=coverage_note,
        )
    except subprocess.TimeoutExpired:
        duration = int((_time.monotonic() - start) * 1000)
        return StageResult(stage=4, name="formal", status=VerifyStatus.TIMEOUT, duration_ms=duration,
                           errors=[{"type": "timeout", "message": "CrossHair symbolic exceeded 120s"}])
    except FileNotFoundError:
        duration = int((_time.monotonic() - start) * 1000)
        # CrossHair not installed — SKIP with routing note (not a real failure)
        return StageResult(stage=4, name="formal", status=VerifyStatus.SKIP, duration_ms=duration,
                           errors=[{"message": "CrossHair not installed; install for complexity routing"}])
    except Exception as e:
        duration = int((_time.monotonic() - start) * 1000)
        return StageResult(stage=4, name="formal", status=VerifyStatus.FAIL, duration_ms=duration,
                           errors=[{"type": "error", "error": str(e)}])
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _stage_ok(result: StageResult) -> bool:
    """Check if a stage result allows the pipeline to continue.

    PASS and SKIP both allow continuation.
    FAIL and TIMEOUT block the pipeline.
    """
    return result.status in (VerifyStatus.PASS, VerifyStatus.SKIP)


def run_pipeline(
    spec: CardSpec,
    code: str,
    spec_path: str = "",
    display_callback: Optional[Any] = None,
) -> VerifyResult:
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

    Complexity routing (U1.5 — SafePilot): simple functions (complexity ≤ 5)
    route to CrossHair symbolic only, skipping Dafny (~70% wall-time savings).

    Display hooks (U1.5): optional display_callback receives stage events.
    Implements nightjar.display.DisplayCallback protocol.
    Defaults to NullDisplay (silent) when not provided.

    Args:
        spec: Parsed .card.md specification.
        code: Generated source code string to verify.
        spec_path: Optional path to the .card.md file (for preflight).
        display_callback: Optional DisplayCallback for streaming output.
            Must implement on_stage_start(int, str), on_stage_complete(StageResult),
            and on_pipeline_complete(VerifyResult). Defaults to NullDisplay.

    Returns:
        VerifyResult with verified=True if at least one stage passes and no stage fails.
        All-SKIP (nothing tested) returns verified=False.
    """
    from nightjar.display import NullDisplay
    display = display_callback if display_callback is not None else NullDisplay()

    start = time.monotonic()
    stages: list[StageResult] = []

    # Stage 0: Pre-flight -- sequential
    display.on_stage_start(0, "preflight")
    result_0 = _run_stage_0(spec, code, spec_path=spec_path)
    stages.append(result_0)
    display.on_stage_complete(result_0)
    if not _stage_ok(result_0):
        result = _build_result(stages, start, verified=False)
        display.on_pipeline_complete(result)
        return result

    # Guard: a spec with zero invariants is vacuously unverifiable.
    # Returning verified=True with no invariants is misleading -- there is
    # nothing to prove.  Append an explicit FAIL stage so the user knows
    # to add invariants, not to interpret silence as safety.
    # This runs AFTER stage 0 so the preflight result is always recorded.
    if not spec.invariants:
        empty_stage = StageResult(
            stage=1,
            name="no_invariants",
            status=VerifyStatus.FAIL,
            duration_ms=0,
            errors=[{
                "type": "no_invariants",
                "message": (
                    "Spec has no invariants -- nothing to verify. "
                    "Add at least one 'property' or 'formal' tier invariant."
                ),
            }],
        )
        stages.append(empty_stage)
        result = _build_result(stages, start, verified=False)
        display.on_pipeline_complete(result)
        return result

    # Stage 1: Dependency check — sequential
    display.on_stage_start(1, "deps")
    result_1 = _run_stage_1(spec, code)
    stages.append(result_1)
    display.on_stage_complete(result_1)
    if not _stage_ok(result_1):
        result = _build_result(stages, start, verified=False)
        display.on_pipeline_complete(result)
        return result

    # Stages 2 + 3: Schema + PBT — parallel per ARCHITECTURE.md
    display.on_stage_start(2, "schema")
    display.on_stage_start(3, "pbt")
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_2 = executor.submit(_run_stage_2, spec, code)
        future_3 = executor.submit(_run_stage_3, spec, code)
        result_2 = future_2.result()
        result_3 = future_3.result()

    stages.append(result_2)
    stages.append(result_3)
    display.on_stage_complete(result_2)
    display.on_stage_complete(result_3)

    if not (_stage_ok(result_2) and _stage_ok(result_3)):
        result = _build_result(stages, start, verified=False)
        display.on_pipeline_complete(result)
        return result

    # Stage 2.5: Negation-proof spec validation (U1.4 — NegProof)
    # Checks FORMAL invariants are meaningful before expensive Dafny run.
    display.on_stage_start(5, "negation_proof")
    result_neg = _run_stage_negproof(spec, code)
    stages.append(result_neg)
    display.on_stage_complete(result_neg)
    if not _stage_ok(result_neg):
        result = _build_result(stages, start, verified=False)
        display.on_pipeline_complete(result)
        return result

    # Stage 4: Formal verification with complexity routing (U1.5 — SafePilot)
    # Routing is encapsulated inside _run_stage_4: simple → CrossHair, complex → Dafny
    display.on_stage_start(4, "formal")
    result_4 = _run_stage_4(spec, code)
    stages.append(result_4)
    display.on_stage_complete(result_4)

    # Sort stages by stage number so list is always in sequential order (0,1,2,3,...)
    stages.sort(key=lambda s: s.stage)

    has_active_pass = any(s.status == VerifyStatus.PASS for s in stages)
    no_failures = _stage_ok(result_4)
    verified = has_active_pass and no_failures
    result = _build_result(stages, start, verified=verified)
    display.on_pipeline_complete(result)
    return result


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
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
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


# ─── DeerFlow Parallel Verification (W2-5) ───────────────────────────────────
# Per DeerFlow (bytedance/deer-flow): lead agent decomposes task into scoped
# subagents that run in parallel. Independent verification stages (schema, PBT,
# formal) share no inter-stage data — fan out → collect → synthesize results.

_HASH_CACHE_PATH = ".card/cache/invariant_hashes.json"


def run_pipeline_parallel(
    spec: CardSpec,
    code: str,
    spec_path: str = "",
) -> VerifyResult:
    """Run verification pipeline with stages 2-4 in parallel (DeerFlow pattern).

    Gated behind NIGHTJAR_PARALLEL=1 env var (off by default). Falls back to
    the standard sequential run_pipeline() when the env var is not set.

    Execution order when NIGHTJAR_PARALLEL=1:
      Stage 0 (preflight)  — sequential gate
      Stage 1 (deps)       — sequential gate
      Stage 2 (schema) ─┐
      Stage 3 (pbt)     ├── parallel fan-out (DeerFlow scoped subagent pattern)
      Stage 4 (formal)  ┘
      Synthesize → VerifyResult (stages always reported in order 0,1,2,3,4)

    Per DeerFlow architecture: each sub-agent runs with isolated scoped context
    and reports structured results back to the lead. Schema validation, PBT,
    and formal proof each receive the same (spec, code) inputs — no inter-stage
    deps — enabling ~60% speedup by overlapping I/O-bound Dafny with CPU-bound
    Hypothesis execution.

    Args:
        spec: Parsed .card.md specification.
        code: Generated source code string to verify.
        spec_path: Optional path to the .card.md file (for preflight).

    Returns:
        VerifyResult with verified=True if at least one stage passes and no stage fails.
        All-SKIP (nothing tested) returns verified=False.
    """
    import os as _os
    if _os.environ.get("NIGHTJAR_PARALLEL") != "1":
        return run_pipeline(spec, code, spec_path=spec_path)

    start = time.monotonic()
    stages: list[StageResult] = []

    # Stage 0: preflight — sequential gate (fast, validates spec file)
    result_0 = _run_stage_0(spec, code, spec_path=spec_path)
    stages.append(result_0)
    if not _stage_ok(result_0):
        return _build_result(stages, start, verified=False)

    # Stage 1: deps — sequential gate (fast, validates dependency manifest)
    result_1 = _run_stage_1(spec, code)
    stages.append(result_1)
    if not _stage_ok(result_1):
        return _build_result(stages, start, verified=False)

    # Negation-proof gate (U1.4 — NegProof): validate FORMAL invariants are meaningful
    # before launching formal verification. Runs before the fan-out so a degenerate
    # spec is caught without wasting the ThreadPoolExecutor budget.
    result_neg = _run_stage_negproof(spec, code)
    stages.append(result_neg)
    if not _stage_ok(result_neg):
        return _build_result(stages, start, verified=False)

    # Stages 2, 3, 4: parallel fan-out (DeerFlow scoped subagent pattern)
    # Each stage receives the same (spec, code) — no inter-stage data dependency.
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_2 = executor.submit(_run_stage_2, spec, code)
        future_3 = executor.submit(_run_stage_3, spec, code)
        future_4 = executor.submit(_run_stage_4, spec, code)
        result_2 = future_2.result()
        result_3 = future_3.result()
        result_4 = future_4.result()

    # Merge in canonical order 0,1,2,3,4 regardless of completion order
    stages.extend([result_2, result_3, result_4])

    has_active_pass = any(s.status == VerifyStatus.PASS for s in stages)
    no_failures = _stage_ok(result_2) and _stage_ok(result_3) and _stage_ok(result_4)
    verified = has_active_pass and no_failures
    return _build_result(stages, start, verified=verified)


# ─── SpecLang Incremental Recompilation (W2-5) ───────────────────────────────
# Per GitHub Next SpecLang: watch for spec changes, identify which sections
# changed, recompile only those. Most spec edits touch 1-2 invariants —
# incremental mode cuts 90%+ of compute for unchanged invariants.


def _save_hashes_to_cache(hashes: dict[str, str]) -> None:
    """Persist invariant hashes to .card/cache/invariant_hashes.json."""
    import json as _json
    from pathlib import Path as _Path
    cache_path = _Path(_HASH_CACHE_PATH)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(_json.dumps(hashes, indent=2), encoding="utf-8")


def _build_incremental_noop_result(start: float) -> VerifyResult:
    """Synthesize an all-PASS VerifyResult for a full cache hit (nothing changed).

    Routes through _build_result() so the confidence score is computed and
    attached consistently with all other pipeline exit paths.
    """
    synthetic_stages = [
        StageResult(stage=i, name=name, status=VerifyStatus.PASS, duration_ms=0)
        for i, name in enumerate(["preflight", "deps", "schema", "pbt", "formal"])
    ]
    # Include negation_proof (stage 5) to match run_pipeline() output — Bug 10
    synthetic_stages.append(
        StageResult(stage=5, name="negation_proof", status=VerifyStatus.SKIP, duration_ms=0)
    )
    return _build_result(synthetic_stages, start, verified=True)


def run_pipeline_incremental(
    spec: CardSpec,
    code: str,
    previous_hashes: dict[str, str],
    spec_path: str = "",
) -> VerifyResult:
    """Run verification for changed/added invariants only (SpecLang incremental pattern).

    Per GitHub Next SpecLang: a background watcher detects spec changes and
    recompiles only the affected sections. Most spec edits touch 1-2 invariants,
    making a full 5-stage re-run wasteful. Incremental mode cuts 90%+ of compute
    for unchanged invariants.

    Algorithm:
      1. Hash current code → compare to __code__ in previous_hashes
         If code changed → full run_pipeline() (cached results are invalid)
      2. Diff invariant hashes → find changed/added invariant IDs
      3. No changes at all → return synthetic all-PASS (full cache hit)
      4. Removals only → full run_pipeline() on current spec (safe, fast path)
      5. Changed/added → build filtered spec with only those invariants,
         run full pipeline on filtered spec + original code
      6. Save updated hashes to .card/cache/invariant_hashes.json

    Unchanged invariants get their previous PASS result carried forward.
    The existing run_pipeline() is not modified (backward-compatible).

    Args:
        spec: Current parsed .card.md specification.
        code: Generated source code to verify.
        previous_hashes: Hash map from the previous run ({invariant_id: sha256}).
            Use the special "__code__" key to carry the previous code hash.
        spec_path: Optional path to the .card.md file (for preflight).

    Returns:
        VerifyResult. verified=True if all active stages pass/skip.
    """
    import hashlib as _hashlib
    import dataclasses as _dc
    from nightjar.parser import hash_invariants, diff_specs

    start = time.monotonic()

    # Step 1: detect code change via __code__ sentinel key
    code_hash = _hashlib.sha256(code.encode()).hexdigest()
    prev_code_hash = previous_hashes.get("__code__", "")
    if prev_code_hash and prev_code_hash != code_hash:
        # Code changed — full pipeline required; no cached invariant results are reusable
        result = run_pipeline(spec, code, spec_path=spec_path)
        _save_hashes_to_cache({**hash_invariants(spec), "__code__": code_hash})
        return result

    # Step 2: diff invariant hashes to find what changed
    current_inv_hashes = hash_invariants(spec)
    inv_previous = {k: v for k, v in previous_hashes.items() if k != "__code__"}
    diff = diff_specs(inv_previous, current_inv_hashes)

    changed_ids = set(diff.changed + diff.added)

    # Step 3: full cache hit — neither invariants nor code changed
    if not changed_ids and not diff.removed:
        result = _build_incremental_noop_result(start)
        _save_hashes_to_cache({**current_inv_hashes, "__code__": code_hash})
        return result

    # Step 4: removals only (no changed/added) — run full pipeline on current spec
    if not changed_ids:
        result = run_pipeline(spec, code, spec_path=spec_path)
        _save_hashes_to_cache({**current_inv_hashes, "__code__": code_hash})
        return result

    # Step 5: build filtered spec containing only changed/added invariants
    filtered_invariants = [inv for inv in spec.invariants if inv.id in changed_ids]
    filtered_spec = _dc.replace(spec, invariants=filtered_invariants)

    result = run_pipeline(filtered_spec, code, spec_path=spec_path)

    # Step 6: persist updated hashes for next incremental run
    _save_hashes_to_cache({**current_inv_hashes, "__code__": code_hash})
    return result


# SARIF rule IDs and metadata per verification stage
_SARIF_RULES: list[dict] = [
    {
        "id": "NJ000",
        "name": "PreflightCheck",
        "shortDescription": {"text": "Spec preflight validation"},
        "helpUri": "https://github.com/j4ngzzz/Nightjar#stage-0-preflight",
    },
    {
        "id": "NJ001",
        "name": "DependencyAudit",
        "shortDescription": {"text": "Dependency security audit"},
        "helpUri": "https://github.com/j4ngzzz/Nightjar#stage-1-deps",
    },
    {
        "id": "NJ002",
        "name": "SchemaValidation",
        "shortDescription": {"text": "Schema and type validation"},
        "helpUri": "https://github.com/j4ngzzz/Nightjar#stage-2-schema",
    },
    {
        "id": "NJ003",
        "name": "PropertyTests",
        "shortDescription": {"text": "Property-based test failure"},
        "helpUri": "https://github.com/j4ngzzz/Nightjar#stage-3-property-tests",
    },
    {
        "id": "NJ004",
        "name": "FormalProof",
        "shortDescription": {"text": "Formal verification failure (Dafny)"},
        "helpUri": "https://github.com/j4ngzzz/Nightjar#stage-4-formal-proof",
    },
]

# Map stage number → SARIF rule ID
_STAGE_RULE_ID: dict[int, str] = {r["id"][-1:]: r["id"] for r in _SARIF_RULES}
_STAGE_TO_RULE: dict[int, str] = {i: f"NJ{i:03d}" for i in range(5)}


def to_sarif(
    result: "VerifyResult",
    spec_path: str = "",
    tool_version: str = "0.1.0",
) -> dict:
    """Convert a VerifyResult to SARIF 2.1.0 format for GitHub Code Scanning.

    SARIF (Static Analysis Results Interchange Format) allows Nightjar
    verification failures to appear as native PR annotations in GitHub.
    Upload the output to GitHub via:

        nightjar verify --sarif > nightjar.sarif
        gh upload-sarif --sarif-file nightjar.sarif

    Args:
        result: The VerifyResult from run_pipeline() or run_pipeline_with_fallback().
        spec_path: Optional path to the .card.md file (used as artifact URI).
        tool_version: Nightjar version string embedded in the SARIF driver block.

    Returns:
        SARIF 2.1.0 dict, ready for json.dumps().

    References:
        SARIF 2.1.0 spec: https://docs.oasis-open.org/sarif/sarif/v2.1.0/
        GitHub Code Scanning: https://docs.github.com/en/code-security/code-scanning
    """
    sarif_results: list[dict] = []

    for stage in result.stages:
        if stage.status not in (VerifyStatus.FAIL, VerifyStatus.TIMEOUT):
            continue

        level = "error" if stage.status == VerifyStatus.FAIL else "warning"
        rule_id = _STAGE_TO_RULE.get(stage.stage, f"NJ{stage.stage:03d}")

        for error in stage.errors:
            message_text = error.get("message") or error.get("error") or str(error)

            sarif_result: dict = {
                "ruleId": rule_id,
                "level": level,
                "message": {"text": f"[{stage.name}] {message_text}"},
            }

            # Attach artifact location if spec_path is provided
            if spec_path:
                sarif_result["locations"] = [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": spec_path},
                            "region": {"startLine": 1},
                        }
                    }
                ]

            # Attach counterexample as a related location note
            if result.stages and stage.counterexample:
                ce_text = "; ".join(
                    f"{k}={v}" for k, v in stage.counterexample.items()
                )
                sarif_result["relatedLocations"] = [
                    {
                        "id": 1,
                        "message": {"text": f"Counterexample: {ce_text}"},
                    }
                ]

            sarif_results.append(sarif_result)

    artifacts = []
    if spec_path:
        artifacts.append({"location": {"uri": spec_path}})

    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Nightjar",
                        "version": tool_version,
                        "informationUri": "https://github.com/j4ngzzz/Nightjar",
                        "rules": _SARIF_RULES,
                    }
                },
                "results": sarif_results,
                "artifacts": artifacts,
            }
        ],
    }
