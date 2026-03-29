"use client";

/**
 * Nightjar Verification Canvas — Landing Page
 *
 * Visual soul: "candlelight in a precision instrument shop — warm, specific, permanently correct"
 *
 * Hero: scanner CTA with GitHub URL input and static CLI install block.
 * Below: proof-state spectrum legend.
 *
 * NOTE: The web scanner and /api/runs feed are not live yet (static export).
 * The scan form shows a CLI fallback on submit; the recent-scans section is
 * replaced with a static "Try the CLI" block — no API calls, no broken UI.
 */

import { useState, type FormEvent, type ChangeEvent } from "react";

// ---------------------------------------------------------------------------
// GitHub URL validation (same rules as ScannerInput)
// ---------------------------------------------------------------------------

const GITHUB_URL_RE =
  /^(?:https?:\/\/)?(?:www\.)?github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\/.*)?$/;

function isValidGithubUrl(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (GITHUB_URL_RE.test(trimmed)) return true;
  return /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(trimmed);
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HomePage() {
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const valid = isValidGithubUrl(value);

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    setValue(e.target.value);
    setSubmitted(false);
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setSubmitted(true);
  }

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
      {/* Hero: scanner input + CLI install block                             */}
      {/* ------------------------------------------------------------------ */}
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

        {/* Scanner input — visual shell preserved; submits to static message */}
        <div style={{ width: "100%", maxWidth: "640px", marginBottom: "40px" }}>
          <form
            onSubmit={handleSubmit}
            style={{ width: "100%", maxWidth: "640px" }}
            aria-label="Scan a GitHub repository"
          >
            {/* Input + button row */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "0",
                borderRadius: "8px",
                border: `1.5px solid ${focused ? "#D4920A" : "#4A3A1A"}`,
                backgroundColor: "#141109",
                boxShadow: focused ? "0 0 0 3px rgba(212,146,10,0.15)" : "none",
                transition: "border-color 150ms ease, box-shadow 150ms ease",
                overflow: "hidden",
              }}
            >
              {/* GitHub icon prefix */}
              <div
                style={{
                  padding: "0 12px",
                  display: "flex",
                  alignItems: "center",
                  flexShrink: 0,
                  userSelect: "none",
                }}
                aria-hidden="true"
              >
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ color: focused ? "#D4920A" : "#6B5A2A" }}
                >
                  <path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22" />
                </svg>
              </div>

              <input
                type="text"
                value={value}
                onChange={handleChange}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                placeholder="github.com/expressjs/express"
                spellCheck={false}
                autoComplete="off"
                autoCapitalize="none"
                aria-label="GitHub repository URL"
                style={{
                  flex: 1,
                  background: "transparent",
                  border: "none",
                  outline: "none",
                  padding: "14px 0",
                  fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
                  fontSize: "18px",
                  fontWeight: 400,
                  color: value ? "#F5F0E8" : "#4A3A1A",
                  caretColor: "#D4920A",
                  minWidth: 0,
                }}
              />

              {/* Scan button */}
              <button
                type="submit"
                disabled={!valid}
                aria-label="Start scan"
                style={{
                  flexShrink: 0,
                  padding: "14px 24px",
                  backgroundColor: valid ? "#D4920A" : "#2A1E08",
                  color: valid ? "#0D0B09" : "#4A3A1A",
                  border: "none",
                  cursor: valid ? "pointer" : "not-allowed",
                  fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
                  fontSize: "15px",
                  fontWeight: 600,
                  letterSpacing: "0.01em",
                  transition: "background-color 150ms ease, color 150ms ease",
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  whiteSpace: "nowrap",
                }}
              >
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{ color: valid ? "#0D0B09" : "#4A3A1A" }}
                  aria-hidden="true"
                >
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                Scan
              </button>
            </div>

            {/* On submit: show CLI fallback instead of hitting /api/scan */}
            {submitted ? (
              <p
                role="status"
                style={{
                  marginTop: "8px",
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "12px",
                  color: "#D4920A",
                  letterSpacing: "0.02em",
                }}
              >
                Web scanner coming soon — use the CLI:{" "}
                <span style={{ color: "#F5B93A" }}>
                  nightjar scan {value.trim()}
                </span>
              </p>
            ) : !value ? (
              <p
                style={{
                  marginTop: "8px",
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "11px",
                  color: "#4A3A1A",
                  letterSpacing: "0.04em",
                }}
              >
                Scoped to 10 files · Fast mode · Free
              </p>
            ) : null}
          </form>
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
            Get started
          </span>
          <div style={{ flex: 1, height: "1px", backgroundColor: "#1A1408" }} />
        </div>

        {/* Static CLI install block — replaces /api/runs feed */}
        <div
          style={{
            width: "100%",
            maxWidth: "640px",
            borderRadius: "8px",
            border: "1px solid #2A2315",
            backgroundColor: "#141109",
            padding: "24px",
          }}
        >
          <p
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              color: "#6B5A2A",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              margin: "0 0 16px",
            }}
          >
            Install · CLI
          </p>

          {/* Install command */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              padding: "12px 16px",
              borderRadius: "6px",
              backgroundColor: "#0D0B09",
              border: "1px solid #1A1408",
              marginBottom: "12px",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "13px",
                color: "#4A3A1A",
                userSelect: "none",
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
              pip install nightjar-verify
            </code>
          </div>

          {/* Scan command */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              padding: "12px 16px",
              borderRadius: "6px",
              backgroundColor: "#0D0B09",
              border: "1px solid #1A1408",
              marginBottom: "20px",
            }}
          >
            <span
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "13px",
                color: "#4A3A1A",
                userSelect: "none",
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
              nightjar scan github.com/your-org/your-app
            </code>
          </div>

          {/* Badge row */}
          <div
            style={{
              display: "flex",
              gap: "8px",
              flexWrap: "wrap",
            }}
          >
            {(
              [
                { label: "6-stage pipeline", color: "#D4920A" },
                { label: "Dafny formal proof", color: "#A87020" },
                { label: "Shareable certificate", color: "#6B5A2A" },
              ] as Array<{ label: string; color: string }>
            ).map(({ label, color }) => (
              <span
                key={label}
                style={{
                  padding: "3px 10px",
                  borderRadius: "4px",
                  border: `1px solid ${color}`,
                  backgroundColor: "#0D0B09",
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "10px",
                  color,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}
              >
                {label}
              </span>
            ))}
          </div>
        </div>
      </section>

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
