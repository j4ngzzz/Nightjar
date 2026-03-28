"use client";

/**
 * CoverageMap — code view with a colored left-border gutter showing proof coverage.
 *
 * Gutter colors (spec):
 *   #F5B93A  — formally proven
 *   #A87020  — PBT covered
 *   #D4920A  — schema validated
 *   #3A2E10  — untested (dim)
 *
 * Hover: tooltip showing which invariants cover this line.
 * Color legend below the code view.
 *
 * Color rules: amber palette, NO green, NO purple.
 */

import * as React from "react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type LineCoverageType =
  | "formal"
  | "pbt"
  | "schema"
  | "untested";

export interface CoverageLineData {
  lineNumber: number;
  /** Source code text for this line. */
  text: string;
  coverage: LineCoverageType;
  /** List of invariant NL descriptions that cover this line. */
  coveringInvariants?: string[];
}

interface CoverageMapProps {
  /** File path or label shown in the header. */
  filePath?: string;
  lines: CoverageLineData[];
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COVERAGE_COLORS: Record<LineCoverageType, string> = {
  formal: "#F5B93A",
  pbt: "#A87020",
  schema: "#D4920A",
  untested: "#3A2E10",
};

const COVERAGE_LABELS: Record<LineCoverageType, string> = {
  formal: "Formally proven",
  pbt: "PBT covered",
  schema: "Schema validated",
  untested: "Untested",
};

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

interface TooltipProps {
  invariants: string[];
  coverageType: LineCoverageType;
  visible: boolean;
}

function LineTooltip({ invariants, coverageType, visible }: TooltipProps) {
  if (!visible) return null;

  return (
    <div
      className="absolute left-10 z-50 w-64 rounded px-3 py-2 shadow-lg pointer-events-none"
      style={{
        background: "#1A1408",
        border: "1px solid #4A3A1A",
        top: "50%",
        transform: "translateY(-50%)",
      }}
      role="tooltip"
    >
      <p
        className="mb-1 text-[10px] uppercase tracking-widest"
        style={{
          color: COVERAGE_COLORS[coverageType],
          fontFamily: "var(--font-jetbrains-mono)",
        }}
      >
        {COVERAGE_LABELS[coverageType]}
      </p>
      {invariants.length === 0 ? (
        <p
          className="text-[11px]"
          style={{ color: "#9A8E78", fontFamily: "var(--font-geist-sans)" }}
        >
          No invariants cover this line.
        </p>
      ) : (
        <ul className="space-y-0.5 list-none p-0 m-0">
          {invariants.map((inv, i) => (
            <li
              key={i}
              className="text-[11px] leading-snug"
              style={{
                color: "#F0EBE3",
                fontFamily: "var(--font-geist-sans)",
              }}
            >
              {inv}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Line row
// ---------------------------------------------------------------------------

interface LineRowProps {
  line: CoverageLineData;
}

function LineRow({ line }: LineRowProps) {
  const [hovered, setHovered] = React.useState(false);
  const color = COVERAGE_COLORS[line.coverage];
  const invariants = line.coveringInvariants ?? [];

  return (
    <div
      className="relative flex items-stretch group"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Colored left-border gutter */}
      <div
        className="flex-shrink-0 w-1 mr-0"
        style={{ background: color }}
        aria-hidden="true"
      />

      {/* Line number */}
      <div
        className="flex-shrink-0 w-10 text-right pr-3 select-none text-[11px] leading-relaxed"
        style={{
          color: "#4A4030",
          fontFamily: "var(--font-jetbrains-mono)",
          background: "#0A0905",
          paddingTop: "1px",
          paddingBottom: "1px",
        }}
        aria-hidden="true"
      >
        {line.lineNumber}
      </div>

      {/* Code content */}
      <pre
        className="flex-1 px-3 text-[12px] leading-relaxed whitespace-pre overflow-x-auto"
        style={{
          fontFamily: "var(--font-jetbrains-mono)",
          color: line.coverage === "untested" ? "#4A4030" : "#F0EBE3",
          background: hovered ? "rgba(212,146,10,0.04)" : "transparent",
          paddingTop: "1px",
          paddingBottom: "1px",
          transition: "background 0.1s",
        }}
      >
        {line.text}
      </pre>

      {/* Tooltip on hover */}
      <LineTooltip
        invariants={invariants}
        coverageType={line.coverage}
        visible={hovered}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Legend
// ---------------------------------------------------------------------------

function CoverageLegend() {
  const items: { type: LineCoverageType; label: string }[] = [
    { type: "formal", label: "Formally proven" },
    { type: "pbt", label: "PBT covered" },
    { type: "schema", label: "Schema validated" },
    { type: "untested", label: "Untested" },
  ];

  return (
    <div
      className="flex flex-wrap items-center gap-4 px-3 py-2"
      style={{ borderTop: "1px solid #2A2315" }}
      aria-label="Coverage legend"
    >
      {items.map(({ type, label }) => (
        <div key={type} className="flex items-center gap-1.5">
          <span
            className="h-2.5 w-1 rounded-sm flex-shrink-0"
            style={{ background: COVERAGE_COLORS[type] }}
            aria-hidden="true"
          />
          <span
            className="text-[10px] uppercase tracking-wider"
            style={{
              color: COVERAGE_COLORS[type],
              fontFamily: "var(--font-jetbrains-mono)",
              opacity: type === "untested" ? 0.6 : 1,
            }}
          >
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CoverageMap({ filePath, lines, className }: CoverageMapProps) {
  // Summary stats
  const stats = React.useMemo(() => {
    const counts: Record<LineCoverageType, number> = {
      formal: 0,
      pbt: 0,
      schema: 0,
      untested: 0,
    };
    for (const line of lines) {
      counts[line.coverage]++;
    }
    const covered =
      counts.formal + counts.pbt + counts.schema;
    const total = lines.length;
    const pct = total === 0 ? 0 : Math.round((covered / total) * 100);
    return { counts, covered, total, pct };
  }, [lines]);

  return (
    <div
      className={cn("rounded-md overflow-hidden", className)}
      style={{
        background: "#0D0B09",
        border: "1px solid #2A2315",
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-2"
        style={{ borderBottom: "1px solid #2A2315", background: "#141109" }}
      >
        <div className="flex items-center gap-2">
          <span
            className="text-[10px] uppercase tracking-widest"
            style={{
              color: "#9A8E78",
              fontFamily: "var(--font-jetbrains-mono)",
            }}
          >
            Coverage
          </span>
          {filePath && (
            <>
              <span
                style={{ color: "#2A2315" }}
                aria-hidden="true"
              >
                /
              </span>
              <span
                className="text-[11px]"
                style={{
                  color: "#D4920A",
                  fontFamily: "var(--font-jetbrains-mono)",
                }}
              >
                {filePath}
              </span>
            </>
          )}
        </div>

        {/* Coverage percentage badge */}
        <span
          className="text-[11px] tabular-nums"
          style={{
            color: stats.pct >= 80 ? "#F5B93A" : stats.pct >= 50 ? "#D4920A" : "#C84B2F",
            fontFamily: "var(--font-jetbrains-mono)",
          }}
          aria-label={`${stats.pct}% of lines covered`}
        >
          {stats.pct}% covered ({stats.covered}/{stats.total})
        </span>
      </div>

      {/* Code lines */}
      <div className="overflow-auto max-h-[480px]">
        {lines.length === 0 ? (
          <div
            className="flex items-center justify-center p-8 text-[12px]"
            style={{
              color: "#9A8E78",
              fontFamily: "var(--font-jetbrains-mono)",
            }}
          >
            No source lines to display
          </div>
        ) : (
          lines.map((line) => (
            <LineRow key={line.lineNumber} line={line} />
          ))
        )}
      </div>

      {/* Legend */}
      <CoverageLegend />
    </div>
  );
}
