"use client";

/**
 * VerificationSeal.tsx
 *
 * 200×200 generative hexagonal SVG — the cryptographic fingerprint made visual.
 *
 * Each proofHash deterministically generates a unique snowflake-like glyph.
 * On first render the geometry "crystallises": the outer hexagon appears
 * instantly, then each interior line draws itself via SVG stroke-dashoffset,
 * staggered 20 ms apart, over a total 600 ms window.
 *
 * No purple/violet colours appear anywhere.  Palette is strictly amber → gold.
 *
 * Props
 * -----
 * proofHash  — hex string (typically SHA-256); drives all geometry
 * size       — bounding box side in px (default 200)
 * className  — additional Tailwind classes for the wrapper <div>
 * animate    — set false to skip the crystallise animation (e.g. for SSR previews)
 */

import { useEffect, useRef, useState } from "react";
import {
  generateSeal,
  hexRingPoints,
  pointsToSvgAttr,
  type SealGeometry,
} from "./sealGenerator";

// ---------------------------------------------------------------------------
// Design tokens — kept local so this component is self-contained
// ---------------------------------------------------------------------------
const AMBER = "#D4920A";
const GOLD = "#F5B93A";
const BG = "#0D0B09";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface VerificationSealProps {
  proofHash: string;
  size?: number;
  className?: string;
  /** Whether to play the crystallisation animation on mount (default: true) */
  animate?: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Target total wall-clock time for the full crystallisation to complete. */
const TOTAL_DURATION_MS = 600;
/** Each individual line draw takes this long once it starts. */
const LINE_DRAW_MS = 100;
/** Ideal stagger between successive line reveals (20ms per spec). */
const IDEAL_STAGGER_MS = 20;

/**
 * Compute the actual inter-line stagger for a given line count.
 *
 * We want the last line to start no later than TOTAL_DURATION_MS − LINE_DRAW_MS
 * so the complete reveal fits inside TOTAL_DURATION_MS.
 *
 * With IDEAL_STAGGER_MS = 20 this is exact up to (600−100)/20 = 25 lines.
 * For larger line counts we compress the stagger proportionally.
 */
function computeStagger(lineCount: number): number {
  if (lineCount <= 1) return 0;
  const availableMs = TOTAL_DURATION_MS - LINE_DRAW_MS;
  return Math.min(IDEAL_STAGGER_MS, Math.floor(availableMs / (lineCount - 1)));
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function VerificationSeal({
  proofHash,
  size = 200,
  className,
  animate = true,
}: VerificationSealProps) {
  // Generate geometry synchronously — pure math, instant.
  const geometry: SealGeometry = generateSeal(proofHash, size);
  const { hexVertices, rings, lines, cx, cy, r, shortHash } = geometry;

  // Track which lines have "crystallised" (drawn in).
  const [revealedCount, setRevealedCount] = useState<number>(animate ? 0 : lines.length);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    if (!animate) {
      setRevealedCount(lines.length);
      return;
    }

    // Reset on every new proofHash.
    setRevealedCount(0);
    // Clear any lingering timers from a previous hash.
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];

    // Compute the actual stagger so all lines complete within TOTAL_DURATION_MS.
    const stagger = computeStagger(lines.length);

    // Schedule one setState per line with the computed stagger.
    lines.forEach((_, idx) => {
      const t = setTimeout(() => {
        setRevealedCount((prev) => Math.max(prev, idx + 1));
      }, idx * stagger);
      timersRef.current.push(t);
    });

    return () => {
      timersRef.current.forEach(clearTimeout);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [proofHash, animate]);

  const hexPoints = pointsToSvgAttr(hexVertices);

  // Text positioning — "VERIFIED" sits near the bottom of the hexagon,
  // the short hash lives just below it.
  const labelY = cy + r * 0.72;
  const hashY = labelY + 11;

  // Center diamond (3×3 rotated square)
  const diamondHalf = 3;

  return (
    <div
      className={className}
      style={{ width: size, height: size, flexShrink: 0 }}
      aria-label={`Verification seal for proof ${shortHash}`}
      role="img"
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        xmlns="http://www.w3.org/2000/svg"
        overflow="visible"
      >
        {/* Background fill */}
        <rect width={size} height={size} fill={BG} rx={2} ry={2} />

        {/* Outer hexagon — appears immediately, no animation */}
        <polygon
          points={hexPoints}
          fill="none"
          stroke={AMBER}
          strokeWidth={1.5}
          strokeLinejoin="round"
        />

        {/* Concentric hexagonal rings — 60% opacity amber */}
        {rings.map((ringR, i) => (
          <polygon
            key={`ring-${i}`}
            points={hexRingPoints(cx, cy, ringR)}
            fill="none"
            stroke={AMBER}
            strokeWidth={0.5}
            strokeLinejoin="round"
            opacity={0.6}
          />
        ))}

        {/* Interior snowflake lines — crystallise staggered.
            Each line is mounted at its reveal time (via revealedCount state).
            On mount, stroke-dashoffset equals the full line length (invisible).
            The CSS animation drives it to 0 over LINE_DRAW_MS ms.
            Because the element is brand-new each time it mounts, the
            animation always plays from the `from` frame. */}
        {lines.map((seg, idx) => {
          const visible = idx < revealedCount;
          if (!visible) return null;

          const len = seg.length;

          // Unique animation name per line length bucket so each element gets
          // its own @keyframes `from` value without CSS custom properties.
          // We round to 1 decimal to keep the style block small.
          const lenKey = len.toFixed(1).replace(".", "_");
          const animName = `nj-draw-${lenKey}`;

          return (
            <line
              key={`line-${idx}`}
              x1={seg.x1}
              y1={seg.y1}
              x2={seg.x2}
              y2={seg.y2}
              stroke={AMBER}
              strokeWidth={0.5}
              opacity={0.4}
              strokeLinecap="round"
              style={{
                strokeDasharray: len,
                strokeDashoffset: animate ? len : 0,
                animation: animate
                  ? `${animName} ${LINE_DRAW_MS}ms cubic-bezier(0.16, 1, 0.3, 1) forwards`
                  : "none",
              }}
            />
          );
        })}

        {/* Center diamond — 3px × 3px rotated 45° */}
        <rect
          x={cx - diamondHalf}
          y={cy - diamondHalf}
          width={diamondHalf * 2}
          height={diamondHalf * 2}
          fill={GOLD}
          transform={`rotate(45 ${cx} ${cy})`}
        />

        {/* "VERIFIED" label */}
        <text
          x={cx}
          y={labelY}
          textAnchor="middle"
          dominantBaseline="auto"
          fill={AMBER}
          fontSize={9}
          fontWeight={600}
          fontFamily="var(--font-geist-sans), system-ui, sans-serif"
          letterSpacing="0.12em"
        >
          VERIFIED
        </text>

        {/* Short proof hash below the label */}
        <text
          x={cx}
          y={hashY}
          textAnchor="middle"
          dominantBaseline="auto"
          fill="#9A8E78"
          fontSize={7}
          fontFamily="var(--font-jetbrains-mono), JetBrains Mono, monospace"
          letterSpacing="0.04em"
        >
          {shortHash}
        </text>
      </svg>

      {/* Per-length @keyframes for the draw-in animation.
          Each unique line length gets its own named keyframe so the
          `from` value is the exact pixel length of that segment.
          This avoids relying on CSS custom properties inside @keyframes,
          which have inconsistent browser support. */}
      {animate && (
        <style>
          {Array.from(
            new Set(lines.map((s) => s.length.toFixed(1)))
          )
            .map((lenStr) => {
              const lenKey = lenStr.replace(".", "_");
              return `@keyframes nj-draw-${lenKey} { from { stroke-dashoffset: ${lenStr}; } to { stroke-dashoffset: 0; } }`;
            })
            .join("\n")}
        </style>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Animated wrapper variant — triggers re-crystallisation on hash change
// ---------------------------------------------------------------------------

/**
 * AnimatedVerificationSeal
 *
 * Wraps VerificationSeal with a key-driven remount strategy so that every
 * proofHash change replays the crystallisation from scratch.
 */
export function AnimatedVerificationSeal(props: VerificationSealProps) {
  return <VerificationSeal key={props.proofHash} {...props} />;
}
