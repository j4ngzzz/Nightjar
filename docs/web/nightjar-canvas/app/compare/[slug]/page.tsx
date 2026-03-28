/**
 * Nightjar Individual Comparison — /compare/[slug]
 *
 * Head-to-head comparison page with feature grid and strengths.
 * Statically generated for all 7 comparisons at build time.
 */

import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getComparisonBySlug, comparisonSlugs } from "@/lib/comparisons-data";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return comparisonSlugs.map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const c = getComparisonBySlug(slug);
  if (!c) return { title: "Comparison Not Found | Nightjar" };
  return {
    title: `Nightjar vs. ${c.competitor} | Nightjar`,
    description: `${c.tagline}. ${c.summary.slice(0, 120)}`,
  };
}

function FeatureCheck({ value }: { value: string | boolean }) {
  if (value === true)
    return (
      <span style={{ color: "#F5B93A", fontWeight: 600, fontFamily: "var(--font-jetbrains-mono), monospace", fontSize: "12px" }}>
        YES
      </span>
    );
  if (value === false)
    return (
      <span style={{ color: "#3A2E10", fontFamily: "var(--font-jetbrains-mono), monospace", fontSize: "12px" }}>
        NO
      </span>
    );
  return (
    <span style={{ color: "#8B8579", fontFamily: "var(--font-jetbrains-mono), monospace", fontSize: "12px" }}>
      {value}
    </span>
  );
}

export default async function ComparisonPage({ params }: PageProps) {
  const { slug } = await params;
  const c = getComparisonBySlug(slug);
  if (!c) notFound();

  // Group features by category
  const categories = Array.from(new Set(c.features.map((f) => f.category)));

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
          href="/compare"
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "12px",
            color: "#8B8579",
            textDecoration: "none",
          }}
        >
          compare
        </Link>
        <span style={{ color: "#3A2E10" }}>/</span>
        <span
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "12px",
            color: "#D4920A",
          }}
        >
          {c.competitor.toLowerCase()}
        </span>
      </nav>

      <article style={{ maxWidth: "820px", margin: "0 auto", padding: "48px 32px 80px" }}>
        {/* Header */}
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
          Nightjar vs.
        </p>
        <h1
          style={{
            fontSize: "32px",
            fontWeight: 600,
            color: "#F5B93A",
            marginBottom: "8px",
            lineHeight: "1.1",
          }}
        >
          {c.competitor}
        </h1>
        <p
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "13px",
            color: "#8B8579",
            marginBottom: "24px",
          }}
        >
          {c.tagline}
        </p>

        {/* Summary */}
        <p
          style={{
            color: "#8B8579",
            fontSize: "15px",
            lineHeight: "1.7",
            marginBottom: "16px",
          }}
        >
          {c.summary}
        </p>

        {/* Verdict */}
        <blockquote
          style={{
            margin: "0 0 40px",
            padding: "16px 20px",
            borderLeft: "3px solid #D4920A",
            backgroundColor: "#141109",
            borderRadius: "0 8px 8px 0",
          }}
        >
          <p
            style={{
              color: "#F0EBE3",
              fontSize: "14px",
              lineHeight: "1.6",
              margin: 0,
              fontStyle: "italic",
            }}
          >
            {c.verdict}
          </p>
        </blockquote>

        {/* Strengths columns */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: "20px",
            marginBottom: "40px",
          }}
        >
          {/* Nightjar */}
          <div
            style={{
              padding: "20px",
              backgroundColor: "#141109",
              border: "1px solid #D4920A",
              borderRadius: "8px",
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "10px",
                color: "#D4920A",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                marginBottom: "12px",
                fontWeight: 600,
              }}
            >
              Nightjar strengths
            </div>
            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "8px" }}>
              {c.nightjarStrengths.map((s, i) => (
                <li
                  key={i}
                  style={{
                    color: "#F0EBE3",
                    fontSize: "13px",
                    lineHeight: "1.4",
                    paddingLeft: "16px",
                    position: "relative",
                  }}
                >
                  <span
                    style={{
                      position: "absolute",
                      left: 0,
                      color: "#D4920A",
                      fontFamily: "var(--font-jetbrains-mono), monospace",
                      fontSize: "12px",
                    }}
                  >
                    ·
                  </span>
                  {s}
                </li>
              ))}
            </ul>
          </div>

          {/* Competitor */}
          <div
            style={{
              padding: "20px",
              backgroundColor: "#141109",
              border: "1px solid #2A2315",
              borderRadius: "8px",
            }}
          >
            <div
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "10px",
                color: "#8B8579",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                marginBottom: "12px",
              }}
            >
              {c.competitor} strengths
            </div>
            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "8px" }}>
              {c.competitorStrengths.map((s, i) => (
                <li
                  key={i}
                  style={{
                    color: "#8B8579",
                    fontSize: "13px",
                    lineHeight: "1.4",
                    paddingLeft: "16px",
                    position: "relative",
                  }}
                >
                  <span
                    style={{
                      position: "absolute",
                      left: 0,
                      color: "#3A2E10",
                      fontFamily: "var(--font-jetbrains-mono), monospace",
                      fontSize: "12px",
                    }}
                  >
                    ·
                  </span>
                  {s}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Feature comparison table */}
        <h2
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "10px",
            color: "#3A2E10",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            marginBottom: "16px",
          }}
        >
          Feature Comparison
        </h2>

        <div
          style={{
            border: "1px solid #2A2315",
            borderRadius: "8px",
            overflow: "hidden",
            marginBottom: "40px",
          }}
        >
          {/* Table header */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 120px 120px",
              padding: "10px 20px",
              backgroundColor: "#141109",
              borderBottom: "1px solid #2A2315",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "10px",
                color: "#3A2E10",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              Feature
            </span>
            <span
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "10px",
                color: "#D4920A",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                textAlign: "center",
              }}
            >
              Nightjar
            </span>
            <span
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "10px",
                color: "#8B8579",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
                textAlign: "center",
              }}
            >
              {c.competitor}
            </span>
          </div>

          {categories.map((cat) => {
            const catFeatures = c.features.filter((f) => f.category === cat);
            return (
              <div key={cat}>
                {/* Category row */}
                <div
                  style={{
                    padding: "8px 20px",
                    backgroundColor: "#0F0D0A",
                    borderBottom: "1px solid #2A2315",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "var(--font-jetbrains-mono), monospace",
                      fontSize: "9px",
                      color: "#3A2E10",
                      letterSpacing: "0.12em",
                      textTransform: "uppercase",
                    }}
                  >
                    {cat}
                  </span>
                </div>
                {catFeatures.map((f, i) => (
                  <div
                    key={i}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "1fr 120px 120px",
                      padding: "12px 20px",
                      borderBottom: "1px solid #1A1408",
                      alignItems: "center",
                    }}
                  >
                    <span style={{ color: "#8B8579", fontSize: "13px" }}>{f.feature}</span>
                    <span style={{ textAlign: "center" }}>
                      <FeatureCheck value={f.nightjar} />
                    </span>
                    <span style={{ textAlign: "center" }}>
                      <FeatureCheck value={f.competitor} />
                    </span>
                  </div>
                ))}
              </div>
            );
          })}
        </div>

        {/* CTA */}
        <div
          style={{
            padding: "24px",
            backgroundColor: "#141109",
            border: "1px solid #D4920A",
            borderRadius: "8px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "16px",
            flexWrap: "wrap",
          }}
        >
          <div>
            <p style={{ color: "#F0EBE3", fontSize: "15px", fontWeight: 600, margin: "0 0 4px" }}>
              See what Nightjar finds in your code
            </p>
            <p style={{ color: "#8B8579", fontSize: "13px", margin: 0 }}>
              Free to try. AGPL open source.
            </p>
          </div>
          <Link
            href="/docs/quickstart"
            style={{
              display: "inline-block",
              padding: "10px 24px",
              backgroundColor: "#D4920A",
              color: "#0D0B09",
              borderRadius: "6px",
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "12px",
              fontWeight: 600,
              textDecoration: "none",
              letterSpacing: "0.04em",
              whiteSpace: "nowrap",
            }}
          >
            Get started →
          </Link>
        </div>

        {/* Footer nav */}
        <div
          style={{
            borderTop: "1px solid #2A2315",
            paddingTop: "24px",
            marginTop: "40px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <Link
            href="/compare"
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "12px",
              color: "#8B8579",
              textDecoration: "none",
            }}
          >
            ← All comparisons
          </Link>
        </div>
      </article>
    </main>
  );
}
