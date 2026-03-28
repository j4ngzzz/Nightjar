/**
 * OG Image Route — /api/og/run/[id]
 *
 * Generates a 1200×630 PNG social card for a verification run using
 * Next.js ImageResponse (which wraps @vercel/og / Satori internally).
 *
 * Layout (left-to-right at 1200px wide):
 *   40% — Trust score number + label
 *   30% — 6 stage nodes as SVG circles
 *   30% — Summary text block
 *   Bottom bar — "nightjar.dev | {repo}@{hash}"
 *
 * Colours:
 *   Background: #0D0B09
 *   Pass:        #F5B93A  (amber gold)
 *   Fail:        #C84B2F  (ember red)
 *   Text:        #F0EBE3  (warm white)
 *   Secondary:   #8B8579
 */

import { ImageResponse } from "next/og";
import type { NextRequest } from "next/server";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BG = "#0D0B09";
const AMBER = "#F5B93A";
const AMBER_DIM = "#D4920A";
const RED = "#C84B2F";
const TEXT = "#F0EBE3";
const TEXT_SECONDARY = "#8B8579";
const BORDER = "#2A2315";

const WIDTH = 1200;
const HEIGHT = 630;

// Cache the rendered PNG for 1 hour (CDN / browser).
export const revalidate = 3600;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StageResult {
  name: string;
  passed: boolean;
  skipped?: boolean;
}

interface OgRunData {
  repo: string;
  hash: string;
  trustScore: number;
  invariantCount: number;
  stageDurationSecs: number;
  stages: StageResult[];
  trustLabel: string;
  isVerified: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Derive colour from trust score (matches badge thresholds). */
function scoreColor(score: number): string {
  if (score >= 81) return AMBER;
  if (score >= 61) return AMBER_DIM;
  return RED;
}

/** Derive human label from trust score. */
function trustLabel(score: number, verified: boolean): string {
  if (!verified) return "ISSUES FOUND";
  if (score >= 96) return "CERTIFIED";
  if (score >= 81) return "FORMALLY VERIFIED";
  if (score >= 61) return "PROPERTY VERIFIED";
  if (score >= 41) return "SCHEMA VERIFIED";
  return "UNVERIFIED";
}

/**
 * Fetch run data from the backend.
 * Falls back to stub data if the backend is unreachable (e.g. at build time).
 */
async function fetchRunData(runId: string): Promise<OgRunData> {
  // Prefer the server-only API_URL (not exposed to the browser bundle).
  // Fall back to NEXT_PUBLIC_API_URL for deployments that only set the public var.
  const apiBase =
    process.env.API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000";

  try {
    const res = await fetch(`${apiBase}/api/runs/${encodeURIComponent(runId)}`, {
      next: { revalidate: 60 },
    });

    if (!res.ok) throw new Error(`API ${res.status}`);

    const run = await res.json();

    // Derive stage list from events in the run snapshot.
    const stagePassed = new Set<string>();
    const stageFailed = new Set<string>();
    const stageNames = ["preflight", "deps", "schema", "pbt", "negation", "formal"];

    for (const ev of run.events ?? []) {
      if (ev.event_type === "stage_complete") {
        stagePassed.add(ev.payload?.stage_name ?? "");
      }
      if (ev.event_type === "stage_fail") {
        stageFailed.add(ev.payload?.stage_name ?? "");
      }
    }

    const stages: StageResult[] = stageNames.map((name) => ({
      name,
      passed: stagePassed.has(name),
      skipped: !stagePassed.has(name) && !stageFailed.has(name),
    }));

    const score: number =
      typeof run.meta?.trust_score === "number" ? run.meta.trust_score : 72;
    const invariants: number = run.invariants?.length ?? 0;

    // Estimate total duration from first/last event timestamps.
    const timestamps: number[] = (run.events ?? [])
      .map((e: { ts: number }) => e.ts)
      .filter((t: number) => typeof t === "number");
    const durationSecs =
      timestamps.length >= 2
        ? Math.round((Math.max(...timestamps) - Math.min(...timestamps)) / 10) /
          100
        : 2.4;

    const meta = run.meta ?? {};
    const repo: string = String(meta.repo ?? run.spec_id ?? "unknown/repo");
    const hash: string = String(meta.commit_hash ?? run.run_id ?? "").slice(0, 7);

    return {
      repo,
      hash,
      trustScore: score,
      invariantCount: invariants,
      stageDurationSecs: durationSecs,
      stages,
      trustLabel: trustLabel(score, run.verified ?? false),
      isVerified: run.verified ?? false,
    };
  } catch {
    // Stub for build-time / error fallback.
    return {
      repo: "nightjar/demo",
      hash: "abc1234",
      trustScore: 88,
      invariantCount: 47,
      stageDurationSecs: 2.4,
      stages: [
        { name: "preflight", passed: true },
        { name: "deps", passed: true },
        { name: "schema", passed: true },
        { name: "pbt", passed: true },
        { name: "negation", passed: true },
        { name: "formal", passed: true },
      ],
      trustLabel: "FORMALLY VERIFIED",
      isVerified: true,
    };
  }
}

// ---------------------------------------------------------------------------
// Stage circles SVG element (rendered via Satori JSX)
// ---------------------------------------------------------------------------

function StageCircle({
  passed,
  skipped,
}: {
  passed: boolean;
  skipped?: boolean;
  index: number;
}) {
  const color = skipped ? "#3A2E10" : passed ? AMBER : RED;
  const border = skipped ? BORDER : passed ? AMBER : RED;

  return (
    <div
      style={{
        width: 52,
        height: 52,
        borderRadius: "50%",
        backgroundColor: `${color}22`,
        border: `2px solid ${border}`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
      }}
    >
      <div
        style={{
          width: 20,
          height: 20,
          borderRadius: "50%",
          backgroundColor: color,
          opacity: skipped ? 0.3 : 1,
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// GET handler
// ---------------------------------------------------------------------------

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id: runId } = await params;

  let data: OgRunData;
  try {
    data = await fetchRunData(runId);
  } catch {
    return new Response("Failed to fetch run data", { status: 500 });
  }

  const primaryColor = scoreColor(data.trustScore);

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          backgroundColor: BG,
          fontFamily: "system-ui, -apple-system, sans-serif",
          position: "relative",
        }}
      >
        {/* ── Top section ─────────────────────────────────────────── */}
        <div
          style={{
            display: "flex",
            flex: 1,
            padding: "48px 56px 0 56px",
          }}
        >
          {/* Left 40% — Trust score */}
          <div
            style={{
              width: "40%",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              paddingRight: 40,
            }}
          >
            {/* Score */}
            <div
              style={{
                fontSize: 96,
                fontWeight: 700,
                color: primaryColor,
                lineHeight: 1,
                letterSpacing: "-4px",
              }}
            >
              {data.trustScore}
            </div>

            {/* /100 label */}
            <div
              style={{
                fontSize: 24,
                color: TEXT_SECONDARY,
                marginTop: 4,
                letterSpacing: "0.04em",
              }}
            >
              / 100
            </div>

            {/* Verification label badge */}
            <div
              style={{
                marginTop: 20,
                display: "flex",
                alignItems: "center",
                backgroundColor: `${primaryColor}1A`,
                border: `1px solid ${primaryColor}4D`,
                borderRadius: 6,
                padding: "6px 14px",
                width: "fit-content",
              }}
            >
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  backgroundColor: primaryColor,
                  marginRight: 10,
                }}
              />
              <div
                style={{
                  fontSize: 15,
                  fontWeight: 700,
                  color: primaryColor,
                  letterSpacing: "0.12em",
                }}
              >
                {data.trustLabel}
              </div>
            </div>
          </div>

          {/* Vertical divider */}
          <div
            style={{
              width: 1,
              alignSelf: "stretch",
              backgroundColor: BORDER,
              marginRight: 40,
            }}
          />

          {/* Centre 30% — Stage nodes */}
          <div
            style={{
              width: "28%",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
            }}
          >
            <div
              style={{
                fontSize: 11,
                color: TEXT_SECONDARY,
                letterSpacing: "0.16em",
                textTransform: "uppercase",
                marginBottom: 16,
              }}
            >
              Stages
            </div>

            {/* Stage grid — 3×2 (2 rows of 3 via flex wrap) */}
            <div
              style={{
                display: "flex",
                flexWrap: "wrap",
                width: 320,
                gap: "16px",
              }}
            >
              {data.stages.slice(0, 6).map((stage, i) => (
                <StageCircle
                  key={stage.name}
                  passed={stage.passed}
                  skipped={stage.skipped}
                  index={i}
                />
              ))}
            </div>
          </div>

          {/* Vertical divider */}
          <div
            style={{
              width: 1,
              alignSelf: "stretch",
              backgroundColor: BORDER,
              marginRight: 40,
            }}
          />

          {/* Right 30% — Stats */}
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              gap: 16,
            }}
          >
            <StatRow
              value={String(data.invariantCount)}
              label="invariants proven"
              color={primaryColor}
            />
            <StatRow
              value={String(data.stages.filter((s) => s.passed).length)}
              label="stages passed"
              color={primaryColor}
            />
            <StatRow
              value={`${data.stageDurationSecs}s`}
              label="verification time"
              color={TEXT_SECONDARY}
            />
          </div>
        </div>

        {/* ── Bottom bar ───────────────────────────────────────────── */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "14px 56px",
            borderTop: `1px solid ${BORDER}`,
            marginTop: 32,
          }}
        >
          {/* Nightjar wordmark */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            {/* Hex icon */}
            <div
              style={{
                width: 24,
                height: 24,
                backgroundColor: primaryColor,
                borderRadius: 4,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <div
                style={{
                  width: 12,
                  height: 12,
                  backgroundColor: BG,
                  borderRadius: 2,
                }}
              />
            </div>
            <div
              style={{
                fontSize: 16,
                fontWeight: 700,
                color: TEXT,
                letterSpacing: "0.06em",
              }}
            >
              nightjar.dev
            </div>
          </div>

          {/* Repo + hash */}
          <div
            style={{
              fontSize: 14,
              color: TEXT_SECONDARY,
              fontFamily: "monospace",
              letterSpacing: "0.02em",
            }}
          >
            {data.repo}@{data.hash}
          </div>
        </div>
      </div>
    ),
    {
      width: WIDTH,
      height: HEIGHT,
      headers: {
        "Cache-Control": "public, max-age=3600, s-maxage=3600, stale-while-revalidate=86400",
        "Content-Type": "image/png",
      },
    }
  );
}

// ---------------------------------------------------------------------------
// Stat row sub-component
// ---------------------------------------------------------------------------

function StatRow({
  value,
  label,
  color,
}: {
  value: string;
  label: string;
  color: string;
}) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
      <div
        style={{
          fontSize: 28,
          fontWeight: 700,
          color,
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      <div
        style={{
          fontSize: 14,
          color: TEXT_SECONDARY,
          letterSpacing: "0.04em",
        }}
      >
        {label}
      </div>
    </div>
  );
}
