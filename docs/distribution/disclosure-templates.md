# Responsible Disclosure Templates

Templates for reporting findings from the Nightjar scan campaign. Use the appropriate template based on the target, severity, and relationship. All templates follow the ISO 29147 coordinated disclosure standard.

---

## Template 1: HIGH Security Bug in Popular Package (GitHub Security Advisory format)

**When to use:** Security-relevant findings (auth bypass, JWT manipulation, OAuth redirect, path traversal) in packages with >1M monthly downloads. File via the GitHub Security tab ("Report a vulnerability"), not as a public issue.

---

**Subject:** Nightjar formal verification: [BUG-ID] — [one-line description] in [package] [version]

**Body:**

```
Hi [maintainer name],

We've been running a public scan of Python packages using Nightjar's property-based testing pipeline. We found an invariant violation in [package] [version] that we believe has security implications.

**Summary**

[One sentence: what invariant is violated and what the attacker impact is.]

**Affected component**

File: [filename]
Function: [function name]
Lines: [line numbers if known]

**Counterexample**

The following input reproduces the issue:

```python
[minimal reproduction script — copy from scan results]
```

Output / observed behavior:
[exact output or exception trace]

**Root cause**

[One paragraph: what the code does wrong. Reference the specific line.]

**Impact**

[Two to three sentences: what an attacker can do with this. Be specific.]

**Suggested fix**

[Code snippet showing the fix, or a description if a code fix requires design decisions.]

**Disclosure timeline**

We intend to publish our scan results publicly. We will not mention this specific finding or your package by name until you have had time to review and respond.

Proposed timeline:
- Day 0: this report
- Day 3: please confirm receipt
- Day 90: public disclosure (or earlier if fix is released)

We are flexible on the timeline. If 90 days is insufficient for your release cycle, let us know.

**What to attach:** The PBT failure output (Hypothesis counterexample trace), any relevant `.card.md` invariant spec.

**What to do if no response in 30 days:** Send a follow-up to the same GitHub Security Advisory thread. If no response after 45 days, attempt contact via the maintainer's email in pyproject.toml or package metadata. If no response after 60 days, notify CERT/CC with the CVE candidate details and your disclosure timeline. At 90 days, publish regardless of response status, noting that the maintainer did not respond.
```

---

## Template 2: Security Bug in Vibe-Coded / Smaller Project (Friendly DM)

**When to use:** Security findings in projects that appear AI-generated, hobbyist, or maintained by a small team. These maintainers may not have a security reporting process. Use GitHub DM or Twitter/X DM rather than filing a Security Advisory (which can feel aggressive if the project has no process).

---

**Subject:** [Project name] — we found a security issue in our scan, happy to share details

**Body (GitHub DM or Twitter DM):**

```
Hey [name],

We've been running a formal verification scan of open-source Python projects using a tool called Nightjar. We scanned [project name] as part of a broader scan of [N] projects and found [X] issues, including [Y] that are security-relevant.

The most serious finding: [one sentence description of the HIGH finding — e.g., "a path traversal vulnerability in the platform query parameter that lets callers read arbitrary files."]

We haven't published anything yet. Before we include this in our public scan report, we wanted to give you time to review and fix it first. We're happy to share the full details and help with a fix if that's useful.

A few options:
1. We share the full findings privately, you fix it, we mention the fix was in place before we published.
2. We share the full findings, you'd prefer we keep your project anonymous in the report.
3. You're not interested — we'll mention the class of bug without naming the project.

Let me know what works. No rush on a decision but we're targeting publication in [X weeks].

[Your name]
```

**What to attach:** After they respond and choose option 1 or 2, send the full scan results file (markdown or PDF). Include the reproduction script.

**What to do if no response in 30 days:** Send one follow-up. If no response after 45 days, publish the finding. For HIGH/CRITICAL issues in deployed production software, publish after 45 days with the finding intact. For MEDIUM or lower with no evidence of active production deployment, you may choose to describe the pattern without naming the specific project.

---

## Template 3: Logic Bug, Non-Security (Brief GitHub Issue)

**When to use:** Confirmed bugs that are correctness failures without security implications — wrong output, crashes on edge-case input, invariant violations that don't enable privilege escalation. File as a public GitHub issue, not a Security Advisory.

---

**Issue title:** `[function_name]([input])` raises `[ExceptionType]` — invariant violation found via property-based testing

**Body:**

```markdown
## Summary

`[function_name]` raises `[ExceptionType]` on input `[specific_input]`. The function's documented contract requires it to [return X / never raise / always produce Y].

## Environment

- Package version: [version]
- Python version: [version]
- Hypothesis version: [version] (used to find this)

## Reproduction

```python
[minimal reproduction script]
```

Output:
```
[exact error or wrong output]
```

## Root cause

[One paragraph explaining why the code fails. Reference the specific line.]

## Suggested fix

[Code snippet or description.]

## How this was found

This was found by [Nightjar's / Hypothesis's] property-based testing engine, which generated random inputs and checked the invariant that `[specific invariant]`. The counterexample was minimized automatically.
```

**What to attach:** Nothing — the reproduction script in the issue body is sufficient.

**What to do if no response in 30 days:** Add a follow-up comment on the issue. If the project appears unmaintained (no commits in >12 months), add a note in your scan results that the bug was reported and not acknowledged, and recommend users consider the maintenance status when choosing the package.

---

## Template 4: Famous Developer's Project (Respectful Personal Outreach)

**When to use:** Findings in projects where the primary maintainer has a significant public following (10K+ GitHub followers or similar). Examples from this scan: Simon Willison (llm, datasette, sqlite-utils), Andrej Karpathy (minbpe). The goal is to get their genuine engagement, not a hostile response.

---

**Subject:** [Project] — interesting edge case found with formal verification, thought you'd find it technically interesting

**DM or email body:**

```
Hi [name],

I've been running a public verification scan of open-source Python projects using a tool called Nightjar that uses Hypothesis property-based testing to check invariants. I scanned [project] as part of a scan of [N] projects.

I found an interesting edge case: [one sentence technical description of the finding, specific and precise — e.g., "BasicTokenizer().train('a', 258) raises ValueError because max() is called on an empty stats dict when vocab_size - 256 exceeds the number of mergeable pairs in the text."]

Reproduction:
```python
[two to four line reproduction script]
```

This is [security-relevant / not security-relevant]. [If security-relevant: "I haven't published anything about it yet." If not: "Happy to file it as a public issue if you'd find that useful."]

A few options:
1. I mention it in my scan results (already being publicly framed positively — e.g., "found in minbpe, fixed before publication")
2. You'd prefer I keep it private or anonymous
3. You're happy to discuss it publicly — I'd love to link to any technical response you write

If the finding is wrong or you want to explain why the behavior is intentional, I'm happy to hear that too — I'd rather be corrected than publish something inaccurate.

[Your name]
```

**Tone notes:** Be specific. Famous developers get vague outreach constantly. A precise bug report with a two-line repro is immediately credible. Do not lead with the tool name. Do not ask for a public endorsement in the first message. Do not mention followers, reach, or marketing.

**What to attach:** Nothing in the first message. If they respond positively, follow up with the full scan file.

**What to do if no response in 30 days:** One follow-up, politely. If still no response, you may publish the finding — but describe the project and its scale (e.g., "a widely-forked ML repository") rather than the maintainer's name. You are under no obligation to suppress a confirmed bug indefinitely to protect someone's reputation, but naming them without their awareness creates unnecessary antagonism.

---

## Template 5: Clean Package — Offering Nightjar Verified Badge

**When to use:** Any package from the scan that passed all invariant checks with no confirmed bugs. Use after scan results are published. Send to the maintainer as a GitHub issue (not DM — this is public-friendly news).

---

**Issue title:** Nightjar Verified — [package] passed formal verification scan, badge available

**Body:**

```markdown
Hi,

We recently completed a [public formal verification scan of N Python packages](https://nightjar.dev/scan/2026-q1/) using [Nightjar](https://github.com/your-org/nightjar)'s property-based testing + formal verification pipeline.

[Package] passed. We checked [N] functions across [areas tested — e.g., "SQL injection surfaces, input validation, encoding edge cases"]. No confirmed invariant violations.

**The offer:** If you'd like to add a "Nightjar Verified" badge to your README, we'll issue a public report tied to this version. The badge links to the scan report.

```markdown
[![Nightjar Verified](https://img.shields.io/endpoint?url=https://api.nightjar.dev/badge/[owner]/[repo])](https://nightjar.dev/scan/[owner]/[repo])
```

**No obligation.** This is a genuine offer because your package passed, not a marketing ask. If you'd prefer not to add the badge, no problem at all — the scan results are published publicly either way.

If you're curious about what we tested and how, the full invariant specs are at [link to scan archive].

Thanks for maintaining [package].

[Your name]
```

**What to attach:** Nothing — link to the public scan report instead.

**What to do if no response in 30 days:** Nothing. This is an offer, not a disclosure. Close the issue if it sits open without a response for 60 days. The public scan results stand regardless.

---

## General Guidance

**Severity thresholds for timeline:**

| Severity | Disclosure window | First contact method |
|----------|------------------|----------------------|
| CRITICAL (CVSS 9+) | 90 days, negotiate if needed | GitHub Security Advisory + email |
| HIGH (CVSS 7–8.9) | 90 days standard | GitHub Security Advisory |
| MEDIUM (CVSS 4–6.9) | 45–60 days | GitHub Security Advisory or public issue |
| LOW (CVSS < 4) | Public issue, no embargo needed | GitHub public issue |
| Logic bug (no CVSS) | No embargo | GitHub public issue |

**Non-negotiables:**

1. Never publish security findings before the maintainer has had reasonable time to respond (at minimum 30 days from confirmed receipt).
2. Attach actual reproduction evidence — not "we believe this is a vulnerability," but "here is the exact input that demonstrates it."
3. Do not include marketing material in the initial disclosure. The finding stands on its own.
4. If a maintainer asks you to extend the timeline for a compelling reason (pending release, complex fix), be reasonable. The goal is a fix in the world, not a publication date.
5. If a maintainer disputes the finding, engage technically. They may be right. Check before publishing.

**For the fastmcp / python-jose findings specifically:** These were the highest-severity findings in the scan. File immediately via GitHub Security Advisory. Do not wait. Use Template 1. The JWT falsy check (fastmcp) and `algorithms=None` bypass (python-jose) are exploitable by anyone who reads the scan results.
