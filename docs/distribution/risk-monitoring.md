# Risk Monitoring Playbook

Based on the unknown unknowns analysis from the SEO/AEO research (March 28, 2026). This playbook defines what to watch, how to watch it, trigger conditions, and response actions for each risk category.

---

## How to Use This Document

Each risk has:
- **Watch signal:** What to monitor and where
- **Trigger condition:** The specific event that activates a response
- **Response:** What to do when triggered, in order
- **Owner:** Whoever is responsible at the time this fires

Set up all monitoring in the first week. Most of it is free and takes under an hour to configure.

---

## Category 1: Competitor Launches

### C1-A: CrossHair major version release or positioning pivot

**Watch signal:**
- GitHub releases feed: https://github.com/pschanely/CrossHair/releases.atom
- pschanely's blog RSS: https://pschanely.github.io/feed.xml
- CrossHair Discord: https://discord.gg/rUeTaYTWbb

**Trigger condition:** CrossHair releases a version that adds any of: multi-stage pipeline, spec file format, LLM integration, dependency scanning, or "AI-generated code" in release notes.

**Response:**
1. Read the release notes completely within 24 hours
2. Update the competitor response guide (this file + `/compare/nightjar-vs-crosshair` page)
3. If CrossHair adds a spec format: publish a technical comparison of `.card.md` vs their format within 1 week — focus on CEGIS loop and immune system as differentiators
4. If CrossHair adds LLM integration: accelerate publishing the formal proof demo that shows something CrossHair misses

**Priority:** HIGH — CrossHair is the most technically proximate tool.

---

### C1-B: Skylos major feature expansion

**Watch signal:**
- GitHub releases: https://github.com/duriantaco/skylos/releases.atom
- Skylos Discord (if available)
- r/Python (skylos posts track there: https://www.reddit.com/r/Python/)

**Trigger condition:** Skylos adds formal proof, Hypothesis integration, or "AI-generated code verification" framing.

**Response:**
1. Update competitor response guide with new feature comparison
2. If their star count exceeds 1,000: update comparison page headline to reflect they are a real competitor, not adjacent
3. If they position as "the Nightjar alternative": publish a point-by-point technical comparison within 1 week

**Priority:** MEDIUM — currently 100–400 stars, SAST-only.

---

### C1-C: Big-player entry (GitHub Copilot, Cursor, JetBrains Qodana, Sonar)

**Watch signal:**
- GitHub Changelog: https://github.blog/changelog/
- JetBrains blog: https://blog.jetbrains.com/
- Sonar blog: https://www.sonarsource.com/blog/
- Google Alerts: "formal verification Python" + "AI code verification" + "Dafny Python"
- HN front page daily scan (no automation needed — just check)

**Trigger condition:** Any Tier-1 player (GitHub, JetBrains, Sonar, Snyk, Checkmarx) announces a feature described as "formal verification," "contract-based testing," or "spec-driven AI code verification."

**Response (within 48 hours):**
1. Read their announcement fully
2. Identify technical overlap vs. differentiation honestly
3. If overlap is substantial: fast-track commercial licensing outreach to any Nightjar users — convert them before they switch
4. If overlap is shallow (just marketing terminology): publish "Why [BigPlayer]'s new feature isn't formal verification" — technical post targeting the shared keywords
5. Notify any enterprise pipeline customers or design partners immediately

**Priority:** CRITICAL — this is the existential risk scenario (M2). Response time matters.

---

### C1-D: New entrant in "vericoding" space

**Watch signal:**
- Google Alerts: "vericoding" + "formal verification Python tool" + "AI code verification pipeline"
- Arxiv cs.SE weekly digest: https://arxiv.org/list/cs.SE/recent
- Martin Kleppmann coined "vericoding" (December 2025 post) — watch his blog: https://martin.kleppmann.com/

**Trigger condition:** A new tool appears on HN, GitHub trending, or arXiv with >500 stars within 30 days that directly overlaps Nightjar's pipeline.

**Response:**
1. Evaluate their technical approach in depth (1 day)
2. Decide: differentiate or potentially partner/integrate
3. If differentiation is clear: publish comparison content within 1 week of their HN post (they will have traffic)
4. If they are technically superior on a specific stage: consider contributing to them and building on top

---

## Category 2: Community Backlash

### C2-A: Disputed bug report / false positive claim

**Watch signal:**
- GitHub Issues on any affected repo mentioning Nightjar
- Twitter/X search: "nightjar false positive" + "nightjar wrong" + "nightjarzzz"
- HN search: site:news.ycombinator.com "nightjar"

**Trigger condition:** A package maintainer publicly claims a Nightjar finding is incorrect, or an HN/Reddit thread accuses Nightjar of generating false positives.

**Response (within 12 hours):**
1. Read the claim in full — do not respond until you understand their argument
2. Attempt to reproduce the disputed finding independently on a clean environment
3. If you were wrong: post a public correction immediately, update the scan results page to mark the finding as disputed/retracted, and contact the maintainer directly
4. If you were right: post a detailed technical response with the exact reproduction script, Python version, package version, and output. Do not argue — just show the evidence
5. If it's ambiguous: post "We're investigating — here's what we know so far" within 24 hours to prevent the dispute from running unaddressed

**What not to do:** Do not delete the finding while it's under dispute. Do not argue with tone. If the finding is retracted, say so publicly and clearly.

**Priority:** HIGH — one credible false-positive accusation in a high-visibility thread can permanently damage the scan campaign's credibility.

---

### C2-B: "Nightjar scanned my repo without permission" complaint

**Watch signal:**
- GitHub Issues on repos Nightjar has publicly scanned
- Twitter/X mentions

**Trigger condition:** A maintainer objects to their repository being scanned or their project being mentioned in scan results.

**Response:**
1. Acknowledge their objection respectfully and immediately
2. Explain: Nightjar runs static analysis on public code (same as Snyk, Semgrep, CodeClimate, Dependabot)
3. Offer to remove their project from the public scan results if they prefer — make this easy to request
4. Add a "Remove my project from scan results" form to nightjarcode.dev/scan/ proactively

**Priority:** MEDIUM — this is manageable if handled promptly and professionally.

---

### C2-C: AGPL enforcement accusation or license dispute

**Watch signal:**
- Google Alerts: "nightjar AGPL" + "nightjarzzz license"
- GitHub Issues on j4ngzzz/Nightjar

**Trigger condition:** A company or developer publicly claims the AGPL is being applied in bad faith, or that Nightjar's license terms are misleading.

**Response:**
1. Consult with a lawyer before responding publicly (do this within 24 hours if it gains traction)
2. Post a clear, factual explanation of what AGPL requires and does not require in Nightjar's context
3. Offer a complimentary 30-day commercial license trial to any party in genuine good-faith dispute

---

## Category 3: Technical Risks Materializing

### C3-A: "Dafny-Python semantic gap" surfaces on HN

**Trigger condition:** An HN comment or post accurately describes the gap (Stage 4 proves a Dafny model, not native Python bytecode) and gains traction (10+ upvotes or front-page visibility).

**Response (within 4 hours):**
1. Post an honest, technically detailed response in the thread — do not deflect
2. If you haven't already: publish `/docs/pipeline#dafny-semantics` page explaining the gap proactively, and link to it in your response
3. Update the Stage 4 documentation to be explicit: "Stage 4 uses Dafny to verify a formal model of your function. CrossHair in the same stage verifies native Python bytecode. They catch different classes of errors."
4. Frame the response positively: the transparency is the point, and you caught the distinction before anyone was misled

**What not to do:** Do not claim the gap doesn't exist. Do not be defensive about it. Developers who understand it respect honesty.

---

### C3-B: Dafny installation failure rate causes user drop-off

**Watch signal:**
- PyPI download stats + GitHub issue reports on "Dafny not found" / ".NET runtime" errors
- Support requests

**Trigger condition:** >20% of GitHub issues in the first month mention Dafny installation failure.

**Response:**
1. Ship a `nightjar check-deps` command that outputs exactly what is and isn't installed and what capability level the tool is running at
2. Ensure the CLI output says "Stage 4: CrossHair-only (Dafny not installed)" — never silently degrade
3. Add a Dafny installation guide specific to each OS to the docs
4. Consider shipping a `--no-dafny` flag to make the degraded mode explicit choice rather than silent default

---

### C3-C: Spec-writing friction drives away new users

**Watch signal:**
- Time-to-first-successful-verify metrics (if you add telemetry)
- GitHub Issues: "I don't know how to write a card file" / "init didn't work"
- Churn from email signups

**Trigger condition:** >30% of GitHub issues are about spec format confusion in the first 60 days.

**Response:**
1. Invest in `nightjar init` auto-generation quality — this is the highest-ROI friction reducer
2. Add a zero-spec mode: `nightjar verify --auto` that runs Stages 0–3 with inferred contracts and no spec file
3. Ship 5 worked examples in the repo covering common patterns (REST API, CLI tool, async service, data pipeline, auth module)

---

## Category 4: Trademark and Legal

### C4-A: Trademark conflict with existing "Nightjar" entities

**Watch signal:**
- USPTO TESS search: https://tmsearch.uspto.gov/ — search "NIGHTJAR" in International Class 42 (computer services) and Class 9 (software)
- UK IPO search: https://trademarks.ipo.gov.uk/ — search "NIGHTJAR"
- Known entities to watch: nightjarsoftware.com (frontend dev agency), nightjar.co (UK digital studio)

**Trigger condition:** Any of the following:
- A cease-and-desist letter arrives
- A USPTO opposition is filed against a Nightjar trademark application
- nightjarsoftware.com or nightjar.co gains significantly in visibility (indicates they may start protecting the name)

**Response:**
1. File USPTO trademark application in Class 42 (computer services / software as a service) and Class 9 (downloadable software) before this happens — do this within 90 days of launch
2. If C&D arrives before filing: immediately engage a trademark attorney; do not respond to the C&D yourself
3. If the plain name `nightjar` is unregistrable: establish "Nightjar Code" or "NightjarVerify" as the brand early rather than at crisis time

**Proactive action (time-sensitive):** The SEO research identified that `nightjar` on PyPI is taken (hence `nightjarzzz`). This suggests a potential namespace conflict. Investigate: who owns the `nightjar` PyPI package, when it was created, and whether it's active. If abandoned, file a PyPI name transfer request.

---

### C4-B: CVE dispute — maintainer claims finding is wrong

**Watch signal:**
- GitHub Security Advisory responses
- MITRE CVE assignment process

**Trigger condition:** A maintainer formally disputes a CVE you've filed, or MITRE rejects a CVE submission citing disputed methodology.

**Response:**
1. Engage technically, not legally — provide the reproduction script, environment details, and exact output
2. If you are wrong: withdraw the CVE request immediately and issue a public correction
3. If the dispute is about severity, not validity: accept their severity assessment while maintaining the finding is real
4. Never threaten legal action. Never escalate to public shaming before the 90-day disclosure window.

**Add to all scan result pages:** "Nightjar's analysis is automated. All reported findings have been manually verified via reproduction script. If you believe a finding is incorrect, file an issue at github.com/j4ngzzz/Nightjar."

---

## Category 5: Market and Positioning

### C5-A: "Vibe coding" terminology becomes cringe / burns out

**Watch signal:**
- Google Trends: "vibe coding" search volume (monthly check)
- HN sentiment: search for "vibe coding" on HN monthly — are the posts mocking or earnest?

**Trigger condition:** "Vibe coding" search volume drops >50% from peak AND the HN framing shifts predominantly to ridicule.

**Response:**
1. Retire "vibe coding" from the product landing page and replace with "AI-generated code"
2. Keep it in blog posts written before the shift (historical content, not deceptive)
3. Lead with "AI code security" and "regenerative development" in all new marketing materials

**What not to do:** Don't let the homepage lead with a buzzword that's turned cringe. Monitor quarterly and update.

---

### C5-B: Solo developer commercial pricing is blocking adoption

**Watch signal:**
- Conversations in issues or DMs: "I'd pay for a solo license but $2,400 is too much"
- PyPI download growth rate stalls despite GitHub interest

**Trigger condition:** 5+ GitHub issues or community discussions mention the price gap in the same quarter.

**Response:**
1. Add a solo developer tier at $200–400/yr (this is the standard JetBrains/Datadog pattern)
2. Announce on HN/Twitter as a pricing update, not buried in changelog
3. Offer a retroactive discount to anyone who raised the issue publicly (converts critics into advocates)

---

## Monitoring Stack (Recommended Setup)

| What | Tool | Setup time | Cost |
|------|------|-----------|------|
| Competitor GitHub releases | RSS reader (e.g., Feedly) | 30 min | Free |
| "nightjar" mentions web | Google Alerts | 10 min | Free |
| HN mentions | hnalerts.io or Algolia HN search | 15 min | Free |
| CrossHair, Skylos, Semgrep releases | GitHub watch (releases only) | 5 min | Free |
| Trademark search | USPTO TESS (manual quarterly) | 30 min/quarter | Free |
| PyPI download stats | pypistats.org + pepy.tech | 10 min | Free |
| Twitter/X brand mentions | Twitter/X notifications | 10 min | Free |

Total setup time: ~2 hours. Monthly maintenance: ~1 hour.

---

## Response Time Standards

| Severity | First acknowledgment | Full response |
|----------|---------------------|---------------|
| CRITICAL (big-player entry, false positive going viral) | 4 hours | 24 hours |
| HIGH (competitor release, disputed CVE) | 12 hours | 48 hours |
| MEDIUM (community complaint, license question) | 24 hours | 5 days |
| LOW (minor trademark watch trigger, pricing feedback) | 1 week | 30 days |
