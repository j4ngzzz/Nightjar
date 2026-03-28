"use client";

/**
 * Nightjar Verification Canvas — StreakIndicator
 *
 * "N consecutive commits, all proven correct"
 *
 * - Flame icon in amber when streak > 0
 * - Count in Geist Sans 600, #F5B93A
 * - Streak > 30: animated ember glow on the flame
 *
 * Color rules: NO GREEN, NO PURPLE — amber palette only.
 */

import { memo } from "react";
import { motion } from "motion/react";

// ---------------------------------------------------------------------------
// Color constants
// ---------------------------------------------------------------------------

const GOLD = "#F5B93A";
const AMBER = "#D4920A";
const PEAK = "#FFD060";
const LOCKED_TEXT = "#3A2E10";
const TEXT_SECONDARY = "#8B8579";
const BG_RAISED = "#141109";
const BORDER_INACTIVE = "#2A2315";

// ---------------------------------------------------------------------------
// Flame SVG
// ---------------------------------------------------------------------------

interface FlameSvgProps {
  size: number;
  /** Whether to apply ember animation (streak > 30) */
  ember: boolean;
}

function FlameSvg({ size, ember }: FlameSvgProps) {
  const cx = size / 2;
  const cy = size / 2 + size * 0.06;
  const s = size / 24; // scale factor

  // Outer flame shape
  const outerFlame = `
    M ${cx},${cy + 9 * s}
    C ${cx - 8 * s},${cy + 4 * s}
      ${cx - 11 * s},${cy - 3 * s}
      ${cx - 5 * s},${cy - 10 * s}
    C ${cx - 2 * s},${cy - 4 * s}
      ${cx - 1 * s},${cy - 1 * s}
      ${cx},${cy - 13 * s}
    C ${cx + 1 * s},${cy - 1 * s}
      ${cx + 2 * s},${cy - 4 * s}
      ${cx + 5 * s},${cy - 10 * s}
    C ${cx + 11 * s},${cy - 3 * s}
      ${cx + 8 * s},${cy + 4 * s}
      ${cx},${cy + 9 * s}
    Z
  `;

  // Inner core flame (brighter center)
  const innerFlame = `
    M ${cx},${cy + 4 * s}
    C ${cx - 3 * s},${cy + 1 * s}
      ${cx - 4 * s},${cy - 3 * s}
      ${cx - 1 * s},${cy - 7 * s}
    C ${cx},${cy - 2 * s}
      ${cx + 1 * s},${cy - 7 * s}
      ${cx + 1 * s},${cy - 7 * s}
    C ${cx + 4 * s},${cy - 3 * s}
      ${cx + 3 * s},${cy + 1 * s}
      ${cx},${cy + 4 * s}
    Z
  `;

  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      aria-hidden
    >
      {ember ? (
        <>
          {/* Ember particles above the flame */}
          {[
            { dx: -5 * s, startY: cy - 14 * s },
            { dx: 3 * s, startY: cy - 16 * s },
            { dx: -1 * s, startY: cy - 18 * s },
          ].map(({ dx, startY }, i) => (
            <motion.circle
              key={i}
              cx={cx + dx}
              cy={startY}
              r={s * 0.9}
              fill={PEAK}
              initial={{ opacity: 0, y: 0 }}
              animate={{
                opacity: [0, 0.9, 0],
                y: [0, -8 * s, -16 * s],
              }}
              transition={{
                duration: 1.4,
                repeat: Infinity,
                delay: i * 0.45,
                ease: "easeOut",
              }}
            />
          ))}
        </>
      ) : null}

      {/* Outer flame */}
      <path
        d={outerFlame}
        fill={AMBER}
        fillOpacity={0.85}
      />

      {/* Inner flame */}
      <path
        d={innerFlame}
        fill={GOLD}
        fillOpacity={0.9}
      />

      {/* Peak highlight dot */}
      <circle
        cx={cx}
        cy={cy - 4 * s}
        r={s * 1.2}
        fill={PEAK}
        fillOpacity={0.7}
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Ember glow animation on the flame container (streak > 30)
// ---------------------------------------------------------------------------

const emberGlowVariants = {
  idle: {
    filter: `drop-shadow(0 0 3px ${AMBER}66)`,
  },
  glow: {
    filter: [
      `drop-shadow(0 0 3px ${AMBER}66)`,
      `drop-shadow(0 0 10px ${GOLD}bb)`,
      `drop-shadow(0 0 18px ${PEAK}99)`,
      `drop-shadow(0 0 10px ${GOLD}bb)`,
      `drop-shadow(0 0 3px ${AMBER}66)`,
    ],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: "easeInOut" as const,
    },
  },
};

// ---------------------------------------------------------------------------
// StreakIndicator
// ---------------------------------------------------------------------------

export interface StreakIndicatorProps {
  /** Number of consecutive proven commits */
  streak: number;
  /** Optional: override label (default "consecutive proven commits") */
  label?: string;
  /** Icon size in px (default 28) */
  iconSize?: number;
  className?: string;
}

function StreakIndicatorInner({
  streak,
  label = "consecutive proven commits",
  iconSize = 28,
  className,
}: StreakIndicatorProps) {
  const hasStreak = streak > 0;
  const isHot = streak > 30;

  const countColor = hasStreak ? GOLD : LOCKED_TEXT;
  const labelColor = hasStreak ? TEXT_SECONDARY : LOCKED_TEXT;

  return (
    <div
      className={className}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        padding: "6px 12px",
        background: BG_RAISED,
        border: `1px solid ${hasStreak ? "#3A2E10" : BORDER_INACTIVE}`,
        borderRadius: 8,
        userSelect: "none",
      }}
      role="status"
      aria-label={`Streak: ${streak} ${label}`}
    >
      {/* Flame icon */}
      {hasStreak ? (
        isHot ? (
          <motion.div
            variants={emberGlowVariants}
            initial="idle"
            animate="glow"
            style={{ lineHeight: 0, flexShrink: 0 }}
          >
            <FlameSvg size={iconSize} ember={true} />
          </motion.div>
        ) : (
          <div style={{ lineHeight: 0, flexShrink: 0 }}>
            <FlameSvg size={iconSize} ember={false} />
          </div>
        )
      ) : (
        /* Dim outline flame for zero streak */
        <svg
          width={iconSize}
          height={iconSize}
          viewBox={`0 0 ${iconSize} ${iconSize}`}
          aria-hidden
          style={{ flexShrink: 0 }}
        >
          <path
            d={dimFlamePath(iconSize)}
            fill="none"
            stroke={BORDER_INACTIVE}
            strokeWidth={1.2}
          />
        </svg>
      )}

      {/* Count + label */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 1,
          lineHeight: 1,
        }}
      >
        <span
          style={{
            fontFamily: "var(--font-geist-sans, sans-serif)",
            fontSize: 20,
            fontWeight: 600,
            color: countColor,
            lineHeight: 1,
            tabularNums: "tabular-nums",
            fontVariantNumeric: "tabular-nums",
          } as React.CSSProperties}
        >
          {streak}
        </span>
        <span
          style={{
            fontFamily: "var(--font-geist-sans, sans-serif)",
            fontSize: 11,
            fontWeight: 400,
            color: labelColor,
            lineHeight: 1.2,
            whiteSpace: "nowrap",
          }}
        >
          {label}
        </span>
      </div>
    </div>
  );
}

/** Simple dim outline flame for zero/inactive state */
function dimFlamePath(size: number): string {
  const cx = size / 2;
  const cy = size / 2 + size * 0.06;
  const s = size / 24;
  return `
    M ${cx},${cy + 9 * s}
    C ${cx - 8 * s},${cy + 4 * s}
      ${cx - 11 * s},${cy - 3 * s}
      ${cx - 5 * s},${cy - 10 * s}
    C ${cx - 2 * s},${cy - 4 * s}
      ${cx - 1 * s},${cy - 1 * s}
      ${cx},${cy - 13 * s}
    C ${cx + 1 * s},${cy - 1 * s}
      ${cx + 2 * s},${cy - 4 * s}
      ${cx + 5 * s},${cy - 10 * s}
    C ${cx + 11 * s},${cy - 3 * s}
      ${cx + 8 * s},${cy + 4 * s}
      ${cx},${cy + 9 * s}
    Z
  `;
}

export const StreakIndicator = memo(StreakIndicatorInner);
StreakIndicator.displayName = "StreakIndicator";
