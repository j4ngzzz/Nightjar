/**
 * Zustand store for Nightjar Verification Canvas run state.
 *
 * Manages the active verification run, its live event stream, and the
 * accumulated list of discovered invariants.  Designed to be used from
 * React components via the `useRunStore` hook.
 *
 * Usage:
 * ```tsx
 * const { activeRun, events, startStream, stopStream } = useRunStore();
 * ```
 *
 * Dependencies: zustand
 */

import { create } from "zustand";
import {
  createRun,
  getRun,
  streamRun,
  type CanvasEvent,
  type CanvasInvariant,
  type CreateRunBody,
  type EventTypeName,
  type RunSnapshot,
  type TrustLevel,
} from "../lib/api-client";

// ---------------------------------------------------------------------------
// Store shape
// ---------------------------------------------------------------------------

/** Subset of run data held in the store for quick access. */
export interface RunSummary {
  run_id: string;
  spec_id: string;
  model: string;
  status: "pending" | "running" | "complete" | "failed";
  verified: boolean;
  trust_level: TrustLevel;
  created_at: number;
  finished_at: number | null;
}

export interface RunStoreState {
  // ── Active run ────────────────────────────────────────────────────────────
  /** The currently active (or most recently loaded) run, or `null`. */
  activeRun: RunSummary | null;

  // ── Event stream ──────────────────────────────────────────────────────────
  /** Ordered list of events received since `startStream` was called. */
  events: CanvasEvent[];

  /** Invariants discovered so far in the active run. */
  invariants: CanvasInvariant[];

  /** Whether a live SSE stream is currently open. */
  streaming: boolean;

  // ── Stage progress ────────────────────────────────────────────────────────
  /** Index of the currently running stage (0–4), or `null` when idle. */
  currentStage: number | null;

  /** Names of stages that have completed successfully. */
  completedStages: string[];

  /** Names of stages that have failed. */
  failedStages: string[];

  // ── Error state ───────────────────────────────────────────────────────────
  /** Last error message, or `null` when healthy. */
  error: string | null;

  // ── Actions ───────────────────────────────────────────────────────────────
  /**
   * Create a new run via the API and set it as the active run.
   *
   * @param body - Optional body forwarded to `POST /api/runs`.
   * @returns The new `run_id`.
   */
  createRun: (body?: CreateRunBody) => Promise<string>;

  /**
   * Load an existing run snapshot from the API and populate the store.
   *
   * @param runId - UUID4 run identifier.
   */
  loadRun: (runId: string) => Promise<void>;

  /**
   * Open an SSE stream for the active run and begin accumulating events.
   *
   * No-op if `activeRun` is `null` or a stream is already open.
   */
  startStream: () => void;

  /** Close the active SSE stream. */
  stopStream: () => void;

  /** Reset all store state to its initial values. */
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

const _initialState = {
  activeRun: null,
  events: [] as CanvasEvent[],
  invariants: [] as CanvasInvariant[],
  streaming: false,
  currentStage: null as number | null,
  completedStages: [] as string[],
  failedStages: [] as string[],
  error: null as string | null,
};

/** Module-level reference so `stopStream` can close the EventSource. */
let _eventSource: EventSource | null = null;

function applyEvent(
  event: CanvasEvent,
  state: RunStoreState
): Partial<RunStoreState> {
  const updates: Partial<RunStoreState> = {
    events: [...state.events, event],
  };

  switch (event.event_type as EventTypeName) {
    case "stage_start": {
      const stage = event.payload?.stage as number | undefined;
      if (stage !== undefined) {
        updates.currentStage = stage;
      }
      break;
    }
    case "stage_complete": {
      const name = event.payload?.name as string | undefined;
      if (name && !state.completedStages.includes(name)) {
        updates.completedStages = [...state.completedStages, name];
      }
      updates.currentStage = null;
      break;
    }
    case "stage_fail": {
      const name = event.payload?.name as string | undefined;
      if (name && !state.failedStages.includes(name)) {
        updates.failedStages = [...state.failedStages, name];
      }
      updates.currentStage = null;
      break;
    }
    case "invariant_found": {
      const inv: CanvasInvariant = {
        invariant_id: event.payload?.invariant_id as string ?? "",
        run_id: event.run_id,
        tier: (event.payload?.tier as CanvasInvariant["tier"]) ?? "example",
        statement: event.payload?.statement as string ?? "",
        rationale: "",
        discovered_at: event.ts,
      };
      updates.invariants = [...state.invariants, inv];
      break;
    }
    case "run_complete": {
      const run = state.activeRun;
      if (run) {
        updates.activeRun = {
          ...run,
          status: "complete",
          verified: Boolean(event.payload?.verified),
          trust_level: (event.payload?.trust_level as TrustLevel) ?? "UNVERIFIED",
          finished_at: event.ts,
        };
      }
      updates.streaming = false;
      break;
    }
    default:
      break;
  }

  return updates;
}

function snapshotToSummary(snapshot: RunSnapshot): RunSummary {
  return {
    run_id: snapshot.run_id,
    spec_id: snapshot.spec_id,
    model: snapshot.model,
    status: snapshot.status,
    verified: snapshot.verified,
    trust_level: snapshot.trust_level,
    created_at: snapshot.created_at,
    finished_at: snapshot.finished_at,
  };
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useRunStore = create<RunStoreState>((set, get) => ({
  ..._initialState,

  createRun: async (body = {}) => {
    set({ error: null });
    try {
      const { run_id } = await createRun(body);
      set({
        activeRun: {
          run_id,
          spec_id: body.spec_id ?? "",
          model: body.model ?? "",
          status: "pending",
          verified: false,
          trust_level: "UNVERIFIED",
          created_at: Date.now() / 1000,
          finished_at: null,
        },
        events: [],
        invariants: [],
        completedStages: [],
        failedStages: [],
        currentStage: null,
      });
      return run_id;
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      set({ error: message });
      throw err;
    }
  },

  loadRun: async (runId: string) => {
    set({ error: null });
    try {
      const snapshot = await getRun(runId);
      set({
        activeRun: snapshotToSummary(snapshot),
        events: snapshot.events,
        invariants: snapshot.invariants,
        completedStages: snapshot.events
          .filter((e) => e.event_type === "stage_complete")
          .map((e) => String(e.payload?.name ?? "")),
        failedStages: snapshot.events
          .filter((e) => e.event_type === "stage_fail")
          .map((e) => String(e.payload?.name ?? "")),
        currentStage: null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      set({ error: message });
      throw err;
    }
  },

  startStream: () => {
    const { activeRun, streaming } = get();
    if (!activeRun || streaming) return;

    set({ streaming: true, error: null });
    _eventSource = streamRun(activeRun.run_id);

    // Listen for each named event type
    const eventTypes: EventTypeName[] = [
      "stage_start",
      "stage_complete",
      "stage_fail",
      "invariant_found",
      "run_complete",
    ];

    for (const eventType of eventTypes) {
      _eventSource.addEventListener(eventType, (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as CanvasEvent;
          set((state) => applyEvent(data, state));
        } catch {
          // Ignore malformed frames
        }
      });
    }

    _eventSource.onerror = () => {
      set({ streaming: false, error: "SSE connection lost" });
      _eventSource?.close();
      _eventSource = null;
    };
  },

  stopStream: () => {
    _eventSource?.close();
    _eventSource = null;
    set({ streaming: false });
  },

  reset: () => {
    _eventSource?.close();
    _eventSource = null;
    set({ ..._initialState });
  },
}));
