"use client";

import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StatCard {
  /** Large numeric/text value displayed prominently. */
  value: string | number;
  /** Descriptor below the value. */
  label: string;
}

export interface StatsRowProps {
  /** Stages completed out of total (e.g. { passed: 6, total: 6 }). */
  stages?: { passed: number; total: number };
  /** Number of invariants formally proven. */
  invariantsProven?: number;
  /** Number of counterexamples found. */
  counterexamples?: number;
  /** Total pipeline execution time in seconds. */
  totalTimeSeconds?: number;
  /** Fully custom cards (overrides the above when provided). */
  cards?: StatCard[];
  className?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format seconds to a compact display string (e.g. 2.4s, 1m 3s). */
function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m ${s}s`;
}

// ---------------------------------------------------------------------------
// Sub-component: single stat card
// ---------------------------------------------------------------------------

function StatCard({ value, label }: StatCard) {
  return (
    <div
      className="flex flex-1 flex-col items-center justify-center gap-0.5 px-4 py-3"
      style={{
        backgroundColor: "#141109",
        border: "1px solid #2A2315",
        borderRadius: "0.5rem",
        minWidth: 0,
      }}
    >
      <span
        className="leading-none tabular-nums"
        style={{
          color: "#F5B93A",
          fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
          fontWeight: 600,
          fontSize: "1.5rem",
          lineHeight: 1,
        }}
        aria-label={String(value)}
      >
        {value}
      </span>
      <span
        className="mt-1 text-xs leading-none"
        style={{
          color: "#9A8E78",
          fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
          fontWeight: 400,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          maxWidth: "100%",
        }}
      >
        {label}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * StatsRow — four-card strip showing pipeline metrics.
 *
 * Default layout:
 *   [6/6 Stages]  [47 Invariants Proven]  [0 Counterexamples]  [2.4s Total Time]
 *
 * Pass `cards` prop to override all four cards with custom data.
 */
export function StatsRow({
  stages = { passed: 0, total: 6 },
  invariantsProven = 0,
  counterexamples = 0,
  totalTimeSeconds = 0,
  cards,
  className,
}: StatsRowProps) {
  const resolvedCards: StatCard[] = cards ?? [
    {
      value: `${stages.passed}/${stages.total}`,
      label: "Stages",
    },
    {
      value: invariantsProven,
      label: "Invariants Proven",
    },
    {
      value: counterexamples,
      label: "Counterexamples",
    },
    {
      value: formatTime(totalTimeSeconds),
      label: "Total Time",
    },
  ];

  return (
    <div
      className={cn("flex w-full flex-row gap-2", className)}
      role="region"
      aria-label="Pipeline statistics"
    >
      {resolvedCards.map((card, i) => (
        <StatCard key={i} value={card.value} label={card.label} />
      ))}
    </div>
  );
}
