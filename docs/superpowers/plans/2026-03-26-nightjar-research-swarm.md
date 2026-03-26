# Nightjar Research Swarm — Discover, Don't Prescribe

> This is a RESEARCH swarm, not a build swarm. Scouts discover solutions. Coordinator synthesizes. Adversarial reviewer kills weak findings. Output: one approved plan document ready for a BUILD swarm.

---

## Current State: What Nightjar IS

Nightjar (formerly contractd/CARD) is a verification layer for AI-generated code. Built in Swarm #1:
- `.card.md` spec parser (YAML frontmatter + Markdown body)
- 5-stage verification pipeline (preflight → deps → schema → PBT → Dafny)
- Clover-pattern retry loop
- Analyst → Formalizer → Coder generation pipeline via litellm
- CLI: init, generate, verify, build, ship, retry, lock, explain
- MCP server: verify_contract, get_violations, suggest_fix
- 159 unit tests passing, 2,920 lines Python
- Live-tested: DeepSeek generates Dafny code, pipeline catches errors

**Full architecture:** See `docs/ARCHITECTURE.md`
**All references:** See `docs/REFERENCES.md` (35 papers, 26 tools, 11 concepts)
**Positioning:** See `docs/POSITIONING.md`

---

## Known Weaknesses (Candid Assessment)

**W1 — Dafny Hallucination Gap:** LLMs hallucinate on complex Dafny. The 5-retry limit becomes a bottleneck. Specialized/premium models help but complex data structures still fail cyclically.

**W2 — Developer Friction:** Writing invariants (especially `property` or `formal` tier) requires explicit programmatic thinking — the opposite of vibe coding. Limits realistic adoption to regulated domains unless invariants are auto-generated.

**W3 — Verification Latency:** 10-55+ seconds per build. Modern devs expect sub-second HMR. A 30-50s feedback loop kills flow.

**W4 — Daikon Reimplementation:** The Fuzzingbook DynamicInvariants implementation is CC-BY-NC-SA (non-commercial). Must clean-room reimplement. Math-heavy ~300 lines.

---

## Swarm Configuration: 10 Agents

| # | Name | Role | Model | Phase |
|---|------|------|-------|-------|
| 1 | **Coordinator** | Synthesize all findings → `nightjar-evolution-plan.md` | **Opus** | Phase 2 |
| 2 | **Adversarial Reviewer** | Stress-test synthesis, kill hallucinations | **Opus** | Phase 3 |
| 3 | **Scout-Dafny** | Kill W1: formal verification alternatives + enhancements | **Sonnet** | Phase 1 |
| 4 | **Scout-ZeroFriction** | Kill W2: auto-generate invariants, invisible verification | **Sonnet** | Phase 1 |
| 5 | **Scout-Speed** | Kill W3: sub-second verification feedback | **Sonnet** | Phase 1 |
| 6 | **Scout-Mining** | Kill W4: invariant mining beyond Daikon | **Sonnet** | Phase 1 |
| 7 | **Scout-Unmatched** | Features nobody has — the "holy shit" factor | **Sonnet** | Phase 1 |
| 8 | **Scout-Frontier** | Beyond agentic engineering — position for the future | **Sonnet** | Phase 1 |
| 9 | **Scout-Demo** | State-of-art visual demo + hosted API + revenue + branding psychology | **Sonnet** | Phase 1 |
| 10 | **Scout-Harvest** | Open-source intelligence harvesting — clean-room playbook | **Sonnet** | Phase 1 |

### Permissions & MCP

**All agents: `--dangerously-skip-permissions`**

| MCP Tool | Coordinator | Reviewer | All Scouts |
|----------|------------|----------|------------|
| `sequential-thinking` | Yes | Yes | Yes |
| `context7` | Yes | Yes | Yes |
| `github` | Yes | Yes | Yes |
| `WebSearch` | Yes | No | **Yes** |
| `WebFetch` | Yes | No | **Yes** |
| `bridgemind` | Yes | No | No |

**EXCLUDED:** brave, exa, coingecko, ccxt, duckdb

### Swarm Skills

- Incremental Commits: OFF (research, not code)
- Test-Driven: OFF
- Code Review: ON (scouts review each other's logic)
- Documentation: ON (structured output required)
- Security Audit: OFF
- DRY Principle: OFF
- Accessibility: OFF
- Keep CI Green: OFF
- Migration Safe: OFF
- Performance: OFF

---

## Phase 1: Scout Missions (8 Scouts in Parallel)

### RESEARCH METHODOLOGY (ALL SCOUTS FOLLOW THIS)

```
1. Use sequential-thinking MCP to plan your search strategy BEFORE searching
2. Search in BOTH English AND Chinese (use proper language for each query)
3. For every finding: provide URL, evidence, honest assessment
4. Check GitHub repos with github MCP — examine actual code, not just READMEs
5. Use context7 MCP to query library documentation for technical details
6. DO NOT HALLUCINATE — if you can't find something, say "not found"
7. Score every finding honestly (1-10) on: relevance, maturity, clean-room feasibility
8. Look for tools with ANY license — we will clean-room reimplement, not copy code
9. Prioritize WORKING tools over theoretical papers
10. Each scout outputs a STRUCTURED REPORT (see deliverables below)
```

---

### Scout 3: Kill the Dafny Gap

**Mission:** Find every tool, model, technique, and approach that makes formal verification of LLM-generated code FASTER, MORE RELIABLE, or UNNECESSARY.

**Search (English):**
- "formal verification alternative to Dafny faster 2025 2026"
- "LLM proof generation specialized model"
- "tree search proof strategy MCTS verification"
- "graceful degradation formal verification property testing fallback"
- "Lean4 vs Dafny vs Verus speed comparison LLM"
- "formal verification without theorem prover"
- "lightweight verification AI generated code"
- "probabilistic verification instead of formal proof"

**Search (Chinese):**
- "形式化验证 替代方案 比Dafny更快 2025 2026"
- "LLM 证明生成 专用模型"
- "轻量级验证 AI生成代码"
- "概率验证 代替形式化证明"
- "树搜索 证明策略 MCTS"

**GitHub searches:**
- Repos: "formal verification fast", "proof generation LLM", "lightweight code verification"
- Examine: Re:Form, DeepSeek-Prover-V2, Goedel-Prover-V2, Leanstral, VerMCTS
- Look for: any tool that verifies code correctness WITHOUT full Dafny/Lean proofs

**Key questions to answer:**
1. Is there a verification approach that gives 80% of Dafny's guarantees in 1/10th the time?
2. Can specialized small models (0.5B-7B) running LOCALLY replace API calls for proof generation?
3. What's the fastest possible formal verification loop? Can it be sub-5-seconds?
4. If Dafny fails, what's the best fallback that's still better than "just run tests"?
5. Are there probabilistic/statistical verification methods that are "good enough" for most code?

**Deliverables:**
- Every alternative verification tool (name, URL, approach, speed, accuracy, license)
- Every specialized proof model (name, size, performance, can it run locally?)
- The FASTEST viable verification approach with evidence
- Clean-room candidates: which tools have brilliant algorithms we should reimplement?
- Honest assessment: should we REPLACE Dafny entirely or SUPPLEMENT it?

---

### Scout 4: Zero-Friction Verification

**Mission:** Find every tool and technique that makes code verification INVISIBLE to the developer. The developer writes natural language ONLY — the system generates all invariants, specs, and proofs automatically.

**Search (English):**
- "auto generate invariants from natural language"
- "invisible formal verification developer experience"
- "AI generates specifications automatically from code"
- "zero-config code verification tool"
- "vibe coding with automatic verification"
- "specification inference from intent natural language"
- "contract generation from docstring automatically"

**Search (Chinese):**
- "自动生成不变量 从自然语言"
- "无感知 代码验证 开发者体验"
- "AI自动生成规约 从代码"
- "零配置 代码验证"
- "从意图自动生成契约"

**GitHub searches:**
- Repos: "auto invariant generation", "specification inference", "contract from docstring"
- Examine: NL2Contract, AutoSpec, Agentic PBT approach, Kiro's property generation
- Look for: anything that generates formal specs without developer input

**Key questions:**
1. Can an LLM generate ALL invariants from just intent + acceptance criteria (no formal input)?
2. What's the best "invariant suggestion" UX? (propose → approve vs auto-apply)
3. How does Kiro's property-based test generation work internally? Can we adopt the approach?
4. Is there a tool that watches code RUNNING and generates invariants without ANY developer input?
5. What's the adoption rate of tools that require formal specs vs tools that auto-generate them?

**Deliverables:**
- Every auto-generation tool (name, URL, input required, output, accuracy, license)
- The UX patterns that make verification feel like "it just works"
- Clean-room candidates for invariant auto-generation
- Honest assessment: can we make invariant writing 100% optional for the developer?

---

### Scout 5: Sub-Second Verification Feedback

**Mission:** Find every technique that makes verification feedback INSTANT or near-instant. Modern devs expect sub-second HMR — we need to match or approach that.

**Search (English):**
- "real-time code verification IDE instant feedback"
- "incremental formal verification only changed code"
- "background verification developer workflow"
- "local LLM inference sub-second code verification"
- "verification caching strategies beyond hashing"
- "hot module replacement formal verification compatible"
- "ESLint real-time verification pattern"

**Search (Chinese):**
- "实时代码验证 IDE 即时反馈"
- "增量验证 只验证修改部分"
- "后台验证 开发者工作流"
- "本地LLM推理 亚秒级 代码验证"
- "验证缓存策略"

**GitHub searches:**
- Repos: "incremental verification", "real-time code analysis", "fast formal verification"
- Examine: how ESLint, TypeScript compiler, Rust borrow checker achieve real-time feedback
- Look for: any verification tool with <1 second feedback loop

**Key questions:**
1. Can verification run on EVERY keystroke (like ESLint) or only on save?
2. What's the minimum verification that gives useful feedback in <1 second?
3. Can we split verification: instant (stages 0-2) + deferred (stages 3-4)?
4. How small can a local proof model be while still being useful? Can 0.5B run on CPU?
5. What caching strategies exist beyond hash-matching? Semantic similarity caching?

**Deliverables:**
- Every technique for fast verification with latency numbers
- Local model options with speed benchmarks
- Caching strategies ranked by effectiveness
- The architecture for "verify while you type"
- Honest assessment: what's the realistic fastest we can achieve?

---

### Scout 6: Invariant Mining Revolution

**Mission:** Find every approach to automatically discovering what "rules" code follows — without Daikon, without Fuzzingbook, across ALL languages. Find the BEST algorithm to clean-room implement.

**Search (English):**
- "dynamic invariant detection Python 2025 2026"
- "specification mining without Daikon alternative"
- "LLM infer invariants from execution traces"
- "runtime assertion inference automatic"
- "program behavior mining tool"
- "property discovery from test execution"

**Search (Chinese):**
- "动态不变量检测 Python 2025 2026"
- "规约挖掘 Daikon替代方案"
- "LLM 从执行轨迹推断不变量"
- "运行时断言推断 自动化"
- "程序行为挖掘 工具"

**GitHub searches:**
- Repos: "invariant mining", "specification mining", "property inference", "dynamic analysis"
- Examine: DIG, TrainCheck, InvariantAnnotator, MonkeyType, CrossHair
- Look for: ANY tool that discovers program properties from runtime behavior

**Key questions:**
1. What's the simplest algorithm that discovers 80% of useful invariants?
2. Can LLMs replace the entire Daikon algorithm? (trace → LLM → invariants, no templates)
3. What invariant templates are most useful for WEB applications specifically?
4. Is there a Python library that does runtime tracing BETTER than sys.settrace?
5. What's the state of the art for JavaScript/TypeScript invariant mining?

**Deliverables:**
- Every mining tool across all languages (name, URL, algorithm, license)
- The TOP 3 algorithms to clean-room implement, ranked by value/effort ratio
- LLM-only approaches that bypass traditional mining entirely
- Clean-room implementation guide: what to study, what to reimplement, how
- Honest assessment: is traditional invariant mining still worth it, or do LLMs make it obsolete?

---

### Scout 7: Features Nobody Has

**Mission:** Find capabilities that would make Nightjar the ONLY tool anyone considers. Things Tessl ($125M), Kiro (AWS), Axiom ($200M), and every other competitor CANNOT easily replicate.

**Search (English):**
- "unique AI code verification feature 2026"
- "developer tool competitive moat"
- "what developers wish existed AI coding 2026"
- "AI code generation biggest unsolved problem"
- "agentic coding missing feature pain point"
- reddit/HN: "I wish my AI coding tool could"

**Search (Chinese):**
- "AI代码验证 独特功能 2026"
- "开发者工具 竞争壁垒"
- "开发者最想要的AI编程功能"
- "AI代码生成 最大未解决问题"
- Zhihu/CSDN: "希望AI编程工具能做到"

**GitHub searches:**
- Trending repos in AI coding tools (last 30 days)
- Issues/discussions on Cursor, Windsurf, Bolt repos — what do users complain about?
- Look for: gaps nobody is filling

**Key questions:**
1. What's the ONE feature that would make a developer switch from Cursor to Nightjar?
2. What's the "immune system for code" equivalent in a feature nobody has built?
3. Is there a way to make verification itself VALUABLE (not just a gate but a feature)?
4. What would make a CTO mandate Nightjar across their entire organization?
5. What's the "MiroFish moment" — the demo feature that makes people say "holy shit"?

**Deliverables:**
- Top 10 unmet needs in the AI coding space with evidence
- Top 5 features that would make Nightjar unmatched
- The "holy shit" feature — what it is, why it works, how to build it
- Competitive analysis: what Tessl/Kiro/Axiom CANNOT do and why
- Honest assessment: which features are gimmicks vs genuine differentiators?

---

### Scout 8: Beyond Agentic Engineering

**Mission:** Find what comes AFTER the current multi-agent swarm paradigm. How should Nightjar position for the computing era that follows vibe coding and agentic engineering?

**Search (English):**
- "what comes after agentic AI 2026 2027"
- "post-swarm computing paradigm"
- "latent space communication between AI agents"
- "ephemeral software runtime 2026"
- "ADAS automated design agentic systems product"
- "software without source code future"
- "Karpathy Software 3.0 what's next"

**Search (Chinese):**
- "智能体之后 下一代计算范式"
- "后群体智能 计算范式"
- "潜在空间通信 AI智能体"
- "临时性软件 运行时"
- "无源代码 软件未来"

**Key questions:**
1. If code becomes ephemeral (regenerated every build), what's the PERMANENT artifact?
2. How does Nightjar's "spec is truth, code is exhaust" position it for Software 3.0?
3. Is there a way Nightjar becomes the COMPILER for the post-code era?
4. What paradigm could Nightjar INVENT (like MiroFish invented "swarm prediction")?
5. What would make Nightjar relevant in 2029, not just 2026?

**Deliverables:**
- Top 5 post-agentic paradigms with evidence of emergence
- How Nightjar maps to each paradigm
- The paradigm Nightjar could OWN (name it, define it)
- Specific technical directions to invest in now for future positioning
- Honest assessment: is the "spec-as-source" paradigm durable or transitional?

---

### Scout 9: Visual Demo + Hosted Product + Branding Psychology

**Mission:** Find what makes AI product demos go viral, how to build a hosted verification API on Cloudflare, how to monetize it, and the psychology behind memorable developer tool branding.

**Search (English):**
- "most viral AI product demo 2025 2026 what made it work"
- "developer tool demo went viral analysis"
- "Cloudflare Workers AI verification API deploy"
- "Stripe usage-based billing developer tool"
- "developer tool branding psychology memorable name"
- "open source developer tool revenue model AGPL dual license"
- "MiroFish demo why it went viral"
- "how to make technical demo visually compelling"

**Search (Chinese):**
- "AI产品演示 病毒式传播 2025 2026"
- "开发者工具 品牌心理学"
- "开源开发者工具 收入模式 AGPL"
- "MiroFish演示 为什么火了"
- "技术产品 视觉吸引力"

**Key questions:**
1. What visual elements make a 60-second demo screenshot-shareable?
2. How to deploy a verification API on Cloudflare Workers that charges per use?
3. What's the psychology of developer tool names? Why do some stick and others don't?
4. How does "Nightjar" (夜鹰) resonate psychologically in both English and Chinese?
5. What revenue infrastructure is fastest to deploy? (Stripe, Lemon Squeezy, Paddle?)
6. What demo FORMAT works best? (Terminal recording? Web UI? Live coding? Challenge?)
7. How did the most successful AGPL projects monetize? Specific numbers.

**Deliverables:**
- Top 5 most viral AI demos of 2025-2026 — what made each one work
- Cloudflare Workers deployment architecture for verification API
- Revenue stack: payment provider + pricing model + billing integration
- Branding analysis: "Nightjar" strengths/weaknesses, logo direction, color psychology
- The demo script: exactly what to show in 60 seconds for maximum viral impact
- AGPL monetization playbook with specific revenue numbers from real companies
- Honest assessment: what's the realistic revenue in month 1, 3, 6?

---

### Scout 10: Open-Source Intelligence Harvest

**Mission:** Find the most brilliant open-source algorithms across ANY license that Nightjar should study and clean-room reimplement. The legal playbook for extracting intelligence without violating licenses.

**Search (English):**
- "clean room implementation legal open source"
- "reimplement algorithm from GPL code legally"
- "best formal verification algorithms to study"
- "brilliant open source code analysis tools 2025"
- "open source tools with restricted license amazing algorithm"
- "clean room reverse engineering software legal precedent"

**Search (Chinese):**
- "洁净室实现 开源合法"
- "从GPL代码重新实现算法 合法"
- "优秀开源代码分析工具 2025"
- "受限许可证 优秀算法 开源工具"

**GitHub searches:**
- Tools with GPL/AGPL/CC-BY-NC-SA licenses that have brilliant verification/mining algorithms
- Academic codebases that implement state-of-art algorithms
- Look for: code we should READ (for the algorithm) then REIMPLEMENT (under MIT)

**Key questions:**
1. What are the TOP 10 algorithms (from any license) that Nightjar should know?
2. What's the legal boundary of clean-room implementation? Specific precedents.
3. Are there any PATENTED algorithms we must avoid?
4. What academic codebases have the best invariant mining implementations?
5. What algorithms from HARDWARE verification could we bring to software?

**Deliverables:**
- Top 10 algorithms to clean-room (name, source, license, what it does, why it's brilliant)
- The legal playbook: clean-room implementation dos and don'ts with precedents
- Patent landscape: any algorithms we must avoid?
- Hardware → software transfer opportunities
- Honest assessment: how much effort is each clean-room implementation?

---

## Phase 2: Coordinator Synthesis

**Agent:** Coordinator (Opus)

**After ALL 8 scouts complete, the Coordinator:**

1. Reads every scout report
2. Cross-references findings (tool X mentioned by Scout 3 AND Scout 6 = high signal)
3. Identifies conflicts (Scout 5 says X, Scout 7 says opposite)
4. Produces: `nightjar-evolution-plan.md` containing:

```
SECTION 1: WEAKNESS ELIMINATION
  For each weakness (W1-W4):
  - The best solution(s) found across all scouts
  - Specific tools to clean-room from
  - Implementation approach
  - Expected outcome

SECTION 2: NEW CAPABILITIES
  Prioritized list of features to add:
  - Feature name + description
  - Why it matters (competitive advantage or user value)
  - Tools/algorithms to adopt
  - Clean-room requirements

SECTION 3: FRONTIER POSITIONING
  How Nightjar positions for the post-agentic era:
  - The paradigm to own
  - Technical investments to make now
  - The 2029 vision

SECTION 4: DEMO + REVENUE
  - The viral demo script (60 seconds)
  - The business demo script (5 minutes)
  - Hosted API architecture (Cloudflare Workers)
  - Revenue model with specific pricing
  - Branding refinement

SECTION 5: BUILD SWARM PLAN
  The ready-to-deploy BUILD swarm configuration:
  - 10 Opus agents
  - Renamed: contractd → nightjar
  - All tasks with file ownership
  - Reference-first development gates
  - Scout findings as required reading per task
  - Full bypass permissions
  - MCP tool assignments
  - Swarm mission brief
  - Supporting context files to attach

SECTION 6: CLEAN-ROOM REGISTER
  Every algorithm to reimplement:
  - Source tool + license
  - Algorithm description (from paper, NOT from code)
  - Our MIT implementation plan
  - Estimated effort
```

**The Coordinator follows OUR methodology:**
- Reference-first: every recommendation cites a specific scout finding
- Antisycophantic: flag recommendations that are weak or uncertain
- No hallucination: if scouts didn't find evidence, don't invent it
- Honest scoring: rank every recommendation by (impact × feasibility)
- The output must be actionable by a 10-Opus BUILD swarm immediately

---

## Phase 3: Adversarial Review

**Agent:** Adversarial Reviewer (Opus)

**Reads the Coordinator's synthesis and ATTACKS it:**

1. Every cited tool — does it actually exist? (Check URLs)
2. Every clean-room candidate — is the algorithm actually described in a paper (not just in the code)?
3. Every "holy shit" feature — is it genuinely novel or does a competitor already have it?
4. Every revenue projection — is it grounded in comparable data?
5. The build swarm plan — are file ownerships non-overlapping? Are dependencies correct?
6. Any finding that seems too good to be true — verify independently

**Output:** APPROVED with issues list, or REJECTED with specific fixes required.

---

## Swarm Mission Brief (paste into BridgeSwarm)

```
RESEARCH SWARM: Discover how to make Nightjar revolutionary.

Nightjar is a verification layer for AI-generated code (formerly contractd/CARD).
Built: parser, 5-stage verification, retry loop, generation pipeline, CLI, MCP server.
159 tests passing. Live-tested with DeepSeek.

THIS SWARM DISCOVERS — it does NOT build.

8 Scouts research in parallel. Each searches English + Chinese sources.
Each returns structured findings with URLs and evidence.
Then the Coordinator synthesizes ALL findings into nightjar-evolution-plan.md.
Then the Adversarial Reviewer stress-tests the plan.
OUTPUT: one approved .md document ready for a BUILD swarm.

SCOUT MISSIONS:
Scout 3: Kill Dafny verification bottleneck — find faster/better alternatives
Scout 4: Kill developer friction — find auto-invariant generation tools
Scout 5: Kill latency — find sub-second verification techniques
Scout 6: Kill Daikon dependency — find better mining algorithms to clean-room
Scout 7: Find features nobody else has — the "holy shit" factor
Scout 8: Find what comes after agentic engineering — future positioning
Scout 9: Find viral demo patterns + hosted API + revenue model + branding
Scout 10: Find open-source algorithms to harvest via clean-room implementation

METHODOLOGY:
- Use sequential-thinking MCP before searching
- Search in BOTH English AND Chinese (proper language per query)
- Every finding needs: URL, evidence, honest score (1-10)
- Check GitHub repos with github MCP — examine actual code
- Use context7 MCP for library documentation
- DO NOT HALLUCINATE — say "not found" if you can't find it
- Look at tools with ANY license — we clean-room, not copy
- Prioritize WORKING tools over theoretical papers

COORDINATOR (Opus):
After ALL scouts complete, synthesize into nightjar-evolution-plan.md:
- Weakness elimination plan
- New capability additions
- Frontier positioning
- Demo + revenue architecture
- Ready-to-deploy BUILD swarm plan (10 Opus agents)
- Clean-room register (every algorithm to reimplement)

ADVERSARIAL REVIEWER (Opus):
Kill anything hallucinated, ungrounded, or impractical.
Verify URLs. Check competitors. Stress-test the build plan.

KEY CONTEXT FILES (attached):
- CLAUDE.md — project rules
- docs/ARCHITECTURE.md — current system design
- docs/REFERENCES.md — existing citation library
- docs/POSITIONING.md — competitive landscape
```

---

## Supporting Context to Attach

1. `CLAUDE.md`
2. `docs/ARCHITECTURE.md`
3. `docs/REFERENCES.md`
4. `docs/POSITIONING.md`
5. This plan document

---

## Swarm Skills

| Toggle | Setting |
|--------|---------|
| Incremental Commits | OFF |
| Code Review | ON |
| Documentation | ON |
| All others | OFF |
