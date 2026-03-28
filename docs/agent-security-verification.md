# Verify Your AI Agent Code Before It Becomes the Next OpenClaw

OpenClaw hit 150,000 GitHub stars in 60 days. It also shipped **8 CVEs in its first 30 days**, including CVSS 8.8 remote code execution. One malicious link — a single click — gave an attacker full control of the victim's machine. No plugins required.

That's not a knock on the developers. It's a structural problem: agent frameworks move fast. Security verification doesn't.

## What Went Wrong

The numbers are specific enough to matter:

- **8 CVEs** in January–February 2026. One-click RCE, command injection, Docker sandbox escape, auth bypass, SSRF, path traversal.
- **341 malicious skills** published to ClawHub, OpenClaw's skill marketplace. Disguised as trading bots. Delivered Atomic macOS Stealer. Exfiltrated API keys, SSH credentials, browser passwords, and crypto wallet seeds from thousands of users.
- **42,000 exposed instances** on the public internet, 93% with authentication bypass.
- **1 Meta executive's entire email inbox**, deleted by a compromised agent.
- **35,000 email addresses and 1.5 million agent tokens** leaked from the Moltbook social network.

The attack surface isn't exotic. Every one of these vulnerabilities traces to a pattern that a verification tool could have caught: unsanitized shell command execution, missing input validation, no path restriction, auth tokens in log output, SSRF via user-controlled URLs.

The code was written. Nobody proved it was safe.

## What Verification Would Have Caught

Nightjar is a verification layer for AI-generated code. You write a spec (a `.card.md` file with invariants). Nightjar generates code, then mathematically proves the code satisfies those invariants before you ship.

For an MCP server or OpenClaw skill, a Nightjar spec expresses the security contract explicitly:

```yaml
invariants:
  - id: SEC-INV-01
    tier: property
    statement: "No tool handler executes shell commands with user-controlled input without allowlist validation"
    rationale: "CVE-2026-25593 class: command injection via unsanitized parameters"

  - id: SEC-INV-03
    tier: property
    statement: "No tool handler reads or writes files outside an explicitly configured allowed_paths list"
    rationale: "CVE-2026-26322 class: path traversal allows arbitrary file read/write"

  - id: SEC-INV-08
    tier: formal
    statement: "For all inputs i, if validate_input(i) returns False then no tool operation is performed"
    rationale: "Formal proof that the validation gate is never bypassed"
```

The `tier: formal` invariant doesn't just test — it runs Dafny, a formal verification engine from Microsoft Research, and produces a mathematical proof. Not "we tested 10,000 inputs." Proof.

Running `nightjar verify` against an MCP server that passes user input directly to `subprocess.run()` would fail SEC-INV-01 immediately, before the code ever deploys. That's the CVE-2026-25593 class caught at the source.

## The Claude Code Skill

The `nightjar-agent-security` Claude Code skill automates this. It triggers when you write:

- MCP server code (`FastMCP`, `mcp.Server`, `@mcp.tool`)
- Agent tool definitions (`@tool`, `function_call`, `tools: [`)
- OpenClaw skill files (`SKILL.md`, `skill.json`)

When triggered, the skill:
1. Detects the agent code pattern
2. Generates a `.card.md` security spec with 8 invariants covering the OpenClaw CVE classes
3. Runs `nightjar verify` against your code
4. Blocks deployment if any invariant fails

The warning it shows when you skip verification:

```
SECURITY WARNING: No Nightjar spec found for this agent code.

OpenClaw shipped without security contracts and accumulated 8 CVEs
including CVSS 8.8 RCE in its first 30 days. 341 malicious skills
compromised 9,000 installations.
```

## Install

```bash
pip install nightjar
nightjar init my-agent
nightjar verify
```

Add to CI:
```yaml
- name: Nightjar Security Verification
  run: pip install nightjar && nightjar verify
```

The skill file lives at `skills/nightjar-agent-security.md` in this repository. Copy it to your `.claude/skills/` directory to activate it in Claude Code.

The spec is the artifact. The code is disposable. Prove it before you ship it.
