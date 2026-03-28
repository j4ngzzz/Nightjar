/**
 * Nightjar Pricing — /pricing
 *
 * Three tiers: Open Source (AGPL free), Teams ($2,400/yr), Enterprise ($12,000/yr).
 * Feature comparison grid + AGPL FAQ section.
 */

import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Pricing | Nightjar",
  description:
    "Nightjar is free and open source under AGPL. Teams pricing at $2,400/yr. Enterprise at $12,000/yr. Formal verification for every budget.",
};

interface PricingTier {
  id: string;
  name: string;
  price: string;
  period: string;
  description: string;
  cta: string;
  ctaHref: string;
  highlight: boolean;
  features: string[];
}

const tiers: PricingTier[] = [
  {
    id: "oss",
    name: "Open Source",
    price: "$0",
    period: "forever",
    description:
      "The full Nightjar verification pipeline, free for individuals, startups, and open source projects under AGPL.",
    cta: "Get started",
    ctaHref: "/docs/quickstart",
    highlight: false,
    features: [
      "Full 6-stage verification pipeline",
      "Dafny formal proof (Stage 4)",
      "Property-based testing (Stage 3)",
      "Schema validation (Stage 2)",
      "CEGIS repair loop",
      "Immune system trace mining",
      "MCP server (3 tools)",
      "Textual TUI dashboard",
      "All CLI commands",
      "Community support (GitHub Issues)",
      "AGPL-3.0 license",
    ],
  },
  {
    id: "teams",
    name: "Teams",
    price: "$2,400",
    period: "per year",
    description:
      "Built for engineering teams that ship AI-generated code to production. Adds SLA, private audit logs, and priority support.",
    cta: "Start free trial",
    ctaHref: "mailto:team@nightjarcode.dev?subject=Teams%20Trial",
    highlight: true,
    features: [
      "Everything in Open Source",
      "Commercial license (no AGPL copyleft)",
      "Private audit log retention (90 days)",
      "Team dashboard with proof certificates",
      "GitHub Actions integration (official)",
      "Slack / Discord alerts on verification failure",
      "Priority support (8-hour response)",
      "Unlimited modules and specs",
      "Up to 20 seats",
      "SSO via Google / GitHub",
      "Monthly verification reports",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "$12,000",
    period: "per year",
    description:
      "For organisations with compliance requirements, custom deployment needs, or large engineering teams.",
    cta: "Contact us",
    ctaHref: "mailto:enterprise@nightjarcode.dev?subject=Enterprise%20Inquiry",
    highlight: false,
    features: [
      "Everything in Teams",
      "Unlimited seats",
      "On-premise or VPC deployment",
      "Custom Dafny rule libraries",
      "SAML / SCIM provisioning",
      "SOC 2 Type II report available",
      "Audit log export (SIEM integration)",
      "SLA: 4-hour critical response",
      "Dedicated customer success manager",
      "Custom integrations (Jira, ServiceNow)",
      "Annual security review",
    ],
  },
];

const featureMatrix = [
  { feature: "Verification pipeline (all 6 stages)", oss: true, teams: true, enterprise: true },
  { feature: "Dafny formal proof", oss: true, teams: true, enterprise: true },
  { feature: "CEGIS repair loop", oss: true, teams: true, enterprise: true },
  { feature: "Commercial license", oss: false, teams: true, enterprise: true },
  { feature: "Team dashboard", oss: false, teams: true, enterprise: true },
  { feature: "Private audit logs", oss: false, teams: "90 days", enterprise: "Unlimited" },
  { feature: "GitHub Actions (official)", oss: false, teams: true, enterprise: true },
  { feature: "Priority support", oss: false, teams: "8hr", enterprise: "4hr" },
  { feature: "SSO (Google / GitHub)", oss: false, teams: true, enterprise: true },
  { feature: "SAML / SCIM", oss: false, teams: false, enterprise: true },
  { feature: "On-premise deployment", oss: false, teams: false, enterprise: true },
  { feature: "SOC 2 Type II", oss: false, teams: false, enterprise: true },
  { feature: "Seats", oss: "Unlimited*", teams: "Up to 20", enterprise: "Unlimited" },
];

const agplFAQ = [
  {
    q: "What does AGPL mean for my code?",
    a: "AGPL-3.0 requires that if you distribute software that incorporates Nightjar — or run it as a network service — you must make your application's source code available under AGPL. If you use Nightjar only internally as a development tool (running it locally, in CI, on your own servers), AGPL does not require you to open-source your product code.",
  },
  {
    q: "Do I need a commercial license?",
    a: "You need a commercial license (Teams or Enterprise) if: (1) you want to distribute a product that includes or links Nightjar, (2) you offer Nightjar as a service to others, or (3) your organisation's legal policy prohibits AGPL dependencies. Most engineering teams using Nightjar internally as a verification tool do not need a commercial license.",
  },
  {
    q: "Can I use the free version in a commercial project?",
    a: "Yes. Using Nightjar as a development and verification tool in a commercial project is permitted under AGPL without needing a paid license, as long as you do not distribute Nightjar itself or use it to provide a service to third parties. When in doubt, consult your legal team or email us.",
  },
  {
    q: "What happens if I contribute to Nightjar?",
    a: "Contributions to the AGPL core are welcome. Contributors retain copyright and license their contributions under AGPL. The codebase uses a contributor license agreement (CLA) to allow us to offer the commercial license alongside the open-source one.",
  },
];

function FeatureValue({ value }: { value: string | boolean }) {
  if (value === true)
    return (
      <span
        style={{
          color: "#F5B93A",
          fontFamily: "var(--font-jetbrains-mono), monospace",
          fontSize: "12px",
          fontWeight: 600,
        }}
      >
        YES
      </span>
    );
  if (value === false)
    return (
      <span
        style={{
          color: "#3A2E10",
          fontFamily: "var(--font-jetbrains-mono), monospace",
          fontSize: "12px",
        }}
      >
        —
      </span>
    );
  return (
    <span
      style={{
        color: "#8B8579",
        fontFamily: "var(--font-jetbrains-mono), monospace",
        fontSize: "11px",
      }}
    >
      {value}
    </span>
  );
}

export default function PricingPage() {
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
          pricing
        </span>
      </nav>

      {/* Header */}
      <header style={{ padding: "56px 32px 40px", textAlign: "center" }}>
        <h1
          style={{
            fontSize: "36px",
            fontWeight: 600,
            color: "#F0EBE3",
            marginBottom: "12px",
            lineHeight: "1.15",
          }}
        >
          Mathematically proven code.
          <br />
          <span style={{ color: "#D4920A" }}>Free to start.</span>
        </h1>
        <p
          style={{
            color: "#8B8579",
            fontSize: "16px",
            lineHeight: "1.6",
            maxWidth: "480px",
            margin: "0 auto",
          }}
        >
          The full verification pipeline is open source under AGPL. Commercial licenses available
          for teams that need a clean IP boundary.
        </p>
      </header>

      {/* Pricing cards */}
      <section
        style={{
          maxWidth: "1000px",
          margin: "0 auto",
          padding: "0 32px 60px",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          gap: "20px",
          alignItems: "start",
        }}
      >
        {tiers.map((tier) => (
          <div
            key={tier.id}
            style={{
              backgroundColor: "#141109",
              border: `1px solid ${tier.highlight ? "#D4920A" : "#2A2315"}`,
              borderRadius: "12px",
              overflow: "hidden",
              boxShadow: tier.highlight ? "0 0 24px rgba(212, 146, 10, 0.15)" : "none",
              position: "relative",
            }}
          >
            {tier.highlight && (
              <div
                style={{
                  backgroundColor: "#D4920A",
                  padding: "4px 0",
                  textAlign: "center",
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "10px",
                  color: "#0D0B09",
                  fontWeight: 600,
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                }}
              >
                Most popular
              </div>
            )}
            <div style={{ padding: "28px 24px 24px" }}>
              {/* Tier name */}
              <div
                style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "11px",
                  color: tier.highlight ? "#D4920A" : "#8B8579",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  marginBottom: "10px",
                }}
              >
                {tier.name}
              </div>

              {/* Price */}
              <div style={{ display: "flex", alignItems: "baseline", gap: "6px", marginBottom: "8px" }}>
                <span
                  style={{
                    fontFamily: "var(--font-jetbrains-mono), monospace",
                    fontSize: "36px",
                    fontWeight: 600,
                    color: "#F0EBE3",
                    lineHeight: 1,
                  }}
                >
                  {tier.price}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-jetbrains-mono), monospace",
                    fontSize: "12px",
                    color: "#8B8579",
                  }}
                >
                  / {tier.period}
                </span>
              </div>

              <p
                style={{
                  color: "#8B8579",
                  fontSize: "13px",
                  lineHeight: "1.5",
                  marginBottom: "20px",
                  minHeight: "54px",
                }}
              >
                {tier.description}
              </p>

              {/* CTA button */}
              <Link
                href={tier.ctaHref}
                style={{
                  display: "block",
                  padding: "10px 20px",
                  backgroundColor: tier.highlight ? "#D4920A" : "transparent",
                  color: tier.highlight ? "#0D0B09" : "#D4920A",
                  border: `1px solid #D4920A`,
                  borderRadius: "6px",
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "12px",
                  fontWeight: 600,
                  textDecoration: "none",
                  textAlign: "center",
                  letterSpacing: "0.04em",
                  marginBottom: "24px",
                  transition: "opacity 0.15s ease",
                }}
              >
                {tier.cta}
              </Link>

              {/* Features list */}
              <ul
                style={{
                  margin: 0,
                  padding: 0,
                  listStyle: "none",
                  display: "flex",
                  flexDirection: "column",
                  gap: "8px",
                }}
              >
                {tier.features.map((feature, i) => (
                  <li
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "8px",
                      fontSize: "13px",
                      color: "#8B8579",
                      lineHeight: "1.4",
                    }}
                  >
                    <span
                      style={{
                        color: "#D4920A",
                        fontFamily: "var(--font-jetbrains-mono), monospace",
                        fontSize: "12px",
                        flexShrink: 0,
                        marginTop: "1px",
                      }}
                    >
                      ·
                    </span>
                    {feature}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </section>

      {/* Feature comparison matrix */}
      <section
        style={{
          maxWidth: "900px",
          margin: "0 auto",
          padding: "0 32px 60px",
        }}
      >
        <h2
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "10px",
            color: "#3A2E10",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            marginBottom: "16px",
            textAlign: "center",
          }}
        >
          Full Feature Comparison
        </h2>

        <div
          style={{
            border: "1px solid #2A2315",
            borderRadius: "8px",
            overflow: "hidden",
          }}
        >
          {/* Table header */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "2fr 1fr 1fr 1fr",
              padding: "12px 20px",
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
            {["Open Source", "Teams", "Enterprise"].map((col) => (
              <span
                key={col}
                style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "10px",
                  color: col === "Teams" ? "#D4920A" : "#8B8579",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  textAlign: "center",
                }}
              >
                {col}
              </span>
            ))}
          </div>

          {featureMatrix.map((row, i) => (
            <div
              key={i}
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 1fr 1fr",
                padding: "11px 20px",
                borderBottom: "1px solid #1A1408",
                alignItems: "center",
              }}
            >
              <span style={{ color: "#8B8579", fontSize: "13px" }}>{row.feature}</span>
              <span style={{ textAlign: "center" }}>
                <FeatureValue value={row.oss} />
              </span>
              <span style={{ textAlign: "center" }}>
                <FeatureValue value={row.teams} />
              </span>
              <span style={{ textAlign: "center" }}>
                <FeatureValue value={row.enterprise} />
              </span>
            </div>
          ))}
        </div>
        <p
          style={{
            marginTop: "8px",
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "10px",
            color: "#3A2E10",
          }}
        >
          * Unlimited seats for internal use. See AGPL FAQ below.
        </p>
      </section>

      {/* AGPL FAQ */}
      <section
        style={{
          maxWidth: "760px",
          margin: "0 auto",
          padding: "0 32px 80px",
        }}
      >
        <h2
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "10px",
            color: "#3A2E10",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            marginBottom: "24px",
          }}
        >
          AGPL License FAQ
        </h2>

        <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
          {agplFAQ.map((item, i) => (
            <div
              key={i}
              style={{
                padding: "24px 0",
                borderBottom: "1px solid #2A2315",
              }}
            >
              <h3
                style={{
                  fontSize: "15px",
                  fontWeight: 600,
                  color: "#F0EBE3",
                  marginBottom: "10px",
                  lineHeight: "1.3",
                }}
              >
                {item.q}
              </h3>
              <p
                style={{
                  color: "#8B8579",
                  fontSize: "14px",
                  lineHeight: "1.7",
                  margin: 0,
                }}
              >
                {item.a}
              </p>
            </div>
          ))}
        </div>

        {/* Enterprise contact CTA */}
        <div
          style={{
            marginTop: "40px",
            padding: "28px",
            backgroundColor: "#141109",
            border: "1px solid #2A2315",
            borderRadius: "8px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "20px",
            flexWrap: "wrap",
          }}
        >
          <div>
            <p
              style={{
                color: "#F0EBE3",
                fontSize: "15px",
                fontWeight: 600,
                margin: "0 0 4px",
              }}
            >
              Need a custom quote or evaluation?
            </p>
            <p style={{ color: "#8B8579", fontSize: "13px", margin: 0 }}>
              We offer 30-day enterprise evaluations with full support.
            </p>
          </div>
          <a
            href="mailto:enterprise@nightjarcode.dev?subject=Enterprise%20Evaluation"
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
            Contact enterprise →
          </a>
        </div>
      </section>
    </main>
  );
}
