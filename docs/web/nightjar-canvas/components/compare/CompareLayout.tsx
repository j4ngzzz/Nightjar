"use client";

/**
 * Nightjar Verification Canvas — CompareLayout
 *
 * Side-by-side comparison of two verification runs.
 *
 * Layout:
 *   [Run A Panel] [central divider] [Run B Panel]
 *
 * - Each panel: run label + TrustGauge + static pipeline stage visualization
 * - Header: Trust Score delta ("▲ +7 points" or "▼ -3 points") with amber/red coloring
 * - Stages that changed status highlighted with amber border + pulse animation
 *
 * Color rules: amber palette only. Warm red (#C84B2F) for removals/failures.
 * No green, no purple.
 */

import { useMemo } from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/cn";
import { TrustGauge } from "@/components/metrics/TrustGauge";
import type { RunSnapshot, CanvasEvent } from "@/lib/api-client";
import { trustLevelToScore } from "@/lib/trust-score";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type StageStatus = "pending" | "pass" | "fail" | "skip";

/** Derived per-stage summary from a RunSnapshot. */
export interface StageSummary {
  name: string;
  label: string;
  status: StageStatus;
  duration?: string;
}

export interface CompareLayoutProps {
  /** Run A (left panel). */
  runA: RunSnapshot;
  /** Run B (right panel). */
  runB: RunSnapshot;
  /** Optional label override for run A (defaults to run_id slice). */
  labelA?: string;
  /** Optional label override for run B (defaults to run_id slice). */
  labelB?: string;
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STAGE_NAMES: Array<{ key: string; label: string }> = [
  { key: "preflight", label: "PREFLIGHT" },
  { key: "deps", label: "DEPS" },
  { key: "schema", label: "SCHEMA" },
  { key: "pbt", label: "PBT" },
  { key: "negation", label: "NEGATION" },
  { key: "formal", label: "FORMAL" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Derive a 0–100 trust score from a RunSnapshot.
 * Delegates to trustLevelToScore() from trust-score.ts so there is one
 * source of truth for threshold values, then scales to 0–100.
 */
function deriveTrustScore(run: RunSnapshot): number {
  return Math.round(trustLevelToScore(run.trust_level) * 100);
}

/** Extract stage statuses from the event log. */
function extractStageStatuses(
  events: CanvasEvent[]
): Record<string, StageStatus> {
  const result: Record<string, StageStatus> = {};

  for (const ev of events) {
    const stageName = ev.payload?.stage as string | undefined;
    if (!stageName) continue;

    if (ev.event_type === "stage_complete") {
      result[stageName] = "pass";
    } else if (ev.event_type === "stage_fail") {
      result[stageName] = "fail";
    } else if (ev.event_type === "stage_start" && !(stageName in result)) {
      result[stageName] = "pending";
    }
  }

  return result;
}

/** Build sorted stage summaries for a run. */
function buildStageSummaries(run: RunSnapshot): StageSummary[] {
  const statuses = extractStageStatuses(run.events ?? []);

  return STAGE_NAMES.map(({ key, label }) => {
    const status: StageStatus = statuses[key] ?? "pending";
    return { name: key, label, status };
  });
}

/** Short label from run_id (last 8 chars). */
function shortRunId(runId: string): string {
  return runId.slice(-8).toUpperCase();
}

// ---------------------------------------------------------------------------
// Delta header
// ---------------------------------------------------------------------------

interface DeltaHeaderProps {
  scoreA: number;
  scoreB: number;
}

function DeltaHeader({ scoreA, scoreB }: DeltaHeaderProps) {
  const delta = scoreB - scoreA;
  const abs = Math.abs(delta);

  let color: string;
  let labelText: string;

  if (delta === 0) {
    color = "#8B8579";
    labelText = `= 0 points`;
  } else if (delta > 0) {
    color = "#F5B93A";
    labelText = `▲ +${abs} point${abs !== 1 ? "s" : ""}`;
  } else {
    color = "#C84B2F";
    labelText = `▼ −${abs} point${abs !== 1 ? "s" : ""}`;
  }

  return (
    <div
      className="flex items-center justify-center gap-2 py-2"
      aria-label={`Trust score delta: ${delta >= 0 ? "+" : ""}${delta} points`}
    >
      <span
        className="text-sm font-semibold tabular-nums"
        style={{
          color,
          fontFamily: "var(--font-jetbrains-mono)",
          letterSpacing: "0.04em",
        }}
      >
        {labelText}
      </span>
      <span
        className="text-xs"
        style={{ color: "#8B8579", fontFamily: "var(--font-geist-sans)" }}
      >
        Run A → Run B
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stage pill (static pipeline visualization)
// ---------------------------------------------------------------------------

/** Module-level constant — avoids per-render allocation. */
const STAGE_PILL_COLORS: Record<
  StageStatus,
  { border: string; text: string; bg: string }
> = {
  pass: { border: "#D4920A", text: "#D4920A", bg: "rgba(212,146,10,0.1)" },
  fail: { border: "#C84B2F", text: "#C84B2F", bg: "rgba(200,75,47,0.1)" },
  pending: { border: "#3A2E10", text: "#8B8579", bg: "transparent" },
  skip: { border: "#3A2E10", text: "#6E6860", bg: "transparent" },
};

interface StagePillProps {
  label: string;
  status: StageStatus;
  /** Whether this stage changed status between the two runs. */
  changed: boolean;
}

function StagePill({ label, status, changed }: StagePillProps) {
  const c = STAGE_PILL_COLORS[status];

  if (changed) {
    return (
      <motion.div
        className="flex items-center justify-center rounded px-2 py-1 border text-[10px] font-semibold tracking-widest"
        style={{
          borderColor: "#D4920A",
          color: c.text,
          backgroundColor: "rgba(212,146,10,0.08)",
          fontFamily: "var(--font-jetbrains-mono)",
        }}
        animate={{
          boxShadow: [
            "0 0 0px rgba(212,146,10,0)",
            "0 0 8px rgba(212,146,10,0.5)",
            "0 0 0px rgba(212,146,10,0)",
          ],
        }}
        transition={{ duration: 1.8, repeat: Infinity, ease: "easeInOut" }}
        aria-label={`${label} — changed`}
      >
        {label}
      </motion.div>
    );
  }

  return (
    <div
      className="flex items-center justify-center rounded px-2 py-1 border text-[10px] font-semibold tracking-widest"
      style={{
        borderColor: c.border,
        color: c.text,
        backgroundColor: c.bg,
        fontFamily: "var(--font-jetbrains-mono)",
      }}
      aria-label={label}
    >
      {label}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Run panel
// ---------------------------------------------------------------------------

interface RunPanelProps {
  run: RunSnapshot;
  label: string;
  trustScore: number;
  stages: StageSummary[];
  /** Set of stage names that changed vs the other run. */
  changedStages: Set<string>;
  side: "left" | "right";
}

function RunPanel({
  run,
  label,
  trustScore,
  stages,
  changedStages,
  side,
}: RunPanelProps) {
  const alignClass = side === "left" ? "items-start" : "items-end";

  return (
    <div
      className={cn("flex flex-1 flex-col gap-4 p-5", alignClass)}
      style={{
        backgroundColor: "#141109",
        border: "1px solid #2A2315",
        borderRadius: "0.5rem",
        minWidth: 0,
      }}
      aria-label={`Run panel: ${label}`}
    >
      {/* Run label */}
      <div className="w-full flex flex-col gap-0.5">
        <span
          className="text-xs font-semibold tracking-widest"
          style={{
            color: "#8B8579",
            fontFamily: "var(--font-jetbrains-mono)",
            letterSpacing: "0.1em",
          }}
        >
          {side === "left" ? "RUN A" : "RUN B"}
        </span>
        <span
          className="text-sm font-medium truncate"
          style={{
            color: "#F0EBE3",
            fontFamily: "var(--font-jetbrains-mono)",
            maxWidth: "100%",
          }}
          title={run.run_id}
        >
          {label}
        </span>
        <span
          className="text-[10px]"
          style={{ color: "#6E6860", fontFamily: "var(--font-geist-sans)" }}
        >
          {run.spec_id ? `spec: ${run.spec_id}` : "no spec"}
          {" · "}
          {run.model ?? "unknown model"}
        </span>
      </div>

      {/* TrustGauge centered */}
      <div className="w-full flex justify-center">
        <TrustGauge score={trustScore} size={120} />
      </div>

      {/* Trust level label */}
      <div className="w-full flex justify-center">
        <span
          className="text-xs font-medium"
          style={{
            color: "#A87020",
            fontFamily: "var(--font-geist-sans)",
            letterSpacing: "0.04em",
          }}
        >
          {run.trust_level.replace(/_/g, " ")}
        </span>
      </div>

      {/* Pipeline stages */}
      <div
        className="w-full grid gap-1.5"
        style={{ gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}
        role="list"
        aria-label="Pipeline stages"
      >
        {stages.map((s) => (
          <div key={s.name} role="listitem">
            <StagePill
              label={s.label}
              status={s.status}
              changed={changedStages.has(s.name)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Central divider
// ---------------------------------------------------------------------------

function CentralDivider() {
  return (
    <div
      className="flex items-stretch justify-center"
      style={{ width: 1, flexShrink: 0, alignSelf: "stretch", minHeight: 200 }}
      aria-hidden
    >
      <div
        style={{
          width: 1,
          height: "100%",
          background:
            "linear-gradient(to bottom, transparent, #D4920A 20%, #D4920A 80%, transparent)",
          opacity: 0.4,
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// CompareLayout
// ---------------------------------------------------------------------------

/**
 * CompareLayout — side-by-side comparison of two verification runs.
 *
 * Renders:
 * - Delta header (trust score change, amber/red colored)
 * - Left panel: Run A label + TrustGauge + pipeline stages
 * - Central amber divider
 * - Right panel: Run B label + TrustGauge + pipeline stages
 *
 * Stages that changed status between runs get amber border + pulse animation.
 */
export function CompareLayout({
  runA,
  runB,
  labelA,
  labelB,
  className,
}: CompareLayoutProps) {
  const scoreA = useMemo(() => deriveTrustScore(runA), [runA]);
  const scoreB = useMemo(() => deriveTrustScore(runB), [runB]);

  const stagesA = useMemo(() => buildStageSummaries(runA), [runA]);
  const stagesB = useMemo(() => buildStageSummaries(runB), [runB]);

  /** Stage names where the status differs between the two runs. */
  const changedStages = useMemo<Set<string>>(() => {
    const changed = new Set<string>();
    for (const sa of stagesA) {
      const sb = stagesB.find((s) => s.name === sa.name);
      if (sb && sb.status !== sa.status) {
        changed.add(sa.name);
      }
    }
    return changed;
  }, [stagesA, stagesB]);

  const resolvedLabelA = labelA ?? shortRunId(runA.run_id);
  const resolvedLabelB = labelB ?? shortRunId(runB.run_id);

  return (
    <div
      className={cn("flex flex-col gap-3 w-full", className)}
      role="region"
      aria-label="Run comparison"
    >
      {/* Delta header */}
      <DeltaHeader scoreA={scoreA} scoreB={scoreB} />

      {/* Two-panel row */}
      <div className="flex flex-row gap-3 w-full items-stretch min-h-0">
        <RunPanel
          run={runA}
          label={resolvedLabelA}
          trustScore={scoreA}
          stages={stagesA}
          changedStages={changedStages}
          side="left"
        />

        <CentralDivider />

        <RunPanel
          run={runB}
          label={resolvedLabelB}
          trustScore={scoreB}
          stages={stagesB}
          changedStages={changedStages}
          side="right"
        />
      </div>
    </div>
  );
}
