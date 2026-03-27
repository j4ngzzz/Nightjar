---
card-version: "1.0"
id: parser
title: Card Spec Parser
status: active
generated-by: nightjar-dogfood
module:
  owns: [parse_card_spec, load_constitution, parse_with_constitution]
  depends-on:
    yaml: "pyyaml>=6.0"
contract:
  inputs:
    - name: path
      type: str
      constraints: "non-empty string, must be a readable file path"
  outputs:
    - name: spec
      type: CardSpec
      schema: {}
  errors:
    - FileNotFoundError
    - ValueError
invariants:
  - id: INV-001
    tier: property
    statement: "parse_card_spec always returns a CardSpec with non-empty id for any valid .card.md file"
    rationale: "id is required field — parser must enforce this"
  - id: INV-002
    tier: property
    statement: "parse_card_spec raises ValueError for any file missing card-version or id fields"
    rationale: "Required fields must be validated"
  - id: INV-003
    tier: property
    statement: "parse_card_spec raises FileNotFoundError when path does not exist"
    rationale: "File access must fail fast with correct exception type"
  - id: INV-004
    tier: example
    statement: "parse_card_spec on tests/fixtures/payment.card.md returns spec with id='payment'"
    rationale: "Canonical fixture must parse correctly"
  - id: INV-005
    tier: property
    statement: "parse_with_constitution merges invariants without duplicating ids"
    rationale: "Module invariants take precedence over global invariants"
---

## Intent

Parse `.card.md` files (YAML frontmatter + Markdown body) into structured CardSpec objects for the verification pipeline. The parser is the entry point for all user-authored specifications — correctness here is critical.

## Acceptance Criteria

### Story 1 — Valid Spec Parsing (P0)

**As a** Nightjar user, **I want** my `.card.md` files to be parsed correctly, **so that** verification runs against my actual intent.

1. **Given** a valid `.card.md` with all required fields, **When** parse_card_spec is called, **Then** returns CardSpec with all fields populated
2. **Given** a file missing `id` field, **When** parse_card_spec is called, **Then** raises ValueError with descriptive message

### Edge Cases

- Malformed YAML frontmatter → ValueError
- File with no `---` delimiters → ValueError
- Empty invariants list → CardSpec with empty invariants (not an error)
- Constitution file missing → parse_with_constitution returns spec unchanged

## Functional Requirements

- **FR-001**: Parser MUST raise ValueError for any missing required field (card-version, id)
- **FR-002**: Parser MUST raise FileNotFoundError for non-existent paths
- **FR-003**: Parser MUST handle empty/missing optional sections gracefully
- **FR-004**: parse_with_constitution MUST deduplicate by id (module invariants win)
