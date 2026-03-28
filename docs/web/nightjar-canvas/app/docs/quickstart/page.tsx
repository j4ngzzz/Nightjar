/**
 * Nightjar Quickstart Docs — /docs/quickstart
 *
 * 5-minute getting started guide: install, init, scan, verify.
 */

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Quickstart — 5 Minutes to First Proof | Nightjar",
  description:
    "Install Nightjar, write your first spec, generate verified code, and get a formal proof in under 5 minutes.",
};

interface Step {
  num: string;
  title: string;
  description: string;
  code: string;
  lang?: string;
  note?: string;
}

const steps: Step[] = [
  {
    num: "01",
    title: "Install Nightjar",
    description:
      "Nightjar requires Python 3.11+ and Dafny 4.x for formal verification. Install the package with pip, then verify the CLI is available.",
    code: `pip install nightjar

# Verify the install
nightjar --version`,
    lang: "bash",
    note: "Dafny 4.x is required for Stage 4 (formal proof). If you just want schema + PBT verification, you can skip it — use --fast to skip Dafny.",
  },
  {
    num: "02",
    title: "Write a spec (.card.md)",
    description:
      "Specs live in .card/ at the root of your project. Each .card.md file defines the invariants your code must satisfy. Nightjar generates and verifies code to match the spec — never the other way around.",
    code: `nightjar init payment

# This creates .card/payment.card.md
# Open it and fill in your contracts:`,
    lang: "bash",
  },
  {
    num: "02b",
    title: "Your first spec",
    description:
      "A spec defines preconditions, postconditions, and invariants. Nightjar's pipeline reads these to generate and verify code.",
    code: `# .card/payment.card.md

## Module: payment

### Function: process_payment

**Preconditions:**
- amount > 0
- currency in ["USD", "EUR", "GBP"]
- card_token is a non-empty string

**Postconditions:**
- Returns a PaymentResult with status "success" or "declined"
- If status == "success", transaction_id is a non-empty string
- If status == "declined", transaction_id is None

**Invariants:**
- total_charged >= 0
- No amount is charged on declined transactions`,
    lang: "markdown",
  },
  {
    num: "03",
    title: "Generate verified code",
    description:
      "Nightjar's generator runs three agents in sequence: Analyst (reads spec), Formalizer (converts to Dafny contracts), Coder (produces Python). The pipeline then verifies the output through 6 stages before accepting it.",
    code: `# Set your LLM model
export NIGHTJAR_MODEL=claude-sonnet-4-6

# Generate code from your spec
nightjar generate

# Output:
# ✓ Analyst extracted 3 preconditions, 2 postconditions
# ✓ Formalizer produced Dafny contracts
# ✓ Coder generated payment.py
# ✓ Stage 0 (Preflight): PASS
# ✓ Stage 1 (Deps): PASS
# ✓ Stage 2 (Schema): PASS
# ✓ Stage 3 (PBT): PASS — 1000 cases
# ✓ Stage 4 (Formal): PASS — proof complete`,
    lang: "bash",
  },
  {
    num: "04",
    title: "Verify your existing code",
    description:
      "Already have code? Point Nightjar at it with a spec. The verify command runs the full 6-stage pipeline against your existing implementation.",
    code: `# Verify all modules (full pipeline)
nightjar verify

# Fast check — skip Dafny (schema + PBT only)
nightjar verify --fast

# Verify a specific module
nightjar verify --module payment

# Launch the TUI dashboard
nightjar verify --tui`,
    lang: "bash",
  },
  {
    num: "05",
    title: "Scan a GitHub repo",
    description:
      "Nightjar can scan any public Python repository directly. Paste a GitHub URL into the scanner on the homepage to get a full verification report.",
    code: `# Or use the CLI directly:
nightjar scan https://github.com/your-org/your-repo

# The scanner:
# 1. Clones the repo
# 2. Extracts function signatures and docstrings
# 3. Generates specs automatically
# 4. Runs the full verification pipeline
# 5. Returns a structured report`,
    lang: "bash",
    note: "Public repos only for the hosted scanner. For private repos, run Nightjar locally.",
  },
];

function CodeBlock({ code, lang }: { code: string; lang?: string }) {
  return (
    <div style={{ position: "relative" }}>
      {lang && (
        <span
          style={{
            position: "absolute",
            top: "10px",
            right: "14px",
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "9px",
            color: "#3A2E10",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
          }}
        >
          {lang}
        </span>
      )}
      <pre
        style={{
          backgroundColor: "#0A0806",
          border: "1px solid #2A2315",
          borderRadius: "8px",
          padding: "20px 24px",
          overflowX: "auto",
          fontFamily: "var(--font-jetbrains-mono), monospace",
          fontSize: "13px",
          lineHeight: "1.7",
          color: "#F0EBE3",
          margin: 0,
        }}
      >
        <code>{code}</code>
      </pre>
    </div>
  );
}

function StepCard({ step }: { step: Step }) {
  return (
    <div style={{ display: "flex", gap: "24px", marginBottom: "48px" }}>
      {/* Step number */}
      <div style={{ flexShrink: 0 }}>
        <div
          style={{
            width: "44px",
            height: "44px",
            borderRadius: "50%",
            border: "1px solid #D4920A",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "rgba(212, 146, 10, 0.08)",
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "11px",
              color: "#D4920A",
              fontWeight: 600,
            }}
          >
            {step.num}
          </span>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <h2
          style={{
            fontSize: "18px",
            fontWeight: 600,
            color: "#F0EBE3",
            marginBottom: "10px",
            lineHeight: "1.3",
            marginTop: "10px",
          }}
        >
          {step.title}
        </h2>
        <p
          style={{
            color: "#8B8579",
            fontSize: "14px",
            lineHeight: "1.6",
            marginBottom: "16px",
          }}
        >
          {step.description}
        </p>
        <CodeBlock code={step.code} lang={step.lang} />
        {step.note && (
          <p
            style={{
              marginTop: "10px",
              padding: "10px 14px",
              backgroundColor: "#141109",
              border: "1px solid #2A2315",
              borderRadius: "6px",
              color: "#8B8579",
              fontSize: "12px",
              lineHeight: "1.5",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                color: "#D4920A",
                fontSize: "10px",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Note:{" "}
            </span>
            {step.note}
          </p>
        )}
      </div>
    </div>
  );
}

export default function QuickstartPage() {
  return (
    <main
      style={{
        minHeight: "100vh",
        backgroundColor: "#0D0B09",
        color: "#F0EBE3",
        fontFamily: "var(--font-geist-sans), sans-serif",
      }}
    >
      {/* Nav */}
      <nav
        style={{
          padding: "20px 32px",
          borderBottom: "1px solid #2A2315",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          flexWrap: "wrap",
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
            color: "#8B8579",
          }}
        >
          docs
        </span>
        <span style={{ color: "#3A2E10" }}>/</span>
        <span
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "12px",
            color: "#D4920A",
          }}
        >
          quickstart
        </span>
      </nav>

      <div style={{ maxWidth: "760px", margin: "0 auto", padding: "48px 32px 80px" }}>
        {/* Header */}
        <header style={{ marginBottom: "48px" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "4px 12px",
              backgroundColor: "rgba(212, 146, 10, 0.1)",
              border: "1px solid rgba(212, 146, 10, 0.3)",
              borderRadius: "100px",
              marginBottom: "20px",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "10px",
                color: "#D4920A",
                letterSpacing: "0.08em",
              }}
            >
              5-minute guide
            </span>
          </div>
          <h1
            style={{
              fontSize: "32px",
              fontWeight: 600,
              color: "#F0EBE3",
              marginBottom: "12px",
              lineHeight: "1.2",
            }}
          >
            Quickstart
          </h1>
          <p style={{ color: "#8B8579", fontSize: "15px", lineHeight: "1.6", maxWidth: "540px" }}>
            Install Nightjar, write your first spec, and get a formal proof of correctness in
            under 5 minutes.
          </p>
        </header>

        {/* Pipeline overview */}
        <div
          style={{
            padding: "20px 24px",
            backgroundColor: "#141109",
            border: "1px solid #2A2315",
            borderRadius: "8px",
            marginBottom: "48px",
          }}
        >
          <div
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              color: "#3A2E10",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              marginBottom: "14px",
            }}
          >
            Verification Pipeline
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", alignItems: "center" }}>
            {[
              { label: "0 Preflight", color: "#8B8579" },
              { label: "1 Deps", color: "#8B8579" },
              { label: "2 Schema", color: "#A87020" },
              { label: "2.5 Negation", color: "#D4920A" },
              { label: "3 PBT", color: "#F5B93A" },
              { label: "4 Formal", color: "#FFD060" },
            ].map((stage, i, arr) => (
              <>
                <span
                  key={stage.label}
                  style={{
                    fontFamily: "var(--font-jetbrains-mono), monospace",
                    fontSize: "11px",
                    color: stage.color,
                    padding: "4px 10px",
                    border: `1px solid ${stage.color}`,
                    borderRadius: "4px",
                    backgroundColor: `${stage.color}11`,
                  }}
                >
                  {stage.label}
                </span>
                {i < arr.length - 1 && (
                  <span
                    key={`arr-${i}`}
                    style={{
                      color: "#3A2E10",
                      fontFamily: "var(--font-jetbrains-mono), monospace",
                      fontSize: "12px",
                    }}
                  >
                    →
                  </span>
                )}
              </>
            ))}
          </div>
        </div>

        {/* Steps */}
        <div
          style={{
            borderLeft: "1px solid #2A2315",
            paddingLeft: "0",
          }}
        >
          {steps.map((step) => (
            <StepCard key={step.num} step={step} />
          ))}
        </div>

        {/* Next steps */}
        <div
          style={{
            borderTop: "1px solid #2A2315",
            paddingTop: "40px",
            marginTop: "8px",
          }}
        >
          <h2
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              color: "#3A2E10",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              marginBottom: "20px",
            }}
          >
            Next Steps
          </h2>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: "12px" }}>
            {[
              { href: "/bugs", label: "Browse bug reports", desc: "48 confirmed bugs found by Nightjar" },
              { href: "/compare", label: "Compare tools", desc: "Nightjar vs. Semgrep, Snyk, CrossHair" },
              { href: "/pricing", label: "Pricing", desc: "Open source, Teams, Enterprise" },
            ].map((link) => (
              <Link
                key={link.href}
                href={link.href}
                style={{
                  display: "block",
                  padding: "16px",
                  backgroundColor: "#141109",
                  border: "1px solid #2A2315",
                  borderRadius: "8px",
                  textDecoration: "none",
                  transition: "border-color 0.15s ease",
                }}
                className="next-step-link"
              >
                <div
                  style={{
                    color: "#D4920A",
                    fontSize: "13px",
                    fontWeight: 600,
                    marginBottom: "4px",
                  }}
                >
                  {link.label}
                </div>
                <div style={{ color: "#8B8579", fontSize: "12px" }}>{link.desc}</div>
              </Link>
            ))}
          </div>
        </div>
      </div>

      <style>{`
        .next-step-link:hover {
          border-color: #D4920A;
        }
      `}</style>
    </main>
  );
}
