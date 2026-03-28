"use client";

/**
 * CounterexamplePlayground — interactive counterexample editor.
 *
 * Left:  JSON editor (textarea, JetBrains Mono, amber border on focus)
 * Right: PlaygroundOutput — Expected / Actual columns
 *
 * Re-run → POST /api/runs/{id}/recheck with edited inputs
 * Output updates in real-time (optimistic: show loading state, then result).
 *
 * Color rules: amber palette, warm red #C84B2F for failures, NO green/purple.
 */

import * as React from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/cn";
import { PlaygroundOutput, PlaygroundOutputData } from "./PlaygroundOutput";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CounterexamplePlaygroundProps {
  runId: string;
  /** Initial counterexample inputs (shown in the editor on first render). */
  initialInputs: Record<string, unknown>;
  /** Initial output data (pre-populated from the last verification run). */
  initialOutput?: PlaygroundOutputData | null;
  className?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function tryParseJSON(text: string): { ok: true; value: unknown } | { ok: false; error: string } {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) };
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PanelLabel({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="mb-2 text-[10px] uppercase tracking-widest"
      style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
    >
      {children}
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function CounterexamplePlayground({
  runId,
  initialInputs,
  initialOutput = null,
  className,
}: CounterexamplePlaygroundProps) {
  const [editorValue, setEditorValue] = React.useState<string>(
    JSON.stringify(initialInputs, null, 2)
  );
  const [parseError, setParseError] = React.useState<string>("");
  const [loading, setLoading] = React.useState(false);
  const [output, setOutput] = React.useState<PlaygroundOutputData | null>(
    initialOutput
  );
  const [fetchError, setFetchError] = React.useState<string>("");
  const [focused, setFocused] = React.useState(false);

  function handleEditorChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const val = e.target.value;
    setEditorValue(val);
    const parsed = tryParseJSON(val);
    if (parsed.ok) {
      setParseError("");
    } else {
      setParseError(parsed.error);
    }
  }

  async function handleRerun() {
    const parsed = tryParseJSON(editorValue);
    if (!parsed.ok) {
      setParseError(parsed.error);
      return;
    }

    setLoading(true);
    setFetchError("");

    try {
      const res = await fetch(
        `/api/runs/${encodeURIComponent(runId)}/recheck`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ inputs: parsed.value }),
        }
      );

      if (!res.ok) {
        const text = await res.text().catch(() => res.statusText);
        throw new Error(`${res.status}: ${text}`);
      }

      const data = (await res.json()) as PlaygroundOutputData;
      setOutput(data);
    } catch (err) {
      setFetchError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const canRun = !parseError && !loading;

  return (
    <div
      className={cn("rounded-md overflow-hidden", className)}
      style={{
        background: "#141109",
        border: "1px solid #2A2315",
      }}
    >
      {/* Header bar */}
      <div
        className="flex items-center justify-between px-4 py-2.5"
        style={{ borderBottom: "1px solid #2A2315" }}
      >
        <div className="flex items-center gap-2">
          <span
            className="h-2 w-2 rounded-full flex-shrink-0"
            style={{ background: "#C84B2F" }}
            aria-hidden="true"
          />
          <span
            className="text-[11px] font-semibold uppercase tracking-wider"
            style={{
              color: "#C84B2F",
              fontFamily: "var(--font-jetbrains-mono)",
            }}
          >
            Counterexample Playground
          </span>
        </div>

        <motion.button
          onClick={handleRerun}
          disabled={!canRun}
          className={cn(
            "inline-flex items-center gap-2 rounded px-3 py-1.5 text-[11px] font-semibold",
            !canRun && "opacity-50 cursor-not-allowed"
          )}
          style={{
            background: canRun ? "#D4920A" : "#2A2315",
            color: canRun ? "#0D0B09" : "#9A8E78",
            fontFamily: "var(--font-jetbrains-mono)",
            transition: "background 0.15s",
          }}
          whileHover={canRun ? { background: "#F5B93A", transition: { duration: 0.12 } } : undefined}
          whileTap={canRun ? { scale: 0.97 } : undefined}
          transition={{ duration: 0.2 }}
          aria-label="Re-run verification with edited inputs"
        >
          {loading && (
            <span
              className="h-3 w-3 rounded-full border-2 border-current border-t-transparent animate-spin"
              aria-hidden="true"
            />
          )}
          {loading ? "Running…" : "Re-run"}
        </motion.button>
      </div>

      {/* Two-column body */}
      <div className="grid grid-cols-2 divide-x divide-[#2A2315] min-h-[280px]">
        {/* LEFT: JSON editor */}
        <div className="p-4 flex flex-col gap-2">
          <PanelLabel>Edit Inputs (JSON)</PanelLabel>

          <textarea
            className="flex-1 resize-none rounded px-3 py-2 text-[12px] leading-relaxed outline-none"
            style={{
              fontFamily: "var(--font-jetbrains-mono)",
              background: "#0D0B09",
              color: "#F0EBE3",
              border: `1px solid ${
                parseError
                  ? "#C84B2F"
                  : focused
                  ? "#D4920A"
                  : "#2A2315"
              }`,
              boxShadow: focused && !parseError ? "0 0 0 2px rgba(212,146,10,0.15)" : undefined,
              minHeight: "200px",
              transition: "border-color 0.15s, box-shadow 0.15s",
            }}
            value={editorValue}
            onChange={handleEditorChange}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            spellCheck={false}
            aria-label="JSON input editor"
            aria-invalid={!!parseError}
            aria-describedby={parseError ? "parse-error" : undefined}
          />

          {parseError && (
            <p
              id="parse-error"
              className="text-[11px] leading-snug"
              style={{
                color: "#C84B2F",
                fontFamily: "var(--font-jetbrains-mono)",
              }}
            >
              {parseError}
            </p>
          )}

          {fetchError && (
            <p
              className="text-[11px] leading-snug"
              style={{
                color: "#C84B2F",
                fontFamily: "var(--font-jetbrains-mono)",
              }}
            >
              Request failed: {fetchError}
            </p>
          )}
        </div>

        {/* RIGHT: Output */}
        <div className="p-4">
          <PanelLabel>Output</PanelLabel>
          <PlaygroundOutput data={output} loading={loading} />
        </div>
      </div>
    </div>
  );
}
