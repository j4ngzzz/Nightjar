"use client";

/**
 * useRunStream — React hook for a live SSE verification run.
 *
 * Connects to `GET /api/run/{runId}/stream`, parses each SSE frame
 * through the Zod CanvasEventSchema, and dispatches into runStateReducer.
 *
 * Lifecycle:
 * 1. On mount (or runId change): open EventSource, set streaming=true
 * 2. Each named event type is listened for individually (matches Python
 *    `event: {type}` SSE frames from CanvasEvent.to_sse())
 * 3. run_complete → streaming=false, provenRing fires if verified=true
 * 4. On error → SET_CONNECTION_ERROR
 * 5. On cleanup → EventSource.close()
 *
 * Usage:
 * ```tsx
 * function RunPage({ runId }: { runId: string }) {
 *   const state = useRunStream(runId);
 *   return <VerificationCanvas stateMap={state.stageStates} />;
 * }
 * ```
 *
 * For tree-wide access without prop drilling, use RunProvider / useRunContext
 * from RunProvider.tsx instead.
 */

import { useReducer, useEffect, useRef, useCallback } from "react";

import { CanvasEventSchema, type EventTypeName } from "./eventTypes";
import {
  runStateReducer,
  initialRunState,
  type RunState,
  type RunStateAction,
} from "./RunStateReducer";

// ---------------------------------------------------------------------------
// SSE endpoint resolver — shared with RunProvider
// ---------------------------------------------------------------------------

export const SSE_BASE_URL: string =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) ||
  "http://localhost:8000";

export function buildStreamUrl(runId: string): string {
  return `${SSE_BASE_URL}/api/run/${encodeURIComponent(runId)}/stream`;
}

// ---------------------------------------------------------------------------
// All named SSE event types emitted by the Python backend
// ---------------------------------------------------------------------------

export const SSE_EVENT_TYPES: EventTypeName[] = [
  "stage_start",
  "stage_complete",
  "stage_fail",
  "log_line",
  "invariant_found",
  "run_complete",
];

// ---------------------------------------------------------------------------
// Shared SSE connection factory — used by useRunStream and RunProvider
//
// Not a hook. Called inside useEffect. Returns a cleanup function.
// Both RunProvider and useRunStream import this to avoid duplicating
// EventSource setup, listener wiring, and parse error handling.
// ---------------------------------------------------------------------------

export function openSseConnection(
  runId: string,
  dispatch: React.Dispatch<RunStateAction>,
  onParseError?: (raw: string, error: unknown) => void
): () => void {
  const es = new EventSource(buildStreamUrl(runId));
  dispatch({ type: "SET_STREAMING", streaming: true });

  for (const eventType of SSE_EVENT_TYPES) {
    es.addEventListener(eventType, (e: MessageEvent) => {
      const raw: string = typeof e.data === "string" ? e.data : "";
      const parsed = CanvasEventSchema.safeParse(
        (() => {
          try {
            return JSON.parse(raw);
          } catch {
            return null;
          }
        })()
      );

      if (!parsed.success) {
        onParseError?.(raw, parsed.error);
        return;
      }

      dispatch({ type: "APPLY_EVENT", event: parsed.data });
    });
  }

  es.onerror = () => {
    dispatch({ type: "SET_CONNECTION_ERROR" });
    es.close();
  };

  return () => {
    es.close();
    dispatch({ type: "SET_STREAMING", streaming: false });
  };
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export interface UseRunStreamOptions {
  /**
   * Called when the Zod schema rejects a frame.
   * Defaults to a no-op; provide a handler to log or report parse errors.
   */
  onParseError?: (raw: string, error: unknown) => void;
}

export function useRunStream(
  runId: string,
  options: UseRunStreamOptions = {}
): RunState {
  const [state, dispatch] = useReducer(runStateReducer, initialRunState);

  // Stable ref to the onParseError callback so the effect doesn't re-run
  const onParseErrorRef = useRef(options.onParseError);
  useEffect(() => {
    onParseErrorRef.current = options.onParseError;
  });

  // Stable dispatch ref for use in SSE handlers
  const dispatchRef = useRef<React.Dispatch<RunStateAction>>(dispatch);
  dispatchRef.current = dispatch;

  useEffect(() => {
    if (!runId) return;

    const cleanup = openSseConnection(
      runId,
      (action) => dispatchRef.current(action),
      (raw, err) => onParseErrorRef.current?.(raw, err)
    );

    return cleanup;
  }, [runId]);

  return state;
}

// ---------------------------------------------------------------------------
// Convenience: clear the provenRing flag after the animation fires
// ---------------------------------------------------------------------------

export function useClearProvenRing(
  dispatch: React.Dispatch<RunStateAction>
): () => void {
  return useCallback(() => {
    dispatch({ type: "CLEAR_PROVEN_RING" });
  }, [dispatch]);
}
