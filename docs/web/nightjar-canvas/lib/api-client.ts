/**
 * Typed fetch wrapper for the Nightjar Canvas API.
 *
 * All requests target the FastAPI backend served by `nightjar.web_server`.
 * The base URL is resolved from the `NEXT_PUBLIC_API_URL` environment
 * variable with a localhost fallback for local development.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Trust-level labels matching `types.TrustLevel` in Python. */
export type TrustLevel =
  | "FORMALLY_VERIFIED"
  | "PROPERTY_VERIFIED"
  | "SCHEMA_VERIFIED"
  | "UNVERIFIED";

/** Run status values. */
export type RunStatus = "pending" | "running" | "complete" | "failed";

/** SSE event type names matching `web_events.EventType` in Python. */
export type EventTypeName =
  | "stage_start"
  | "stage_complete"
  | "stage_fail"
  | "invariant_found"
  | "run_complete";

/** A single SSE event as stored in the database. */
export interface CanvasEvent {
  event_id: number;
  run_id: string;
  seq: number;
  event_type: EventTypeName;
  payload: Record<string, unknown>;
  ts: number;
}

/** A canvas invariant record. */
export interface CanvasInvariant {
  invariant_id: string;
  run_id: string;
  tier: "example" | "property" | "formal";
  statement: string;
  rationale: string;
  discovered_at: number;
}

/** Full verification run snapshot returned by `GET /api/runs/{id}`. */
export interface RunSnapshot {
  run_id: string;
  spec_id: string;
  model: string;
  status: RunStatus;
  verified: boolean;
  trust_level: TrustLevel;
  created_at: number;
  finished_at: number | null;
  meta: Record<string, unknown>;
  events: CanvasEvent[];
  invariants: CanvasInvariant[];
}

/** Body for `POST /api/runs`. */
export interface CreateRunBody {
  spec_id?: string;
  model?: string;
  meta?: Record<string, unknown>;
}

/** Response from `POST /api/runs`. */
export interface CreateRunResponse {
  run_id: string;
}

/** Response from `GET /api/badge/{owner}/{name}`. */
export interface BadgeData {
  spec_id: string;
  pass_rate: number;
  trust_level: TrustLevel;
  run_count: number;
  badge_url: string;
}

/** Health check response. */
export interface HealthResponse {
  status: "ok";
  version: string;
}

// ---------------------------------------------------------------------------
// Client
// ---------------------------------------------------------------------------

/** Base URL resolved at module-load time from the environment. */
const BASE_URL: string =
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_URL) ||
  "http://localhost:8000";

/** Shared fetch helper with JSON body support. */
async function apiFetch<T>(
  path: string,
  init?: RequestInit & { json?: unknown }
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init?.headers as Record<string, string>),
  };

  let body: BodyInit | undefined;
  if (init?.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers,
    body: body ?? init?.body,
  });

  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText);
    throw new Error(
      `Nightjar API ${init?.method ?? "GET"} ${path} → ${response.status}: ${text}`
    );
  }

  return response.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------

/** Verify that the backend is reachable. */
export async function checkHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/api/health");
}

/**
 * Create a new verification run.
 *
 * @param body - Optional spec_id, model, and metadata.
 * @returns The new run's UUID.
 */
export async function createRun(
  body: CreateRunBody = {}
): Promise<CreateRunResponse> {
  return apiFetch<CreateRunResponse>("/api/runs", {
    method: "POST",
    json: body,
  });
}

/**
 * Fetch a full run snapshot, including events and invariants.
 *
 * @param runId - UUID4 run identifier.
 */
export async function getRun(runId: string): Promise<RunSnapshot> {
  return apiFetch<RunSnapshot>(`/api/runs/${encodeURIComponent(runId)}`);
}

/**
 * Fetch only the stored event log for a run.
 *
 * @param runId - UUID4 run identifier.
 */
export async function getRunEvents(runId: string): Promise<CanvasEvent[]> {
  return apiFetch<CanvasEvent[]>(
    `/api/runs/${encodeURIComponent(runId)}/events`
  );
}

/**
 * Open a live SSE stream for a run.
 *
 * Returns an `EventSource` connected to `GET /api/runs/{id}/stream`.
 * The caller is responsible for calling `.close()` when done.
 *
 * @example
 * ```ts
 * const es = streamRun(runId);
 * es.addEventListener("stage_complete", (e) => console.log(e.data));
 * es.addEventListener("run_complete",   () => es.close());
 * ```
 */
export function streamRun(runId: string): EventSource {
  return new EventSource(
    `${BASE_URL}/api/runs/${encodeURIComponent(runId)}/stream`
  );
}

/**
 * Fetch trust-score data for a badge.
 *
 * @param owner - Repository owner / organisation slug.
 * @param name  - Repository or module name.
 */
export async function getBadge(
  owner: string,
  name: string
): Promise<BadgeData> {
  return apiFetch<BadgeData>(
    `/api/badge/${encodeURIComponent(owner)}/${encodeURIComponent(name)}`
  );
}
