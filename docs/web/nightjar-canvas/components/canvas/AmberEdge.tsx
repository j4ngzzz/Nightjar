"use client";

/**
 * Nightjar Verification Canvas — Amber Edge Components
 *
 * Three edge variants:
 * 1. AmberParticleEdge  — running: 3 staggered SVG animateMotion dots
 * 2. AmberCompletedEdge — solid gold gradient line when upstream complete
 * 3. BlockedEdge        — dashed dark line when downstream of failure
 *
 * All use @xyflow/react BaseEdge + getBezierPath.
 * SVG animateMotion is used directly (no external animation lib needed for edges).
 */

import { memo } from "react";
import {
  BaseEdge,
  getBezierPath,
  type EdgeProps,
} from "@xyflow/react";

// ---------------------------------------------------------------------------
// Shared path helper
// ---------------------------------------------------------------------------

function useEdgePath(props: EdgeProps) {
  const {
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  } = props;

  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return edgePath;
}

// ---------------------------------------------------------------------------
// 1. AmberParticleEdge — active / running
//    3 SVG circles staggered along the path via animateMotion
// ---------------------------------------------------------------------------

function AmberParticleEdgeInner(props: EdgeProps) {
  const { id, markerEnd, style } = props;
  const edgePath = useEdgePath(props);
  const pathId = `particle-path-${id}`;

  const particles = [
    { delay: "0s", color: "#D4920A" },
    { delay: "0.65s", color: "#E0A830" },
    { delay: "1.3s", color: "#F5B93A" },
  ];

  return (
    <g>
      {/* Base path — dim amber line */}
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: "#3A2E10",
          strokeWidth: 2,
          ...style,
        }}
      />

      {/* Hidden path element for animateMotion reference */}
      <path id={pathId} d={edgePath} fill="none" stroke="none" />

      {/* 3 staggered amber particles */}
      {particles.map((p, i) => (
        <circle key={i} r={4} fill={p.color} opacity={0.9}>
          <animateMotion
            dur="2s"
            begin={p.delay}
            repeatCount="indefinite"
            rotate="auto"
          >
            <mpath href={`#${pathId}`} />
          </animateMotion>
        </circle>
      ))}
    </g>
  );
}

export const AmberParticleEdge = memo(AmberParticleEdgeInner);
AmberParticleEdge.displayName = "AmberParticleEdge";

// ---------------------------------------------------------------------------
// 2. AmberCompletedEdge — solid gold gradient when upstream complete
// ---------------------------------------------------------------------------

function AmberCompletedEdgeInner(props: EdgeProps) {
  const { id, markerEnd, style } = props;
  const edgePath = useEdgePath(props);
  const gradientId = `amber-grad-${id}`;

  const {
    sourceX,
    sourceY,
    targetX,
    targetY,
  } = props;

  return (
    <g>
      {/* SVG gradient definition */}
      <defs>
        <linearGradient
          id={gradientId}
          x1={sourceX}
          y1={sourceY}
          x2={targetX}
          y2={targetY}
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0%" stopColor="#A87020" />
          <stop offset="50%" stopColor="#D4920A" />
          <stop offset="100%" stopColor="#F5B93A" />
        </linearGradient>
      </defs>

      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: `url(#${gradientId})`,
          strokeWidth: 2,
          ...style,
        }}
      />
    </g>
  );
}

export const AmberCompletedEdge = memo(AmberCompletedEdgeInner);
AmberCompletedEdge.displayName = "AmberCompletedEdge";

// ---------------------------------------------------------------------------
// 3. BlockedEdge — dashed dark line when downstream of failure
// ---------------------------------------------------------------------------

function BlockedEdgeInner(props: EdgeProps) {
  const { id, markerEnd, style } = props;
  const edgePath = useEdgePath(props);

  return (
    <BaseEdge
      id={id}
      path={edgePath}
      markerEnd={markerEnd}
      style={{
        stroke: "#2A2315",
        strokeWidth: 1.5,
        strokeDasharray: "6 4",
        opacity: 0.3,
        ...style,
      }}
    />
  );
}

export const BlockedEdge = memo(BlockedEdgeInner);
BlockedEdge.displayName = "BlockedEdge";

// ---------------------------------------------------------------------------
// Edge type registry — export for use in edgeTypes map
// ---------------------------------------------------------------------------

export const amberEdgeTypes = {
  amberParticle: AmberParticleEdge,
  amberCompleted: AmberCompletedEdge,
  blocked: BlockedEdge,
} as const;

export type AmberEdgeType = keyof typeof amberEdgeTypes;
