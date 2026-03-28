"use client";

/**
 * Nightjar Verification Canvas — ScrubberBar
 *
 * Horizontal playback scrubber for Replay Mode.
 *
 * Visual spec:
 *   - Track:        #2A2315 (--color-border-inactive)
 *   - Amber fill:   #F5B93A (--color-gold) — shows elapsed progress
 *   - Tick marks:   #D4920A (--color-amber) at each stage_start boundary
 *   - Stage labels: #9A8E78 above tick marks (JetBrains Mono)
 *   - Thumb:        #F5B93A circle with amber glow
 *
 * Click anywhere on the track to seek to the nearest event index.
 * Drag (pointermove after pointerdown) is fully supported.
 * Keyboard: ArrowLeft/Right step by 1, Home/End jump to bounds.
 *
 * Uses CanvasEvent from C1's eventTypes.ts — stage boundaries are found by
 * locating the first "stage_start" event for each stage index (0–5).
 */

import { useRef, useCallback, type PointerEvent as ReactPointerEvent } from "react";
import type { CanvasEvent } from "../realtime/eventTypes";

// ---------------------------------------------------------------------------
// Stage index → display label
// ---------------------------------------------------------------------------

const STAGE_LABELS: Record<number, string> = {
  0: "PREFLIGHT",
  1: "DEPS",
  2: "SCHEMA",
  3: "PBT",
  4: "NEGATION",
  5: "FORMAL",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

/**
 * Convert a pointer clientX into the nearest event index (0..events.length).
 */
function xToEventIndex(
  x: number,
  trackWidth: number,
  totalEvents: number
): number {
  if (totalEvents === 0) return 0;
  const ratio = clamp(x / trackWidth, 0, 1);
  return Math.round(ratio * totalEvents);
}

/**
 * Build tick marks from the event list.
 * One tick per unique stage index found in "stage_start" events, in order.
 */
interface StageTick {
  stageIndex: number;
  label: string;
  eventIndex: number;
  ratio: number;
}

function buildStageTicks(events: CanvasEvent[]): StageTick[] {
  if (events.length === 0) return [];

  const seen = new Set<number>();
  const ticks: StageTick[] = [];

  for (let i = 0; i < events.length; i++) {
    const e = events[i];
    if (e.event_type === "stage_start") {
      const stageIndex = e.payload.stage;
      if (!seen.has(stageIndex)) {
        seen.add(stageIndex);
        ticks.push({
          stageIndex,
          label: STAGE_LABELS[stageIndex] ?? `STAGE ${stageIndex}`,
          eventIndex: i,
          ratio: i / events.length,
        });
      }
    }
  }

  // Sort by event index (should already be in order, but be defensive).
  ticks.sort((a, b) => a.eventIndex - b.eventIndex);
  return ticks;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ScrubberBarProps {
  /** Full list of run events (used for tick positioning and seek math). */
  events: CanvasEvent[];
  /** Current cursor position (0..events.length). */
  cursor: number;
  /** Called when the user clicks or drags to a new position. */
  onSeek: (index: number) => void;
  /** Optional CSS class on the outer wrapper. */
  className?: string;
}

// ---------------------------------------------------------------------------
// ScrubberBar
// ---------------------------------------------------------------------------

export function ScrubberBar({
  events,
  cursor,
  onSeek,
  className,
}: ScrubberBarProps) {
  const trackRef = useRef<HTMLDivElement>(null);
  const isDraggingRef = useRef(false);

  const total = events.length;
  const progressRatio = total > 0 ? clamp(cursor / total, 0, 1) : 0;
  const progressPercent = `${(progressRatio * 100).toFixed(3)}%`;

  const stageTicks = buildStageTicks(events);

  // -------------------------------------------------------------------------
  // Seek from pointer position
  // -------------------------------------------------------------------------

  const seekFromPointer = useCallback(
    (clientX: number) => {
      if (!trackRef.current) return;
      const rect = trackRef.current.getBoundingClientRect();
      const x = clientX - rect.left;
      const index = xToEventIndex(x, rect.width, total);
      onSeek(index);
    },
    [total, onSeek]
  );

  // -------------------------------------------------------------------------
  // Pointer event handlers — support click and drag
  // -------------------------------------------------------------------------

  const handlePointerDown = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      e.currentTarget.setPointerCapture(e.pointerId);
      isDraggingRef.current = true;
      seekFromPointer(e.clientX);
    },
    [seekFromPointer]
  );

  const handlePointerMove = useCallback(
    (e: ReactPointerEvent<HTMLDivElement>) => {
      if (!isDraggingRef.current) return;
      seekFromPointer(e.clientX);
    },
    [seekFromPointer]
  );

  const handlePointerUp = useCallback(() => {
    isDraggingRef.current = false;
  }, []);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div
      className={className}
      style={{ width: "100%", userSelect: "none" }}
    >
      {/* Stage labels row — above the track */}
      {stageTicks.length > 0 && (
        <div
          className="relative w-full"
          style={{ height: 16, marginBottom: 4 }}
          aria-hidden
        >
          {stageTicks.map((tick) => (
            <span
              key={tick.stageIndex}
              className="absolute text-[9px] font-semibold uppercase tracking-widest"
              style={{
                left: `${(tick.ratio * 100).toFixed(3)}%`,
                transform: "translateX(-50%)",
                color: "#9A8E78",
                fontFamily: "var(--font-jetbrains-mono)",
                whiteSpace: "nowrap",
                lineHeight: 1,
                bottom: 0,
              }}
            >
              {tick.label}
            </span>
          ))}
        </div>
      )}

      {/* Track outer — expanded hit area via padding */}
      <div
        ref={trackRef}
        role="slider"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={cursor}
        aria-label="Seek through replay"
        tabIndex={0}
        className="relative w-full rounded-full"
        style={{
          height: 6,
          backgroundColor: "#2A2315",
          // Expanded hit area without affecting layout
          paddingTop: 8,
          paddingBottom: 8,
          marginTop: -8,
          marginBottom: -8,
          boxSizing: "content-box",
          cursor: total === 0 ? "default" : "pointer",
        }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onKeyDown={(e) => {
          if (e.key === "ArrowRight") {
            e.preventDefault();
            onSeek(Math.min(cursor + 1, total));
          } else if (e.key === "ArrowLeft") {
            e.preventDefault();
            onSeek(Math.max(cursor - 1, 0));
          } else if (e.key === "Home") {
            e.preventDefault();
            onSeek(0);
          } else if (e.key === "End") {
            e.preventDefault();
            onSeek(total);
          }
        }}
      >
        {/* Visible track base */}
        <div
          className="absolute inset-x-0 rounded-full pointer-events-none"
          style={{
            top: "50%",
            transform: "translateY(-50%)",
            height: 6,
            backgroundColor: "#2A2315",
          }}
        />

        {/* Amber fill — elapsed progress */}
        <div
          className="absolute left-0 rounded-full pointer-events-none"
          style={{
            top: "50%",
            transform: "translateY(-50%)",
            height: 6,
            width: progressPercent,
            backgroundColor: "#F5B93A",
            transition: "width 80ms linear",
          }}
        />

        {/* Stage boundary ticks */}
        {stageTicks.map((tick) => (
          <div
            key={tick.stageIndex}
            className="absolute pointer-events-none"
            style={{
              top: "50%",
              left: `${(tick.ratio * 100).toFixed(3)}%`,
              transform: "translate(-50%, -50%)",
              width: 3,
              height: 10,
              backgroundColor: "#D4920A",
              borderRadius: 2,
            }}
            aria-hidden
          />
        ))}

        {/* Thumb — follows progress */}
        <div
          className="absolute pointer-events-none rounded-full"
          style={{
            top: "50%",
            left: progressPercent,
            transform: "translate(-50%, -50%)",
            width: 14,
            height: 14,
            backgroundColor: "#F5B93A",
            boxShadow: "0 0 8px rgba(245,185,58,0.6)",
            border: "2px solid #D4920A",
            transition: "left 80ms linear",
          }}
          aria-hidden
        />
      </div>

      {/* Spacer to compensate for expanded hit area */}
      <div style={{ height: 8 }} aria-hidden />
    </div>
  );
}
