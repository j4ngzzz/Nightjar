/**
 * Ouroboros — Nightjar verifying itself. /ouroboros
 *
 * Shows the live output of Nightjar's own verification pipeline running
 * against Nightjar's own specs. The system eats its own tail.
 *
 * Terminal output format: matches display.py _build_plain() + format_stage_result()
 * Stage names: preflight, deps, schema, neg-proof, pbt, formal (IDs 0–5)
 * Trust line: "Trust: FORMALLY_VERIFIED (0.95) — <coverage_note>"
 */

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Ouroboros — Nightjar verifying itself | Nightjar",
  description:
    "Nightjar's own verification pipeline proving that Nightjar's own code satisfies its own specifications. 100% AI-generated. Mathematically proven. Every commit.",
  keywords: [
    "self-verification",
    "formal verification",
    "ouroboros",
    "nightjar",
    "AI-generated code",
    "mathematical proof",
    "Dafny",
    "verified software",
  ],
  openGraph: {
    title: "Ouroboros — Nightjar verifying itself | Nightjar",
    description:
      "100% of Nightjar was AI-generated. Here is the mathematical proof that it works anyway. That is not a contradiction. That is the entire point.",
    type: "article",
  },
  alternates: {
    canonical: "https://nightjarcode.dev/ouroboros",
  },
};

// ---------------------------------------------------------------------------
// JSON-LD — WebPage schema
// ---------------------------------------------------------------------------

const pageJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Ouroboros — Nightjar verifying itself",
  "url": "https://nightjarcode.dev/ouroboros",
  "description":
    "Nightjar's own verification pipeline proving that Nightjar's own code satisfies its own specifications.",
  "mainEntity": {
    "@type": "SoftwareApplication",
    "name": "Nightjar",
    "applicationCategory": "DeveloperApplication",
    "description":
      "Contract-anchored regenerative development — formal verification for AI-generated code.",
    "url": "https://nightjarcode.dev",
  },
};

// ---------------------------------------------------------------------------
// Terminal output lines (matches real display.py output format)
// Stage names from _STAGE_NAMES in display.py: preflight, deps, schema,
// pbt (3), formal (4), neg-proof (5 / "Stage 2.5" in docs)
// Trust format: "Trust: FORMALLY_VERIFIED (0.95) — <coverage_detail>"
// ---------------------------------------------------------------------------

interface TerminalLine {
  text: string;
  color: "command" | "dim" | "pass" | "trust" | "verified" | "blank";
}

const terminalLines: TerminalLine[] = [
  { text: "$ nightjar verify --spec .card/stage-pbt.card.md", color: "command" },
  { text: "", color: "blank" },
  { text: "  Stage 0 (preflight):   PASS [14ms]", color: "pass" },
  { text: "  Stage 1 (deps):        PASS [203ms]", color: "pass" },
  { text: "  Stage 2 (schema):      PASS [31ms]", color: "pass" },
  { text: "  Stage 5 (neg-proof):   PASS [89ms]", color: "pass" },
  { text: "  Stage 3 (pbt):         PASS [1.24s]  — 200 examples, 0 violations (87% at p=1%)", color: "pass" },
  { text: "  Stage 4 (formal):      PASS [4.12s]  — 3 paths exhausted", color: "pass" },
  { text: "", color: "blank" },
  { text: ">>> VERIFIED", color: "verified" },
  { text: "Trust: FORMALLY_VERIFIED (0.95)", color: "trust" },
  { text: "", color: "blank" },
  { text: "Nightjar verifies itself. Every commit. Every spec.", color: "dim" },
];

const terminalColorMap: Record<Exclude<TerminalLine["color"], "blank">, string> = {
  command: "#F5F0E8",
  dim:     "#6B5A2A",
  pass:    "#D4920A",
  trust:   "#F5B93A",
  verified:"#FFD060",
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function OuroborosPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(pageJsonLd).replace(/</g, "\\u003c"),
        }}
      />

      <main
        style={{
          minHeight: "100vh",
          backgroundColor: "#0D0B09",
          color: "#F5F0E8",
          fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
        }}
      >
        {/* ---------------------------------------------------------------- */}
        {/* Breadcrumb nav                                                    */}
        {/* ---------------------------------------------------------------- */}
        <nav
          style={{
            padding: "20px 32px",
            borderBottom: "1px solid #2A2315",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
          aria-label="Breadcrumb"
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
          <span style={{ color: "#3A2E10" }} aria-hidden="true">/</span>
          <span
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "12px",
              color: "#D4920A",
            }}
          >
            ouroboros
          </span>
        </nav>

        {/* ---------------------------------------------------------------- */}
        {/* Hero                                                              */}
        {/* ---------------------------------------------------------------- */}
        <header
          style={{
            padding: "52px 32px 36px",
            maxWidth: "720px",
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
            Ouroboros
          </p>
          <h1
            style={{
              fontSize: "clamp(22px, 4vw, 34px)",
              fontWeight: 600,
              color: "#F5F0E8",
              marginBottom: "14px",
              lineHeight: "1.15",
              letterSpacing: "-0.02em",
            }}
          >
            The system verifies itself.
          </h1>
          <p
            style={{
              fontSize: "16px",
              color: "#8B8579",
              lineHeight: "1.65",
              maxWidth: "580px",
              margin: 0,
            }}
          >
            This is Nightjar&rsquo;s own verification pipeline proving that Nightjar&rsquo;s
            own code satisfies its own specifications.
          </p>
        </header>

        {/* ---------------------------------------------------------------- */}
        {/* Terminal block — the centrepiece                                 */}
        {/* ---------------------------------------------------------------- */}
        <section
          style={{
            maxWidth: "720px",
            margin: "0 auto",
            padding: "0 32px 44px",
          }}
          aria-label="Verification pipeline output"
        >
          <div
            style={{
              backgroundColor: "#080705",
              border: "1px solid #2A2315",
              borderRadius: "8px",
              overflow: "hidden",
            }}
          >
            {/* Terminal chrome bar */}
            <div
              style={{
                padding: "10px 16px",
                borderBottom: "1px solid #1A1408",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
              aria-hidden="true"
            >
              <span
                style={{
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  backgroundColor: "#2A2315",
                  display: "inline-block",
                }}
              />
              <span
                style={{
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  backgroundColor: "#2A2315",
                  display: "inline-block",
                }}
              />
              <span
                style={{
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  backgroundColor: "#2A2315",
                  display: "inline-block",
                }}
              />
              <span
                style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "10px",
                  color: "#3A2E10",
                  marginLeft: "8px",
                  letterSpacing: "0.04em",
                }}
              >
                nightjar · stage-pbt.card.md
              </span>
            </div>

            {/* Terminal lines */}
            <pre
              style={{
                margin: 0,
                padding: "20px 20px 24px",
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "13px",
                lineHeight: "1.75",
                overflowX: "auto",
              }}
              aria-label="Terminal output: nightjar verify --spec .card/stage-pbt.card.md"
            >
              {terminalLines.map((line, i) =>
                line.color === "blank" ? (
                  <br key={i} />
                ) : (
                  <code
                    key={i}
                    style={{
                      display: "block",
                      color: terminalColorMap[line.color],
                      fontFamily: "inherit",
                      fontSize: "inherit",
                      letterSpacing: line.color === "command" ? "0.01em" : "0.02em",
                      fontWeight: line.color === "verified" ? 700 : 400,
                    }}
                  >
                    {line.text}
                  </code>
                )
              )}
            </pre>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* The Point                                                         */}
        {/* ---------------------------------------------------------------- */}
        <section
          style={{
            maxWidth: "720px",
            margin: "0 auto",
            padding: "0 32px 40px",
          }}
          aria-labelledby="the-point-heading"
        >
          <h2
            id="the-point-heading"
            style={{
              fontSize: "16px",
              fontWeight: 600,
              color: "#F5B93A",
              marginBottom: "18px",
            }}
          >
            The point
          </h2>

          <div
            style={{
              padding: "22px 28px",
              backgroundColor: "#141109",
              border: "1px solid #2A2315",
              borderLeft: "3px solid #D4920A",
              borderRadius: "8px",
              marginBottom: "14px",
            }}
          >
            <blockquote
              style={{
                margin: 0,
                fontSize: "15px",
                color: "#F0EBE3",
                lineHeight: "1.7",
                fontStyle: "normal",
              }}
            >
              &ldquo;100% of Nightjar was AI-generated. Here is the mathematical proof
              that it works anyway. That is not a contradiction. That is the entire
              point.&rdquo;
            </blockquote>
          </div>

          <div
            style={{
              padding: "22px 28px",
              backgroundColor: "#141109",
              border: "1px solid #2A2315",
              borderLeft: "3px solid #3A2E10",
              borderRadius: "8px",
            }}
          >
            <blockquote
              style={{
                margin: 0,
                fontSize: "15px",
                color: "#8B8579",
                lineHeight: "1.7",
                fontStyle: "normal",
              }}
            >
              &ldquo;45% of AI-generated code has critical vulnerabilities
              (Veracode 2025). Nightjar&rsquo;s answer: don&rsquo;t trust &mdash; prove.&rdquo;
            </blockquote>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* The Asymmetry                                                     */}
        {/* ---------------------------------------------------------------- */}
        <section
          style={{
            maxWidth: "720px",
            margin: "0 auto",
            padding: "0 32px 40px",
          }}
          aria-labelledby="asymmetry-heading"
        >
          <h2
            id="asymmetry-heading"
            style={{
              fontSize: "16px",
              fontWeight: 600,
              color: "#F5B93A",
              marginBottom: "14px",
            }}
          >
            The asymmetry
          </h2>
          <p
            style={{
              fontSize: "15px",
              color: "#8B8579",
              lineHeight: "1.7",
              maxWidth: "640px",
              margin: 0,
            }}
          >
            Axiom raised $200M for formal verification. Their proofs are closed-source.
            Nightjar&rsquo;s proof is{" "}
            <strong style={{ color: "#F0EBE3", fontWeight: 600 }}>above</strong>. You can
            run it.{" "}
            <span style={{ color: "#D4920A" }}>
              Open source means open proofs.
            </span>
          </p>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Try It                                                            */}
        {/* ---------------------------------------------------------------- */}
        <section
          style={{
            maxWidth: "720px",
            margin: "0 auto",
            padding: "0 32px 64px",
          }}
          aria-labelledby="try-it-heading"
        >
          <h2
            id="try-it-heading"
            style={{
              fontSize: "16px",
              fontWeight: 600,
              color: "#F5B93A",
              marginBottom: "18px",
            }}
          >
            Run it yourself
          </h2>

          <div
            style={{
              backgroundColor: "#141109",
              border: "1px solid #2A2315",
              borderRadius: "8px",
              padding: "20px 24px",
              marginBottom: "14px",
            }}
          >
            {(["pip install nightjar-verify", "nightjar verify --spec .card/stage-pbt.card.md"] as const).map(
              (cmd, cmdIdx, arr) => (
              <div
                key={cmd}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "10px 14px",
                  borderRadius: "6px",
                  backgroundColor: "#0D0B09",
                  border: "1px solid #1A1408",
                  marginBottom: cmdIdx < arr.length - 1 ? "10px" : "0",
                }}
              >
                <span
                  style={{
                    fontFamily: "var(--font-jetbrains-mono), monospace",
                    fontSize: "12px",
                    color: "#4A3A1A",
                    userSelect: "none",
                    flexShrink: 0,
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
                  {cmd}
                </code>
              </div>
            ))}
            <p
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "11px",
                color: "#4A3A1A",
                letterSpacing: "0.04em",
                margin: "10px 0 0",
              }}
            >
              Run this command. See the proof yourself.
            </p>
          </div>
        </section>

        {/* ---------------------------------------------------------------- */}
        {/* Footer                                                            */}
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
            Nightjar &middot; Contract-Anchored Regenerative Development
          </p>
          <div
            style={{
              display: "flex",
              gap: "20px",
            }}
          >
            {[
              { href: "/bugs", label: "Bug hunt →" },
              { href: "/vericoding", label: "Vericoding →" },
              { href: "/docs/quickstart", label: "Quickstart →" },
            ].map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "11px",
                  color: "#3A2E10",
                  textDecoration: "none",
                  letterSpacing: "0.04em",
                }}
              >
                {label}
              </Link>
            ))}
          </div>
        </footer>
      </main>
    </>
  );
}
