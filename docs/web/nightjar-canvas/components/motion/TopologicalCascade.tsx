"use client";

/**
 * TopologicalCascade
 *
 * Orchestrates the 6-stage unlock sequence when a verification run completes.
 *
 * Timing spec:
 *   Preflight  t = 0 ms
 *   Deps       t = 60 ms
 *   Schema     t = 120 ms
 *   PBT        t = 180 ms
 *   Negation   t = 240 ms
 *   Formal     t = 300 ms
 *
 * Per-node ceremony (300 ms total):
 *   0–100 ms  : flash to #FFD060 (bright gold)
 *   100–300 ms: settle to #F5B93A (warm gold)
 *
 * The cascade fires when `triggered` transitions from false → true.
 * It does NOT loop and does NOT partially fire (all-or-nothing on `triggered`).
 *
 * Usage:
 *   <TopologicalCascade
 *     triggered={allPassed}
 *     runId={runId}
 *     stageStates={stageStateMap}
 *   >
 *     {({ flashColor, isUnlocked, staggerIndex }) => (
 *       <StageNode style={{ borderColor: flashColor }} ... />
 *     )}
 *   </TopologicalCascade>
 *
 * The render-prop pattern lets callers wire the flash color into their
 * existing StageNode without this component owning the node layout.
 */

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { type ReactNode } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Pipeline stage names in topological order. */
export type CascadeStageName =
  | "preflight"
  | "deps"
  | "schema"
  | "pbt"
  | "negation"
  | "formal";

/** 0-indexed position of each stage in the cascade. */
const STAGE_ORDER: Record<CascadeStageName, number> = {
  preflight: 0,
  deps: 1,
  schema: 2,
  pbt: 3,
  negation: 4,
  formal: 5,
};

/** Stagger step between stage unlocks (ms). */
const STAGGER_MS = 60;

/** Duration of the bright flash (#FFD060) phase (ms). */
const FLASH_DURATION_MS = 100;

/** Duration of the settle (#F5B93A) phase (ms). */
const SETTLE_DURATION_MS = 200;

/** Color during flash phase. */
const FLASH_COLOR = "#FFD060";

/** Color after settling. */
const SETTLE_COLOR = "#F5B93A";

// ---------------------------------------------------------------------------
// Per-stage animation state
// ---------------------------------------------------------------------------

type StagePhase = "idle" | "flash" | "settled";

interface StageAnimState {
  phase: StagePhase;
  /** Resolved color for border/text — consumers can read this directly. */
  color: string;
}

function initialStageState(): StageAnimState {
  return { phase: "idle", color: SETTLE_COLOR };
}

// ---------------------------------------------------------------------------
// Render prop shape exposed to children
// ---------------------------------------------------------------------------

export interface CascadeRenderProps {
  /** Current flash color (#FFD060 during flash, #F5B93A when settled, undefined when idle). */
  flashColor: string | undefined;
  /** True once this stage's cascade animation has completed. */
  isUnlocked: boolean;
  /** 0-based stagger index (for positioning / motion delays). */
  staggerIndex: number;
  /** Current animation phase for this node. */
  phase: StagePhase;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface TopologicalCascadeProps {
  /**
   * Whether to fire the cascade.  Fires once per `runId` when this
   * transitions from false → true.
   */
  triggered: boolean;
  /**
   * Run identifier.  Changing this resets the cascade so a new run
   * can trigger it again.
   */
  runId?: string;
  /** Ordered list of stages to animate (must be in topological order). */
  stages?: CascadeStageName[];
  /**
   * Render prop called once per stage.  Return the node content.
   * The returned element is wrapped in a motion.div that applies the
   * cascade timing — callers don't need to manage delays themselves.
   */
  children: (stageName: CascadeStageName, props: CascadeRenderProps) => ReactNode;
  /** Class applied to each per-stage motion.div wrapper. */
  itemClassName?: string;
}

// ---------------------------------------------------------------------------
// Default stage order
// ---------------------------------------------------------------------------

const DEFAULT_STAGES: CascadeStageName[] = [
  "preflight",
  "deps",
  "schema",
  "pbt",
  "negation",
  "formal",
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * TopologicalCascade
 *
 * Fires a 60 ms-staggered unlock sequence across all pipeline nodes.
 * Each node flashes bright gold (#FFD060) for 100 ms then settles to
 * warm gold (#F5B93A) over the following 200 ms.
 *
 * The cascade is purely presentational — it surfaces `flashColor` and
 * `isUnlocked` to the render prop so callers can wire them into their
 * existing node components.
 */
export function TopologicalCascade({
  triggered,
  runId = "default",
  stages = DEFAULT_STAGES,
  children,
  itemClassName,
}: TopologicalCascadeProps) {
  const prefersReduced = useReducedMotion();

  // Per-stage animation state
  const [stageStates, setStageStates] = useState<Record<CascadeStageName, StageAnimState>>(
    () => {
      const init = {} as Record<CascadeStageName, StageAnimState>;
      stages.forEach((s) => { init[s] = initialStageState(); });
      return init;
    }
  );

  // Guard: track the runId for which the cascade has already fired.
  const firedForRunRef = useRef<string | null>(null);
  // Collect all timeout handles for cleanup.
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Reset on new run.
  useEffect(() => {
    firedForRunRef.current = null;
    // Clear pending timers from the previous run.
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = [];
    // Reset all stages to idle.
    setStageStates(() => {
      const reset = {} as Record<CascadeStageName, StageAnimState>;
      stages.forEach((s) => { reset[s] = initialStageState(); });
      return reset;
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  useEffect(() => {
    if (!triggered) return;
    if (firedForRunRef.current === runId) return;

    firedForRunRef.current = runId;

    // Clear any leftover timers (defensive).
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = [];

    stages.forEach((stageName, idx) => {
      const staggerOffset = idx * STAGGER_MS;

      // Flash phase: fire at staggerOffset
      const flashTimer = setTimeout(() => {
        setStageStates((prev) => ({
          ...prev,
          [stageName]: { phase: "flash", color: FLASH_COLOR },
        }));
      }, staggerOffset);

      // Settle phase: fire at staggerOffset + FLASH_DURATION_MS
      const settleTimer = setTimeout(() => {
        setStageStates((prev) => ({
          ...prev,
          [stageName]: { phase: "settled", color: SETTLE_COLOR },
        }));
      }, staggerOffset + FLASH_DURATION_MS);

      timeoutsRef.current.push(flashTimer, settleTimer);
    });

    return () => {
      timeoutsRef.current.forEach(clearTimeout);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggered, runId]);

  return (
    <>
      {stages.map((stageName) => {
        const animState = stageStates[stageName] ?? initialStageState();
        const staggerIndex = STAGE_ORDER[stageName] ?? 0;

        const renderProps: CascadeRenderProps = {
          flashColor: animState.phase !== "idle" ? animState.color : undefined,
          isUnlocked: animState.phase === "settled",
          staggerIndex,
          phase: animState.phase,
        };

        // When reduced motion is preferred, skip the motion wrapper entirely.
        if (prefersReduced) {
          return (
            <div key={stageName} className={itemClassName}>
              {children(stageName, renderProps)}
            </div>
          );
        }

        // `transition` must be a separate prop on motion.div — placing it
        // inside `animate` treats it as an animation target value and silently
        // ignores it, causing the flash/settle durations to be wrong.
        const phase = animState.phase;
        const animateTarget =
          phase === "flash"
            ? { filter: "brightness(1.15)" }
            : { filter: "brightness(1)" };

        const transitionConfig =
          phase === "flash"
            ? {
                duration: FLASH_DURATION_MS / 1000,
                ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
              }
            : phase === "settled"
            ? {
                duration: SETTLE_DURATION_MS / 1000,
                ease: "easeOut" as const,
              }
            : { duration: 0 };

        return (
          <motion.div
            key={stageName}
            className={itemClassName}
            animate={animateTarget}
            transition={transitionConfig}
          >
            {children(stageName, renderProps)}
          </motion.div>
        );
      })}
    </>
  );
}

// ---------------------------------------------------------------------------
// Utility: derive flash color for a single node given its stagger offset
// ---------------------------------------------------------------------------

/**
 * Standalone utility for callers that don't use the full TopologicalCascade
 * component but want to drive a single node's flash color imperatively.
 *
 * Returns cleanup function.
 */
export function fireNodeFlash(
  onFlash: (color: string) => void,
  onSettle: (color: string) => void,
  staggerIndex: number
): () => void {
  const offset = staggerIndex * STAGGER_MS;
  const t1 = setTimeout(() => onFlash(FLASH_COLOR), offset);
  const t2 = setTimeout(() => onSettle(SETTLE_COLOR), offset + FLASH_DURATION_MS);
  return () => { clearTimeout(t1); clearTimeout(t2); };
}
