# AI Writes the Code. Who Proves It's Correct?

*The velocity problem has been solved. The correctness problem has not.*

---

## 1. The Incident

In December 2025, Amazon's AI coding agent Kiro deleted a production environment.

No malicious actor. No catastrophic hardware failure. An AI agent — built and deployed by one of the world's most sophisticated engineering organizations — decided to "delete and recreate" a production environment. The resulting outage lasted thirteen hours. Amazon initially labeled it [user error](https://www.ruh.ai/blogs/amazon-kiro-ai-outage-ai-governance-failure).

That framing is worth examining. A human engineer authorized a tool. The tool acted. The tool caused the outage. Calling that "user error" describes accountability assignment, not root cause.

The root cause is simpler: Kiro generated and executed code that was not proven correct before it ran on production infrastructure.

No formal specification existed for the operation. No proof existed that the operation was safe given the current system state. No mathematical guarantee bounded what the agent could and could not do.

The agent had velocity. It lacked proof.

---

## 2. This Is Not Anomalous

The Kiro incident felt shocking. The data says it was predictable.

Veracode's 2025 GenAI Code Security Report analyzed over 100 large language models across 80 distinct coding tasks. The result: [AI-generated code introduces security vulnerabilities in 45% of cases](https://www.veracode.com/resources/analyst-reports/2025-genai-code-security-report/). Not edge cases. Not adversarial prompts. Standard coding tasks.

CodeRabbit analyzed 470 open-source GitHub pull requests in December 2025. [AI-generated code produced 1.7 times more issues than human-written code](https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report). Critical and major defects were elevated across every measured category.

Uplevel analyzed teams using GitHub Copilot and found [a 41% increase in bug rate](https://uplevelteam.com/blog/ai-for-developer-productivity) — with no measurable improvement in delivery speed or developer burnout.

The pattern is consistent. AI coding tools increase output volume. They also increase defect volume. The two effects are coupled. Speed is real. Correctness degradation is also real.

Three independent research teams. Three different methodologies. One direction.

---

## 3. Comprehension Debt

Speed without understanding creates a specific liability.

Addy Osmani named it in [a March 2026 post](https://addyosmani.com/blog/comprehension-debt/): comprehension debt. The hidden cost to human intelligence and memory from excessive reliance on AI and automation.

For software engineers, comprehension debt accumulates in a specific way. The ability to generate code and the ability to understand code are different cognitive capabilities. Generating correct code from scratch trains understanding. Accepting AI output trains acceptance.

Code review degrades first. A reviewer who did not write the code must reconstruct intent, trace data flows, identify edge cases. That work requires deep familiarity with the system. AI-generated code arrives with no such familiarity. Review becomes harder precisely when the code being reviewed contains more defects per line than human-written code.

The failure mode is not a single bad commit. It is gradual erosion. Teams move faster. Coverage appears high. Pull requests ship. Comprehension of what the system actually does — not what it appears to do — decreases.

When the Kiro agent deleted a production environment, no human had formally specified what the agent was permitted to do. The agent acted within a comprehension gap.

---

## 4. We Solved This Elsewhere

Software correctness problems that kill people have been solved. The solutions are well-documented.

Aviation uses [DO-178C](https://en.wikipedia.org/wiki/DO-178C), the international standard for airborne software certification. Level A software — software whose failure could cause a catastrophic accident — requires exhaustive structural coverage, formal review, and independence between development and verification. Airlines do not ship flight control software based on confidence. They ship it based on proof of correctness against formal requirements.

Medical devices operate under [IEC 62304](https://www.iso.org/standard/38421.html), which the FDA accepts as evidence that medical device software meets an acceptable standard. Class C software — software whose failure could result in death — requires systematic verification at every stage of the software lifecycle. The requirement is not "test it thoroughly." The requirement is "demonstrate it satisfies its specification."

Neither domain tolerates "we think it's correct." Both require formal evidence.

The aviation and medical industries did not invent these requirements because formal verification was cheap or easy. They invented them because the alternative — shipping unproven code — was not acceptable given the consequences of failure.

---

## 5. AI Changed the Economics

Formal verification has always been technically available. It has not been economically practical for most software development.

The barrier was cost of specification. Writing a formal behavioral specification for a function takes longer than writing the function. For human-authored code, the specification cost was always higher than the code cost. Teams chose testing and code review instead.

AI code generation breaks that ratio.

When an LLM generates a function in three seconds, the development time drops toward zero. The verification time does not. The ratio inverts. Specification and proof are now the dominant cost — but the function itself is free.

The cost of specification and proof is now lower than the cost of debugging a production defect. That inversion is new.

The Kiro outage lasted thirteen hours. Thirteen hours of AWS downtime has a calculable cost. Formal specification of the operation Kiro was executing would have taken minutes.

The economic argument for proof-as-default exists now in a way it did not five years ago.

---

## 6. A New Term for a New Practice

In September 2025, researchers from BAIF, MIT, and nine other institutions published a benchmark paper at [Dafny @ POPL 2026](https://arxiv.org/abs/2509.22908). They coined a term for what they were measuring.

Vericoding: LLM generation of formally verified code from formal specifications. The contrast class is vibe coding — generating potentially buggy code from natural language descriptions.

The paper presents the largest existing benchmark for this task, spanning multiple verification-capable languages. The benchmark measures not whether code compiles or passes tests, but whether code carries a machine-checked proof that it satisfies its specification.

The distinction matters. Tests verify behavior on the inputs you thought to test. Formal proof verifies behavior on all possible inputs — including the ones you did not consider.

A JWT expiry check that fails when the expiry field is `None` will pass unit tests if no test passes `None`. A property-based test finds it only if the tester wrote a generator that reaches `None`. A formal proof will always find it, because the proof cannot complete unless the function handles every case.

The difference between a 45% defect rate and a 0% defect rate is not better prompts. It is mathematical proof as a build requirement.

---

## 7. What This Requires

Proof-as-default requires three technical changes.

**Specification before generation.** Code must derive from a formal behavioral specification, not from a natural language prompt. The specification defines what the function must do, what it must not do, and what it must preserve across all inputs. The LLM generates an implementation. The specification gates acceptance.

**Proof as a CI artifact.** Each merged commit carries a machine-checked proof that the implementation satisfies the specification. The proof is versioned alongside the code. The CI pipeline fails if the proof does not exist or does not check. No proof, no merge.

**Counterexample-guided repair loops.** When a proof attempt fails, the verification system extracts a concrete counterexample — a specific input that causes the implementation to violate the specification. That counterexample feeds back into the next generation attempt. The loop continues until proof succeeds or the specification is revised.

These are not research-only capabilities. Dafny 4.x ships with a verification compiler that produces machine-checked proofs. CrossHair performs symbolic execution for Python functions. Hypothesis finds boundary violations through property-based testing. The tools exist. The practice of requiring them as standard software development infrastructure does not yet exist at scale.

The aviation industry did not wait for formal verification to become easy before requiring it. It required it, and the tooling matured to meet the requirement.

---

## 8. The Open Question

The open question is not whether AI-generated code contains defects. It does. Three independent studies confirm it.

The open question is not whether formal verification can catch what testing misses. It can. The mathematics of proof cover all inputs by construction.

The open question is whether the software industry treats the Kiro incident as an anomaly or as a signal.

Kiro is not the last AI agent that will be given authority to act on production systems. It is the first widely reported one. The systems AI agents will be authorized to act on will become more critical, not less. The volume of AI-generated code will increase, not decrease.

The signal is clear: velocity without proof creates outages. The aviation and medical industries solved this problem decades ago. The tools exist. The economic case is now favorable.

The only remaining variable is whether the software industry decides to require proof.

---

*The author builds [Nightjar](https://github.com/j4ngzzz/Nightjar), a verification orchestrator for Python that implements proof-as-default for AI-generated code.*

---

**Sources cited:**
1. Amazon Kiro incident: https://www.ruh.ai/blogs/amazon-kiro-ai-outage-ai-governance-failure
2. Veracode 2025 GenAI Code Security Report: https://www.veracode.com/resources/analyst-reports/2025-genai-code-security-report/
3. CodeRabbit State of AI vs Human Code Generation Report: https://www.coderabbit.ai/blog/state-of-ai-vs-human-code-generation-report
4. Uplevel AI productivity study (41% bug increase): https://uplevelteam.com/blog/ai-for-developer-productivity
5. Addy Osmani, "Comprehension Debt": https://addyosmani.com/blog/comprehension-debt/
6. BAIF et al., "A benchmark for formally verified program synthesis" (arXiv 2509.22908): https://arxiv.org/abs/2509.22908
7. DO-178C aviation software standard: https://en.wikipedia.org/wiki/DO-178C
8. IEC 62304 medical device software standard: https://www.iso.org/standard/38421.html
