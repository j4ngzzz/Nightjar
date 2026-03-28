"use client";

/**
 * FixSuggestion — git-diff-style view for a spec fix.
 *
 * Removed lines: warm red  #C84B2F
 * Added lines:   amber     #D4920A  (NOT green)
 * "Apply this fix to spec" → POST /api/runs/{id}/apply-fix
 *
 * Color rules: NO green, NO purple.
 */

import * as React from "react";
import { motion, AnimatePresence } from "motion/react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DiffLine =
  | { type: "context"; text: string }
  | { type: "removed"; text: string }
  | { type: "added"; text: string };

export interface FixSuggestionData {
  /** Human-readable summary of what the fix does. */
  summary: string;
  /** The diff to display as an array of typed lines. */
  diff: DiffLine[];
}

interface FixSuggestionProps {
  runId: string;
  fix: FixSuggestionData;
  className?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function linePrefix(type: DiffLine["type"]): string {
  if (type === "removed") return "-";
  if (type === "added") return "+";
  return " ";
}

function lineStyle(type: DiffLine["type"]): React.CSSProperties {
  if (type === "removed") {
    return {
      background: "rgba(200,75,47,0.12)",
      color: "#C84B2F",
      borderLeft: "2px solid #C84B2F",
    };
  }
  if (type === "added") {
    return {
      background: "rgba(212,146,10,0.10)",
      color: "#D4920A",
      borderLeft: "2px solid #D4920A",
    };
  }
  return {
    color: "#9A8E78",
    borderLeft: "2px solid transparent",
  };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface DiffViewProps {
  diff: DiffLine[];
}

function DiffView({ diff }: DiffViewProps) {
  return (
    <div
      className="overflow-auto rounded text-[11px] leading-relaxed"
      style={{
        background: "#0D0B09",
        border: "1px solid #2A2315",
        fontFamily: "var(--font-jetbrains-mono)",
      }}
    >
      {diff.map((line, idx) => (
        <div
          key={idx}
          className="flex items-start gap-3 px-3 py-0.5"
          style={lineStyle(line.type)}
        >
          {/* Gutter: line number + prefix symbol */}
          <span
            className="flex-shrink-0 select-none w-6 text-right opacity-50"
            aria-hidden="true"
          >
            {idx + 1}
          </span>
          <span className="flex-shrink-0 select-none w-3" aria-hidden="true">
            {linePrefix(line.type)}
          </span>
          <span className="whitespace-pre-wrap break-all">{line.text}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

type ApplyState = "idle" | "loading" | "success" | "error";

export function FixSuggestion({ runId, fix, className }: FixSuggestionProps) {
  const [applyState, setApplyState] = React.useState<ApplyState>("idle");
  const [errorMessage, setErrorMessage] = React.useState<string>("");

  async function handleApply() {
    setApplyState("loading");
    setErrorMessage("");
    try {
      const res = await fetch(`/api/runs/${encodeURIComponent(runId)}/apply-fix`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ diff: fix.diff }),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => res.statusText);
        throw new Error(`${res.status}: ${text}`);
      }
      setApplyState("success");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
      setApplyState("error");
    }
  }

  return (
    <div
      className={cn("rounded-md space-y-3 p-4", className)}
      style={{
        background: "#141109",
        border: "1px solid #2A2315",
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        <span
          className="h-2 w-2 rounded-full flex-shrink-0"
          style={{ background: "#D4920A" }}
          aria-hidden="true"
        />
        <span
          className="text-[11px] font-semibold uppercase tracking-wider"
          style={{
            color: "#D4920A",
            fontFamily: "var(--font-jetbrains-mono)",
          }}
        >
          Suggested Fix
        </span>
      </div>

      {/* Summary */}
      <p
        className="text-[13px] leading-snug"
        style={{ color: "#F0EBE3", fontFamily: "var(--font-geist-sans)" }}
      >
        {fix.summary}
      </p>

      {/* Diff view */}
      <DiffView diff={fix.diff} />

      {/* Apply button + feedback */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <motion.button
          onClick={handleApply}
          disabled={applyState === "loading" || applyState === "success"}
          className={cn(
            "inline-flex items-center gap-2 rounded px-3 py-1.5 text-[12px] font-semibold transition-opacity",
            (applyState === "loading" || applyState === "success") &&
              "opacity-60 cursor-not-allowed"
          )}
          style={{
            background: "#D4920A",
            color: "#0D0B09",
            fontFamily: "var(--font-jetbrains-mono)",
          }}
          whileHover={
            applyState === "idle"
              ? { background: "#F5B93A", transition: { duration: 0.12 } }
              : undefined
          }
          whileTap={applyState === "idle" ? { scale: 0.97 } : undefined}
          transition={{ duration: 0.2 }}
        >
          {applyState === "loading" && (
            <span
              className="h-3 w-3 rounded-full border-2 border-current border-t-transparent animate-spin"
              aria-hidden="true"
            />
          )}
          {applyState === "loading"
            ? "Applying…"
            : applyState === "success"
            ? "Applied"
            : "Apply this fix to spec"}
        </motion.button>

        <AnimatePresence>
          {applyState === "success" && (
            <motion.span
              key="success"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="text-[11px]"
              style={{
                color: "#D4920A",
                fontFamily: "var(--font-jetbrains-mono)",
              }}
            >
              Spec updated. Regenerate to verify.
            </motion.span>
          )}
          {applyState === "error" && (
            <motion.span
              key="error"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="text-[11px]"
              style={{
                color: "#C84B2F",
                fontFamily: "var(--font-jetbrains-mono)",
              }}
            >
              {errorMessage || "Failed to apply fix."}
            </motion.span>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
