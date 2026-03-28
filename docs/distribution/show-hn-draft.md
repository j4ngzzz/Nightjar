# Show HN Draft

**Title:** Show HN: Nightjar – formal verification pipeline that found 48 bugs in 20 Python packages

---

## Post Body

We built a verification pipeline for Python code and ran it against 20 popular open-source packages: Tier 1 infrastructure (requests, httpx, fastapi), JWT/OAuth libraries (python-jose, passlib, PyJWT, fastmcp), AI agent frameworks (DeerFlow, Open-SWE, Hermes), Karpathy's minbpe tokenizer, and a recently viral AI-generated app called MiroFish.

Total confirmed bugs: 48. Zero false positives in the verified set — every finding in the report has a reproduction script.

The most interesting ones:

- fastmcp 2.14.5: `if exp` truthiness check on JWT expiry — `exp=None` or `exp=0` both pass, token never expires. Also: `fnmatch` for OAuth redirect URI validation lets `evil.com/cb?legit.example.com/x` pass `*.example.com/*`.
- python-jose 3.5.0: `jwt.decode(token, key, algorithms=None)` skips the algorithm allowlist entirely. The default API call uses `algorithms=None`.
- passlib 1.7.4: completely broken against bcrypt 4.x and 5.x. `bcrypt.hashpw()` now enforces the 72-byte limit; passlib's startup probe passes a 255-byte password and crashes before any hash call.
- Open-SWE: `"success" in pr_payload` is always True — including when `success: False`. The agent silently abandons failed PR creation.
- minbpe: `BasicTokenizer().train('a', 258)` raises ValueError in four seconds. `max()` on an empty stats dict.

The well-maintained projects — datasette, rich, hypothesis — were clean.

The tool is Nightjar. You write a contract spec in a `.card.md` file. The pipeline runs 5 stages: syntax/preflight, dependency CVE scan, schema validation, property-based testing (Hypothesis), and formal verification (CrossHair + Dafny). CEGIS retry loop on verification failures. The scan above used the PBT stage only — Dafny is optional and requires .NET.

Repo: https://github.com/j4ngzzz/Nightjar
PyPI: `pip install nightjarzzz`
Full scan results with repro scripts: https://nightjarcode.dev/scan/2026-q1/

Happy to answer questions about methodology, specific bugs, or how the pipeline works.

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
1. "This is just Hypothesis" — answer: "Hypothesis is Stage 3 of 5. The pipeline adds dependency CVE scanning (Stage 1), schema invariant checking (Stage 2), and formal Dafny proofs (Stage 4). The fastmcp JWT finding came from a spec-driven check against documented behavior, not a Hypothesis strategy."
2. "passlib being broken is known" — answer: "Known as a compatibility warning on PyPI, yes. Not known as an uncaught crash in production deployments. The bug fires in passlib's startup probe before any user authentication call executes."
3. "Why use Dafny for Python?" — answer: "Dafny proves a formal model of the function, not native Python bytecode. CrossHair runs on native Python. We use both because they find different classes of errors — CrossHair is stronger on runtime semantics, Dafny on algorithmic invariants. The documentation is explicit about this distinction."

**If the post gets traction (top 10 front page):**
- Have the scan archive page live and fast-loading before posting
- Have individual bug report pages for the top 5 findings (fastmcp JWT, python-jose, passlib, Open-SWE, minbpe) ready to link to in comments
