/**
 * SHA-256 utilities for the Nightjar Verification Canvas.
 *
 * Provides helpers for hashing verification artefacts (spec text, generated
 * code, stage results) to produce deterministic proof fingerprints that can
 * be embedded in badges and audit trails.
 *
 * Uses the Web Crypto API (`SubtleCrypto`) available in all modern browsers
 * and in the Node.js 20+ `globalThis.crypto` object.  Falls back to the
 * Node.js `crypto` built-in for SSR contexts that predate the global.
 */

// ---------------------------------------------------------------------------
// Core hash primitive
// ---------------------------------------------------------------------------

/**
 * Compute the SHA-256 digest of an arbitrary string and return it as a
 * lowercase hex string.
 *
 * Works in both browser and Node.js environments.
 *
 * @param input - The string to hash (encoded as UTF-8).
 * @returns A 64-character lowercase hex digest.
 */
export async function sha256Hex(input: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(input);

  // Prefer the standards-compliant Web Crypto API
  const subtle: SubtleCrypto | undefined =
    (typeof globalThis !== "undefined" && globalThis.crypto?.subtle) ||
    (typeof crypto !== "undefined" && (crypto as Crypto).subtle) ||
    undefined;

  if (subtle) {
    const hashBuffer = await subtle.digest("SHA-256", data);
    return bufferToHex(hashBuffer);
  }

  // Fallback for older Node.js environments without globalThis.crypto
  const nodeCrypto = await import("crypto");
  return nodeCrypto
    .createHash("sha256")
    .update(input, "utf8")
    .digest("hex");
}

/** Convert an `ArrayBuffer` to a lowercase hex string. */
function bufferToHex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

// ---------------------------------------------------------------------------
// Proof-fingerprint helpers
// ---------------------------------------------------------------------------

/**
 * Produce a short (8-character) proof fingerprint from a full hex digest.
 *
 * The fingerprint is used in badge tooltips and audit-trail links.
 *
 * @param hexDigest - A full 64-character SHA-256 hex string.
 * @returns The first 8 characters of the digest.
 */
export function shortFingerprint(hexDigest: string): string {
  return hexDigest.slice(0, 8);
}

/**
 * Hash a verification run's key fields to produce a stable proof ID.
 *
 * The input is the canonical JSON serialisation of:
 *   `{ spec_id, model, run_id, verified, trust_level }`
 *
 * @param fields - Run metadata fields.
 * @returns A full SHA-256 hex digest.
 */
export async function hashRunProof(fields: {
  spec_id: string;
  model: string;
  run_id: string;
  verified: boolean;
  trust_level: string;
}): Promise<string> {
  // Canonical JSON — keys sorted alphabetically for determinism
  const canonical = JSON.stringify(
    Object.fromEntries(Object.entries(fields).sort(([a], [b]) => a.localeCompare(b)))
  );
  return sha256Hex(canonical);
}

/**
 * Derive a proof hash from a spec's raw text content.
 *
 * This anchors the badge to the exact spec that was verified.
 *
 * @param specText - Raw contents of the `.card.md` file.
 * @returns A full SHA-256 hex digest.
 */
export async function hashSpecText(specText: string): Promise<string> {
  return sha256Hex(specText);
}

/**
 * Return a human-readable proof label combining trust level and fingerprint.
 *
 * @example
 * proofLabel("FORMALLY_VERIFIED", "a1b2c3d4") → "FV:a1b2c3d4"
 *
 * @param trustLevel - The trust level string.
 * @param fingerprint - An 8-character hex fingerprint.
 */
export function proofLabel(trustLevel: string, fingerprint: string): string {
  const prefix = trustLevel
    .split("_")
    .map((w) => w[0])
    .join("");
  return `${prefix}:${fingerprint}`;
}
