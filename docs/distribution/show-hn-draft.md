# Show HN Draft

**Title:** Show HN: I'm 19, can't code, so I vibecoded a formal verifier that found 48 bugs in popular packages

---

## Post Body

I'm 19, year one polytechnic CS student in Singapore. I vibecoded this entire project — 25,000+ lines, 1,363 passing tests, Dafny formal proofs — in 62 hours using Claude Code. I never wrote a Python function manually.

The problem I kept hitting: AI writes code that looks right but isn't. Not "wrong type" wrong — logically wrong. The kind of wrong that passes unit tests and ships to production. I was spending half my time debugging my own vibecoded stuff. Testing wasn't enough because you can only test the cases you think of.

So I built a 6-stage verification pipeline. You write a `.card.md` spec describing what your code should do. Nightjar generates an implementation, then runs it through schema validation, property-based tests (Hypothesis), and finally Dafny — a theorem prover that gives you a mathematical certificate that the code satisfies the spec for all possible inputs.

To validate it, I scanned 20 popular Python packages. 48 confirmed bugs. A few highlights:

- `fastmcp 2.14.5`: JWT tokens with `exp=0` accepted as valid (a token from 1970 authenticates). Also: `fnmatch` redirect URI validation lets `evil.com/cb?legit.example.com/x` pass `*.example.com/*`
- `litellm 1.82.6`: default arg evaluated at import time — budget limits stop working on long-running servers
- `python-jose 3.5.0`: `algorithms=None` accepts any signing algorithm. The default API call uses `algorithms=None`
- `passlib 1.7.4`: completely broken against bcrypt 4.x and 5.x — startup probe crashes before any hash call executes
- `minbpe`: Karpathy's BPE tokenizer crashes with short text — `max()` on an empty stats dict

Every finding runs in one script. Clean results are listed too — `datasette`, `rich`, `hypothesis` itself passed clean.

96% of developers don't fully trust AI-generated code (Sonar 2026, 1,100+ devs). Only 48% verify it. Nightjar closes that gap automatically.

The NCSC said AI-generated code poses "intolerable risks" on March 24. Nightjar shipped March 29. Make of that what you will.

62 hours. 175 commits. 20 packages scanned. 48 bugs confirmed. One person. First year of college.

AGPL-3.0. Python 3.11+. Dafny optional — falls back to CrossHair without it.

Repo: https://github.com/j4ngzzz/Nightjar
PyPI: `pip install nightjar-verify`
Full scan results with repro scripts: https://nightjarcode.dev/scan/2026-q1/

---

## Submission Notes

**Timing:** Post between 9am–11am ET on a weekday. Tuesday–Thursday tend to have better HN front-page staying power for technical posts. Avoid Mondays and Fridays.

**What to do after posting:**
- Check every comment within the first 2 hours — this is the window where responses most affect ranking
- Engage with technical challenges seriously, not defensively. If someone says "this is just Hypothesis," answer precisely: what Stages 0–2 and Stage 4 add that Hypothesis doesn't do
- If someone disputes a specific finding, engage technically and offer to share the reproduction script directly
- Do not link to any product/pricing page in the comments unless directly asked

**What not to do:**
- Do not ask friends to upvote — HN's fraud detection is good and vote rings result in permanent shadowbanning
- Do not post from a brand-new account; use an account with some comment history
- Do not edit the title after submission (it resets the clock on HN's ranking algorithm)

**Likely objections to prepare for:**
1. "This is just Hypothesis" — answer: "Hypothesis is Stage 3 of 6. The pipeline adds dependency CVE scanning (Stage 1), schema invariant checking (Stage 2), and formal Dafny proofs (Stage 4). The fastmcp JWT finding came from a spec-driven check against documented behavior, not a Hypothesis strategy."
2. "passlib being broken is known" — answer: "Known as a compatibility warning on PyPI, yes. Not known as an uncaught crash in production deployments. The bug fires in passlib's startup probe before any user authentication call executes."
3. "Why use Dafny for Python?" — answer: "Dafny proves a formal model of the function, not native Python bytecode. CrossHair runs on native Python. We use both because they find different classes of errors — CrossHair is stronger on runtime semantics, Dafny on algorithmic invariants. The documentation is explicit about this distinction."
4. "You can't code so how do you know the bugs are real?" — answer: "Every finding has a reproduction script in the repo. Run it yourself. Nightjar doesn't find bugs by intuition — it finds them by checking the code against a formal spec of what it's supposed to do. Whether I wrote the pipeline manually or directed agents to build it doesn't change whether `exp=0` authenticates."
5. "This is just a vibe coding stunt" — answer: "The NCSC put it plainly on March 24: AI-generated code poses 'intolerable risks.' The question isn't whether to verify AI code. It's whether you have a tool that does it mathematically. 48 bugs in 20 packages in one weekend is the answer to whether the tool works."

**If the post gets traction (top 10 front page):**
- Have the scan archive page live and fast-loading before posting
- Have individual bug report pages for the top 5 findings (fastmcp JWT, litellm budget, python-jose, passlib, minbpe) ready to link to in comments
- The commit history on GitHub is timestamped — if anyone disputes the 62-hour claim, link directly to it
