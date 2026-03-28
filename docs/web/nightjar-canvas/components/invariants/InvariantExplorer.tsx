"use client";

/**
 * InvariantExplorer — masonry-style grid of InvariantCards with filter controls.
 *
 * Uses CSS Grid auto-fill minmax(280px, 1fr) for masonry layout.
 * Imports InvariantCard from B3 (../panels/InvariantCard).
 * Uses InvariantFilter for stage / confidence / origin / search controls.
 *
 * Color rules: amber palette, NO green, NO purple.
 */

import * as React from "react";
import { AnimatePresence, motion } from "motion/react";
import { cn } from "@/lib/cn";
import {
  InvariantCard,
  type InvariantData,
} from "../panels/InvariantCard";
import {
  InvariantFilter,
  type InvariantFilterState,
} from "./InvariantFilter";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface InvariantExplorerProps {
  invariants: InvariantData[];
  className?: string;
}

// ---------------------------------------------------------------------------
// Filter logic (pure)
// ---------------------------------------------------------------------------

function applyFilters(
  invariants: InvariantData[],
  filters: InvariantFilterState
): InvariantData[] {
  let result = invariants;

  // Stage
  if (filters.stage !== "all") {
    result = result.filter((inv) => inv.tier === filters.stage);
  }

  // Confidence
  result = result.filter((inv) => inv.confidence > filters.confidence);

  // Origin
  if (filters.origin !== "all") {
    result = result.filter((inv) => inv.origin === filters.origin);
  }

  // Search (NL description substring, case-insensitive)
  if (filters.search.trim()) {
    const needle = filters.search.trim().toLowerCase();
    result = result.filter((inv) =>
      inv.description.toLowerCase().includes(needle)
    );
  }

  return result;
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div
      className="col-span-full flex flex-col items-center justify-center gap-2 rounded-md p-10"
      style={{
        border: "1px dashed #2A2315",
        color: "#9A8E78",
      }}
    >
      <span
        className="text-[12px] uppercase tracking-widest"
        style={{ fontFamily: "var(--font-jetbrains-mono)" }}
      >
        No invariants match
      </span>
      <span
        className="text-[11px]"
        style={{ fontFamily: "var(--font-geist-sans)" }}
      >
        Adjust filters or search to see results.
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function InvariantExplorer({
  invariants,
  className,
}: InvariantExplorerProps) {
  const [filters, setFilters] = React.useState<InvariantFilterState>({
    stage: "all",
    confidence: 50,
    origin: "all",
    search: "",
  });

  const filtered = applyFilters(invariants, filters);

  return (
    <div className={cn("space-y-4", className)}>
      {/* Filter bar */}
      <InvariantFilter
        value={filters}
        onChange={setFilters}
        displayCount={filtered.length}
        totalCount={invariants.length}
      />

      {/* Masonry-style grid */}
      <div
        className="grid gap-3"
        style={{
          gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
          alignItems: "start",
        }}
      >
        <AnimatePresence mode="popLayout">
          {filtered.length === 0 ? (
            <EmptyState />
          ) : (
            filtered.map((inv) => (
              <motion.div
                key={inv.id}
                layout
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.94 }}
                transition={{
                  duration: 0.18,
                  ease: [0.16, 1, 0.3, 1],
                }}
              >
                <InvariantCard invariant={inv} />
              </motion.div>
            ))
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
