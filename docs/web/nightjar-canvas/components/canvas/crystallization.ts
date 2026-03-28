/**
 * Nightjar Verification Canvas — Crystallization Animation Constants
 *
 * Crystal nucleation metaphor: nodes "crystallize" into existence from
 * an uncertain amber haze into hard, mathematically-verified form.
 *
 * Visual soul: "candlelight in a precision instrument shop"
 * The animation mirrors the moment amber solidifies — a trembling snap,
 * not a gentle fade.
 */

// ---------------------------------------------------------------------------
// Easing
// ---------------------------------------------------------------------------

/** Expo-out cubic bezier. Used for the crystallize snap. */
export const EASE_CRYSTALLIZE = [0.16, 1, 0.3, 1] as const;

// ---------------------------------------------------------------------------
// Crystallization entry animation variants (motion/react)
// ---------------------------------------------------------------------------

/** Node entry: shimmer→tremble→snap into place */
export const crystallizeVariants = {
  hidden: {
    opacity: 0.5,
    scale: 0.85,
    x: 0,
  },
  /**
   * Visible state. The tremble is achieved with a keyframes array on x,
   * simulating crystal nucleation micro-vibration before final snap.
   */
  visible: {
    opacity: 1,
    scale: 1,
    x: [0, 2, -2, 1, -1, 0] as number[],
    transition: {
      duration: 0.18, // 180ms total
      ease: EASE_CRYSTALLIZE as unknown as [number, number, number, number],
      x: {
        duration: 0.08, // 80ms tremble on x
        times: [0, 0.2, 0.4, 0.6, 0.8, 1] as number[],
        ease: "linear" as const,
      },
    },
  },
};

/**
 * Stagger delay between pipeline nodes (topological order).
 * 6 nodes × 60ms = 360ms for full pipeline reveal.
 */
export const STAGE_STAGGER_DELAY_MS = 60;

/** Convert stagger index to seconds for motion delay. */
export function staggerDelay(index: number): number {
  return (index * STAGE_STAGGER_DELAY_MS) / 1000;
}

// ---------------------------------------------------------------------------
// Amber pulse (Running state) — ring animation
// ---------------------------------------------------------------------------

export const amberPulseRingVariants = {
  idle: { scale: 1, opacity: 0 },
  pulse: {
    scale: [1, 1.5, 2] as number[],
    opacity: [0.8, 0.4, 0] as number[],
    transition: {
      duration: 1.2,
      repeat: Infinity,
      ease: "easeOut" as const,
    },
  },
};

// ---------------------------------------------------------------------------
// Proven glow ring (Proven state) — one-shot expanding ring
// ---------------------------------------------------------------------------

export const provenRingVariants = {
  hidden: { scale: 1, opacity: 1 },
  burst: {
    scale: 2.5,
    opacity: 0,
    transition: {
      duration: 1.2,
      ease: "easeOut" as const,
    },
  },
};

// ---------------------------------------------------------------------------
// State → color mapping (amber palette — no purple/violet/green)
// ---------------------------------------------------------------------------

export type StageState =
  | "pending"
  | "running"
  | "pbt_pass"
  | "formal_pass"
  | "proven"
  | "failed";

export interface StateColors {
  border: string;
  fill: string;
  fillOpacity: number;
  glow?: string;
  text: string;
}

export const STATE_COLORS: Record<StageState, StateColors> = {
  pending: {
    border: "#3A2E10",
    fill: "#3A2E10",
    fillOpacity: 0,
    text: "#8B8579",
  },
  running: {
    border: "#D4920A",
    fill: "#3A2E10",
    fillOpacity: 1,
    glow: "0 0 12px rgba(212,146,10,0.35)",
    text: "#D4920A",
  },
  pbt_pass: {
    border: "#A87020",
    fill: "#A87020",
    fillOpacity: 0.2,
    text: "#A87020",
  },
  formal_pass: {
    border: "#F5B93A",
    fill: "#F5B93A",
    fillOpacity: 0.25,
    glow: "0 0 12px rgba(245,185,58,0.3)",
    text: "#F5B93A",
  },
  proven: {
    border: "#FFD060",
    fill: "#FFD060",
    fillOpacity: 0.3,
    glow: "0 0 20px rgba(255,208,96,0.5)",
    text: "#FFD060",
  },
  failed: {
    border: "#C84B2F",
    fill: "#C84B2F",
    fillOpacity: 0.2,
    text: "#C84B2F",
  },
};

// ---------------------------------------------------------------------------
// Edge variant types — values must match keys in amberEdgeTypes registry
// ---------------------------------------------------------------------------

export type EdgeVariant = "amberParticle" | "amberCompleted" | "blocked";

/**
 * Derive edge variant from source + target state.
 * - If source has failed: blocked
 * - If source is running or pending: amberParticle (active)
 * - If source is any pass/proven: amberCompleted
 */
export function deriveEdgeVariant(
  sourceState: StageState,
  targetState: StageState
): EdgeVariant {
  if (sourceState === "failed" || targetState === "failed") return "blocked";
  if (sourceState === "running") return "amberParticle";
  if (
    sourceState === "pbt_pass" ||
    sourceState === "formal_pass" ||
    sourceState === "proven"
  ) {
    return "amberCompleted";
  }
  if (targetState === "running") return "amberParticle";
  return "blocked";
}
