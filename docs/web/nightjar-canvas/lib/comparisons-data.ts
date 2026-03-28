/**
 * Nightjar Comparisons Data
 *
 * 7 head-to-head comparisons showing how Nightjar differs from
 * existing security and verification tools.
 */

export interface ComparisonFeature {
  category: string;
  feature: string;
  nightjar: string | boolean;
  competitor: string | boolean;
}

export interface Comparison {
  slug: string;
  competitor: string;
  tagline: string;
  summary: string;
  verdict: string;
  nightjarStrengths: string[];
  competitorStrengths: string[];
  features: ComparisonFeature[];
}

export const comparisons: Comparison[] = [
  {
    slug: "nightjar-vs-crosshair",
    competitor: "CrossHair",
    tagline: "Symbolic execution vs. full formal proof",
    summary:
      "CrossHair uses symbolic execution and property-based testing to find counterexamples to Python contracts. Nightjar goes further: it generates Dafny formal proofs and synthesises specifications from runtime traces. Nightjar subsumes CrossHair as Stage 3 in its pipeline.",
    verdict:
      "CrossHair is excellent at finding counterexamples in isolation. Nightjar runs CrossHair internally, then escalates to mathematical proof when counterexamples cannot be found.",
    nightjarStrengths: [
      "Dafny formal verification (mathematical proof, not just testing)",
      "Auto-generates specs from runtime traces via immune system",
      "6-stage pipeline: schema → PBT → CrossHair → formal proof",
      "CEGIS repair loop synthesises fixes from counterexamples",
      "Covers multi-module invariants and temporal supersession",
    ],
    competitorStrengths: [
      "Lightweight — pip install, no external tools required",
      "Works with standard Python type annotations and asserts",
      "Fast for small functions",
      "Good IDE integration",
    ],
    features: [
      { category: "Analysis", feature: "Symbolic execution", nightjar: true, competitor: true },
      { category: "Analysis", feature: "Formal proof (Dafny)", nightjar: true, competitor: false },
      { category: "Analysis", feature: "Property-based testing", nightjar: true, competitor: false },
      { category: "Analysis", feature: "Runtime trace mining", nightjar: true, competitor: false },
      { category: "Workflow", feature: "Auto-generates specs", nightjar: true, competitor: false },
      { category: "Workflow", feature: "CEGIS repair loop", nightjar: true, competitor: false },
      { category: "Workflow", feature: "Multi-module invariants", nightjar: true, competitor: false },
      { category: "Integration", feature: "CI/CD pipeline", nightjar: true, competitor: "limited" },
    ],
  },
  {
    slug: "nightjar-vs-semgrep",
    competitor: "Semgrep",
    tagline: "Pattern matching vs. semantic proof",
    summary:
      "Semgrep finds bugs by matching code patterns. It is fast and rule-based. Nightjar proves that code satisfies behavioural contracts — it is not pattern matching but semantic verification. Nightjar found real bugs in httpx, fastmcp, and litellm that no Semgrep rule covers.",
    verdict:
      "Semgrep is a best-in-class static analysis tool for known pattern classes. Nightjar catches a different class of bugs: semantic contract violations, logic errors, and invariant breaks that have no matching pattern.",
    nightjarStrengths: [
      "Catches semantic bugs with no pattern to match (e.g. falsy `exp=0` JWT bypass)",
      "Verifies behavioural contracts, not just syntax",
      "Generates formal proofs — not just warnings",
      "48 confirmed bugs found in popular Python packages",
      "No rule library required — specs are derived from code",
    ],
    competitorStrengths: [
      "Extremely fast on large codebases",
      "Thousands of community and proprietary rules",
      "Language-agnostic",
      "Low false-positive rate for known patterns",
      "First-class CI integration",
    ],
    features: [
      { category: "Detection", feature: "Known vulnerability patterns", nightjar: true, competitor: true },
      { category: "Detection", feature: "Logic / semantic errors", nightjar: true, competitor: false },
      { category: "Detection", feature: "Contract violations", nightjar: true, competitor: false },
      { category: "Detection", feature: "Formal proof generation", nightjar: true, competitor: false },
      { category: "Scale", feature: "Monorepo scale", nightjar: "coming", competitor: true },
      { category: "Scale", feature: "Real-time in editor", nightjar: false, competitor: true },
    ],
  },
  {
    slug: "nightjar-vs-bandit",
    competitor: "Bandit",
    tagline: "Security linting vs. verified correctness",
    summary:
      "Bandit is a Python security linter that flags dangerous function calls and imports. It operates at the AST level and does not understand program semantics. Nightjar's verification pipeline catches the bugs Bandit misses — the ones that look syntactically correct but are semantically wrong.",
    verdict:
      "Bandit would not catch any of the 48 bugs Nightjar found. Falsy JWT expiry checks, mutable defaults, and getattr-on-dict errors all look clean to a pattern linter. Use both: Bandit for quick AST scans, Nightjar for semantic proof.",
    nightjarStrengths: [
      "Catches falsy-check logic errors (e.g. `if exp and ...`)",
      "Catches mutable default argument bugs",
      "Catches semantic type mismatches (`getattr` on dict)",
      "Generates verified fixes, not just warnings",
      "No false negatives for verified properties",
    ],
    competitorStrengths: [
      "Zero configuration required",
      "Fast — seconds on any codebase",
      "Covers OWASP Top 10 patterns",
      "Widely understood by security teams",
      "Free and open source",
    ],
    features: [
      { category: "Detection", feature: "Dangerous imports / calls", nightjar: true, competitor: true },
      { category: "Detection", feature: "Semantic logic errors", nightjar: true, competitor: false },
      { category: "Detection", feature: "Contract verification", nightjar: true, competitor: false },
      { category: "Output", feature: "Actionable fix generation", nightjar: true, competitor: false },
      { category: "Output", feature: "Formal proof certificate", nightjar: true, competitor: false },
    ],
  },
  {
    slug: "nightjar-vs-snyk",
    competitor: "Snyk",
    tagline: "Dependency CVEs vs. first-party logic proof",
    summary:
      "Snyk monitors dependency graphs for known CVEs and license issues. It does not analyse first-party logic or verify that your code correctly uses its dependencies. Nightjar verifies that your code handles edge cases that third-party packages expose — including the 48 confirmed bugs in packages Snyk marks as clean.",
    verdict:
      "Snyk and Nightjar are complementary. Snyk monitors the supply chain. Nightjar proves your first-party code is correct and that you are not inadvertently triggering bugs in your dependencies.",
    nightjarStrengths: [
      "Verifies first-party logic that calls third-party packages",
      "Finds bugs in packages with no published CVE",
      "Generates proofs, not just vulnerability lists",
      "Works on private code with no cloud upload required",
      "Catches usage errors of dependency APIs",
    ],
    competitorStrengths: [
      "Industry standard for supply chain CVE monitoring",
      "Covers npm, PyPI, Maven, and more",
      "Excellent CI/CD and IDE integration",
      "License compliance scanning",
      "Fix PRs generated automatically for known CVEs",
    ],
    features: [
      { category: "Scope", feature: "Dependency CVE scanning", nightjar: false, competitor: true },
      { category: "Scope", feature: "First-party logic verification", nightjar: true, competitor: false },
      { category: "Scope", feature: "Dependency usage verification", nightjar: true, competitor: false },
      { category: "Output", feature: "Formal proof generation", nightjar: true, competitor: false },
      { category: "Output", feature: "Fix PRs", nightjar: "coming", competitor: true },
    ],
  },
  {
    slug: "nightjar-vs-mypy-pytest",
    competitor: "mypy + pytest",
    tagline: "Types and tests vs. mathematical proof",
    summary:
      "mypy proves types are consistent. pytest proves that specific inputs produce specific outputs. Neither proves that no input can violate a contract. Nightjar's formal verification closes this gap: it proves universally quantified properties over all possible inputs.",
    verdict:
      "mypy + pytest is necessary but not sufficient. They cannot prove absence of bugs — only presence of correct behavior on tested inputs. Nightjar adds the missing layer: mathematical proof of correctness for all inputs.",
    nightjarStrengths: [
      "Universal quantification — proves all inputs, not just tested ones",
      "Dafny formal proof with machine-checkable certificate",
      "Auto-generates property-based tests from specs",
      "CEGIS loop finds counterexamples and repairs them",
      "Specs survive code regeneration unchanged",
    ],
    competitorStrengths: [
      "mypy: industry standard type checking, free and fast",
      "pytest: enormous ecosystem, excellent tooling",
      "Both are widely understood by all Python developers",
      "Incremental adoption with no spec language required",
      "pytest fixtures and parametrize cover many edge cases",
    ],
    features: [
      { category: "Coverage", feature: "Type safety", nightjar: true, competitor: true },
      { category: "Coverage", feature: "Tested-input correctness", nightjar: true, competitor: true },
      { category: "Coverage", feature: "All-input proof", nightjar: true, competitor: false },
      { category: "Coverage", feature: "Temporal invariants", nightjar: true, competitor: false },
      { category: "Workflow", feature: "Auto-generates tests from specs", nightjar: true, competitor: false },
    ],
  },
  {
    slug: "nightjar-vs-github-copilot",
    competitor: "GitHub Copilot",
    tagline: "Code generation vs. verified code generation",
    summary:
      "GitHub Copilot generates code from prompts. It produces plausible code that may contain subtle logic errors. Nightjar also generates code — but mathematically proves the generated code satisfies its spec before accepting it. The difference: Copilot confidence vs. Nightjar certainty.",
    verdict:
      "Copilot and Nightjar can be used together. Write specs, let Copilot draft implementations, run Nightjar to prove correctness. Nightjar is the verification layer that makes AI-generated code production-safe.",
    nightjarStrengths: [
      "Generated code is formally verified before being accepted",
      "CEGIS loop rejects and repairs failing implementations",
      "Specs are the durable artifact — code is regenerated",
      "No hallucinated APIs — verification catches them",
      "Audit trail: proof certificate stored per module",
    ],
    competitorStrengths: [
      "Extremely fast code generation",
      "Works across all languages and frameworks",
      "First-class IDE integration",
      "Large context window for complex refactors",
      "Chat interface for explanations",
    ],
    features: [
      { category: "Generation", feature: "Code generation from prompt", nightjar: true, competitor: true },
      { category: "Quality", feature: "Formal verification of output", nightjar: true, competitor: false },
      { category: "Quality", feature: "CEGIS repair on failure", nightjar: true, competitor: false },
      { category: "Quality", feature: "Proof certificate", nightjar: true, competitor: false },
      { category: "Integration", feature: "IDE plugin", nightjar: "coming", competitor: true },
    ],
  },
  {
    slug: "nightjar-vs-deepeval",
    competitor: "DeepEval",
    tagline: "LLM output evaluation vs. code contract proof",
    summary:
      "DeepEval evaluates LLM outputs against quality metrics: correctness, faithfulness, relevance. It operates on natural-language outputs. Nightjar verifies the code that runs LLM applications — the parsers, validators, routers, and API handlers that sit around the LLM. These are different layers.",
    verdict:
      "DeepEval and Nightjar address different layers. DeepEval: is the LLM output good? Nightjar: is the code handling the LLM output correct? Both are needed in a production LLM application.",
    nightjarStrengths: [
      "Verifies the application code around LLM calls",
      "Catches logic errors in parsers, routers, validators",
      "Found real bugs in litellm and hermes-agent",
      "Formal proof of correctness — not probabilistic metrics",
      "Works on non-LLM code too",
    ],
    competitorStrengths: [
      "Evaluates LLM output quality end-to-end",
      "Hallucination detection and faithfulness metrics",
      "Regression tracking across model versions",
      "RAG pipeline evaluation",
      "Human-in-the-loop evaluation workflows",
    ],
    features: [
      { category: "Scope", feature: "LLM output quality metrics", nightjar: false, competitor: true },
      { category: "Scope", feature: "Application code verification", nightjar: true, competitor: false },
      { category: "Scope", feature: "Formal proof generation", nightjar: true, competitor: false },
      { category: "Scope", feature: "Hallucination detection", nightjar: false, competitor: true },
      { category: "Integration", feature: "Works on any Python code", nightjar: true, competitor: false },
    ],
  },
];

export function getComparisonBySlug(slug: string): Comparison | undefined {
  return comparisons.find((c) => c.slug === slug);
}

export const comparisonSlugs = comparisons.map((c) => c.slug);
