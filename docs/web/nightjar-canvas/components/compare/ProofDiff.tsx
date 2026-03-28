"use client";

/**
 * Nightjar Verification Canvas — ProofDiff
 *
 * Monospace diff view for proof text between two verification runs.
 * Uses JetBrains Mono for all content.
 *
 * Line coloring:
 *   Added lines (+):   faint #D4920A background  (amber)
 *   Removed lines (-): faint #C84B2F background  (warm red)
 *   Context lines:     transparent background
 *   Chunk headers (@@): dim amber tint
 *
 * Color rules: amber palette only. Warm red for removals. No green, no purple.
 */

import { useMemo } from "react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DiffLineKind = "added" | "removed" | "context" | "chunk-header";

export interface DiffLine {
  kind: DiffLineKind;
  content: string;
  /** 1-based line number in the original (A) file — undefined for added lines */
  lineNumberA?: number;
  /** 1-based line number in the resulting (B) file — undefined for removed lines */
  lineNumberB?: number;
}

export interface ProofDiffProps {
  /**
   * Proof text from Run A (baseline).
   * Typically the Dafny source or formal spec string.
   */
  proofTextA: string;
  /**
   * Proof text from Run B (comparison).
   */
  proofTextB: string;
  /**
   * Number of context lines to show around changes (default 3).
   */
  contextLines?: number;
  /**
   * Optional filename label shown in the diff header.
   */
  filename?: string;
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Background colors per line kind. */
const LINE_BG: Record<DiffLineKind, string> = {
  added: "rgba(212, 146, 10, 0.12)",
  removed: "rgba(200, 75, 47, 0.10)",
  context: "transparent",
  "chunk-header": "rgba(212, 146, 10, 0.06)",
};

/** Text colors per line kind. */
const LINE_TEXT: Record<DiffLineKind, string> = {
  added: "#D4920A",
  removed: "#C84B2F",
  context: "#8B8579",
  "chunk-header": "#A87020",
};

/** Prefix sigils per line kind. */
const LINE_SIGIL: Record<DiffLineKind, string> = {
  added: "+",
  removed: "−",
  context: " ",
  "chunk-header": "",
};

// ---------------------------------------------------------------------------
// Diff algorithm — unified diff from scratch
// ---------------------------------------------------------------------------

/**
 * Compute the Myers diff between two arrays of strings.
 * Returns an edit script as an array of [kind, line] tuples.
 *
 * We implement the Hunt-McIlroy / Myers O(ND) LCS approach.
 * Reference: Myers, E.W. "An O(ND) Difference Algorithm and Its Variations."
 * Algorithmica 1:2, 251–266, 1986.
 *
 * This is a simplified Myers algorithm suitable for proof text (typically
 * dozens to hundreds of lines). It produces a minimal edit sequence.
 */
function myersDiff(
  linesA: string[],
  linesB: string[]
): Array<{ kind: "equal" | "insert" | "delete"; line: string }> {
  const n = linesA.length;
  const m = linesB.length;
  const max = n + m;

  if (max === 0) return [];

  // v[k] = furthest reaching x-coordinate on diagonal k
  const v: Record<number, number> = { [1]: 0 };
  // trace[d] = snapshot of v after d edits
  const trace: Array<Record<number, number>> = [];

  outer: for (let d = 0; d <= max; d++) {
    trace.push({ ...v });
    for (let k = -d; k <= d; k += 2) {
      let x: number;
      if (k === -d || (k !== d && (v[k - 1] ?? -1) < (v[k + 1] ?? -1))) {
        x = (v[k + 1] ?? 0);
      } else {
        x = (v[k - 1] ?? 0) + 1;
      }
      let y = x - k;
      while (x < n && y < m && linesA[x] === linesB[y]) {
        x++;
        y++;
      }
      v[k] = x;
      if (x >= n && y >= m) {
        trace.push({ ...v });
        break outer;
      }
    }
  }

  // Backtrack through trace to reconstruct the edit path.
  // Standard Myers backtrack: for each edit distance d, determine which
  // diagonal we came from (prevK), emit the trailing snake as equal lines,
  // then emit the single insert or delete that moved us to prevK.
  const edits: Array<{ kind: "equal" | "insert" | "delete"; line: string }> =
    [];
  let x = n;
  let y = m;

  for (let d = trace.length - 1; d >= 1; d--) {
    const vPrev = trace[d - 1];
    const k = x - y;

    // Determine which diagonal we were on before this edit step.
    let prevK: number;
    if (
      k === -(d - 1) ||
      (k !== d - 1 && (vPrev[k - 1] ?? -1) < (vPrev[k + 1] ?? -1))
    ) {
      prevK = k + 1; // came from diagonal k+1 (insert moves us down)
    } else {
      prevK = k - 1; // came from diagonal k-1 (delete moves us right)
    }

    const prevX = vPrev[prevK] ?? 0;
    const prevY = prevX - prevK;

    // Walk the trailing snake backward: equal lines between prevX→x and prevY→y.
    while (x > prevX + 1 && y > prevY + 1) {
      edits.unshift({ kind: "equal", line: linesA[x - 1] });
      x--;
      y--;
    }

    // Emit the single edit that got us onto diagonal k.
    if (prevK === k - 1) {
      // Came from diagonal k-1 via a delete (x moved right, y stayed)
      if (x > 0) {
        edits.unshift({ kind: "delete", line: linesA[x - 1] });
        x--;
      }
    } else {
      // Came from diagonal k+1 via an insert (y moved down, x stayed)
      if (y > 0) {
        edits.unshift({ kind: "insert", line: linesB[y - 1] });
        y--;
      }
    }
  }

  // Any remaining equal lines at the start of the file.
  while (x > 0 && y > 0) {
    edits.unshift({ kind: "equal", line: linesA[x - 1] });
    x--;
    y--;
  }

  return edits;
}

/**
 * Convert raw edit sequence to DiffLines with chunk headers and context culling.
 */
function buildDiffLines(
  linesA: string[],
  linesB: string[],
  contextLines: number
): DiffLine[] {
  const edits = myersDiff(linesA, linesB);

  // First pass: assign line numbers
  interface RawLine {
    kind: "equal" | "insert" | "delete";
    line: string;
    lineNumberA?: number;
    lineNumberB?: number;
  }

  const raw: RawLine[] = [];
  let lineA = 1;
  let lineB = 1;

  for (const edit of edits) {
    if (edit.kind === "equal") {
      raw.push({ kind: "equal", line: edit.line, lineNumberA: lineA, lineNumberB: lineB });
      lineA++;
      lineB++;
    } else if (edit.kind === "delete") {
      raw.push({ kind: "delete", line: edit.line, lineNumberA: lineA });
      lineA++;
    } else {
      raw.push({ kind: "insert", line: edit.line, lineNumberB: lineB });
      lineB++;
    }
  }

  // Second pass: find changed indices for context culling
  const changedIdx = new Set<number>();
  for (let i = 0; i < raw.length; i++) {
    if (raw[i].kind !== "equal") changedIdx.add(i);
  }

  // Expand context window around changed lines
  const included = new Set<number>();
  for (const idx of changedIdx) {
    for (let j = Math.max(0, idx - contextLines); j <= Math.min(raw.length - 1, idx + contextLines); j++) {
      included.add(j);
    }
  }

  // Third pass: build DiffLine array with chunk headers
  const result: DiffLine[] = [];
  let prevIncluded = false;

  for (let i = 0; i < raw.length; i++) {
    if (!included.has(i)) {
      prevIncluded = false;
      continue;
    }

    if (!prevIncluded && result.length > 0) {
      // Insert chunk header
      const r = raw[i];
      const aStart = r.lineNumberA ?? "?";
      const bStart = r.lineNumberB ?? "?";
      result.push({
        kind: "chunk-header",
        content: `@@ −${aStart} +${bStart} @@`,
      });
    }
    prevIncluded = true;

    const r = raw[i];
    result.push({
      kind: r.kind === "equal" ? "context" : r.kind === "insert" ? "added" : "removed",
      content: r.line,
      lineNumberA: r.lineNumberA,
      lineNumberB: r.lineNumberB,
    });
  }

  return result;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface DiffLineRowProps {
  line: DiffLine;
  showLineNumbers: boolean;
}

function DiffLineRow({ line, showLineNumbers }: DiffLineRowProps) {
  const bg = LINE_BG[line.kind];
  const textColor = LINE_TEXT[line.kind];
  const sigil = LINE_SIGIL[line.kind];

  if (line.kind === "chunk-header") {
    return (
      <div
        className="flex items-center px-3 py-0.5 select-none"
        style={{ backgroundColor: bg }}
        aria-hidden
      >
        <span
          className="text-xs"
          style={{
            color: textColor,
            fontFamily: "var(--font-jetbrains-mono)",
            opacity: 0.75,
          }}
        >
          {line.content}
        </span>
      </div>
    );
  }

  return (
    <div
      className="flex items-start gap-0"
      style={{ backgroundColor: bg }}
      role="row"
    >
      {/* Line numbers */}
      {showLineNumbers && (
        <>
          <span
            className="w-9 shrink-0 text-right pr-2 py-0.5 select-none text-[11px] tabular-nums"
            style={{
              color: "#3A2E10",
              fontFamily: "var(--font-jetbrains-mono)",
              userSelect: "none",
            }}
            aria-hidden
          >
            {line.lineNumberA ?? ""}
          </span>
          <span
            className="w-9 shrink-0 text-right pr-2 py-0.5 select-none text-[11px] tabular-nums"
            style={{
              color: "#3A2E10",
              fontFamily: "var(--font-jetbrains-mono)",
              userSelect: "none",
            }}
            aria-hidden
          >
            {line.lineNumberB ?? ""}
          </span>
        </>
      )}

      {/* Sigil */}
      <span
        className="w-4 shrink-0 text-center py-0.5 select-none text-[11px] font-bold"
        style={{
          color: textColor,
          fontFamily: "var(--font-jetbrains-mono)",
          userSelect: "none",
          opacity: line.kind === "context" ? 0.3 : 1,
        }}
        aria-hidden
      >
        {sigil}
      </span>

      {/* Content */}
      <span
        className="flex-1 py-0.5 pr-3 text-[11px] leading-relaxed whitespace-pre-wrap break-all"
        style={{
          color: textColor,
          fontFamily: "var(--font-jetbrains-mono)",
        }}
      >
        {line.content || " "}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProofDiff
// ---------------------------------------------------------------------------

/**
 * ProofDiff — monospace unified diff view for proof/spec text between two runs.
 *
 * Renders in JetBrains Mono with:
 * - Added lines: faint amber (#D4920A) background
 * - Removed lines: faint warm red (#C84B2F) background
 * - Context lines: transparent
 * - Chunk headers: dim amber tint
 *
 * If the texts are identical, renders a "No differences" message.
 */
export function ProofDiff({
  proofTextA,
  proofTextB,
  contextLines = 3,
  filename,
  className,
}: ProofDiffProps) {
  const diffLines = useMemo(() => {
    const linesA = proofTextA.split("\n");
    const linesB = proofTextB.split("\n");
    return buildDiffLines(linesA, linesB, contextLines);
  }, [proofTextA, proofTextB, contextLines]);

  const hasChanges = useMemo(
    () => diffLines.some((l) => l.kind === "added" || l.kind === "removed"),
    [diffLines]
  );

  const addedCount = useMemo(
    () => diffLines.filter((l) => l.kind === "added").length,
    [diffLines]
  );
  const removedCount = useMemo(
    () => diffLines.filter((l) => l.kind === "removed").length,
    [diffLines]
  );

  return (
    <div
      className={cn("flex flex-col w-full overflow-hidden rounded", className)}
      style={{
        backgroundColor: "#0D0B09",
        border: "1px solid #2A2315",
      }}
      role="region"
      aria-label={filename ? `Proof diff: ${filename}` : "Proof diff"}
    >
      {/* Header bar */}
      <div
        className="flex items-center justify-between px-3 py-2 gap-2"
        style={{ borderBottom: "1px solid #2A2315", backgroundColor: "#141109" }}
      >
        {/* Filename */}
        <span
          className="text-xs font-medium truncate"
          style={{
            color: "#8B8579",
            fontFamily: "var(--font-jetbrains-mono)",
            maxWidth: "60%",
          }}
        >
          {filename ?? "proof.dfy"}
        </span>

        {/* Change stats */}
        <div className="flex items-center gap-3 shrink-0">
          {hasChanges ? (
            <>
              <span
                className="text-[11px] font-semibold tabular-nums"
                style={{ color: "#D4920A", fontFamily: "var(--font-jetbrains-mono)" }}
                aria-label={`${addedCount} lines added`}
              >
                +{addedCount}
              </span>
              <span
                className="text-[11px] font-semibold tabular-nums"
                style={{ color: "#C84B2F", fontFamily: "var(--font-jetbrains-mono)" }}
                aria-label={`${removedCount} lines removed`}
              >
                −{removedCount}
              </span>
            </>
          ) : (
            <span
              className="text-[11px]"
              style={{ color: "#3A2E10", fontFamily: "var(--font-jetbrains-mono)" }}
            >
              no changes
            </span>
          )}
        </div>
      </div>

      {/* Diff body */}
      {hasChanges ? (
        <div
          className="overflow-x-auto overflow-y-auto"
          style={{ maxHeight: "32rem" }}
          role="table"
          aria-label="Diff lines"
        >
          <div className="min-w-0">
            {diffLines.map((line, idx) => (
              <DiffLineRow
                key={idx}
                line={line}
                showLineNumbers
              />
            ))}
          </div>
        </div>
      ) : (
        <div
          className="flex items-center justify-center py-8"
          style={{
            color: "#6E6860",
            fontFamily: "var(--font-jetbrains-mono)",
            fontSize: "0.75rem",
          }}
          aria-label="No differences between runs"
        >
          No differences between runs
        </div>
      )}
    </div>
  );
}
