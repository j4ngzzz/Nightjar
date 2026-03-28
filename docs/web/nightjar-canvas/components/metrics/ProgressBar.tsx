"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ProgressBarProps {
  /**
   * Completion percentage 0–100. Animates left-to-right as stages complete.
   * Pass `null` to render an indeterminate pulsing bar.
   */
  percent: number | null;
  /** Height in px (default 3). */
  height?: number;
  className?: string;
  /** Accessible label for screen readers. */
  "aria-label"?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * ProgressBar — amber full-width progress bar.
 *
 * - 3px height by default
 * - #F5B93A fill, animated left-to-right via CSS width transition
 * - When `percent` is null, renders an indeterminate shimmer
 */
export function ProgressBar({
  percent,
  height = 3,
  className,
  "aria-label": ariaLabel = "Pipeline progress",
}: ProgressBarProps) {
  // We defer setting the width to the next paint so the CSS transition fires.
  const [displayPercent, setDisplayPercent] = useState<number>(0);
  const isFirstMount = useRef(true);

  useEffect(() => {
    if (percent === null) return;

    const clampedPct = Math.min(100, Math.max(0, percent));

    if (isFirstMount.current) {
      // On first mount, let React render 0 first, then animate to the target.
      isFirstMount.current = false;
      const raf = requestAnimationFrame(() => {
        setDisplayPercent(clampedPct);
      });
      return () => cancelAnimationFrame(raf);
    }

    setDisplayPercent(clampedPct);
  }, [percent]);

  const isIndeterminate = percent === null;

  return (
    <div
      className={cn("relative w-full overflow-hidden", className)}
      style={{
        height,
        backgroundColor: "#2A2315",
        borderRadius: height,
      }}
      role="progressbar"
      aria-valuenow={isIndeterminate ? undefined : displayPercent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={ariaLabel}
      aria-busy={isIndeterminate}
    >
      {isIndeterminate ? (
        /* Indeterminate shimmer — slides from left to right indefinitely */
        <div
          className="absolute inset-y-0"
          style={{
            width: "40%",
            backgroundColor: "#F5B93A",
            borderRadius: height,
            animation: "nightjar-progress-shimmer 1.4s ease-in-out infinite",
          }}
        />
      ) : (
        /* Determinate fill */
        <div
          style={{
            height: "100%",
            width: `${displayPercent}%`,
            backgroundColor: "#F5B93A",
            borderRadius: height,
            transition: "width 400ms cubic-bezier(0.16, 1, 0.3, 1)",
            willChange: "width",
          }}
        />
      )}

      {/*
        Keyframes for indeterminate shimmer. Injected inline so the component
        is self-contained — no global CSS dependency.
      */}
      {isIndeterminate && (
        <style>{`
          @keyframes nightjar-progress-shimmer {
            0%   { left: -40%; opacity: 0.8; }
            50%  { opacity: 1; }
            100% { left: 100%; opacity: 0.8; }
          }
        `}</style>
      )}
    </div>
  );
}
