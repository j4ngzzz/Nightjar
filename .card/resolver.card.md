---
card-version: "1.0"
id: resolver
title: Module Dependency Resolver
status: draft
invariants:
  - id: INV-01
    tier: formal
    statement: "forall module_id :: if resolve_build_order returns successfully, then module_id appears exactly once in the result"
    rationale: "Kahn's algorithm produces a permutation of input nodes — no duplicates, no omissions"
  - id: INV-02
    tier: formal
    statement: "forall pair (A, B) :: if A depends_on B in the spec set, then B appears before A in the resolved order"
    rationale: "The topological sort guarantee — dependencies are always built before their dependents"
  - id: INV-03
    tier: property
    statement: "resolve_build_order raises CyclicDependencyError if and only if there exists a cycle in the in-set dependency graph"
    rationale: "Kahn's algorithm detects cycles by checking len(result) != len(module_ids) after exhausting the queue"
  - id: INV-04
    tier: property
    statement: "External dependencies (module IDs not present in the spec set) are excluded from the resolved build order"
    rationale: "build_dependency_graph includes all declared depends_on keys, but resolve_build_order filters to in_set_deps only"
  - id: INV-05
    tier: example
    statement: "resolve_build_order returns an empty list when given an empty spec list"
    rationale: "Empty input is a valid base case — no modules means no build order"
  - id: INV-06
    tier: property
    statement: "scan_and_resolve skips constitution.card.md — the constitution is not a buildable module"
    rationale: "The constitution contains project-level invariants and is explicitly excluded from the module build graph"
  - id: INV-07
    tier: property
    statement: "For modules with equal in-set dependency counts, build order is deterministic (lexicographic by module ID)"
    rationale: "queue.sort() after each dequeue ensures identical runs produce identical orderings"
---

## Intent

Scans `.card.md` specification files, constructs a directed dependency graph from
`module.depends-on` fields, and produces a topologically sorted build order via
Kahn's algorithm. Detects and reports circular dependencies with a clear error
identifying the cycle participants.

This module enables multi-module projects to build in dependency order without
manual ordering.

References:
- ARCHITECTURE.md Section 2 (module boundary with depends-on)
- [REF-T25] Spec Kit conventions for module dependencies
- Kahn, A.B. (1962) — Topological sorting of large networks

## Acceptance Criteria

- [ ] `resolve_build_order` returns modules in valid topological order for all DAGs
- [ ] `CyclicDependencyError` is raised with the cycle participant module IDs named
- [ ] External dependencies (not in the spec set) are silently ignored
- [ ] Empty input produces an empty list (no error)
- [ ] `constitution.card.md` is always excluded from scan results
- [ ] Build order for equal-priority modules is lexicographic (deterministic)

## Functional Requirements

1. **build_dependency_graph(specs)** — builds `dict[str, set[str]]` mapping module ID to its declared depends_on keys; includes external dependency names (not filtered here)
2. **resolve_build_order(specs)** — implements Kahn's algorithm:
   - filters dependency graph to in-set deps only (external deps assumed satisfied)
   - computes in-degrees as count of in-set dependencies per module
   - initializes queue with zero-degree modules, sorted lexicographically
   - repeatedly dequeues, appends to result, decrements dependents' in-degrees
   - re-sorts queue after each update for deterministic ordering
   - raises `CyclicDependencyError` if `len(result) != len(module_ids)` at termination
3. **scan_and_resolve(card_dir)** — scans `*.card.md` in the given directory, skips `constitution.card.md`, parses each with `parse_card_spec`, then calls `resolve_build_order` on the collected specs; returns list of `(path, CardSpec)` tuples in resolved order
4. **CyclicDependencyError** — exception class; message includes sorted list of modules participating in the cycle
