# CARD Positioning

> Why CARD exists, why it's different from everything else, and how it wins.
> This document is for humans (investors, collaborators, press) and for BridgeSwarm context.

---

## 1. The Problem: Verification Debt

AI now generates 42% of all code [REF-P33]. But 96% of developers don't fully trust it, and only 48% verify before committing. AWS CTO Werner Vogels calls this **"verification debt"** — the growing gap between AI-generated code volume and verification coverage.

The result: 20% faster PRs, but 23.5% more incidents and 30% higher failure rates.

**"2025 was the year of AI speed. 2026 will be the year of AI quality."** — Industry consensus [REF-P33]

Every vibe coding tool — Cursor, Windsurf, Bolt, Lovable, Kiro — generates code. None mathematically verifies it. CARD is the verification layer they all need.

---

## 2. Why CARD Is Not MDD 2.0

Model-Driven Development (MDD/MDA) promised the same thing in the 2000s: write the model, generate the code. It died. Martin Fowler's team warns CARD risks the same fate [REF-P30].

Here's the honest autopsy and why CARD is structurally different:

| MDD Failure | What Killed It | CARD's Response | Status |
|-------------|---------------|-----------------|--------|
| **Round-trip engineering** | Devs edited generated code. Model-code diverged irreversibly. | Code is NEVER edited. Regenerated from scratch every build. Enforced architecturally, not by convention [REF-C07, REF-P29]. | **Solved** |
| **Template rigidity** | Generators couldn't handle edge cases. Devs hit walls. | LLMs handle ambiguity and edge cases. Qualitatively different from template generation. | **Improved** (new risk: non-determinism → mitigated by verification [REF-P34]) |
| **Wrong abstraction level** | UML was as complex as code. No one wanted to write it. | Natural language + simple invariants. 30-line minimum spec [REF-C01]. | **Improved** |
| **No lifecycle support** | Models abandoned after first generation. | Spec is the living artifact that evolves. Immune system grows invariants over time [REF-C09]. | **Reframed** |
| **Vendor lock-in** | Rational Rose, proprietary metamodels. | Open spec format (`.card.md`), MIT-licensed tools. | **Improvable by design** |
| **No verification loop** | Assumed "correct model = correct code." Silent failures. | 5-stage verification pipeline with formal mathematical proof [REF-T01]. | **Genuinely novel** |

### The Positioning Paragraph

> CARD is not MDD with better generation — it is MDD with a correctness signal. MDD's fatal flaw was not that it generated code from specs; it was that generation had no feedback loop. CARD severs this failure mode: generated code is structurally non-editable, and a formal verification loop rejects code that doesn't satisfy stated invariants. What MDD lacked — and what every current spec-driven tool including Tessl still lacks — is the ability to distinguish generated code that satisfies correctness requirements from code that merely compiles. CARD's invariant enforcement is the first answer to that question the field has ever had.

---

## 3. Competitor Map

### What Exists vs What CARD Does

| Feature | Tessl [REF-D01] | Kiro [REF-D02] | Augment Intent [REF-D03] | Spec Kit [REF-D04] | **CARD** |
|---------|------|------|---------------|----------|------|
| Spec-as-source | Exploring | No | Partial | No | **Yes** |
| Code regenerated from scratch | No | No | No | No | **Yes** |
| Formal verification (Dafny) | No | No | No | No | **Yes** |
| Tiered invariants | No | No | No | No | **Yes** |
| Self-improving invariants | No | No | No | No | **Yes** |
| Runtime invariant enforcement | No | No | No | No | **Yes** |
| Model-agnostic (swap LLMs) | Unclear | No | No | N/A | **Yes** |
| MCP server for IDE integration | Yes | Yes | No | Yes | **Yes** |
| Spec Registry (10K+ specs) | **Yes** | No | No | No | No |
| $125M+ funding | **Yes** | **AWS** | **$252M** | **GitHub** | No |

### Key Competitor Realities

**Tessl** ($125M, Guy Podjarny / Snyk founder): The most philosophically aligned competitor. But Fowler's team confirms they're only "exploring" spec-as-source — not productized [REF-P30]. No formal verification. No immune system. Their Spec Registry (10K+ library specs) is their real moat — not their generation pipeline.

**Amazon Kiro** (AWS-backed): Spec-driven IDE with property-based testing. Closest to CARD's PBT approach. But no formal verification, no code regeneration, no immune system.

**Axiom Math** ($200M, $1.6B valuation) [REF-D05]: Lean proof engine for quant finance. Targets PhDs, not developers. Not a developer-facing code verification product.

---

## 4. Academic Validation

CARD's approach is independently validated by multiple research groups:

- **Microsoft Research** (March 2026): Lahiri names "intent formalization" as a "grand challenge" [REF-P01]
- **York University** (March 2026): VibeContract independently proposes contract-guided vibe coding [REF-P09]
- **Stanford** (2024): Clover proves closed-loop verification works at 87% acceptance / 0% false positive [REF-P03]
- **MIT/BAIF** (POPL 2026): Vericoding benchmark shows 82-96% Dafny success [REF-P02]
- **Trail of Bits** (2025): Calls for "invariant-driven development" as first-class practice [REF-P31]
- **Martin Kleppmann** (2025): Predicts "AI will make formal verification mainstream" [REF-P28]

---

## 5. The Hardware Precedent

**CARD is not inventing a new paradigm. It's bringing an existing one from hardware to software.**

Chip companies (Intel, AMD, TSMC) have operated with exactly the CARD model for decades:
- **Spec** = C reference model (the source of truth)
- **Code** = RTL (generated, disposable)
- **Verification** = formal equivalence checking (mathematical proof that RTL matches spec)

The paper Prometheus [REF-P21] demonstrates transient code verification, while FormalRTL (arxiv 2603.08738) demonstrates the spec→generated-RTL→equivalence-checking paradigm at scale with AI-generated hardware in 2026. CARD applies the same paradigm to software: spec = `.card.md`, code = generated Python/JS, verification = Dafny + PBT.

**The pitch:** "We're bringing hardware verification practices to software. Chip companies have done this for decades. Now, with LLMs, software can too."

---

## 6. Market Validation

**$445M+ in VC funding for verified AI code in 90 days (Q1 2026):**

| Company | Round | Amount | Valuation | Focus |
|---------|-------|--------|-----------|-------|
| Axiom Math [REF-D05] | Series A | $200M | $1.6B | Lean proofs for quant finance |
| Code Metal | Series B | $125M | ~$250M | Code translation verification |
| Harmonic AI | Series C | $120M | $1.45B | Mathematical theorem proving |

All target PhDs and researchers. None target developers. The developer-facing gap is CARD's territory.

**Decision Intelligence market:** $15-19B (2025) → $57-68B (2032).

---

## 7. The 8 Literature Gaps CARD Addresses

From Agent 5 academic sweep [REF-P01 through REF-P35]:

| Gap | What's Missing | How CARD Addresses It |
|-----|---------------|----------------------|
| 1. Specification completeness | Nobody knows when a spec is "done" | Immune system continuously discovers new invariants [REF-C09] |
| 2. Incremental regeneration | No theory of partial regeneration | Modular architecture — regenerate per module [REF-P26] |
| 3. Spec evolution/versioning | No framework for spec change over time | `.card.md` is git-versioned; intent diff is the PR |
| 4. Production-scale verification | All benchmarks are toy scale | Module-level verification stays within proven ranges [REF-P02] |
| 5. Multi-spec conflict detection | Invariants from different specs may contradict | Constitution.card.md + module boundary declarations |
| 6. Performance contracts | Zero papers on verified latency/throughput | Constraints block in `.card.md` (future: formal perf verification) |
| 7. Developer UX for spec writing | Only HiLDe addresses this | 30-line minimum spec; tier escalation path |
| 8. Organizational study | No data on teams using spec-as-source | CARD's early customers ARE the study |

---

## 8. Adoption Playbook Summary

From Agent 3 research on how MCP, ESLint, Docker, and OpenClaw became standards:

### The 4 Non-Negotiable Moves

1. **Ship CARD as an MCP server on day one** [REF-T18]
   Every MCP-compatible tool (Cursor, Windsurf, Claude Code, TRAE, Tongyi Lingma, Kiro) can integrate CARD without any SDK work.

2. **Own the phrase "verification debt"**
   Use Werner Vogels' framing. Cite Sonar's 96%/48% data [REF-P33]. CARD is the structural solution.

3. **Get Bolt.new or Lovable to integrate first**
   Their non-technical users CAN'T verify code themselves. CARD solves an existential quality problem for these platforms.

4. **Separate the spec repo from the implementation repo**
   The `.card.md` format must be independently readable and implementable. This signals the format belongs to the community, not to CARD the company.

### Integration Priority

| Wave | Target | Why | Timeline |
|------|--------|-----|----------|
| 1 | Bolt.new, Lovable, GitHub Spec Kit | Highest need, easiest integration | Month 1-3 |
| 2 | Windsurf, Kiro | Enterprise + spec-driven alignment | Month 3-6 |
| 3 | Tongyi Lingma, TRAE, CodeBuddy | Chinese market via MCP | Month 6-12 |

### Timeline to "Required"

Based on precedent: MCP took 13 months to Linux Foundation. ESLint took 2.5 years. Docker took 3 years. Realistic timeline for CARD to become genuinely "required": **24-30 months** if first 6 months execute correctly.

---

## 9. Business Model

**Phase 1 (Launch):** Open-source CLI + MCP server. MIT license. Free forever.

**Phase 2 (Growth):** CARD Cloud — hosted registry of verified contract templates, team management, audit logs.

**Phase 3 (Scale):** CARD Enterprise — on-premise deployment, SSO/SCIM, compliance reporting, "CARD Verified" certification badges.

**Revenue model:** Subscription SaaS. Free tier for individual devs. $50-200/month for teams. Enterprise pricing for large orgs.

**The moat compounds:**
- The contract registry grows with community contributions (network effect)
- The `.card.md` format becomes the standard (format lock-in)
- Enterprise audit trails are not portable (data moat)
- The immune system's invariant library gets stronger over time (self-improving moat)
