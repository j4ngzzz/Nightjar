/**
 * Nightjar Bug Reports Index — /bugs
 *
 * Lists all 48 confirmed bugs by severity.
 * Each bug links to its individual report page.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { bugs, type BugReport } from "@/lib/bugs-data";

export const metadata: Metadata = {
  title: "Bug Reports | Nightjar",
  description:
    "48 confirmed security and logic bugs found by Nightjar in popular Python packages including httpx, fastapi, fastmcp, litellm, pydantic, and more.",
};

const SEVERITY_ORDER: BugReport["severity"][] = ["HIGH", "MEDIUM", "LOW"];

const severityStyles: Record<
  BugReport["severity"],
  { label: string; color: string; border: string; bg: string }
> = {
  HIGH: {
    label: "HIGH",
    color: "#F85149",
    border: "#F85149",
    bg: "rgba(248, 81, 73, 0.08)",
  },
  MEDIUM: {
    label: "MED",
    color: "#D4920A",
    border: "#D4920A",
    bg: "rgba(212, 146, 10, 0.08)",
  },
  LOW: {
    label: "LOW",
    color: "#8B8579",
    border: "#2A2315",
    bg: "transparent",
  },
};

function SeverityBadge({ severity }: { severity: BugReport["severity"] }) {
  const s = severityStyles[severity];
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: "4px",
        border: `1px solid ${s.border}`,
        backgroundColor: s.bg,
        color: s.color,
        fontFamily: "var(--font-jetbrains-mono), monospace",
        fontSize: "10px",
        letterSpacing: "0.08em",
        fontWeight: 600,
        flexShrink: 0,
      }}
    >
      {s.label}
    </span>
  );
}

function BugRow({ bug }: { bug: BugReport }) {
  return (
    <Link
      href={`/bugs/${bug.slug}`}
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "16px",
        padding: "16px 20px",
        borderBottom: "1px solid #2A2315",
        textDecoration: "none",
        transition: "background-color 0.15s ease",
      }}
      className="bug-row"
    >
      <SeverityBadge severity={bug.severity} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: "10px",
            marginBottom: "4px",
            flexWrap: "wrap",
          }}
        >
          <span
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "11px",
              color: "#D4920A",
              letterSpacing: "0.04em",
            }}
          >
            {bug.package}
          </span>
          <span
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              color: "#3A2E10",
            }}
          >
            {bug.version}
          </span>
          {bug.cve && (
            <span
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "10px",
                color: "#F85149",
                border: "1px solid rgba(248, 81, 73, 0.3)",
                padding: "0 6px",
                borderRadius: "3px",
              }}
            >
              {bug.cve}
            </span>
          )}
        </div>
        <p
          style={{
            margin: 0,
            color: "#F0EBE3",
            fontSize: "14px",
            lineHeight: "1.4",
          }}
        >
          {bug.title}
        </p>
      </div>
      <span
        style={{
          color: "#3A2E10",
          fontSize: "16px",
          flexShrink: 0,
          alignSelf: "center",
        }}
        aria-hidden
      >
        →
      </span>
    </Link>
  );
}

export default function BugsIndexPage() {
  const counts = {
    HIGH: bugs.filter((b) => b.severity === "HIGH").length,
    MEDIUM: bugs.filter((b) => b.severity === "MEDIUM").length,
    LOW: bugs.filter((b) => b.severity === "LOW").length,
  };

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
          bugs
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
          Responsible Disclosure
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
          48 Confirmed Bugs
        </h1>
        <p style={{ color: "#8B8579", fontSize: "15px", maxWidth: "600px", lineHeight: "1.6" }}>
          Security and logic bugs found by Nightjar in popular Python packages. All 48 reproduced
          by direct execution. Verified 2026-03-28.
        </p>

        {/* Stats row */}
        <div
          style={{
            display: "flex",
            gap: "12px",
            marginTop: "24px",
            flexWrap: "wrap",
          }}
        >
          {(["HIGH", "MEDIUM", "LOW"] as const).map((sev) => {
            const s = severityStyles[sev];
            return (
              <div
                key={sev}
                style={{
                  padding: "12px 20px",
                  borderRadius: "8px",
                  border: `1px solid ${s.border}`,
                  backgroundColor: s.bg,
                  display: "flex",
                  flexDirection: "column",
                  gap: "4px",
                }}
              >
                <span
                  style={{
                    fontFamily: "var(--font-jetbrains-mono), monospace",
                    fontSize: "22px",
                    fontWeight: 600,
                    color: s.color,
                  }}
                >
                  {counts[sev]}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-jetbrains-mono), monospace",
                    fontSize: "10px",
                    color: s.color,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                  }}
                >
                  {sev}
                </span>
              </div>
            );
          })}
          <div
            style={{
              padding: "12px 20px",
              borderRadius: "8px",
              border: "1px solid #2A2315",
              backgroundColor: "#141109",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "22px",
                fontWeight: 600,
                color: "#F5B93A",
              }}
            >
              48/48
            </span>
            <span
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "10px",
                color: "#8B8579",
                letterSpacing: "0.08em",
              }}
            >
              CONFIRMED
            </span>
          </div>
        </div>
      </header>

      {/* Bug list grouped by severity */}
      <section style={{ maxWidth: "900px", margin: "0 auto", padding: "0 32px 80px" }}>
        {SEVERITY_ORDER.map((severity) => {
          const group = bugs.filter((b) => b.severity === severity);
          if (group.length === 0) return null;
          const s = severityStyles[severity];
          return (
            <div key={severity} style={{ marginBottom: "40px" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  padding: "10px 20px",
                  backgroundColor: "#141109",
                  borderTop: `2px solid ${s.border}`,
                  borderLeft: "1px solid #2A2315",
                  borderRight: "1px solid #2A2315",
                }}
              >
                <span
                  style={{
                    fontFamily: "var(--font-jetbrains-mono), monospace",
                    fontSize: "11px",
                    color: s.color,
                    fontWeight: 600,
                    letterSpacing: "0.1em",
                  }}
                >
                  {severity}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-jetbrains-mono), monospace",
                    fontSize: "11px",
                    color: "#3A2E10",
                  }}
                >
                  — {group.length} bugs
                </span>
              </div>
              <div
                style={{
                  border: "1px solid #2A2315",
                  borderTop: "none",
                  borderRadius: "0 0 8px 8px",
                  overflow: "hidden",
                }}
              >
                {group.map((bug) => (
                  <BugRow key={bug.slug} bug={bug} />
                ))}
              </div>
            </div>
          );
        })}
      </section>

      <style>{`
        .bug-row:hover {
          background-color: #141109;
        }
      `}</style>
    </main>
  );
}
