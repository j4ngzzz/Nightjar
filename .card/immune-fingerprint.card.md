---
card-version: "1.0"
id: immune_fingerprint
title: Immune System - Function Fingerprinter
status: draft
invariants:
  - id: INV-01
    tier: property
    statement: "similarity_score(fp1, fp2) always returns a float in [0.0, 1.0] — never negative and never greater than 1.0"
    rationale: "The score is a weighted sum of four components each in [0.0, 1.0] with weights summing to 1.0; the result is always a valid probability-like score"
  - id: INV-02
    tier: property
    statement: "similarity_score(fp1, fp2) returns 0.0 when either fingerprint is empty ({})"
    rationale: "An empty fingerprint means the function was not found or the source was unparseable; a match against nothing must score zero to prevent false matches"
  - id: INV-03
    tier: property
    statement: "fingerprint_function(source, func_name) returns {} when func_name is not found in source, or when source has a SyntaxError"
    rationale: "Callers must be able to detect 'function not found' by checking for empty dict; exceptions must not escape on invalid source"
  - id: INV-04
    tier: property
    statement: "match_functions and match_functions_with_confidence only return matches where similarity_score >= threshold (default 0.7) — no pair below the threshold appears in the result"
    rationale: "The threshold is the minimum confidence for invariant rehydration; sub-threshold matches are too structurally different to safely carry invariants"
  - id: INV-05
    tier: property
    statement: "match_functions and match_functions_with_confidence use greedy one-to-one assignment — each old function and each new function appears in the result at most once"
    rationale: "Invariants must map to exactly one new function; ambiguous many-to-one matches would apply the same invariant to multiple targets"
  - id: INV-06
    tier: property
    statement: "rehydrate_invariants only transfers invariants for functions that appear in the matches dict — functions with no match produce no output entry"
    rationale: "Invariants for unmatched functions were lost in regeneration and must be rediscovered by the mining pipeline; silent exclusion is correct behavior"
---

## Intent

Fingerprints Python functions by their structural shape (parameter names/annotations,
docstring hash, return type, called functions, cyclomatic complexity) and computes
weighted Jaccard similarity between fingerprints to identify the same function after
code regeneration.

Inspired by Scrapling's multi-field structural element matching (`element_to_dict` +
similarity scoring), adapted for Python AST nodes instead of HTML DOM elements.

Used by the immune system to rehydrate invariants discovered before regeneration onto
the corresponding functions in newly generated code, even when function names change.

References:
- D4Vinci/Scrapling `_StorageTools.element_to_dict` — structural fingerprint pattern
- D4Vinci/Scrapling `scrapling/core/storage.py` — similarity-based re-matching
- [REF-T10] icontract — runtime contract enforcement
- [REF-C09] Immune System — runtime enforcement stage

## Acceptance Criteria

- [ ] `fingerprint_function(source, name)` returns `{}` on SyntaxError or missing function
- [ ] Returned fingerprint dict contains keys: `name`, `params`, `param_names`, `docstring_hash`, `return_type`, `called_functions`, `complexity`
- [ ] `complexity` is always >= 1 (baseline of 1 + count of branch/loop/handler nodes)
- [ ] `similarity_score(fp1, fp2)` returns float in [0.0, 1.0] always
- [ ] `similarity_score({}, fp2)` == 0.0 and `similarity_score(fp1, {})` == 0.0
- [ ] Weights sum to exactly 1.0: signature 0.50, called_functions 0.30, complexity 0.15, return_type 0.05
- [ ] `match_functions` returns only pairs with score >= threshold (default 0.7)
- [ ] `match_functions` result maps each old name at most once; each new name at most once
- [ ] `match_functions_with_confidence` returns `{old_name: {"new_name": str, "confidence": float}}` format
- [ ] `rehydrate_invariants` excludes functions absent from the matches dict

## Functional Requirements

1. **fingerprint_function(source, func_name)** — parses `source` with `ast.parse`; returns `{}` on SyntaxError; walks AST for the named function; returns dict with: `name`, `params` (list of `{name, annotation, has_default}`), `param_names` (frozenset), `docstring_hash` (SHA-256[:16] or None), `return_type` (ast.unparse or None), `called_functions` (frozenset of called names), `complexity` (McCabe-like: 1 + count of If/For/While/Try/With/ExceptHandler/comprehension/TryStar nodes)
2. **similarity_score(fp1, fp2)** — returns 0.0 if either is empty; computes four components:
   - `sig_score`: Jaccard similarity on `param_names` frozensets (both empty -> 1.0; one empty -> 0.0)
   - `call_score`: Jaccard similarity on `called_functions` frozensets (same empty handling)
   - `comp_score`: `1.0 - abs(c1 - c2) / max(c1, c2, 1)` normalized absolute difference
   - `ret_score`: 1.0 if `return_type` strings are equal (including both None), else 0.0
   - Final: `0.50 * sig + 0.30 * call + 0.15 * comp + 0.05 * ret`
3. **match_functions(old_fingerprints, new_source, threshold=0.7)** — fingerprints all functions in `new_source`; scores all (old, new) pairs; filters by threshold; sorts descending by score; greedy one-to-one assignment; returns `{old_name: new_name}`
4. **match_functions_with_confidence(old_fingerprints, new_source, threshold=0.7)** — same algorithm; returns `{old_name: {"new_name": str, "confidence": round(score, 4)}}`
5. **rehydrate_invariants(old_invariants, matches)** — accepts matches in both `{old: new_name}` and `{old: {"new_name": ..., "confidence": ...}}` formats; returns `{new_name: [invariants]}` for matched functions only
