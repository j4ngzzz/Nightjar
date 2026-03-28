"use client";

/**
 * InvariantCard — single invariant with natural language description,
 * formal expression, stage badge, confidence, and origin badge.
 *
 * Color rules: amber/gold for pass states, warm red for fail, no green/purple.
 */

import * as React from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type InvariantTier = "pbt" | "formal" | "both";
export type InvariantOrigin = "spec" | "immune" | "lifted";

export interface InvariantData {
  id: string;
  /** Natural language description shown to the user */
  description: string;
  /** Formal expression, e.g. "forall x :: f(x) >= 0" */
  formalExpression: string;
  tier: InvariantTier;
  origin: InvariantOrigin;
  /** 0–100 */
  confidence: number;
}

interface InvariantCardProps {
  invariant: InvariantData;
  className?: string;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function TierBadge({ tier }: { tier: InvariantTier }) {
  if (tier === "pbt") {
    return (
      <span
        className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
        style={{ background: "#A87020", color: "#0D0B09" }}
      >
        PBT
      </span>
    );
  }
  if (tier === "formal") {
    return (
      <span
        className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
        style={{ background: "#F5B93A", color: "#0D0B09" }}
      >
        Formal
      </span>
    );
  }
  // "both"
  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
      style={{
        background: "linear-gradient(90deg, #A87020 0%, #F5B93A 100%)",
        color: "#0D0B09",
      }}
    >
      Both
    </span>
  );
}

function OriginBadge({ origin }: { origin: InvariantOrigin }) {
  const styles: Record<InvariantOrigin, React.CSSProperties> = {
    spec: { background: "#2A2315", color: "#D4920A", border: "1px solid #4A3A1A" },
    immune: { background: "#1A1408", color: "#9A8E78", border: "1px solid #2A2315" },
    lifted: { background: "#1A1408", color: "#9A8E78", border: "1px solid #2A2315" },
  };

  return (
    <span
      className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wider"
      style={styles[origin]}
    >
      {origin}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function InvariantCard({ invariant, className }: InvariantCardProps) {
  const { description, formalExpression, tier, origin, confidence } = invariant;

  return (
    <motion.div
      className={cn("relative rounded-md p-3 cursor-default select-none", className)}
      style={{
        background: "#141109",
        border: "1px solid #2A2315",
      }}
      whileHover={{
        // Note: motion cannot tween between a hex and a gradient string — this
        // is an intentional instant switch on hover entry/exit, not an animation.
        background:
          "radial-gradient(ellipse at 50% 0%, rgba(212,146,10,0.06) 0%, #141109 70%)",
        borderColor: "#4A3A1A",
      }}
      transition={{ duration: 0.18 }}
    >
      {/* Natural language description */}
      <p
        className="mb-2 text-[14px] leading-snug"
        style={{
          fontFamily: "var(--font-geist-sans)",
          fontWeight: 400,
          color: "#F5F0E8",
        }}
      >
        {description}
      </p>

      {/* Formal expression */}
      <pre
        className="mb-3 overflow-x-auto rounded px-2 py-1 text-[12px] leading-relaxed whitespace-pre-wrap break-all"
        style={{
          fontFamily: "var(--font-jetbrains-mono)",
          color: "#D4920A",
          background: "rgba(212,146,10,0.05)",
          border: "1px solid #2A2315",
        }}
      >
        {formalExpression}
      </pre>

      {/* Footer row: badges + confidence */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5">
          <TierBadge tier={tier} />
          <OriginBadge origin={origin} />
        </div>

        <span
          className="text-[11px] tabular-nums"
          style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
        >
          {confidence}% conf
        </span>
      </div>
    </motion.div>
  );
}
