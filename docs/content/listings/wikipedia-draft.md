# Wikipedia Draft — "List of tools for static code analysis"

**Target page:** https://en.wikipedia.org/wiki/List_of_tools_for_static_code_analysis
**Status:** HOLD — notability requirements not yet met. See section below.

---

## Current Notability Assessment

**Do not submit this entry yet.** Wikipedia requires reliable, independent secondary sources for all list entries. As of March 2026, Nightjar does not yet have coverage in sources Wikipedia editors accept. Submitting without citations will result in the entry being removed within days.

See the "Required Sources" section at the bottom of this document for what must be gathered before submission.

---

## Proposed Table Entry

The "List of tools for static code analysis" page uses a table with these columns:
`Name | Language(s) | License | Notes`

Some entries link to a standalone Wikipedia article; others link directly to the tool's website or GitHub. Nightjar does not yet have a standalone Wikipedia article.

### Table row to add

Under the **Python** section of the table:

```
| [[nightjar-verify|Nightjar]] || Python || [[GNU Affero General Public License|AGPL-3.0]] / Commercial || Verification pipeline coordinating property-based testing ([[Hypothesis (Python library)|Hypothesis]]), symbolic execution ([[CrossHair]]), and formal proof ([[Dafny]]). Extracts invariant contracts from existing code via AST analysis. Found 74 confirmed defects across 34 open-source Python packages in a documented public scan.<ref>{{cite web|url=https://nightjarcode.dev/scan/2026-q1/|title=Nightjar public scan results — Q1 2026|publisher=Nightjar|access-date=2026-03-29}}</ref> ||
```

**Note on the self-citation:** The nightjarcode.dev URL is the project's own site, which is not a reliable independent source. This ref will be challenged. It is included as a placeholder only. Replace with an independent press citation before submission.

---

## Standalone Article Draft

*Use this if/when Nightjar has sufficient independent coverage for a standalone article. Wikipedia requires "significant coverage in multiple reliable sources that are independent of the subject."*

---

### Article title: `Nightjar (software)`

---

**Nightjar** is an open-source verification pipeline for [[Python (programming language)|Python]] code. It coordinates [[property-based testing]] ([[Hypothesis (Python library)|Hypothesis]]), [[symbolic execution]] (CrossHair), and [[formal verification]] ([[Dafny]]) into a six-stage automated pipeline that checks whether code satisfies behavioral specifications.{{cn}}

#### Overview

Nightjar operates on a spec-first model: developers write `.card.md` files describing behavioral invariants, and Nightjar generates code and proves it satisfies those invariants for all possible inputs.{{cn}} For existing codebases, a scanner command extracts invariant contracts from Python source using [[abstract syntax tree|AST]] analysis without requiring manual spec writing.{{cn}}

The verification pipeline runs six stages: syntax preflight, [[CVE]] dependency scanning via pip-audit, schema validation via [[Pydantic]], negation proofs, property-based testing, and formal symbolic proof. When formal verification fails, a [[counterexample-guided inductive synthesis|CEGIS]] retry loop extracts the counterexample and feeds it to an LLM repair cycle.{{cn}}

#### Bug findings

In a public scan conducted in early 2026, Nightjar scanned 34 open-source Python packages and reported 74 confirmed defects.{{cn}} Findings included an [[Ethereum Name Service|ENS]] address resolution flaw in web3.py related to [[Unicode]] fullwidth normalization,{{cn}} JWT token expiry bypasses in fastmcp,{{cn}} and session state isolation failures in Google's Agent Development Kit.{{cn}} Fourteen packages were reported as defect-free.{{cn}}

#### License and availability

Nightjar is released under the [[GNU Affero General Public License]] version 3 (AGPL-3.0). A commercial license is available for organizations that cannot use AGPL.{{cn}} The package is distributed via [[PyPI]] under the name `nightjar-verify`.{{cn}}

#### See also

* [[Dafny]]
* [[Hypothesis (Python library)]]
* [[CrossHair]]
* [[Formal verification]]
* [[Property-based testing]]
* [[Static program analysis]]

#### References

{{reflist}}

---

## Required Sources Before Submission

Wikipedia editors will remove any entry or article lacking reliable independent citations. The following sources are needed and are not currently available. This is not an obstacle to work around — it is a signal that the tool needs real-world coverage before being submitted.

### Tier 1 — Required (at least one before any submission)

| Source type | Example | How to obtain |
|-------------|---------|---------------|
| **CVE advisory** | A CVE number assigned to any of the bugs Nightjar found (e.g., fastmcp JWT bypass, python-jose algorithm bypass) where Nightjar is credited as the finder | File with MITRE via https://cveform.mitre.org/ or through the package maintainer. The advisory itself becomes a citable source. |
| **Independent press coverage** | Article in Ars Technica, The Register, Wired, InfoQ, SDTimes, or a recognized tech news outlet covering the scan findings or the tool | Pitch the scan findings to security journalists. The web3.py ENS finding is bounty-eligible and press-worthy if the Ethereum Foundation acknowledges it. |
| **Academic citation** | A paper that cites Nightjar, or a paper that Nightjar's findings corroborate with independent coverage | Submit findings to an academic venue or wait for POPL/USENIX Security to accept related work that references the scan. |

### Tier 2 — Strengthen the article

| Source type | Example | How to obtain |
|-------------|---------|---------------|
| **Maintainer security advisory** | The fastmcp maintainer publishes a GitHub security advisory for the JWT bypass and credits Nightjar as the reporter | Already filed — follow up with maintainers to publish advisories |
| **HackerOne disclosure** | Public HackerOne report for the openai-agents handoff trust escalation | Already filed per the README — request public disclosure when resolved |
| **Industry analyst mention** | Reference in a Gartner, Forrester, or similar analyst report on Python security tools | Submit to analyst briefing programs after HN launch |
| **Conference talk or paper** | Accepted talk at PyCon, DEF CON, or similar | Submit the scan methodology and findings as a talk proposal |

### What is NOT a reliable Wikipedia source

The following will be rejected by Wikipedia editors and should not be used as the primary citation:

- The Nightjar GitHub repository README
- nightjarcode.dev (the project's own website)
- PyPI listing
- The project's own blog posts or documentation
- Hacker News Show HN post (community posts are not press)
- Personal blog posts about the tool
- The CLAUDE.md file or any internal documentation

### Submission Checklist

Before opening a Wikipedia edit:

- [ ] At least one CVE advisory credits Nightjar as the finder
- [ ] OR at least one article in a recognized tech publication covers Nightjar independently
- [ ] The tool has been live for at least 3 months (avoids speedy-deletion as non-notable new software)
- [ ] The PyPI package has meaningful download numbers (provides evidence of use)
- [ ] Citations are formatted as `<ref>` tags following Wikipedia's inline citation style
- [ ] The table row has been reviewed against the current page format (the page may have been reformatted since this draft was written)
- [ ] A Wikipedia account with some edit history is used for the submission (reduces new-editor scrutiny)

### Recommended submission timing

Given the March 2026 launch, the earliest realistic submission window is **late June 2026**, assuming:
1. The HN Show HN post generates press pickup within the first few weeks
2. At least one CVE is assigned to the fastmcp or python-jose findings
3. The package reaches meaningful PyPI adoption

If press coverage comes earlier (e.g., within 2 weeks of launch), move the submission date up accordingly. The CVE path is the most reliable because CVE advisories are themselves considered reliable secondary sources by Wikipedia's citation standards.
