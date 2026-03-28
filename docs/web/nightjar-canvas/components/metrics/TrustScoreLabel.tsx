"use client";

import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types & constants
// ---------------------------------------------------------------------------

export type TrustScoreRange =
  | "critical"
  | "developing"
  | "proving"
  | "verified"
  | "certified";

interface RangeConfig {
  label: string;
  color: string;
  /** Subtle background at 15% opacity of the text color. */
  bg: string;
  /** Border at 30% opacity. */
  border: string;
}

const RANGE_CONFIG: Record<TrustScoreRange, RangeConfig> = {
  critical: {
    label: "Critical",
    color: "#C84B2F",
    bg: "rgba(200,75,47,0.12)",
    border: "rgba(200,75,47,0.30)",
  },
  developing: {
    label: "Developing",
    color: "#A87020",
    bg: "rgba(168,112,32,0.12)",
    border: "rgba(168,112,32,0.30)",
  },
  proving: {
    label: "Proving",
    color: "#D4920A",
    bg: "rgba(212,146,10,0.12)",
    border: "rgba(212,146,10,0.30)",
  },
  verified: {
    label: "Verified",
    color: "#F5B93A",
    bg: "rgba(245,185,58,0.12)",
    border: "rgba(245,185,58,0.30)",
  },
  certified: {
    label: "Certified",
    color: "#FFD060",
    bg: "rgba(255,208,96,0.12)",
    border: "rgba(255,208,96,0.30)",
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Derive the trust range from a 0–100 score. */
export function scoreToRange(score: number): TrustScoreRange {
  if (score <= 40) return "critical";
  if (score <= 60) return "developing";
  if (score <= 80) return "proving";
  if (score <= 95) return "verified";
  return "certified";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface TrustScoreLabelProps {
  /**
   * Numeric score 0–100. The component derives its range + color from this.
   * Provide either `score` or `range` — `score` takes precedence.
   */
  score?: number;
  /**
   * Explicit range override. Used when a score is not available (e.g.
   * rendering from a stored trust level).
   */
  range?: TrustScoreRange;
  className?: string;
}

/**
 * TrustScoreLabel — color-coded pill badge.
 *
 * | Score   | Label      | Color     |
 * |---------|------------|-----------|
 * | 0–40    | Critical   | #C84B2F   |
 * | 41–60   | Developing | #A87020   |
 * | 61–80   | Proving    | #D4920A   |
 * | 81–95   | Verified   | #F5B93A   |
 * | 96–100  | Certified  | #FFD060   |
 *
 * Styled as a compact pill with `letter-spacing: 0.12em`.
 */
export function TrustScoreLabel({
  score,
  range,
  className,
}: TrustScoreLabelProps) {
  const resolvedRange: TrustScoreRange =
    score !== undefined ? scoreToRange(score) : (range ?? "critical");

  const config = RANGE_CONFIG[resolvedRange];

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-full px-3 py-0.5",
        "text-xs font-semibold uppercase",
        className,
      )}
      style={{
        color: config.color,
        backgroundColor: config.bg,
        border: `1px solid ${config.border}`,
        letterSpacing: "0.12em",
        fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
      }}
      aria-label={`Trust level: ${config.label}`}
    >
      {config.label}
    </span>
  );
}
