# nightjar-agent-security

Verify AI agent code with Nightjar before deployment — auto-generates security contracts and runs mathematical proof for MCP servers, OpenClaw skills, and agent tool definitions.

## TRIGGER when

- Writing or editing files that contain MCP server patterns (`FastMCP`, `mcp.Server`, `@mcp.tool`, `@server.tool`, `tool_handler`)
- Writing or editing files that define agent tools (`@tool`, `function_call`, `tools: [`, `tool_choice`)
- Writing or editing OpenClaw skill files (`SKILL.md`, `skill.json`, skill manifests)
- Writing agent config files (`agent.json`, `openclaw.json`, `soul.md`, `SOUL.md`)
- Files named matching `*agent*.py`, `*mcp*.py`, `*tool*.py`, `*skill*.py`
- User writes any of: "MCP server", "tool definition", "agent skill", "function calling", "tool handler"

## Why This Matters

OpenClaw — the open-source AI agent framework that hit 150,000+ GitHub stars in 60 days — shipped **8 CVEs in its first 30 days**, including:

- **CVE-2026-25253** (CVSS 8.8): 1-click WebSocket hijack → full RCE. Single malicious link was enough.
- **CVE-2026-25593**: Command injection via `cliPath` — unauthenticated local RCE
- **CVE-2026-24763**: Docker sandbox escape → host RCE (CVSS 8.8)
- **CVE-2026-26329**: Auth bypass — unauthenticated access to all agent functions

And those are just the CVEs. The ClawHavoc supply chain attack put **341 malicious skills** on ClawHub, compromising 9,000+ installations with Atomic macOS Stealer. The Moltbook breach leaked 35,000 emails and 1.5 million agent tokens.

**Pattern:** Agent frameworks grow fast. Security verification doesn't. Nightjar closes that gap before you ship.

## Steps

### Step 1 — Detect agent code context

Identify what kind of agent code is being written:

```
AGENT_TYPE: one of
  - mcp_server     (FastMCP / mcp.Server files)
  - openclaw_skill (SKILL.md / skill.json / openclaw.json)
  - tool_definition (files with @tool / function_call patterns)
  - agent_config   (SOUL.md / agent.json)
```

Scan the file being edited for these patterns:
- `FastMCP` or `mcp.Server` → `mcp_server`
- `@tool` or `tool_handler` → `tool_definition`
- `SKILL.md` filename or `"skill":` in JSON → `openclaw_skill`
- `SOUL.md` filename or `"soul":` in JSON → `agent_config`

### Step 2 — Generate a .card.md security spec

Create `.card/<module_name>-security.card.md` using the template below, filling in module-specific details from the code being written.

The spec MUST include these security invariants (add others as appropriate):

```yaml
---
card-version: "1.0"
id: <module_name>-security
title: <ModuleName> Security Contract
status: active
module:
  owns: [<list the tool/handler functions>]
  depends-on: {}
contract:
  inputs:
    - name: tool_input
      type: any
      constraints: "all inputs validated before execution"
  outputs:
    - name: tool_output
      type: any
      constraints: "no sensitive data leaked in output"
invariants:
  - id: SEC-INV-01
    tier: property
    statement: "No tool handler executes shell commands (exec, spawn, eval, subprocess) with user-controlled input without explicit allowlist validation"
    rationale: "CVE-2026-25593 class: command injection via unsanitized cliPath-style parameters"
  - id: SEC-INV-02
    tier: property
    statement: "All tool parameters are validated against a strict schema before any operation is performed"
    rationale: "Input validation prevents injection attacks; 47% of ClawHub skills lacked input validation (Snyk ToxicSkills report)"
  - id: SEC-INV-03
    tier: property
    statement: "No tool handler reads or writes files outside an explicitly configured allowed_paths list"
    rationale: "CVE-2026-26322 class: path traversal allows arbitrary file read/write"
  - id: SEC-INV-04
    tier: property
    statement: "Authentication tokens and API keys are never included in tool output or log messages"
    rationale: "Moltbook breach pattern: 1.5M agent tokens leaked via inadequate output sanitization"
  - id: SEC-INV-05
    tier: property
    statement: "Every tool handler that makes network requests validates the target URL against an allowlist (no SSRF)"
    rationale: "CVE-2026-26319: SSRF in OpenClaw allowed internal network access from agent context"
  - id: SEC-INV-06
    tier: example
    statement: "Calling any tool handler with a payload containing '../../../etc/passwd' returns an error, not file contents"
    rationale: "Path traversal smoke test — should fail immediately at validation layer"
  - id: SEC-INV-07
    tier: property
    statement: "The MCP server only registers the tools explicitly listed in module.owns — no dynamic tool registration from external input"
    rationale: "ClawHavoc pattern: malicious skills registered hidden tools by manipulating tool registration"
  - id: SEC-INV-08
    tier: formal
    statement: "For all inputs i, if validate_input(i) returns False then no tool operation is performed and an error is returned"
    rationale: "Formal proof that the validation gate is never bypassed"
---

## Intent

Security contract for <ModuleName>. Every tool handler must validate inputs, sanitize outputs, enforce path restrictions, and never execute unsanitized commands. This contract is the machine-checkable proof that the agent code is not vulnerable to the injection, traversal, and exfiltration patterns that caused the OpenClaw security incidents of early 2026.

## Acceptance Criteria

### Story 1 — Input Validation (P0)

**As a** security reviewer, **I want** all tool inputs validated before execution, **so that** injection attacks are structurally impossible.

1. **Given** a tool call with SQL injection payload, **When** the tool handler runs, **Then** returns error without executing any operation
2. **Given** a tool call with path traversal (`../`), **When** the handler runs, **Then** returns error without file access
3. **Given** a tool call with shell metacharacters (`; rm -rf`), **When** the handler runs, **Then** returns error without command execution

### Story 2 — Output Sanitization (P0)

**As a** security reviewer, **I want** tool outputs to never include secrets, **so that** credential exfiltration is impossible.

1. **Given** a tool response, **When** it is returned, **Then** it contains no strings matching API key patterns (`sk-`, `Bearer `, `token:`)
2. **Given** a tool response, **When** it is returned, **Then** it contains no file contents from outside allowed_paths

### Story 3 — Auth Enforcement (P1)

**As a** security reviewer, **I want** every tool call to be authenticated, **so that** CVE-2026-26329-style auth bypass is impossible.

1. **Given** a tool call without a valid auth token, **When** the handler runs, **Then** returns 401/unauthorized
2. **Given** a tool call with an expired token, **When** the handler runs, **Then** returns 401/unauthorized
```

Save the spec to `.card/<module_name>-security.card.md`.

### Step 3 — Run Nightjar verification

Run the full verification pipeline against the generated spec:

```bash
nightjar verify --spec .card/<module_name>-security.card.md
```

If `nightjar` is not installed:
```bash
pip install nightjar
nightjar verify --spec .card/<module_name>-security.card.md
```

For a fast check (skip Dafny formal proof, run in <30 seconds):
```bash
nightjar verify --spec .card/<module_name>-security.card.md --fast
```

### Step 4 — Interpret results

**If verification passes:**
- All security invariants are satisfied
- Safe to proceed with deployment
- Tell the user: "Security verification passed. Agent code satisfies all 8 security invariants."

**If verification fails with violations:**
- Show the user which invariant failed and why
- Do NOT proceed to deployment
- Ask the user: "Verification found a security issue. Fix the violation before deploying?"
- If yes, fix the code and re-run Step 3

**Common failures and fixes:**

| Failing Invariant | Likely Root Cause | Fix |
|-------------------|------------------|-----|
| SEC-INV-01 | `subprocess.run(user_input)` | Add allowlist: `if cmd not in ALLOWED_COMMANDS: raise ValueError` |
| SEC-INV-02 | No schema validation on tool params | Add Pydantic model for tool input |
| SEC-INV-03 | `open(user_path)` without path check | Add: `if not path.startswith(ALLOWED_ROOT): raise PermissionError` |
| SEC-INV-04 | Logging full request/response | Strip secrets: `re.sub(r'sk-[a-zA-Z0-9]+', '[REDACTED]', output)` |
| SEC-INV-05 | `requests.get(user_url)` | Validate URL against allowlist before fetch |
| SEC-INV-07 | Dynamic tool registration | Make tool list static, loaded from config only |

### Step 5 — Block deployment if spec is missing

If the user attempts to deploy agent code without a verified `.card.md` spec, warn them:

```
SECURITY WARNING: No Nightjar spec found for this agent code.

OpenClaw shipped without security contracts and accumulated 8 CVEs
including CVSS 8.8 RCE in its first 30 days. 341 malicious skills
compromised 9,000 installations.

Run: nightjar verify --spec .card/<module_name>-security.card.md

Or generate a spec now: nightjar generate --module <module_name>
```

## Install Instructions

```bash
# Install Nightjar
pip install nightjar

# Initialize a security spec for your agent
nightjar init <your-agent-module-name>

# Verify the agent code
nightjar verify

# Full pipeline with formal proof
nightjar build --target py
```

Add to your CI:
```yaml
# .github/workflows/agent-security.yml
- name: Nightjar Security Verification
  run: |
    pip install nightjar
    nightjar verify
```

## Nightjar MCP Server (use from Claude Code)

If you have the Nightjar MCP server running:
```bash
nightjar serve  # starts MCP server on stdio
```

Then from Claude Code:
```
verify_contract(spec_path=".card/my-agent-security.card.md", code_path="src/my_agent.py")
```

## References

- [ClawArmor CVE Analysis](https://github.com/xhls008/ClawArmor) — full OpenClaw CVE breakdown
- [ToxicSkills: Snyk Report](https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/) — 341 malicious skills analysis
- [OpenClaw Scanner](https://www.helpnetsecurity.com/2026/02/12/openclaw-scanner-open-source-tool-detects-autonomous-ai-agents/) — 42,000 exposed instances
- [Oasis Security: ClawJacked](https://www.oasis.security/blog/openclaw-vulnerability) — full agent takeover vulnerability chain
- [Nightjar Documentation](https://github.com/your-org/nightjar) — verification pipeline docs
