/**
 * Trust score formula for the Nightjar Verification Canvas.
 *
 * Translates the graduated `TrustLevel` labels (from `types.TrustLevel`
 * in Python) into numeric scores and human-readable display values.
 *
 * Thresholds are aligned with the SkillFortify trust algebra:
 *   FORMALLY_VERIFIED  >= 0.75
 *   PROPERTY_VERIFIED  >= 0.50
 *   SCHEMA_VERIFIED    >= 0.25
 *   UNVERIFIED         <  0.25
 *
 * References:
 *   - arxiv:2603.00195 DY-Skill threat model
 *   - qualixar/skillfortify src/skillfortify/core/trust/models.py
 */

import type { TrustLevel } from "./api-client";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Minimum numeric score (0–1) for each trust level. */
export const TRUST_THRESHOLDS: Readonly<Record<TrustLevel, number>> = {
  FORMALLY_VERIFIED: 0.75,
  PROPERTY_VERIFIED: 0.5,
  SCHEMA_VERIFIED: 0.25,
  UNVERIFIED: 0.0,
} as const;

/** Display labels shown in the UI for each trust level. */
export const TRUST_LABELS: Readonly<Record<TrustLevel, string>> = {
  FORMALLY_VERIFIED: "Formally Verified",
  PROPERTY_VERIFIED: "Property Verified",
  SCHEMA_VERIFIED: "Schema Verified",
  UNVERIFIED: "Unverified",
} as const;

/** Tailwind CSS colour token (background) per trust level. */
export const TRUST_COLOURS: Readonly<Record<TrustLevel, string>> = {
  FORMALLY_VERIFIED: "bg-green-500",
  PROPERTY_VERIFIED: "bg-blue-500",
  SCHEMA_VERIFIED: "bg-yellow-500",
  UNVERIFIED: "bg-gray-400",
} as const;

/** Hex colours for non-Tailwind contexts (e.g. shields.io badge). */
export const TRUST_HEX: Readonly<Record<TrustLevel, string>> = {
  FORMALLY_VERIFIED: "#22c55e",
  PROPERTY_VERIFIED: "#3b82f6",
  SCHEMA_VERIFIED: "#eab308",
  UNVERIFIED: "#9ca3af",
} as const;

// ---------------------------------------------------------------------------
// Functions
// ---------------------------------------------------------------------------

/**
 * Convert a `TrustLevel` to its minimum numeric score (0–1).
 *
 * @param level - The trust level label.
 * @returns A value in the range [0, 1].
 */
export function trustLevelToScore(level: TrustLevel): number {
  return TRUST_THRESHOLDS[level] ?? 0.0;
}

/**
 * Derive the `TrustLevel` label from a raw numeric pass-rate.
 *
 * Thresholds match the SkillFortify trust algebra.
 *
 * @param passRate - Fraction of verified runs (0–1).
 * @returns The corresponding `TrustLevel`.
 */
export function scoreToTrustLevel(passRate: number): TrustLevel {
  if (passRate >= TRUST_THRESHOLDS.FORMALLY_VERIFIED) return "FORMALLY_VERIFIED";
  if (passRate >= TRUST_THRESHOLDS.PROPERTY_VERIFIED) return "PROPERTY_VERIFIED";
  if (passRate >= TRUST_THRESHOLDS.SCHEMA_VERIFIED) return "SCHEMA_VERIFIED";
  return "UNVERIFIED";
}

/**
 * Compute a composite trust score from pipeline-stage data.
 *
 * The score is a weighted average of stage outcomes:
 *   - preflight  (stage 0) contributes 5 %
 *   - deps       (stage 1) contributes 10 %
 *   - schema     (stage 2) contributes 20 %
 *   - pbt        (stage 3) contributes 30 %
 *   - formal     (stage 4) contributes 35 %
 *
 * Each passing stage contributes its full weight; failing stages zero out
 * all higher stages (the pipeline halts on first failure).
 *
 * @param stagesPassed - Number of stages that passed (0–5).
 * @returns Composite score in [0, 1].
 */
export function computeCompositeScore(stagesPassed: number): number {
  const weights = [0.05, 0.1, 0.2, 0.3, 0.35];
  let score = 0;
  for (let i = 0; i < Math.min(stagesPassed, weights.length); i++) {
    score += weights[i];
  }
  return Math.min(Math.max(score, 0), 1);
}

/**
 * Return a human-readable label for a trust level.
 *
 * @param level - The trust level.
 */
export function trustLabel(level: TrustLevel): string {
  return TRUST_LABELS[level] ?? "Unknown";
}

/**
 * Return the Tailwind CSS background colour class for a trust level.
 *
 * @param level - The trust level.
 */
export function trustColour(level: TrustLevel): string {
  return TRUST_COLOURS[level] ?? "bg-gray-400";
}

/**
 * Format a pass-rate fraction as a percentage string.
 *
 * @example passRateDisplay(0.75) → "75%"
 */
export function passRateDisplay(passRate: number): string {
  return `${Math.round(passRate * 100)}%`;
}
