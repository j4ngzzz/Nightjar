"use client";

/**
 * Nightjar Verification Canvas — Stage Node Component
 *
 * Custom React Flow node for a single pipeline stage.
 * 200×110px. Amber palette — no purple/violet/green.
 *
 * Visual spec:
 * - Top row:    Lucide icon + stage name (JetBrains Mono, uppercase, #9A8E78)
 * - Middle:     status ring (animated for Running, static glow for terminal)
 * - Bottom-left: duration badge (#D4920A)
 * - Bottom-right: findings count badge
 *
 * Animation: crystallize entry (trembling snap) via motion/react.
 * Running state: pulsing amber ring via CSS keyframes.
 */

import { memo, useMemo, useCallback } from "react";
import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { motion } from "motion/react";
import {
  Shield,
  Package,
  Database,
  FlaskConical,
  Sigma,
  BookOpen,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/cn";
import {
  type StageState,
  STATE_COLORS,
  crystallizeVariants,
  staggerDelay,
  amberPulseRingVariants,
  provenRingVariants,
} from "./crystallization";

// ---------------------------------------------------------------------------
// Stage definitions
// ---------------------------------------------------------------------------

export type StageName =
  | "preflight"
  | "deps"
  | "schema"
  | "pbt"
  | "negation"
  | "formal";

const STAGE_META: Record<
  StageName,
  { label: string; icon: LucideIcon; index: number }
> = {
  preflight: { label: "PREFLIGHT", icon: Shield, index: 0 },
  deps: { label: "DEPS", icon: Package, index: 1 },
  schema: { label: "SCHEMA", icon: Database, index: 2 },
  pbt: { label: "PBT", icon: FlaskConical, index: 3 },
  negation: { label: "NEGATION", icon: Sigma, index: 4 },
  formal: { label: "FORMAL", icon: BookOpen, index: 5 },
};

/** Human-readable status labels for screen readers — module-scoped constant. */
const STATUS_ARIA_LABELS: Record<StageState, string> = {
  pending: "pending",
  running: "running",
  pbt_pass: "PBT pass",
  formal_pass: "formal pass",
  proven: "proven",
  failed: "failed",
};

// ---------------------------------------------------------------------------
// Node data shape
// ---------------------------------------------------------------------------

export interface StageNodeData extends Record<string, unknown> {
  /** Which pipeline stage this node represents */
  stage: StageName;
  /** Current proof state */
  state: StageState;
  /** Elapsed time string, e.g. "1.2s" */
  duration?: string;
  /** Number of findings/violations discovered */
  findings?: number;
  /** Called when this node is clicked (used by Formal node to open ProofTree) */
  onClick?: (stage: StageName, state: StageState) => void;
}

// ---------------------------------------------------------------------------
// Status ring sub-component
// ---------------------------------------------------------------------------

interface StatusRingProps {
  state: StageState;
}

function StatusRing({ state }: StatusRingProps) {
  const colors = STATE_COLORS[state];

  if (state === "running") {
    return (
      <div className="relative flex items-center justify-center w-8 h-8">
        {/* Pulsing outer ring */}
        <motion.div
          className="absolute inset-0 rounded-full border-2"
          style={{ borderColor: colors.border }}
          variants={amberPulseRingVariants}
          initial="idle"
          animate="pulse"
        />
        {/* Inner dot */}
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: "#D4920A" }}
        />
      </div>
    );
  }

  if (state === "proven") {
    return (
      <div className="relative flex items-center justify-center w-8 h-8">
        {/* One-shot expanding ring */}
        <motion.div
          className="absolute inset-0 rounded-full border-2"
          style={{ borderColor: colors.border }}
          variants={provenRingVariants}
          initial="hidden"
          animate="burst"
        />
        {/* Solid gold dot */}
        <div
          className="w-3 h-3 rounded-full"
          style={{
            backgroundColor: colors.border,
            boxShadow: `0 0 8px ${colors.border}`,
          }}
        />
      </div>
    );
  }

  if (state === "pending") {
    return (
      <div className="relative flex items-center justify-center w-8 h-8">
        <div
          className="w-3 h-3 rounded-full border"
          style={{ borderColor: colors.border, backgroundColor: "transparent" }}
        />
      </div>
    );
  }

  if (state === "failed") {
    return (
      <div className="relative flex items-center justify-center w-8 h-8">
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: "#C84B2F", opacity: 0.8 }}
        />
      </div>
    );
  }

  // pbt_pass or formal_pass
  return (
    <div className="relative flex items-center justify-center w-8 h-8">
      <div
        className="w-3 h-3 rounded-full"
        style={{
          backgroundColor: colors.border,
          boxShadow: colors.glow
            ? `0 0 6px ${colors.border}`
            : undefined,
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// StageNode
// ---------------------------------------------------------------------------

function StageNodeInner({ data, selected }: NodeProps<Node<StageNodeData>>) {
  const { stage, state, duration, findings, onClick } = data as StageNodeData;
  const meta = STAGE_META[stage as StageName];
  const colors = STATE_COLORS[state as StageState];
  const Icon = meta.icon;
  const staggerIndex = meta.index;

  const handleClick = useMemo(
    () =>
      onClick
        ? () => onClick(stage, state)
        : undefined,
    [onClick, stage, state]
  );

  // Keyboard handler: Enter or Space activates the node (same as click)
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if ((e.key === "Enter" || e.key === " ") && onClick) {
        e.preventDefault();
        onClick(stage, state);
      }
    },
    [onClick, stage, state]
  );

  const borderStyle = useMemo(() => {
    const base = {
      borderColor: colors.border,
      backgroundColor: `rgba(${hexToRgb(colors.fill)}, ${colors.fillOpacity})`,
      boxShadow: colors.glow ?? "none",
    };
    if (selected) {
      return { ...base, boxShadow: `0 0 0 2px ${colors.border}, ${colors.glow ?? "none"}` };
    }
    return base;
  }, [colors, selected]);

  return (
    <motion.div
      variants={crystallizeVariants}
      initial="hidden"
      animate="visible"
      transition={{ delay: staggerDelay(staggerIndex) }}
      style={{ width: 200, height: 110 }}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role={onClick ? "button" : undefined}
      aria-label={`Stage: ${meta.label}, status: ${STATUS_ARIA_LABELS[state as StageState]}`}
      tabIndex={onClick ? 0 : undefined}
      className={cn(
        "relative flex flex-col rounded-lg cursor-default select-none",
        "transition-shadow duration-300",
        onClick && "cursor-pointer",
        // Amber focus ring — only visible on keyboard focus, not mouse click
        onClick && "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4920A] focus-visible:ring-offset-2 focus-visible:ring-offset-[#0D0B09]"
      )}
      // Override motion style with dynamic border + fill
      // (motion.div merges style prop with its own)
    >
      {/* Inner wrapper with border/fill colors */}
      <div
        className="absolute inset-0 rounded-lg border"
        style={borderStyle}
        aria-hidden
      />

      {/* Content sits above the border overlay */}
      <div
        className="relative flex flex-col h-full px-3 py-2.5 gap-1.5"
      >
        {/* TOP ROW: icon + stage name */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <Icon
            size={14}
            color={colors.text}
            strokeWidth={1.5}
            aria-hidden
          />
          <span
            className="text-[10px] font-semibold tracking-widest"
            style={{
              fontFamily: "var(--font-jetbrains-mono)",
              color: "#9A8E78",
              letterSpacing: "0.12em",
            }}
          >
            {meta.label}
          </span>
        </div>

        {/* MIDDLE: status ring */}
        <div className="flex items-center justify-center flex-1">
          <StatusRing state={state} />
        </div>

        {/* BOTTOM ROW: duration badge + findings badge */}
        <div className="flex items-center justify-between flex-shrink-0">
          {/* Duration badge */}
          <span
            className="text-[9px] font-medium px-1.5 py-0.5 rounded"
            style={{
              fontFamily: "var(--font-jetbrains-mono)",
              color: duration ? "#D4920A" : "#3A2E10",
              backgroundColor: duration
                ? "rgba(212,146,10,0.12)"
                : "transparent",
            }}
          >
            {duration ?? "—"}
          </span>

          {/* Findings badge */}
          {findings !== undefined && findings > 0 ? (
            <span
              className="text-[9px] font-medium px-1.5 py-0.5 rounded"
              style={{
                fontFamily: "var(--font-jetbrains-mono)",
                color: state === "failed" ? "#C84B2F" : "#A87020",
                backgroundColor:
                  state === "failed"
                    ? "rgba(200,75,47,0.15)"
                    : "rgba(168,112,32,0.15)",
              }}
            >
              {findings} {findings === 1 ? "finding" : "findings"}
            </span>
          ) : (
            <span
              className="text-[9px]"
              style={{
                fontFamily: "var(--font-jetbrains-mono)",
                color: "#3A2E10",
              }}
            >
              {findings === 0 ? "0 findings" : ""}
            </span>
          )}
        </div>
      </div>

      {/* React Flow connection handles (hidden visually) */}
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: colors.border,
          border: "none",
          width: 8,
          height: 8,
          opacity: 0,
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: colors.border,
          border: "none",
          width: 8,
          height: 8,
          opacity: 0,
        }}
      />
    </motion.div>
  );
}

export const StageNode = memo(StageNodeInner);
StageNode.displayName = "StageNode";

// ---------------------------------------------------------------------------
// Helper: hex to "r, g, b" string for rgba()
// ---------------------------------------------------------------------------

function hexToRgb(hex: string): string {
  const clean = hex.replace(/^#/, "");
  const num = parseInt(clean.length === 3
    ? clean.split("").map((c) => c + c).join("")
    : clean, 16);
  const r = (num >> 16) & 255;
  const g = (num >> 8) & 255;
  const b = num & 255;
  return `${r}, ${g}, ${b}`;
}
