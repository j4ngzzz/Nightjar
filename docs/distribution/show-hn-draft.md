# Show HN Draft

**Title:** Show HN: I'm 19, can't code, so I vibecoded a formal verifier that found 74 bugs in popular packages

---

## Post Body

I'm 19, year one polytechnic CS student in Singapore. I vibecoded this entire project — 30,000+ lines, 1,514 passing tests, Dafny formal proofs — in 62 hours using Claude Code. I never wrote a Python function manually.

The problem I kept hitting: AI writes code that looks right but isn't. Not "wrong type" wrong — logically wrong. The kind of wrong that passes unit tests and ships to production. I was spending half my time debugging my own vibecoded stuff. Testing wasn't enough because you can only test the cases you think of.

So I built a 6-stage verification pipeline. You write a `.card.md` spec describing what your code should do. Nightjar generates an implementation, then runs it through schema validation, property-based tests (Hypothesis), and finally Dafny — a theorem prover that gives you a mathematical certificate that the code satisfies the spec for all possible inputs.

To validate it, I scanned 34 popular Python packages. 74 confirmed bugs. 14 verified clean. A few highlights:

- `web3.py`: ENS fullwidth Unicode normalization → ETH address hijacking. Send funds to `ａdmin.eth` (fullwidth 'a') and it resolves to a different address than `admin.eth`. CRITICAL, bounty-eligible
- `RestrictedPython`: confirmed RCE via misconfigured sandbox. `exec` escapes the restricted namespace through a specific attribute traversal chain. HIGH
- `openai-agents`: handoff trust escalation — any agent can invoke any other agent's tools without boundary checks. Filed on HackerOne. HIGH
- `ragas`: 9 evaluation metrics return NaN silently when inputs are edge cases. Your RAG system scores itself as perfect on the inputs that should fail it. HIGH
- `pydantic v2`: `model_copy(update={...})` bypasses ALL validators. 270M monthly downloads. The escape hatch is documented but not guarded. HIGH
- `google-adk`: session state is a shared mutable dict — one user's request can overwrite another user's session data. HIGH
- `langgraph`: silent routing failure — the graph executes successfully, returns a result, and does absolutely nothing. MEDIUM-HIGH
- `MiroFish` (billionaire-funded vibe-coded app): hardcoded `SECRET_KEY = 'mirofish-secret-key'` in the config, `DEBUG=True` in production, path traversal on the profile endpoint. HIGH

Clean packages: datasette, rich, hypothesis, sqlite-utils, httpx, requests, and 8 others. The well-maintained hand-tested projects held up. The AI tooling ecosystem and AI-generated apps did not.

96% of developers don't fully trust AI-generated code (Sonar 2026, 1,100+ devs). Only 48% verify it. Nightjar closes that gap automatically.

The NCSC said AI-generated code poses "intolerable risks" on March 24. Nightjar shipped March 29. Make of that what you will.

62 hours. 175 commits. 34 packages scanned. 74 bugs confirmed. 14 clean. One person. First year of college.

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
1. "This is just Hypothesis" — answer: "Hypothesis is Stage 3 of 6. The pipeline adds dependency CVE scanning (Stage 1), schema invariant checking (Stage 2), and formal Dafny proofs (Stage 4). The web3.py ENS finding came from a spec-driven check against documented Unicode normalization behavior, not a Hypothesis strategy."
2. "passlib being broken is known" — answer: "Known as a compatibility warning on PyPI, yes. Not known as an uncaught crash in production deployments. The bug fires in passlib's startup probe before any user authentication call executes."
3. "Why use Dafny for Python?" — answer: "Dafny proves a formal model of the function, not native Python bytecode. CrossHair runs on native Python. We use both because they find different classes of errors — CrossHair is stronger on runtime semantics, Dafny on algorithmic invariants. The documentation is explicit about this distinction."
4. "You can't code so how do you know the bugs are real?" — answer: "Every finding has a reproduction script in the repo. Run it yourself. Nightjar doesn't find bugs by intuition — it finds them by checking the code against a formal spec of what it's supposed to do. Whether I wrote the pipeline manually or directed agents to build it doesn't change whether ENS resolves a fullwidth Unicode address to a different wallet."
5. "This is just a vibe coding stunt" — answer: "The NCSC put it plainly on March 24: AI-generated code poses 'intolerable risks.' The question isn't whether to verify AI code. It's whether you have a tool that does it mathematically. 74 bugs in 34 packages is the answer to whether the tool works."
6. "The pydantic model_copy thing is by design" — answer: "It's documented, yes. What's not guarded is using it as an escape hatch for untrusted data. At 270M monthly downloads, the number of applications accidentally bypassing validators this way is not small."
7. "openai-agents handoff trust — is that really a bug?" — answer: "Filed on HackerOne. The design allows any agent in a multi-agent system to invoke any other agent's tools without boundary checks. In a system where agents have different permission levels, that's an escalation path."

**If the post gets traction (top 10 front page):**
- Have the scan archive page live and fast-loading before posting
- Have individual bug report pages for the top 5 findings (web3.py ENS, RestrictedPython RCE, openai-agents handoff, ragas NaN, pydantic model_copy) ready to link to in comments
- The commit history on GitHub is timestamped — if anyone disputes the 62-hour claim, link directly to it
