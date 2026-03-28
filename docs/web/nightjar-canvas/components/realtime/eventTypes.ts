/**
 * Typed Zod schemas for Nightjar SSE events.
 *
 * These schemas mirror the Python `web_events.py` types exactly:
 *   - EventType enum → z.literal union
 *   - CanvasEvent dataclass → CanvasEventSchema
 *   - Per-event payload schemas for discriminated access
 *
 * Usage:
 * ```ts
 * const event = CanvasEventSchema.parse(JSON.parse(rawData));
 * // event is fully typed — event.event_type narrows payload
 * ```
 */

import { z } from "zod";

// ---------------------------------------------------------------------------
// Event type literals — match EventType enum in web_events.py
// ---------------------------------------------------------------------------

export const EventTypeSchema = z.literal([
  "stage_start",
  "stage_complete",
  "stage_fail",
  "log_line",
  "invariant_found",
  "run_complete",
]);

export type EventTypeName = z.infer<typeof EventTypeSchema>;

// ---------------------------------------------------------------------------
// Per-event payload schemas
// ---------------------------------------------------------------------------

/** Payload for stage_start */
export const StageStartPayloadSchema = z.object({
  stage: z.number().int(),
  name: z.string(),
});

/** Payload for stage_complete */
export const StageCompletePayloadSchema = z.object({
  stage: z.number().int(),
  name: z.string(),
  duration_ms: z.number().int().default(0),
});

/** Payload for stage_fail */
export const StageFailPayloadSchema = z.object({
  stage: z.number().int(),
  name: z.string(),
  errors: z.array(z.record(z.string(), z.unknown())).default([]),
});

/** Payload for log_line (not yet in Python web_events.py — reserved for Phase 6.1) */
export const LogLinePayloadSchema = z.object({
  stage: z.number().int(),
  text: z.string(),
  level: z.literal(["info", "warn", "error"]).optional(),
});

/** Payload for invariant_found */
export const InvariantFoundPayloadSchema = z.object({
  invariant_id: z.string(),
  statement: z.string(),
  tier: z.literal(["example", "property", "formal"]),
});

/** Payload for run_complete */
export const RunCompletePayloadSchema = z.object({
  verified: z.boolean(),
  trust_level: z.literal([
    "FORMALLY_VERIFIED",
    "PROPERTY_VERIFIED",
    "SCHEMA_VERIFIED",
    "UNVERIFIED",
  ]),
  total_duration_ms: z.number().int().default(0),
});

// ---------------------------------------------------------------------------
// Discriminated union — one schema per event_type
// ---------------------------------------------------------------------------

export const StageStartEventSchema = z.object({
  event_type: z.literal("stage_start"),
  run_id: z.string(),
  payload: StageStartPayloadSchema,
  ts: z.number(),
  seq: z.number().int(),
});

export const StageCompleteEventSchema = z.object({
  event_type: z.literal("stage_complete"),
  run_id: z.string(),
  payload: StageCompletePayloadSchema,
  ts: z.number(),
  seq: z.number().int(),
});

export const StageFailEventSchema = z.object({
  event_type: z.literal("stage_fail"),
  run_id: z.string(),
  payload: StageFailPayloadSchema,
  ts: z.number(),
  seq: z.number().int(),
});

export const LogLineEventSchema = z.object({
  event_type: z.literal("log_line"),
  run_id: z.string(),
  payload: LogLinePayloadSchema,
  ts: z.number(),
  seq: z.number().int(),
});

export const InvariantFoundEventSchema = z.object({
  event_type: z.literal("invariant_found"),
  run_id: z.string(),
  payload: InvariantFoundPayloadSchema,
  ts: z.number(),
  seq: z.number().int(),
});

export const RunCompleteEventSchema = z.object({
  event_type: z.literal("run_complete"),
  run_id: z.string(),
  payload: RunCompletePayloadSchema,
  ts: z.number(),
  seq: z.number().int(),
});

/**
 * Discriminated union over all SSE event variants.
 * Mirrors the CanvasEvent dataclass in web_events.py.
 * log_line is reserved for Phase 6.1 (not yet in Python web_events.py).
 */
export const CanvasEventSchema = z.discriminatedUnion("event_type", [
  StageStartEventSchema,
  StageCompleteEventSchema,
  StageFailEventSchema,
  LogLineEventSchema,
  InvariantFoundEventSchema,
  RunCompleteEventSchema,
]);

export type CanvasEvent = z.infer<typeof CanvasEventSchema>;
export type StageStartEvent = z.infer<typeof StageStartEventSchema>;
export type StageCompleteEvent = z.infer<typeof StageCompleteEventSchema>;
export type StageFailEvent = z.infer<typeof StageFailEventSchema>;
export type LogLineEvent = z.infer<typeof LogLineEventSchema>;
export type InvariantFoundEvent = z.infer<typeof InvariantFoundEventSchema>;
export type RunCompleteEvent = z.infer<typeof RunCompleteEventSchema>;

// ---------------------------------------------------------------------------
// Payload type helpers (narrowed access after discriminant check)
// ---------------------------------------------------------------------------

export type StageStartPayload = z.infer<typeof StageStartPayloadSchema>;
export type StageCompletePayload = z.infer<typeof StageCompletePayloadSchema>;
export type StageFailPayload = z.infer<typeof StageFailPayloadSchema>;
export type LogLinePayload = z.infer<typeof LogLinePayloadSchema>;
export type InvariantFoundPayload = z.infer<typeof InvariantFoundPayloadSchema>;
export type RunCompletePayload = z.infer<typeof RunCompletePayloadSchema>;

export type TrustLevel = z.infer<typeof RunCompletePayloadSchema>["trust_level"];
export type InvariantTier = z.infer<typeof InvariantFoundPayloadSchema>["tier"];
