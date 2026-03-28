/**
 * Nightjar Verification Canvas — Run State Reducer
 *
 * Shared state model for a single verification run.
 * This file is owned by Agent C1 (Realtime Mode). Agent C2 (Replay Mode)
 * imports from here so both modes operate on the same state shape.
 *
 * Handles both:
 * 1. SSE wire events from the Python backend (CanvasEvent from eventTypes.ts)
 * 2. Internal canvas actions (RESET, SET_STREAMING, SET_CONNECTION_ERROR)
 *
 * Stage index → StageName mapping matches the Python pipeline:
 *   0 = preflight, 1 = deps, 2 = schema, 3 = pbt, 4 = negation, 5 = formal
 *
 * Stage pass state resolution for the canvas visual model:
 *   - Stage 3 (pbt) complete + verified  → "pbt_pass"
 *   - Stage 5 (formal) complete + verified → "formal_pass"
 *   - run_complete with verified=true     → all passed stages → "proven"
 *   - Otherwise complete                  → generic "pbt_pass" (amber mid-tone)
 */

import type { StageState } from "../canvas/crystallization";
import type { StageName } from "../canvas/StageNode";
import type { CanvasEvent, InvariantFoundPayload, TrustLevel } from "./eventTypes";

// ---------------------------------------------------------------------------
// Stage index → StageName
// ---------------------------------------------------------------------------

const STAGE_INDEX_TO_NAME: Record<number, StageName> = {
  0: "preflight",
  1: "deps",
  2: "schema",
  3: "pbt",
  4: "negation",
  5: "formal",
};

function stageNameFromIndex(index: number): StageName | null {
  return STAGE_INDEX_TO_NAME[index] ?? null;
}

/** Choose the visual pass state for a completed stage. */
function resolvePassState(stageName: StageName): Extract<StageState, "pbt_pass" | "formal_pass"> {
  if (stageName === "formal") return "formal_pass";
  return "pbt_pass";
}

// ---------------------------------------------------------------------------
// Invariant record (SSE-derived, mirrors Python CanvasInvariant)
// ---------------------------------------------------------------------------

export interface InvariantRecord {
  invariant_id: string;
  run_id: string;
  tier: InvariantFoundPayload["tier"];
  statement: string;
  discoveredAt: number;
}

// ---------------------------------------------------------------------------
// Per-stage log line
// ---------------------------------------------------------------------------

export interface StageLogs {
  [stageIndex: number]: string[];
}

// ---------------------------------------------------------------------------
// RunState — the materialised view of all events so far
// ---------------------------------------------------------------------------

export interface RunState {
  /** UUID of the active verification run, or null before first event. */
  runId: string | null;
  /** Overall pipeline status. */
  status: "idle" | "running" | "completed" | "failed";
  /**
   * Per-stage visual state for the canvas (keyed by StageName).
   * Used directly by VerificationCanvas / StageNode.
   */
  stageStates: Partial<Record<StageName, StageState>>;
  /** Per-stage elapsed duration strings (e.g. "1.2s"), keyed by StageName. */
  stageDurations: Partial<Record<StageName, string>>;
  /** Per-stage error/findings counts, keyed by StageName. */
  stageFindings: Partial<Record<StageName, number>>;
  /** Human-readable total duration from run_complete. */
  totalDuration: string | null;
  /** Name of the first stage that failed, or null. */
  failedStage: StageName | null;
  // ── SSE-specific fields ──────────────────────────────────────────────────
  /** Whether the SSE connection is currently open. */
  streaming: boolean;
  /** Whether the SSE connection has errored out. */
  connectionError: boolean;
  /**
   * Whether to fire the PROVEN ring animation.
   * Set true by run_complete where verified=true.
   * Consumers call CLEAR_PROVEN_RING after consuming.
   */
  provenRing: boolean;
  /** Trust level from run_complete payload. */
  trustLevel: TrustLevel | null;
  /** Invariants discovered so far in this run, in arrival order. */
  invariants: InvariantRecord[];
  /** Per-stage accumulated log lines (keyed by stage index 0–5). */
  stageLogs: StageLogs;
  /** Ordered raw SSE event log. */
  events: CanvasEvent[];
}

export const initialRunState: RunState = {
  runId: null,
  status: "idle",
  stageStates: {},
  stageDurations: {},
  stageFindings: {},
  totalDuration: null,
  failedStage: null,
  streaming: false,
  connectionError: false,
  provenRing: false,
  trustLevel: null,
  invariants: [],
  stageLogs: {},
  events: [],
};

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

export interface ApplyEventAction {
  type: "APPLY_EVENT";
  event: CanvasEvent;
}

export interface ResetAction {
  type: "RESET";
}

export interface SetStreamingAction {
  type: "SET_STREAMING";
  streaming: boolean;
}

export interface SetConnectionErrorAction {
  type: "SET_CONNECTION_ERROR";
}

export interface ClearProvenRingAction {
  type: "CLEAR_PROVEN_RING";
}

export type RunStateAction =
  | ApplyEventAction
  | ResetAction
  | SetStreamingAction
  | SetConnectionErrorAction
  | ClearProvenRingAction;

// ---------------------------------------------------------------------------
// Pure reducer — no side effects
// ---------------------------------------------------------------------------

export function runStateReducer(state: RunState, action: RunStateAction): RunState {
  switch (action.type) {
    case "RESET":
      return { ...initialRunState };

    case "SET_STREAMING":
      return { ...state, streaming: action.streaming, connectionError: false };

    case "SET_CONNECTION_ERROR":
      return { ...state, streaming: false, connectionError: true };

    case "CLEAR_PROVEN_RING":
      return { ...state, provenRing: false };

    case "APPLY_EVENT": {
      const { event } = action;
      const nextEvents = [...state.events, event];

      switch (event.event_type) {
        case "stage_start": {
          const { stage: stageIndex } = event.payload;
          const stageName = stageNameFromIndex(stageIndex);
          if (!stageName) return { ...state, events: nextEvents };
          return {
            ...state,
            runId: state.runId ?? event.run_id,
            status: "running",
            events: nextEvents,
            stageStates: {
              ...state.stageStates,
              [stageName]: "running" as StageState,
            },
            // Pre-seed stageLogs entry so log_line events have a buffer to append to
            stageLogs: {
              ...state.stageLogs,
              [stageIndex]: state.stageLogs[stageIndex] ?? [],
            },
          };
        }

        case "stage_complete": {
          const { stage: stageIndex, duration_ms } = event.payload;
          const stageName = stageNameFromIndex(stageIndex);
          if (!stageName) return { ...state, events: nextEvents };
          const passState = resolvePassState(stageName);
          const durationStr = `${(duration_ms / 1000).toFixed(1)}s`;
          return {
            ...state,
            events: nextEvents,
            stageStates: {
              ...state.stageStates,
              [stageName]: passState,
            },
            stageDurations: {
              ...state.stageDurations,
              [stageName]: durationStr,
            },
          };
        }

        case "stage_fail": {
          const { stage: stageIndex, errors } = event.payload;
          const stageName = stageNameFromIndex(stageIndex);
          if (!stageName) return { ...state, events: nextEvents };
          return {
            ...state,
            events: nextEvents,
            stageStates: {
              ...state.stageStates,
              [stageName]: "failed" as StageState,
            },
            stageFindings: {
              ...state.stageFindings,
              [stageName]: errors.length,
            },
            failedStage: state.failedStage ?? stageName,
          };
        }

        case "log_line": {
          const { stage: stageIndex, text } = event.payload;
          const existingLogs = state.stageLogs[stageIndex] ?? [];
          return {
            ...state,
            events: nextEvents,
            stageLogs: {
              ...state.stageLogs,
              [stageIndex]: [...existingLogs, text],
            },
          };
        }

        case "invariant_found": {
          const { invariant_id, statement, tier } = event.payload;
          const record: InvariantRecord = {
            invariant_id,
            run_id: event.run_id,
            tier,
            statement,
            discoveredAt: event.ts,
          };
          return {
            ...state,
            events: nextEvents,
            invariants: [...state.invariants, record],
          };
        }

        case "run_complete": {
          const { verified, trust_level, total_duration_ms } = event.payload;
          const totalDurationStr = `${(total_duration_ms / 1000).toFixed(1)}s`;

          // If verified, promote all "pbt_pass" / "formal_pass" stages to "proven"
          const nextStageStates = verified
            ? (Object.fromEntries(
                Object.entries(state.stageStates).map(([k, v]) =>
                  v === "pbt_pass" || v === "formal_pass"
                    ? [k, "proven" as StageState]
                    : [k, v]
                )
              ) as Partial<Record<StageName, StageState>>)
            : state.stageStates;

          return {
            ...state,
            events: nextEvents,
            status: verified ? "completed" : "failed",
            trustLevel: trust_level,
            totalDuration: totalDurationStr,
            streaming: false,
            provenRing: verified,
            stageStates: nextStageStates,
          };
        }

        default:
          return { ...state, events: nextEvents };
      }
    }

    default:
      return state;
  }
}
