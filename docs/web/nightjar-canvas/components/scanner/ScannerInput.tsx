"use client";

/**
 * ScannerInput — GitHub URL input + Scan button for the landing page hero.
 *
 * Validates GitHub URL format before enabling the Scan button.
 * On submit, POSTs to /api/scan and redirects to /run/{run_id}.
 *
 * Design tokens: amber palette only — no green, no purple.
 * Text: Geist 18px, #F5F0E8 on #141109. Amber border #4A3A1A, focus #D4920A.
 */

import { useState, useRef, type FormEvent, type ChangeEvent } from "react";
import { useRouter } from "next/navigation";

// ---------------------------------------------------------------------------
// GitHub URL validation
// ---------------------------------------------------------------------------

const GITHUB_URL_RE =
  /^(?:https?:\/\/)?(?:www\.)?github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\/.*)?$/;

function isValidGithubUrl(value: string): boolean {
  const trimmed = value.trim();
  if (!trimmed) return false;
  // Accept bare "owner/repo" form as well as full URLs
  if (GITHUB_URL_RE.test(trimmed)) return true;
  const bareRe = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;
  return bareRe.test(trimmed);
}

function normaliseUrl(value: string): string {
  const trimmed = value.trim();
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  if (trimmed.startsWith("github.com/")) return `https://${trimmed}`;
  // bare owner/repo
  if (/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(trimmed)) {
    return `https://github.com/${trimmed}`;
  }
  return trimmed;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface ScannerInputProps {
  /** Called with the created run_id after a successful POST /api/scan. */
  onScanStarted?: (runId: string) => void;
  /** Override API base for testing. */
  apiBase?: string;
}

export function ScannerInput({
  onScanStarted,
  apiBase = "",
}: ScannerInputProps) {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [focused, setFocused] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const valid = isValidGithubUrl(value);

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    setValue(e.target.value);
    setError(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!valid || loading) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${apiBase}/api/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ github_url: normaliseUrl(value) }),
      });

      if (res.status === 429) {
        setError("Rate limit reached — max 5 scans per day. Try again tomorrow.");
        return;
      }

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setError(
          (body as { detail?: string }).detail ??
            `Server error (${res.status}). Please try again.`
        );
        return;
      }

      const data = (await res.json()) as { run_id: string; url?: string };
      onScanStarted?.(data.run_id);
      router.push(`/run/${data.run_id}`);
    } catch {
      setError("Could not connect to the Nightjar server. Is it running?");
    } finally {
      setLoading(false);
    }
  }

  return (
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
        {/* Lock icon prefix */}
        <div
          style={{
            padding: "0 12px",
            display: "flex",
            alignItems: "center",
            color: "#4A3A1A",
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
          ref={inputRef}
          type="text"
          value={value}
          onChange={handleChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="github.com/expressjs/express"
          disabled={loading}
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
          disabled={!valid || loading}
          aria-label="Start scan"
          style={{
            flexShrink: 0,
            padding: "14px 24px",
            backgroundColor: valid && !loading ? "#D4920A" : "#2A1E08",
            color: valid && !loading ? "#0D0B09" : "#4A3A1A",
            border: "none",
            cursor: valid && !loading ? "pointer" : "not-allowed",
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
          {loading ? (
            <>
              <SpinnerIcon />
              Scanning…
            </>
          ) : (
            <>
              <ScanIcon active={valid} />
              Scan
            </>
          )}
        </button>
      </div>

      {/* Error message */}
      {error && (
        <p
          role="alert"
          style={{
            marginTop: "8px",
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "12px",
            color: "#F85149",
            letterSpacing: "0.02em",
          }}
        >
          {error}
        </p>
      )}

      {/* Subtle hint when no value */}
      {!value && !error && (
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
      )}
    </form>
  );
}

// ---------------------------------------------------------------------------
// Icon sub-components
// ---------------------------------------------------------------------------

function ScanIcon({ active }: { active: boolean }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ color: active ? "#0D0B09" : "#4A3A1A" }}
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="#0D0B09"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={{ animation: "spin 0.8s linear infinite" }}
    >
      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  );
}
