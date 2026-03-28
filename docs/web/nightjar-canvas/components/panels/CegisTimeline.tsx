"use client";

/**
 * CegisTimeline — horizontal CEGIS iteration timeline.
 *
 * Each iteration node shows a circle, counterexample label, and fix description.
 * Final iteration uses peak (#F5B93A) with PROVEN checkmark.
 * Clicking an iteration node expands to show input values + code diff.
 */

import * as React from "react";
import { motion, AnimatePresence } from "motion/react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CegisIteration {
  id: string;
  /** 1-based iteration index */
  index: number;
  /** Label for the counterexample (e.g., "x=-1, n=0") */
  counterexampleLabel: string;
  /** Human-readable description of the fix applied */
  fixDescription: string;
  /** Whether this is the final proven iteration */
  proven: boolean;
  /** Optional: input key-value pairs to show on expand */
  inputs?: Record<string, unknown>;
  /** Optional: code diff snippet to show on expand */
  codeDiff?: string;
}

interface CegisTimelineProps {
  iterations: CegisIteration[];
  className?: string;
}

// ---------------------------------------------------------------------------
// Helper: pretty-print a value
// ---------------------------------------------------------------------------

function prettyValue(v: unknown): string {
  if (v === null) return "null";
  if (v === undefined) return "undefined";
  if (typeof v === "string") return `"${v}"`;
  if (typeof v === "object") {
    try {
      return JSON.stringify(v);
    } catch {
      return String(v);
    }
  }
  return String(v);
}

// ---------------------------------------------------------------------------
// Single iteration node
// ---------------------------------------------------------------------------

interface IterationNodeProps {
  iteration: CegisIteration;
}

function IterationNode({ iteration }: IterationNodeProps) {
  const [expanded, setExpanded] = React.useState(false);
  const { proven, index, counterexampleLabel, fixDescription, inputs, codeDiff } =
    iteration;

  const nodeColor = proven ? "#F5B93A" : "#D4920A";
  const nodeBorder = proven ? "#FFD060" : "#D4920A";
  const nodeBg = proven ? "rgba(245,185,58,0.15)" : "rgba(212,146,10,0.1)";

  return (
    <div className="flex flex-col items-center flex-shrink-0" style={{ minWidth: 80 }}>
      {/* Circle node */}
      <motion.button
        className="relative flex items-center justify-center rounded-full border-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-1"
        style={{
          width: 36,
          height: 36,
          background: nodeBg,
          borderColor: nodeBorder,
          cursor: "pointer",
        }}
        onClick={() => setExpanded((v) => !v)}
        whileHover={{ scale: 1.1, boxShadow: `0 0 8px ${nodeColor}60` }}
        whileTap={{ scale: 0.95 }}
        transition={{ duration: 0.15 }}
        aria-label={`CEGIS iteration ${index}${proven ? " — PROVEN" : ""}`}
        aria-expanded={expanded}
      >
        {proven ? (
          <span
            style={{
              color: "#F5B93A",
              fontSize: 14,
              fontFamily: "var(--font-jetbrains-mono)",
              fontWeight: 600,
            }}
          >
            ✓
          </span>
        ) : (
          <span
            style={{
              color: nodeColor,
              fontSize: 11,
              fontFamily: "var(--font-jetbrains-mono)",
              fontWeight: 600,
            }}
          >
            {index}
          </span>
        )}

        {/* Amber pulse for non-proven */}
        {!proven && (
          <span
            className="absolute inset-0 rounded-full"
            style={{
              border: `1px solid ${nodeColor}`,
              opacity: 0.4,
              transform: "scale(1.3)",
              pointerEvents: "none",
            }}
            aria-hidden
          />
        )}
      </motion.button>

      {/* Labels below node */}
      <div className="mt-2 flex flex-col items-center gap-0.5 text-center" style={{ width: 80 }}>
        {proven ? (
          <span
            className="text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: "#F5B93A", fontFamily: "var(--font-jetbrains-mono)" }}
          >
            PROVEN ✓
          </span>
        ) : (
          <>
            <span
              className="text-[10px] leading-tight line-clamp-2"
              style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
            >
              {counterexampleLabel}
            </span>
            <span
              className="text-[10px] leading-tight line-clamp-2 mt-0.5"
              style={{ color: "#D4920A", fontFamily: "var(--font-geist-sans)" }}
            >
              {fixDescription}
            </span>
          </>
        )}
      </div>

      {/* Expanded detail panel */}
      <AnimatePresence>
        {expanded && (inputs || codeDiff) && (
          <motion.div
            initial={{ opacity: 0, height: 0, y: -4 }}
            animate={{ opacity: 1, height: "auto", y: 0 }}
            exit={{ opacity: 0, height: 0, y: -4 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="mt-2 w-full overflow-hidden rounded"
            style={{
              background: "#141109",
              border: "1px solid #2A2315",
              minWidth: 180,
            }}
          >
            <div className="p-2 space-y-2">
              {inputs && Object.keys(inputs).length > 0 && (
                <div>
                  <p
                    className="mb-1 text-[9px] uppercase tracking-widest"
                    style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
                  >
                    Inputs
                  </p>
                  <div className="space-y-0.5">
                    {Object.entries(inputs).map(([k, v]) => (
                      <div
                        key={k}
                        className="flex gap-1.5 text-[10px]"
                        style={{ fontFamily: "var(--font-jetbrains-mono)" }}
                      >
                        <span style={{ color: "#D4920A" }}>{k}</span>
                        <span style={{ color: "#9A8E78" }}>=</span>
                        <span style={{ color: "#F5F0E8" }}>{prettyValue(v)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {codeDiff && (
                <div>
                  <p
                    className="mb-1 text-[9px] uppercase tracking-widest"
                    style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
                  >
                    Fix
                  </p>
                  <pre
                    className="overflow-x-auto text-[10px] leading-relaxed whitespace-pre-wrap"
                    style={{
                      fontFamily: "var(--font-jetbrains-mono)",
                      color: "#F5F0E8",
                    }}
                  >
                    {codeDiff}
                  </pre>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CegisTimeline({ iterations, className }: CegisTimelineProps) {
  if (!iterations || iterations.length === 0) {
    return (
      <div
        className={cn("flex items-center justify-center py-4", className)}
        style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)", fontSize: 12 }}
      >
        No CEGIS iterations recorded
      </div>
    );
  }

  return (
    <div className={cn("w-full", className)}>
      <p
        className="mb-3 text-[10px] uppercase tracking-widest"
        style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
      >
        CEGIS Iterations
      </p>

      {/* Scroll container for many iterations */}
      <div className="overflow-x-auto pb-2">
        <div
          className="relative flex gap-0 items-start"
          style={{ minWidth: "max-content" }}
        >
          {iterations.map((iter, idx) => (
            <div
              key={iter.id}
              className="relative flex items-start"
              style={{ paddingRight: idx < iterations.length - 1 ? 48 : 0 }}
            >
              <IterationNode iteration={iter} />

              {/* Horizontal connector line */}
              {idx < iterations.length - 1 && (
                <div
                  className="absolute top-[17px]"
                  style={{
                    left: 36,
                    width: 48,
                    height: 2,
                    background: "#2A2315",
                    borderRadius: 1,
                  }}
                  aria-hidden
                />
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
