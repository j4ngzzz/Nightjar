---
card-version: "1.0"
id: replay
title: Experience Replay Store
status: draft
module:
  owns: [ReplayStore, store_success, retrieve_similar, get_replay_count]
  depends-on:
    sqlite3: "standard library — persistent store"
    nightjar.replay._tokenize: "internal TF-IDF tokenizer"
    nightjar.replay._cosine_similarity: "internal similarity metric"
contract:
  inputs:
    - name: spec_id
      type: str
      constraints: "non-empty module identifier"
    - name: spec_text
      type: str
      constraints: "full spec text"
    - name: prompt
      type: str
      constraints: "prompt sent to LLM"
    - name: generated_code
      type: str
      constraints: "generated code that passed verification"
    - name: verification_result
      type: dict
      constraints: "JSON-serializable verification result dict"
  outputs:
    - name: entry_id
      type: int
      schema: {autoincrement: true, positive: true}
  errors:
    - sqlite3.OperationalError
invariants:
  - id: INV-01
    tier: property
    statement: "store_success always returns a positive integer entry ID (AUTOINCREMENT PRIMARY KEY)"
    rationale: "SQLite AUTOINCREMENT guarantees monotonically increasing IDs starting at 1"
  - id: INV-02
    tier: property
    statement: "retrieve_similar returns at most k results"
    rationale: "The result list is sliced to [:k] before return — never exceeds the requested count"
  - id: INV-03
    tier: property
    statement: "retrieve_similar returns results ordered by cosine similarity descending"
    rationale: "Callers rely on the first result being the most similar — ordering must be guaranteed"
  - id: INV-04
    tier: property
    statement: "retrieve_similar returns an empty list when the store contains no entries"
    rationale: "Empty store is a valid state; callers must not receive an error, just an empty list"
  - id: INV-05
    tier: property
    statement: "cosine_similarity returns 0.0 when vectors share no common terms or either norm is zero"
    rationale: "Division by zero is guarded — no NaN or ZeroDivisionError can propagate"
  - id: INV-06
    tier: property
    statement: "store_success serializes verification_result to JSON before writing; retrieve_similar deserializes it back to a dict"
    rationale: "Round-trip serialization must preserve the dict structure for downstream consumers"
---

## Intent

Provide a SQLite-backed experience replay store for successful generation+verification runs. When a spec generates code that passes all verification stages, the (spec_id, spec_text, prompt, generated_code, verification_result) tuple is stored. On future generation runs, the top-K most similar past successes are retrieved as few-shot context using TF-IDF cosine similarity on the concatenated spec_text+prompt. This implements the AlphaVerus ([REF-P04]) self-improving loop pattern.

## Acceptance Criteria

### Story 1 — Store and Retrieve (P0)

**As a** generation pipeline, **I want** to store successful runs and retrieve similar ones, **so that** future generation can use proven examples as few-shot context.

1. **Given** 5 stored successes, **When** retrieve_similar(query, k=3) is called, **Then** returns exactly 3 results ordered by similarity descending
2. **Given** a brand-new empty database, **When** retrieve_similar is called, **Then** returns []
3. **Given** query text that matches one stored entry closely, **When** retrieve_similar is called, **Then** that entry appears first in results

### Story 2 — Similarity Computation (P0)

**As a** generation pipeline, **I want** similarity based on spec and prompt content, **so that** structurally similar specs get relevant examples.

1. **Given** two identical texts, **When** cosine_similarity is computed, **Then** returns 1.0
2. **Given** two texts with no overlapping tokens, **When** cosine_similarity is computed, **Then** returns 0.0

## Functional Requirements

- **FR-001**: MUST create the successes table with an index on spec_id if it does not exist
- **FR-002**: MUST serialize verification_result as JSON string for storage
- **FR-003**: retrieve_similar MUST score similarity on spec_text + prompt (space-separated concatenation)
- **FR-004**: MUST NOT raise on empty database — return empty list
- **FR-005**: get_count MUST return the total row count as an integer
