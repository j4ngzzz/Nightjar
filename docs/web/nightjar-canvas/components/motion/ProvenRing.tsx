"use client";

/**
 * ProvenRing
 *
 * The emotional climax of the verification experience.
 *
 * Fires ONCE when every pipeline stage reaches a terminal pass state.
 * A golden ring expands from the root node: scale 1→8, opacity 1→0,
 * over 1.2 s with an expo-out easing (cubic-bezier 0.16, 1, 0.3, 1).
 *
 * Rules:
 *   - NOT on partial pass (any stage still pending/running/failed).
 *   - NOT looping.  AnimatePresence removes the element after 1.2 s.
 *   - Color: #FFD060.  boxShadow: 0 0 20px rgba(255, 208, 96, 0.6).
 *   - No spring bounce — must feel WEIGHTY, not playful.
 *
 * Usage:
 *   <ProvenRing allPassed={stageStates.every(s => s === "proven")} />
 *
 * The `allPassed` flag is the ONLY trigger.  Pass false when the run is
 * in-progress or has any failure.  Pass true once — the component fires
 * and disappears; subsequent renders with allPassed=true re-trigger
 * only if `runId` changes (prevents false re-fires on parent re-renders).
 */

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";

// ---------------------------------------------------------------------------
// Design tokens — kept local, no import needed
// ---------------------------------------------------------------------------
const RING_COLOR = "#FFD060";
const RING_GLOW = "0 0 20px rgba(255, 208, 96, 0.6)";

/** Total ring animation duration in seconds. Must match easing curve. */
const BURST_DURATION = 1.2;

/** Expo-out cubic bezier — weighty, decisive, not playful. */
const EASE_EXPO_OUT: [number, number, number, number] = [0.16, 1, 0.3, 1];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface ProvenRingProps {
  /**
   * True when every pipeline stage has passed (proven).
   * The ring fires once per transition from false → true within the same
   * `runId`.  Changing `runId` resets the "has fired" guard so the next
   * full pass plays the ceremony again.
   */
  allPassed: boolean;
  /**
   * Identifier for the current verification run.  Changing this resets
   * the "ring has fired" guard so a new full pass plays the ceremony.
   * Defaults to a static string — callers should pass the actual run ID.
   */
  runId?: string;
  /**
   * Size in px of the ring at scale(1).  Should match the node that the
   * ring expands from (default: 32 — the 8×8 Tailwind w-8/h-8 status ring).
   */
  baseSize?: number;
  /** Additional class on the wrapper <div> (for positioning). */
  className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * ProvenRing
 *
 * Renders a zero-size absolute-positioned ring element.  When `allPassed`
 * flips to true, AnimatePresence mounts the ring, motion drives it from
 * scale(1) opacity(1) → scale(8) opacity(0), then AnimatePresence removes
 * the DOM node once the exit is complete.
 *
 * The one-shot guard (`hasRungRef`) lives inside the component so each
 * instance is independent.
 */
export function ProvenRing({
  allPassed,
  runId = "default",
  baseSize = 32,
  className,
}: ProvenRingProps) {
  // Whether the ring is currently visible (mounted inside AnimatePresence).
  const [visible, setVisible] = useState(false);

  // Guard: track the runId for which the ring has already fired.
  const firedForRunRef = useRef<string | null>(null);

  useEffect(() => {
    // Step 1: if this is a new run (runId changed), always reset state first.
    // Merging reset + fire into one effect prevents the two-effect race where
    // the reset clears firedForRunRef and then the fire effect immediately
    // re-triggers when allPassed is already true.
    if (firedForRunRef.current !== null && firedForRunRef.current !== runId) {
      firedForRunRef.current = null;
      setVisible(false);
    }

    // Step 2: gate on allPassed.
    if (!allPassed) return;

    // Step 3: fire only once per runId.
    if (firedForRunRef.current === runId) return;

    firedForRunRef.current = runId;
    setVisible(true);

    // Auto-dismiss after the burst completes + 100ms buffer.
    const dismissTimeout = setTimeout(() => {
      setVisible(false);
    }, (BURST_DURATION + 0.1) * 1000);

    return () => clearTimeout(dismissTimeout);
  }, [allPassed, runId]);

  return (
    /*
     * Outer wrapper: zero-width/height, positioned relative to whatever
     * container the caller places it in.  The ring expands outward from
     * this anchor point via scale().
     */
    <div
      className={className}
      style={{
        position: "relative",
        width: baseSize,
        height: baseSize,
        pointerEvents: "none",
      }}
      aria-hidden
    >
      <AnimatePresence>
        {visible && (
          <motion.div
            key={`proven-ring-${runId}`}
            style={{
              position: "absolute",
              inset: 0,
              borderRadius: "50%",
              border: `2px solid ${RING_COLOR}`,
              boxShadow: RING_GLOW,
              // Ensure the ring is centered when scaling beyond its box
              transformOrigin: "center center",
            }}
            initial={{ scale: 1, opacity: 1 }}
            animate={{
              scale: 8,
              opacity: 0,
            }}
            exit={{
              // Already invisible at this point — instant exit
              opacity: 0,
            }}
            transition={{
              duration: BURST_DURATION,
              ease: EASE_EXPO_OUT,
              // Explicit property transitions — no spring, no bounce
              scale: { duration: BURST_DURATION, ease: EASE_EXPO_OUT },
              opacity: { duration: BURST_DURATION, ease: EASE_EXPO_OUT },
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
