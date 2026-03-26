"""NL Intent Router — parse and classify natural language intent.

Step 1 (parse_nl_intent): Path-aware slicing of NL intent into structured
NLIntent. Inspired by ContextCov coverage-guided context selection
(CR-02, CC-BY-4.0, arxiv 2603.00822).

Step 3 (classify_invariant): Classify invariant statements into:
  NUMERICAL   — bounds, arithmetic, counts
  BEHAVIORAL  — pre/postcondition style, I/O relationships
  STATE       — always/never invariants, lifecycle properties
  FORMAL      — logical quantifiers (for all, there exists)

Clean-room implementation. No code copied from ContextCov or NL2Contract.

References:
- CR-02: ContextCov | License: CC-BY-4.0 | Source: arxiv 2603.00822
- CR-03: NL2Contract | License: Research paper | Source: arxiv 2510.12702
- [REF-P14] NL2Contract: LLMs generate full functional contracts from NL
- Scout 4 F1: ContextCov path-aware slicing for invariant coverage
"""

import re
from dataclasses import dataclass, field
from enum import Enum


# ── Types ─────────────────────────────────────────────────────────────────────


@dataclass
class NLIntent:
    """Structured representation of a parsed NL intent string.

    Produced by parse_nl_intent() (Step 1 of nightjar auto pipeline).
    Inspired by ContextCov path-aware slicing: each field is a
    coverage-relevant context slice of the original NL string.

    CR-02: ContextCov (CC-BY-4.0, arxiv 2603.00822)
    """

    raw: str
    """Original NL string, preserved unchanged."""

    subject: str
    """Core noun phrase — what is being built (e.g., 'payment processor')."""

    inferred_inputs: list[str] = field(default_factory=list)
    """Inferred parameter names/types from context words."""

    inferred_outputs: list[str] = field(default_factory=list)
    """Inferred return types from 'returns', 'outputs', 'produces' phrases."""

    behaviors: list[str] = field(default_factory=list)
    """Behavioral phrases extracted from the NL string."""


class InvariantClass(str, Enum):
    """Invariant domain classification.

    Maps to the four generator domains:
    - NUMERICAL → icontract bounds + Hypothesis numeric strategies
    - BEHAVIORAL → icontract @require/@ensure
    - STATE → icontract @invariant for persistent state
    - FORMAL → Dafny requires/ensures (optional, auto-suggested only)

    Scout 4 honest assessment: FORMAL tier is optional — LLMs still struggle
    with complex Dafny invariants. Generate but mark as optional.
    """

    NUMERICAL = "numerical"
    BEHAVIORAL = "behavioral"
    STATE = "state"
    FORMAL = "formal"


# ── Keyword sets for classification ───────────────────────────────────────────

# Words strongly indicative of NUMERICAL invariants
_NUMERICAL_KEYWORDS = frozenset({
    "positive", "negative", "zero", "nonzero", "non-zero",
    "greater", "less", "larger", "smaller", "bigger",
    "maximum", "minimum", "max", "min", "bound", "bounds",
    "bounded", "unbounded", "finite", "infinite",
    "count", "size", "length", "height", "width", "depth",
    "sum", "total", "average", "mean", "median",
    "percent", "percentage", "ratio", "rate",
    "non-negative", "nonnegative",
    "exceed", "exceeds", "overflow", "underflow",
})

_NUMERICAL_OPERATORS = frozenset({">=", "<=", ">", "<", "!=", "==", "="})

# Words strongly indicative of BEHAVIORAL invariants (pre/postconditions)
_BEHAVIORAL_KEYWORDS = frozenset({
    "returns", "return", "output", "outputs", "produces", "result",
    "input", "inputs", "parameter", "parameters", "argument", "arguments",
    "require", "requires", "ensure", "ensures",
    "must", "should", "shall",
    "when", "given", "after", "before", "if", "then",
    "valid", "invalid", "null", "none", "empty", "nonempty", "non-empty",
    "not none", "not null",
    "succeed", "succeeds", "fail", "fails",
    "raises", "throws", "exception",
})

# Words strongly indicative of STATE invariants
_STATE_KEYWORDS = frozenset({
    "always", "never", "throughout", "invariant",
    "remain", "remains", "persist", "persists", "maintain", "maintains",
    "constant", "unchanged", "stable",
    "every time", "each time", "all the time",
    "lifecycle", "lifetime",
    "state", "states", "transition", "transitions",
    "pending", "completed", "active", "inactive", "started", "stopped",
})

# Words strongly indicative of FORMAL invariants
_FORMAL_KEYWORDS = frozenset({
    "for all", "for any", "for every", "forall",
    "there exists", "there exist", "exists", "iff",
    "implies", "implication",
    "mathematically", "formally", "provably",
    "bijection", "injection", "surjection",
})

# Output-inference patterns
_OUTPUT_PATTERNS = [
    re.compile(r"returns?\s+(?:a\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"outputs?\s+(?:a\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"produces?\s+(?:a\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"(?:yields?|gives?)\s+(?:a\s+)?(\w+)", re.IGNORECASE),
]

# Input-inference patterns
_INPUT_PATTERNS = [
    re.compile(r"(?:takes?|accepts?|receives?)\s+(?:a\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"given\s+(?:a\s+)?(\w+)", re.IGNORECASE),
    re.compile(r"with\s+(?:a\s+)?(\w+)\s+(?:input|parameter|argument)", re.IGNORECASE),
]

# Behavior extraction: clause-like phrases
_BEHAVIOR_PATTERNS = [
    re.compile(r"(?:that|which|and)\s+([\w\s]+)", re.IGNORECASE),
    re.compile(r"(?:so that|in order to)\s+([\w\s]+)", re.IGNORECASE),
]

# Vague generic terms that lower specificity in ranking
VAGUE_TERMS = frozenset({
    "valid", "correct", "proper", "appropriate",
    "good", "right", "ok", "okay", "fine",
    "reasonable", "sensible", "suitable",
})

# Boundary-condition terms that boost ranking
BOUNDARY_TERMS = frozenset({
    "null", "none", "empty", "zero", "max", "min",
    "overflow", "underflow", "negative", "boundary",
    "edge", "corner", "extreme",
})


# ── parse_nl_intent ───────────────────────────────────────────────────────────


def parse_nl_intent(nl_string: str) -> NLIntent:
    """Parse a natural language intent string into structured NLIntent.

    Path-aware slicing (ContextCov, CR-02): extracts subject, inferred I/O,
    and behavioral phrases as coverage-relevant context slices.

    The slicing is intentionally lightweight — we don't build a full AST
    (NL has no grammar), but we extract the fragments most relevant to
    invariant generation: subject, I/O types, and behavioral constraints.

    Args:
        nl_string: Natural language description of the software component.
            Example: "Build a payment processor that charges credit cards"

    Returns:
        NLIntent with structured slices of the intent.

    Raises:
        ValueError: If nl_string is empty or whitespace-only.

    References:
        CR-02: ContextCov (CC-BY-4.0, arxiv 2603.00822)
    """
    if not nl_string or not nl_string.strip():
        raise ValueError("intent string must not be empty")

    stripped = nl_string.strip()

    subject = _extract_subject(stripped)
    inferred_inputs = _infer_inputs(stripped)
    inferred_outputs = _infer_outputs(stripped)
    behaviors = _extract_behaviors(stripped)

    return NLIntent(
        raw=stripped,
        subject=subject,
        inferred_inputs=inferred_inputs,
        inferred_outputs=inferred_outputs,
        behaviors=behaviors,
    )


def _extract_subject(text: str) -> str:
    """Extract the core noun phrase subject from the NL text.

    Removes common verb prefixes (Build, Create, Implement, Make) and
    subordinate clauses (starting with 'that', 'which', 'so that').
    """
    # Strip leading imperative verbs
    stripped = re.sub(
        r"^(?:build|create|implement|make|design|write|develop|add|provide)\s+(?:a\s+|an\s+)?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    # Take only up to the first subordinate clause
    subordinate_match = re.split(r"\s+(?:that|which|so that|in order to|to)\s+", stripped, maxsplit=1)
    subject = subordinate_match[0].strip()

    # Remove trailing articles
    subject = re.sub(r"^(?:a|an|the)\s+", "", subject, flags=re.IGNORECASE)

    return subject if subject else text.split()[0]


def _infer_inputs(text: str) -> list[str]:
    """Infer input parameter names/types from the NL text."""
    inputs = []
    for pattern in _INPUT_PATTERNS:
        for match in pattern.finditer(text):
            word = match.group(1).lower()
            if word not in {"a", "an", "the"} and word not in inputs:
                inputs.append(word)
    return inputs


def _infer_outputs(text: str) -> list[str]:
    """Infer output types from the NL text."""
    outputs = []
    for pattern in _OUTPUT_PATTERNS:
        for match in pattern.finditer(text):
            word = match.group(1).lower()
            if word not in {"a", "an", "the"} and word not in outputs:
                outputs.append(word)
    return outputs


def _extract_behaviors(text: str) -> list[str]:
    """Extract behavioral phrases from the NL text."""
    behaviors = []
    for pattern in _BEHAVIOR_PATTERNS:
        for match in pattern.finditer(text):
            phrase = match.group(1).strip()
            if len(phrase) > 3 and phrase not in behaviors:
                behaviors.append(phrase)
    return behaviors[:5]  # Limit to top 5 behavioral phrases


# ── classify_invariant ────────────────────────────────────────────────────────


def classify_invariant(statement: str) -> InvariantClass:
    """Classify an invariant statement into a domain category.

    Classification determines which generator handles the invariant:
    - NUMERICAL → icontract bounds + Hypothesis numeric strategies
    - BEHAVIORAL → icontract @require/@ensure
    - STATE → icontract @invariant for lifecycle invariants
    - FORMAL → Dafny requires/ensures (optional)

    Uses keyword-based classification with priority ordering:
    FORMAL > STATE > NUMERICAL > BEHAVIORAL (most specific → least specific)

    Args:
        statement: Natural language invariant statement to classify.

    Returns:
        InvariantClass enum value.

    References:
        CR-03: NL2Contract (arxiv 2510.12702) — classification schema
        Scout 4 F9: intent router classifies into these four domains
    """
    if not statement or not statement.strip():
        return InvariantClass.BEHAVIORAL

    lower = statement.lower()
    tokens = set(re.findall(r"\b[\w-]+\b", lower))

    # FORMAL: highest priority — logical quantifiers are unambiguous
    if _has_formal_markers(lower):
        return InvariantClass.FORMAL

    # STATE: 'always', 'never', 'throughout', 'transition' language
    state_score = len(tokens & _STATE_KEYWORDS)
    # Check multi-word phrases too
    if any(phrase in lower for phrase in ("always", "never", "throughout", "every time", "each time", "lifecycle", "transition")):
        state_score += 2

    # NUMERICAL: numeric operators or numeric keywords
    numerical_score = len(tokens & _NUMERICAL_KEYWORDS)
    if any(op in statement for op in _NUMERICAL_OPERATORS):
        numerical_score += 3

    # BEHAVIORAL: pre/postcondition keywords (default)
    behavioral_score = len(tokens & _BEHAVIORAL_KEYWORDS)

    # Resolve by highest score, with BEHAVIORAL as default
    if state_score > numerical_score and state_score > behavioral_score:
        return InvariantClass.STATE
    # Prefer NUMERICAL on tie — numerical keywords are highly specific indicators
    if numerical_score >= behavioral_score and numerical_score > 0:
        return InvariantClass.NUMERICAL
    return InvariantClass.BEHAVIORAL


def _has_formal_markers(lower_text: str) -> bool:
    """Check for formal logic quantifiers in the text."""
    formal_phrases = (
        "for all", "for any", "for every", "there exists",
        "there exist", "forall", " iff ", "implies",
        "\u2200",  # ∀
        "\u2203",  # ∃
    )
    return any(phrase in lower_text for phrase in formal_phrases)
