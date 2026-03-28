"use client";

/**
 * Nightjar Verification Canvas — Main React Flow Pipeline Wrapper
 *
 * Renders the 6-stage verification pipeline as a horizontal DAG:
 *   Preflight → Deps → Schema → PBT → Negation → Formal
 *
 * Features:
 * - ElkJS layered layout (RIGHT direction, NETWORK_SIMPLEX placement)
 * - Crystallization entry animation with 60ms topological stagger
 * - AmberEdge variants (particle / completed / blocked) driven by stage state
 * - ProofTreeCanvas expands below when Formal node is clicked in passed state
 * - Pannable + zoomable
 * - All amber palette — no purple/violet/green
 *
 * IMPORTANT: nodeTypes and edgeTypes are declared OUTSIDE the component
 * to prevent React Flow from re-registering types on every render.
 */

import "@xyflow/react/dist/style.css";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
} from "@xyflow/react";

import { StageNode, type StageNodeData, type StageName } from "./StageNode";
import {
  AmberParticleEdge,
  AmberCompletedEdge,
  BlockedEdge,
  type AmberEdgeType,
} from "./AmberEdge";
import { ProofTreeCanvas } from "./ProofTreeCanvas";
import { applyElkLayout, buildFallbackPositions, NODE_WIDTH, NODE_HEIGHT } from "./elkLayout";
import {
  type StageState,
  deriveEdgeVariant,
} from "./crystallization";

// ---------------------------------------------------------------------------
// nodeTypes + edgeTypes — MUST be outside component (React Flow requirement)
// ---------------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const nodeTypes: NodeTypes = {
  stage: StageNode as any,
};

const edgeTypes = {
  amberParticle: AmberParticleEdge,
  amberCompleted: AmberCompletedEdge,
  blocked: BlockedEdge,
} as const;

// ---------------------------------------------------------------------------
// Pipeline definition
// ---------------------------------------------------------------------------

const PIPELINE_STAGES: StageName[] = [
  "preflight",
  "deps",
  "schema",
  "pbt",
  "negation",
  "formal",
];

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface StageStateMap {
  preflight?: StageState;
  deps?: StageState;
  schema?: StageState;
  pbt?: StageState;
  negation?: StageState;
  formal?: StageState;
}

export interface StageDurationMap {
  preflight?: string;
  deps?: string;
  schema?: string;
  pbt?: string;
  negation?: string;
  formal?: string;
}

export interface StageFindingsMap {
  preflight?: number;
  deps?: number;
  schema?: number;
  pbt?: number;
  negation?: number;
  formal?: number;
}

export interface VerificationCanvasProps {
  /** Per-stage proof states. Defaults to all "pending". */
  stateMap?: StageStateMap;
  /** Per-stage elapsed duration strings */
  durationMap?: StageDurationMap;
  /** Per-stage findings counts */
  findingsMap?: StageFindingsMap;
  /** Canvas height (default: 280px) */
  height?: number;
}

// ---------------------------------------------------------------------------
// Helpers — build nodes + edges from state
// ---------------------------------------------------------------------------

function buildNodes(
  stateMap: StageStateMap,
  durationMap: StageDurationMap,
  findingsMap: StageFindingsMap,
  onNodeClick: (stage: StageName, state: StageState) => void
): Node<StageNodeData>[] {
  return PIPELINE_STAGES.map((stage, i) => ({
    id: stage,
    type: "stage",
    position: { x: i * (NODE_WIDTH + 80), y: 0 }, // fallback; ELK overwrites
    data: {
      stage,
      state: stateMap[stage] ?? "pending",
      duration: durationMap[stage],
      findings: findingsMap[stage],
      onClick: onNodeClick,
    },
    width: NODE_WIDTH,
    height: NODE_HEIGHT,
  }));
}

function buildEdges(stateMap: StageStateMap): Edge[] {
  const edges: Edge[] = [];
  for (let i = 0; i < PIPELINE_STAGES.length - 1; i++) {
    const sourceStage = PIPELINE_STAGES[i];
    const targetStage = PIPELINE_STAGES[i + 1];
    const sourceState = stateMap[sourceStage] ?? "pending";
    const targetState = stateMap[targetStage] ?? "pending";
    const variant: AmberEdgeType = deriveEdgeVariant(sourceState, targetState);

    edges.push({
      id: `e-${sourceStage}-${targetStage}`,
      source: sourceStage,
      target: targetStage,
      type: variant,
    });
  }
  return edges;
}

// ---------------------------------------------------------------------------
// VerificationCanvas
// ---------------------------------------------------------------------------

export function VerificationCanvas({
  stateMap = {},
  durationMap = {},
  findingsMap = {},
  height = 280,
}: VerificationCanvasProps) {
  const [proofTreeVisible, setProofTreeVisible] = useState(false);

  // Node click handler — memoized, stable reference
  const handleNodeClick = useCallback(
    (stage: StageName, state: StageState) => {
      if (stage === "formal" && (state === "formal_pass" || state === "proven")) {
        setProofTreeVisible((v) => !v);
      }
    },
    []
  );

  // Build initial nodes + edges from prop state
  const rawNodes = useMemo(
    () => buildNodes(stateMap, durationMap, findingsMap, handleNodeClick),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(stateMap), JSON.stringify(durationMap), JSON.stringify(findingsMap), handleNodeClick]
  );

  const rawEdges = useMemo(
    () => buildEdges(stateMap),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(stateMap)]
  );

  // Apply fallback positions immediately (synchronous), then ELK layout async
  const [nodes, setNodes, onNodesChange] = useNodesState(
    buildFallbackPositions(rawNodes)
  );
  const [edges, setEdges, onEdgesChange] = useEdgesState(rawEdges);

  // Re-run ELK layout whenever state map changes
  useEffect(() => {
    const nodesWithFallback = buildFallbackPositions(rawNodes);
    setEdges(rawEdges);

    applyElkLayout(nodesWithFallback, rawEdges)
      .then((layouted) => setNodes(layouted))
      .catch(() => {
        // ELK unavailable (SSR / bundler issue) — keep fallback positions
        setNodes(nodesWithFallback);
      });
  }, [rawNodes, rawEdges, setNodes, setEdges]);

  const handleCloseProofTree = useCallback(() => {
    setProofTreeVisible(false);
  }, []);

  return (
    <div className="flex flex-col gap-3 w-full">
      {/* Main pipeline canvas */}
      <div
        className="w-full rounded-lg overflow-hidden border"
        style={{
          height,
          borderColor: "#2A2315",
          backgroundColor: "#0D0B09",
        }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          fitViewOptions={{ padding: 0.2, maxZoom: 1.2 }}
          nodesDraggable={false}
          nodesConnectable={false}
          proOptions={{ hideAttribution: true }}
          style={{ backgroundColor: "#0D0B09" }}
        >
          <Background
            variant={BackgroundVariant.Dots}
            color="#1E1A10"
            gap={20}
            size={1}
          />
          <Controls
            showInteractive={false}
            style={{
              backgroundColor: "#141109",
              border: "1px solid #2A2315",
              borderRadius: "6px",
            }}
          />
          <MiniMap
            nodeColor={(node) => {
              const data = node.data as StageNodeData;
              const state: StageState = data.state ?? "pending";
              const stateColorMap: Record<StageState, string> = {
                pending: "#3A2E10",
                running: "#D4920A",
                pbt_pass: "#A87020",
                formal_pass: "#F5B93A",
                proven: "#FFD060",
                failed: "#C84B2F",
              };
              return stateColorMap[state];
            }}
            maskColor="rgba(13, 11, 9, 0.7)"
            style={{
              backgroundColor: "#141109",
              border: "1px solid #2A2315",
              borderRadius: "6px",
            }}
          />
        </ReactFlow>
      </div>

      {/* ProofTreeCanvas — expands below on Formal node click */}
      <ProofTreeCanvas
        visible={proofTreeVisible}
        onClose={handleCloseProofTree}
      />
    </div>
  );
}
