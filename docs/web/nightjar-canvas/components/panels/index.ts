/**
 * Nightjar Verification Canvas — Stage Detail Panels
 *
 * Re-exports all panel components for convenient importing:
 *
 * ```tsx
 * import { StageDetailPanel, InvariantCard, CounterexampleDisplay, CegisTimeline, ProofExplanation } from '@/components/panels';
 * ```
 */

export { StageDetailPanel } from "./StageDetailPanel";
export type { StageDetailData, StageStatus, StageLogLine } from "./StageDetailPanel";

export { InvariantCard } from "./InvariantCard";
export type { InvariantData, InvariantTier, InvariantOrigin } from "./InvariantCard";

export { CounterexampleDisplay } from "./CounterexampleDisplay";
export type { CounterexampleData } from "./CounterexampleDisplay";

export { CegisTimeline } from "./CegisTimeline";
export type { CegisIteration } from "./CegisTimeline";

export { ProofExplanation } from "./ProofExplanation";
