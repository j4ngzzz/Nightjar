"use client";

/**
 * Nightjar Verification Canvas — InvariantDiff
 *
 * Diff view for invariants between two verification runs.
 * Categorizes invariants into: NEW, CHANGED, REMOVED, SAME.
 *
 * Color rules:
 *   ▲ NEW (n):      amber  #D4920A
 *   ~ CHANGED (n):  amber  #A87020
 *   ▼ REMOVED (n):  warm red #C84B2F
 *   = SAME (n):     dim    #3A2E10
 *
 * No green, no purple.
 */

import { useMemo } from "react";
import { cn } from "@/lib/cn";
import type { CanvasInvariant } from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type InvariantDiffCategory = "new" | "changed" | "removed" | "same";

export interface DiffedInvariant {
  invariant_id: string;
  statement: string;
  rationale: string;
  tier: CanvasInvariant["tier"];
  category: InvariantDiffCategory;
}

export interface InvariantDiffProps {
  /** Invariants from Run A (baseline). */
  invariantsA: CanvasInvariant[];
  /** Invariants from Run B (comparison). */
  invariantsB: CanvasInvariant[];
  /**
   * When true, renders the SAME group collapsed by default.
   * Defaults to true.
   */
  collapseSame?: boolean;
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const CATEGORY_META: Record<
  InvariantDiffCategory,
  { symbol: string; label: string; color: string; dimColor: string }
> = {
  new: {
    symbol: "▲",
    label: "NEW",
    color: "#D4920A",
    dimColor: "rgba(212,146,10,0.12)",
  },
  changed: {
    symbol: "~",
    label: "CHANGED",
    color: "#A87020",
    dimColor: "rgba(168,112,32,0.12)",
  },
  removed: {
    symbol: "▼",
    label: "REMOVED",
    color: "#C84B2F",
    dimColor: "rgba(200,75,47,0.1)",
  },
  same: {
    symbol: "=",
    label: "SAME",
    color: "#3A2E10",
    dimColor: "transparent",
  },
};

// ---------------------------------------------------------------------------
// Diff algorithm
// ---------------------------------------------------------------------------

/**
 * Match invariants between two runs by normalizing the statement text.
 *
 * Matching strategy (in priority order):
 * 1. Exact invariant_id match → SAME (or CHANGED if statement differs)
 * 2. Exact normalized statement match (across both runs) → SAME
 * 3. Fuzzy normalized match (ignoring whitespace) → CHANGED
 * 4. In A only → REMOVED
 * 5. In B only → NEW
 */
export function diffInvariants(
  invariantsA: CanvasInvariant[],
  invariantsB: CanvasInvariant[]
): DiffedInvariant[] {
  /** Normalize: trim + collapse whitespace + lowercase for comparison only. */
  function normalize(s: string): string {
    return s.trim().replace(/\s+/g, " ").toLowerCase();
  }

  const results: DiffedInvariant[] = [];

  const usedB = new Set<string>(); // invariant_ids from B that have been matched

  // Index B by id and by normalized statement
  const bById = new Map<string, CanvasInvariant>();
  const bByNorm = new Map<string, CanvasInvariant>();

  for (const inv of invariantsB) {
    bById.set(inv.invariant_id, inv);
    bByNorm.set(normalize(inv.statement), inv);
  }

  // Pass 1: match each A invariant
  for (const invA of invariantsA) {
    const normA = normalize(invA.statement);

    // Priority 1: same id
    const matchById = bById.get(invA.invariant_id);
    if (matchById && !usedB.has(matchById.invariant_id)) {
      usedB.add(matchById.invariant_id);
      const category: InvariantDiffCategory =
        normalize(matchById.statement) === normA ? "same" : "changed";
      results.push({
        invariant_id: invA.invariant_id,
        // For changed items show B-side statement (the new version).
        statement: category === "changed" ? matchById.statement : invA.statement,
        // For changed items show B-side rationale to match the shown statement.
        rationale: category === "changed" ? matchById.rationale : invA.rationale,
        tier: invA.tier,
        category,
      });
      continue;
    }

    // Priority 2: same normalized statement (different id)
    const matchByNorm = bByNorm.get(normA);
    if (matchByNorm && !usedB.has(matchByNorm.invariant_id)) {
      usedB.add(matchByNorm.invariant_id);
      results.push({
        invariant_id: invA.invariant_id,
        statement: invA.statement,
        rationale: invA.rationale,
        tier: invA.tier,
        category: "same",
      });
      continue;
    }

    // No match → REMOVED
    results.push({
      invariant_id: invA.invariant_id,
      statement: invA.statement,
      rationale: invA.rationale,
      tier: invA.tier,
      category: "removed",
    });
  }

  // Pass 2: B invariants not matched → NEW
  for (const invB of invariantsB) {
    if (!usedB.has(invB.invariant_id)) {
      results.push({
        invariant_id: invB.invariant_id,
        statement: invB.statement,
        rationale: invB.rationale,
        tier: invB.tier,
        category: "new",
      });
    }
  }

  // Sort: new → changed → removed → same
  const order: InvariantDiffCategory[] = ["new", "changed", "removed", "same"];
  results.sort(
    (a, b) => order.indexOf(a.category) - order.indexOf(b.category)
  );

  return results;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface CategoryHeaderProps {
  category: InvariantDiffCategory;
  count: number;
}

function CategoryHeader({ category, count }: CategoryHeaderProps) {
  const meta = CATEGORY_META[category];

  return (
    <div
      className="flex items-center gap-2 py-1 select-none"
      aria-label={`${meta.label}: ${count}`}
    >
      <span
        className="text-xs font-bold w-4 text-center"
        style={{
          color: meta.color,
          fontFamily: "var(--font-jetbrains-mono)",
        }}
        aria-hidden
      >
        {meta.symbol}
      </span>
      <span
        className="text-xs font-semibold tracking-wider"
        style={{
          color: meta.color,
          fontFamily: "var(--font-jetbrains-mono)",
          letterSpacing: "0.08em",
        }}
      >
        {meta.label}
      </span>
      <span
        className="text-xs tabular-nums"
        style={{
          color: meta.color,
          fontFamily: "var(--font-jetbrains-mono)",
          opacity: 0.7,
        }}
      >
        ({count})
      </span>
    </div>
  );
}

interface InvariantRowProps {
  inv: DiffedInvariant;
}

function InvariantRow({ inv }: InvariantRowProps) {
  const meta = CATEGORY_META[inv.category];

  return (
    <div
      className="flex flex-col gap-0.5 rounded px-3 py-2"
      style={{
        backgroundColor: meta.dimColor,
        borderLeft: `2px solid ${meta.color}`,
      }}
      role="listitem"
    >
      {/* Tier badge + statement */}
      <div className="flex items-start gap-2">
        <span
          className="mt-0.5 text-[9px] font-semibold rounded px-1 py-0.5 shrink-0"
          style={{
            color: "#8B8579",
            backgroundColor: "#0D0B09",
            fontFamily: "var(--font-jetbrains-mono)",
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          {inv.tier}
        </span>
        <span
          className="text-xs leading-relaxed flex-1"
          style={{
            color: inv.category === "same" ? "#6E6860" : "#F0EBE3",
            fontFamily: "var(--font-jetbrains-mono)",
            wordBreak: "break-word",
          }}
        >
          {inv.statement}
        </span>
      </div>

      {/* Rationale — only for non-same items */}
      {inv.category !== "same" && inv.rationale && (
        <p
          className="text-[11px] leading-relaxed pl-10"
          style={{
            color: "#8B8579",
            fontFamily: "var(--font-geist-sans)",
            fontStyle: "italic",
          }}
        >
          {inv.rationale}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// InvariantDiff
// ---------------------------------------------------------------------------

/**
 * InvariantDiff — categorized diff view for invariants between two runs.
 *
 * Groups invariants as NEW / CHANGED / REMOVED / SAME.
 * The SAME group can be collapsed to keep the view scannable.
 */
export function InvariantDiff({
  invariantsA,
  invariantsB,
  collapseSame = true,
  className,
}: InvariantDiffProps) {
  const diffed = useMemo(
    () => diffInvariants(invariantsA, invariantsB),
    [invariantsA, invariantsB]
  );

  const byCategory = useMemo(() => {
    const groups: Record<InvariantDiffCategory, DiffedInvariant[]> = {
      new: [],
      changed: [],
      removed: [],
      same: [],
    };
    for (const inv of diffed) {
      groups[inv.category].push(inv);
    }
    return groups;
  }, [diffed]);

  const totalNew = byCategory.new.length;
  const totalChanged = byCategory.changed.length;
  const totalRemoved = byCategory.removed.length;
  const totalSame = byCategory.same.length;

  const visibleCategories: InvariantDiffCategory[] = ["new", "changed", "removed"];

  return (
    <div
      className={cn("flex flex-col gap-4 w-full", className)}
      role="region"
      aria-label="Invariant diff"
    >
      {/* Summary row */}
      <div
        className="flex flex-row flex-wrap gap-3 pb-2"
        style={{ borderBottom: "1px solid #2A2315" }}
        aria-label="Invariant diff summary"
      >
        {(
          [
            { cat: "new" as const, count: totalNew },
            { cat: "changed" as const, count: totalChanged },
            { cat: "removed" as const, count: totalRemoved },
            { cat: "same" as const, count: totalSame },
          ] as const
        ).map(({ cat, count }) => {
          const meta = CATEGORY_META[cat];
          return (
            <span
              key={cat}
              className="text-xs font-medium tabular-nums"
              style={{
                color: meta.color,
                fontFamily: "var(--font-jetbrains-mono)",
                opacity: count === 0 ? 0.35 : 1,
              }}
            >
              {meta.symbol} {meta.label} ({count})
            </span>
          );
        })}
      </div>

      {/* New / Changed / Removed groups */}
      {visibleCategories.map((cat) => {
        const items = byCategory[cat];
        if (items.length === 0) return null;

        return (
          <div key={cat} className="flex flex-col gap-1">
            <CategoryHeader category={cat} count={items.length} />
            <div
              className="flex flex-col gap-1 pl-1"
              role="list"
              aria-label={`${CATEGORY_META[cat].label} invariants`}
            >
              {items.map((inv) => (
                <InvariantRow key={inv.invariant_id} inv={inv} />
              ))}
            </div>
          </div>
        );
      })}

      {/* Same group — collapsible */}
      {totalSame > 0 && (
        <details open={!collapseSame}>
          <summary
            className="cursor-pointer select-none list-none flex items-center gap-2 py-1"
            style={{ userSelect: "none" }}
          >
            <CategoryHeader category="same" count={totalSame} />
          </summary>
          <div
            className="flex flex-col gap-1 pl-1 mt-1"
            role="list"
            aria-label="Unchanged invariants"
          >
            {byCategory.same.map((inv) => (
              <InvariantRow key={inv.invariant_id} inv={inv} />
            ))}
          </div>
        </details>
      )}

      {/* Empty state */}
      {diffed.length === 0 && (
        <div
          className="text-sm text-center py-6"
          style={{
            color: "#6E6860",
            fontFamily: "var(--font-geist-sans)",
          }}
        >
          No invariants found in either run.
        </div>
      )}
    </div>
  );
}
