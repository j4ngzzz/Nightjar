# CARD Reference Library

> **MANDATORY**: Every BridgeSwarm agent MUST consult this document before implementing any component.
> Find the relevant `[REF-XXX]` entries for your task, fetch the URLs, read the source material, THEN write code.
> Do NOT implement from memory or training data. Every pattern must trace to a specific citation below.

---

## Section A: Academic Papers

### Core Papers (Must-Read Before Any Implementation)

**[REF-P01]** Intent Formalization: A Grand Challenge for Reliable Coding in the Age of AI Agents
- Authors: Shuvendu K. Lahiri (Microsoft Research)
- Date: March 2026
- URL: https://arxiv.org/abs/2603.17150
- Key Finding: Names "intent formalization" as THE central unsolved problem of AI coding. Defines the "intent gap" — the distance between informal user intent and checkable specifications. Proposes a spectrum from lightweight tests through full formal specs.
- CARD Relevance: This paper defines the field CARD occupies. Our `.card.md` format is an implementation of Lahiri's "formal functional contracts." Cite in README, positioning, and academic communications.

**[REF-P02]** A Benchmark for Vericoding: Formally Verified Program Synthesis
- Authors: Sergiu Bursuc, Theodore Ehrenborg, Shaowei Lin, Max Tegmark + 10 others (MIT / Beneficial AI Foundation)
- Date: September 2025; accepted POPL 2026 Dafny Workshop
- URL: https://arxiv.org/abs/2509.22908
- Key Finding: Coins "vericoding." 12,504 specs across Dafny/Verus/Lean. Success rates: 82% Dafny, 44% Verus, 27% Lean with off-the-shelf LLMs. Dafny improved from 68% to 96% in one year.
- CARD Relevance: Establishes baseline success rates for CARD's verification loop. Validates Dafny as the most tractable verification language. Use for benchmarking claims.
- Code: https://github.com/Beneficial-AI-Foundation/deductive-vericoding

**[REF-P03]** Clover: Closed-Loop Verifiable Code Generation
- Authors: Chuyue Sun, Ying Sheng, Oded Padon, Clark Barrett (Stanford)
- Date: 2023/2024; SAIV 2024
- URL: https://arxiv.org/abs/2310.17807
- Key Finding: Consistency checking among code, docstrings, and formal annotations. 87% acceptance rate for correct instances, zero false positives. Discovered 6 bugs in human-written MBPP-DFY-50 dataset.
- CARD Relevance: The "closed-loop" pattern is CARD's retry loop architecture. Implement the generate → verify → feedback → regenerate cycle exactly as described.

**[REF-P04]** AlphaVerus: Bootstrapping Formally Verified Code Generation through Self-Improving Translation and Treefinement
- Authors: Pranjal Aggarwal, Bryan Parno, Sean Welleck (Carnegie Mellon University)
- Date: December 2024; ICML 2025
- URL: https://arxiv.org/abs/2412.06176
- Key Finding: Self-improving loop: translate Python → Verus/Rust, use verifier feedback + tree search. No human intervention required. Addresses spec validation without unit tests.
- CARD Relevance: The self-improvement loop architecture informs CARD's immune system design. Treefinement = CARD's regeneration-with-verification cycle.
- Code: https://github.com/cmu-l3/alphaverus

**[REF-P05]** AutoVerus: Automated Proof Generation for Rust Code
- Authors: Microsoft Research team
- Date: September 2024; PACMPL 2025
- URL: https://arxiv.org/abs/2409.13082
- Key Finding: Multi-agent LLM network in three phases: preliminary generation, generic tip refinement, error-guided debugging. >90% correctness on 150 tasks, >50% in under 30 seconds.
- CARD Relevance: Direct implementation model for CARD's verification agent layer. The 3-phase proof construction is production-ready.
- Code: https://github.com/microsoft/verus-proof-synthesis

**[REF-P06]** DafnyPro: LLM-Assisted Automated Verification for Dafny Programs
- Authors: (POPL 2026 Dafny Workshop)
- Date: January 2026
- URL: https://arxiv.org/abs/2601.05385
- Key Finding: 86% pass@10 with Claude 3.5 Sonnet on DafnyBench. Structured error format with assertion batch IDs and resource units consumed enables targeted repair.
- CARD Relevance: The structured error format for the retry loop. Copy the repair prompt design: include file, line, error message, assertion batch, resource units, counterexample.

**[REF-P07]** Requirements Development and Formalization for Reliable Code Generation: A Multi-Agent Vision (ReDeFo)
- Authors: Weisong Sun + NSFC-funded collaborators (NTU Singapore)
- Date: August 2025
- URL: https://arxiv.org/abs/2508.18675
- Key Finding: First multi-agent framework with Analyst → Formalizer → Coder pipeline. Uses formal specs to bridge ambiguous NL requirements to correct code. First system with formal correctness guarantees in multi-agent code generation.
- CARD Relevance: This IS the multi-agent architecture of CARD's `contractd generate` pipeline. Directly implementable.

**[REF-P08]** Automatic Generation of Formal Specification and Verification Annotations Using LLMs and Test Oracles
- Date: January 2026
- URL: https://arxiv.org/abs/2601.12845
- Key Finding: Multi-model approach (Claude + GPT) generates correct Dafny annotations for 98.2% of 110 programs within 8 repair iterations. Test assertions as static oracles for spec validation.
- CARD Relevance: 98.2% success rate is production-viable. The test-oracle-as-spec-validator pattern solves the bootstrapping problem.

**[REF-P09]** VibeContract: The Missing Quality Assurance Piece in Vibe Coding
- Authors: Song Wang (York University, Toronto)
- Date: March 16, 2026
- URL: https://arxiv.org/abs/2603.15691
- Key Finding: Proposes decomposing natural language intent into task sequences with formal contracts (pre/postconditions). Independent validation of contract-guided generation.
- CARD Relevance: Cite as independent academic validation. Complementary, not competitive. Author is potential collaborator.

**[REF-P10]** Use Property-Based Testing to Bridge LLM Code Generation and Validation (PGS)
- Date: June 2025
- URL: https://arxiv.org/abs/2506.18315
- Key Finding: Property-based testing raises correction rates from 46.6% to 75.9%. LLMs are 20-47% more accurate generating validation properties than generating implementations.
- CARD Relevance: Validates that PBT is the right verification approach for Stage 3. LLMs are BETTER at writing invariants than writing code — this is why CARD works.

### Supporting Papers

**[REF-P11]** ATLAS: Automated Toolkit for Large-Scale Verified Code Synthesis
- URL: https://arxiv.org/abs/2512.10173
- Key Finding: Pipeline generates 2.7K verified Dafny programs. Fine-tuning Qwen 2.5 7B: DafnyBench 32% → 57%.
- CARD Relevance: Solves training data scarcity. CARD can build domain-specific verified code models.

**[REF-P12]** Dafny as Verification-Aware Intermediate Language for Code Generation
- Authors: Amazon AWS
- Date: POPL 2025
- URL: https://arxiv.org/abs/2501.06283
- Key Finding: NL → Dafny → verified Python/JS/Go/Java/C#. The user never sees Dafny.
- CARD Relevance: This IS CARD's core generation pipeline architecture. The "OASIS equivalent."

**[REF-P13]** Spec-Driven Development: From Code to Contract in the Age of AI Coding Assistants
- URL: https://arxiv.org/abs/2602.00180
- Key Finding: Academic paper formalizing the spec-first/spec-anchored/spec-as-source taxonomy.
- CARD Relevance: Positions CARD at the "spec-as-source" apex of the maturity model.

**[REF-P14]** Beyond Postconditions: Can LLMs Infer Formal Contracts for Automatic Software Verification? (NL2Contract)
- URL: https://arxiv.org/abs/2510.12702
- Key Finding: LLMs generate full functional contracts (pre+postconditions) from NL. Sound contracts for all inputs. Fewer false alarms than postconditions alone.
- CARD Relevance: Automated behavioral contract inference from natural language intent. Directly applicable to CARD's invariant generation.

**[REF-P15]** Agentic Property-Based Testing (Agentic PBT)
- URL: https://arxiv.org/abs/2510.09907
- Code: https://github.com/mmaaz-git/agentic-pbt
- Key Finding: LLM agent proposes properties, writes Hypothesis tests, executes them. 56% valid bug detection rate. 86% of top-scored bugs were valid.
- CARD Relevance: The most immediately deployable LLM-based invariant discovery pipeline for Python. Directly applicable to immune system.

**[REF-P16]** Preguss: It Analyzes, It Specifies, It Verifies
- Authors: Zhejiang University
- URL: https://arxiv.org/abs/2508.14532
- Key Finding: Divide-and-conquer framework for LLM-based formal spec synthesis for large programs (1,000+ LoC). Reduces human verification effort by 80-89%.
- CARD Relevance: Addresses scalability challenge — how to generate specs for large systems.

**[REF-P17]** MINES: Inferring Web API Invariants from HTTP Logs
- URL: https://arxiv.org/abs/2512.06906
- Key Finding: LLM hypothesizes constraints from API logs → validates against normal instances → Python verification code. ICSE 2026 accepted.
- CARD Relevance: Directly applicable to CARD's immune system for web API endpoints. The OTel → LLM → invariant pipeline.

**[REF-P18]** Self-Healing Software Systems: Lessons from Nature, Powered by AI
- URL: https://arxiv.org/abs/2504.20093
- Key Finding: Biological immune system model: observability → AI diagnosis → healing agents → patches.
- CARD Relevance: Validates CARD's immune system biological metaphor. Architecture reference.

**[REF-P19]** The 4/δ Bound: Designing Predictable LLM-Verifier Systems
- URL: https://arxiv.org/abs/2512.02080
- Key Finding: Theoretical reliability bounds for LLM+verifier systems.
- CARD Relevance: The math CARD needs for reliability claims.

**[REF-P20]** Rango: Adaptive Retrieval-Augmented Proving for Automated Software Verification
- URL: https://arxiv.org/abs/2412.14063
- Key Finding: RAG at every proof step. +47% theorems proven. ICSE 2025 ACM SIGSOFT Distinguished Paper Award.
- CARD Relevance: Context-aware proof retrieval for scaling verification to large codebases.

**[REF-P21]** Prometheus: Dissect-and-Restore — AI-based Code Verification with Transient Refactoring
- Authors: KTH
- URL: https://arxiv.org/abs/2510.25406
- Key Finding: Transient refactoring — decompose complex code into verifiable units, verify, recompose. Uses word "transient" explicitly.
- CARD Relevance: "Transient" = CARD's ephemeral code philosophy applied to verification.

**[REF-P22]** Towards Automated Formal Verification of Backend Systems with LLMs
- Authors: Kangping Xu + Andrew C. Yao (Tsinghua IIIS)
- URL: https://arxiv.org/abs/2506.10998
- Key Finding: Scala backend → Lean formal representations. Auto-generates theorems for API and DB operation correctness.
- CARD Relevance: Yao group targeting backend verification — closest to CARD's production use case.

**[REF-P23]** Goedel-Prover-V2: Scaling Formal Theorem Proving
- Authors: Tsinghua IIIS
- URL: https://arxiv.org/abs/2508.03613
- Key Finding: 88.1% MiniF2F, first among open-source provers. Scaffolded data synthesis + self-correction.
- CARD Relevance: Strongest open-source prover model. Potential CARD verification backbone.

**[REF-P24]** DeepSeek-Prover-V2
- URL: https://arxiv.org/abs/2504.21801
- Key Finding: 88.9% MiniF2F-test. Fully open-source (MIT). Both 7B and 671B versions.
- CARD Relevance: SOTA prover model, free to use. Chinese industrial contribution.

**[REF-P25]** CLEVER: A Curated Benchmark for Formally Verified Code Generation
- URL: https://arxiv.org/abs/2505.13938
- Key Finding: 161 Lean 4 problems. SOTA LLMs solve only 1/161 end-to-end.
- CARD Relevance: Measures the real difficulty of FULL pipeline. CARD's MVP uses annotation verification (82%), not full end-to-end (1/161).

**[REF-P26]** VeriSoftBench: Repository-Scale Formal Verification
- URL: https://arxiv.org/abs/2602.18307
- Key Finding: 500 Lean 4 tasks from 23 real repos. Best model: 41% with curated context, 35% with raw repo.
- CARD Relevance: Repository-scale verification is hard. CARD must stay modular (per-module verification).

**[REF-P27]** Package Hallucinations: How LLMs Can Invent Vulnerabilities (Slopsquatting)
- URL: https://www.usenix.org/publications/loginonline/we-have-package-you-comprehensive-analysis-package-hallucinations-code
- Key Finding: 19.7% of AI-generated package dependencies are hallucinated. 58% repeat across runs.
- CARD Relevance: Why the sealed dependency manifest (Stage 1) is mandatory.

**[REF-P28]** Martin Kleppmann: AI Will Make Formal Verification Go Mainstream
- URL: https://martin.kleppmann.com/2025/12/08/ai-formal-verification.html
- Key Finding: LLMs write Lean proofs faster than humans. Proof checkers reject invalid proofs deterministically.
- CARD Relevance: Industry thought-leader validation of CARD's core thesis.

**[REF-P29]** MDA/MDD: Don't Round-Trip! (Véronique Hanniet, 2011)
- URL: https://vhanniet.wordpress.com/2011/04/20/mdamdd-dont-round-trip/
- Key Finding: Treat generated code as disposable, apply all changes through the model. Written 15 years before CARD.
- CARD Relevance: Independent validation of CARD's architectural principle. The industry KNEW this was right but couldn't enforce it without structural prevention.

**[REF-P30]** Understanding Spec-Driven-Development: Kiro, spec-kit, and Tessl (Martin Fowler team)
- URL: https://martinfowler.com/articles/exploring-gen-ai/sdd-3-tools.html
- Key Finding: Tessl is only "exploring" spec-as-source. Warns spec-as-source risks repeating MDD failure.
- CARD Relevance: The MDD warning we must address. Also confirms Tessl is aspirational, not productized.

**[REF-P31]** The Call for Invariant-Driven Development (Trail of Bits)
- URL: https://blog.trailofbits.com/2025/02/12/the-call-for-invariant-driven-development/
- Key Finding: Argues invariants should be first-class development artifacts, not afterthoughts.
- CARD Relevance: Inspiration for tiered invariant system. Validates invariant-first philosophy.

**[REF-P32]** Re:Form — RL-Based Formal Code Verification (Shanghai AI Lab)
- URL: https://arxiv.org/abs/2507.16331
- Code: https://github.com/Veri-Code/ReForm
- Key Finding: RL-trained for Dafny without human CoT priors. Small models (0.5B) work. 80%+ verification rate.
- CARD Relevance: On-premise alternative to Claude API for repair calls. $0.001 vs $0.01 per retry.

**[REF-P33]** Sonar: Critical Verification Gap in AI Coding
- URL: https://www.sonarsource.com/company/press-releases/sonar-data-reveals-critical-verification-gap-in-ai-coding/
- Key Finding: 96% of developers don't fully trust AI code. Only 48% verify before committing.
- CARD Relevance: Market validation data. The "verification debt" problem quantified.

**[REF-P34]** Non-Determinism of "Deterministic" LLM Settings
- URL: https://arxiv.org/abs/2408.04667
- Key Finding: Even at temperature 0, 75.76% of tasks produce different outputs across runs. Raw string agreement below 50%.
- CARD Relevance: Why CARD verifies BEHAVIOR not CODE TEXT. Non-determinism is real and measured.

**[REF-P35]** LIG-MM: Loop Invariant Generation for Memory-Manipulating Programs (Shanghai Jiao Tong University)
- URL: https://github.com/Thinklab-SJTU/LIG-MM
- Key Finding: 312 programs from Linux Kernel, GlibC. LLM-SE framework combining LLM with symbolic execution.
- CARD Relevance: Leading Chinese contribution to invariant generation. NeurIPS 2024.

---

## Section B: Tools & Frameworks

### Verification Layer

**[REF-T01]** Dafny — Verification-Aware Programming Language
- URL: https://github.com/dafny-lang/dafny
- License: MIT
- Install: Download binary from GitHub releases
- What it does: Verification engine with built-in pre/postconditions, loop invariants. Compiles verified code to Python, JavaScript, Go, Java, C#.
- How CARD uses it: Stage 4 of verification pipeline. The core verifier. `dafny verify module.dfy` then `dafny compile --target py`.
- Production precedent: Amazon uses Dafny for auth services at 1 billion calls/second.

**[REF-T02]** dafny-annotator — LLM-Assisted Dafny Annotation
- URL: https://github.com/metareflection/dafny-annotator
- License: MIT
- Install: `pip install dafny-annotator` (or clone repo)
- What it does: AI adds loop invariants/assertions to Dafny until verification passes. The generate→verify→repair loop.
- How CARD uses it: Reference implementation for CARD's retry loop. Study and adapt the prompting strategy.

**[REF-T03]** Hypothesis — Property-Based Testing for Python
- URL: https://github.com/HypothesisWorks/hypothesis
- License: MPL 2.0
- Install: `pip install hypothesis`
- What it does: Generates random inputs, checks properties hold for all of them. Shrinks failures to minimal counterexamples.
- How CARD uses it: Stage 3 of verification pipeline. Auto-generated from `.card.md` invariants. Also used in immune system for verifying candidate invariants.

**[REF-T04]** fast-check — Property-Based Testing for JS/TS
- URL: https://github.com/dubzzz/fast-check
- License: MIT
- Install: `npm install fast-check`
- What it does: Same as Hypothesis but for JavaScript/TypeScript.
- How CARD uses it: Stage 3 for JS/TS targets.

**[REF-T05]** uv — Fast Python Package Manager
- URL: https://github.com/astral-sh/uv
- License: MIT
- Install: `pip install uv`
- What it does: Ultra-fast pip replacement with hash verification and sealed lockfiles.
- How CARD uses it: Stage 1 dependency check. `uv pip sync --require-hashes --dry-run` enforces sealed manifest.

**[REF-T06]** pip-audit — Vulnerability Scanning
- URL: https://github.com/pypa/pip-audit
- License: Apache 2.0
- Install: `pip install pip-audit`
- What it does: Scans Python dependencies for known CVEs.
- How CARD uses it: Stage 1 CVE check. `pip-audit --requirement deps.lock --format json`.

**[REF-T07]** audit-ci — JS/TS Dependency Auditing
- URL: https://github.com/IBM/audit-ci
- License: Apache 2.0
- Install: `npx audit-ci`
- What it does: CI-friendly npm audit with allowlists and severity thresholds.
- How CARD uses it: Stage 1 for JS/TS targets.

**[REF-T08]** Pydantic v2 — Data Validation
- URL: https://github.com/pydantic/pydantic
- License: MIT
- Install: `pip install pydantic`
- What it does: Runtime data validation using Python type hints. Validates generated code output schemas.
- How CARD uses it: Stage 2 schema validation. Parse generated data structures against contract schema.

**[REF-T09]** CrossHair — Python Symbolic Execution
- URL: https://github.com/pschanely/CrossHair
- License: MIT
- Install: `pip install crosshair-tool`
- What it does: Symbolic execution via Z3. Finds contract violations by exploring all execution paths.
- How CARD uses it: Immune system — formally verifies LLM-proposed invariants. Used in NL2Contract pipeline [REF-P14].

**[REF-T10]** icontract — Python Design by Contract
- URL: https://github.com/Parquery/icontract
- License: MIT
- Install: `pip install icontract`
- What it does: `@require`, `@ensure`, `@invariant` decorators with informative violation messages.
- How CARD uses it: Immune system — runtime enforcement of discovered invariants in production Python code.

**[REF-T11]** deal — Python DBC with Formal Verification
- URL: https://github.com/life4/deal
- License: MIT
- Install: `pip install deal`
- What it does: DBC library with `@pre`, `@post`, `@inv` + built-in Hypothesis integration (`deal test`) + Z3 verification (`deal-solver`).
- How CARD uses it: Alternative to icontract. The `deal test` integration is particularly useful — invariant as deal contract → auto-fuzz with Hypothesis.

### Data Collection & Mining

**[REF-T12]** MonkeyType — Runtime Type Collection (Instagram)
- URL: https://github.com/Instagram/MonkeyType
- License: BSD-3
- Install: `pip install monkeytype`
- What it does: Uses `sys.setprofile` to record runtime types of all function arguments and returns. Stores in SQLite. Generates type stubs.
- How CARD uses it: Immune system trace collection — type invariants from production. Instagram runs this on production Django with middleware.

**[REF-T13]** Fuzzingbook DynamicInvariants — Python Daikon Equivalent
- URL: https://www.fuzzingbook.org/html/DynamicInvariants.html
- License: CC-BY-NC-SA (check for commercial use)
- Install: `pip install fuzzingbook`
- What it does: Complete Python implementation of the Daikon algorithm. Uses `sys.settrace` to hook function calls. Applies invariant templates: type checks, value bounds, relational bounds, nullness, length constraints.
- How CARD uses it: Immune system core mining engine. `InvariantAnnotator` wraps any Python function and discovers invariants from observed executions. This IS the "Python Daikon" that resolves the Daikon-has-no-Python-frontend blocker.
- **LICENSE WARNING**: CC-BY-NC-SA prohibits commercial use. For CARD's commercial product, we MUST reimplement the Daikon algorithm in Python (~300 lines) under MIT license. Use Fuzzingbook as the REFERENCE IMPLEMENTATION to understand the algorithm, but do NOT ship Fuzzingbook code in production. The algorithm itself (Daikon, 1999) is not patented — only the Fuzzingbook implementation is CC-BY-NC-SA.

**[REF-T14]** DIG — Dynamic Invariant Generator
- URL: https://github.com/dynaroars/dig
- License: Check repo
- What it does: Infers polynomial and array invariants from execution traces. Takes CSV files as input. Uses SymPy + Z3.
- How CARD uses it: Immune system — numerical invariants for math-heavy code. Python → CSV → DIG → polynomial invariants.

**[REF-T15]** OpenTelemetry — Distributed Tracing
- URL: https://opentelemetry.io/
- License: Apache 2.0
- Install: `pip install opentelemetry-api opentelemetry-sdk`
- What it does: Auto-instrumented spans for web frameworks (FastAPI, Django, Flask, Express, NestJS).
- How CARD uses it: Immune system trace collection at API level. OTel captures HTTP method, URL, status code, request/response bodies — sufficient for MINES-style API invariant mining [REF-P17].

### Code Generation

**[REF-T16]** litellm — Unified LLM API
- URL: https://github.com/BerriAI/litellm
- License: MIT
- Install: `pip install litellm`
- What it does: Call Claude/GPT/DeepSeek/Gemini/Qwen/local models through one interface. Handles auth, retries, fallbacks.
- How CARD uses it: All LLM calls go through litellm. Model-agnostic by design. Switch models via env var.

### CLI & Infrastructure

**[REF-T17]** Click — Python CLI Framework
- URL: https://click.palletsprojects.com/
- License: BSD-3
- Install: `pip install click`
- How CARD uses it: The `contractd` CLI (init, generate, verify, build, ship).

**[REF-T18]** MCP SDK — Model Context Protocol
- URL: https://modelcontextprotocol.io/
- License: MIT
- What it does: Standard protocol for AI tool integration. Supported by Cursor, Windsurf, Claude Code, TRAE, Tongyi Lingma, Kiro.
- How CARD uses it: CARD ships as an MCP server with 3 tools: `verify_contract`, `get_violations`, `suggest_fix`. This is the universal IDE integration bus.

**[REF-T19]** EvoAgentX — Self-Evolving Agent Framework
- URL: https://github.com/EvoAgentX/EvoAgentX
- License: Check repo
- What it does: Execution → evaluation → evolution feedback loops. TextGrad for prompt evolution, AFlow for workflow restructuring, MIPRO for example selection. 8-13% improvement on benchmarks.
- How CARD uses it: Evolution layer (month 6+). Evolve invariant generation prompts, verification workflow order, and template selection based on performance feedback.
- Paper: https://arxiv.org/abs/2507.03616

**[REF-T26]** DSPy — Framework for Programming with Foundation Models
- URL: https://dspy.ai/
- License: MIT
- Install: `pip install dspy`
- Code: https://github.com/stanfordnlp/dspy
- What it does: Optimizes LLM prompts and pipelines automatically. SIMBA optimizer finds best prompt configurations via Bayesian optimization. 15-40% improvement on LLM pipeline tasks.
- How CARD uses it: Self-evolution layer. Optimizes Analyst/Formalizer/Coder prompts based on verification pass rate as the metric. `contractd optimize` triggers SIMBA optimization.

**[REF-T20]** OpenDP — Differential Privacy Library
- URL: https://github.com/opendp/opendp
- License: MIT
- Install: `pip install opendp`
- How CARD uses it: Immune system network effect — privacy-preserving cross-tenant invariant sharing (month 6+).
- Reference: Federated learning with DP — https://arxiv.org/abs/1911.00222

### Frontend

**[REF-T21]** Next.js 15
- URL: https://nextjs.org/
- How CARD uses it: Demo dashboard and web interface.

**[REF-T22]** shadcn/ui
- URL: https://ui.shadcn.com/
- How CARD uses it: UI component library for dashboard.

**[REF-T23]** Tremor
- URL: https://www.tremor.so/
- How CARD uses it: Dashboard charts (verification pass rates, invariant growth, cost tracking).

### Format Standards

**[REF-T24]** Agent Skills Open Standard (Anthropic, Dec 2025)
- URL: https://agentskills.io/specification
- What it does: YAML frontmatter + Markdown body format for AI tool instructions. Supported by 16+ tools including Cursor, Claude Code, Windsurf.
- How CARD uses it: The `.card.md` format adopts this standard as its base format — YAML frontmatter (machine-readable) + Markdown body (human-readable). This ensures compatibility with the existing vibe coding tool ecosystem.

**[REF-T25]** GitHub Spec Kit Format
- URL: https://github.com/github/spec-kit
- What it does: Given/When/Then acceptance criteria, FR-NNN numbered requirements, `[NEEDS CLARIFICATION]` markers, constitution.md for project-level invariants.
- How CARD uses it: `.card.md` adopts Given/When/Then acceptance criteria, FR-NNN requirements with RFC 2119 keywords (MUST/SHOULD/MAY), and `[NEEDS CLARIFICATION]` markers from Spec Kit conventions.

---

## Section C: Concepts & Patterns

**[REF-C01]** Tiered Invariants — CARD's Invention
- Source: No prior art. Inspired by [REF-P31] Trail of Bits "invariant-driven development."
- What: Each invariant in `.card.md` has a `tier`: `example` (unit test), `property` (PBT auto-generated), `formal` (Dafny mathematical proof).
- Maps to: `.card.md` YAML frontmatter `invariants:` block. Spec parser routes to appropriate verification stage based on tier.

**[REF-C02]** Closed-Loop Verification (Clover Pattern)
- Source: [REF-P03] Clover (Stanford)
- What: Generate code → verify → if fail, feed structured error back to LLM → regenerate → re-verify. Repeat up to N times.
- Maps to: `contractd verify` retry loop. The structured error format from [REF-P06] DafnyPro.

**[REF-C03]** Analyst → Formalizer → Coder Pipeline
- Source: [REF-P07] ReDeFo (NTU Singapore)
- What: Three sequential LLM agents. Agent 1 analyzes requirements. Agent 2 formalizes into specs. Agent 3 generates code.
- Maps to: `contractd generate` internal pipeline. Three LLM calls with different system prompts.

**[REF-C04]** Dafny as Intermediate Language
- Source: [REF-P12] Amazon AWS paper
- What: User writes NL → LLM generates Dafny → Dafny verifies → compiles to Python/JS/Go/Java/C#. User never sees Dafny.
- Maps to: Core generation pipeline. LLM outputs `.dfy` → `dafny verify` → `dafny compile --target py`.

**[REF-C05]** Dynamic Invariant Mining (Python Daikon)
- Source: [REF-T13] Fuzzingbook DynamicInvariants, based on Daikon algorithm (UW, 1999)
- What: Watch code run → discover what's always true → those become invariants.
- Maps to: Immune system Stage 2. `from fuzzingbook.DynamicInvariants import InvariantAnnotator`.

**[REF-C06]** LLM-Driven Invariant Enrichment
- Source: [REF-P15] Agentic PBT, [REF-P14] NL2Contract
- What: Raw mined invariants → LLM adds semantic understanding → formal assert statements → verify with CrossHair/Hypothesis.
- Maps to: Immune system Stage 2→3 transition.

**[REF-C07]** Don't Round-Trip Architecture
- Source: [REF-P29] Hanniet (2011), validated by [REF-P30] Fowler team
- What: Generated code is NEVER manually edited. All changes go through the spec. Enforced architecturally, not by convention.
- Maps to: CARD's core principle. Code marked `// GENERATED FROM SPEC - DO NOT EDIT`. Regeneration on every build.

**[REF-C08]** Sealed Dependency Manifest
- Source: [REF-P27] Slopsquatting paper (USENIX)
- What: Dependencies locked with SHA hashes. AI cannot add new packages without human approval.
- Maps to: `deps.lock` file. Stage 1 verification. Import allowlist check.

**[REF-C09]** Immune System / Acquired Immunity
- Source: [REF-P18] Self-Healing Software, IBM MAPE-K (Kephart & Chess, 2003), AIS literature
- What: Production bugs → auto-generate invariant → verify → add to spec → next build is protected. Network effect: one customer's bug immunizes all.
- Maps to: Immune system pipeline (Stages 1-5). Month 2-3 implementation.

**[REF-C10]** Herd Immunity via Differential Privacy
- Source: [REF-T20] OpenDP, federated learning literature
- What: Invariants shared across customers via structural abstraction + Laplace mechanism. Bugs from any customer strengthen all.
- Maps to: Immune system Stage 5. Month 6+ implementation.

**[REF-C11]** Verification Debt
- Source: AWS CTO Werner Vogels (2026), [REF-P33] Sonar data
- What: The gap between AI-generated code volume and verification coverage. 96% don't trust, only 48% verify.
- Maps to: CARD's market positioning. The phrase to own in marketing.

---

## Section D: Competitors

**[REF-D01]** Tessl — $125M, Guy Podjarny (Snyk founder)
- URL: https://tessl.io/
- What they do: Spec-as-source workflow management. Spec Registry (10K+ library specs). Code marked `// GENERATED - DO NOT EDIT`.
- What they DON'T do: No formal verification. No regeneration from scratch every build. No immune system. No runtime invariant enforcement. Fowler team says they're only "exploring" spec-as-source.
- Source: [REF-P30], Agent A findings

**[REF-D02]** Amazon Kiro — AWS-backed
- URL: https://kiro.dev/
- What they do: Spec-driven IDE. Specs → requirements → design → code. Property-based testing via Hypothesis. Agent hooks.
- What they DON'T do: No formal verification (Dafny/Lean). No code deletion/regeneration. No immune system.
- Source: Agent 3 findings

**[REF-D03]** Augment Code Intent — $252M total
- URL: https://www.augmentcode.com/product/intent
- What they do: Multi-agent spec-driven orchestration. 6 specialist agents. Living specs.
- What they DON'T do: No formal verification. Code persists and is maintained. No immune system.
- Source: Web search findings

**[REF-D04]** GitHub Spec Kit — 72.7K stars
- URL: https://github.com/github/spec-kit
- What they do: Open-source spec-driven toolkit. Supports 22+ AI agents. Given/When/Then format.
- What they DON'T do: No verification. No generation. Toolkit only, not a system.
- Source: Agent 1 findings

**[REF-D05]** Axiom Math — $200M Series A, $1.6B valuation
- URL: https://axiommath.ai/
- What they do: Lean proof engine for quant finance. AXLE product.
- What they DON'T do: No developer-facing code verification. Targets PhDs and mathematicians, not developers.
- Source: Scout 3 findings

---

## Section E: Research Groups

**[REF-G01]** CMU L3 Lab — Bryan Parno, Sean Welleck. AlphaVerus, Verus/Rust verification.
**[REF-G02]** Stanford Theory Lab — Clark Barrett, Oded Padon. Clover, closed-loop verification.
**[REF-G03]** Microsoft Research Formal Methods — Shuvendu Lahiri. Intent Formalization, AutoVerus.
**[REF-G04]** Harvard SEAS PL Lab — Nada Amin. DafnyBench, VerMCTS.
**[REF-G05]** Tsinghua IIIS — Andrew C. Yao. Goedel-Prover, backend verification.
**[REF-G06]** NTU Singapore — Weisong Sun. ReDeFo multi-agent pipeline.
**[REF-G07]** KTH ASSERT — Martin Monperrus. Prometheus, VeCoGen.
**[REF-G08]** Shanghai AI Lab — Veri-Code team. Re:Form.
**[REF-G09]** Nanjing University PASCAL Lab — Tian Tan. ChiSA, Tai-e framework.
**[REF-G10]** UC San Diego PL — Nadia Polikarpova. HiLDe, intent-based coding.
