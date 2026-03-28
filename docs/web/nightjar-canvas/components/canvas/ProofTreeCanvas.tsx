"use client";

/**
 * Nightjar Verification Canvas — Proof Tree Canvas
 *
 * Secondary React Flow canvas that appears below the main pipeline
 * when the Formal stage node is clicked in a passed state.
 *
 * Renders Dafny proof obligations as a tree of nodes:
 * - Root: the top-level lemma / method being verified
 * - Branches: preconditions, postconditions, loop invariants
 * - Leaves: atomic SMT calls (sat/unsat)
 *
 * Visual: Background variant="dots", color="#2A2315"
 * Entry: crystallize animation with shorter stagger (20ms)
 */

import { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import { motion, AnimatePresence } from "motion/react";
import { X } from "lucide-react";

import { crystallizeVariants, EASE_CRYSTALLIZE } from "./crystallization";

// ---------------------------------------------------------------------------
// Proof node data
// ---------------------------------------------------------------------------

export interface ProofNodeData extends Record<string, unknown> {
  label: string;
  kind: "lemma" | "precondition" | "postcondition" | "invariant" | "smt";
  status: "verified" | "unknown" | "failed";
}

// ---------------------------------------------------------------------------
// Proof node kind → amber shade
// ---------------------------------------------------------------------------

const KIND_COLORS: Record<ProofNodeData["kind"], string> = {
  lemma: "#FFD060",
  precondition: "#F5B93A",
  postcondition: "#D4920A",
  invariant: "#A87020",
  smt: "#6E4E1A",
};

const STATUS_BORDER: Record<ProofNodeData["status"], string> = {
  verified: "#A87020",
  unknown: "#3A2E10",
  failed: "#C84B2F",
};

// ---------------------------------------------------------------------------
// ProofTreeNode — custom node for proof items
// ---------------------------------------------------------------------------

function ProofTreeNode({ data }: NodeProps<Node<ProofNodeData>>) {
  const { kind, status, label } = data as ProofNodeData;
  const accentColor = KIND_COLORS[kind];
  const borderColor = STATUS_BORDER[status];

  return (
    <motion.div
      variants={crystallizeVariants}
      initial="hidden"
      animate="visible"
      className="rounded-md border px-3 py-2 text-left"
      style={{
        borderColor,
        backgroundColor: `rgba(20, 17, 9, 0.95)`,
        minWidth: 140,
        maxWidth: 220,
      }}
    >
      <div
        className="text-[9px] uppercase tracking-widest mb-1"
        style={{
          fontFamily: "var(--font-jetbrains-mono)",
          color: accentColor,
          letterSpacing: "0.1em",
        }}
      >
        {kind}
      </div>
      <div
        className="text-[11px] font-medium leading-snug"
        style={{
          fontFamily: "var(--font-jetbrains-mono)",
          color:
            status === "failed"
              ? "#C84B2F"
              : status === "verified"
              ? "#F0EBE3"
              : "#8B8579",
        }}
      >
        {label}
      </div>
    </motion.div>
  );
}

const proofNodeTypes = {
  proofNode: ProofTreeNode,
};

// ---------------------------------------------------------------------------
// Default demo tree (shown when no real proof data is available)
// ---------------------------------------------------------------------------

function buildDemoTree(): { nodes: Node<ProofNodeData>[]; edges: Edge[] } {
  const nodes: Node<ProofNodeData>[] = [
    {
      id: "root",
      type: "proofNode",
      position: { x: 0, y: 0 },
      data: {
        label: "verify_payment_amount",
        kind: "lemma",
        status: "verified",
      },
    },
    {
      id: "pre1",
      type: "proofNode",
      position: { x: -200, y: 130 },
      data: {
        label: "amount > 0",
        kind: "precondition",
        status: "verified",
      },
    },
    {
      id: "pre2",
      type: "proofNode",
      position: { x: 0, y: 130 },
      data: {
        label: "currency != null",
        kind: "precondition",
        status: "verified",
      },
    },
    {
      id: "post1",
      type: "proofNode",
      position: { x: 200, y: 130 },
      data: {
        label: "result.status == OK",
        kind: "postcondition",
        status: "verified",
      },
    },
    {
      id: "inv1",
      type: "proofNode",
      position: { x: -300, y: 270 },
      data: {
        label: "0 <= i <= |ledger|",
        kind: "invariant",
        status: "verified",
      },
    },
    {
      id: "smt1",
      type: "proofNode",
      position: { x: -100, y: 270 },
      data: {
        label: "z3: unsat (safe)",
        kind: "smt",
        status: "verified",
      },
    },
    {
      id: "smt2",
      type: "proofNode",
      position: { x: 120, y: 270 },
      data: {
        label: "z3: unsat (safe)",
        kind: "smt",
        status: "verified",
      },
    },
  ];

  const edges: Edge[] = [
    { id: "e-root-pre1", source: "root", target: "pre1" },
    { id: "e-root-pre2", source: "root", target: "pre2" },
    { id: "e-root-post1", source: "root", target: "post1" },
    { id: "e-pre1-inv1", source: "pre1", target: "inv1" },
    { id: "e-pre1-smt1", source: "pre1", target: "smt1" },
    { id: "e-post1-smt2", source: "post1", target: "smt2" },
  ];

  return { nodes, edges };
}

// ---------------------------------------------------------------------------
// ProofTreeCanvas
// ---------------------------------------------------------------------------

export interface ProofTreeCanvasProps {
  /** Proof nodes to render. Falls back to demo tree if not provided. */
  nodes?: Node<ProofNodeData>[];
  /** Proof edges to render. Falls back to demo tree if not provided. */
  edges?: Edge[];
  /** Called when user dismisses the proof panel */
  onClose: () => void;
  /** Whether the panel is visible */
  visible: boolean;
}

export function ProofTreeCanvas({
  nodes: propNodes,
  edges: propEdges,
  onClose,
  visible,
}: ProofTreeCanvasProps) {
  const demo = useMemo(() => buildDemoTree(), []);
  const initialNodes = propNodes ?? demo.nodes;
  const initialEdges = propEdges ?? demo.edges;

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  const handleClose = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onClose();
    },
    [onClose]
  );

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="proof-tree"
          initial={{ opacity: 0, height: 0 }}
          animate={{
            opacity: 1,
            height: 320,
            transition: {
              duration: 0.25,
              ease: EASE_CRYSTALLIZE,
            },
          }}
          exit={{
            opacity: 0,
            height: 0,
            transition: { duration: 0.18, ease: "easeIn" },
          }}
          className="w-full overflow-hidden border rounded-lg"
          style={{
            borderColor: "#2A2315",
            backgroundColor: "#0D0B09",
          }}
        >
          {/* Header bar */}
          <div
            className="flex items-center justify-between px-4 py-2 border-b"
            style={{ borderColor: "#2A2315" }}
          >
            <span
              className="text-[10px] uppercase tracking-widest"
              style={{
                fontFamily: "var(--font-jetbrains-mono)",
                color: "#F5B93A",
                letterSpacing: "0.12em",
              }}
            >
              Dafny Proof Tree
            </span>
            <button
              onClick={handleClose}
              className="p-1 rounded transition-opacity hover:opacity-70"
              style={{ color: "#8B8579" }}
              aria-label="Close proof tree"
            >
              <X size={14} />
            </button>
          </div>

          {/* React Flow proof canvas */}
          <div style={{ height: "calc(320px - 37px)" }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={proofNodeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              fitView
              fitViewOptions={{ padding: 0.3 }}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
              defaultEdgeOptions={{
                style: {
                  stroke: "#3A2E10",
                  strokeWidth: 1.5,
                },
              }}
              proOptions={{ hideAttribution: true }}
            >
              <Background
                variant={BackgroundVariant.Dots}
                color="#2A2315"
                gap={18}
                size={1}
              />
              <Controls
                showInteractive={false}
                style={{
                  backgroundColor: "#141109",
                  border: "1px solid #2A2315",
                }}
              />
            </ReactFlow>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
