"use client";

/**
 * CrystallizationNode
 *
 * A motion/react wrapper that gives any node the crystallization entry
 * ceremony: the node starts at 50% opacity + 0.85 scale, trembles briefly
 * on the x-axis (±2px, 80ms), then snaps into full presence via the
 * expo-out curve (180ms total).
 *
 * Delegates all visual content to children — this component only provides
 * the entry animation, so it wraps B1's StageNode without duplicating its
 * interior layout.
 *
 * Usage:
 *   <CrystallizationNode staggerIndex={2}>
 *     <StageNode ... />
 *   </CrystallizationNode>
 */

import { type ReactNode } from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/cn";
import {
  crystallizeVariants,
  staggerDelay,
  EASE_CRYSTALLIZE,
} from "../canvas/crystallization";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface CrystallizationNodeProps {
  /**
   * Pipeline order index (0–5).  Drives the 60ms stagger delay so nodes
   * crystallize in topological order: Preflight first, Formal last.
   */
  staggerIndex: number;
  /** Node content. */
  children: ReactNode;
  /** Optional extra class on the motion wrapper. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * CrystallizationNode
 *
 * Applies the tremble-snap entry animation to its children.
 *
 * Animation spec:
 *   hidden : opacity 0.5, scale 0.85
 *   tremble: translateX oscillates ±2px over 80ms (linear, 5 keyframes)
 *   snap   : cubic-bezier(0.16, 1, 0.3, 1) to opacity 1 / scale 1 over 180ms
 */
export function CrystallizationNode({
  staggerIndex,
  children,
  className,
}: CrystallizationNodeProps) {
  return (
    <motion.div
      variants={crystallizeVariants}
      initial="hidden"
      animate="visible"
      // A bare `transition={{ delay }}` would OVERRIDE the variant's full
      // transition definition, discarding the 180ms duration and the 80ms
      // x-keyframe tremble timing.  Merge the delay with the full spec so the
      // crystallization character is preserved.
      transition={{
        delay: staggerDelay(staggerIndex),
        duration: 0.18,
        ease: EASE_CRYSTALLIZE as unknown as [number, number, number, number],
        x: {
          duration: 0.08,
          times: [0, 0.2, 0.4, 0.6, 0.8, 1] as number[],
          ease: "linear" as const,
        },
      }}
      className={cn("relative", className)}
    >
      {children}
    </motion.div>
  );
}
