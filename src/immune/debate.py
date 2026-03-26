"""Adversarial debate for invariant validation.

Task U2.3: Proposer + skeptic LLM agents — only invariants that survive
the skeptic challenge enter the spec.

TradingAgents adversarial debate pattern:
  1. Proposer argues why the invariant is always true
  2. Skeptic tries to find a counterexample or refutation
  3. Verdict parsed from first word of skeptic response:
       REFUTED → invariant rejected
       STANDS  → invariant accepted

Two litellm calls per invariant. On any LLM error the invariant
survives by default (conservative: never drop on infrastructure failure).

Wire: miner.py → quality_scorer.py → debate.py → enricher.py

References:
  TradingAgents adversarial debate pattern
  (https://github.com/TauricResearch/TradingAgents)
  [REF-T16] litellm unified LLM API
"""

from __future__ import annotations

from dataclasses import dataclass

import litellm

from immune.enricher import CandidateInvariant


# ── Constants ─────────────────────────────────────────────────────────────────

_TEMPERATURE = 0.2
_MAX_TOKENS = 256

_PROPOSER_SYSTEM = """\
You are a formal verification expert.
Given a program invariant, argue concisely why it must always hold.
Be specific — reference the invariant expression directly.
"""

_SKEPTIC_SYSTEM = """\
You are a strict adversarial reviewer of program invariants.
Given an invariant and a proposer's argument, decide whether the invariant
can be refuted by a counterexample.

Respond with EXACTLY one of these words as your FIRST word:
  REFUTED  — if you can identify a concrete counterexample or flaw
  STANDS   — if you cannot refute the invariant

Then explain your reasoning briefly.
"""


# ── DebateResult ──────────────────────────────────────────────────────────────


@dataclass
class DebateResult:
    """Outcome of one adversarial debate round.

    TradingAgents pattern: proposer argues, skeptic challenges,
    verdict determines whether the invariant enters the spec.
    """

    candidate: CandidateInvariant
    survived: bool    # True if skeptic could not refute
    challenge: str    # Full skeptic response
    reason: str       # Human-readable verdict summary


# ── Internal helpers ──────────────────────────────────────────────────────────


def _proposer_call(expression: str, model: str) -> str:
    """Ask the proposer to defend the invariant."""
    try:
        resp = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": _PROPOSER_SYSTEM},
                {"role": "user", "content": f"Invariant: {expression}"},
            ],
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"(proposer error: {e})"


def _skeptic_call(expression: str, defence: str, model: str) -> str:
    """Ask the skeptic to challenge the invariant."""
    user_msg = (
        f"Invariant: {expression}\n\n"
        f"Proposer's argument:\n{defence}\n\n"
        "Can you refute this? Answer REFUTED or STANDS first."
    )
    try:
        resp = litellm.completion(
            model=model,
            messages=[
                {"role": "system", "content": _SKEPTIC_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"(skeptic error: {e})"


def _parse_verdict(skeptic_response: str) -> bool:
    """Return True (survived) if skeptic says STANDS, False if REFUTED.

    Case-insensitive match on the first word of the response.
    Defaults to survived=True on unrecognised responses (conservative).
    """
    first_word = skeptic_response.strip().split()[0].upper() if skeptic_response.strip() else ""
    if first_word.startswith("REFUTED"):
        return False
    # STANDS, or anything that isn't clearly REFUTED → survived
    return True


# ── Public API ────────────────────────────────────────────────────────────────


def debate_invariant(
    candidate: CandidateInvariant,
    model: str,
) -> DebateResult:
    """Run one adversarial debate round for a single invariant.

    Makes exactly two litellm calls: proposer then skeptic.
    On any LLM error the invariant survives (conservative default).

    Args:
        candidate: Candidate invariant from miner/quality_scorer.
        model:     litellm model identifier.

    Returns:
        DebateResult with survived=True/False and the skeptic's challenge.
    """
    try:
        defence = _proposer_call(candidate.expression, model)
        challenge = _skeptic_call(candidate.expression, defence, model)
        survived = _parse_verdict(challenge)
        reason = "skeptic could not refute" if survived else "refuted by skeptic"
    except Exception as e:
        # Infrastructure failure — conservative: keep the invariant
        return DebateResult(
            candidate=candidate,
            survived=True,
            challenge="",
            reason=f"error during debate — defaulting to survived: {e}",
        )

    return DebateResult(
        candidate=candidate,
        survived=survived,
        challenge=challenge,
        reason=reason,
    )


def debate_invariants(
    candidates: list[CandidateInvariant],
    model: str,
) -> list[DebateResult]:
    """Run adversarial debate on a batch of invariant candidates.

    Args:
        candidates: Candidates from miner/quality_scorer output.
        model:      litellm model identifier.

    Returns:
        List of DebateResult, same length and order as input.
    """
    return [debate_invariant(c, model) for c in candidates]


def filter_by_debate(
    candidates: list[CandidateInvariant],
    model: str,
) -> list[CandidateInvariant]:
    """Filter out invariants refuted by the skeptic agent.

    Wires into the immune pipeline after quality_scorer and before
    enricher: only debate survivors proceed to LLM enrichment.

    Args:
        candidates: Quality-filtered invariant candidates.
        model:      litellm model identifier.

    Returns:
        Candidates that survived adversarial debate, original order preserved.
    """
    return [
        dr.candidate
        for dr in debate_invariants(candidates, model)
        if dr.survived
    ]
