"use client";

/**
 * Nightjar Verification Canvas — ReplayController
 *
 * Top-level Replay Mode UI. Renders:
 *   - ScrubberBar (seek through events)
 *   - Play/Pause button (Lucide icons)
 *   - Speed selector: 1× / 2× / 10× (amber radio group)
 *   - Current event timestamp display (JetBrains Mono)
 *   - VerificationCanvas showing the state at the current cursor position
 *
 * All amber palette — no green or purple.
 * Accepts a list of CanvasEvents and drives the replay engine.
 *
 * Usage:
 *   <ReplayController events={storedEvents} />
 */

import { useState, useCallback } from "react";
import { Play, Pause, RotateCcw } from "lucide-react";

import { useReplayEngine, type ReplaySpeed } from "./useReplayEngine";
import { ScrubberBar } from "./ScrubberBar";
import { VerificationCanvas } from "../canvas/VerificationCanvas";
import type { CanvasEvent } from "../realtime/eventTypes";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Format a millisecond timestamp as a human-readable offset string. */
function formatTimestamp(ms: number): string {
  const safe = Math.max(0, Math.round(ms));
  if (safe < 1000) return `${safe}ms`;
  const s = safe / 1000;
  if (s < 60) return `${s.toFixed(2)}s`;
  const m = Math.floor(s / 60);
  const rem = (s % 60).toFixed(1);
  return `${m}m ${rem}s`;
}

/** Get the timestamp of the event at `cursor - 1` (last dispatched). */
function currentTimestamp(events: CanvasEvent[], cursor: number): string {
  if (cursor === 0 || events.length === 0) return "0ms";
  const idx = Math.min(cursor - 1, events.length - 1);
  const startTs = events[0].ts;
  const relative = events[idx].ts - startTs;
  return formatTimestamp(relative);
}

// ---------------------------------------------------------------------------
// Speed option button
// ---------------------------------------------------------------------------

interface SpeedOptionProps {
  value: ReplaySpeed;
  current: ReplaySpeed;
  onSelect: (v: ReplaySpeed) => void;
}

function SpeedOption({ value, current, onSelect }: SpeedOptionProps) {
  const active = value === current;
  return (
    <button
      type="button"
      onClick={() => onSelect(value)}
      aria-pressed={active}
      aria-label={`Set replay speed to ${value}×`}
      className="relative flex items-center justify-center rounded text-[11px] font-semibold transition-all duration-150 focus:outline-none focus-visible:ring-1 focus-visible:ring-amber-400"
      style={{
        fontFamily: "var(--font-jetbrains-mono)",
        width: 36,
        height: 28,
        backgroundColor: active ? "rgba(245,185,58,0.15)" : "transparent",
        border: active ? "1px solid #F5B93A" : "1px solid #2A2315",
        color: active ? "#F5B93A" : "#9A8E78",
        boxShadow: active ? "0 0 6px rgba(245,185,58,0.25)" : "none",
        cursor: "pointer",
      }}
    >
      {value}×
    </button>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ReplayControllerProps {
  /** The complete ordered list of run events to replay. */
  events: CanvasEvent[];
  /** Optional canvas height override. */
  canvasHeight?: number;
  /** Optional CSS class on the outer wrapper. */
  className?: string;
}

// ---------------------------------------------------------------------------
// ReplayController
// ---------------------------------------------------------------------------

export function ReplayController({
  events,
  canvasHeight = 280,
  className,
}: ReplayControllerProps) {
  const [speed, setSpeed] = useState<ReplaySpeed>(1);

  const {
    state,
    cursor,
    playing,
    total,
    finished,
    pause,
    togglePlayPause,
    seek,
    reset,
  } = useReplayEngine(events, speed);

  // -------------------------------------------------------------------------
  // Speed change: pause first so the timer doesn't race
  // -------------------------------------------------------------------------

  const handleSpeedChange = useCallback(
    (v: ReplaySpeed) => {
      pause();
      setSpeed(v);
    },
    [pause]
  );

  // -------------------------------------------------------------------------
  // Derived display values
  // -------------------------------------------------------------------------

  const timestampLabel = currentTimestamp(events, cursor);
  const progressLabel = total > 0 ? `${cursor} / ${total}` : "—";
  const isEmpty = events.length === 0;

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div
      className={className}
      style={{
        backgroundColor: "#0D0B09",
        border: "1px solid #2A2315",
        borderRadius: 8,
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        width: "100%",
      }}
    >
      {/* Replay mode header badge */}
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span
          style={{
            fontFamily: "var(--font-jetbrains-mono)",
            fontSize: 9,
            fontWeight: 600,
            letterSpacing: "0.15em",
            color: "#D4920A",
            textTransform: "uppercase" as const,
            padding: "2px 6px",
            border: "1px solid #D4920A",
            borderRadius: 3,
            backgroundColor: "rgba(212,146,10,0.08)",
          }}
        >
          REPLAY
        </span>
        {state.runId && (
          <span
            style={{
              fontFamily: "var(--font-jetbrains-mono)",
              fontSize: 10,
              color: "#9A8E78",
            }}
          >
            {state.runId}
          </span>
        )}
      </div>

      {/* Canvas — shows verification state at current cursor */}
      <VerificationCanvas
        stateMap={state.stageStates}
        durationMap={state.stageDurations}
        findingsMap={state.stageFindings}
        height={canvasHeight}
      />

      {/* Scrubber */}
      <ScrubberBar
        events={events}
        cursor={cursor}
        onSeek={seek}
      />

      {/* Controls row */}
      <div
        className="flex items-center gap-3"
        style={{ flexWrap: "wrap" }}
      >
        {/* Play / Pause button */}
        <button
          type="button"
          onClick={finished ? reset : togglePlayPause}
          disabled={isEmpty}
          aria-label={finished ? "Restart replay" : playing ? "Pause" : "Play"}
          className="flex items-center justify-center rounded-full transition-all duration-150 focus:outline-none focus-visible:ring-1 focus-visible:ring-amber-400"
          style={{
            width: 36,
            height: 36,
            backgroundColor: isEmpty
              ? "transparent"
              : "rgba(212,146,10,0.15)",
            border: `1px solid ${isEmpty ? "#2A2315" : "#D4920A"}`,
            color: isEmpty ? "#3A2E10" : "#D4920A",
            cursor: isEmpty ? "not-allowed" : "pointer",
            boxShadow: isEmpty ? "none" : "0 0 6px rgba(212,146,10,0.2)",
          }}
        >
          {finished ? (
            <RotateCcw size={16} strokeWidth={1.5} aria-hidden />
          ) : playing ? (
            <Pause size={16} strokeWidth={1.5} aria-hidden />
          ) : (
            <Play size={16} strokeWidth={1.5} aria-hidden />
          )}
        </button>

        {/* Speed selector */}
        <div
          className="flex items-center gap-1"
          role="group"
          aria-label="Replay speed"
        >
          {([1, 2, 10] as ReplaySpeed[]).map((v) => (
            <SpeedOption
              key={v}
              value={v}
              current={speed}
              onSelect={handleSpeedChange}
            />
          ))}
        </div>

        {/* Timestamp display */}
        <div
          className="flex items-center gap-2 ml-auto"
          style={{ flexShrink: 0 }}
        >
          {/* Event counter */}
          <span
            style={{
              fontFamily: "var(--font-jetbrains-mono)",
              fontSize: 11,
              color: "#9A8E78",
            }}
          >
            {progressLabel}
          </span>

          {/* Separator */}
          <span
            style={{ color: "#2A2315", fontSize: 11 }}
            aria-hidden
          >
            |
          </span>

          {/* Elapsed timestamp */}
          <span
            style={{
              fontFamily: "var(--font-jetbrains-mono)",
              fontSize: 12,
              color: "#F5B93A",
              minWidth: 56,
              textAlign: "right",
            }}
            aria-label={`Current replay time: ${timestampLabel}`}
          >
            {timestampLabel}
          </span>
        </div>
      </div>

      {/* Empty state */}
      {isEmpty && (
        <div
          style={{
            fontFamily: "var(--font-jetbrains-mono)",
            fontSize: 11,
            color: "#9A8E78",
            textAlign: "center",
            paddingTop: 4,
          }}
        >
          No recorded events to replay
        </div>
      )}

      {/* Finished banner */}
      {finished && !isEmpty && (
        <div
          style={{
            fontFamily: "var(--font-jetbrains-mono)",
            fontSize: 11,
            color: "#A87020",
            textAlign: "center",
            paddingTop: 4,
          }}
          aria-live="polite"
        >
          Replay complete — click restart to replay
        </div>
      )}
    </div>
  );
}
