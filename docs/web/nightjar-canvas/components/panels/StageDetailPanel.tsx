"use client";

/**
 * StageDetailPanel — right-side detail panel for a verification stage.
 *
 * Slides in from the right (x: 320 → 0) when a stage node is clicked.
 * Width: 320px.
 *
 * Contains:
 * 1. Stage name + status badge
 * 2. Scrollable log output (streaming log lines with slide+fade animation)
 * 3. Findings count + invariants proven count
 * 4. List of InvariantCard components
 * 5. CounterexampleDisplay if stage failed
 * 6. CegisTimeline if CEGIS data present
 * 7. "Explain this" button → ProofExplanation streaming
 */

import * as React from "react";
import { motion, AnimatePresence } from "motion/react";
import { cn } from "@/lib/cn";
import { InvariantCard, type InvariantData } from "./InvariantCard";
import { CounterexampleDisplay, type CounterexampleData } from "./CounterexampleDisplay";
import { CegisTimeline, type CegisIteration } from "./CegisTimeline";
import { ProofExplanation } from "./ProofExplanation";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type StageStatus =
  | "pending"
  | "running"
  | "pbt_pass"
  | "formal_pass"
  | "proven"
  | "failed";

export interface StageLogLine {
  id: string;
  text: string;
  level?: "info" | "warn" | "error";
  ts?: number;
}

export interface StageDetailData {
  stageName: string;
  status: StageStatus;
  logs: StageLogLine[];
  invariants: InvariantData[];
  findingsCount: number;
  invariantsProvenCount: number;
  counterexample?: CounterexampleData;
  cegisIterations?: CegisIteration[];
  runId?: string;
}

interface StageDetailPanelProps {
  stage: StageDetailData | null;
  onClose: () => void;
  className?: string;
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_LABELS: Record<StageStatus, string> = {
  pending: "PENDING",
  running: "RUNNING",
  pbt_pass: "PBT PASS",
  formal_pass: "FORMAL",
  proven: "PROVEN",
  failed: "FAILED",
};

const STATUS_COLORS: Record<StageStatus, { bg: string; text: string; border: string }> = {
  pending: { bg: "#3A2E10", text: "#9A8E78", border: "#3A2E10" },
  running: { bg: "rgba(212,146,10,0.15)", text: "#D4920A", border: "#D4920A" },
  pbt_pass: { bg: "rgba(168,112,32,0.2)", text: "#A87020", border: "#A87020" },
  formal_pass: { bg: "rgba(245,185,58,0.2)", text: "#F5B93A", border: "#F5B93A" },
  proven: { bg: "rgba(255,208,96,0.2)", text: "#FFD060", border: "#FFD060" },
  failed: { bg: "rgba(200,75,47,0.15)", text: "#C84B2F", border: "#C84B2F" },
};

function StatusBadge({ status }: { status: StageStatus }) {
  const c = STATUS_COLORS[status];
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
      style={{
        background: c.bg,
        color: c.text,
        border: `1px solid ${c.border}`,
        fontFamily: "var(--font-jetbrains-mono)",
      }}
    >
      {status === "running" && (
        <motion.span
          animate={{ opacity: [1, 0.3, 1] }}
          transition={{ duration: 1.2, repeat: Infinity }}
          className="mr-1.5 h-1.5 w-1.5 rounded-full flex-shrink-0"
          style={{ background: "#D4920A" }}
          aria-hidden
        />
      )}
      {STATUS_LABELS[status]}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Log virtualization constants
// ---------------------------------------------------------------------------

/**
 * When log count exceeds this threshold, switch from animated motion.div
 * rendering to a simple fixed-height windowed list. This prevents layout
 * thrashing and animation overhead with 500+ log lines.
 */
const LOG_VIRTUALIZE_THRESHOLD = 500;

/** Fixed row height in px — must match the row height in VirtualLogList */
const LOG_ROW_HEIGHT = 20;

/** Visible container height in px — matches maxHeight on the log container */
const LOG_PANEL_HEIGHT = 160;

/** Extra rows rendered above/below visible window to prevent pop-in */
const LOG_OVERSCAN = 5;

// ---------------------------------------------------------------------------
// Log line with slide+fade animation (used when < LOG_VIRTUALIZE_THRESHOLD)
// ---------------------------------------------------------------------------

interface LogLineProps {
  line: StageLogLine;
  index: number;
}

function LogLine({ line, index }: LogLineProps) {
  const textColor =
    line.level === "error"
      ? "#C84B2F"
      : line.level === "warn"
      ? "#D4920A"
      : "#9A8E78";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.15,
        ease: [0, 0, 0.4, 1], // ease-out
        delay: Math.min(index * 0.04, 0.6), // 40ms stagger, capped at 600ms
      }}
      className="flex items-start gap-2 leading-relaxed"
    >
      {line.ts !== undefined && (
        <span
          className="flex-shrink-0 tabular-nums select-none"
          style={{
            color: "#6E6860",
            fontFamily: "var(--font-jetbrains-mono)",
            fontSize: 10,
            minWidth: "4ch",
          }}
        >
          {new Date(line.ts * 1000).toISOString().slice(11, 19)}
        </span>
      )}
      <span
        style={{
          color: textColor,
          fontFamily: "var(--font-jetbrains-mono)",
          fontSize: 12,
          wordBreak: "break-all",
        }}
      >
        {line.text}
      </span>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// VirtualLogList — windowed renderer for 500+ log lines.
//
// No external dependency. A fixed-height scroll container wraps a tall inner
// div (height = total rows * LOG_ROW_HEIGHT). Only rows in the current scroll
// viewport — plus LOG_OVERSCAN rows above/below — are mounted. Each row is
// absolutely positioned at top = rowIndex * LOG_ROW_HEIGHT.
//
// On each scroll event, scrollTop is captured in state; React re-renders only
// the changed slice. Overscan prevents pop-in during fast scrolling.
// ---------------------------------------------------------------------------

interface VirtualLogListProps {
  logs: StageLogLine[];
  /** Changing this value triggers a scroll-to-bottom (pass logs.length) */
  scrollToBottomDep?: number;
}

function VirtualLogList({ logs, scrollToBottomDep }: VirtualLogListProps) {
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = React.useState(0);

  // Auto-scroll to bottom whenever new lines arrive.
  // scrollToBottomDep (= logs.length) is the sole dep; containerRef is a
  // stable ref object and intentionally omitted per React ref conventions.
  React.useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [scrollToBottomDep]);

  const handleScroll = React.useCallback(
    (e: React.UIEvent<HTMLDivElement>) => {
      setScrollTop((e.currentTarget as HTMLDivElement).scrollTop);
    },
    []
  );

  const totalHeight = logs.length * LOG_ROW_HEIGHT;
  const visibleStart = Math.max(
    0,
    Math.floor(scrollTop / LOG_ROW_HEIGHT) - LOG_OVERSCAN
  );
  const visibleEnd = Math.min(
    logs.length,
    Math.ceil((scrollTop + LOG_PANEL_HEIGHT) / LOG_ROW_HEIGHT) + LOG_OVERSCAN
  );

  const visibleLogs = logs.slice(visibleStart, visibleEnd);

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      // aria-live intentionally omitted — screen readers must not announce
      // DOM mutations caused by scroll-driven virtualization. The parent
      // section heading already identifies this region to AT users.
      aria-label="Stage log output"
      role="log"
      style={{
        height: LOG_PANEL_HEIGHT,
        overflowY: "scroll",
        position: "relative",
      }}
    >
      {/* Spacer gives the container its full scrollable height */}
      <div style={{ height: totalHeight, position: "relative" }}>
        {visibleLogs.map((line, i) => {
          const rowIndex = visibleStart + i;
          const textColor =
            line.level === "error"
              ? "#C84B2F"
              : line.level === "warn"
              ? "#D4920A"
              : "#9A8E78";

          return (
            <div
              key={line.id}
              style={{
                position: "absolute",
                top: rowIndex * LOG_ROW_HEIGHT,
                left: 0,
                right: 0,
                height: LOG_ROW_HEIGHT,
                display: "flex",
                alignItems: "center",
                gap: 8,
                overflow: "hidden",
              }}
            >
              {line.ts !== undefined && (
                <span
                  className="flex-shrink-0 tabular-nums select-none"
                  style={{
                    color: "#6E6860",
                    fontFamily: "var(--font-jetbrains-mono)",
                    fontSize: 10,
                    minWidth: "4ch",
                  }}
                >
                  {new Date(line.ts * 1000).toISOString().slice(11, 19)}
                </span>
              )}
              <span
                style={{
                  color: textColor,
                  fontFamily: "var(--font-jetbrains-mono)",
                  fontSize: 12,
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {line.text}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section heading
// ---------------------------------------------------------------------------

function SectionHeading({ children }: { children: React.ReactNode }) {
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
// Close button
// ---------------------------------------------------------------------------

const CloseButton = React.forwardRef<HTMLButtonElement, { onClick: () => void }>(
  function CloseButton({ onClick }, ref) {
    return (
      <button
        ref={ref}
        onClick={onClick}
        className={[
          "flex h-6 w-6 items-center justify-center rounded transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4920A]",
          "focus-visible:ring-offset-1 focus-visible:ring-offset-[#0D0B09]",
        ].join(" ")}
        style={{ color: "#9A8E78" }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "#F5F0E8";
          (e.currentTarget as HTMLButtonElement).style.background = "rgba(212,146,10,0.1)";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color = "#9A8E78";
          (e.currentTarget as HTMLButtonElement).style.background = "transparent";
        }}
        aria-label="Close stage detail panel"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
          <path
            d="M1 1L11 11M11 1L1 11"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </button>
    );
  }
);

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function StageDetailPanel({
  stage,
  onClose,
  className,
}: StageDetailPanelProps) {
  const logsEndRef = React.useRef<HTMLDivElement>(null);
  const closeButtonRef = React.useRef<HTMLButtonElement>(null);
  const [showExplanation, setShowExplanation] = React.useState(false);

  // Reset explanation when stage changes
  React.useEffect(() => {
    setShowExplanation(false);
  }, [stage?.stageName]);

  // Auto-scroll logs to bottom when new lines arrive
  React.useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [stage?.logs.length]);

  // Move focus into the panel when it opens, restore on close
  React.useEffect(() => {
    if (stage && closeButtonRef.current) {
      closeButtonRef.current.focus();
    }
  }, [stage?.stageName]);

  // Keyboard: Escape closes the panel
  React.useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && stage) {
        onClose();
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [stage, onClose]);

  const hasFailed = stage?.status === "failed";
  const hasCounterexample = hasFailed && Boolean(stage?.counterexample);
  const hasCegis =
    stage?.cegisIterations && stage.cegisIterations.length > 0;

  return (
    <AnimatePresence>
      {stage && (
        <>
          {/* Backdrop for mobile / touch close */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-30 md:hidden"
            style={{ background: "rgba(0,0,0,0.5)" }}
            onClick={onClose}
            aria-hidden
          />

          {/* Panel */}
          <motion.aside
            key="panel"
            initial={{ x: 320, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 320, opacity: 0 }}
            transition={{
              type: "tween",
              duration: 0.22,
              ease: [0.16, 1, 0.3, 1],
            }}
            className={cn(
              "fixed right-0 top-0 bottom-0 z-40 flex flex-col overflow-hidden",
              className
            )}
            style={{
              width: 320,
              background: "#0D0B09",
              borderLeft: "1px solid #2A2315",
            }}
            role="complementary"
            aria-label={`Stage detail: ${stage.stageName}`}
            aria-modal="false"
          >
            {/* ── Header ───────────────────────────────────────────────── */}
            <div
              className="flex items-center justify-between gap-2 px-4 py-3 flex-shrink-0"
              style={{ borderBottom: "1px solid #2A2315" }}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span
                  className="truncate text-[13px] font-semibold"
                  style={{
                    color: "#F5F0E8",
                    fontFamily: "var(--font-jetbrains-mono)",
                    letterSpacing: "0.02em",
                  }}
                >
                  {stage.stageName}
                </span>
                <StatusBadge status={stage.status} />
              </div>
              <CloseButton ref={closeButtonRef} onClick={onClose} />
            </div>

            {/* ── Scrollable body ───────────────────────────────────────── */}
            <div
              className="flex-1 overflow-y-auto px-4 py-4 space-y-6 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4920A] focus-visible:ring-inset"
              tabIndex={0}
              aria-label="Stage detail content"
            >

              {/* Stats row */}
              <div className="grid grid-cols-2 gap-2">
                <div
                  className="rounded p-2.5"
                  style={{ background: "#141109", border: "1px solid #2A2315" }}
                >
                  <p
                    className="text-[10px] uppercase tracking-wider mb-0.5"
                    style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
                  >
                    Findings
                  </p>
                  <p
                    className="text-[20px] font-semibold tabular-nums"
                    style={{ color: "#D4920A", fontFamily: "var(--font-jetbrains-mono)" }}
                  >
                    {stage.findingsCount}
                  </p>
                </div>
                <div
                  className="rounded p-2.5"
                  style={{ background: "#141109", border: "1px solid #2A2315" }}
                >
                  <p
                    className="text-[10px] uppercase tracking-wider mb-0.5"
                    style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
                  >
                    Proven
                  </p>
                  <p
                    className="text-[20px] font-semibold tabular-nums"
                    style={{ color: "#F5B93A", fontFamily: "var(--font-jetbrains-mono)" }}
                  >
                    {stage.invariantsProvenCount}
                  </p>
                </div>
              </div>

              {/* Log output */}
              {stage.logs.length > 0 && (
                <div>
                  <SectionHeading>
                    Log Output
                    {stage.logs.length > LOG_VIRTUALIZE_THRESHOLD && (
                      <span
                        className="ml-2 normal-case font-normal"
                        style={{ color: "#6E6860" }}
                      >
                        ({stage.logs.length} lines)
                      </span>
                    )}
                  </SectionHeading>
                  <div
                    className="rounded px-3 py-2.5"
                    style={{
                      background: "#141109",
                      border: "1px solid #2A2315",
                    }}
                  >
                    {stage.logs.length > LOG_VIRTUALIZE_THRESHOLD ? (
                      // Windowed virtual list — only renders visible rows.
                      // Handles 1000+ lines without animation overhead.
                      <VirtualLogList
                        logs={stage.logs}
                        scrollToBottomDep={stage.logs.length}
                      />
                    ) : (
                      // Animated list for smaller log sets.
                      // maxHeight matches LOG_PANEL_HEIGHT — single source of truth.
                      <div
                        className="overflow-y-auto space-y-0.5"
                        style={{ maxHeight: LOG_PANEL_HEIGHT }}
                        aria-live="polite"
                        aria-label="Stage log output"
                        role="log"
                      >
                        {stage.logs.map((line, idx) => (
                          <LogLine key={line.id} line={line} index={idx} />
                        ))}
                        <div ref={logsEndRef} />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Counterexample (failed stages) */}
              {hasCounterexample && stage.counterexample && (
                <div>
                  <SectionHeading>Counterexample</SectionHeading>
                  <CounterexampleDisplay data={stage.counterexample} />
                </div>
              )}

              {/* CEGIS Timeline */}
              {hasCegis && stage.cegisIterations && (
                <div>
                  <CegisTimeline iterations={stage.cegisIterations} />
                </div>
              )}

              {/* Invariants */}
              {stage.invariants.length > 0 && (
                <div>
                  <SectionHeading>
                    Invariants ({stage.invariants.length})
                  </SectionHeading>
                  <div className="space-y-2">
                    {stage.invariants.map((inv) => (
                      <InvariantCard key={inv.id} invariant={inv} />
                    ))}
                  </div>
                </div>
              )}

              {/* LLM Explanation */}
              <div>
                <SectionHeading>Explanation</SectionHeading>
                <ProofExplanation
                  runId={stage.runId}
                  stageName={stage.stageName}
                  autoStream={showExplanation}
                  showTriggerButton={false}
                  mockText={
                    !stage.runId
                      ? `Stage "${stage.stageName}" completed with status ${stage.status}. ` +
                        `${stage.invariantsProvenCount} invariant${stage.invariantsProvenCount !== 1 ? "s" : ""} proven` +
                        ` across ${stage.findingsCount} finding${stage.findingsCount !== 1 ? "s" : ""}. ` +
                        (hasFailed
                          ? "A counterexample was found that violates the specified invariants. The CEGIS loop will attempt to repair the implementation."
                          : "All property-based tests and formal checks passed for this stage.")
                      : undefined
                  }
                />
              </div>

              {/* Spacer so last item isn't flush against bottom */}
              <div className="h-4" />
            </div>

            {/* ── Footer: Explain button ────────────────────────────────── */}
            {!showExplanation && (
              <div
                className="flex-shrink-0 px-4 py-3"
                style={{ borderTop: "1px solid #2A2315" }}
              >
                <button
                  className={[
                    "w-full rounded px-3 py-2 text-[12px] font-medium transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4920A]",
                    "focus-visible:ring-offset-1 focus-visible:ring-offset-[#0D0B09]",
                  ].join(" ")}
                  style={{
                    background: "rgba(212,146,10,0.1)",
                    border: "1px solid #D4920A",
                    color: "#D4920A",
                    fontFamily: "var(--font-geist-sans)",
                    cursor: "pointer",
                  }}
                  onClick={() => setShowExplanation(true)}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background =
                      "rgba(212,146,10,0.18)";
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLButtonElement).style.background =
                      "rgba(212,146,10,0.1)";
                  }}
                  aria-label={`Explain stage ${stage.stageName}`}
                >
                  ◈ Explain this stage
                </button>
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
