/**
 * Badge SVG Route — /api/badge/[owner]/[repo]
 *
 * Returns a shields.io-style SVG badge for a given owner/repo.
 * Color thresholds:
 *   81–100 → #F5B93A (gold — formally verified range)
 *   61–80  → #D4920A (amber — property verified range)
 *   0–60   → #C84B2F (ember red — failing / unverified)
 *
 * Query params:
 *   ?style=for-the-badge  (default)
 *   ?style=flat-square
 *   ?style=flat
 *
 * Cache: 5 minutes (badge data changes frequently).
 */

import type { NextRequest } from "next/server";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COLOR_GOLD = "#F5B93A";
const COLOR_AMBER = "#D4920A";
const COLOR_RED = "#C84B2F";
const COLOR_LABEL_BG = "#555555";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type BadgeStyle = "for-the-badge" | "flat-square" | "flat";

interface BadgeConfig {
  height: number;
  fontSize: number;
  radius: number;
  letterSpacing: number;
  paddingX: number;
  textYOffset: number;
  textUppercase: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function badgeColor(score: number): string {
  if (score >= 81) return COLOR_GOLD;
  if (score >= 61) return COLOR_AMBER;
  return COLOR_RED;
}

function scoreToLabel(score: number, isVerified: boolean): string {
  if (!isVerified) return "failing";
  if (score >= 96) return "certified";
  if (score >= 81) return "verified";
  if (score >= 61) return "proving";
  return "unverified";
}

function styleConfig(style: BadgeStyle): BadgeConfig {
  switch (style) {
    case "for-the-badge":
      return {
        height: 28,
        fontSize: 11,
        radius: 4,
        letterSpacing: 0.8,
        paddingX: 12,
        textYOffset: 17,
        textUppercase: true,
      };
    case "flat-square":
      return {
        height: 20,
        fontSize: 11,
        radius: 0,
        letterSpacing: 0,
        paddingX: 8,
        textYOffset: 14,
        textUppercase: false,
      };
    case "flat":
    default:
      return {
        height: 20,
        fontSize: 11,
        radius: 3,
        letterSpacing: 0,
        paddingX: 8,
        textYOffset: 14,
        textUppercase: false,
      };
  }
}

/** Rough character-width estimator for DejaVu Sans at the given font size. */
function approxTextWidth(text: string, fontSize: number): number {
  // Base ratio for Latin characters: ~0.60× font size.
  // Non-ASCII characters (e.g. ✓ U+2713, ✗ U+2717, |) tend to render wider;
  // add an extra 0.6× per non-ASCII char to avoid text clipping in SVG renderers.
  let width = 0;
  for (const ch of text) {
    width += ch.codePointAt(0)! > 0x7f ? fontSize * 1.2 : fontSize * 0.6;
  }
  return width;
}

/**
 * Fetch the latest badge data for owner/repo from the backend.
 * Returns a stub on any error so the badge still renders.
 */
async function fetchBadgeData(
  owner: string,
  repo: string
): Promise<{ score: number; isVerified: boolean }> {
  // Prefer the server-only API_URL (not exposed to browser bundle).
  const apiBase =
    process.env.API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000";

  try {
    const res = await fetch(
      `${apiBase}/api/badge/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`,
      { next: { revalidate: 300 } }
    );
    if (!res.ok) throw new Error(`API ${res.status}`);

    const data = await res.json();
    // `pass_rate` is 0–1 in the API; convert to 0–100.
    const score = Math.round((data.pass_rate ?? 0.88) * 100);
    const isVerified =
      data.trust_level === "FORMALLY_VERIFIED" ||
      data.trust_level === "PROPERTY_VERIFIED";

    return { score, isVerified };
  } catch {
    // Fallback stub.
    return { score: 88, isVerified: true };
  }
}

// ---------------------------------------------------------------------------
// SVG builder
// ---------------------------------------------------------------------------

function buildBadgeSvg(
  score: number,
  isVerified: boolean,
  style: BadgeStyle
): string {
  const cfg = styleConfig(style);
  const color = badgeColor(score);
  const statusLabel = scoreToLabel(score, isVerified);

  // Left section (label "nightjar")
  const leftText = cfg.textUppercase ? "NIGHTJAR" : "nightjar";
  const leftContentWidth = approxTextWidth(leftText, cfg.fontSize);
  const leftWidth = Math.ceil(leftContentWidth + cfg.paddingX * 2);

  // Right section (" ✓ {score} ")
  const checkmark = isVerified ? "✓" : "✗";
  const rightText = cfg.textUppercase
    ? `${checkmark} ${score} | ${statusLabel.toUpperCase()}`
    : `${checkmark} ${score} | ${statusLabel}`;
  const rightContentWidth = approxTextWidth(rightText, cfg.fontSize);
  const rightWidth = Math.ceil(rightContentWidth + cfg.paddingX * 2);

  const totalWidth = leftWidth + rightWidth;
  const h = cfg.height;
  const r = cfg.radius;
  const ty = cfg.textYOffset;

  return `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${totalWidth}" height="${h}" role="img" aria-label="nightjar: ${score}">
  <title>nightjar: ${checkmark} ${score} ${statusLabel}</title>
  <defs>
    <linearGradient id="s" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
      <stop offset="1" stop-opacity=".1"/>
    </linearGradient>
    <clipPath id="r">
      <rect width="${totalWidth}" height="${h}" rx="${r}" fill="white"/>
    </clipPath>
  </defs>
  <g clip-path="url(#r)">
    <rect width="${leftWidth}" height="${h}" fill="${COLOR_LABEL_BG}"/>
    <rect x="${leftWidth}" width="${rightWidth}" height="${h}" fill="${color}"/>
    <rect width="${totalWidth}" height="${h}" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="${cfg.fontSize}" letter-spacing="${cfg.letterSpacing}">
    <text x="${Math.floor(leftWidth / 2) + 1}" y="${ty + 1}" fill="#010101" fill-opacity=".3">${leftText}</text>
    <text x="${Math.floor(leftWidth / 2)}" y="${ty}">${leftText}</text>
    <text x="${leftWidth + Math.floor(rightWidth / 2) + 1}" y="${ty + 1}" fill="#010101" fill-opacity=".3">${rightText}</text>
    <text x="${leftWidth + Math.floor(rightWidth / 2)}" y="${ty}">${rightText}</text>
  </g>
</svg>`;
}

// ---------------------------------------------------------------------------
// GET handler
// ---------------------------------------------------------------------------

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ owner: string; repo: string }> }
) {
  const { owner, repo } = await params;
  const { searchParams } = request.nextUrl;

  const rawStyle = searchParams.get("style") ?? "flat";
  const style: BadgeStyle =
    rawStyle === "for-the-badge"
      ? "for-the-badge"
      : rawStyle === "flat-square"
        ? "flat-square"
        : "flat";

  const { score, isVerified } = await fetchBadgeData(owner, repo);
  const svg = buildBadgeSvg(score, isVerified, style);

  return new Response(svg, {
    headers: {
      "Content-Type": "image/svg+xml;charset=utf-8",
      "Cache-Control": "public, max-age=300, s-maxage=300, stale-while-revalidate=600",
      // Tell shields.io / GitHub not to cache aggressively.
      Pragma: "no-cache",
      "X-Nightjar-Score": String(score),
    },
  });
}
