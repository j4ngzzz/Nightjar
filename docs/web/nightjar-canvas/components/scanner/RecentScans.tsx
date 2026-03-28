"use client";

/**
 * RecentScans — Live feed of public verification runs.
 *
 * Polls GET /api/runs?public=true&limit=10 every 30 seconds.
 * New entries animate with a crystallization snap (150ms).
 *
 * Trust score badge colours follow the amber proof-state spectrum:
 *   UNVERIFIED       → dim (#4A3A1A text, #1A1408 bg)
 *   SCHEMA_VERIFIED  → evaluated (#A87020)
 *   PROPERTY_VERIFIED → pbt pass (#F5B93A)
 *   FORMALLY_VERIFIED → proven (#FFD060)
 */

import { useState, useEffect, useRef } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PublicRun {
  run_id: string;
  spec_id: string;        // "owner/repo" or module name
  trust_level: string;
  status: string;
  created_at: number;     // Unix timestamp (seconds)
  verified: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TRUST_BADGE_STYLES: Record<
  string,
  { bg: string; text: string; border: string; label: string }
> = {
  FORMALLY_VERIFIED: {
    bg: "#1A1408",
    text: "#FFD060",
    border: "#FFD060",
    label: "Proven",
  },
  PROPERTY_VERIFIED: {
    bg: "#1A1408",
    text: "#F5B93A",
    border: "#F5B93A",
    label: "PBT Pass",
  },
  SCHEMA_VERIFIED: {
    bg: "#1A1408",
    text: "#A87020",
    border: "#A87020",
    label: "Schema",
  },
  UNVERIFIED: {
    bg: "#1A1408",
    text: "#4A3A1A",
    border: "#2A1E08",
    label: "Unverified",
  },
};

function trustBadgeStyle(trust: string) {
  return TRUST_BADGE_STYLES[trust] ?? TRUST_BADGE_STYLES["UNVERIFIED"];
}

function timeAgo(ts: number): string {
  const diffMs = Date.now() - ts * 1000;
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return `${Math.floor(diffHr / 24)}d ago`;
}

function repoName(specId: string): string {
  // spec_id is "owner/repo" — show full slug; fall back gracefully
  return specId || "unknown/repo";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface RecentScansProps {
  /** Override API base for testing. */
  apiBase?: string;
  /** Poll interval in ms (default 30000). */
  pollIntervalMs?: number;
}

export function RecentScans({
  apiBase = "",
  pollIntervalMs = 30_000,
}: RecentScansProps) {
  const [runs, setRuns] = useState<PublicRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  // Track which run_ids are newly added so we can animate them
  const knownIdsRef = useRef<Set<string>>(new Set());
  const [newIds, setNewIds] = useState<Set<string>>(new Set());

  async function fetchRuns() {
    try {
      const res = await fetch(`${apiBase}/api/runs?public=true&limit=10`, {
        cache: "no-store",
      });
      if (!res.ok) {
        setError(true);
        return;
      }
      const data = (await res.json()) as PublicRun[];
      const fresh = new Set<string>();
      for (const r of data) {
        if (!knownIdsRef.current.has(r.run_id)) {
          fresh.add(r.run_id);
          knownIdsRef.current.add(r.run_id);
        }
      }
      if (fresh.size > 0) {
        setNewIds(fresh);
        // Clear animation class after 300ms
        setTimeout(() => setNewIds(new Set()), 300);
      }
      setRuns(data);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchRuns();
    const id = setInterval(fetchRuns, pollIntervalMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiBase, pollIntervalMs]);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: "16px 0" }}>
        <span
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "11px",
            color: "#4A3A1A",
            letterSpacing: "0.06em",
          }}
        >
          Loading recent scans…
        </span>
      </div>
    );
  }

  if (error || runs.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "16px 0" }}>
        <span
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "11px",
            color: "#3A2E10",
            letterSpacing: "0.06em",
          }}
        >
          {error ? "Could not load recent scans." : "No public scans yet — be the first."}
        </span>
      </div>
    );
  }

  return (
    <div
      role="list"
      aria-label="Recent public verification scans"
      style={{ width: "100%", maxWidth: "640px" }}
    >
      {/* Column headers */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          padding: "0 4px 8px",
          borderBottom: "1px solid #2A2315",
          marginBottom: "4px",
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-jetbrains-mono), monospace",
            fontSize: "10px",
            color: "#4A3A1A",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
          }}
        >
          Repository
        </span>
        <div style={{ display: "flex", gap: "32px" }}>
          <span
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              color: "#4A3A1A",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
            }}
          >
            Result
          </span>
          <span
            style={{
              fontFamily: "var(--font-jetbrains-mono), monospace",
              fontSize: "10px",
              color: "#4A3A1A",
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              minWidth: "56px",
              textAlign: "right",
            }}
          >
            When
          </span>
        </div>
      </div>

      {runs.map((run) => {
        const badge = trustBadgeStyle(run.trust_level);
        const isNew = newIds.has(run.run_id);

        return (
          <a
            key={run.run_id}
            href={`/run/${run.run_id}`}
            role="listitem"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 4px",
              borderBottom: "1px solid #1A1408",
              textDecoration: "none",
              borderRadius: "4px",
              // Crystallization entry animation — 150ms snap
              opacity: isNew ? 0 : 1,
              transform: isNew ? "translateY(-4px)" : "translateY(0)",
              transition: isNew
                ? "none"
                : "opacity 150ms cubic-bezier(0.16,1,0.3,1), transform 150ms cubic-bezier(0.16,1,0.3,1), background-color 120ms ease",
              backgroundColor: "transparent",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.backgroundColor =
                "#141109";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.backgroundColor =
                "transparent";
            }}
          >
            {/* Repo name */}
            <span
              style={{
                fontFamily: "var(--font-jetbrains-mono), monospace",
                fontSize: "13px",
                color: "#A89070",
                letterSpacing: "0.02em",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                maxWidth: "320px",
              }}
            >
              {repoName(run.spec_id)}
            </span>

            <div style={{ display: "flex", alignItems: "center", gap: "24px", flexShrink: 0 }}>
              {/* Trust badge */}
              <span
                style={{
                  padding: "2px 8px",
                  borderRadius: "4px",
                  border: `1px solid ${badge.border}`,
                  backgroundColor: badge.bg,
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "10px",
                  fontWeight: 600,
                  color: badge.text,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  whiteSpace: "nowrap",
                }}
              >
                {badge.label}
              </span>

              {/* Time ago */}
              <span
                style={{
                  fontFamily: "var(--font-jetbrains-mono), monospace",
                  fontSize: "11px",
                  color: "#4A3A1A",
                  letterSpacing: "0.04em",
                  minWidth: "56px",
                  textAlign: "right",
                }}
              >
                {timeAgo(run.created_at)}
              </span>
            </div>
          </a>
        );
      })}
    </div>
  );
}
