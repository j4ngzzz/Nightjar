/**
 * Nightjar Verification Canvas — Landing Page
 *
 * Visual soul: "candlelight in a precision instrument shop — warm, specific, permanently correct"
 *
 * Hero: scanner CTA with GitHub URL input and recent public scans feed.
 * Below: proof-state spectrum legend.
 */

import { ScanCTASection } from "@/components/scanner/ScanCTASection";

export default function HomePage() {
  return (
    <main
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        minHeight: "100vh",
        backgroundColor: "#0D0B09",
      }}
    >
      {/* ------------------------------------------------------------------ */}
      {/* Hero: scanner input + recent scans                                  */}
      {/* ------------------------------------------------------------------ */}
      <ScanCTASection />

      {/* ------------------------------------------------------------------ */}
      {/* Proof-state spectrum legend                                          */}
      {/* ------------------------------------------------------------------ */}
      <section
        style={{
          width: "100%",
          maxWidth: "640px",
          padding: "0 24px 80px",
        }}
        aria-label="Proof state spectrum"
      >
        <p
          style={{
            marginBottom: "16px",
            textAlign: "center",
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "10px",
            color: "#3A2E10",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
        >
          Proof State Spectrum
        </p>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(5, 1fr)",
            gap: "8px",
          }}
        >
          {(
            [
              { label: "Pending", bg: "#1A1408", text: "#3A2E10", border: "#2A2315" },
              { label: "Running", bg: "#1A1408", text: "#D4920A", border: "#D4920A" },
              { label: "Schema", bg: "#1A1408", text: "#A87020", border: "#A87020" },
              { label: "PBT Pass", bg: "#1A1408", text: "#F5B93A", border: "#F5B93A" },
              { label: "Proven", bg: "#1A1408", text: "#FFD060", border: "#FFD060" },
            ] as Array<{ label: string; bg: string; text: string; border: string }>
          ).map(({ label, bg, text, border }) => (
            <div
              key={label}
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                gap: "8px",
                padding: "12px 8px",
                borderRadius: "6px",
                backgroundColor: bg,
                border: `1px solid ${border}`,
              }}
            >
              <div
                style={{
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  backgroundColor: text,
                }}
              />
              <span
                style={{
                  color: text,
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "9px",
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  textAlign: "center",
                }}
              >
                {label}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Footer                                                               */}
      {/* ------------------------------------------------------------------ */}
      <footer
        style={{
          width: "100%",
          padding: "24px",
          borderTop: "1px solid #1A1408",
          textAlign: "center",
        }}
      >
        <p
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "10px",
            color: "#2A2315",
            letterSpacing: "0.08em",
          }}
        >
          Nightjar · Contract-Anchored Regenerative Development
        </p>
      </footer>
    </main>
  );
}
