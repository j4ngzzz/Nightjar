"use client";

/**
 * TrustScoreChart — AreaChart of trust score history with amber gradient fill.
 *
 * Features:
 * - Recharts AreaChart with amber gradient (#D4920A → #0D0B09)
 * - X-axis toggle: "30 runs" (last 30 verification runs) vs "30 days" (calendar days)
 * - Y-axis: 0–100
 * - Hover tooltip: run ID, timestamp, trust score, stage results
 * - Click on a data point: navigates to /run/{id}
 * - Accepts optional commit markers rendered as ReferenceLine overlays (used by
 *   CommitCorrelation to overlay vertical lines without re-implementing the chart)
 */

import * as React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { useRouter } from "next/navigation";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Stage result summary attached to a run entry. */
export interface StageResult {
  name: string;
  passed: boolean;
}

/** A single run data point for the chart. */
export interface RunDataPoint {
  /** UUID of the run. */
  runId: string;
  /** Unix timestamp (ms). */
  ts: number;
  /** Trust score 0–100. */
  score: number;
  /** Optional stage breakdown for tooltip. */
  stages?: StageResult[];
}

/** A commit marker to overlay as a vertical reference line. */
export interface CommitMarker {
  /** The x-axis key value this marker aligns to (runId or date string). */
  xValue: string;
  /** Short commit message for tooltip / label. */
  message: string;
  /** Unix timestamp (ms) of the commit. */
  ts: number;
}

export type XAxisMode = "runs" | "days";

export interface TrustScoreChartProps {
  /** Run data points — already sorted ascending by ts. */
  data: RunDataPoint[];
  /** Optional commit markers to overlay. */
  commitMarkers?: CommitMarker[];
  /** Initial x-axis mode (default: "runs"). */
  defaultMode?: XAxisMode;
  className?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const AMBER_LINE = "#D4920A";
const AMBER_FILL_TOP = "#D4920A";
const AMBER_FILL_BOTTOM = "#0D0B09";
const GRID_COLOR = "#2A2315";
const AXIS_TICK_COLOR = "#8B8579";
const COMMIT_LINE_COLOR = "#4A3A1A";

/** Format a unix ms timestamp as a full datetime string for the tooltip. */
function formatDateTime(ts: number): string {
  const d = new Date(ts);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Truncate a run ID to 8 chars for display. */
function shortId(runId: string): string {
  return runId.length > 8 ? runId.slice(0, 8) : runId;
}

// ---------------------------------------------------------------------------
// Aggregate by day: given sorted run points, produce one point per calendar
// day (using the best score of that day) for the "30 days" view.
// ---------------------------------------------------------------------------

interface DayPoint {
  /** ISO date string YYYY-MM-DD — used as the x key. */
  day: string;
  /** Best score that day. */
  score: number;
  /** Run ID of the best run that day. */
  runId: string;
  /** Timestamp of the best run that day. */
  ts: number;
  stages?: StageResult[];
}

function aggregateByDay(data: RunDataPoint[]): DayPoint[] {
  const byDay = new Map<string, DayPoint>();

  for (const pt of data) {
    const d = new Date(pt.ts);
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const existing = byDay.get(key);
    if (!existing || pt.score > existing.score) {
      byDay.set(key, {
        day: key,
        score: pt.score,
        runId: pt.runId,
        ts: pt.ts,
        stages: pt.stages,
      });
    }
  }

  // Sort ascending by day key (ISO string sort is lexicographically correct)
  return Array.from(byDay.values()).sort((a, b) =>
    a.day < b.day ? -1 : a.day > b.day ? 1 : 0
  );
}

// ---------------------------------------------------------------------------
// Custom Tooltip
// ---------------------------------------------------------------------------

interface TooltipPayloadEntry {
  payload: {
    runId: string;
    ts: number;
    score: number;
    stages?: StageResult[];
  };
  value: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}

function CustomTooltip({ active, payload }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  const pt = payload[0]?.payload;
  if (!pt) return null;

  return (
    <div
      className="rounded border px-3 py-2 text-xs shadow-lg"
      style={{
        background: "#141109",
        borderColor: "#2A2315",
        fontFamily: "var(--font-jetbrains-mono)",
        minWidth: 180,
      }}
    >
      {/* Score */}
      <div className="flex items-center justify-between gap-4 mb-1.5">
        <span style={{ color: "#9A8E78" }}>Trust Score</span>
        <span
          className="font-semibold tabular-nums"
          style={{ color: AMBER_LINE, fontSize: 14 }}
        >
          {pt.score}
        </span>
      </div>

      {/* Run ID */}
      <div className="flex items-center justify-between gap-4 mb-0.5">
        <span style={{ color: "#9A8E78" }}>Run</span>
        <span style={{ color: "#F0EBE3" }}>{shortId(pt.runId)}</span>
      </div>

      {/* Timestamp */}
      <div className="flex items-center justify-between gap-4 mb-1.5">
        <span style={{ color: "#9A8E78" }}>Time</span>
        <span style={{ color: "#F0EBE3" }}>{formatDateTime(pt.ts)}</span>
      </div>

      {/* Stage results */}
      {pt.stages && pt.stages.length > 0 && (
        <>
          <div
            className="mb-1 border-t pt-1.5"
            style={{ borderColor: "#2A2315" }}
          />
          <div className="space-y-0.5">
            {pt.stages.map((s) => (
              <div
                key={s.name}
                className="flex items-center justify-between gap-4"
              >
                <span style={{ color: "#9A8E78" }}>{s.name}</span>
                <span
                  style={{
                    color: s.passed ? "#A87020" : "#F85149",
                    fontWeight: 600,
                  }}
                >
                  {s.passed ? "PASS" : "FAIL"}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function TrustScoreChart({
  data,
  commitMarkers = [],
  defaultMode = "runs",
  className,
}: TrustScoreChartProps) {
  const router = useRouter();
  const [mode, setMode] = React.useState<XAxisMode>(defaultMode);

  // Slice to last 30 entries in either mode
  const runPoints = React.useMemo(() => data.slice(-30), [data]);
  const dayPoints = React.useMemo(
    () => aggregateByDay(data).slice(-30),
    [data]
  );

  // Active dataset based on mode
  const chartData = React.useMemo(
    () =>
      mode === "runs"
        ? runPoints.map((p) => ({ ...p, xKey: shortId(p.runId) }))
        : dayPoints.map((p) => ({
            runId: p.runId,
            ts: p.ts,
            score: p.score,
            stages: p.stages,
            xKey: p.day,
          })),
    [mode, runPoints, dayPoints]
  );

  // Commit markers mapped to xKey values for the current mode
  const activeMarkers = React.useMemo(() => {
    if (mode === "runs") {
      // Match commit ts to the nearest run xKey
      return commitMarkers.map((cm) => {
        // Find run closest in time
        let best = chartData[0];
        let bestDelta = Infinity;
        for (const pt of chartData) {
          const delta = Math.abs(pt.ts - cm.ts);
          if (delta < bestDelta) {
            bestDelta = delta;
            best = pt;
          }
        }
        return { ...cm, xValue: best?.xKey ?? cm.xValue };
      });
    }
    // Days mode: match commit ts to day bucket
    return commitMarkers.map((cm) => {
      const d = new Date(cm.ts);
      const dayKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      return { ...cm, xValue: dayKey };
    });
  }, [commitMarkers, chartData, mode]);

  // Handle click on area / chart — navigate to run page
  const handleClick = React.useCallback(
    (chartState: { activePayload?: Array<{ payload: { runId: string } }> }) => {
      const runId = chartState?.activePayload?.[0]?.payload?.runId;
      if (runId) {
        router.push(`/run/${runId}`);
      }
    },
    [router]
  );

  const gradientId = "trustScoreGradient";

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {/* Header row */}
      <div className="flex items-center justify-between">
        <span
          className="text-[11px] uppercase tracking-widest"
          style={{
            color: "#9A8E78",
            fontFamily: "var(--font-jetbrains-mono)",
          }}
        >
          Trust Score History
        </span>

        {/* Toggle */}
        <div
          className="flex rounded overflow-hidden"
          style={{ border: "1px solid #2A2315" }}
        >
          {(["runs", "days"] as XAxisMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className="px-2.5 py-1 text-[10px] uppercase tracking-wider transition-colors"
              style={{
                fontFamily: "var(--font-jetbrains-mono)",
                background: mode === m ? "#D4920A" : "#141109",
                color: mode === m ? "#0D0B09" : "#8B8579",
                border: "none",
                cursor: "pointer",
                fontWeight: mode === m ? 600 : 400,
              }}
              aria-pressed={mode === m}
            >
              {m === "runs" ? "30 Runs" : "30 Days"}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div style={{ width: "100%", height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={chartData}
            margin={{ top: 8, right: 8, left: -16, bottom: 0 }}
            onClick={handleClick}
            style={{ cursor: "pointer" }}
          >
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor={AMBER_FILL_TOP}
                  stopOpacity={0.55}
                />
                <stop
                  offset="100%"
                  stopColor={AMBER_FILL_BOTTOM}
                  stopOpacity={0.0}
                />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke={GRID_COLOR}
              vertical={false}
            />

            <XAxis
              dataKey="xKey"
              tick={{ fill: AXIS_TICK_COLOR, fontSize: 10, fontFamily: "var(--font-jetbrains-mono)" }}
              tickLine={false}
              axisLine={{ stroke: GRID_COLOR }}
              interval="preserveStartEnd"
              tickFormatter={
                mode === "days"
                  ? (v: string) => {
                      const parts = v.split("-");
                      if (parts.length === 3) {
                        const month = new Date(0, parseInt(parts[1]) - 1).toLocaleString("en-US", { month: "short" });
                        return `${month} ${parseInt(parts[2])}`;
                      }
                      return v;
                    }
                  : undefined
              }
            />

            <YAxis
              domain={[0, 100]}
              tick={{ fill: AXIS_TICK_COLOR, fontSize: 10, fontFamily: "var(--font-jetbrains-mono)" }}
              tickLine={false}
              axisLine={false}
              tickCount={5}
            />

            <Tooltip
              content={<CustomTooltip />}
              cursor={{ stroke: AMBER_LINE, strokeWidth: 1, strokeOpacity: 0.4 }}
            />

            {/* Commit reference lines — rendered before Area so they sit behind the fill */}
            {activeMarkers.map((cm, i) => (
              <ReferenceLine
                key={`commit-${i}`}
                x={cm.xValue}
                stroke={COMMIT_LINE_COLOR}
                strokeWidth={1.5}
                strokeDasharray="4 2"
              />
            ))}

            <Area
              type="monotone"
              dataKey="score"
              stroke={AMBER_LINE}
              strokeWidth={2}
              fill={`url(#${gradientId})`}
              fillOpacity={1}
              dot={false}
              activeDot={{
                r: 4,
                fill: AMBER_LINE,
                stroke: "#0D0B09",
                strokeWidth: 2,
              }}
              isAnimationActive={true}
              animationDuration={600}
              animationEasing="ease-out"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
