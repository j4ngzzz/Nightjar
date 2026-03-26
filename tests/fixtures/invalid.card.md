---
card-version: "1.0"
id: broken-spec
title: This YAML is malformed
status: draft
invariants:
  - id: INV-001
    tier: property
    statement: "This is fine
    rationale: Missing closing quote
---

## Intent

This spec has malformed YAML frontmatter and should fail parsing.
