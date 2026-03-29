/**
 * What is Vericoding? — /vericoding
 *
 * Explains vericoding: LLM-generation of formally verified code from formal
 * specifications, contrasts it with vibe coding, lists supporting tools, and
 * shows how Nightjar implements the practice.
 *
 * Cite: "A benchmark for vericoding: formally verified program synthesis"
 * Bursuc, Ehrenborg, Lin et al. (Beneficial AI Foundation / MIT), arXiv:2509.22908
 */

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "What is Vericoding? | Nightjar",
  description:
    "Vericoding is LLM-generation of formally verified code from formal specifications. Learn how it differs from vibe coding, what tools support it, and how Nightjar implements it.",
  keywords: [
    "vericoding",
    "formal verification",
    "vibe coding",
    "verified code generation",
    "Dafny",
    "nightjar",
    "BAIF",
    "formally verified program synthesis",
  ],
  openGraph: {
    title: "What is Vericoding? | Nightjar",
    description:
      "Vericoding is LLM-generation of formally verified code from formal specifications — not just tested, but mathematically proven correct.",
    type: "article",
  },
  alternates: {
    canonical: "https://nightjarcode.dev/vericoding",
  },
};

// ---------------------------------------------------------------------------
// FAQ data — drives both the visible accordion and the JSON-LD FAQPage schema
// ---------------------------------------------------------------------------

const faqs = [
  {
    question: "What is vericoding?",
    answer:
      "Vericoding is the practice of using LLMs to generate formally verified code from formal specifications. The generated code is not merely tested — it is accompanied by a mathematical proof that it satisfies the spec. The term was coined in the 2025 BAIF/MIT benchmark paper (arXiv:2509.22908), which evaluated AI systems across 12,504 formal specifications in Dafny, Verus/Rust, and Lean.",
  },
  {
    question: "How is vericoding different from vibe coding?",
    answer:
      "Vibe coding uses natural language prompts and intuition to generate code, accepting informal or no specification and no correctness guarantee. Vericoding starts with a formal machine-checkable spec, then generates code that an automated verifier proves satisfies that spec. The output is not code that looks right — it is code that is provably correct against an explicit contract.",
  },
  {
    question: "What tools support vericoding today?",
    answer:
      "The three verification languages benchmarked in arXiv:2509.22908 are Dafny (82% LLM success rate), Verus/Rust (44%), and Lean (27%). Nightjar adds a full pipeline around Dafny: it reads .card.md specs, generates code via an Analyst→Formalizer→Coder chain, and runs a 6-stage pipeline ending in a Dafny formal proof.",
  },
  {
    question: "Does vericoding slow down development?",
    answer:
      "For AI-generated code specifically, vericoding can be faster than manual debugging. The BAIF benchmark showed pure Dafny verification success improved from 68% to 96% in one year, meaning the overhead of writing a spec is increasingly offset by the LLM generating correct code on the first attempt. Nightjar's CEGIS retry loop automates recovery from verification failures without human intervention.",
  },
  {
    question: "What is the BAIF benchmark for vericoding?",
    answer:
      "The BAIF (Beneficial AI Foundation) benchmark, arXiv:2509.22908, is a dataset of 12,504 formal specifications: 3,029 in Dafny, 2,334 in Verus/Rust, and 7,141 in Lean. It was produced by Sergiu Bursuc, Theodore Ehrenborg, Shaowei Lin, and 10 co-authors including Max Tegmark (MIT). It is the first large-scale benchmark specifically for formally verified program synthesis by LLMs.",
  },
  {
    question: "How does Nightjar implement vericoding?",
    answer:
      "Nightjar implements a 6-stage vericoding pipeline: Stage 0 (preflight), Stage 1 (dependency audit), Stage 2 (schema validation via Pydantic), Stage 2.5 (negation proof), Stage 3 (property-based testing via Hypothesis), and Stage 4 (Dafny formal proof). Specs are written in .card.md files. Code is regenerated from scratch on every build and never manually edited. A CEGIS retry loop automatically repairs failing specs.",
  },
];

// ---------------------------------------------------------------------------
// Contrast table data
// ---------------------------------------------------------------------------

interface ContrastRow {
  dimension: string;
  vibeCoding: string;
  vericoding: string;
  vericodingGood: boolean;
}

const contrastRows: ContrastRow[] = [
  {
    dimension: "Specification",
    vibeCoding: "Natural language prompt",
    vericoding: "Formal machine-checkable spec",
    vericodingGood: true,
  },
  {
    dimension: "Correctness guarantee",
    vibeCoding: "None — code might work",
    vericoding: "Mathematical proof",
    vericodingGood: true,
  },
  {
    dimension: "Verification method",
    vibeCoding: "Human review, ad-hoc tests",
    vericoding: "Automated verifier (Dafny, Lean, Verus)",
    vericodingGood: true,
  },
  {
    dimension: "Output artifact",
    vibeCoding: "Code + test suite",
    vericoding: "Code + proof + audit trail",
    vericodingGood: true,
  },
  {
    dimension: "Failure recovery",
    vibeCoding: "Prompt again, guess",
    vericoding: "CEGIS — counterexample-guided repair",
    vericodingGood: true,
  },
  {
    dimension: "Manual editing",
    vibeCoding: "Required — AI output is a draft",
    vericoding: "Prohibited — spec is the source of truth",
    vericodingGood: true,
  },
  {
    dimension: "Risk profile",
    vibeCoding: "High — unknown unknowns",
    vericoding: "Bounded — only unspecified behaviors can fail",
    vericodingGood: true,
  },
];

// ---------------------------------------------------------------------------
// Tools data
// ---------------------------------------------------------------------------

interface VeritoolEntry {
  name: string;
  role: string;
  successRate?: string;
  tagline: string;
}

const veritools: VeritoolEntry[] = [
  {
    name: "Dafny",
    role: "Verification language + verifier",
    successRate: "82%",
    tagline:
      "Microsoft Research's verifier-integrated language. Highest LLM success rate in the BAIF benchmark. Used by Nightjar's Stage 4.",
  },
  {
    name: "Verus / Rust",
    role: "Rust verification layer",
    successRate: "44%",
    tagline:
      "Brings Dafny-style specifications into idiomatic Rust. Strong safety story for systems code.",
  },
  {
    name: "Lean 4",
    role: "Proof assistant + programming language",
    successRate: "27%",
    tagline:
      "Mathlib-backed proof assistant. Highest expressiveness, steepest LLM learning curve. Gold standard for pure math proofs.",
  },
  {
    name: "Nightjar",
    role: "Full vericoding pipeline",
    tagline:
      "Wraps Dafny in a 6-stage pipeline. Reads .card.md specs, generates code via LLM, verifies, and produces shareable proof certificates.",
  },
];

// ---------------------------------------------------------------------------
// FAQPage JSON-LD
// ---------------------------------------------------------------------------

const faqJsonLd = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": faqs.map((faq) => ({
    "@type": "Question",
    "name": faq.question,
    "acceptedAnswer": {
      "@type": "Answer",
      "text": faq.answer,
    },
  })),
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function VericodingPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(faqJsonLd).replace(/</g, "\\u003c"),
        }}
      />

      <main
        style={{
          minHeight: "100vh",
          backgroundColor: "#0D0B09",
          color: "#F0EBE3",
          fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
        }}
      >
        {/* ---------------------------------------------------------------- */}
        {/* Nav breadcrumb                                                    */}
        {/* ---------------------------------------------------------------- */}
        <nav
          style={{
            padding: "20px 32px",
            borderBottom: "1px solid #2A2315",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <Link
            href="/"
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "12px",
              color: "#8B8579",
              textDecoration: "none",
            }}
          >
            nightjar
          </Link>
          <span style={{ color: "#3A2E10" }}>/</span>
          <span
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "12px",
              color: "#D4920A",
            }}
          >
            vericoding
          </span>
        </nav>

        {/* ---------------------------------------------------------------- */}
        {/* Hero header                                                       */}
        {/* ---------------------------------------------------------------- */}
        <header
          style={{
            padding: "56px 32px 40px",
            maxWidth: "900px",
            margin: "0 auto",
          }}
        >
          <p
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              color: "#3A2E10",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              marginBottom: "14px",
            }}
          >
            Concept
          </p>
          <h1
            style={{
              fontSize: "clamp(24px, 4vw, 36px)",
              fontWeight: 600,
              color: "#F5F0E8",
              marginBottom: "16px",
              lineHeight: "1.15",
              letterSpacing: "-0.02em",
            }}
          >
            What is Vericoding?
          </h1>
          <p
            style={{
              fontSize: "17px",
              color: "#8B8579",
              lineHeight: "1.65",
              maxWidth: "640px",
              margin: "0 0 20px",
            }}
          >
            Vericoding is{" "}
            <strong style={{ color: "#F0EBE3", fontWeight: 600 }}>
              LLM-generation of formally verified code from formal specifications
            </strong>
            . The output is not code that looks right — it is code accompanied by a
            mathematical proof that it satisfies an explicit contract.
          </p>
          <p
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "11px",
              color: "#6B5A2A",
              letterSpacing: "0.04em",
            }}
          >
            Term coined in:{" "}
            <a
              href="https://arxiv.org/abs/2509.22908"
              target="_blank"
              rel="noopener noreferrer"
              style={{ color: "#D4920A", textDecoration: "none" }}
            >
              arXiv:2509.22908
            </a>{" "}
            · Bursuc, Ehrenborg, Lin et al. (Beneficial AI Foundation / MIT, 2025)
          </p>
        </header>

        {/* ---------------------------------------------------------------- */}
        {/* Section 1: Definition                                            */}
        {/* ---------------------------------------------------------------- */}
        <section
          style={{
            maxWidth: "900px",
            margin: "0 auto",
            padding: "0 32px 56px",
          }}
          aria-labelledby="definition-heading"
        >
          <h2
            id="definition-heading"
            style={{
              fontSize: "18px",
              fontWeight: 600,
              color: "#F5B93A",
              marginBottom: "20px",
            }}
          >
            The definition
          </h2>

          <div
            style={{
              padding: "28px 32px",
              backgroundColor: "#141109",
              border: "1px solid #2A2315",
              borderLeft: "3px solid #D4920A",
              borderRadius: "8px",
              marginBottom: "24px",
            }}
          >
            <blockquote
              style={{
                margin: 0,
                fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
                fontSize: "16px",
                color: "#F0EBE3",
                lineHeight: "1.7",
                fontStyle: "normal",
              }}
            >
              &ldquo;Vericoding: LLM-generation of formally verified code from formal
              specifications.&rdquo;
            </blockquote>
            <footer
              style={{
                marginTop: "14px",
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "11px",
                color: "#6B5A2A",
                letterSpacing: "0.04em",
              }}
            >
              — Bursuc, Ehrenborg, Lin et al.,{" "}
              <a
                href="https://arxiv.org/abs/2509.22908"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "#A87020", textDecoration: "none" }}
              >
                &ldquo;A benchmark for vericoding: formally verified program synthesis&rdquo;
              </a>
              , arXiv:2509.22908, Beneficial AI Foundation / MIT (2025)
            </footer>
          </div>

          <p
            style={{
              fontSize: "15px",
              color: "#8B8579",
              lineHeight: "1.7",
              maxWidth: "720px",
              marginBottom: "16px",
            }}
          >
            The BAIF benchmark evaluated AI systems across{" "}
            <strong style={{ color: "#F0EBE3" }}>12,504 formal specifications</strong> in three
            verification languages — Dafny, Verus/Rust, and Lean. LLMs achieved 82% success in
            Dafny, 44% in Verus/Rust, and 27% in Lean. Pure Dafny verification success improved
            from 68% to{" "}
            <strong style={{ color: "#F5B93A" }}>96% in a single year</strong>, demonstrating
            that the practice is not just theoretically sound — it is industrially tractable today.
          </p>

          <p
            style={{
              fontSize: "15px",
              color: "#8B8579",
              lineHeight: "1.7",
              maxWidth: "720px",
            }}
          >
            Vericoding is not a niche academic exercise. It is the logical endpoint of AI-assisted
            development: if an LLM is writing your code, you can also require that LLM to supply a
            proof of correctness rather than trusting your test suite to catch every edge case.
          </p>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Section 2: Contrast table                                        */}
        {/* ---------------------------------------------------------------- */}
        <section
          style={{
            maxWidth: "900px",
            margin: "0 auto",
            padding: "0 32px 56px",
          }}
          aria-labelledby="contrast-heading"
        >
          <h2
            id="contrast-heading"
            style={{
              fontSize: "18px",
              fontWeight: 600,
              color: "#F5B93A",
              marginBottom: "8px",
            }}
          >
            Vibe coding vs. Vericoding
          </h2>
          <p
            style={{
              fontSize: "14px",
              color: "#6B5A2A",
              marginBottom: "24px",
              lineHeight: "1.6",
            }}
          >
            The difference is not speed — it is the nature of the guarantee you get at the end.
          </p>

          <div style={{ overflowX: "auto" }}>
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
                fontSize: "14px",
              }}
              aria-label="Vibe coding vs vericoding comparison"
            >
              <thead>
                <tr>
                  <th
                    style={{
                      padding: "12px 16px",
                      textAlign: "left",
                      fontFamily: "var(--font-jetbrains-mono), monospace",
                      fontSize: "10px",
                      color: "#3A2E10",
                      letterSpacing: "0.1em",
                      textTransform: "uppercase",
                      borderBottom: "1px solid #2A2315",
                      backgroundColor: "#141109",
                      fontWeight: 400,
                    }}
                  >
                    Dimension
                  </th>
                  <th
                    style={{
                      padding: "12px 16px",
                      textAlign: "left",
                      fontFamily: "var(--font-jetbrains-mono), monospace",
                      fontSize: "10px",
                      color: "#6B5A2A",
                      letterSpacing: "0.1em",
                      textTransform: "uppercase",
                      borderBottom: "1px solid #2A2315",
                      backgroundColor: "#141109",
                      fontWeight: 400,
                    }}
                  >
                    Vibe Coding
                  </th>
                  <th
                    style={{
                      padding: "12px 16px",
                      textAlign: "left",
                      fontFamily: "var(--font-jetbrains-mono), monospace",
                      fontSize: "10px",
                      color: "#D4920A",
                      letterSpacing: "0.1em",
                      textTransform: "uppercase",
                      borderBottom: "1px solid #2A2315",
                      backgroundColor: "#141109",
                      fontWeight: 400,
                    }}
                  >
                    Vericoding
                  </th>
                </tr>
              </thead>
              <tbody>
                {contrastRows.map((row, i) => (
                  <tr
                    key={row.dimension}
                    style={{
                      backgroundColor: i % 2 === 0 ? "#0D0B09" : "#141109",
                    }}
                  >
                    <td
                      style={{
                        padding: "14px 16px",
                        fontFamily: "var(--font-jetbrains-mono), monospace",
                        fontSize: "12px",
                        color: "#8B8579",
                        letterSpacing: "0.02em",
                        borderBottom: "1px solid #1A1408",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {row.dimension}
                    </td>
                    <td
                      style={{
                        padding: "14px 16px",
                        color: "#6B5A2A",
                        lineHeight: "1.5",
                        borderBottom: "1px solid #1A1408",
                      }}
                    >
                      {row.vibeCoding}
                    </td>
                    <td
                      style={{
                        padding: "14px 16px",
                        color: "#F5B93A",
                        lineHeight: "1.5",
                        borderBottom: "1px solid #1A1408",
                      }}
                    >
                      {row.vericoding}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Section 3: Tools                                                 */}
        {/* ---------------------------------------------------------------- */}
        <section
          style={{
            maxWidth: "900px",
            margin: "0 auto",
            padding: "0 32px 56px",
          }}
          aria-labelledby="tools-heading"
        >
          <h2
            id="tools-heading"
            style={{
              fontSize: "18px",
              fontWeight: 600,
              color: "#F5B93A",
              marginBottom: "8px",
            }}
          >
            Tools that exist today
          </h2>
          <p
            style={{
              fontSize: "14px",
              color: "#6B5A2A",
              marginBottom: "24px",
              lineHeight: "1.6",
            }}
          >
            Success rates are from the BAIF benchmark (arXiv:2509.22908, 2025), measured as
            percentage of formal specifications for which an LLM generated verifying code.
          </p>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))",
              gap: "16px",
            }}
          >
            {veritools.map((tool) => (
              <div
                key={tool.name}
                style={{
                  padding: "24px",
                  backgroundColor: "#141109",
                  border: "1px solid #2A2315",
                  borderRadius: "8px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    gap: "12px",
                    marginBottom: "6px",
                  }}
                >
                  <h3
                    style={{
                      fontSize: "16px",
                      fontWeight: 600,
                      color: "#F0EBE3",
                      margin: 0,
                    }}
                  >
                    {tool.name}
                  </h3>
                  {tool.successRate && (
                    <span
                      style={{
                        fontFamily: "var(--font-jetbrains-mono), monospace",
                        fontSize: "12px",
                        color: "#D4920A",
                        padding: "2px 8px",
                        border: "1px solid #D4920A",
                        borderRadius: "4px",
                        letterSpacing: "0.04em",
                      }}
                    >
                      {tool.successRate} LLM success
                    </span>
                  )}
                  {!tool.successRate && (
                    <span
                      style={{
                        fontFamily: "var(--font-jetbrains-mono), monospace",
                        fontSize: "12px",
                        color: "#F5B93A",
                        padding: "2px 8px",
                        border: "1px solid #F5B93A",
                        borderRadius: "4px",
                        letterSpacing: "0.04em",
                      }}
                    >
                      full pipeline
                    </span>
                  )}
                </div>
                <p
                  style={{
                    fontFamily: "var(--font-jetbrains-mono), monospace",
                    fontSize: "10px",
                    color: "#4A3A1A",
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    marginBottom: "10px",
                  }}
                >
                  {tool.role}
                </p>
                <p
                  style={{
                    fontSize: "13px",
                    color: "#8B8579",
                    lineHeight: "1.6",
                    margin: 0,
                  }}
                >
                  {tool.tagline}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Section 4: How Nightjar implements vericoding                    */}
        {/* ---------------------------------------------------------------- */}
        <section
          style={{
            maxWidth: "900px",
            margin: "0 auto",
            padding: "0 32px 56px",
          }}
          aria-labelledby="nightjar-heading"
        >
          <h2
            id="nightjar-heading"
            style={{
              fontSize: "18px",
              fontWeight: 600,
              color: "#F5B93A",
              marginBottom: "8px",
            }}
          >
            How Nightjar implements vericoding
          </h2>
          <p
            style={{
              fontSize: "14px",
              color: "#6B5A2A",
              marginBottom: "28px",
              lineHeight: "1.6",
            }}
          >
            Nightjar is a contract-anchored regenerative development pipeline. Developers write
            specs. AI generates code. Nightjar proves the code satisfies the specs. Code is never
            manually edited.
          </p>

          {/* Pipeline stages */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
            {[
              {
                stage: "Stage 0",
                name: "Preflight",
                desc: "Parse .card.md specs. Run 19 proven rewrite rules to normalise invariants before generation.",
                color: "#3A2E10",
              },
              {
                stage: "Stage 1",
                name: "Dependency Audit",
                desc: "Seal the dependency manifest. Run pip-audit and uv to detect vulnerabilities in the supply chain.",
                color: "#4A3A1A",
              },
              {
                stage: "Stage 2",
                name: "Schema Validation",
                desc: "Validate all data structures against Pydantic v2 models derived from the spec.",
                color: "#6B5A2A",
              },
              {
                stage: "Stage 2.5",
                name: "Negation Proof",
                desc: "Prove that the negation of each invariant is unsatisfiable — an early counterexample check.",
                color: "#A87020",
              },
              {
                stage: "Stage 3",
                name: "Property-Based Testing",
                desc: "Run Hypothesis PBT strategies generated from the spec. Failures become CEGIS counterexamples.",
                color: "#D4920A",
              },
              {
                stage: "Stage 4",
                name: "Dafny Formal Proof",
                desc: "Translate the spec into Dafny and call the verifier. A CEGIS retry loop repairs failing proofs automatically.",
                color: "#F5B93A",
              },
            ].map((step, i, arr) => (
              <div
                key={step.stage}
                style={{
                  display: "flex",
                  gap: "0",
                  position: "relative",
                }}
              >
                {/* Left rail */}
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    flexShrink: 0,
                    width: "40px",
                    marginRight: "20px",
                  }}
                >
                  <div
                    style={{
                      width: "10px",
                      height: "10px",
                      borderRadius: "50%",
                      backgroundColor: step.color,
                      flexShrink: 0,
                      marginTop: "6px",
                    }}
                  />
                  {i < arr.length - 1 && (
                    <div
                      style={{
                        width: "1px",
                        flex: 1,
                        backgroundColor: "#2A2315",
                        marginTop: "6px",
                      }}
                    />
                  )}
                </div>

                {/* Content */}
                <div
                  style={{
                    paddingBottom: i < arr.length - 1 ? "24px" : "0",
                    paddingTop: "0",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "baseline",
                      gap: "10px",
                      marginBottom: "4px",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: "var(--font-jetbrains-mono), monospace",
                        fontSize: "10px",
                        color: step.color,
                        letterSpacing: "0.08em",
                        textTransform: "uppercase",
                      }}
                    >
                      {step.stage}
                    </span>
                    <span
                      style={{
                        fontSize: "15px",
                        fontWeight: 600,
                        color: "#F0EBE3",
                      }}
                    >
                      {step.name}
                    </span>
                  </div>
                  <p
                    style={{
                      fontSize: "13px",
                      color: "#8B8579",
                      lineHeight: "1.6",
                      margin: 0,
                      maxWidth: "580px",
                    }}
                  >
                    {step.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Try it block */}
          <div
            style={{
              marginTop: "32px",
              padding: "20px 24px",
              backgroundColor: "#141109",
              border: "1px solid #2A2315",
              borderRadius: "8px",
            }}
          >
            <p
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "10px",
                color: "#6B5A2A",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                margin: "0 0 14px",
              }}
            >
              Try it
            </p>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                padding: "10px 14px",
                borderRadius: "6px",
                backgroundColor: "#0D0B09",
                border: "1px solid #1A1408",
                marginBottom: "10px",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "12px",
                  color: "#4A3A1A",
                  userSelect: "none",
                }}
                aria-hidden="true"
              >
                $
              </span>
              <code
                style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "13px",
                  color: "#F5B93A",
                  letterSpacing: "0.02em",
                }}
              >
                pip install nightjar-verify &amp;&amp; nightjar init payment
              </code>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "12px",
                padding: "10px 14px",
                borderRadius: "6px",
                backgroundColor: "#0D0B09",
                border: "1px solid #1A1408",
              }}
            >
              <span
                style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "12px",
                  color: "#4A3A1A",
                  userSelect: "none",
                }}
                aria-hidden="true"
              >
                $
              </span>
              <code
                style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "13px",
                  color: "#F5B93A",
                  letterSpacing: "0.02em",
                }}
              >
                nightjar verify --tui
              </code>
            </div>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Section 5: FAQ                                                   */}
        {/* ---------------------------------------------------------------- */}
        <section
          style={{
            maxWidth: "900px",
            margin: "0 auto",
            padding: "0 32px 80px",
          }}
          aria-labelledby="faq-heading"
        >
          <h2
            id="faq-heading"
            style={{
              fontSize: "18px",
              fontWeight: 600,
              color: "#F5B93A",
              marginBottom: "24px",
            }}
          >
            Frequently asked questions
          </h2>

          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            {faqs.map((faq) => (
              <div
                key={faq.question}
                style={{
                  padding: "20px 24px",
                  backgroundColor: "#141109",
                  border: "1px solid #2A2315",
                  borderRadius: "6px",
                }}
              >
                <h3
                  style={{
                    fontSize: "15px",
                    fontWeight: 600,
                    color: "#F0EBE3",
                    margin: "0 0 10px",
                    lineHeight: "1.4",
                  }}
                >
                  {faq.question}
                </h3>
                <p
                  style={{
                    fontSize: "14px",
                    color: "#8B8579",
                    lineHeight: "1.7",
                    margin: 0,
                  }}
                >
                  {faq.answer}
                </p>
              </div>
            ))}
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Footer                                                           */}
        {/* ---------------------------------------------------------------- */}
        <footer
          style={{
            width: "100%",
            padding: "24px 32px",
            borderTop: "1px solid #1A1408",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "12px",
          }}
        >
          <p
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              color: "#2A2315",
              letterSpacing: "0.08em",
              margin: 0,
            }}
          >
            Nightjar · Contract-Anchored Regenerative Development
          </p>
          <div
            style={{
              display: "flex",
              gap: "20px",
            }}
          >
            <Link
              href="/compare"
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "11px",
                color: "#3A2E10",
                textDecoration: "none",
                letterSpacing: "0.04em",
              }}
            >
              Compare tools →
            </Link>
            <Link
              href="/docs/quickstart"
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "11px",
                color: "#3A2E10",
                textDecoration: "none",
                letterSpacing: "0.04em",
              }}
            >
              Quickstart →
            </Link>
          </div>
        </footer>
      </main>
    </>
  );
}
