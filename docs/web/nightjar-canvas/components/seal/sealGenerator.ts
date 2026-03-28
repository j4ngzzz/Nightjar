/**
 * sealGenerator.ts
 *
 * Deterministic hash → SVG geometry for the Nightjar Verification Seal.
 *
 * The seal is a 200×200 hexagonal glyph.  Every call with the same proofHash
 * produces identical geometry; different hashes produce visually distinct seals.
 *
 * Algorithm:
 *   1. Parse the first 8 hex chars of the proofHash as a uint32 seed.
 *   2. Drive a mulberry32 PRNG with that seed — pure math, no platform entropy.
 *   3. Derive: outer hexagon vertices, three concentric hexagonal rings, and
 *      a 6-fold radially-symmetric interior snowflake (6–12 spokes × 6 copies).
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Point {
  x: number;
  y: number;
}

export interface LineSegment {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  /** total length of this segment, pre-computed for stroke-dasharray animation */
  length: number;
}

export interface SealGeometry {
  /** Six vertices of the outer hexagon, in order. */
  hexVertices: Point[];
  /** Radii of the three concentric inner hexagonal rings. */
  rings: number[];
  /** Interior snowflake lines (6-fold symmetric). */
  lines: LineSegment[];
  /** SVG centre coordinates */
  cx: number;
  cy: number;
  /** Outer hexagon radius */
  r: number;
  /** First 7 chars of proofHash, shown in the badge label */
  shortHash: string;
}

// ---------------------------------------------------------------------------
// mulberry32 PRNG — public domain, deterministic, no external deps
// ---------------------------------------------------------------------------

/**
 * Returns a seeded pseudo-random function in [0, 1).
 * Implementation: mulberry32 by Tommy Ettinger (public domain).
 */
export function seededRandom(seed: number): () => number {
  let s = seed >>> 0; // coerce to uint32
  return function rng(): number {
    s = (s + 0x6d2b79f5) >>> 0;
    let z = s;
    z = Math.imul(z ^ (z >>> 15), z | 1);
    z ^= z + Math.imul(z ^ (z >>> 7), z | 61);
    return ((z ^ (z >>> 14)) >>> 0) / 0x100000000;
  };
}

// ---------------------------------------------------------------------------
// Geometry helpers
// ---------------------------------------------------------------------------

function segmentLength(x1: number, y1: number, x2: number, y2: number): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  return Math.sqrt(dx * dx + dy * dy);
}

// ---------------------------------------------------------------------------
// Main generator
// ---------------------------------------------------------------------------

/**
 * Generate the deterministic seal geometry from a proof hash.
 *
 * @param proofHash  - Any hex string; only the first 8 chars are consumed as seed.
 * @param size       - Bounding box side length in pixels (default 200).
 * @returns          SealGeometry — pure data, no DOM, no React.
 *
 * @example
 * const g = generateSeal("abc12345");
 * // g.hexVertices → 6 {x, y} points
 * // g.rings       → [r/7, 2r/7, 4r/7]
 * // g.lines       → 6-fold symmetric line segments
 */
export function generateSeal(proofHash: string, size = 200): SealGeometry {
  // --- 1. Seed -----------------------------------------------------------------
  // Pad with zeroes if the hash is shorter than 8 chars so parseInt never
  // returns NaN.  This lets callers pass arbitrary strings safely.
  const hexChunk = proofHash.slice(0, 8).padEnd(8, "0");
  const seed = parseInt(hexChunk, 16) >>> 0; // uint32
  const rng = seededRandom(seed);

  // --- 2. Outer hexagon --------------------------------------------------------
  const cx = size / 2;
  const cy = size / 2;
  const r = size * 0.42;

  // Flat-topped orientation: first vertex at top-right (angle = -π/6 = −30°)
  const hexVertices: Point[] = Array.from({ length: 6 }, (_, i) => ({
    x: cx + r * Math.cos((Math.PI / 3) * i - Math.PI / 6),
    y: cy + r * Math.sin((Math.PI / 3) * i - Math.PI / 6),
  }));

  // --- 3. Concentric hexagonal rings at prime proportions ----------------------
  const rings: number[] = [1 / 7, 2 / 7, 4 / 7].map((f) => f * r);

  // --- 4. 6-fold radially symmetric interior lines (snowflake) -----------------
  // Between 6 and 12 spoke templates (one spoke → 6 copies by symmetry).
  const lineCount = 6 + Math.floor(rng() * 7); // 6 … 12

  const lines: LineSegment[] = Array.from({ length: lineCount }, (_, i) => {
    // Base angle for this spoke, spread evenly within one 60° sector.
    const baseAngle = (i / lineCount) * (Math.PI / 3);
    // Spoke length: 30%–80% of outer radius.
    const len = (0.3 + rng() * 0.5) * r;

    // Replicate the spoke 6 times (one per hex sector).
    const allAngles: number[] = Array.from({ length: 6 }, (_, k) => baseAngle + k * (Math.PI / 3));

    return allAngles.map((angle) => {
      const x2 = cx + len * Math.cos(angle);
      const y2 = cy + len * Math.sin(angle);
      return {
        x1: cx,
        y1: cy,
        x2,
        y2,
        length: segmentLength(cx, cy, x2, y2),
      };
    });
  }).flat();

  // --- 5. Short hash label -----------------------------------------------------
  const shortHash = proofHash.slice(0, 7);

  return { hexVertices, rings, lines, cx, cy, r, shortHash };
}

// ---------------------------------------------------------------------------
// SVG path helpers (used by VerificationSeal renderer)
// ---------------------------------------------------------------------------

/**
 * Convert an array of Points into a closed SVG polygon `points` attribute string.
 *
 * @example
 * pointsToSvgAttr([{x:10,y:0},{x:5,y:9},{x:0,y:0}]) → "10,0 5,9 0,0"
 */
export function pointsToSvgAttr(pts: Point[]): string {
  return pts.map((p) => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
}

/**
 * Build a closed hexagon `<polygon>` points string scaled to a given ring radius.
 * Shares the same flat-topped orientation as the outer hexagon.
 */
export function hexRingPoints(cx: number, cy: number, radius: number): string {
  const pts: Point[] = Array.from({ length: 6 }, (_, i) => ({
    x: cx + radius * Math.cos((Math.PI / 3) * i - Math.PI / 6),
    y: cy + radius * Math.sin((Math.PI / 3) * i - Math.PI / 6),
  }));
  return pointsToSvgAttr(pts);
}
