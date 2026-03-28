# Nightjar MCP Server — Marketplace Listing

## Tool Name
**Nightjar**

## Tagline
Formally verify AI-generated code. Not tested — proved.

## Description

Nightjar is a contract-anchored verification layer for AI-generated code. It exposes a 6-stage mathematical verification pipeline as MCP tools, letting any AI coding assistant instantly check whether generated code satisfies a formal specification.

Developers write specs in `.card.md` files. AI generates code. Nightjar proves the code satisfies the specs — using property-based testing (Hypothesis), schema validation (Pydantic), symbolic execution (CrossHair), and formal proof (Dafny).

The MCP server makes this pipeline available as three tools any Claude Code session can call.

---

## Tools Provided

### `verify_contract`
Run the full Nightjar verification pipeline on generated code against a `.card.md` spec.

**Inputs:**
- `spec_path` (string) — Path to the `.card.md` spec file
- `code_path` (string) — Path to the generated code file to verify
- `stages` (string, optional) — Which stages to run: `"all"` (default), `"fast"` (stages 0–3, skips Dafny), or `"formal"` (stage 4 only)

**Output:** JSON with `{ verified, stages, errors, duration_ms, retry_count }`

**Example output:**
```json
{
  "verified": true,
  "stages": [
    { "stage": 0, "name": "preflight", "status": "pass", "duration_ms": 12 },
    { "stage": 1, "name": "deps",      "status": "pass", "duration_ms": 340 },
    { "stage": 2, "name": "schema",    "status": "pass", "duration_ms": 820 },
    { "stage": 3, "name": "pbt",       "status": "pass", "duration_ms": 4100 },
    { "stage": 4, "name": "formal",    "status": "pass", "duration_ms": 8700 }
  ],
  "errors": [],
  "duration_ms": 13972,
  "retry_count": 0
}
```

---

### `get_violations`
Retrieve the detailed violation report from the most recent `verify_contract` call.

**Inputs:**
- `spec_path` (string) — Path to the `.card.md` file (used as the key to look up results)

**Output:** JSON with `{ violations: [{ stage, stage_num, file, line, message, type, counterexample? }] }`

**Example output:**
```json
{
  "violations": [
    {
      "stage": "pbt",
      "stage_num": 3,
      "file": "payment.py",
      "line": 42,
      "message": "Property 'amount must be positive' failed: counterexample amount=-1",
      "type": "property_failure",
      "counterexample": { "amount": -1 }
    }
  ]
}
```

---

### `suggest_fix`
Get an LLM-generated code fix for a specific violation from the last verification run.

**Inputs:**
- `spec_path` (string) — Path to the `.card.md` file
- `violation_id` (string) — Index of the violation to fix (0-based, from the `get_violations` list)

**Output:** JSON with `{ suggested_code, explanation, confidence }`

**Example output:**
```json
{
  "suggested_code": "if amount <= 0:\n    raise ValueError('amount must be positive')",
  "explanation": "Fix for property_failure violation at payment.py:42",
  "confidence": 0.7
}
```

---

## Typical Workflow

```
1. User writes a .card.md spec
2. AI generates code
3. Call verify_contract → get verification result
4. If violations exist, call get_violations → see details
5. Call suggest_fix for each violation → get code repair
6. AI applies fix, repeat until verified: true
```

---

## Install

```bash
pip install nightjar-verify
```

Requires Python 3.11+. For formal proof (Stage 4), also install Dafny 4.x.

---

## Configuration

### Claude Code (project-level `.mcp.json`)

```json
{
  "mcpServers": {
    "nightjar": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "nightjar.mcp_server"],
      "env": {
        "NIGHTJAR_MODEL": "deepseek/deepseek-chat"
      }
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "nightjar": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "nightjar.mcp_server"],
      "env": {
        "NIGHTJAR_MODEL": "claude-sonnet-4-6"
      }
    }
  }
}
```

### Supported Models (via `NIGHTJAR_MODEL`)

Nightjar uses [litellm](https://github.com/BerriAI/litellm) for LLM calls, so any model litellm supports works:

| Model | Value |
|-------|-------|
| Claude Sonnet | `claude-sonnet-4-6` |
| DeepSeek Chat | `deepseek/deepseek-chat` |
| GPT-4o | `gpt-4o` |
| Gemini Pro | `gemini/gemini-1.5-pro` |
| Ollama Llama | `ollama/llama3.2` |

---

## Requirements

- Python 3.11+
- `mcp[fastmcp]` (installed automatically with nightjar-verify)
- `litellm` (installed automatically)
- LLM API key in env (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`)
- Optional: Dafny 4.x for Stage 4 formal proof

---

## Example `.card.md` Spec

```markdown
# payment

## contract

### inputs
- amount: float

### invariants
- [property] amount must be positive: amount > 0
- [property] amount must not overflow: amount < 1_000_000
- [formal] no negative payments: forall x :: x > 0 ==> process(x) >= 0
```

---

## Links

- Homepage: https://nightjar.dev
- GitHub: https://github.com/nightjar-dev/nightjar
- PyPI: https://pypi.org/project/nightjar-verify/
- Issues: https://github.com/nightjar-dev/nightjar/issues

---

## License

AGPL-3.0-only

---

## Submission Notes (for mcp.so / Cline Marketplace)

- **Category:** Developer Tools, Code Quality, Verification
- **Tags:** verification, formal-proof, property-testing, dafny, hypothesis, AI-generated-code, contracts
- **Transport:** stdio
- **Install method:** pip
- **Auth required:** No (uses your own LLM API key via env var)
- **Data access:** Local filesystem only (reads .card.md spec files and generated code)
