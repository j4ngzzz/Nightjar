"use client";

/**
 * Nightjar Verification Canvas — BadgeGrid
 *
 * Grid of AchievementBadge components.
 * - Locked badges at 40% opacity (handled inside AchievementBadge via unlocked prop)
 * - Recently unlocked badge gets crystallization animation on mount
 * - Handles 0 badges gracefully (empty state)
 *
 * Color rules: NO GREEN, NO PURPLE — amber palette only.
 */

import { memo } from "react";
import { motion } from "motion/react";

import {
  AchievementBadge,
  type BadgeType,
  BADGE_META,
} from "./AchievementBadge";
import {
  crystallizeVariants,
  staggerDelay,
} from "@/components/canvas/crystallization";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface BadgeEntry {
  type: BadgeType;
  unlocked: boolean;
  /**
   * If true, the badge was just unlocked in this session —
   * triggers crystallization animation on mount.
   */
  recentlyUnlocked?: boolean;
}

export interface BadgeGridProps {
  badges?: BadgeEntry[];
  /** Badge size in px (default 56) */
  badgeSize?: number;
  /** Show label under each badge (default true) */
  showLabels?: boolean;
  className?: string;
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        padding: "32px 16px",
        color: "#4A3D20",
        fontFamily: "var(--font-geist-sans, sans-serif)",
        fontSize: 13,
        textAlign: "center",
      }}
    >
      {/* Dim hexagon outline as placeholder */}
      <svg width={40} height={40} viewBox="0 0 40 40">
        <path
          d={hexPathLocal(20, 20, 14)}
          fill="none"
          stroke="#2A2315"
          strokeWidth={1.5}
        />
      </svg>
      <span style={{ color: "#3A2E10" }}>No achievements yet</span>
    </div>
  );
}

/** Hexagon path helper (local copy to avoid circular import concerns) */
function hexPathLocal(cx: number, cy: number, r: number): string {
  const pts = Array.from({ length: 6 }, (_, i) => {
    const angle = (Math.PI / 3) * i - Math.PI / 6;
    return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
  });
  return `M ${pts.join(" L ")} Z`;
}

// ---------------------------------------------------------------------------
// BadgeGrid
// ---------------------------------------------------------------------------

/**
 * Build the default full badge list (all 15 types) from BADGE_META.
 * Used when no `badges` prop is supplied.
 */
function buildDefaultBadges(): BadgeEntry[] {
  return (Object.keys(BADGE_META) as BadgeType[]).map((type) => ({
    type,
    unlocked: false,
    recentlyUnlocked: false,
  }));
}

function BadgeGridInner({
  badges,
  badgeSize = 56,
  showLabels = true,
  className,
}: BadgeGridProps) {
  const entries = badges ?? buildDefaultBadges();

  if (entries.length === 0) {
    return <EmptyState />;
  }

  // Sort: recently unlocked first, then other unlocked, then locked
  const sorted = [...entries].sort((a, b) => {
    if (a.recentlyUnlocked && !b.recentlyUnlocked) return -1;
    if (!a.recentlyUnlocked && b.recentlyUnlocked) return 1;
    if (a.unlocked && !b.unlocked) return -1;
    if (!a.unlocked && b.unlocked) return 1;
    return 0;
  });

  return (
    <div
      className={className}
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(auto-fill, minmax(${badgeSize + 32}px, 1fr))`,
        gap: "16px 12px",
        padding: "12px 0",
      }}
      role="list"
      aria-label="Achievement badges"
    >
      {sorted.map((entry, index) => {
        const isRecentlyUnlocked = Boolean(entry.recentlyUnlocked);

        // Coerce: recentlyUnlocked implies unlocked — prevents "NEW" pill on locked badge
        const effectivelyUnlocked = isRecentlyUnlocked ? true : entry.unlocked;

        return (
          <div
            key={entry.type}
            role="listitem"
            style={{ display: "flex", justifyContent: "center" }}
          >
            {isRecentlyUnlocked ? (
              /* Crystallization animation on mount for recently unlocked */
              <motion.div
                variants={crystallizeVariants}
                initial="hidden"
                animate="visible"
                transition={{ delay: staggerDelay(index % 6) }}
                style={{
                  display: "inline-flex",
                  flexDirection: "column",
                  alignItems: "center",
                  position: "relative",
                }}
              >
                <AchievementBadge
                  type={entry.type}
                  unlocked={effectivelyUnlocked}
                  size={badgeSize}
                  showLabel={showLabels}
                />
                {/* "NEW" indicator for recently unlocked */}
                <span
                  style={{
                    position: "absolute",
                    top: -6,
                    right: -6,
                    background: "#D4920A",
                    color: "#0D0B09",
                    fontSize: 8,
                    fontWeight: 700,
                    fontFamily: "var(--font-geist-sans, sans-serif)",
                    padding: "1px 4px",
                    borderRadius: 4,
                    letterSpacing: "0.05em",
                    lineHeight: 1.4,
                    pointerEvents: "none",
                  }}
                >
                  NEW
                </span>
              </motion.div>
            ) : (
              <AchievementBadge
                type={entry.type}
                unlocked={entry.unlocked}
                size={badgeSize}
                showLabel={showLabels}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export const BadgeGrid = memo(BadgeGridInner);
BadgeGrid.displayName = "BadgeGrid";
