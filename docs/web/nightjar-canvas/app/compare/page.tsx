/**
 * Nightjar Comparisons Index — /compare
 *
 * Lists all 7 head-to-head comparisons.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { comparisons } from "@/lib/comparisons-data";

export const metadata: Metadata = {
  title: "Nightjar vs. Alternatives | Nightjar",
  description:
    "How Nightjar compares to CrossHair, Semgrep, Bandit, Snyk, mypy+pytest, GitHub Copilot, and DeepEval. Formal verification vs. pattern matching vs. testing.",
};

export default function CompareIndexPage() {
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
          compare
        </span>
      </nav>

      {/* Header */}
      <header style={{ padding: "48px 32px 32px", maxWidth: "900px", margin: "0 auto" }}>
        <p
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "10px",
            color: "#3A2E10",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            marginBottom: "12px",
          }}
        >
          Tool Comparisons
        </p>
        <h1
          style={{
            fontSize: "28px",
            fontWeight: 600,
            color: "#F0EBE3",
            marginBottom: "12px",
            lineHeight: "1.2",
          }}
        >
          Nightjar vs. Alternatives
        </h1>
        <p style={{ color: "#8B8579", fontSize: "15px", maxWidth: "600px", lineHeight: "1.6" }}>
          Nightjar is not a linter, not a test framework, and not a vulnerability scanner. It is
          a formal verification layer. Here is how it differs from tools you already know.
        </p>
      </header>

      {/* Comparison cards */}
      <section
        style={{
          maxWidth: "900px",
          margin: "0 auto",
          padding: "0 32px 80px",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))",
          gap: "16px",
        }}
      >
        {comparisons.map((c) => (
          <Link
            key={c.slug}
            href={`/compare/${c.slug}`}
            style={{
              display: "block",
              padding: "24px",
              backgroundColor: "#141109",
              border: "1px solid #2A2315",
              borderRadius: "8px",
              textDecoration: "none",
              transition: "border-color 0.15s ease",
            }}
            className="compare-card"
          >
            <div
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "10px",
                color: "#3A2E10",
                letterSpacing: "0.08em",
                marginBottom: "10px",
                textTransform: "uppercase",
              }}
            >
              nightjar vs.
            </div>
            <h2
              style={{
                fontSize: "18px",
                fontWeight: 600,
                color: "#F5B93A",
                marginBottom: "8px",
              }}
            >
              {c.competitor}
            </h2>
            <p
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "11px",
                color: "#8B8579",
                marginBottom: "12px",
                letterSpacing: "0.04em",
              }}
            >
              {c.tagline}
            </p>
            <p
              style={{
                color: "#8B8579",
                fontSize: "13px",
                lineHeight: "1.5",
                margin: "0 0 16px",
                display: "-webkit-box",
                WebkitLineClamp: 3,
                WebkitBoxOrient: "vertical",
                overflow: "hidden",
              }}
            >
              {c.summary}
            </p>
            <div
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "11px",
                color: "#D4920A",
              }}
            >
              Read comparison →
            </div>
          </Link>
        ))}
      </section>

      <style>{`
        .compare-card:hover {
          border-color: #D4920A;
        }
      `}</style>
    </main>
  );
}
