/**
 * History Timeline — barrel export.
 *
 * Export surface for the three history visualisation components:
 * - TrustScoreChart  — AreaChart of trust scores over time
 * - CalendarHeatmap  — 52-week GitHub-style heatmap
 * - CommitCorrelation — TrustScoreChart + commit marker overlay
 */

export { TrustScoreChart } from "./TrustScoreChart";
export type {
  TrustScoreChartProps,
  RunDataPoint,
  StageResult,
  CommitMarker,
  XAxisMode,
} from "./TrustScoreChart";

export { CalendarHeatmap } from "./CalendarHeatmap";
export type {
  CalendarHeatmapProps,
  DayRunSummary,
} from "./CalendarHeatmap";

export { CommitCorrelation } from "./CommitCorrelation";
export type { CommitCorrelationProps } from "./CommitCorrelation";
