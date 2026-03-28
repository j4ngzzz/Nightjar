"use client";

/**
 * InvariantFilter — filter bar for the InvariantExplorer grid.
 *
 * Controls:
 * - Stage tabs: All / PBT / Formal / Both
 * - Confidence threshold: >50% / >80% / >95%
 * - Origin: All / spec / immune / lifted
 * - Full-text search (client-side)
 *
 * Color rules: amber palette, NO green, NO purple.
 */

import * as React from "react";
import { cn } from "@/lib/cn";
import type { InvariantTier, InvariantOrigin } from "../panels/InvariantCard";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type StageFilter = "all" | InvariantTier;
export type ConfidenceFilter = 50 | 80 | 95;
export type OriginFilter = "all" | InvariantOrigin;

export interface InvariantFilterState {
  stage: StageFilter;
  confidence: ConfidenceFilter;
  origin: OriginFilter;
  search: string;
}

interface InvariantFilterProps {
  value: InvariantFilterState;
  onChange: (next: InvariantFilterState) => void;
  /** Total count of displayed invariants after filtering. */
  displayCount: number;
  /** Total unfiltered count. */
  totalCount: number;
  className?: string;
}

// ---------------------------------------------------------------------------
// Primitive: pill tab button
// ---------------------------------------------------------------------------

interface PillProps {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}

function Pill({ active, onClick, children }: PillProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center rounded px-2.5 py-1 text-[11px] font-medium transition-colors"
      style={{
        background: active ? "#D4920A" : "#1A1408",
        color: active ? "#0D0B09" : "#9A8E78",
        border: `1px solid ${active ? "#D4920A" : "#2A2315"}`,
        fontFamily: "var(--font-jetbrains-mono)",
        cursor: "pointer",
      }}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Primitive: group label
// ---------------------------------------------------------------------------

function GroupLabel({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="text-[10px] uppercase tracking-widest flex-shrink-0"
      style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
    >
      {children}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function InvariantFilter({
  value,
  onChange,
  displayCount,
  totalCount,
  className,
}: InvariantFilterProps) {
  const { stage, confidence, origin, search } = value;

  function set<K extends keyof InvariantFilterState>(
    key: K,
    val: InvariantFilterState[K]
  ) {
    onChange({ ...value, [key]: val });
  }

  const STAGE_OPTIONS: { label: string; value: StageFilter }[] = [
    { label: "All", value: "all" },
    { label: "PBT", value: "pbt" },
    { label: "Formal", value: "formal" },
    { label: "Both", value: "both" },
  ];

  const CONFIDENCE_OPTIONS: { label: string; value: ConfidenceFilter }[] = [
    { label: ">50%", value: 50 },
    { label: ">80%", value: 80 },
    { label: ">95%", value: 95 },
  ];

  const ORIGIN_OPTIONS: { label: string; value: OriginFilter }[] = [
    { label: "All", value: "all" },
    { label: "spec", value: "spec" },
    { label: "immune", value: "immune" },
    { label: "lifted", value: "lifted" },
  ];

  return (
    <div
      className={cn("rounded-md p-3 space-y-3", className)}
      style={{
        background: "#141109",
        border: "1px solid #2A2315",
      }}
    >
      {/* Search + count */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Search invariants…"
          value={search}
          onChange={(e) => set("search", e.target.value)}
          className="flex-1 rounded px-3 py-1.5 text-[12px] outline-none"
          style={{
            background: "#0D0B09",
            border: "1px solid #2A2315",
            color: "#F0EBE3",
            fontFamily: "var(--font-jetbrains-mono)",
            transition: "border-color 0.15s",
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderColor = "#D4920A";
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderColor = "#2A2315";
          }}
          aria-label="Search invariants by description"
        />

        <span
          className="flex-shrink-0 rounded px-2 py-1 text-[11px] tabular-nums"
          style={{
            background: "#1A1408",
            border: "1px solid #2A2315",
            color: "#D4920A",
            fontFamily: "var(--font-jetbrains-mono)",
          }}
          aria-live="polite"
          aria-label={`${displayCount} of ${totalCount} invariants shown`}
        >
          {displayCount} / {totalCount} invariants proven
        </span>
      </div>

      {/* Filter row */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {/* Stage */}
        <div className="flex items-center gap-2">
          <GroupLabel>Stage</GroupLabel>
          <div className="flex items-center gap-1">
            {STAGE_OPTIONS.map((opt) => (
              <Pill
                key={opt.value}
                active={stage === opt.value}
                onClick={() => set("stage", opt.value)}
              >
                {opt.label}
              </Pill>
            ))}
          </div>
        </div>

        {/* Separator */}
        <span
          className="hidden sm:block h-4 w-px flex-shrink-0"
          style={{ background: "#2A2315" }}
          aria-hidden="true"
        />

        {/* Confidence */}
        <div className="flex items-center gap-2">
          <GroupLabel>Conf</GroupLabel>
          <div className="flex items-center gap-1">
            {CONFIDENCE_OPTIONS.map((opt) => (
              <Pill
                key={opt.value}
                active={confidence === opt.value}
                onClick={() => set("confidence", opt.value)}
              >
                {opt.label}
              </Pill>
            ))}
          </div>
        </div>

        {/* Separator */}
        <span
          className="hidden sm:block h-4 w-px flex-shrink-0"
          style={{ background: "#2A2315" }}
          aria-hidden="true"
        />

        {/* Origin */}
        <div className="flex items-center gap-2">
          <GroupLabel>Origin</GroupLabel>
          <div className="flex items-center gap-1">
            {ORIGIN_OPTIONS.map((opt) => (
              <Pill
                key={opt.value}
                active={origin === opt.value}
                onClick={() => set("origin", opt.value)}
              >
                {opt.label}
              </Pill>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
