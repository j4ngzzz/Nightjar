"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** SVG viewport size — gauge is drawn inside a square viewBox. */
const SIZE = 160;
const CENTER = SIZE / 2;
const RADIUS = 64;
const STROKE_WIDTH = 10;

/**
 * The gauge sweeps 240° from 210° (7 o'clock) to 330° (clockwise, 5 o'clock).
 * SVG angles: 0° = 3 o'clock, increasing clockwise.
 *
 * 7 o'clock → 210° from 3 o'clock  →  SVG angle = 210°
 * 5 o'clock → 150° from 3 o'clock  →  SVG angle = 150° + 360° = 510° (going clockwise past 0)
 * Total sweep = 240°
 */
const START_ANGLE_DEG = 210;
const TOTAL_SWEEP_DEG = 240;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert degrees (SVG: 0° = right, CW positive) to (x, y) on the circle. */
function polarToCartesian(
  cx: number,
  cy: number,
  r: number,
  angleDeg: number,
): { x: number; y: number } {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return {
    x: cx + r * Math.cos(rad),
    y: cy + r * Math.sin(rad),
  };
}

/**
 * Build an SVG arc `d` attribute for an arc that starts at `startAngle` and
 * sweeps `sweepDeg` degrees clockwise.
 */
function arcPath(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  sweepDeg: number,
): string {
  const endAngle = startAngle + sweepDeg;
  const start = polarToCartesian(cx, cy, r, startAngle);
  const end = polarToCartesian(cx, cy, r, endAngle);
  const largeArc = sweepDeg > 180 ? 1 : 0;
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;
}

// ---------------------------------------------------------------------------
// Color logic
// ---------------------------------------------------------------------------

/** Return the amber-spectrum fill color for a given 0–100 score. */
function gaugeColor(score: number): string {
  if (score <= 40) return "#C84B2F";
  if (score <= 60) return "#A87020";
  if (score <= 80) return "#D4920A";
  if (score <= 95) return "#F5B93A";
  return "#FFD060";
}

/** Returns true when score qualifies for the peak glow. */
function hasPeakGlow(score: number): boolean {
  return score >= 96;
}

// ---------------------------------------------------------------------------
// Animation
// ---------------------------------------------------------------------------

/**
 * Custom spring-like easing that slightly overshoots then settles.
 * Implemented via requestAnimationFrame so we don't need a full motion dep
 * for this single SVG stroke-dashoffset animation.
 *
 * Easing: cubic-bezier(0.34, 1.56, 0.64, 1)
 * Approximated with a numeric integrator since CSS cubic-bezier can't drive
 * stroke-dashoffset directly in older Safari.
 */
function cubicBezier(
  t: number,
  p1x: number,
  p1y: number,
  p2x: number,
  p2y: number,
): number {
  // De Casteljau at t for cubic bezier with P0=(0,0) P1=(p1x,p1y) P2=(p2x,p2y) P3=(1,1)
  const cx = 3 * p1x;
  const bx = 3 * (p2x - p1x) - cx;
  const ax = 1 - cx - bx;
  const cy2 = 3 * p1y;
  const by = 3 * (p2y - p1y) - cy2;
  const ay = 1 - cy2 - by;

  // Solve for t given x using Newton-Raphson
  let tGuess = t;
  for (let i = 0; i < 8; i++) {
    const currentX =
      ((ax * tGuess + bx) * tGuess + cx) * tGuess - t;
    const derivX = (3 * ax * tGuess + 2 * bx) * tGuess + cx;
    if (Math.abs(derivX) < 1e-6) break;
    tGuess -= currentX / derivX;
  }

  return ((ay * tGuess + by) * tGuess + cy2) * tGuess;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export interface TrustGaugeProps {
  /** Score from 0–100. */
  score: number;
  /** Extra CSS class for the outer wrapper. */
  className?: string;
  /** Size in px (default 160). */
  size?: number;
}

/**
 * TrustGauge — circular SVG arc gauge with spring overshoot animation.
 *
 * Arc: 240° sweep (7 o'clock → 5 o'clock, speedometer style).
 * Animation: cubic-bezier(0.34, 1.56, 0.64, 1) over 1500 ms — slight
 * overshoot then settle (reaches ~target+3, settles at target).
 * Breathing idle: scale 1.0 → 1.02 → 1.0 every ~5s.
 */
export function TrustGauge({
  score,
  className,
  size = SIZE,
}: TrustGaugeProps) {
  // Clamp to [0, 100]
  const clampedScore = Math.min(100, Math.max(0, score));

  // Animated display score (drives the fill arc and the number).
  const [displayScore, setDisplayScore] = useState(0);

  // Whether the breathing idle animation is active.
  const [breathing, setBreathing] = useState(false);

  const animFrameRef = useRef<number | null>(null);
  const breathIntervalRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const breathTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Main sweep animation: 0 → clampedScore over 1500 ms with overshoot easing.
  useEffect(() => {
    const DURATION = 1500;
    let startTime: number | null = null;
    const fromScore = 0;
    const toScore = clampedScore;

    function frame(timestamp: number) {
      if (!startTime) startTime = timestamp;
      const elapsed = timestamp - startTime;
      const t = Math.min(elapsed / DURATION, 1);

      // cubic-bezier(0.34, 1.56, 0.64, 1) — slight overshoot
      const eased = cubicBezier(t, 0.34, 1.56, 0.64, 1);
      const current = fromScore + (toScore - fromScore) * eased;

      setDisplayScore(current);

      if (t < 1) {
        animFrameRef.current = requestAnimationFrame(frame);
      } else {
        setDisplayScore(toScore);
      }
    }

    animFrameRef.current = requestAnimationFrame(frame);

    return () => {
      if (animFrameRef.current !== null) {
        cancelAnimationFrame(animFrameRef.current);
      }
    };
  // Only re-animate when clampedScore changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clampedScore]);

  // Breathing idle: pulse every ~5 seconds after initial animation.
  useEffect(() => {
    function scheduleBreath() {
      // Fire every 5 seconds
      breathIntervalRef.current = setTimeout(() => {
        setBreathing(true);
        // Reset after 800ms
        breathTimeoutRef.current = setTimeout(() => {
          setBreathing(false);
          scheduleBreath();
        }, 800);
      }, 5000);
    }

    // Start the first breath cycle after the initial animation completes.
    const initialDelay = setTimeout(scheduleBreath, 1600);

    return () => {
      clearTimeout(initialDelay);
      if (breathIntervalRef.current) clearTimeout(breathIntervalRef.current);
      if (breathTimeoutRef.current) clearTimeout(breathTimeoutRef.current);
    };
  }, []);

  // ---------------------------------------------------------------------------
  // SVG geometry
  // ---------------------------------------------------------------------------
  const scale = size / SIZE;

  // Track: full 240° arc.
  const trackPath = arcPath(CENTER, CENTER, RADIUS, START_ANGLE_DEG, TOTAL_SWEEP_DEG);

  // Fill: arc proportional to displayScore.
  const fillSweep = (displayScore / 100) * TOTAL_SWEEP_DEG;
  const fillPath =
    fillSweep > 0.1
      ? arcPath(CENTER, CENTER, RADIUS, START_ANGLE_DEG, fillSweep)
      : null;

  const color = gaugeColor(displayScore);
  const glow = hasPeakGlow(displayScore);
  const roundedScore = Math.round(displayScore);

  // Breathing: scale the SVG wrapper
  const breathStyle: React.CSSProperties = {
    transition: "transform 400ms ease-in-out",
    transform: breathing ? "scale(1.02)" : "scale(1.0)",
  };

  return (
    <div
      className={cn("relative flex items-center justify-center", className)}
      style={{ width: size, height: size, ...breathStyle }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        fill="none"
        aria-label={`Trust score: ${roundedScore} out of 100`}
        role="img"
      >
        {/* Glow filter for 96–100 range */}
        {glow && (
          <defs>
            <filter id="gauge-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
        )}

        {/* Track arc — warm dark background */}
        <path
          d={trackPath}
          stroke="#2A2315"
          strokeWidth={STROKE_WIDTH}
          strokeLinecap="round"
          fill="none"
        />

        {/* Fill arc — amber spectrum, animated */}
        {fillPath && (
          <path
            d={fillPath}
            stroke={color}
            strokeWidth={STROKE_WIDTH}
            strokeLinecap="round"
            fill="none"
            filter={glow ? "url(#gauge-glow)" : undefined}
          />
        )}

        {/* Score number — centered */}
        <text
          x={CENTER}
          y={CENTER + 2}
          textAnchor="middle"
          dominantBaseline="middle"
          fill={color}
          fontSize={Math.round(48 * scale)}
          fontWeight={600}
          fontFamily="var(--font-geist-sans), system-ui, sans-serif"
          style={{ fontVariantNumeric: "tabular-nums" }}
        >
          {roundedScore}
        </text>
      </svg>
    </div>
  );
}
