# Product Hunt Listing — Nightjar

**Submission URL:** https://www.producthunt.com/posts/new
**Platform:** Product Hunt
**Status:** Draft — submit at 12:01 AM PST on Day T+7 (one week after Show HN)
**Category:** Developer Tools

---

## 1. Tagline

Hard limit: 60 characters. This is the first line under the product name. Must be scannable in the feed.

---

> Write specs. AI codes. Dafny proves.

**Character count:** 36 / 60

**Why this tagline:** Three actors, three verbs, one rhythm. "Dafny" is a specific technology credential that signals technical depth to developers. The loop is self-evident: you → AI → proof engine. No buzzwords.

---

## 2. Description

Hard limit: 260 characters. Appears on the product card in the feed and in the header of the product page. Every word earns its place.

---

> Nightjar is the verification layer for AI-generated Python code. Write a spec, get provably-correct code. Found 74 bugs in 34 packages that passed existing tests. Spec-first. Contract-anchored. Built for teams that can't afford vibe-coded outages.

**Character count:** ~249 / 260

**Structure:**
- Sentence 1: What it is (one sentence, no jargon)
- Sentence 2: Core value proposition (write → get)
- Sentence 3: Social proof with a number (74 bugs, 34 packages — matches README)
- Sentences 4–6: Positioning keywords (spec-first, contract-anchored, vericoding adjacent)

**Note:** The GTM plan draft used "32 packages." The README (authoritative public doc) says "34 packages / 34 codebases." Use 34.

---

## 3. Maker Comment

Post this verbatim within 5 minutes of the listing going live. Do not edit it after posting — edits look nervous. Fill in the two bracketed placeholders before launch day.

---

```
Hey PH! Maker here.

Nightjar came out of a simple frustration: AI-generated Python passes all
the tests I write, but still ships bugs I didn't anticipate.

The fix isn't more tests — it's specs. Write what the function MUST do.
Let the AI generate code that satisfies it. Let Dafny prove it formally.
Never ship unproven code.

We launched on HN last week and the thread surfaced the hardest question:
"specs can be wrong too." Absolutely true. That's why the whole system is
in the open — your specs are auditable, not just your code.

If you've ever deployed AI-generated code and held your breath hoping it
worked — Nightjar is for you.

Would love feedback on: (1) the spec writing experience and (2) which
frameworks you'd most want supported next.
```

**Before posting, fill in:**
- The words "last week" refer to the Show HN thread — optionally add the HN link in parentheses: "We launched on HN last week ([link])..."
- No other changes.

---

## 4. Screenshots

Product Hunt requires exactly 5 screenshots. Upload in this order — they tell a story arc: proof → spec → evidence → mechanism → integration.

PH recommended dimensions: 1270 x 952 px (4:3). PNG preferred. Each should be captured at 2x/Retina resolution if possible, then downscaled.

---

### Screenshot 1 — Terminal VERIFIED Output

**Story this tells:** The tool works. Code is proven correct.

**Exact capture instructions:**

1. Open a terminal with a dark theme (black or near-black background). The Nightjar brand uses `#0d0b09` background — if your terminal supports custom colors, use it.
2. Run the following sequence in order:
   ```
   nightjar init payment
   nightjar generate --model claude-sonnet-4-6
   nightjar verify
   ```
3. Wait for all 6 stages to complete.
4. The final output should show each stage with a pass indicator and end with a `VERIFIED` status in bright amber/gold.
5. Capture the full terminal window — include the command you ran (`nightjar verify`) at the top and the complete output down to the final VERIFIED line.

**Key elements that must be visible in the frame:**
- The command `nightjar verify` at the top
- Each stage listed by name: Preflight, Deps, Schema, Negation Proof, Property Tests, Formal Proof
- Pass/check indicators next to each stage
- The final `VERIFIED` status in a clearly visible color (not truncated)
- Module name `payment` somewhere in the output

**If the verify run is slow:** use `nightjar verify --fast` for a quicker capture, then annotate the filename with "(fast mode)" — but the full 6-stage run is preferable for PH.

---

### Screenshot 2 — .card.md Spec File

**Story this tells:** Writing a spec is simple and readable. Developers understand it immediately.

**Exact capture instructions:**

1. Open VS Code (preferred for syntax highlighting) or any code editor with a dark theme.
2. Open the file: `.card/payment.card.md`
3. Scroll so the `invariants:` section is the vertical center of the screen.
4. The `contract:` section should be visible above it and at least 3 invariants visible below.
5. Make sure the invariant with `tier: formal` (INV-004: the accounting invariant) is visible — it's the highest-stakes proof and the most impressive.
6. Capture the full editor window including the file tab showing the filename and the line numbers in the gutter.

**Key elements that must be visible in the frame:**
- File name `.card/payment.card.md` in the editor tab
- The `invariants:` key in YAML
- At least one `tier: formal` invariant and one `tier: property` invariant
- The `statement:` field showing human-readable English (not Dafny syntax)
- Dark editor theme — the amber-on-dark aesthetic matches Nightjar's brand

**What to avoid:** Do not show the Intent or Acceptance Criteria sections — they read like boilerplate. The invariants section is the differentiating content.

---

### Screenshot 3 — Bug List

**Story this tells:** This isn't a toy. It found 74 real bugs in real packages that passed existing tests.

**Exact capture instructions:**

1. Open a browser in dark mode (GitHub supports dark mode under Settings → Appearance).
2. Navigate to: `https://github.com/j4ngzzz/Nightjar`
3. Scroll down to the "What we found" section.
4. Position the scroll so the following are visible in a single frame:
   - The "74 bugs across 34 codebases. Zero false positives." line
   - The **fastmcp** finding (OAuth redirect URI wildcard + JWT expiry bypass) — two bugs in one entry is compact and striking
   - The **litellm** finding (budget windows never reset) — shows a time-based semantic bug that tests miss
5. Capture the browser window. Include the GitHub URL bar so the source is clear.

**Why these two bugs:** fastmcp demonstrates a security vulnerability (auth bypass). litellm demonstrates a semantic correctness bug (logic works but is time-broken). Together they show two different failure modes that testing misses.

**Alternative if GitHub dark mode isn't available:** Run `nightjar audit fastmcp` in the terminal and capture the report card output. The A-F grading is visually compact and scannable.

---

### Screenshot 4 — Pipeline Diagram

**Story this tells:** This is a multi-stage verification system with a repair loop — technical depth is real.

**Exact capture instructions:**

1. Open a browser in dark mode.
2. Navigate to: `https://github.com/j4ngzzz/Nightjar`
3. Scroll to the "How it works" section.
4. GitHub renders the Mermaid diagram as an SVG. In dark mode it will render with the dark background and amber/gold stage boxes as specified in the diagram style block.
5. Capture the rendered diagram showing: Stage 0 through Stage 4 in sequence, the "Verified" outcome node, and the "CEGIS Retry" loop feeding back to Stage 2.
6. Include a few lines of the explanatory text below the diagram if it fits in the frame.

**Key elements that must be visible:**
- All 6 stage boxes (Preflight, Deps, Schema, Negation Proof, Property Tests, Formal Proof)
- The "Verified" terminal node
- The "CEGIS Retry" feedback arrow
- Dark background with amber/gold box styling

**If the Mermaid diagram does not render on GitHub (e.g., you are viewing a fork or the page is slow):** use `nightjar verify --tui` instead and capture the Textual TUI dashboard showing the live pipeline stages. This is an equally valid alternative.

---

### Screenshot 5 — Badge / CI Integration

**Story this tells:** This integrates into real developer workflows. Add it to your project and prove it publicly.

**Exact capture instructions:**

1. Open a browser (light or dark mode both work for this one).
2. Navigate to: `https://github.com/j4ngzzz/Nightjar/actions`
3. Click on the most recent successful "CI Verify" workflow run.
4. Capture the workflow run detail view showing:
   - The green checkmark (success) on the overall run
   - The individual job steps with green checks, including the `nightjar verify` step
   - The workflow name "CI Verify" visible in the breadcrumb or title

**Why the CI run over the README badges:** The CI actions view shows the tool running in a real pipeline, not just a static badge. For developers, seeing `nightjar verify` as a passing CI step is the most direct signal that this works in their environment too.

**Alternative (README badge row):** If the CI run view is cluttered, navigate to `https://github.com/j4ngzzz/Nightjar` and capture the README header showing the full badge row (PyPI version, tests-1841_passed, license, verified_with-Dafny_4.x, CI Verify green). Crop tightly around the banner and badge row.

**Second alternative (nightjar badge command):** Run `nightjar badge` in the terminal. It outputs the Markdown embed code and a preview URL for the shields.io badge a user would add to their own project's README. Screenshot this output alongside the rendered badge in a browser — shows the "add this to YOUR project" use case directly.

---

## 5. Category

**Select:** Developer Tools

This is the correct primary category. Do not use "Productivity" or "Artificial Intelligence" as primary — Nightjar's core audience actively browses Developer Tools.

---

## 6. Tags

Select up to 5 tags. Choose all 5:

| Tag | Rationale |
|-----|-----------|
| **Developer Tools** | Primary audience signal — people browsing this tag are your users |
| **Python** | Language-specific discovery — Python developers searching PH |
| **Open Source** | Trust signal — AGPL-3.0, everything is auditable |
| **Artificial Intelligence** | Trend visibility — surfaces in the AI tools feed |
| **Security** | Secondary audience — security engineers concerned about AI code vulnerabilities |

**Tag entry format on PH:** These are typed into a freeform tag field. PH auto-suggests from existing tags. Type the exact strings above and select the suggestion if it appears.

---

## 7. Additional Assets

### GIF / Video

Use the same demo GIF created for the website (see GTM plan Task 2, Step 2):
- Recorded with `asciinema` + `agg`
- Shows the full loop: `nightjar init` → `nightjar generate` → `nightjar verify` → VERIFIED
- Max 30 seconds, max 5MB
- Monokai or dark theme, ends on the green/amber VERIFIED status

PH supports either a GIF (uploaded) or a YouTube/Vimeo link. GIF is preferred for instant autoplay in the feed — no click required.

### Thumbnail

PH auto-generates a thumbnail from your first screenshot. To control the thumbnail:
- Make Screenshot 1 (the VERIFIED terminal) the most visually striking
- Ensure the VERIFIED text is large and centered in the terminal
- The amber/gold color on black background is high-contrast and stands out in a dark feed

### Website URL

`https://nightjarcode.dev` (or your live landing page URL)

Do NOT link directly to GitHub — the landing page has the demo GIF and install command above the fold. GitHub is a click away from there.

---

## Submission Checklist

Before clicking submit at 12:01 AM PST Day T+7:

- [ ] Tagline entered exactly as above (no trailing space)
- [ ] Description entered, character count confirmed under 260
- [ ] Maker comment saved in clipboard, ready to paste within 5 minutes of launch
- [ ] All 5 screenshots uploaded in order (1 through 5)
- [ ] Demo GIF uploaded (or YouTube link added)
- [ ] Category set to "Developer Tools"
- [ ] All 5 tags selected
- [ ] Website URL points to landing page (not GitHub)
- [ ] HN thread link filled in maker comment (bracket placeholder)
- [ ] You are logged in as the maker account (not a test/throwaway account)
- [ ] You are online and available to respond to comments for the first 8 hours

---

## Notes

- PH resets at midnight PST — submitting at 12:01 AM gives a full day of visibility
- Respond to every comment within 1 hour on launch day
- Do not ask friends to upvote — PH detects coordinated voting and it backfires
- On launch morning, post one tweet: "We're on Product Hunt today! [link]. Built on the back of the HN community's feedback last week. Come say hi."
- The Show HN thread (T-0) will have generated genuine community reactions by T+7 — reference it in comments when relevant, it is credibility
