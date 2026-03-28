/**
 * Nightjar Verification Canvas — ElkJS Layered Layout Utility
 *
 * Applies ELK's layered algorithm to a React Flow node/edge set,
 * returning new nodes with computed (x, y) positions.
 *
 * Import note: use elk.bundled.js to avoid Web Worker issues in Next.js.
 * The import path 'elkjs/lib/elk.bundled.js' bundles the algorithm
 * inline without requiring a separate worker file.
 */

import ELK from "elkjs/lib/elk.bundled.js";
import type { Node, Edge } from "@xyflow/react";

// ---------------------------------------------------------------------------
// ELK layout options — Nightjar pipeline defaults
// ---------------------------------------------------------------------------

const NIGHTJAR_ELK_OPTIONS: Record<string, string> = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.layered.spacing.nodeNodeBetweenLayers": "80",
  "elk.spacing.nodeNode": "60",
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  "elk.edgeRouting": "SPLINES",
};

// ---------------------------------------------------------------------------
// Node dimensions — must match StageNode visual spec
// ---------------------------------------------------------------------------

export const NODE_WIDTH = 200;
export const NODE_HEIGHT = 110;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ElkNode {
  id: string;
  width: number;
  height: number;
  x?: number;
  y?: number;
}

interface ElkEdge {
  id: string;
  sources: string[];
  targets: string[];
}

interface ElkGraph {
  id: string;
  layoutOptions: Record<string, string>;
  children: ElkNode[];
  edges: ElkEdge[];
}

// ---------------------------------------------------------------------------
// Layout function
// ---------------------------------------------------------------------------

const elk = new ELK();

/**
 * Apply ELK layered layout to React Flow nodes and edges.
 *
 * @param nodes - React Flow nodes (positions will be recomputed)
 * @param edges - React Flow edges (topology only; routing ignored)
 * @param options - Override ELK layout options (merged with defaults)
 * @returns New array of nodes with updated `position` values
 */
export async function applyElkLayout<NodeData extends Record<string, unknown>>(
  nodes: Node<NodeData>[],
  edges: Edge[],
  options: Record<string, string> = {}
): Promise<Node<NodeData>[]> {
  if (nodes.length === 0) return nodes;

  const layoutOptions = { ...NIGHTJAR_ELK_OPTIONS, ...options };

  const graph: ElkGraph = {
    id: "nightjar-pipeline",
    layoutOptions,
    children: nodes.map((node) => ({
      id: node.id,
      width: node.measured?.width ?? NODE_WIDTH,
      height: node.measured?.height ?? NODE_HEIGHT,
    })),
    edges: edges.map((edge) => ({
      id: edge.id,
      sources: [edge.source],
      targets: [edge.target],
    })),
  };

  const layoutedGraph = await elk.layout(graph);

  return nodes.map((node) => {
    const elkNode = layoutedGraph.children?.find((n) => n.id === node.id);
    if (elkNode?.x === undefined || elkNode?.y === undefined) return node;

    return {
      ...node,
      position: {
        x: elkNode.x,
        y: elkNode.y,
      },
    };
  });
}

/**
 * Synchronous fallback: space nodes evenly in a horizontal row.
 * Used as an initial position before ELK computes the real layout,
 * so React Flow renders something immediately on first paint.
 */
export function buildFallbackPositions<NodeData extends Record<string, unknown>>(
  nodes: Node<NodeData>[]
): Node<NodeData>[] {
  const gap = NODE_WIDTH + 80;
  const totalWidth = nodes.length * gap - 80;
  const startX = -(totalWidth / 2);

  return nodes.map((node, i) => ({
    ...node,
    position: {
      x: startX + i * gap,
      y: 0,
    },
  }));
}
