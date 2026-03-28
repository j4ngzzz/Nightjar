/**
 * Nightjar Verification Canvas — Landing Page
 * Placeholder: demonstrates the amber design system is working.
 *
 * Visual soul: "candlelight in a precision instrument shop — warm, specific, permanently correct"
 */

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 py-16">
      {/* Logo + wordmark */}
      <div className="mb-12 flex flex-col items-center gap-4">
        {/* Nightjar hexagonal logo */}
        <svg
          width="64"
          height="64"
          viewBox="0 0 64 64"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          aria-label="Nightjar logo"
        >
          {/* Hexagonal frame */}
          <path
            d="M32 4 L56 18 L56 46 L32 60 L8 46 L8 18 Z"
            stroke="#D4920A"
            strokeWidth="1.5"
            fill="none"
          />
          {/* Inner ring */}
          <path
            d="M32 14 L48 23 L48 41 L32 50 L16 41 L16 23 Z"
            stroke="#F5B93A"
            strokeWidth="0.75"
            fill="none"
            opacity="0.5"
          />
          {/* Amber core */}
          <circle cx="32" cy="32" r="8" fill="#D4920A" />
          <circle cx="32" cy="32" r="4" fill="#FFD060" />
        </svg>

        <h1
          style={{
            fontFamily: "var(--font-geist-sans)",
            fontWeight: 600,
            fontSize: "2rem",
            color: "#F0EBE3",
            letterSpacing: "-0.02em",
            lineHeight: 1,
          }}
        >
          Nightjar
        </h1>
        <p
          style={{
            fontFamily: "var(--font-jetbrains-mono)",
            fontSize: "0.75rem",
            color: "#D4920A",
            letterSpacing: "0.12em",
            textTransform: "uppercase",
          }}
        >
          Verification Canvas
        </p>
      </div>

      {/* Tagline */}
      <p
        className="mb-16 max-w-md text-center"
        style={{ color: "#8B8579", fontSize: "1rem", lineHeight: 1.6 }}
      >
        Not just tested —{" "}
        <span style={{ color: "#F5B93A" }}>proven</span>.
        Mathematical certainty for every commit.
      </p>

      {/* Amber palette swatch — design system validation */}
      <div className="mb-12 w-full max-w-2xl">
        <p
          className="mb-4 text-center text-xs uppercase tracking-widest"
          style={{ color: "#8B8579", fontFamily: "var(--font-jetbrains-mono)" }}
        >
          Proof State Spectrum
        </p>
        <div className="grid grid-cols-5 gap-2">
          {[
            { label: "Pending", bg: "#3A2E10", text: "#8B8579" },
            { label: "Running", bg: "#1A1408", text: "#D4920A", border: "#D4920A" },
            { label: "Evaluated", bg: "#2A1E08", text: "#A87020", border: "#A87020" },
            { label: "Verified", bg: "#2A1E08", text: "#F5B93A", border: "#F5B93A" },
            { label: "PROVEN", bg: "#1A1408", text: "#FFD060", border: "#FFD060" },
          ].map(({ label, bg, text, border }) => (
            <div
              key={label}
              className="flex flex-col items-center gap-2 rounded p-3"
              style={{
                backgroundColor: bg,
                border: `1px solid ${border ?? "#2A2315"}`,
              }}
            >
              <div
                className="h-3 w-3 rounded-full"
                style={{ backgroundColor: text }}
              />
              <span
                className="text-center"
                style={{
                  color: text,
                  fontFamily: "var(--font-jetbrains-mono)",
                  fontSize: "0.65rem",
                  letterSpacing: "0.05em",
                }}
              >
                {label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Design token validation cards */}
      <div className="grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3">
        {/* Background tokens */}
        <div
          className="rounded p-4"
          style={{
            backgroundColor: "var(--color-bg-raised)",
            border: "1px solid var(--color-border-inactive)",
          }}
        >
          <p
            className="mb-1 text-xs uppercase tracking-wider"
            style={{ color: "#8B8579", fontFamily: "var(--font-jetbrains-mono)" }}
          >
            Surface
          </p>
          <p
            className="text-sm font-semibold"
            style={{ color: "var(--color-text-primary)" }}
          >
            #141109
          </p>
          <p
            className="mt-1 text-xs"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Warm near-black card
          </p>
        </div>

        {/* Amber token */}
        <div
          className="rounded p-4"
          style={{
            backgroundColor: "var(--color-bg-raised)",
            border: "1px solid var(--color-border-active)",
          }}
        >
          <p
            className="mb-1 text-xs uppercase tracking-wider"
            style={{ color: "#8B8579", fontFamily: "var(--font-jetbrains-mono)" }}
          >
            Proof Amber
          </p>
          <p
            className="text-sm font-semibold"
            style={{ color: "var(--color-amber)" }}
          >
            #D4920A
          </p>
          <p
            className="mt-1 text-xs"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Verification in progress
          </p>
        </div>

        {/* Peak token */}
        <div
          className="rounded p-4"
          style={{
            backgroundColor: "var(--color-bg-raised)",
            border: "1px solid var(--color-peak)",
            boxShadow: "0 0 12px rgba(255, 208, 96, 0.15)",
          }}
        >
          <p
            className="mb-1 text-xs uppercase tracking-wider"
            style={{ color: "#8B8579", fontFamily: "var(--font-jetbrains-mono)" }}
          >
            Peak
          </p>
          <p
            className="text-sm font-semibold"
            style={{ color: "var(--color-peak)" }}
          >
            #FFD060
          </p>
          <p
            className="mt-1 text-xs"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Mathematically proven
          </p>
        </div>
      </div>

      {/* Canvas coming soon note */}
      <div className="mt-16 text-center">
        <p
          className="text-xs"
          style={{
            color: "#6E6860",
            fontFamily: "var(--font-jetbrains-mono)",
            letterSpacing: "0.08em",
          }}
        >
          Verification Canvas — Phase 6 · Building...
        </p>
      </div>
    </main>
  );
}
