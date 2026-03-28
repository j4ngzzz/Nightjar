"use client";

/**
 * RunProvider — React Context provider for live SSE verification run state.
 *
 * Wraps a run page / route segment. Any descendant can call `useRunContext()`
 * to read the current `RunState` and dispatch actions without prop drilling.
 *
 * Delegates all SSE connection logic to `openSseConnection` from useRunStream,
 * so there is no duplicated EventSource setup between provider and hook.
 *
 * Usage:
 * ```tsx
 * // In a page or layout:
 * <RunProvider runId={runId}>
 *   <VerificationCanvas stateMap={...} />
 *   <StageDetailPanel ... />
 * </RunProvider>
 *
 * // In any child:
 * const { state, dispatch } = useRunContext();
 * ```
 *
 * Error boundary note: if the SSE connection errors, `state.connectionError`
 * is set to true. The consumer is responsible for surfacing that to the user.
 */

import {
  createContext,
  useContext,
  useReducer,
  useEffect,
  useRef,
  type ReactNode,
} from "react";

import {
  runStateReducer,
  initialRunState,
  type RunState,
  type RunStateAction,
} from "./RunStateReducer";

import { openSseConnection } from "./useRunStream";

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

export interface RunContextValue {
  /** The current materialised run state. */
  state: RunState;
  /** Dispatch an action into the run reducer (e.g. CLEAR_PROVEN_RING). */
  dispatch: React.Dispatch<RunStateAction>;
}

const RunContext = createContext<RunContextValue | null>(null);
RunContext.displayName = "RunContext";

// ---------------------------------------------------------------------------
// Provider props
// ---------------------------------------------------------------------------

export interface RunProviderProps {
  /** UUID of the verification run to stream. */
  runId: string;
  children: ReactNode;
  /**
   * Optional parse-error callback. Called when a Zod parse fails on
   * an incoming SSE frame so callers can log / report without crashing.
   */
  onParseError?: (raw: string, error: unknown) => void;
}

// ---------------------------------------------------------------------------
// Provider component
// ---------------------------------------------------------------------------

export function RunProvider({
  runId,
  children,
  onParseError,
}: RunProviderProps) {
  const [state, dispatch] = useReducer(runStateReducer, initialRunState);

  // Stable ref so SSE handlers always call the current dispatch without
  // the effect re-running on every render.
  const dispatchRef = useRef<React.Dispatch<RunStateAction>>(dispatch);
  dispatchRef.current = dispatch;

  const onParseErrorRef = useRef(onParseError);
  useEffect(() => {
    onParseErrorRef.current = onParseError;
  });

  useEffect(() => {
    if (!runId) return;

    const cleanup = openSseConnection(
      runId,
      (action) => dispatchRef.current(action),
      (raw, err) => onParseErrorRef.current?.(raw, err)
    );

    return cleanup;
  }, [runId]);

  return (
    <RunContext.Provider value={{ state, dispatch }}>
      {children}
    </RunContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Consumer hook
// ---------------------------------------------------------------------------

/**
 * useRunContext — consume the nearest RunProvider's state and dispatch.
 *
 * Throws if called outside a RunProvider tree, giving a clear error message
 * rather than a silent null/undefined crash.
 */
export function useRunContext(): RunContextValue {
  const ctx = useContext(RunContext);
  if (ctx === null) {
    throw new Error(
      "useRunContext must be used within a <RunProvider>. " +
        "Wrap the run page with <RunProvider runId={runId}>."
    );
  }
  return ctx;
}
