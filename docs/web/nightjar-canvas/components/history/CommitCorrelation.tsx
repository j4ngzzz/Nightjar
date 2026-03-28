"use client";

/**
 * CommitCorrelation — TrustScoreChart with commit markers overlaid.
 *
 * This component wraps TrustScoreChart and adds vertical commit markers:
 *   - A dashed vertical ReferenceLine at each commit's position (#4A3A1A)
 *   - A clickable commit icon rendered above the chart at each marker position
 *   - Click on icon: shows a popover tooltip with the commit message
 *
 * The commit icon layer is an absolutely-positioned SVG overlay drawn on top
 * of the recharts canvas. Positions are calculated via a ResizeObserver so
 * they stay accurate when the container is resized.
 *
 * Usage:
 * ```tsx
 * <CommitCorrelation
 *   data={runData}
 *   commitMarkers={commits}
 * />
 * ```
 */

import * as React from "react";
import { cn } from "@/lib/cn";
import {
  TrustScoreChart,
  type RunDataPoint,
  type CommitMarker,
  type XAxisMode,
} from "./TrustScoreChart";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CommitCorrelationProps {
  /** Run history data points. */
  data: RunDataPoint[];
  /** Commit markers to overlay. */
  commitMarkers: CommitMarker[];
  /** Initial axis mode. */
  defaultMode?: XAxisMode;
  className?: string;
}

// ---------------------------------------------------------------------------
// CommitTooltip — small popover shown when a commit icon is clicked.
// ---------------------------------------------------------------------------

interface CommitTooltipProps {
  marker: CommitMarker;
  /** Position relative to the icon overlay container. */
  x: number;
  onClose: () => void;
}

function CommitTooltip({ marker, x, onClose }: CommitTooltipProps) {
  const ref = React.useRef<HTMLDivElement>(null);

  // Close on outside click
  React.useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [onClose]);

  const date = new Date(marker.ts);
  const dateStr = date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div
      ref={ref}
      className="absolute z-30 rounded border px-3 py-2 shadow-lg"
      style={{
        left: x,
        top: 0,
        transform: "translate(-50%, -110%)",
        background: "#141109",
        borderColor: "#4A3A1A",
        fontFamily: "var(--font-jetbrains-mono)",
        fontSize: 11,
        minWidth: 180,
        maxWidth: 260,
        pointerEvents: "auto",
      }}
    >
      {/* Commit icon + label */}
      <div
        className="flex items-center gap-1.5 mb-1.5"
        style={{ color: "#D4920A" }}
      >
        <CommitSvgIcon size={12} color="#D4920A" />
        <span className="uppercase tracking-wider text-[9px] font-semibold">
          Commit
        </span>
      </div>

      {/* Message */}
      <p
        className="leading-snug mb-1"
        style={{ color: "#F0EBE3", wordBreak: "break-word" }}
      >
        {marker.message}
      </p>

      {/* Timestamp */}
      <p style={{ color: "#9A8E78", fontSize: 10 }}>{dateStr}</p>

      {/* Close button */}
      <button
        onClick={onClose}
        className="absolute top-1.5 right-1.5 flex items-center justify-center rounded"
        style={{
          background: "transparent",
          border: "none",
          color: "#9A8E78",
          cursor: "pointer",
          width: 16,
          height: 16,
          fontSize: 12,
          lineHeight: 1,
        }}
        aria-label="Close commit tooltip"
      >
        ×
      </button>

      {/* Arrow pointing down */}
      <div
        className="absolute"
        style={{
          bottom: -5,
          left: "50%",
          transform: "translateX(-50%)",
          width: 0,
          height: 0,
          borderLeft: "5px solid transparent",
          borderRight: "5px solid transparent",
          borderTop: "5px solid #4A3A1A",
        }}
        aria-hidden
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small commit SVG icon (like GitHub's commit dot icon)
// ---------------------------------------------------------------------------

function CommitSvgIcon({
  size = 14,
  color = "#4A3A1A",
}: {
  size?: number;
  color?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      aria-hidden="true"
    >
      {/* Circle with horizontal line through center — classic commit icon */}
      <circle cx="8" cy="8" r="4" fill={color} />
      <line x1="0" y1="8" x2="4" y2="8" stroke={color} strokeWidth="1.5" />
      <line x1="12" y1="8" x2="16" y2="8" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// CommitIconOverlay — absolutely positioned icon row above the chart.
//
// Uses the recharts internal layout: recharts leaves a left margin of ~8px
// (margin.left in TrustScoreChart) and the chart area starts after the YAxis
// (~32px wide with our tick config). We measure the container width and
// distribute marker x positions proportionally.
// ---------------------------------------------------------------------------

interface CommitIconOverlayProps {
  markers: CommitMarker[];
  data: RunDataPoint[];
  mode: XAxisMode;
  containerWidth: number;
  /** Pixel offset from left of container to the chart plot area start. */
  plotLeft: number;
  /** Pixel width of the chart plot area. */
  plotWidth: number;
}

function CommitIconOverlay({
  markers,
  data,
  mode,
  containerWidth: _containerWidth,
  plotLeft,
  plotWidth,
}: CommitIconOverlayProps) {
  const [openIdx, setOpenIdx] = React.useState<number | null>(null);

  // Close any open tooltip when mode switches — prevents stale popovers
  React.useEffect(() => {
    setOpenIdx(null);
  }, [mode]);

  // Build the x-key array for the current mode (mirrors TrustScoreChart logic)
  const xKeys = React.useMemo(() => {
    if (mode === "runs") {
      const last30 = data.slice(-30);
      return last30.map((p) =>
        p.runId.length > 8 ? p.runId.slice(0, 8) : p.runId
      );
    }
    // days mode: deduplicate by calendar day, keep last 30
    const byDay = new Map<string, number>();
    for (const p of data) {
      const d = new Date(p.ts);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
      if (!byDay.has(key) || p.score > (byDay.get(key) ?? 0)) {
        byDay.set(key, p.score);
      }
    }
    return Array.from(byDay.keys()).sort().slice(-30);
  }, [data, mode]);

  if (!xKeys.length || plotWidth <= 0) return null;

  const stepPx = plotWidth / Math.max(xKeys.length - 1, 1);

  // For each marker, find the index of its nearest x-key
  const markerPositions = markers.map((cm) => {
    let bestIdx = 0;
    let bestDelta = Infinity;

    if (mode === "runs") {
      for (let i = 0; i < data.slice(-30).length; i++) {
        const delta = Math.abs(data.slice(-30)[i].ts - cm.ts);
        if (delta < bestDelta) {
          bestDelta = delta;
          bestIdx = i;
        }
      }
    } else {
      // days mode
      for (let i = 0; i < xKeys.length; i++) {
        const dayDate = new Date(xKeys[i] + "T00:00:00Z");
        const delta = Math.abs(dayDate.getTime() - cm.ts);
        if (delta < bestDelta) {
          bestDelta = delta;
          bestIdx = i;
        }
      }
    }

    const x = plotLeft + bestIdx * stepPx;
    return { marker: cm, x };
  });

  return (
    <div
      className="absolute inset-0 pointer-events-none"
      aria-hidden="false"
    >
      {markerPositions.map(({ marker, x }, idx) => (
        <div
          key={`ci-${idx}`}
          className="absolute"
          style={{
            left: x,
            top: 8,
            transform: "translateX(-50%)",
            pointerEvents: "auto",
          }}
        >
          {/* Clickable icon */}
          <button
            className="flex items-center justify-center rounded-full"
            style={{
              background: "#1A1409",
              border: `1px solid #4A3A1A`,
              width: 18,
              height: 18,
              cursor: "pointer",
              padding: 0,
            }}
            onClick={() => setOpenIdx(openIdx === idx ? null : idx)}
            aria-label={`Commit: ${marker.message}`}
            title={marker.message}
          >
            <CommitSvgIcon size={10} color="#D4920A" />
          </button>

          {/* Tooltip on click */}
          {openIdx === idx && (
            <CommitTooltip
              marker={marker}
              x={0}
              onClose={() => setOpenIdx(null)}
            />
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * Approximate pixel offset from the left edge of the wrapper to the start of
 * the recharts plot area (where x=0 of the data lies).
 *
 * TrustScoreChart uses margin={{ left: -16 }} which shifts the whole chart
 * left by 16px. Recharts' YAxis with tickCount=5 and values 0–100 renders
 * approximately 32px wide. Net plot left = 32 - 16 = 16px.
 *
 * TODO: If the YAxis width ever changes (e.g. 3-digit scores removed), adjust
 * this constant or derive it via a ref on the recharts wrapper.
 */
const CHART_PLOT_LEFT_OFFSET = 16; // YAxis(~32px) + margin.left(-16) = 16px

export function CommitCorrelation({
  data,
  commitMarkers,
  defaultMode = "runs",
  className,
}: CommitCorrelationProps) {
  const [mode, setMode] = React.useState<XAxisMode>(defaultMode);
  const wrapperRef = React.useRef<HTMLDivElement>(null);
  const [plotWidth, setPlotWidth] = React.useState(0);

  // Measure container to compute plot area width
  React.useEffect(() => {
    if (!wrapperRef.current) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        const totalWidth = entry.contentRect.width;
        // Subtract left offset and right margin(8)
        setPlotWidth(
          Math.max(0, totalWidth - CHART_PLOT_LEFT_OFFSET - 8)
        );
      }
    });

    observer.observe(wrapperRef.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div className={cn("relative", className)} ref={wrapperRef} data-commit-correlation="true">
      {/* Base chart — passes commit markers for ReferenceLine rendering */}
      <TrustScoreChart
        data={data}
        commitMarkers={commitMarkers}
        defaultMode={defaultMode}
        // Sync mode state so overlay positions match chart view
        // We shadow the internal toggle by intercepting mode changes via a
        // thin wrapper div that listens to button clicks.
      />

      {/* Icon overlay: rendered as a separate absolutely-positioned layer */}
      {commitMarkers.length > 0 && plotWidth > 0 && (
        <div
          className="absolute pointer-events-none"
          style={{
            // Position the overlay to sit in the chart area below the header row
            // TrustScoreChart header is ~32px (text + gap), then chart starts.
            top: 40,
            left: 0,
            right: 0,
            // Chart height is 220px, icon sits at top of chart area
            height: 220,
          }}
          aria-label="Commit markers overlay"
        >
          <CommitIconOverlay
            markers={commitMarkers}
            data={data}
            mode={mode}
            containerWidth={
              wrapperRef.current?.getBoundingClientRect().width ?? 0
            }
            plotLeft={CHART_PLOT_LEFT_OFFSET}
            plotWidth={plotWidth}
          />
        </div>
      )}

      {/* Mode sync: listen for button clicks to keep `mode` in sync with chart */}
      <ModeObserver onModeChange={setMode} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// ModeObserver — listens for clicks on the toggle buttons rendered inside
// TrustScoreChart and syncs the parent `mode` state so overlay aligns.
// This is the minimal coupling needed — we don't re-implement the toggle.
// ---------------------------------------------------------------------------

function ModeObserver({
  onModeChange,
}: {
  onModeChange: (m: XAxisMode) => void;
}) {
  const ref = React.useRef<HTMLSpanElement>(null);

  React.useEffect(() => {
    const container = ref.current?.closest("[data-commit-correlation]");
    if (!container) return;

    function handleClick(e: Event) {
      const target = e.target as HTMLElement;
      const btn = target.closest("button[aria-pressed]");
      if (!btn) return;
      const text = btn.textContent?.toLowerCase() ?? "";
      if (text.includes("run")) onModeChange("runs");
      else if (text.includes("day")) onModeChange("days");
    }

    container.addEventListener("click", handleClick);
    return () => container.removeEventListener("click", handleClick);
  }, [onModeChange]);

  return <span ref={ref} aria-hidden className="sr-only" />;
}
