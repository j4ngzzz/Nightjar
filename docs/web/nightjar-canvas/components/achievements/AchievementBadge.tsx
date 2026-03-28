"use client";

/**
 * Nightjar Verification Canvas — AchievementBadge
 *
 * Generative SVG geometric badge per achievement type.
 * Circuit-board-inspired hexagonal design.
 *
 * Locked state:  #2A2315 fill, dim outline, 40% opacity (applied by parent)
 * Unlocked state: amber fill, label below
 *
 * Color rules: NO GREEN, NO PURPLE — amber palette only.
 */

import { memo } from "react";
import { motion } from "motion/react";

// ---------------------------------------------------------------------------
// Badge type definitions
// ---------------------------------------------------------------------------

export type BadgeType =
  | "first_proof"
  | "perfect_pipeline"
  | "the_mathematician"
  | "bug_hunter"
  | "speed_demon"
  | "streak_master"
  | "deep_dive"
  | "night_owl"
  | "iron_spec"
  | "polyglot"
  | "no_regressions"
  | "100_verifications"
  | "formal_purist"
  | "invariant_miner"
  | "cegis_champion";

export interface BadgeMeta {
  label: string;
  description: string;
}

export const BADGE_META: Record<BadgeType, BadgeMeta> = {
  first_proof: {
    label: "First Proof",
    description: "Ran your first formal verification",
  },
  perfect_pipeline: {
    label: "Perfect Pipeline",
    description: "All 6 stages passed in a single run",
  },
  the_mathematician: {
    label: "The Mathematician",
    description: "Achieved Trust Score 100",
  },
  bug_hunter: {
    label: "Bug Hunter",
    description: "Caught 10+ violations before ship",
  },
  speed_demon: {
    label: "Speed Demon",
    description: "Full pipeline under 5 seconds",
  },
  streak_master: {
    label: "Streak Master",
    description: "30 consecutive proven commits",
  },
  deep_dive: {
    label: "Deep Dive",
    description: "Explored 5+ spec files in one session",
  },
  night_owl: {
    label: "Night Owl",
    description: "Verified after midnight, 3 times",
  },
  iron_spec: {
    label: "Iron Spec",
    description: "Spec survived 100 PBT runs unchanged",
  },
  polyglot: {
    label: "Polyglot",
    description: "Verified Python, Go, and TypeScript",
  },
  no_regressions: {
    label: "No Regressions",
    description: "Zero regressions across 50 builds",
  },
  "100_verifications": {
    label: "Centurion",
    description: "Ran 100 verification cycles",
  },
  formal_purist: {
    label: "Formal Purist",
    description: "Used only Stage 4 (Dafny) for 10 proofs",
  },
  invariant_miner: {
    label: "Invariant Miner",
    description: "Immune system mined 20+ invariants",
  },
  cegis_champion: {
    label: "CEGIS Champion",
    description: "Retry loop auto-repaired 5 failing specs",
  },
};

// ---------------------------------------------------------------------------
// Amber palette constants
// ---------------------------------------------------------------------------

const LOCKED_FILL = "#2A2315";
const LOCKED_STROKE = "#3A2E10";
const LOCKED_TEXT = "#4A3D20";

const AMBER = "#D4920A";
const GOLD = "#F5B93A";
const PEAK = "#FFD060";
const AMBER_DIM = "#A87020";
const TEXT_PRIMARY = "#F0EBE3";
const TEXT_SECONDARY = "#8B8579";

// ---------------------------------------------------------------------------
// SVG geometry helpers
// ---------------------------------------------------------------------------

/** Generate a regular hexagon path centered at (cx, cy) with radius r */
function hexPath(cx: number, cy: number, r: number): string {
  const pts = Array.from({ length: 6 }, (_, i) => {
    const angle = (Math.PI / 3) * i - Math.PI / 6;
    return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
  });
  return `M ${pts.join(" L ")} Z`;
}

/** Small circuit-trace line from (x1,y1) to (x2,y2) with an elbow */
function tracePath(
  x1: number,
  y1: number,
  x2: number,
  y2: number
): string {
  const mx = (x1 + x2) / 2;
  return `M ${x1},${y1} L ${mx},${y1} L ${mx},${y2} L ${x2},${y2}`;
}

// ---------------------------------------------------------------------------
// Per-badge SVG renderers
// ---------------------------------------------------------------------------

interface SvgProps {
  unlocked: boolean;
  size: number;
}

// 1. First Proof — single hexagon + Dafny λ symbol
function FirstProofSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.32;
  const stroke = unlocked ? AMBER : LOCKED_STROKE;
  const fill = unlocked ? `${AMBER}22` : LOCKED_FILL;
  const iconColor = unlocked ? GOLD : LOCKED_TEXT;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <path d={hexPath(cx, cy, r)} fill={fill} stroke={stroke} strokeWidth={1.5} />
      {/* λ symbol */}
      <text
        x={cx}
        y={cy + 6}
        textAnchor="middle"
        fontSize={size * 0.28}
        fill={iconColor}
        fontFamily="serif"
        fontStyle="italic"
        fontWeight="600"
      >
        λ
      </text>
    </svg>
  );
}

// 2. Perfect Pipeline — six connected hexagons in ring
function PerfectPipelineSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const orbitR = size * 0.28;
  const hexR = size * 0.13;
  const stroke = unlocked ? AMBER : LOCKED_STROKE;
  const fill = unlocked ? `${AMBER}22` : LOCKED_FILL;
  const centerFill = unlocked ? `${GOLD}33` : LOCKED_FILL;
  const centerStroke = unlocked ? GOLD : LOCKED_STROKE;
  const lineColor = unlocked ? `${AMBER_DIM}88` : `${LOCKED_STROKE}44`;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Center hex */}
      <path d={hexPath(cx, cy, hexR)} fill={centerFill} stroke={centerStroke} strokeWidth={1} />
      {/* Six orbit hexagons */}
      {Array.from({ length: 6 }, (_, i) => {
        const angle = (Math.PI / 3) * i - Math.PI / 6;
        const hx = cx + orbitR * Math.cos(angle);
        const hy = cy + orbitR * Math.sin(angle);
        return (
          <g key={i}>
            <line
              x1={cx}
              y1={cy}
              x2={hx}
              y2={hy}
              stroke={lineColor}
              strokeWidth={1}
            />
            <path d={hexPath(hx, hy, hexR)} fill={fill} stroke={stroke} strokeWidth={1} />
          </g>
        );
      })}
    </svg>
  );
}

// 3. The Mathematician — golden sigma, pulsing glow (unlocked only)
function TheMathematicianSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.36;
  const stroke = unlocked ? PEAK : LOCKED_STROKE;
  const fill = unlocked ? `${PEAK}18` : LOCKED_FILL;
  const sigmaColor = unlocked ? PEAK : LOCKED_TEXT;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {/* Outer decorative circle */}
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill={fill}
        stroke={stroke}
        strokeWidth={1.5}
        strokeDasharray="4 2"
      />
      {/* Inner solid hex */}
      <path
        d={hexPath(cx, cy, r * 0.7)}
        fill={unlocked ? `${PEAK}22` : LOCKED_FILL}
        stroke={stroke}
        strokeWidth={1}
      />
      {/* Σ symbol */}
      <text
        x={cx}
        y={cy + 7}
        textAnchor="middle"
        fontSize={size * 0.32}
        fill={sigmaColor}
        fontFamily="serif"
        fontWeight="700"
      >
        Σ
      </text>
    </svg>
  );
}

// 4. Bug Hunter — crosshair with circuit traces
function BugHunterSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.3;
  const stroke = unlocked ? AMBER : LOCKED_STROKE;
  const fill = unlocked ? `${AMBER}15` : LOCKED_FILL;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r} fill={fill} stroke={stroke} strokeWidth={1.5} />
      <line x1={cx} y1={cy - r - 4} x2={cx} y2={cy - r + 8} stroke={stroke} strokeWidth={1.5} />
      <line x1={cx} y1={cy + r - 8} x2={cx} y2={cy + r + 4} stroke={stroke} strokeWidth={1.5} />
      <line x1={cx - r - 4} y1={cy} x2={cx - r + 8} y2={cy} stroke={stroke} strokeWidth={1.5} />
      <line x1={cx + r - 8} y1={cy} x2={cx + r + 4} y2={cy} stroke={stroke} strokeWidth={1.5} />
      <circle cx={cx} cy={cy} r={3} fill={unlocked ? GOLD : LOCKED_STROKE} />
      {/* Traces */}
      <path d={tracePath(cx + r + 4, cy, cx + r + 10, cy - 8)} stroke={unlocked ? `${AMBER_DIM}88` : `${LOCKED_STROKE}44`} strokeWidth={1} fill="none" />
    </svg>
  );
}

// 5. Speed Demon — lightning bolt in hexagon
function SpeedDemonSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.33;
  const stroke = unlocked ? AMBER : LOCKED_STROKE;
  const fill = unlocked ? `${AMBER}18` : LOCKED_FILL;
  const boltColor = unlocked ? GOLD : LOCKED_TEXT;

  // Lightning bolt path
  const bx = cx;
  const by = cy;
  const bolt = `M ${bx + 4},${by - 12} L ${bx - 3},${by - 1} L ${bx + 2},${by - 1} L ${bx - 4},${by + 12} L ${bx + 3},${by + 1} L ${bx - 2},${by + 1} Z`;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <path d={hexPath(cx, cy, r)} fill={fill} stroke={stroke} strokeWidth={1.5} />
      <path d={bolt} fill={boltColor} />
    </svg>
  );
}

// 6. Streak Master — flame shape
function StreakMasterSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2 + 4;
  const stroke = unlocked ? GOLD : LOCKED_STROKE;
  const flameFill = unlocked ? `${GOLD}33` : LOCKED_FILL;
  const innerFill = unlocked ? `${AMBER}55` : LOCKED_FILL;

  // Outer flame
  const ox = cx, oy = cy;
  const outerFlame = `M ${ox},${oy + 16} C ${ox - 14},${oy + 8} ${ox - 18},${oy - 4} ${ox - 8},${oy - 14} C ${ox - 4},${oy - 6} ${ox - 2},${oy - 2} ${ox},${oy - 20} C ${ox + 2},${oy - 2} ${ox + 4},${oy - 6} ${ox + 8},${oy - 14} C ${ox + 18},${oy - 4} ${ox + 14},${oy + 8} ${ox},${oy + 16} Z`;
  // Inner flame
  const innerFlame = `M ${ox},${oy + 8} C ${ox - 6},${oy + 2} ${ox - 8},${oy - 4} ${ox - 2},${oy - 10} C ${ox},${oy - 4} ${ox + 2},${oy - 10} ${ox + 2},${oy - 10} C ${ox + 8},${oy - 4} ${ox + 6},${oy + 2} ${ox},${oy + 8} Z`;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <path d={outerFlame} fill={flameFill} stroke={stroke} strokeWidth={1.5} />
      <path d={innerFlame} fill={innerFill} stroke={unlocked ? AMBER : LOCKED_STROKE} strokeWidth={1} />
    </svg>
  );
}

// 7. Deep Dive — layered hexagons (depth)
function DeepDiveSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const stroke = unlocked ? AMBER : LOCKED_STROKE;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {[0.36, 0.26, 0.16].map((scale, i) => (
        <path
          key={i}
          d={hexPath(cx, cy, size * scale)}
          fill={unlocked ? `rgba(212,146,10,${0.07 + i * 0.08})` : LOCKED_FILL}
          stroke={unlocked ? (i === 2 ? GOLD : stroke) : LOCKED_STROKE}
          strokeWidth={i === 2 ? 1.5 : 1}
        />
      ))}
      <circle cx={cx} cy={cy} r={3} fill={unlocked ? GOLD : LOCKED_STROKE} />
    </svg>
  );
}

// 8. Night Owl — moon + circuit dot grid
function NightOwlSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const stroke = unlocked ? AMBER : LOCKED_STROKE;
  const fill = unlocked ? `${AMBER}18` : LOCKED_FILL;
  const moonColor = unlocked ? GOLD : LOCKED_TEXT;

  // Crescent: large circle minus offset circle (via clip-path trick with two arcs)
  const moonPath = `
    M ${cx - 8},${cy - 12}
    A 14,14 0 1,1 ${cx - 8},${cy + 12}
    A 10,10 0 1,0 ${cx - 8},${cy - 12}
    Z
  `;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <path d={hexPath(cx, cy, size * 0.33)} fill={fill} stroke={stroke} strokeWidth={1.5} />
      <path d={moonPath} fill={moonColor} />
      {/* Stars */}
      {[[cx + 8, cy - 10], [cx + 12, cy], [cx + 6, cy + 10]].map(([sx, sy], i) => (
        <circle key={i} cx={sx} cy={sy} r={1.5} fill={unlocked ? GOLD : LOCKED_STROKE} />
      ))}
    </svg>
  );
}

// 9. Iron Spec — shield with spec lines
function IronSpecSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const stroke = unlocked ? AMBER : LOCKED_STROKE;
  const fill = unlocked ? `${AMBER}18` : LOCKED_FILL;
  const lineColor = unlocked ? `${AMBER_DIM}99` : `${LOCKED_STROKE}55`;

  // Shield path
  const sh = size * 0.36;
  const sw = size * 0.28;
  const shieldPath = `M ${cx},${cy - sh} L ${cx + sw},${cy - sh * 0.5} L ${cx + sw},${cy + sh * 0.1} Q ${cx + sw * 0.5},${cy + sh} ${cx},${cy + sh} Q ${cx - sw * 0.5},${cy + sh} ${cx - sw},${cy + sh * 0.1} L ${cx - sw},${cy - sh * 0.5} Z`;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <path d={shieldPath} fill={fill} stroke={stroke} strokeWidth={1.5} />
      {/* Spec lines */}
      {[cy - 6, cy, cy + 6].map((ly, i) => (
        <line
          key={i}
          x1={cx - 10}
          y1={ly}
          x2={cx + 10}
          y2={ly}
          stroke={lineColor}
          strokeWidth={1}
        />
      ))}
    </svg>
  );
}

// 10. Polyglot — three interlocking circles (Venn)
function PolyglotSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.18;
  const off = size * 0.12;
  const positions = [
    [cx, cy - off],
    [cx - off * 0.87, cy + off * 0.5],
    [cx + off * 0.87, cy + off * 0.5],
  ];
  const stroke = unlocked ? AMBER : LOCKED_STROKE;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      {positions.map(([px, py], i) => (
        <circle
          key={i}
          cx={px}
          cy={py}
          r={r}
          fill={unlocked ? `rgba(212,146,10,${0.1 + i * 0.04})` : "none"}
          stroke={stroke}
          strokeWidth={1.5}
        />
      ))}
      {/* Center dot */}
      <circle cx={cx} cy={cy + off * 0.1} r={2.5} fill={unlocked ? GOLD : LOCKED_STROKE} />
    </svg>
  );
}

// 11. No Regressions — upward arrow in hexagon
function NoRegressionsSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.33;
  const stroke = unlocked ? AMBER : LOCKED_STROKE;
  const fill = unlocked ? `${AMBER}18` : LOCKED_FILL;
  const arrowColor = unlocked ? GOLD : LOCKED_TEXT;

  const arrowPath = `M ${cx},${cy - 12} L ${cx + 8},${cy - 2} L ${cx + 3},${cy - 2} L ${cx + 3},${cy + 12} L ${cx - 3},${cy + 12} L ${cx - 3},${cy - 2} L ${cx - 8},${cy - 2} Z`;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <path d={hexPath(cx, cy, r)} fill={fill} stroke={stroke} strokeWidth={1.5} />
      <path d={arrowPath} fill={arrowColor} />
    </svg>
  );
}

// 12. Centurion (100 verifications) — Roman numeral C in circuit frame
function CenturionSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.33;
  const stroke = unlocked ? AMBER : LOCKED_STROKE;
  const fill = unlocked ? `${AMBER}18` : LOCKED_FILL;
  const textColor = unlocked ? GOLD : LOCKED_TEXT;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={cx} cy={cy} r={r} fill={fill} stroke={stroke} strokeWidth={1.5} />
      {/* Tick marks at cardinal points */}
      {[0, 90, 180, 270].map((deg) => {
        const rad = (deg * Math.PI) / 180;
        return (
          <line
            key={deg}
            x1={cx + (r - 4) * Math.cos(rad)}
            y1={cy + (r - 4) * Math.sin(rad)}
            x2={cx + (r + 4) * Math.cos(rad)}
            y2={cy + (r + 4) * Math.sin(rad)}
            stroke={stroke}
            strokeWidth={1.5}
          />
        );
      })}
      <text
        x={cx}
        y={cy + 7}
        textAnchor="middle"
        fontSize={size * 0.26}
        fill={textColor}
        fontFamily="serif"
        fontWeight="700"
      >
        C
      </text>
    </svg>
  );
}

// 13. Formal Purist — Dafny λ inside double hexagon
function FormalPuristSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const stroke = unlocked ? AMBER : LOCKED_STROKE;
  const outerFill = unlocked ? `${AMBER}10` : LOCKED_FILL;
  const innerFill = unlocked ? `${AMBER}22` : LOCKED_FILL;
  const textColor = unlocked ? PEAK : LOCKED_TEXT;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <path d={hexPath(cx, cy, size * 0.38)} fill={outerFill} stroke={stroke} strokeWidth={1} />
      <path d={hexPath(cx, cy, size * 0.26)} fill={innerFill} stroke={unlocked ? GOLD : LOCKED_STROKE} strokeWidth={1.5} />
      <text
        x={cx}
        y={cy + 6}
        textAnchor="middle"
        fontSize={size * 0.24}
        fill={textColor}
        fontFamily="serif"
        fontStyle="italic"
        fontWeight="700"
      >
        λ
      </text>
    </svg>
  );
}

// 14. Invariant Miner — pick-axe + circuit traces
function InvariantMinerSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const stroke = unlocked ? AMBER : LOCKED_STROKE;
  const fill = unlocked ? `${AMBER}18` : LOCKED_FILL;
  const toolColor = unlocked ? GOLD : LOCKED_TEXT;

  // Simplified pickaxe via two rectangles rotated
  const pickPath = `
    M ${cx - 14},${cy + 10}
    L ${cx + 14},${cy - 10}
    L ${cx + 16},${cy - 7}
    L ${cx + 2},${cy + 3}
    L ${cx + 8},${cy + 14}
    L ${cx + 4},${cy + 16}
    L ${cx - 2},${cy + 6}
    L ${cx - 12},${cy + 14}
    L ${cx - 16},${cy + 8}
    Z
  `;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <path d={hexPath(cx, cy, size * 0.33)} fill={fill} stroke={stroke} strokeWidth={1.5} />
      <path d={pickPath} fill={toolColor} />
    </svg>
  );
}

// 15. CEGIS Champion — recursive arrow (counterexample loop)
function CegisChampionSvg({ unlocked, size }: SvgProps) {
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.28;
  const stroke = unlocked ? GOLD : LOCKED_STROKE;
  const fill = unlocked ? `${GOLD}15` : LOCKED_FILL;

  // Circular arrow path (arc + arrowhead)
  const startAngle = -Math.PI * 0.3;
  const endAngle = Math.PI * 1.6;
  const sx = cx + r * Math.cos(startAngle);
  const sy = cy + r * Math.sin(startAngle);
  const ex = cx + r * Math.cos(endAngle);
  const ey = cy + r * Math.sin(endAngle);

  const arcPath = `M ${sx},${sy} A ${r},${r} 0 1,1 ${ex},${ey}`;

  // Arrowhead tip
  const tipAngle = endAngle + 0.2;
  const arrowHead = `M ${ex},${ey} L ${ex + 7 * Math.cos(tipAngle - 0.4)},${ey + 7 * Math.sin(tipAngle - 0.4)} L ${ex + 7 * Math.cos(tipAngle + 0.4)},${ey + 7 * Math.sin(tipAngle + 0.4)} Z`;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <path d={hexPath(cx, cy, size * 0.38)} fill={fill} stroke={unlocked ? AMBER : LOCKED_STROKE} strokeWidth={1} />
      <path d={arcPath} fill="none" stroke={stroke} strokeWidth={2} />
      <path d={arrowHead} fill={stroke} />
      <circle cx={cx} cy={cy} r={3} fill={unlocked ? GOLD : LOCKED_STROKE} />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// SVG renderer map
// ---------------------------------------------------------------------------

const SVG_RENDERERS: Record<BadgeType, React.ComponentType<SvgProps>> = {
  first_proof: FirstProofSvg,
  perfect_pipeline: PerfectPipelineSvg,
  the_mathematician: TheMathematicianSvg,
  bug_hunter: BugHunterSvg,
  speed_demon: SpeedDemonSvg,
  streak_master: StreakMasterSvg,
  deep_dive: DeepDiveSvg,
  night_owl: NightOwlSvg,
  iron_spec: IronSpecSvg,
  polyglot: PolyglotSvg,
  no_regressions: NoRegressionsSvg,
  "100_verifications": CenturionSvg,
  formal_purist: FormalPuristSvg,
  invariant_miner: InvariantMinerSvg,
  cegis_champion: CegisChampionSvg,
};

// ---------------------------------------------------------------------------
// Glow animation for "The Mathematician"
// ---------------------------------------------------------------------------

const mathematicianGlowVariants = {
  idle: {
    filter: `drop-shadow(0 0 4px ${PEAK}88)`,
    opacity: 1,
  },
  glow: {
    filter: [
      `drop-shadow(0 0 4px ${PEAK}88)`,
      `drop-shadow(0 0 16px ${PEAK}cc)`,
      `drop-shadow(0 0 28px ${PEAK}ff)`,
      `drop-shadow(0 0 16px ${PEAK}cc)`,
      `drop-shadow(0 0 4px ${PEAK}88)`,
    ],
    opacity: [1, 1, 1, 1, 1],
    transition: {
      duration: 3,
      repeat: Infinity,
      ease: "easeInOut" as const,
    },
  },
};

// ---------------------------------------------------------------------------
// AchievementBadge component
// ---------------------------------------------------------------------------

export interface AchievementBadgeProps {
  type: BadgeType;
  unlocked: boolean;
  /** Size in px (default 64) */
  size?: number;
  /** Show the label below the badge */
  showLabel?: boolean;
  className?: string;
}

function AchievementBadgeInner({
  type,
  unlocked,
  size = 64,
  showLabel = true,
  className,
}: AchievementBadgeProps) {
  const meta = BADGE_META[type];
  const SvgRenderer = SVG_RENDERERS[type];
  const isMathematician = type === "the_mathematician" && unlocked;

  const containerStyle: React.CSSProperties = {
    display: "inline-flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 6,
    opacity: unlocked ? 1 : 0.4,
    cursor: "default",
    userSelect: "none",
  };

  const tooltipTitle = `${meta.label}: ${meta.description}`;

  return (
    <div style={containerStyle} className={className} title={tooltipTitle}>
      {isMathematician ? (
        <motion.div
          variants={mathematicianGlowVariants}
          initial="idle"
          animate="glow"
          style={{ lineHeight: 0 }}
        >
          <SvgRenderer unlocked={unlocked} size={size} />
        </motion.div>
      ) : (
        <div style={{ lineHeight: 0 }}>
          <SvgRenderer unlocked={unlocked} size={size} />
        </div>
      )}

      {showLabel && (
        <span
          style={{
            fontFamily: "var(--font-geist-sans, sans-serif)",
            fontSize: Math.max(9, size * 0.16),
            fontWeight: 600,
            color: unlocked ? TEXT_PRIMARY : TEXT_SECONDARY,
            textAlign: "center",
            maxWidth: size + 16,
            lineHeight: 1.2,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {meta.label}
        </span>
      )}
    </div>
  );
}

export const AchievementBadge = memo(AchievementBadgeInner);
AchievementBadge.displayName = "AchievementBadge";
