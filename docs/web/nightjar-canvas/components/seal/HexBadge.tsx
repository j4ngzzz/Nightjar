"use client";

/**
 * HexBadge.tsx
 *
 * Small 30 px-tall hexagonal badge — the README-embed variant of the
 * Verification Seal.  Static, no animation, no external dependencies.
 *
 * Layout (left → right):
 *   [hexagon border]  [12px bird icon]  [VERIFIED text]
 *
 * The badge glows on hover: border brightens from #D4920A → #F5B93A and a
 * soft amber box-shadow appears.
 *
 * Props
 * -----
 * proofHash  — shown in a <title> tooltip for accessibility (first 7 chars)
 * href       — optional link wrapper
 * className  — extra Tailwind classes for the <span> wrapper
 */

import { type ComponentProps } from "react";

// ---------------------------------------------------------------------------
// Design tokens
// ---------------------------------------------------------------------------
const AMBER = "#D4920A";
const GOLD = "#F5B93A";
const BG = "#0D0B09";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface HexBadgeProps {
  proofHash?: string;
  href?: string;
  className?: string;
}

// ---------------------------------------------------------------------------
// Nightjar bird icon — stylised wing silhouette as an inline SVG path
// The shape is a minimalist nightjar (goatsucker) in profile: swept wings,
// low body.  Fits in a 12×12 viewport.
// ---------------------------------------------------------------------------
function NightjarIcon({ size = 12 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 12 12"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      style={{ display: "inline-block", verticalAlign: "middle" }}
    >
      {/* Wing sweep — left wing */}
      <path
        d="M6 7 C4 6, 2 4, 0.5 5 C2 3, 5 3.5, 6 5Z"
        fill={AMBER}
      />
      {/* Wing sweep — right wing */}
      <path
        d="M6 7 C8 6, 10 4, 11.5 5 C10 3, 7 3.5, 6 5Z"
        fill={AMBER}
      />
      {/* Body / tail */}
      <path
        d="M5.2 5.5 Q6 9, 6.8 5.5 Q6 4.5, 5.2 5.5Z"
        fill={GOLD}
      />
      {/* Eye — tiny dot */}
      <circle cx={5} cy={5} r={0.5} fill={BG} />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Hexagon outline path (30 px tall, 26 px wide — pointy-top orientation)
// ---------------------------------------------------------------------------
//
// A pointy-top regular hexagon fitting in a 26 × 30 bounding box:
//   centre (13, 15), circumradius 14
//   vertices at angles 90°, 30°, 330°, 270°, 210°, 150° (−90° offset)
//
const HEX_W = 26;
const HEX_H = 30;
const HEX_CX = 13;
const HEX_CY = 15;
const HEX_R = 13.5; // slightly inset so stroke doesn't clip

function hexPath(): string {
  const pts = Array.from({ length: 6 }, (_, i) => {
    const angle = (Math.PI / 3) * i - Math.PI / 2; // pointy-top
    return `${(HEX_CX + HEX_R * Math.cos(angle)).toFixed(2)},${(HEX_CY + HEX_R * Math.sin(angle)).toFixed(2)}`;
  });
  return `M${pts.join("L")}Z`;
}

const HEX_POINTS = hexPath();

// ---------------------------------------------------------------------------
// Badge component
// ---------------------------------------------------------------------------

export function HexBadge({ proofHash, href, className }: HexBadgeProps) {
  const shortHash = proofHash ? proofHash.slice(0, 7) : "";
  const label = `Nightjar verified${shortHash ? ` — ${shortHash}` : ""}`;

  const inner = (
    <span
      className={className}
      role="img"
      aria-label={label}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "0 10px",
        height: 30,
        position: "relative",
        cursor: href ? "pointer" : "default",
        // Hover glow handled via CSS custom property trick below
      }}
    >
      {/* Hexagonal border SVG — absolute, fills the badge */}
      <svg
        width={HEX_W}
        height={HEX_H}
        viewBox={`0 0 ${HEX_W} ${HEX_H}`}
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          pointerEvents: "none",
        }}
        aria-hidden="true"
      >
        {shortHash && <title>{label}</title>}
        {/* Background */}
        <path d={HEX_POINTS} fill={BG} />
        {/* Border — class-driven so hover can change stroke */}
        <path
          d={HEX_POINTS}
          fill="none"
          className="nightjar-badge-border"
          strokeWidth={1.2}
          strokeLinejoin="round"
          style={{ stroke: AMBER }}
        />
      </svg>

      {/* Pill background (fills space to the right of hex) */}
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 5,
          paddingLeft: HEX_W / 2 + 4,
          paddingRight: 8,
          height: "100%",
          backgroundColor: BG,
          borderRadius: "0 4px 4px 0",
          borderTop: `1px solid ${AMBER}`,
          borderRight: `1px solid ${AMBER}`,
          borderBottom: `1px solid ${AMBER}`,
          // Transition for hover glow
          transition: "border-color 150ms ease, box-shadow 150ms ease",
        }}
        // Hover styles injected via inline style + class below
        className="nightjar-badge-pill"
      >
        <NightjarIcon size={12} />
        <span
          style={{
            fontFamily: "var(--font-geist-sans), system-ui, sans-serif",
            fontWeight: 600,
            letterSpacing: "0.12em",
            fontSize: 9,
            color: AMBER,
            textTransform: "uppercase",
            whiteSpace: "nowrap",
            transition: "color 150ms ease",
          }}
          className="nightjar-badge-text"
        >
          VERIFIED
        </span>
      </span>

      {/* Scoped hover styles */}
      <style>{`
        .nightjar-badge-border {
          transition: stroke 150ms ease;
        }
        :hover > svg .nightjar-badge-border,
        :focus > svg .nightjar-badge-border {
          stroke: ${GOLD} !important;
        }
        :hover .nightjar-badge-pill,
        :focus .nightjar-badge-pill {
          border-color: ${GOLD} !important;
          box-shadow: 0 0 8px rgba(212, 146, 10, 0.4) !important;
        }
        :hover .nightjar-badge-text,
        :focus .nightjar-badge-text {
          color: ${GOLD} !important;
        }
      `}</style>
    </span>
  );

  if (href) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        style={{ display: "inline-flex", textDecoration: "none" }}
      >
        {inner}
      </a>
    );
  }

  return inner;
}

// ---------------------------------------------------------------------------
// Static variant — zero JS, for README img embeds
// (renders as a plain SVG string you can inline or serve as /api/badge.svg)
// ---------------------------------------------------------------------------

type StaticHexBadgeSvgProps = ComponentProps<"svg"> & { proofHash?: string };

/**
 * StaticHexBadgeSvg
 *
 * Returns a self-contained SVG element suitable for embedding in a Markdown
 * README.  No animation, no hover, no React events — pure markup.
 *
 * Consumers can stringify this component with `renderToStaticMarkup` to
 * produce a badge .svg file.
 */
export function StaticHexBadgeSvg({ proofHash, ...svgProps }: StaticHexBadgeSvgProps) {
  const shortHash = proofHash ? proofHash.slice(0, 7) : "";
  // Badge dimensions: hex (26) + gap (4) + text area (52) + padding (8) = 90 wide, 30 tall
  const W = 90;
  const H = 30;

  // Pointy-top hex outline at left edge
  const hexPts = Array.from({ length: 6 }, (_, i) => {
    const angle = (Math.PI / 3) * i - Math.PI / 2;
    return `${(HEX_CX + HEX_R * Math.cos(angle)).toFixed(2)},${(HEX_CY + HEX_R * Math.sin(angle)).toFixed(2)}`;
  }).join(" ");

  // Bird icon approximated with simple paths at (32, 9) — 12×12 space
  const bx = 32; // bird x offset within badge
  const by = 7;  // bird y offset

  return (
    <svg
      width={W}
      height={H}
      viewBox={`0 0 ${W} ${H}`}
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label={`Nightjar verified${shortHash ? ` — ${shortHash}` : ""}`}
      {...svgProps}
    >
      <title>{`Nightjar verified${shortHash ? ` — ${shortHash}` : ""}`}</title>

      {/* Full badge background */}
      <rect width={W} height={H} fill={BG} rx={2} />

      {/* Left hex border */}
      <polygon
        points={hexPts}
        fill={BG}
        stroke={AMBER}
        strokeWidth={1.2}
        strokeLinejoin="round"
      />

      {/* Right section border */}
      <rect
        x={HEX_W - 1}
        y={0.6}
        width={W - HEX_W + 0.8}
        height={H - 1.2}
        rx={2}
        fill={BG}
        stroke={AMBER}
        strokeWidth={1.2}
      />

      {/* Bird icon — left wing */}
      <path
        d={`M${bx + 6} ${by + 7} C${bx + 4} ${by + 6}, ${bx + 2} ${by + 4}, ${bx + 0.5} ${by + 5} C${bx + 2} ${by + 3}, ${bx + 5} ${by + 3.5}, ${bx + 6} ${by + 5}Z`}
        fill={AMBER}
      />
      {/* Bird icon — right wing */}
      <path
        d={`M${bx + 6} ${by + 7} C${bx + 8} ${by + 6}, ${bx + 10} ${by + 4}, ${bx + 11.5} ${by + 5} C${bx + 10} ${by + 3}, ${bx + 7} ${by + 3.5}, ${bx + 6} ${by + 5}Z`}
        fill={AMBER}
      />
      {/* Bird body */}
      <path
        d={`M${bx + 5.2} ${by + 5.5} Q${bx + 6} ${by + 9}, ${bx + 6.8} ${by + 5.5} Q${bx + 6} ${by + 4.5}, ${bx + 5.2} ${by + 5.5}Z`}
        fill={GOLD}
      />

      {/* VERIFIED text */}
      <text
        x={49}
        y={19}
        textAnchor="middle"
        fill={AMBER}
        fontSize={8}
        fontWeight="600"
        fontFamily="system-ui, sans-serif"
        letterSpacing="0.12em"
      >
        VERIFIED
      </text>
    </svg>
  );
}
