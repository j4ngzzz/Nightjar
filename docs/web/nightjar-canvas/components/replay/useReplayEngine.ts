"use client";

/**
 * Nightjar Verification Canvas — Replay Engine Hook
 *
 * Replays a stored sequence of CanvasEvents in order, dispatching each event
 * into the RunState reducer at the correct wall-clock tempo.
 *
 * Speed semantics:
 *   1×  — real-time: delay between events matches original recording
 *   2×  — half the real-time delay
 *   10× — one-tenth the real-time delay
 *
 * Pause stops the timer mid-sequence; resume continues from the same cursor.
 *
 * Seeking (seek(index)) instantly materialises state up to that index by
 * replaying all events from 0 to index-1 synchronously, then pausing.
 *
 * The engine works with CanvasEvent (C1's SSE wire type from eventTypes.ts) so
 * replay mode operates on the same state shape as real-time mode.
 */

import { useState, useEffect, useReducer, useCallback, useRef } from "react";
import {
  runStateReducer,
  initialRunState,
  type RunState,
} from "../realtime/RunStateReducer";
import type { CanvasEvent } from "../realtime/eventTypes";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ReplaySpeed = 1 | 2 | 10;

export interface ReplayEngineState {
  /** The materialised RunState at the current cursor position. */
  state: RunState;
  /** Index of the next event to dispatch (0 = before any events). */
  cursor: number;
  /** Whether the replay is currently advancing. */
  playing: boolean;
  /** Total number of events in the sequence. */
  total: number;
  /** Whether replay has dispatched the final event. */
  finished: boolean;
}

export interface ReplayEngineControls {
  /** Start or resume playback. */
  play: () => void;
  /** Pause playback. */
  pause: () => void;
  /** Toggle between play and pause. */
  togglePlayPause: () => void;
  /**
   * Seek to a specific cursor position.
   * Replays events [0, index) synchronously to derive correct state, then
   * pauses at that position. Clamps to [0, events.length].
   */
  seek: (index: number) => void;
  /** Reset to the beginning and stop. */
  reset: () => void;
}

// ---------------------------------------------------------------------------
// materialiseStateAt — pure synchronous replay, no side-effects
// ---------------------------------------------------------------------------

function materialiseStateAt(events: CanvasEvent[], index: number): RunState {
  let s = initialRunState;
  const bound = Math.min(index, events.length);
  for (let i = 0; i < bound; i++) {
    s = runStateReducer(s, { type: "APPLY_EVENT", event: events[i] });
  }
  return s;
}

// ---------------------------------------------------------------------------
// useReplayEngine
// ---------------------------------------------------------------------------

export function useReplayEngine(
  events: CanvasEvent[],
  speed: ReplaySpeed = 1
): ReplayEngineState & ReplayEngineControls {
  // cursor = index of the *next* event to be dispatched.
  // cursor === events.length means all events have been dispatched.
  const [cursor, setCursor] = useState<number>(0);
  const [playing, setPlaying] = useState<boolean>(false);

  // Primary reducer — driven by normal playback.
  const [reducerState, dispatch] = useReducer(runStateReducer, initialRunState);

  // Speed ref so the timer closure always reads the latest value without
  // needing to be in the dependency array (avoids restarting timer on speed
  // change while mid-event — speed changes pause anyway).
  const speedRef = useRef<ReplaySpeed>(speed);
  speedRef.current = speed;

  // Events ref for stable access inside callbacks.
  const eventsRef = useRef<CanvasEvent[]>(events);
  eventsRef.current = events;

  // -------------------------------------------------------------------------
  // Seek snapshot — when the user seeks, we materialise state synchronously
  // and store it here. The exposed `state` uses this snapshot until normal
  // playback resumes and clears it.
  // -------------------------------------------------------------------------
  const [seekSnapshot, setSeekSnapshot] = useState<RunState | null>(null);
  const seekSnapshotRef = useRef<RunState | null>(null);

  // Reset engine when a completely new events array is loaded (identity change).
  // Uses a ref to track the previous identity without triggering extra effects.
  const prevEventsRef = useRef<CanvasEvent[]>(events);
  useEffect(() => {
    if (prevEventsRef.current !== events) {
      prevEventsRef.current = events;
      setPlaying(false);
      setCursor(0);
      seekSnapshotRef.current = null;
      setSeekSnapshot(null);
      dispatch({ type: "RESET" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events]);

  // -------------------------------------------------------------------------
  // Playback timer — fires once per event, then schedules the next.
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!playing) return;

    const currentEvents = eventsRef.current;
    if (cursor >= currentEvents.length) {
      // All events exhausted — stop automatically.
      setPlaying(false);
      return;
    }

    const currentEvent = currentEvents[cursor];
    const nextEvent = currentEvents[cursor + 1];

    // Delay until the next event, scaled by speed.
    // If there is no next event, fire with no delay (last event shows instantly).
    const rawDelay = nextEvent
      ? Math.max(0, nextEvent.ts - currentEvent.ts)
      : 0;
    const scaledDelay = rawDelay / speedRef.current;

    // Dispatch the current event and clear any stale seek snapshot so the
    // reducer-driven state takes over again.
    dispatch({ type: "APPLY_EVENT", event: currentEvent });
    if (seekSnapshotRef.current !== null) {
      seekSnapshotRef.current = null;
      setSeekSnapshot(null);
    }

    const timer = setTimeout(() => {
      setCursor((c) => c + 1);
    }, scaledDelay);

    return () => clearTimeout(timer);
    // cursor and playing are intentional deps; eventsRef is stable.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, cursor]);

  // -------------------------------------------------------------------------
  // Controls
  // -------------------------------------------------------------------------

  const play = useCallback(() => {
    setPlaying(true);
  }, []);

  const pause = useCallback(() => {
    setPlaying(false);
  }, []);

  const togglePlayPause = useCallback(() => {
    setPlaying((p) => !p);
  }, []);

  const seek = useCallback((index: number) => {
    const currentEvents = eventsRef.current;
    const clamped = Math.max(0, Math.min(index, currentEvents.length));

    // Pause playback immediately to prevent race with timer.
    setPlaying(false);

    // Materialise state synchronously.
    const materialisedState = materialiseStateAt(currentEvents, clamped);

    // Store snapshot — overrides reducer state until next playback advance.
    seekSnapshotRef.current = materialisedState;
    setSeekSnapshot(materialisedState);

    // Move cursor to the seeked position.
    setCursor(clamped);
  }, []);

  const reset = useCallback(() => {
    setPlaying(false);
    setCursor(0);
    seekSnapshotRef.current = null;
    setSeekSnapshot(null);
    dispatch({ type: "RESET" });
  }, []);

  // -------------------------------------------------------------------------
  // Derived values
  // -------------------------------------------------------------------------

  // The state we expose: seek snapshot takes priority during a seek jump;
  // reducer state takes over during normal playback.
  const exposedState: RunState =
    seekSnapshot !== null ? seekSnapshot : reducerState;

  const finished = events.length > 0 && cursor >= events.length;

  return {
    state: exposedState,
    cursor,
    playing,
    total: events.length,
    finished,
    play,
    pause,
    togglePlayPause,
    seek,
    reset,
  };
}
