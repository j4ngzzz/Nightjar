"""Shared types for Nightjar. All builders import from here.

DO NOT modify without Coordinator approval — this is the shared interface.

References:
- [REF-C01] Tiered invariants — CARD's invention
- [REF-T03] Hypothesis PBT for property tier
- [REF-T01] Dafny mathematical proof for formal tier
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class InvariantTier(str, Enum):
    """[REF-C01] Tiered invariants — CARD's invention."""
    EXAMPLE = "example"    # Unit test only
    PROPERTY = "property"  # Hypothesis PBT auto-generated [REF-T03]
    FORMAL = "formal"      # Dafny mathematical proof [REF-T01]


class VerifyStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    TIMEOUT = "timeout"


class TrustLevel(str, Enum):
    """SkillFortify graduated trust levels [Scout 9 W2-2].

    Thresholds aligned with SkillFortify's trust algebra
    (qualixar/skillfortify src/skillfortify/core/trust/models.py):
      LEVEL_FORMAL_THRESHOLD     = 0.75
      LEVEL_COMMUNITY_THRESHOLD  = 0.50
      LEVEL_SIGNED_THRESHOLD     = 0.25

    References:
    - arxiv:2603.00195 DY-Skill threat model — trust algebra with formal properties
    - qualixar/skillfortify src/skillfortify/core/trust/models.py
    """
    FORMALLY_VERIFIED = "FORMALLY_VERIFIED"  # score >= 0.75 — Stage 4 Dafny proof passed
    PROPERTY_VERIFIED = "PROPERTY_VERIFIED"  # score >= 0.50 — Stage 3 PBT passed
    SCHEMA_VERIFIED   = "SCHEMA_VERIFIED"    # score >= 0.25 — Stage 2 schema passed
    UNVERIFIED        = "UNVERIFIED"         # score <  0.25 — preflight/deps only or nothing


@dataclass
class Invariant:
    id: str
    tier: InvariantTier
    statement: str
    rationale: str = ""


@dataclass
class ContractInput:
    name: str
    type: str
    constraints: str = ""


@dataclass
class ContractOutput:
    name: str
    type: str
    schema: dict = field(default_factory=dict)


@dataclass
class ModuleBoundary:
    owns: list[str] = field(default_factory=list)
    depends_on: dict[str, str] = field(default_factory=dict)
    excludes: list[str] = field(default_factory=list)


@dataclass
class Contract:
    inputs: list[ContractInput] = field(default_factory=list)
    outputs: list[ContractOutput] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    events_emitted: list[str] = field(default_factory=list)


@dataclass
class CardSpec:
    """Parsed .card.md specification."""
    card_version: str
    id: str
    title: str
    status: str
    module: ModuleBoundary
    contract: Contract
    invariants: list[Invariant]
    constraints: dict[str, str] = field(default_factory=dict)
    intent: str = ""
    acceptance_criteria: str = ""
    functional_requirements: str = ""


@dataclass
class StageResult:
    """Result from one verification stage."""
    stage: int
    name: str
    status: VerifyStatus
    duration_ms: int = 0
    errors: list[dict] = field(default_factory=list)
    counterexample: Optional[dict] = None


@dataclass
class VerifyResult:
    """Result from the full verification pipeline."""
    verified: bool
    stages: list[StageResult] = field(default_factory=list)
    total_duration_ms: int = 0
    retry_count: int = 0
    confidence: Optional[Any] = None  # ConfidenceScore; Any avoids circular import
    trust_level: Optional["TrustLevel"] = None  # SkillFortify graduated trust [Scout 9 W2-2]
