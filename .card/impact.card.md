---
card-version: "1.0"
id: impact
title: Offline Blast-Radius Analysis
status: draft
module:
  owns: [blast_radius, build_import_graph, spec_blast_radius, format_blast_radius]
  depends-on:
    ast: "standard library — parse Python source"
    pathlib: "standard library — file traversal"
    collections: "standard library — deque for BFS"
contract:
  inputs:
    - name: changed_file
      type: str
      constraints: "path to a .py file; can be relative or absolute"
    - name: project_root
      type: str
      constraints: "valid directory path; defaults to '.'"
  outputs:
    - name: affected_files
      type: list[str]
      schema: {sorted: true, absolute_paths: true}
  errors:
    - OSError
    - SyntaxError
invariants:
  - id: INV-01
    tier: property
    statement: "blast_radius never includes the changed_file itself in its return value"
    rationale: "The changed file is the source of change, not an affected dependent"
  - id: INV-02
    tier: property
    statement: "blast_radius returns a sorted list of absolute file paths"
    rationale: "Sorted output is deterministic; absolute paths are unambiguous regardless of cwd"
  - id: INV-03
    tier: property
    statement: "build_import_graph returns a dict keyed by absolute file paths covering every .py file under project_root"
    rationale: "The graph must be complete — missing files would produce false negatives in blast-radius analysis"
  - id: INV-04
    tier: property
    statement: "_extract_imports returns an empty set for files with SyntaxError or OSError — it never raises"
    rationale: "A single unreadable file must not abort the full graph construction"
  - id: INV-05
    tier: property
    statement: "Relative imports (level > 0) are excluded from the extracted import set"
    rationale: "Relative imports cannot be resolved to absolute module names without package context; omitting them avoids false blast-radius matches"
  - id: INV-06
    tier: property
    statement: "blast_radius BFS visits each file at most once — no infinite loops on circular imports"
    rationale: "The affected set tracks visited nodes; a file already in affected is never re-queued"
---

## Intent

Provide fully offline import-graph blast-radius analysis without any external service dependency. Walk all Python files in the project, parse import statements with `ast`, build a reverse import graph, and BFS from a changed file to find every transitive dependent. Also supports spec-ID blast-radius by scanning AST constant nodes for string literals.

## Acceptance Criteria

### Story 1 — Import Graph (P0)

**As a** developer, **I want** to know which files import a module I changed, **so that** I can assess risk before committing.

1. **Given** file A imports file B imports file C, **When** blast_radius is called on C, **Then** returns [A, B] (both direct and transitive dependents)
2. **Given** a file with a SyntaxError, **When** build_import_graph is called, **Then** the errored file maps to an empty set and processing continues normally
3. **Given** changed_file is not imported by anyone, **When** blast_radius is called, **Then** returns empty list

### Story 2 — Spec Blast Radius (P0)

**As a** CI pipeline, **I want** to find all files that reference a spec ID string, **so that** I can verify spec-coupled tests are re-run.

1. **Given** spec_id "payment" appears as string literal in 2 files, **When** spec_blast_radius is called, **Then** returns those 2 file paths sorted

## Functional Requirements

- **FR-001**: MUST work fully offline — no network calls, no external services
- **FR-002**: MUST handle SyntaxError and OSError in any .py file gracefully (return empty set for that file)
- **FR-003**: MUST exclude relative imports from the reverse graph
- **FR-004**: BFS MUST terminate on circular import graphs
- **FR-005**: format_blast_radius MUST include the count of affected files in its first line
