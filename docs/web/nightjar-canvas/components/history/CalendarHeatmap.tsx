"use client";

/**
 * CalendarHeatmap — 52-week GitHub-style contribution heatmap.
 *
 * Displays trust score history as a grid of 52 columns × 7 rows.
 * Each cell represents one day. Color encodes the best trust score that day:
 *   - No run:    #3A2E10  (dim — color-pending-state)
 *   - Low  0–40: #A87020  (pbt-pass amber)
 *   - Mid 41–70: #D4920A  (amber)
 *   - High 71–95:#F5B93A  (gold)
 *   - Peak 96+: #FFD060  (peak)
 *
 * Month labels render in #9A8E78 above the week columns.
 * Hover tooltip shows the best run ID + score for that day.
 */

import * as React from "react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Input: one entry per day that had at least one run. */
export interface DayRunSummary {
  /** ISO date string YYYY-MM-DD */
  date: string;
  /** Best trust score for that day (0–100) */
  bestScore: number;
  /** Run ID of the best run */
  bestRunId: string;
  /** Total runs that day */
  runCount: number;
}

export interface CalendarHeatmapProps {
  /** Day summaries — need not cover all 364 days. Missing days = no run. */
  data: DayRunSummary[];
  className?: string;
  /**
   * Anchor date (last day shown). Defaults to today.
   * All dates are derived from this anchor going back 52 weeks.
   */
  anchorDate?: Date;
}

// ---------------------------------------------------------------------------
// Color mapping
// ---------------------------------------------------------------------------

const COLOR_NO_RUN = "#3A2E10";
const COLOR_LOW = "#A87020";
const COLOR_MID = "#D4920A";
const COLOR_HIGH = "#F5B93A";
const COLOR_PEAK = "#FFD060";

function scoreToColor(score: number | null): string {
  if (score === null) return COLOR_NO_RUN;
  if (score <= 40) return COLOR_LOW;
  if (score <= 70) return COLOR_MID;
  if (score <= 95) return COLOR_HIGH;
  return COLOR_PEAK;
}

// ---------------------------------------------------------------------------
// Date utilities
// ---------------------------------------------------------------------------

/** Format a Date as YYYY-MM-DD. */
function toISODate(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Add `n` days to a Date (does not mutate). */
function addDays(d: Date, n: number): Date {
  const result = new Date(d.getTime());
  result.setDate(result.getDate() + n);
  return result;
}

/**
 * Build the 52×7 grid of dates.
 *
 * The grid starts on the Sunday of the week that contains the date
 * 52 weeks before the anchor. Columns = weeks (left=oldest), rows = day-of-week.
 *
 * Returns an array of 52 columns, each column is an array of 7 Date|null
 * (null = padding days outside the [start, anchor] range).
 */
function buildGrid(anchor: Date): Date[][] {
  // Start at the Sunday 52 weeks ago
  const dayOfWeek = anchor.getDay(); // 0=Sun

  // End of grid = anchor's Saturday (or anchor itself if it's Saturday)
  const daysToSaturday = (6 - dayOfWeek + 7) % 7;
  const gridEnd = addDays(anchor, daysToSaturday);

  // Start of grid = gridEnd - 364 days (= 52 weeks)
  const gridStart = addDays(gridEnd, -363);

  // Collect all 364 dates
  const allDates: Date[] = [];
  for (let i = 0; i < 364; i++) {
    allDates.push(addDays(gridStart, i));
  }

  // Split into 52 weeks (columns), each week starting Sunday
  const columns: Date[][] = [];
  for (let w = 0; w < 52; w++) {
    columns.push(allDates.slice(w * 7, w * 7 + 7));
  }

  return columns;
}

// Short month names
const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

// Short day-of-week labels (only Mon/Wed/Fri shown to save vertical space)
const DOW_LABELS = ["", "Mon", "", "Wed", "", "Fri", ""];

// ---------------------------------------------------------------------------
// Cell tooltip state
// ---------------------------------------------------------------------------

interface TooltipState {
  date: string;
  score: number | null;
  runId: string | null;
  runCount: number;
  x: number;
  y: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CalendarHeatmap({
  data,
  className,
  anchorDate,
}: CalendarHeatmapProps) {
  const anchor = React.useMemo(
    () => anchorDate ?? new Date(),
    [anchorDate]
  );

  // Build lookup: date string → DayRunSummary
  const dataMap = React.useMemo(() => {
    const m = new Map<string, DayRunSummary>();
    for (const d of data) m.set(d.date, d);
    return m;
  }, [data]);

  // Build 52×7 grid
  const columns = React.useMemo(() => buildGrid(anchor), [anchor]);

  // Month label positions: track which week column is the first of each month
  const monthLabels = React.useMemo(() => {
    const labels: Array<{ col: number; label: string }> = [];
    let lastMonth = -1;
    columns.forEach((col, colIdx) => {
      // Use the first date of the week for month detection
      const firstDate = col[0];
      if (!firstDate) return;
      const m = firstDate.getMonth();
      if (m !== lastMonth) {
        labels.push({ col: colIdx, label: MONTH_NAMES[m] });
        lastMonth = m;
      }
    });
    return labels;
  }, [columns]);

  // Tooltip state
  const [tooltip, setTooltip] = React.useState<TooltipState | null>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);

  const CELL_SIZE = 11;
  const CELL_GAP = 2;
  const CELL_STEP = CELL_SIZE + CELL_GAP;
  const DOW_LABEL_WIDTH = 28;
  const MONTH_LABEL_HEIGHT = 18;

  const gridWidth = DOW_LABEL_WIDTH + 52 * CELL_STEP - CELL_GAP;
  const gridHeight = MONTH_LABEL_HEIGHT + 7 * CELL_STEP - CELL_GAP;

  return (
    <div className={cn("relative", className)}>
      <div
        ref={containerRef}
        className="overflow-x-auto"
        onMouseLeave={() => setTooltip(null)}
      >
        <svg
          width={gridWidth}
          height={gridHeight}
          aria-label="Trust score calendar heatmap — last 52 weeks"
          role="img"
        >
          {/* Month labels */}
          {monthLabels.map(({ col, label }) => (
            <text
              key={`month-${col}`}
              x={DOW_LABEL_WIDTH + col * CELL_STEP}
              y={MONTH_LABEL_HEIGHT - 4}
              fontSize={9}
              fill="#9A8E78"
              fontFamily="var(--font-jetbrains-mono)"
            >
              {label}
            </text>
          ))}

          {/* Day-of-week labels */}
          {DOW_LABELS.map((label, row) =>
            label ? (
              <text
                key={`dow-${row}`}
                x={0}
                y={MONTH_LABEL_HEIGHT + row * CELL_STEP + CELL_SIZE - 1}
                fontSize={9}
                fill="#9A8E78"
                fontFamily="var(--font-jetbrains-mono)"
                textAnchor="start"
              >
                {label}
              </text>
            ) : null
          )}

          {/* Grid cells */}
          {columns.map((col, colIdx) =>
            col.map((date, rowIdx) => {
              const dateStr = toISODate(date);
              const summary = dataMap.get(dateStr) ?? null;
              const color = scoreToColor(summary?.bestScore ?? null);

              return (
                <rect
                  key={dateStr}
                  x={DOW_LABEL_WIDTH + colIdx * CELL_STEP}
                  y={MONTH_LABEL_HEIGHT + rowIdx * CELL_STEP}
                  width={CELL_SIZE}
                  height={CELL_SIZE}
                  rx={2}
                  ry={2}
                  fill={color}
                  style={{ cursor: summary ? "pointer" : "default" }}
                  onMouseEnter={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    const containerRect =
                      containerRef.current?.getBoundingClientRect();
                    setTooltip({
                      date: dateStr,
                      score: summary?.bestScore ?? null,
                      runId: summary?.bestRunId ?? null,
                      runCount: summary?.runCount ?? 0,
                      x:
                        rect.left -
                        (containerRect?.left ?? 0) +
                        (containerRef.current?.scrollLeft ?? 0) +
                        CELL_SIZE / 2,
                      y:
                        rect.top -
                        (containerRect?.top ?? 0) -
                        4,
                    });
                  }}
                  aria-label={
                    summary
                      ? `${dateStr}: best score ${summary.bestScore}, ${summary.runCount} run${summary.runCount !== 1 ? "s" : ""}`
                      : `${dateStr}: no runs`
                  }
                />
              );
            })
          )}
        </svg>

        {/* Hover Tooltip */}
        {tooltip && (
          <div
            className="pointer-events-none absolute z-20 rounded border px-2.5 py-1.5 text-xs shadow-lg"
            style={{
              left: tooltip.x,
              top: tooltip.y,
              transform: "translate(-50%, -100%)",
              background: "#141109",
              borderColor: "#2A2315",
              fontFamily: "var(--font-jetbrains-mono)",
              minWidth: 160,
              whiteSpace: "nowrap",
            }}
          >
            {/* Date */}
            <div
              className="mb-1 font-semibold"
              style={{ color: "#F0EBE3" }}
            >
              {tooltip.date}
            </div>

            {tooltip.score !== null ? (
              <>
                <div className="flex items-center justify-between gap-3">
                  <span style={{ color: "#9A8E78" }}>Best Score</span>
                  <span
                    style={{
                      color: scoreToColor(tooltip.score),
                      fontWeight: 600,
                    }}
                  >
                    {tooltip.score}
                  </span>
                </div>
                {tooltip.runId && (
                  <div className="flex items-center justify-between gap-3">
                    <span style={{ color: "#9A8E78" }}>Run</span>
                    <span style={{ color: "#F0EBE3" }}>
                      {tooltip.runId.length > 8
                        ? tooltip.runId.slice(0, 8)
                        : tooltip.runId}
                    </span>
                  </div>
                )}
                <div className="flex items-center justify-between gap-3">
                  <span style={{ color: "#9A8E78" }}>Runs</span>
                  <span style={{ color: "#F0EBE3" }}>{tooltip.runCount}</span>
                </div>
              </>
            ) : (
              <div style={{ color: "#8B8579" }}>No runs</div>
            )}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="mt-2 flex items-center gap-2">
        <span
          className="text-[9px] uppercase tracking-wider"
          style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
        >
          Less
        </span>
        {[COLOR_NO_RUN, COLOR_LOW, COLOR_MID, COLOR_HIGH, COLOR_PEAK].map(
          (c) => (
            <div
              key={c}
              style={{
                width: CELL_SIZE,
                height: CELL_SIZE,
                background: c,
                borderRadius: 2,
                flexShrink: 0,
              }}
            />
          )
        )}
        <span
          className="text-[9px] uppercase tracking-wider"
          style={{ color: "#9A8E78", fontFamily: "var(--font-jetbrains-mono)" }}
        >
          More
        </span>
      </div>
    </div>
  );
}
