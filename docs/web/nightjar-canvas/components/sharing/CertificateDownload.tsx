"use client";

/**
 * CertificateDownload — client-side SVG certificate generator.
 *
 * Generates an A4-proportion (794×1123px) SVG certificate documenting
 * a Nightjar verification result. Uses the amber design token palette.
 * No server round-trip — entirely client-side via URL.createObjectURL.
 *
 * Contents:
 *   - Hexagonal border motif in amber (uses sealGenerator geometry).
 *   - Module name, commit hash, date, Trust Score.
 *   - Top 10 invariants listed.
 *   - "Download Certificate (SVG)" button triggers a browser download.
 *
 * Colour rules: NO green, NO purple. Amber palette only.
 */

import { Download, Award } from "lucide-react";
import { cn } from "@/lib/cn";
import { generateSeal, pointsToSvgAttr, hexRingPoints } from "@/components/seal/sealGenerator";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CertificateDownloadProps {
  /** Module / spec name (e.g. "payment-processing"). */
  moduleName: string;
  /** Short commit hash (7 chars). */
  commitHash: string;
  /** ISO date string of verification run. */
  verifiedAt: string;
  /** Trust score 0–100. */
  trustScore: number;
  /** Proof hash for deterministic seal geometry. */
  proofHash: string;
  /** Up to the first 10 are used. */
  invariants: string[];
  /** Optional extra className for the trigger button wrapper. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Design constants
// ---------------------------------------------------------------------------

// A4 at 96dpi: 794×1123
const CERT_W = 794;
const CERT_H = 1123;

const BG = "#0D0B09";
const AMBER = "#F5B93A";
const AMBER_DIM = "#D4920A";
const AMBER_DEEP = "#A87020";
const TEXT_PRIMARY = "#F0EBE3";
const TEXT_SECONDARY = "#8B8579";
const BORDER = "#2A2315";
const RED = "#C84B2F";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function scoreColor(score: number): string {
  if (score >= 81) return AMBER;
  if (score >= 61) return AMBER_DIM;
  return RED;
}

function scoreLabel(score: number): string {
  if (score >= 96) return "CERTIFIED";
  if (score >= 81) return "FORMALLY VERIFIED";
  if (score >= 61) return "PROPERTY VERIFIED";
  if (score >= 41) return "SCHEMA VERIFIED";
  return "UNVERIFIED";
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// SVG hex border strip (top and bottom decorative strips)
// ---------------------------------------------------------------------------

/**
 * Build a row of small hexagons as an SVG <path> string.
 * The hexagons are flat-topped and tightly packed.
 */
function hexStripPath(
  y: number,
  width: number,
  hexR: number,
  opacity: number
): string {
  const hexW = hexR * 2;
  const spacing = hexW * 1.05;
  const count = Math.ceil(width / spacing) + 2;
  const offsetX = -hexR;

  let path = "";
  for (let i = 0; i < count; i++) {
    const cx = offsetX + i * spacing;
    const cy = y;
    for (let k = 0; k < 6; k++) {
      const angle = (Math.PI / 3) * k - Math.PI / 6;
      const x = cx + hexR * Math.cos(angle);
      const yy = cy + hexR * Math.sin(angle);
      path += k === 0 ? `M${x.toFixed(1)},${yy.toFixed(1)}` : `L${x.toFixed(1)},${yy.toFixed(1)}`;
    }
    path += "Z";
  }

  return `<path d="${path}" fill="none" stroke="${AMBER}" stroke-width="0.8" opacity="${opacity}"/>`;
}

// ---------------------------------------------------------------------------
// Main SVG generator
// ---------------------------------------------------------------------------

function generateCertificateSvg(props: CertificateDownloadProps): string {
  const {
    moduleName,
    commitHash,
    verifiedAt,
    trustScore,
    proofHash,
    invariants,
  } = props;

  const topInvariants = invariants.slice(0, 10);
  const primaryColor = scoreColor(trustScore);
  const label = scoreLabel(trustScore);
  const formattedDate = formatDate(verifiedAt);

  // Generate seal geometry at 120px for the certificate.
  const seal = generateSeal(proofHash, 120);
  const sealCx = CERT_W / 2;
  const sealCy = 248;

  // Build hex vertices SVG polygon points.
  const hexPts = pointsToSvgAttr(
    seal.hexVertices.map((p) => ({
      x: p.x - seal.cx + sealCx,
      y: p.y - seal.cy + sealCy,
    }))
  );

  // Ring polygons.
  const ringPolygons = seal.rings
    .map(
      (r, i) =>
        `<polygon points="${hexRingPoints(sealCx, sealCy, r)}" fill="none" stroke="${primaryColor}" stroke-width="${0.6 + i * 0.2}" opacity="${0.3 + i * 0.1}"/>`
    )
    .join("\n  ");

  // Snowflake lines.
  const snowflakeLines = seal.lines
    .map((l) => {
      const x1 = l.x1 - seal.cx + sealCx;
      const y1 = l.y1 - seal.cy + sealCy;
      const x2 = l.x2 - seal.cx + sealCx;
      const y2 = l.y2 - seal.cy + sealCy;
      return `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" stroke="${primaryColor}" stroke-width="0.6" opacity="0.35"/>`;
    })
    .join("\n  ");

  // Invariant list rows (up to 10).
  const invStartY = 680;
  const invRowH = 32;
  const invRows = topInvariants
    .map((inv, i) => {
      const y = invStartY + i * invRowH;
      const truncated =
        inv.length > 72 ? inv.slice(0, 69) + "…" : inv;
      return `
  <line x1="80" y1="${y + 16}" x2="${CERT_W - 80}" y2="${y + 16}" stroke="${BORDER}" stroke-width="0.5"/>
  <text x="80" y="${y + 10}" font-family="monospace" font-size="10" fill="${TEXT_SECONDARY}">${i + 1 < 10 ? "0" : ""}${i + 1}</text>
  <text x="108" y="${y + 10}" font-family="monospace" font-size="10" fill="${TEXT_PRIMARY}">${escapeXml(truncated)}</text>`;
    })
    .join("");

  // Top + bottom hex strip decorations.
  const topStrip = hexStripPath(14, CERT_W, 8, 0.35);
  const bottomStrip = hexStripPath(CERT_H - 14, CERT_W, 8, 0.35);

  return `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${CERT_W}" height="${CERT_H}" viewBox="0 0 ${CERT_W} ${CERT_H}">
  <title>Nightjar Verification Certificate — ${moduleName}</title>

  <!-- Background -->
  <rect width="${CERT_W}" height="${CERT_H}" fill="${BG}"/>

  <!-- Outer border -->
  <rect x="24" y="24" width="${CERT_W - 48}" height="${CERT_H - 48}" fill="none" stroke="${BORDER}" stroke-width="1" rx="8"/>
  <rect x="28" y="28" width="${CERT_W - 56}" height="${CERT_H - 56}" fill="none" stroke="${primaryColor}" stroke-width="0.5" rx="6" opacity="0.4"/>

  <!-- Hex strip decorations -->
  ${topStrip}
  ${bottomStrip}

  <!-- Certificate header -->
  <text x="${CERT_W / 2}" y="80" text-anchor="middle" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="${TEXT_SECONDARY}" letter-spacing="0.18em">NIGHTJAR VERIFICATION CERTIFICATE</text>

  <!-- Divider line under header -->
  <line x1="80" y1="96" x2="${CERT_W - 80}" y2="96" stroke="${BORDER}" stroke-width="1"/>

  <!-- Seal -->
  <polygon points="${hexPts}" fill="none" stroke="${primaryColor}" stroke-width="1.5" opacity="0.8"/>
  ${ringPolygons}
  ${snowflakeLines}

  <!-- Trust score circle overlay on seal -->
  <circle cx="${sealCx}" cy="${sealCy}" r="28" fill="${BG}80"/>
  <text x="${sealCx}" y="${sealCy - 4}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="22" font-weight="700" fill="${primaryColor}">${trustScore}</text>
  <text x="${sealCx}" y="${sealCy + 12}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="8" fill="${TEXT_SECONDARY}" letter-spacing="0.1em">/100</text>

  <!-- Trust label badge -->
  <rect x="${sealCx - 80}" y="${sealCy + 64}" width="160" height="24" rx="4" fill="${primaryColor}1A" stroke="${primaryColor}4D" stroke-width="1"/>
  <text x="${sealCx}" y="${sealCy + 80}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="10" font-weight="700" fill="${primaryColor}" letter-spacing="0.12em">${label}</text>

  <!-- Module name -->
  <text x="${CERT_W / 2}" y="388" text-anchor="middle" font-family="system-ui, sans-serif" font-size="28" font-weight="700" fill="${TEXT_PRIMARY}">${escapeXml(moduleName)}</text>

  <!-- Meta row: commit hash, date -->
  <text x="${CERT_W / 2}" y="424" text-anchor="middle" font-family="monospace" font-size="13" fill="${TEXT_SECONDARY}">commit ${escapeXml(commitHash.slice(0, 7))} · ${escapeXml(formattedDate)}</text>

  <!-- Divider -->
  <line x1="80" y1="452" x2="${CERT_W - 80}" y2="452" stroke="${BORDER}" stroke-width="1"/>

  <!-- Declaration text -->
  <text x="${CERT_W / 2}" y="480" text-anchor="middle" font-family="system-ui, sans-serif" font-size="13" fill="${TEXT_SECONDARY}">This certifies that the specification has been formally verified by the Nightjar pipeline.</text>
  <text x="${CERT_W / 2}" y="500" text-anchor="middle" font-family="system-ui, sans-serif" font-size="13" fill="${TEXT_SECONDARY}">The following invariants were proven to hold across all inputs:</text>

  <!-- Invariants section header -->
  <text x="80" y="548" font-family="system-ui, sans-serif" font-size="11" font-weight="700" fill="${AMBER_DEEP}" letter-spacing="0.14em">PROVEN INVARIANTS</text>
  <text x="${CERT_W - 80}" y="548" text-anchor="end" font-family="monospace" font-size="11" fill="${TEXT_SECONDARY}">${topInvariants.length} of ${invariants.length}</text>
  <line x1="80" y1="558" x2="${CERT_W - 80}" y2="558" stroke="${AMBER_DIM}" stroke-width="0.5" opacity="0.6"/>

  <!-- Invariant rows -->
  ${invRows}

  <!-- Footer -->
  <line x1="80" y1="${CERT_H - 80}" x2="${CERT_W - 80}" y2="${CERT_H - 80}" stroke="${BORDER}" stroke-width="1"/>
  <text x="80" y="${CERT_H - 56}" font-family="system-ui, sans-serif" font-size="11" fill="${TEXT_SECONDARY}">nightjar.dev</text>
  <text x="${CERT_W - 80}" y="${CERT_H - 56}" text-anchor="end" font-family="monospace" font-size="11" fill="${TEXT_SECONDARY}">${escapeXml(commitHash.slice(0, 7))}</text>
  <text x="${CERT_W / 2}" y="${CERT_H - 56}" text-anchor="middle" font-family="system-ui, sans-serif" font-size="11" fill="${BORDER}">Mathematically proven. Cryptographically anchored.</text>
</svg>`;
}

// ---------------------------------------------------------------------------
// XML escape helper
// ---------------------------------------------------------------------------

function escapeXml(str: string): string {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

// ---------------------------------------------------------------------------
// Download trigger
// ---------------------------------------------------------------------------

function downloadSvg(svgContent: string, filename: string): void {
  const blob = new Blob([svgContent], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  // Release the object URL after a brief delay so the download can start.
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

// ---------------------------------------------------------------------------
// CertificateDownload component
// ---------------------------------------------------------------------------

export function CertificateDownload({
  moduleName,
  commitHash,
  verifiedAt,
  trustScore,
  proofHash,
  invariants,
  className,
}: CertificateDownloadProps) {
  const primaryColor = scoreColor(trustScore);
  const label = scoreLabel(trustScore);

  function handleDownload() {
    const svg = generateCertificateSvg({
      moduleName,
      commitHash,
      verifiedAt,
      trustScore,
      proofHash,
      invariants,
    });
    const safeName = moduleName.replace(/[^a-z0-9-_]/gi, "-").toLowerCase();
    const shortHash = commitHash.slice(0, 7);
    downloadSvg(svg, `nightjar-certificate-${safeName}-${shortHash}.svg`);
  }

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-[#2A2315] bg-[#0D0B09] p-5",
        className
      )}
    >
      {/* Header row */}
      <div className="flex items-center gap-2">
        <Award size={16} style={{ color: primaryColor }} aria-hidden="true" />
        <span
          className="text-xs font-semibold uppercase tracking-[0.12em]"
          style={{ color: "#8B8579" }}
        >
          Proof Certificate
        </span>
      </div>

      {/* Certificate preview summary */}
      <div className="flex items-center justify-between rounded-md border border-[#2A2315] bg-[#141109] px-4 py-3">
        <div className="flex flex-col gap-0.5">
          <span
            className="text-sm font-semibold"
            style={{ color: TEXT_PRIMARY }}
          >
            {moduleName}
          </span>
          <span
            className="font-mono text-xs"
            style={{ color: TEXT_SECONDARY }}
          >
            {commitHash.slice(0, 7)} · {formatDate(verifiedAt)}
          </span>
        </div>

        {/* Score badge */}
        <div
          className="flex items-center gap-2 rounded px-3 py-1.5"
          style={{
            backgroundColor: `${primaryColor}1A`,
            border: `1px solid ${primaryColor}4D`,
          }}
        >
          <span
            className="text-xl font-bold leading-none"
            style={{ color: primaryColor }}
          >
            {trustScore}
          </span>
          <div className="flex flex-col">
            <span
              className="text-[10px] font-bold leading-none"
              style={{ color: primaryColor, letterSpacing: "0.08em" }}
            >
              /100
            </span>
            <span
              className="mt-0.5 text-[9px] font-bold uppercase leading-none"
              style={{ color: primaryColor, letterSpacing: "0.10em" }}
            >
              {label}
            </span>
          </div>
        </div>
      </div>

      {/* Invariant count hint */}
      {invariants.length > 0 && (
        <p
          className="text-xs"
          style={{ color: TEXT_SECONDARY }}
        >
          Certificate includes{" "}
          <span style={{ color: primaryColor }}>
            {Math.min(invariants.length, 10)}
          </span>{" "}
          proven invariant{invariants.length !== 1 ? "s" : ""}
          {invariants.length > 10 ? ` (top 10 of ${invariants.length})` : ""}.
        </p>
      )}

      {/* Download button */}
      <button
        onClick={handleDownload}
        className={cn(
          "flex items-center justify-center gap-2 rounded-md px-4 py-3 text-sm font-semibold transition-all duration-200",
          "border bg-[#141109]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4920A]"
        )}
        style={{
          borderColor: primaryColor,
          color: primaryColor,
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.backgroundColor =
            `${primaryColor}15`;
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.backgroundColor =
            "#141109";
        }}
      >
        <Download size={16} aria-hidden="true" />
        Download Certificate (SVG)
      </button>
    </div>
  );
}
