"use client";

/**
 * PlaygroundOutput — side-by-side Expected / Actual columns.
 *
 * The violated invariant row is highlighted with warm red (#C84B2F).
 * No green, no purple — amber palette only.
 */

import * as React from "react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PlaygroundOutputData {
  /** The invariant expression that was violated (or null if none). */
  violatedInvariant: string | null;
  /** Expected output value (any JSON-serialisable value). */
  expected: unknown;
  /** Actual output value (any JSON-serialisable value). */
  actual: unknown;
}

interface PlaygroundOutputProps {
  data: PlaygroundOutputData | null;
  /** Show a pulsing skeleton while a re-check is in flight. */
  loading?: boolean;
  className?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function prettyPrint(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (typeof value === "string") return `"${value}"`;
  if (typeof value === "object") {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="mb-1.5 text-[10px] uppercase tracking-widest"
      style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
    >
      {children}
    </p>
  );
}

interface OutputBlockProps {
  value: unknown;
  highlight?: boolean;
}

function OutputBlock({ value, highlight }: OutputBlockProps) {
  return (
    <pre
      className="h-full min-h-[80px] overflow-auto rounded px-3 py-2 text-[12px] leading-relaxed whitespace-pre-wrap break-all"
      style={{
        fontFamily: "var(--font-jetbrains-mono)",
        background: highlight ? "rgba(200,75,47,0.10)" : "rgba(212,146,10,0.04)",
        border: `1px solid ${highlight ? "rgba(200,75,47,0.35)" : "#2A2315"}`,
        color: highlight ? "#C84B2F" : "#F5F0E8",
      }}
    >
      {prettyPrint(value)}
    </pre>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse rounded", className)}
      style={{ background: "#2A2315" }}
    />
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function PlaygroundOutput({
  data,
  loading = false,
  className,
}: PlaygroundOutputProps) {
  if (loading) {
    return (
      <div className={cn("space-y-3", className)}>
        <Skeleton className="h-4 w-28" />
        <div className="grid grid-cols-2 gap-3">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-12" />
      </div>
    );
  }

  if (!data) {
    return (
      <div
        className={cn(
          "flex items-center justify-center rounded-md p-6 text-[12px]",
          className
        )}
        style={{
          border: "1px dashed #2A2315",
          color: "#9A8E78",
          fontFamily: "var(--font-jetbrains-mono)",
        }}
      >
        Run a check to see output
      </div>
    );
  }

  const { violatedInvariant, expected, actual } = data;
  const hasMismatch = violatedInvariant !== null;

  return (
    <div className={cn("space-y-4", className)}>
      {/* Expected / Actual side-by-side */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <SectionLabel>Expected</SectionLabel>
          <OutputBlock value={expected} />
        </div>
        <div>
          <SectionLabel>Actual</SectionLabel>
          <OutputBlock value={actual} highlight={hasMismatch} />
        </div>
      </div>

      {/* Violated invariant */}
      {violatedInvariant && (
        <div>
          <SectionLabel>Violated Invariant</SectionLabel>
          <div
            className="flex items-start gap-2 rounded px-3 py-2"
            style={{
              background: "rgba(200,75,47,0.08)",
              border: "1px solid rgba(200,75,47,0.30)",
            }}
          >
            <span
              className="mt-0.5 h-2 w-2 flex-shrink-0 rounded-full"
              style={{ background: "#C84B2F" }}
              aria-hidden="true"
            />
            <pre
              className="overflow-x-auto text-[11px] leading-relaxed whitespace-pre-wrap break-all"
              style={{
                fontFamily: "var(--font-jetbrains-mono)",
                color: "#C84B2F",
              }}
            >
              {violatedInvariant}
            </pre>
          </div>
        </div>
      )}

      {/* Pass indicator */}
      {!violatedInvariant && (
        <div
          className="flex items-center gap-2 rounded px-3 py-2"
          style={{
            background: "rgba(212,146,10,0.06)",
            border: "1px solid #4A3A1A",
          }}
        >
          <span
            className="h-2 w-2 rounded-full flex-shrink-0"
            style={{ background: "#D4920A" }}
            aria-hidden="true"
          />
          <span
            className="text-[11px]"
            style={{
              color: "#D4920A",
              fontFamily: "var(--font-jetbrains-mono)",
            }}
          >
            All invariants satisfied
          </span>
        </div>
      )}
    </div>
  );
}
