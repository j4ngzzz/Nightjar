---
card-version: "1.0"
id: intent_router
title: NL Intent Router
status: draft
invariants:
  - id: INV-01
    tier: property
    statement: "parse_nl_intent raises ValueError if and only if nl_string is empty or whitespace-only"
    rationale: "Empty intent has no subject or behaviors to extract; failing fast prevents nonsensical NLIntent objects"
  - id: INV-02
    tier: property
    statement: "parse_nl_intent preserves the input string unchanged in NLIntent.raw (after strip)"
    rationale: "The raw field is the audit trail — downstream stages can always recover the original intent"
  - id: INV-03
    tier: property
    statement: "classify_invariant returns InvariantClass.BEHAVIORAL for empty or whitespace-only statements"
    rationale: "BEHAVIORAL is the safe default — it produces icontract @require/@ensure which are the most general invariant form"
  - id: INV-04
    tier: property
    statement: "classify_invariant returns FORMAL when the statement contains a logical quantifier (for all, there exists, forall, iff, implies, ∀, ∃)"
    rationale: "Logical quantifiers are unambiguous formal logic markers; FORMAL has highest priority in the classification hierarchy"
  - id: INV-05
    tier: property
    statement: "classify_invariant priority order is FORMAL > STATE > NUMERICAL > BEHAVIORAL — a statement matching multiple classes resolves to the highest priority"
    rationale: "Priority ordering prevents cross-class ambiguity; FORMAL markers are strongest, BEHAVIORAL is the fallback"
  - id: INV-06
    tier: property
    statement: "parse_nl_intent.behaviors list contains at most 5 entries"
    rationale: "Behavioral phrase extraction is capped at 5 to limit downstream context size; the 5 most prominent phrases are sufficient"
  - id: INV-07
    tier: example
    statement: "classify_invariant returns NUMERICAL when the statement contains a comparison operator (>=, <=, >, <, !=, ==)"
    rationale: "Numeric operators provide a strong +3 score boost, making NUMERICAL the dominant classification for any statement with a comparison"
---

## Intent

Two-function NL processing layer for the Nightjar auto pipeline:

- **parse_nl_intent** (Step 1): Parses a natural language intent string into a
  structured `NLIntent` using path-aware slicing inspired by ContextCov (CR-02).
  Extracts subject, inferred inputs/outputs, and behavioral phrases.

- **classify_invariant** (Step 3): Classifies invariant statements into one of four
  domains (NUMERICAL, BEHAVIORAL, STATE, FORMAL) to route to the correct generator.
  Based on NL2Contract classification schema (CR-03).

Clean-room implementation — no code copied from ContextCov or NL2Contract.

References:
- CR-02: ContextCov (CC-BY-4.0, arxiv 2603.00822) — path-aware slicing
- CR-03: NL2Contract (arxiv 2510.12702) — classification schema
- [REF-P14] NL2Contract: LLMs generate full functional contracts from NL
- Scout 4 F1: ContextCov path-aware slicing for invariant coverage
- Scout 4 F9: intent router classifies into the four generator domains

## Acceptance Criteria

- [ ] `parse_nl_intent("")` raises `ValueError`
- [ ] `parse_nl_intent("Build a payment processor...")` sets `raw` to stripped input
- [ ] `parse_nl_intent` extracts subject by removing leading imperative verbs and subordinate clauses
- [ ] `parse_nl_intent` infers outputs from "returns/outputs/produces/yields/gives" patterns
- [ ] `parse_nl_intent` infers inputs from "takes/accepts/receives/given/with X input" patterns
- [ ] `parse_nl_intent` limits behaviors list to 5 entries
- [ ] `classify_invariant` returns FORMAL for "for all x, result > 0"
- [ ] `classify_invariant` returns NUMERICAL for "result >= 0"
- [ ] `classify_invariant` returns STATE for "always maintains sorted order"
- [ ] `classify_invariant` returns BEHAVIORAL for "returns a valid token when credentials are correct"

## Functional Requirements

1. **NLIntent** — dataclass with (raw: str, subject: str, inferred_inputs: list[str], inferred_outputs: list[str], behaviors: list[str]); all list fields default to empty
2. **InvariantClass** — four-valued enum: NUMERICAL, BEHAVIORAL, STATE, FORMAL (values lowercase strings)
3. **parse_nl_intent(nl_string) -> NLIntent** — raises ValueError on empty/whitespace; applies _extract_subject, _infer_inputs, _infer_outputs, _extract_behaviors
4. **_extract_subject(text)** — strips leading imperative verbs (build/create/implement/make/design/write/develop/add/provide), splits on first subordinate clause (that/which/so that/in order to/to), strips trailing articles; falls back to first word
5. **_infer_outputs(text)** — matches "returns?/outputs?/produces?/yields?/gives?" followed by optional article and word; deduplicates; excludes articles
6. **_infer_inputs(text)** — matches "takes?/accepts?/receives?/given/with X input" patterns; deduplicates; excludes articles
7. **_extract_behaviors(text)** — extracts clauses after "that/which/and" and "so that/in order to"; returns at most 5 phrases longer than 3 characters
8. **classify_invariant(statement) -> InvariantClass** — returns BEHAVIORAL for empty input; checks _has_formal_markers first (FORMAL wins); scores STATE, NUMERICAL, BEHAVIORAL by keyword overlap; numerical score gets +3 bonus for any comparison operator; resolves by highest score with BEHAVIORAL as default; NUMERICAL wins ties with BEHAVIORAL when numerical_score > 0
9. **_has_formal_markers(lower_text)** — checks for "for all/any/every", "there exists/exist", "forall", " iff ", "implies", "∀" (U+2200), "∃" (U+2203)
10. **Keyword sets** — VAGUE_TERMS and BOUNDARY_TERMS are defined for external ranking use (not used internally by classify_invariant)
