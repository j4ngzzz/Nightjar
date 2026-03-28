"use client";

/**
 * CounterexampleDisplay — shows a failing counterexample from verification.
 *
 * Displays:
 * - Input key-value pairs that triggered the failure
 * - The invariant that was violated (highlighted in warm red)
 * - Expected vs Actual output side-by-side
 */

import * as React from "react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CounterexampleData {
  /** Input variable name → value pairs that triggered the failure */
  inputs: Record<string, unknown>;
  /** The invariant expression that was violated */
  violatedInvariant: string;
  /** Expected output value / description */
  expected: unknown;
  /** Actual output value / description */
  actual: unknown;
}

interface CounterexampleDisplayProps {
  data: CounterexampleData;
  className?: string;
}

// ---------------------------------------------------------------------------
// Helper: pretty-print an unknown value
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

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

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

function MonoBlock({
  children,
  highlight,
}: {
  children: React.ReactNode;
  highlight?: boolean;
}) {
  return (
    <pre
      className="overflow-x-auto rounded px-2 py-1.5 text-[11px] leading-relaxed whitespace-pre-wrap break-all"
      style={{
        fontFamily: "var(--font-jetbrains-mono)",
        background: highlight ? "rgba(200,75,47,0.08)" : "rgba(212,146,10,0.04)",
        border: `1px solid ${highlight ? "rgba(200,75,47,0.3)" : "#2A2315"}`,
        color: highlight ? "#C84B2F" : "#F5F0E8",
      }}
    >
      {children}
    </pre>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CounterexampleDisplay({
  data,
  className,
}: CounterexampleDisplayProps) {
  const { inputs, violatedInvariant, expected, actual } = data;
  const inputEntries = Object.entries(inputs);

  return (
    <div
      className={cn("rounded-md p-4 space-y-4", className)}
      style={{
        background: "#141109",
        border: "1px solid #4A3A1A",
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        <span
          className="h-2 w-2 rounded-full flex-shrink-0"
          style={{ background: "#C84B2F" }}
          aria-hidden="true"
        />
        <span
          className="text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: "#C84B2F", fontFamily: "var(--font-jetbrains-mono)" }}
        >
          Counterexample Found
        </span>
      </div>

      {/* Inputs */}
      <div>
        <SectionLabel>Inputs</SectionLabel>
        <div className="space-y-1">
          {inputEntries.length === 0 ? (
            <span className="text-[11px]" style={{ color: "#9A8E78" }}>
              No inputs captured
            </span>
          ) : (
            inputEntries.map(([key, value]) => (
              <div
                key={key}
                className="flex items-start gap-2 rounded px-2 py-1"
                style={{ background: "rgba(212,146,10,0.04)" }}
              >
                <span
                  className="flex-shrink-0 text-[11px] font-semibold"
                  style={{
                    color: "#D4920A",
                    fontFamily: "var(--font-jetbrains-mono)",
                  }}
                >
                  {key}
                </span>
                <span
                  className="text-[11px]"
                  style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
                >
                  =
                </span>
                <span
                  className="break-all text-[11px]"
                  style={{
                    color: "#F5F0E8",
                    fontFamily: "var(--font-jetbrains-mono)",
                  }}
                >
                  {prettyPrint(value)}
                </span>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Violated invariant */}
      <div>
        <SectionLabel>Violated Invariant</SectionLabel>
        <MonoBlock highlight>{violatedInvariant}</MonoBlock>
      </div>

      {/* Expected vs Actual */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <SectionLabel>Expected</SectionLabel>
          <MonoBlock>{prettyPrint(expected)}</MonoBlock>
        </div>
        <div>
          <SectionLabel>Actual</SectionLabel>
          <MonoBlock highlight>{prettyPrint(actual)}</MonoBlock>
        </div>
      </div>
    </div>
  );
}
