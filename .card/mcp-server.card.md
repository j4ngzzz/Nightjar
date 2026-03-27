---
card-version: "1.0"
id: mcp-server
title: MCP Server
status: active
module:
  owns: [create_mcp_server, handle_verify_contract, handle_get_violations, handle_suggest_fix]
  depends-on:
    mcp: "mcp>=1.0"
    litellm: "litellm>=1.0"
    nightjar.types: "internal"
contract:
  inputs:
    - name: spec_path
      type: str
      constraints: "path to a .card.md spec file"
    - name: code_path
      type: str
      constraints: "path to the generated code file to verify"
    - name: stages
      type: str
      constraints: "one of 'all', 'fast', or 'formal'"
    - name: violation_id
      type: str
      constraints: "string representation of integer index into violations list"
  outputs:
    - name: json_response
      type: str
      schema: {}
invariants:
  - id: INV-01
    tier: example
    statement: "create_mcp_server registers exactly 3 tools named verify_contract, get_violations, and suggest_fix on the FastMCP instance"
    rationale: "The MCP tool set is fixed per ARCHITECTURE.md Section 7; no undocumented tools should be registered"
  - id: INV-02
    tier: property
    statement: "handle_verify_contract always returns a JSON string containing the keys: verified, stages, errors, duration_ms, retry_count"
    rationale: "AI coding assistants depend on this schema; missing keys would cause silent failures in callers"
  - id: INV-03
    tier: property
    statement: "handle_get_violations returns a JSON string with key 'violations' containing an empty list when spec_path has not been previously verified"
    rationale: "_violation_store.get(spec_path, []) must return [] for unknown keys, not raise KeyError"
  - id: INV-04
    tier: property
    statement: "handle_suggest_fix returns a JSON string with key 'error' when violation_id is not a valid integer index into the stored violations list"
    rationale: "Invalid indices must produce a structured error response, not an exception"
  - id: INV-05
    tier: property
    statement: "handle_suggest_fix reads the LLM model from os.environ.get('NIGHTJAR_MODEL') and never uses a hardcoded model string"
    rationale: "Anti-pattern: DO NOT hardcode model names — NIGHTJAR_MODEL must control all LLM calls"
  - id: INV-06
    tier: example
    statement: "After handle_verify_contract succeeds for spec_path, handle_get_violations(spec_path) returns the violations extracted from that result"
    rationale: "_violation_store persists in-memory between calls; get_violations depends on verify_contract having run first"
---

## Intent

The MCP server exposes Nightjar's verification capabilities to AI coding assistants through the Model Context Protocol. It registers three tools: `verify_contract` (runs the pipeline), `get_violations` (retrieves the last violation report), and `suggest_fix` (generates an LLM repair suggestion for a specific violation). In-memory stores (`_violation_store`, `_result_store`) persist results between tool calls within a session, allowing an AI assistant to run verification and then query violations without re-running the pipeline.

## Acceptance Criteria

### Story 1 — Verification Tool (P0)

**As an** AI coding assistant, **I want** to call `verify_contract(spec_path, code_path)` and get a structured result, **so that** I can automatically check whether generated code satisfies its spec.

1. **Given** a valid spec_path and code_path, **When** verify_contract is called, **Then** returns JSON with `verified` boolean and `stages` array
2. **Given** stages="fast", **When** verify_contract is called, **Then** only stages 0-3 run

### Story 2 — Violation Retrieval (P1)

**As an** AI coding assistant, **I want** to call `get_violations(spec_path)` after verification, **so that** I can get structured violation details without re-parsing the result.

1. **Given** verify_contract was previously called for spec_path, **When** get_violations is called, **Then** returns violations extracted from that run
2. **Given** verify_contract was never called for spec_path, **When** get_violations is called, **Then** returns `{"violations": []}`

### Story 3 — Fix Suggestion (P1)

**As an** AI coding assistant, **I want** to call `suggest_fix(spec_path, "0")` to get a repair suggestion for the first violation, **so that** I can apply the fix automatically.

1. **Given** violations exist and violation_id="0", **When** suggest_fix is called, **Then** returns JSON with suggested_code, explanation, and confidence
2. **Given** violation_id="999" with fewer violations, **When** suggest_fix is called, **Then** returns JSON with "error" key

### Edge Cases

- suggest_fix with violation_id="abc" (non-integer) → returns JSON with "error" key
- get_violations with unknown spec_path → returns {"violations": []}
- suggest_fix with no violations stored → error message includes "No violations stored"

## Functional Requirements

- **FR-001**: The MCP server MUST be created via create_mcp_server() which returns a configured FastMCP instance
- **FR-002**: verify_contract MUST store extracted violations in _violation_store[spec_path] after each run
- **FR-003**: suggest_fix MUST use max_tokens=2048 and temperature=0.2 for LLM calls
- **FR-004**: The server MUST be runnable as a stdio transport via server.run(transport="stdio")
- **FR-005**: All three tool handler functions MUST be async
