#!/usr/bin/env node
"use strict";

/**
 * nightjar-mcp — Zero-setup MCP stdio shim for Nightjar formal verification.
 *
 * Delegates to: uvx --from nightjar-verify python -m nightjar.mcp_server
 *
 * Usage (Claude Code .mcp.json or Claude Desktop config):
 *   {
 *     "mcpServers": {
 *       "nightjar": {
 *         "type": "stdio",
 *         "command": "npx",
 *         "args": ["-y", "@nightjar/mcp"],
 *         "env": {
 *           "NIGHTJAR_MODEL": "claude-sonnet-4-6",
 *           "ANTHROPIC_API_KEY": "sk-ant-..."
 *         }
 *       }
 *     }
 *   }
 *
 * Tools exposed (discovered via MCP protocol at runtime):
 *   verify_contract — Run 6-stage verification pipeline against a .card.md spec
 *   get_violations  — Get violation details from last verify_contract run
 *   suggest_fix     — Get LLM-generated code repair for a specific violation
 *
 * Environment variables (set at least one LLM API key for suggest_fix):
 *   NIGHTJAR_MODEL     litellm model string (default: claude-sonnet-4-6)
 *   ANTHROPIC_API_KEY  for Claude models
 *   OPENAI_API_KEY     for GPT models
 *   DEEPSEEK_API_KEY   for deepseek/deepseek-chat
 *   GEMINI_API_KEY     for Gemini models
 *
 * Requires: uv/uvx  https://docs.astral.sh/uv/getting-started/installation/
 *           Python 3.11+  (installed automatically by uvx)
 *           Dafny 4.x     (optional, only needed for Stage 4 formal proof)
 */

const { spawn } = require("child_process");
const { execSync } = require("child_process");

/** Check that uvx is available on PATH. */
function checkUvx() {
  try {
    execSync("uvx --version", { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

if (!checkUvx()) {
  process.stderr.write(
    "[nightjar-mcp] Error: 'uvx' not found on PATH.\n" +
      "uvx is part of uv — the fast Python package manager.\n\n" +
      "Install uv:\n" +
      "  macOS / Linux:\n" +
      "    curl -LsSf https://astral.sh/uv/install.sh | sh\n" +
      "  Windows:\n" +
      "    powershell -c \"irm https://astral.sh/uv/install.ps1 | iex\"\n" +
      "  pip (any platform):\n" +
      "    pip install uv\n\n" +
      "After installing, restart your terminal and try again.\n"
  );
  process.exit(1);
}

const child = spawn(
  "uvx",
  ["--from", "nightjar-verify", "python", "-m", "nightjar.mcp_server"],
  {
    // Inherit stdio so MCP JSON-RPC frames pass through unmodified.
    stdio: "inherit",
    // Forward the full environment so NIGHTJAR_MODEL, API keys, etc. reach the server.
    env: process.env,
  }
);

child.on("error", (err) => {
  process.stderr.write(
    `[nightjar-mcp] Failed to start server: ${err.message}\n`
  );
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) {
    // Re-raise the signal so the parent process sees a proper signal exit.
    process.kill(process.pid, signal);
  } else {
    process.exit(code ?? 1);
  }
});

// Forward termination signals from the parent to the child process.
for (const sig of ["SIGTERM", "SIGINT", "SIGHUP"]) {
  process.on(sig, () => {
    try {
      child.kill(sig);
    } catch {
      // Child may have already exited.
    }
  });
}
