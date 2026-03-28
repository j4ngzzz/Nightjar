"use client";

/**
 * AmberPulse
 *
 * Breathing idle animation for nodes that have reached proven state.
 *
 * Behavior:
 *   - Activates 1.3 s after the ProvenRing burst completes.
 *   - Every 4–6 s (random jitter per instance): scale 1.0 → 1.02 → 1.0
 *     over 800 ms, ease-in-out.
 *   - Barely perceptible at 100% zoom.  Visible but subtle at 200% zoom.
 *   - NOT aggressive.  No large scale jumps, no color flashes.
 *
 * Props:
 *   active   — set true once the ProvenRing burst has completed
 *   children — the node content that breathes
 *
 * Implementation notes:
 *   - Uses motion/react `animate` prop with a keyframes array for the
 *     scale so the 1→1.02→1 triple-point is explicit and deterministic.
 *   - The repeat delay is randomised with `Math.random()` on first mount
 *     so multiple proven nodes don't pulse in sync.
 *   - `transition.repeatDelay` handles the 4–6 s window.
 */

import { type ReactNode, useState } from "react";
import { motion, useReducedMotion } from "motion/react";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Delay after ProvenRing burst before breathing starts (seconds). */
const BREATH_START_DELAY = 1.3;

/** Duration of one breath cycle in seconds. */
const BREATH_DURATION = 0.8;

/** Minimum repeat delay between breaths (seconds). */
const REPEAT_DELAY_MIN = 4;

/** Maximum repeat delay between breaths (seconds). */
const REPEAT_DELAY_MAX = 6;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Returns a random repeat delay in the [min, max] range.
 * Called once per instance at render time — stable for the component's
 * lifetime because it's at module scope within the function body.
 */
function randomRepeatDelay(): number {
  return REPEAT_DELAY_MIN + Math.random() * (REPEAT_DELAY_MAX - REPEAT_DELAY_MIN);
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface AmberPulseProps {
  /**
   * Whether the breathing animation is active.
   * Set to true once the ProvenRing burst has fully completed.
   * When false, the wrapper renders children without any animation.
   */
  active: boolean;
  /** Content to breathe (typically a StageNode or CrystallizationNode). */
  children: ReactNode;
  /** Additional class on the wrapper. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * AmberPulse
 *
 * Wraps children in a motion.div that breathes when `active`.
 * Respects `prefers-reduced-motion` — if the user has that system
 * preference set, the animation is suppressed entirely.
 */
export function AmberPulse({ active, children, className }: AmberPulseProps) {
  const prefersReduced = useReducedMotion();

  // Stabilize via useState initializer — computed exactly once per component
  // instance, regardless of how many times the parent re-renders.  Calling
  // randomRepeatDelay() directly in the function body would produce a new
  // delay on every render, causing the motion transition to be recreated and
  // restarting the breathing animation mid-cycle.
  const [repeatDelay] = useState(() => randomRepeatDelay());

  // Disabled states: user prefers reduced motion, or the proven ring hasn't
  // completed yet.
  if (prefersReduced || !active) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      style={{ transformOrigin: "center center" }}
      animate={{
        // Triple-point keyframe: rest → inhale → rest
        scale: [1, 1.02, 1],
      }}
      transition={{
        // Start 1.3 s after mount (ProvenRing burst window)
        delay: BREATH_START_DELAY,
        duration: BREATH_DURATION,
        ease: "easeInOut",
        // Repeat indefinitely with random jitter between cycles
        repeat: Infinity,
        repeatDelay,
        // Use "mirror" repeat type so we always return to scale(1) cleanly
        repeatType: "loop",
      }}
    >
      {children}
    </motion.div>
  );
}
