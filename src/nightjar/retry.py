"""Clover-pattern retry loop + BFS proof search for Nightjar verification.

Implements the closed-loop: generate → verify → repair → re-verify.
On verification failure, collects structured error context, builds a
repair prompt, calls LLM via litellm, and re-runs the full pipeline.

Also implements BFS proof search (W1.3) as an upgrade to flat retry:
  - BFS tree where each node = partial Dafny annotation candidate
  - At each depth level, generate beam_width candidates from best node
  - Verify each; return on first pass
  - Keep best-scoring candidate for next depth
  - >30% absolute improvement over flat sampling (Scout 3 S10)

U1.2 — CEGIS Counterexample-Guided Retry [REF-NEW-03]:
  Per SpecLoop (arxiv:2603.02895), including the Dafny counterexample
  (concrete failing input values) is MORE informative than raw error messages.
  LLM can reason about "why does X=5, Y=-3 break my invariant?" rather than
  decode SMT output.
  Upgrade: formal stage FAIL → parse counterexample → CEGIS framing in prompt.

References:
- [REF-C02] Closed-loop verification (Clover pattern)
- [REF-P03] Clover paper — 87% correct acceptance, 0% false positives.
  The cycle: generate → verify → if fail, feed structured error back
  to LLM → regenerate → re-verify. Repeat up to N times.
- [REF-P06] DafnyPro — structured error format: file, line, message,
  assertion batch ID, resource units. Repair prompt includes all context.
- [REF-NEW-03] SpecLoop CEGIS (arxiv:2603.02895) — counterexample-guided retry.
- [REF-T16] litellm — all LLM calls go through litellm for model-agnosticism.
- ARCHITECTURE.md Section 4 — retry loop design, max N=5, temperature 0.2
- Scout 3 S3.1-3.2: VerMCTS/BFS proof search
- CR-12: VerMCTS arxiv:2402.08147 (NeurIPS 2024) — BFS with verifier-in-loop
- BFS-Prover arxiv:2502.03438 (ACL 2025) — BFS matches MCTS without critic

Design per ARCHITECTURE.md Section 4 + W1.3 BFS:
  Flat retry: collect errors → LLM repair → re-verify (sequential, N=5)
  BFS search: beam of candidates → expand best → verify → prune weaker branches
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Optional

import litellm

from nightjar.types import CardSpec, StageResult, VerifyResult, VerifyStatus
from nightjar.verifier import run_pipeline


# Default retry settings per ARCHITECTURE.md Section 4
DEFAULT_MAX_RETRIES = 5
REPAIR_TEMPERATURE = 0.2  # Deterministic repair [ARCHITECTURE.md]
REPAIR_MAX_TOKENS = 2048  # Output cap per ARCHITECTURE.md


# ─── CEGIS Counterexample Parsing (U1.2) ─────────────────────────────────────
# Per [REF-NEW-03] SpecLoop (arxiv:2603.02895): parse concrete failing values
# from Dafny output. Dafny counterexample format:
#   counterexample for 'func_name':
#     var1 := value1
#     var2 := value2

_CE_BLOCK_PATTERN = re.compile(
    r"counterexample for[^\n]*:\n((?:[ \t]+\w[\w.]*[ \t]*:=[ \t]*[^\n]+\n)+)",
    re.MULTILINE,
)
_CE_VAR_PATTERN = re.compile(r"[ \t]+(\w[\w.]*)[ \t]*:=[ \t]*([^\n]+)")


def parse_dafny_counterexample(output: str) -> Optional[dict[str, str]]:
    """Extract concrete counterexample values from Dafny FAIL output.

    Per [REF-NEW-03] SpecLoop: Dafny counterexample format:
      counterexample for 'func_name':
        var1 := value1
        var2 := value2

    Args:
        output: Raw Dafny verification output string.

    Returns:
        Dict of {variable_name: value_string} or None if no counterexample.
    """
    m = _CE_BLOCK_PATTERN.search(output)
    if not m:
        return None
    vals: dict[str, str] = {}
    for line in m.group(1).splitlines():
        kv = _CE_VAR_PATTERN.match(line)
        if kv:
            vals[kv.group(1).strip()] = kv.group(2).strip()
    return vals if vals else None


def extract_counterexample_from_stage(
    stage: StageResult,
) -> Optional[dict[str, str]]:
    """Extract CEGIS counterexample from a failing formal verification stage.

    Only formal stages (stage 4, name 'formal') can contain Dafny
    counterexamples. All other stages return None.

    Per [REF-NEW-03]: scans stage.errors[].message for counterexample blocks.

    Args:
        stage: A StageResult from the verification pipeline.

    Returns:
        Dict of concrete variable values, or None.
    """
    if stage.name != "formal":
        return None
    for err in stage.errors:
        msg = err.get("message", "")
        ce = parse_dafny_counterexample(msg)
        if ce:
            return ce
    return None


def build_cegis_repair_prompt(
    spec: "CardSpec",
    failed_code: str,
    verify_result: VerifyResult,
    attempt: int,
    counterexample: Optional[dict[str, str]],
) -> str:
    """Build CEGIS-style repair prompt per [REF-NEW-03] SpecLoop.

    When a counterexample is available, the prompt frames the failure as
    "Your spec fails on input X=5, Y=-3 because..." — more actionable than
    a raw SMT error message.

    Args:
        spec: Original .card.md specification.
        failed_code: Code that failed verification.
        verify_result: The failed VerifyResult with error details.
        attempt: Current retry attempt number (1-based).
        counterexample: Parsed {variable: value} dict from Dafny, or None.

    Returns:
        Formatted repair prompt string.
    """
    invariants_text = "\n".join(
        f"  - {inv.id} ({inv.tier.value}): {inv.statement}"
        for inv in spec.invariants
    )

    if counterexample:
        ce_str = ", ".join(f"{k}={v}" for k, v in counterexample.items())
        counterexample_section = (
            f"\n### Counterexample (concrete failing inputs)\n"
            f"Verification fails on: {ce_str}\n"
            f"Your implementation does not satisfy the invariants for "
            f"these specific input values. Fix the logic so it holds.\n"
        )
    else:
        # Fall back: include structured error context only
        failures = []
        for stage in verify_result.stages:
            if stage.status == VerifyStatus.FAIL:
                failures.append({
                    "stage": stage.stage,
                    "stage_name": stage.name,
                    "errors": stage.errors,
                })
        failure_block = json.dumps(failures, indent=2, default=str)
        counterexample_section = (
            f"\n### Verification Errors\n"
            f"```json\n{failure_block}\n```\n"
        )

    return f"""## CEGIS Repair Request — Attempt {attempt}

### Original Specification
Module: {spec.id} — {spec.title}
Invariants:
{invariants_text}

### Failed Code
```
{failed_code}
```
{counterexample_section}
### Instructions
Fix the code so it satisfies ALL invariants. Return ONLY the corrected code.
"""


def _call_llm_with_prompt(prompt: str) -> str:
    """Send a pre-built prompt to the LLM via litellm [REF-T16].

    Separating prompt construction from LLM dispatch allows CEGIS prompts
    to be injected cleanly at the dispatch boundary.

    Args:
        prompt: Pre-formatted repair prompt string.

    Returns:
        LLM response content string.
    """
    model = os.environ.get("NIGHTJAR_MODEL", "claude-sonnet-4-6")
    response = litellm.completion(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a code repair agent for CARD "
                    "(Contract-Anchored Regenerative Development). "
                    "Fix verification failures in generated code. "
                    "Return ONLY the corrected code."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=REPAIR_TEMPERATURE,
        max_tokens=REPAIR_MAX_TOKENS,
    )
    return response.choices[0].message.content


def _collect_failure_context(verify_result: VerifyResult) -> list[dict]:
    """Collect structured error context from all failing stages.

    Per [REF-P06] DafnyPro, the repair prompt needs:
    - Failing stage name and number
    - Error messages with file, line, type
    - Counterexamples if available
    """
    failures = []
    for stage in verify_result.stages:
        if stage.status == VerifyStatus.FAIL:
            failure = {
                "stage": stage.stage,
                "stage_name": stage.name,
                "errors": stage.errors,
            }
            if stage.counterexample:
                failure["counterexample"] = stage.counterexample
            failures.append(failure)
    return failures


def build_repair_prompt(
    spec: CardSpec,
    failed_code: str,
    verify_result: VerifyResult,
    attempt: int,
) -> str:
    """Build a structured repair prompt for the LLM.

    Per [REF-P06] DafnyPro and [REF-P03] Clover:
    - System context: original .card.md spec
    - Failed code with structured error block
    - Prior attempt count for context
    - Specific instructions to fix the identified issues

    Args:
        spec: Original .card.md specification.
        failed_code: The code that failed verification.
        verify_result: The failed VerifyResult with error details.
        attempt: Current retry attempt number (1-based).

    Returns:
        Formatted repair prompt string.
    """
    failures = _collect_failure_context(verify_result)

    # Format failure context per [REF-P06] structured error format
    failure_block = json.dumps(failures, indent=2, default=str)

    # Format invariants from spec
    invariants_text = "\n".join(
        f"  - {inv.id} ({inv.tier.value}): {inv.statement}"
        for inv in spec.invariants
    )

    return f"""## Repair Request — Attempt {attempt}

### Original Specification
Module: {spec.id} — {spec.title}
Invariants:
{invariants_text}

### Failed Code
```
{failed_code}
```

### Verification Errors (structured)
```json
{failure_block}
```

### Instructions
Fix the code above so that it satisfies ALL invariants from the specification.
The verification pipeline reported the errors shown above.
Focus on the specific failing assertions — do not rewrite unrelated code.
Return ONLY the corrected code, no explanations.
"""


def _call_repair_llm(
    spec: CardSpec,
    failed_code: str,
    verify_result: VerifyResult,
    attempt: int,
) -> str:
    """Call LLM via litellm to repair failed code using CEGIS when possible.

    Per [REF-NEW-03] SpecLoop: extracts Dafny counterexample from failing
    formal stage (if present) and uses CEGIS-style prompt. Falls back to
    generic error-message prompt for non-formal failures.

    Per [REF-T16], all LLM calls go through litellm for model-agnosticism.
    Model selected from NIGHTJAR_MODEL env var. Temperature 0.2 for
    deterministic repair per ARCHITECTURE.md Section 4.

    Args:
        spec: Original .card.md specification.
        failed_code: Code that failed verification.
        verify_result: Failed verification result with errors.
        attempt: Current attempt number.

    Returns:
        Repaired code string from LLM.
    """
    # CEGIS upgrade: extract counterexample from formal stage if available
    counterexample: Optional[dict[str, str]] = None
    for stage in verify_result.stages:
        if stage.status == VerifyStatus.FAIL:
            ce = extract_counterexample_from_stage(stage)
            if ce:
                counterexample = ce
                break

    prompt = build_cegis_repair_prompt(
        spec, failed_code, verify_result, attempt, counterexample
    )
    return _call_llm_with_prompt(prompt)


def run_with_retry(
    spec: CardSpec,
    code: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> VerifyResult:
    """Run verification with Clover-pattern retry loop [REF-C02, REF-P03].

    1. Run full verification pipeline
    2. If PASS → return success
    3. If FAIL → collect error context → build repair prompt →
       call LLM → get repaired code → re-run pipeline
    4. Repeat up to max_retries times
    5. If still failing after max_retries → return failure (human escalation)

    Args:
        spec: Parsed .card.md specification.
        code: Initial generated code to verify.
        max_retries: Maximum repair attempts (default 5 per ARCHITECTURE.md).

    Returns:
        VerifyResult with verified status and retry_count.
    """
    current_code = code

    # First attempt — no retry yet
    result = run_pipeline(spec, current_code)

    if result.verified:
        result.retry_count = 0
        return result

    # Retry loop per [REF-P03] Clover pattern
    for attempt in range(1, max_retries + 1):
        # Step 1: Call LLM for repair [REF-T16]
        repaired_code = _call_repair_llm(spec, current_code, result, attempt)

        # Step 2: Re-run full pipeline from Stage 0 [REF-P03]
        current_code = repaired_code
        result = run_pipeline(spec, current_code)

        if result.verified:
            result.retry_count = attempt
            return result

    # Exhausted retries — human escalation needed
    result.retry_count = max_retries
    return result


# ─── BFS Proof Search (W1.3) ──────────────────────────────────────────────────
# Per Scout 3 S3.1-3.2 + CR-12 (VerMCTS arxiv:2402.08147, NeurIPS 2024):
# Best-First Search with verifier-in-the-loop. Each node = partial Dafny
# annotation candidate. At each depth, generate beam_width candidates from
# best node, verify each, keep best for next depth.
# BFS-Prover (arxiv:2502.03438) shows BFS matches MCTS without a critic model.
# >30% absolute improvement over flat sampling (Scout 3 S10).


@dataclass
class BFSNode:
    """A node in the BFS proof search tree.

    Per CR-12 (VerMCTS): each node represents a partial Dafny annotation
    candidate. The score reflects how close it is to passing verification.

    Attributes:
        code: Dafny code candidate for this node.
        score: Verification progress score in [0.0, 1.0].
               1.0 = verified, approaches 1.0 as errors decrease.
        depth: Tree depth (0 = initial, 1 = first repair level, etc.)
    """
    code: str
    score: float
    depth: int = 0


def _score_verify_result(result: VerifyResult) -> float:
    """Score a VerifyResult for BFS node ranking.

    Per Scout 3 S5.3 confidence score framework (preview):
    Score reflects verification progress. Used by BFS to rank candidates.

    Scoring:
    - Verified = 1.0
    - Failed with N errors: 1/(N+1) — fewer errors = closer to proof

    Args:
        result: VerifyResult from run_pipeline().

    Returns:
        Score in [0.0, 1.0].
    """
    if result.verified:
        return 1.0
    # Count total errors across all failing stages
    total_errors = sum(
        len(stage.errors)
        for stage in result.stages
        if stage.status == VerifyStatus.FAIL
    )
    return 1.0 / (total_errors + 1)


# Default BFS parameters per Scout 3 S3.2 recommendation
DEFAULT_BFS_MAX_DEPTH = 3
DEFAULT_BFS_BEAM_WIDTH = 2


def run_bfs_search(
    spec: CardSpec,
    code: str,
    max_depth: int = DEFAULT_BFS_MAX_DEPTH,
    beam_width: int = DEFAULT_BFS_BEAM_WIDTH,
) -> VerifyResult:
    """Run BFS proof search — upgrade to flat Clover retry [CR-12, Scout 3 S3].

    Algorithm per BFS-Prover (arxiv:2502.03438) adapted for Dafny:
    1. Verify initial code
    2. For each depth level (up to max_depth):
       a. Generate beam_width repair candidates from best current node
       b. Verify each candidate immediately (verifier-in-the-loop)
       c. Return on first PASS
       d. Keep best-scoring candidate as root for next depth
    3. Return best failing result if all depths exhausted

    Total pipeline calls: 1 + max_depth * beam_width (bounded)
    Expected improvement: >30% over flat sampling (Scout 3 S10)

    Args:
        spec: Parsed .card.md specification.
        code: Initial generated code to verify.
        max_depth: Maximum search depth (generations), default 3.
        beam_width: Candidates generated per depth level, default 2.

    Returns:
        VerifyResult with verified=True if BFS finds a proof.
    """
    # Step 0: Verify initial code
    result = run_pipeline(spec, code)
    if result.verified:
        result.retry_count = 0
        return result

    # BFS: current best node (root of beam)
    best_node = BFSNode(code=code, score=_score_verify_result(result), depth=0)
    best_result = result
    total_attempts = 0

    # Search over max_depth levels
    for depth in range(1, max_depth + 1):
        depth_candidates: list[tuple[BFSNode, VerifyResult]] = []

        # Generate beam_width candidates from best node at this depth
        for candidate_idx in range(beam_width):
            total_attempts += 1
            # Generate repair candidate from best node's code + error context
            candidate_code = _call_repair_llm(
                spec, best_node.code, best_result, attempt=total_attempts
            )

            # Verify candidate (verifier-in-the-loop per CR-12)
            candidate_result = run_pipeline(spec, candidate_code)

            if candidate_result.verified:
                candidate_result.retry_count = total_attempts
                return candidate_result

            # Score for beam ranking
            score = _score_verify_result(candidate_result)
            node = BFSNode(code=candidate_code, score=score, depth=depth)
            depth_candidates.append((node, candidate_result))

        # Select best candidate for next depth (highest score = fewer errors)
        if depth_candidates:
            best_node, best_result = max(depth_candidates, key=lambda pair: pair[0].score)

    # Exhausted search — return best failing result
    best_result.retry_count = total_attempts
    return best_result
