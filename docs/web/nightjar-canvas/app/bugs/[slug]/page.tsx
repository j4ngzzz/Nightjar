/**
 * Nightjar Individual Bug Report — /bugs/[slug]
 *
 * Individual bug report page with full reproduction details.
 * Statically generated for all 48 bugs at build time.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getBugBySlug, bugSlugs, type BugReport } from "@/lib/bugs-data";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return bugSlugs.map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const bug = getBugBySlug(slug);
  if (!bug) return { title: "Bug Not Found | Nightjar" };
  return {
    title: `${bug.title} | Nightjar Bug Reports`,
    description: `${bug.severity} severity bug in ${bug.package} ${bug.version}. ${bug.description.slice(0, 120)}`,
  };
}

const severityConfig: Record<
  BugReport["severity"],
  { color: string; border: string; bg: string; label: string }
> = {
  HIGH: { color: "#F85149", border: "#F85149", bg: "rgba(248, 81, 73, 0.08)", label: "HIGH SEVERITY" },
  MEDIUM: { color: "#D4920A", border: "#D4920A", bg: "rgba(212, 146, 10, 0.08)", label: "MEDIUM SEVERITY" },
  LOW: { color: "#8B8579", border: "#2A2315", bg: "transparent", label: "LOW SEVERITY" },
};

const statusConfig: Record<
  BugReport["status"],
  { color: string; label: string }
> = {
  confirmed: { color: "#D4920A", label: "CONFIRMED" },
  disclosed: { color: "#F5B93A", label: "DISCLOSED" },
  fixed: { color: "#3FB950", label: "FIXED" },
};

function CodeBlock({ code }: { code: string }) {
  return (
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
  );
}

export default async function BugReportPage({ params }: PageProps) {
  const { slug } = await params;
  const bug = getBugBySlug(slug);
  if (!bug) notFound();

  const sev = severityConfig[bug.severity];
  const status = statusConfig[bug.status];

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
        <Link
          href="/bugs"
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "12px",
            color: "#8B8579",
            textDecoration: "none",
          }}
        >
          bugs
        </Link>
        <span style={{ color: "#3A2E10" }}>/</span>
        <span
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "12px",
            color: "#D4920A",
            wordBreak: "break-all",
          }}
        >
          {slug}
        </span>
      </nav>

      <article style={{ maxWidth: "760px", margin: "0 auto", padding: "48px 32px 80px" }}>
        {/* Severity + status badges */}
        <div style={{ display: "flex", gap: "10px", marginBottom: "20px", flexWrap: "wrap" }}>
          <span
            style={{
              display: "inline-block",
              padding: "4px 12px",
              borderRadius: "4px",
              border: `1px solid ${sev.border}`,
              backgroundColor: sev.bg,
              color: sev.color,
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              letterSpacing: "0.1em",
              fontWeight: 600,
            }}
          >
            {sev.label}
          </span>
          <span
            style={{
              display: "inline-block",
              padding: "4px 12px",
              borderRadius: "4px",
              border: "1px solid #2A2315",
              backgroundColor: "#141109",
              color: status.color,
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              letterSpacing: "0.1em",
            }}
          >
            {status.label}
          </span>
          {bug.cve && (
            <span
              style={{
                display: "inline-block",
                padding: "4px 12px",
                borderRadius: "4px",
                border: "1px solid rgba(248, 81, 73, 0.4)",
                backgroundColor: "rgba(248, 81, 73, 0.06)",
                color: "#F85149",
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "10px",
                letterSpacing: "0.1em",
              }}
            >
              {bug.cve}
            </span>
          )}
        </div>

        {/* Title */}
        <h1
          style={{
            fontSize: "24px",
            fontWeight: 600,
            color: "#F0EBE3",
            lineHeight: "1.3",
            marginBottom: "24px",
          }}
        >
          {bug.title}
        </h1>

        {/* Package meta */}
        <div
          style={{
            display: "flex",
            gap: "24px",
            padding: "16px 20px",
            backgroundColor: "#141109",
            border: "1px solid #2A2315",
            borderRadius: "8px",
            marginBottom: "32px",
            flexWrap: "wrap",
          }}
        >
          {[
            { label: "Package", value: bug.package },
            { label: "Version", value: bug.version },
            { label: "Verified", value: "2026-03-28" },
          ].map(({ label, value }) => (
            <div key={label}>
              <div
                style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "9px",
                  color: "#3A2E10",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  marginBottom: "4px",
                }}
              >
                {label}
              </div>
              <div
                style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "13px",
                  color: "#D4920A",
                }}
              >
                {value}
              </div>
            </div>
          ))}
        </div>

        {/* Description */}
        <section style={{ marginBottom: "32px" }}>
          <h2
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              color: "#3A2E10",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              marginBottom: "12px",
            }}
          >
            Description
          </h2>
          <p
            style={{
              color: "#8B8579",
              fontSize: "15px",
              lineHeight: "1.7",
              margin: 0,
            }}
          >
            {bug.description}
          </p>
        </section>

        {/* Reproduction */}
        <section style={{ marginBottom: "40px" }}>
          <h2
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              color: "#3A2E10",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              marginBottom: "12px",
            }}
          >
            Reproduction
          </h2>
          <CodeBlock code={bug.reproduction} />
        </section>

        {/* Footer nav */}
        <div
          style={{
            borderTop: "1px solid #2A2315",
            paddingTop: "24px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "16px",
            flexWrap: "wrap",
          }}
        >
          <Link
            href="/bugs"
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "12px",
              color: "#8B8579",
              textDecoration: "none",
            }}
          >
            ← All bugs
          </Link>
          <Link
            href="/docs/quickstart"
            style={{
              display: "inline-block",
              padding: "8px 20px",
              backgroundColor: "#D4920A",
              color: "#0D0B09",
              borderRadius: "6px",
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "12px",
              fontWeight: 600,
              textDecoration: "none",
              letterSpacing: "0.04em",
            }}
          >
            Scan your code →
          </Link>
        </div>
      </article>
    </main>
  );
}
