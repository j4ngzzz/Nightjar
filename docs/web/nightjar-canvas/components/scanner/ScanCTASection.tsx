"use client";

/**
 * ScanCTASection — Landing page hero with scanner input and recent scans.
 *
 * Layout:
 *   Large heading: "Formal verification for any Python codebase."
 *   Subheading: "Paste a GitHub URL. Watch six stages of mathematical proof run.
 *                Get a shareable certificate."
 *   [ScannerInput]
 *   [RecentScans below]
 *
 * All text #F5F0E8, background #0D0B09. No aurora background.
 */

import { ScannerInput } from "./ScannerInput";
import { RecentScans } from "./RecentScans";

export interface ScanCTASectionProps {
  /** Override API base for testing. */
  apiBase?: string;
}

export function ScanCTASection({ apiBase = "" }: ScanCTASectionProps) {
  return (
    <section
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        width: "100%",
        padding: "72px 24px 80px",
        backgroundColor: "#0D0B09",
      }}
      aria-labelledby="hero-heading"
    >
      {/* Nightjar logo mark */}
      <div style={{ marginBottom: "32px" }}>
        <svg
          width="48"
          height="48"
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-label="Nightjar logo"
        >
          <path
            d="M32 4 L56 18 L56 46 L32 60 L8 46 L8 18 Z"
            stroke="#D4920A"
            strokeWidth="1.5"
            fill="none"
          />
          <path
            d="M32 14 L48 23 L48 41 L32 50 L16 41 L16 23 Z"
            stroke="#F5B93A"
            strokeWidth="0.75"
            fill="none"
            opacity="0.4"
          />
          <circle cx="32" cy="32" r="8" fill="#D4920A" />
          <circle cx="32" cy="32" r="4" fill="#FFD060" />
        </svg>
      </div>

      {/* Main heading */}
      <h1
        id="hero-heading"
        style={{
          fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
          fontSize: "clamp(28px, 5vw, 48px)",
          fontWeight: 600,
          color: "#F5F0E8",
          letterSpacing: "-0.025em",
          lineHeight: 1.1,
          textAlign: "center",
          maxWidth: "720px",
          margin: "0 0 20px",
        }}
      >
        Formal verification for any Python codebase.
      </h1>

      {/* Subheading */}
      <p
        style={{
          fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
          fontSize: "clamp(15px, 2vw, 18px)",
          color: "#8B8579",
          lineHeight: 1.6,
          textAlign: "center",
          maxWidth: "560px",
          margin: "0 0 48px",
        }}
      >
        Paste a GitHub URL. Watch six stages of mathematical proof run.
        Get a shareable certificate.
      </p>

      {/* Scanner input */}
      <div style={{ width: "100%", maxWidth: "640px", marginBottom: "40px" }}>
        <ScannerInput apiBase={apiBase} />
      </div>

      {/* Divider with label */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          width: "100%",
          maxWidth: "640px",
          marginBottom: "16px",
        }}
      >
        <div style={{ flex: 1, height: "1px", backgroundColor: "#1A1408" }} />
        <span
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "10px",
            color: "#3A2E10",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            whiteSpace: "nowrap",
          }}
        >
          Recent scans
        </span>
        <div style={{ flex: 1, height: "1px", backgroundColor: "#1A1408" }} />
      </div>

      {/* Recent scans */}
      <RecentScans apiBase={apiBase} />
    </section>
  );
}
