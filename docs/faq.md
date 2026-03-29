# Nightjar FAQ

Answers to the questions developers ask most often. For deeper coverage see
[Architecture](ARCHITECTURE.md), the [CLI reference in the README](../README.md#cli-commands),
and the full [LLM context document](web/nightjar-canvas/public/llms-ctx.txt).

---

## Getting Started

**Do I need to write specs manually?**
No — three zero-friction entry points exist for existing codebases. `nightjar scan app.py`
extracts invariants from your code via AST analysis (fast, no LLM). `nightjar infer app.py`
uses an LLM plus CrossHair to generate and validate richer contracts automatically.
`nightjar auto "payment processing with refunds"` guides you through spec design via
interactive natural-language Q&A. Manual spec writing is the power-user path for
greenfield modules.

**Do I need Dafny installed?**
No. Without Dafny, Nightjar uses CrossHair symbolic execution for all formal invariants.
Dafny is only invoked automatically when a function's cyclomatic complexity exceeds a
routing threshold — most modules never reach it. Use `nightjar verify --fast` to skip
Stage 2.5 and Dafny entirely and still get schema validation plus property-based testing
with a confidence score.

**What Python versions are supported?**
Python 3.11 and above. Nightjar is tested on Linux, macOS, and Windows. Dafny has
Windows binaries; CrossHair and Hypothesis run on all platforms.

**Does Nightjar modify my code?**
No. Nightjar reads your source files and checks them against their specs. Any code it
generates goes into `.card/audit/` — a read-only directory that you never edit directly.
Your working source files are untouched.

**Is generated code committed to git?**
Yes. `.card/audit/` is git-tracked, giving you a diff-based history of every
regeneration. The convention is to treat these files as read-only build artifacts — all
intentional changes go through the `.card.md` spec, not the generated code.

**Does Nightjar work on Windows?**
Yes. All stages (CrossHair, Hypothesis, Pydantic, pip-audit) run on Windows. Dafny
distributes Windows binaries. The full test suite runs on Windows in CI.

---

## How It Works

**What is the difference between `scan`, `infer`, and `auto`?**
`scan` performs pure AST analysis — fast, offline, no LLM required. It extracts
observable invariants (argument checks, return constraints, guard conditions) directly
from the code structure. `infer` adds an LLM generation step followed by CrossHair
symbolic validation, producing richer precondition and postcondition contracts.
`auto` is the interactive path: you describe intent in plain English and Nightjar
guides you through spec design with a Q&A loop.

**What are the six verification stages?**
The pipeline runs cheapest-first and short-circuits on the first failure:
Stage 0 (Preflight) validates syntax and YAML schema; Stage 1 (Deps) checks for CVEs
and hallucinated packages; Stage 2 (Schema) validates output shapes with Pydantic v2;
Stage 2.5 (Negation-proof) guards against vacuously-passing invariants using CrossHair;
Stage 3 (Property-based tests) runs Hypothesis with 200+ random inputs; Stage 4
(Formal proof) runs CrossHair or Dafny depending on function complexity. See
[pipeline docs](https://nightjarcode.dev/docs/pipeline) for timing and cost per stage.

**What if verification fails?**
Nightjar displays the concrete counterexample — the exact input that violated the
invariant — with a Python-developer-friendly explanation. Use `nightjar explain` for
the full LP dual root-cause diagnosis, which identifies which invariant is the binding
constraint. If you have retries enabled, the CEGIS loop automatically feeds the
counterexample back into the LLM repair prompt and re-runs the pipeline.

**How does caching work?**
Verification results are cached in `.card/cache/` keyed by a content hash of the
spec and source. Repeated `nightjar verify` runs are sub-second when nothing has
changed. Set `NIGHTJAR_DISABLE_CACHE=1` to bypass the cache.

**What happens if the LLM API is down?**
Nightjar exits with code 4 (LLM API error) and does not proceed. Verification itself
(Stages 0–4) requires no LLM — only `nightjar generate` and `nightjar retry` make LLM
calls. If the API is unavailable, existing verified artifacts remain valid; you just
cannot regenerate or auto-repair until connectivity is restored.

**How does Nightjar handle multi-file modules?**
One `.card.md` per logical module. The `module.owns` field lists every function and
class that belongs to the module. Multiple cards can declare dependencies on each other
via `module.depends-on`, and Nightjar respects the declared dependency order when
running the pipeline. See the [spec format docs](https://nightjarcode.dev/docs/card-format)
for a full example.

---

## Integration

**How do I use Nightjar in CI?**
Add `j4ngzzz/Nightjar@v1` to your GitHub Actions workflow for SARIF annotations on
PRs. Alternatively, call `nightjar verify --ci` directly — this disables interactive
prompts and TUI output and exits 0 on pass, 1 on fail. For non-blocking rollout, use
`nightjar shadow-ci --mode shadow` to run verification in parallel without gating
the build. See the [CI setup guide](tutorials/ci-one-commit.md).

**Does it work with Claude Code / OpenClaw?**
Yes — skills are available for both. In Claude Code, the `nightjar-verify` skill
auto-verifies code after every AI generation step. In OpenClaw, the skill is at
`skills/openclaw/nightjar-verify/`. The MCP server (`nightjar mcp`) also works with
Cursor, Windsurf, Kiro, and any MCP-compatible IDE.

**Can I use it with VS Code?**
`nightjar verify --format=vscode` outputs problem matcher format that populates the
Problems panel with inline squiggles. SARIF output (`--output-sarif results.sarif`) is
available for GitHub Code Scanning. A first-class VS Code extension with LSP diagnostics
is on the roadmap.

**What about Docker?**
A Dockerfile bundling Dafny 4.8.0 is in the repository root — build it locally with
`docker build -t nightjar .`. The Docker image is not yet published to
`ghcr.io/j4ngzzz/nightjar`; publication will happen with the next tagged release.

---

## The Bug Findings

**Did Nightjar-the-CLI find the 74 bugs?**
We used standalone Hypothesis scripts in `scan-lab/` that apply the same property-based
testing methodology Nightjar automates. Nightjar packages and orchestrates this approach
into a multi-stage pipeline — the methodology is identical, the CLI wraps it. Saying
Nightjar found 74 bugs is accurate in the same way you'd say "pytest found a bug" when a
Hypothesis test fails inside pytest.

**Are the bugs verified?**
Every finding has a standalone reproduction script in `scan-lab/` that runs without
Nightjar installed. Zero false positives — each bug produces a concrete counterexample
you can run yourself. See [nightjarcode.dev/bugs/](https://nightjarcode.dev/bugs/) for
the full audit report.

**Were disclosures sent?**
Disclosure templates are at `docs/distribution/disclosure-templates.md`. Critical
findings (e.g., the fastmcp OAuth bypass, the openai-agents handoff injection) have been
prioritized for responsible disclosure to the respective maintainers.

---

## Technical

**What is "contractual computing"?**
Contractual computing is the principle that the spec (contract) is the only permanent
artifact. Code is disposable — regenerated from scratch on every build and never manually
edited. Contracts are discoverable, transferable, and compounding: the more you specify,
the more Nightjar can prove. See [docs/ARCHITECTURE.md](ARCHITECTURE.md) for the full
design rationale.

**What is "vericoding"?**
Vericoding is formally verified code generation from specifications — the rigorous
counterpart to vibe coding. Rather than generating code that looks plausible, vericoding
requires mathematical proof that the generated code satisfies its spec for all inputs.
The term is referenced in the POPL 2026 vericoding benchmark (BAIF/MIT); Nightjar's
`nightjar benchmark` command reports pass@k rates against that suite.

**What LLM models work?**
Any litellm-compatible model. Tested with `claude-sonnet-4-6`, `openai/o3`,
`openai/gpt-4o`, and `deepseek/deepseek-chat`. Set the model via the `NIGHTJAR_MODEL`
environment variable — never hardcode a model name. The 86% pass@10 benchmark was run
with Claude 3.5 Sonnet on the DafnyPro benchmark.

**Is Nightjar itself verified?**
Yes. The project dogfoods its own pipeline: CI runs `nightjar verify` on the specs in
`.card/`. If Nightjar's own code violates a property, Nightjar's own CI fails. The badge
in the README reflects the last passing run; run `nightjar badge` locally to print the
current shields.io URL.

**What is slopsquatting?**
Slopsquatting occurs when an AI coding assistant suggests a package name that does not
exist on PyPI, or a name similar to a real package that an attacker has registered with
malicious code. Research from USENIX found 19.7% of AI-generated package dependencies
are hallucinated. Nightjar's Stage 1 sealed manifest (`deps.lock`) with SHA-256 hashes
blocks any package not explicitly listed, preventing slopsquatting attacks before any
code can import a compromised package.

**What is the Wonda quality filter?**
Wonda is Nightjar's four-criteria filter for invariant candidates produced by the immune
system. A candidate must score at or above 0.8 on all four dimensions — precision (few
false positives), recall (catches real violations), specificity (not trivially satisfied
by any code), and stability (holds across 50+ production trace windows) — before it is
appended to the spec. This prevents low-quality or degenerate invariants from entering
the contract and weakening future verifications.

---

## Licensing

**What license is Nightjar under?**
AGPL-3.0. Free for open-source projects. The Daikon algorithm implementation in
`src/immune/daikon.py` is MIT-licensed (reimplemented from scratch — the Fuzzingbook
CC-BY-NC-SA implementation is not used). See [LICENSE](../LICENSE) for the full terms.

**What does commercial use cost?**
Teams: $2,400/yr. Enterprise: $12,000/yr. Contact
[nightjar-license@proton.me](mailto:nightjar-license@proton.me) to arrange a license.
Every sponsor also gets listed in the README and a direct support line.
