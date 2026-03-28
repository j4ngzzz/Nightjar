"use client";

/**
 * ProofExplanation — streaming LLM natural language explanation.
 *
 * Text appears word-by-word, simulating a streaming LLM response.
 * Uses useEffect + ReadableStream pattern (or mock interval fallback).
 *
 * API integration: POST /api/runs/{runId}/explain → text/event-stream
 * Mock mode: pass `mockText` prop to bypass the real API.
 */

import * as React from "react";
import { motion, AnimatePresence } from "motion/react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ProofExplanationProps {
  /** Run ID to fetch explanation for */
  runId?: string;
  /** Stage name to explain */
  stageName?: string;
  /** Mock text for development/demo mode */
  mockText?: string;
  /** Whether to auto-start streaming on mount */
  autoStream?: boolean;
  /**
   * Whether to render the internal "Explain this" trigger button.
   * Set to false when the parent provides its own trigger (e.g. StageDetailPanel footer).
   * Defaults to true.
   */
  showTriggerButton?: boolean;
  className?: string;
}

// ---------------------------------------------------------------------------
// Mock stream generator — splits text into words with realistic delay
// ---------------------------------------------------------------------------

const DEFAULT_MOCK_TEXT = [
  "The verification pipeline examined this stage using property-based testing with 1,024 random inputs.",
  "Hypothesis generated edge cases covering boundary values, negative inputs, and overflow conditions.",
  "All 1,024 test cases passed.",
  "The invariant `forall x :: result >= 0` was confirmed to hold across the full input domain.",
  "Confidence level: 97.3%. The stage is ready for formal verification.",
].join(" ");

function splitIntoWords(text: string): string[] {
  // Split on spaces but keep trailing spaces as part of each token
  return text.split(/(?<=\s)|(?=\s)/).filter(Boolean);
}

// ---------------------------------------------------------------------------
// Hook: useWordStream
// ---------------------------------------------------------------------------

function useWordStream(
  enabled: boolean,
  words: string[],
  onComplete?: () => void
): { visibleText: string; isStreaming: boolean; isDone: boolean } {
  const [index, setIndex] = React.useState(0);
  const [isStreaming, setIsStreaming] = React.useState(false);
  const [isDone, setIsDone] = React.useState(false);
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    if (!enabled || words.length === 0) return;

    setIndex(0);
    setIsStreaming(true);
    setIsDone(false);

    let current = 0;

    function tick() {
      current += 1;
      setIndex(current);

      if (current >= words.length) {
        setIsStreaming(false);
        setIsDone(true);
        onComplete?.();
        return;
      }

      // Variable delay: short for regular words, slightly longer at punctuation
      const word = words[current - 1] ?? "";
      const hasPunctuation = /[.,!?;:]/.test(word);
      const delay = hasPunctuation ? 80 : 35;
      timerRef.current = setTimeout(tick, delay);
    }

    // Initial delay before first word
    timerRef.current = setTimeout(tick, 120);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, words.join("|")]);

  const visibleText = words.slice(0, index).join("");

  return { visibleText, isStreaming, isDone };
}

// ---------------------------------------------------------------------------
// Hook: useFetchStream — fetch real streaming explanation from API
// ---------------------------------------------------------------------------

function useFetchStream(
  runId: string | undefined,
  stageName: string | undefined,
  enabled: boolean
): { text: string; loading: boolean; error: string | null } {
  const [text, setText] = React.useState("");
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!enabled || !runId) return;

    let ignore = false;
    const controller = new AbortController();

    async function startStream() {
      setLoading(true);
      setError(null);
      setText("");

      try {
        const url = stageName
          ? `/api/runs/${encodeURIComponent(runId!)}/explain?stage=${encodeURIComponent(stageName)}`
          : `/api/runs/${encodeURIComponent(runId!)}/explain`;

        const response = await fetch(url, {
          signal: controller.signal,
        });

        if (!response.ok) {
          if (!ignore) {
            setError(`API error: ${response.status}`);
            setLoading(false);
          }
          return;
        }

        if (!response.body) {
          if (!ignore) {
            setError("No response body from explain API");
            setLoading(false);
          }
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          if (!ignore) {
            setText((prev) => prev + chunk);
          }
        }

        if (!ignore) setLoading(false);
      } catch (err) {
        if (!ignore && (err as Error).name !== "AbortError") {
          setError((err as Error).message);
          setLoading(false);
        }
      }
    }

    startStream();

    return () => {
      ignore = true;
      controller.abort();
    };
  }, [enabled, runId, stageName]);

  return { text, loading, error };
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ProofExplanation({
  runId,
  stageName,
  mockText,
  autoStream = false,
  showTriggerButton = true,
  className,
}: ProofExplanationProps) {
  const [started, setStarted] = React.useState(autoStream);
  const [useMock] = React.useState(!runId || Boolean(mockText));

  // Real API stream
  const { text: apiText, loading: apiLoading, error: apiError } = useFetchStream(
    runId,
    stageName,
    started && !useMock
  );

  // Build word list for mock stream
  const effectiveMockText = mockText ?? DEFAULT_MOCK_TEXT;
  const mockWords = React.useMemo(
    () => (useMock ? splitIntoWords(effectiveMockText) : []),
    [useMock, effectiveMockText]
  );

  const { visibleText: mockVisible, isStreaming: mockStreaming } = useWordStream(
    started && useMock,
    mockWords
  );

  const displayText = useMock ? mockVisible : apiText;
  const isStreaming = useMock ? mockStreaming : apiLoading;
  const error = useMock ? null : apiError;

  const hasContent = displayText.length > 0;

  return (
    <div className={cn("", className)}>
      {/* Trigger button — shown before streaming starts, unless parent supplies its own */}
      <AnimatePresence>
        {showTriggerButton && !started && (
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="inline-flex items-center gap-2 rounded px-3 py-1.5 text-[12px] font-medium transition-colors"
            style={{
              background: "rgba(212,146,10,0.12)",
              border: "1px solid #D4920A",
              color: "#D4920A",
              fontFamily: "var(--font-geist-sans)",
              cursor: "pointer",
            }}
            onClick={() => setStarted(true)}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background =
                "rgba(212,146,10,0.2)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.background =
                "rgba(212,146,10,0.12)";
            }}
          >
            <span aria-hidden>◈</span>
            Explain this
          </motion.button>
        )}
      </AnimatePresence>

      {/* Streaming content panel */}
      <AnimatePresence>
        {started && (
          <motion.div
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
            className="rounded-r-md"
            style={{
              background: "#141109",
              borderLeft: "3px solid #D4920A",
              padding: "12px 14px",
            }}
          >
            {/* Error state */}
            {error && (
              <p
                className="text-[12px]"
                style={{ color: "#C84B2F", fontFamily: "var(--font-geist-sans)" }}
              >
                {error}
              </p>
            )}

            {/* Streaming / done text */}
            {!error && (
              <>
                <p
                  className="text-[13px] leading-relaxed"
                  style={{
                    color: "#F5F0E8",
                    fontFamily: "var(--font-geist-sans)",
                    fontWeight: 400,
                  }}
                >
                  {hasContent ? displayText : null}
                  {/* Cursor blink while streaming */}
                  {isStreaming && (
                    <motion.span
                      animate={{ opacity: [1, 0] }}
                      transition={{ duration: 0.6, repeat: Infinity }}
                      style={{ color: "#D4920A", marginLeft: 1 }}
                      aria-hidden
                    >
                      ▌
                    </motion.span>
                  )}
                </p>

                {/* Loading state before first token */}
                {!hasContent && isStreaming && (
                  <p
                    className="text-[11px]"
                    style={{
                      color: "#9A8E78",
                      fontFamily: "var(--font-jetbrains-mono)",
                    }}
                  >
                    Generating explanation…
                  </p>
                )}
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
