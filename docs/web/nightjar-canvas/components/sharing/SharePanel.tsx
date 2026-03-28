"use client";

/**
 * SharePanel — sharing controls for a verification run result.
 *
 * Contains:
 *   1. "Share on X / Twitter" — opens a pre-filled tweet in a new tab.
 *   2. "Copy link" — writes the canonical run URL to the clipboard,
 *      then briefly swaps the icon to a checkmark.
 *   3. "Add badge to README" — renders the BadgeEmbed sub-panel.
 *
 * Colour rules: amber palette only — no green, no purple.
 */

import { useState } from "react";
import { Link2, Check, Share2, Code2, ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";
import { BadgeEmbed } from "./BadgeEmbed";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SharePanelProps {
  /** Canonical run URL to share (e.g. https://nightjar.dev/run/abc123). */
  runUrl: string;
  /** Repository slug in "owner/repo" form. Used for tweet copy + badge URLs. */
  repo: string;
  /** Numeric trust score 0–100. */
  trustScore: number;
  /** Human label ("FORMALLY VERIFIED", "ISSUES FOUND", …). */
  trustLabel: string;
  /** Optional extra className for the container. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Copy-link button
// ---------------------------------------------------------------------------

function CopyLinkButton({ url }: { url: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select a temporary input.
      const input = document.createElement("input");
      input.value = url;
      document.body.appendChild(input);
      input.select();
      // execCommand is deprecated but kept as intentional legacy HTTP fallback
      // for environments where navigator.clipboard is unavailable.
      document.execCommand("copy");
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  return (
    <>
      {/* aria-live region announces clipboard status to screen readers */}
      <span
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="sr-only"
      >
        {copied ? "Link copied to clipboard" : ""}
      </span>
      <button
        onClick={handleCopy}
        className={cn(
          "flex items-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium transition-all duration-200",
          "border border-[#2A2315] bg-[#141109] text-[#F0EBE3]",
          "hover:border-[#D4920A] hover:text-[#F5B93A]",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4920A]",
          "focus-visible:ring-offset-2 focus-visible:ring-offset-[#0D0B09]"
        )}
        aria-label={copied ? "Link copied to clipboard" : "Copy link to clipboard"}
      >
        {copied ? (
          <Check size={15} style={{ color: "#F5B93A" }} aria-hidden="true" />
        ) : (
          <Link2 size={15} aria-hidden="true" />
        )}
        <span>{copied ? "Copied!" : "Copy link"}</span>
      </button>
    </>
  );
}

// ---------------------------------------------------------------------------
// Twitter / X share button
// ---------------------------------------------------------------------------

function buildTweetText(
  repo: string,
  trustScore: number,
  trustLabel: string,
  runUrl: string
): string {
  const emoji = trustScore >= 81 ? "🔐" : "⚠️";
  return (
    `${emoji} ${repo} is ${trustLabel.toLowerCase()} — ` +
    `Trust Score ${trustScore}/100 ` +
    `via @nightjardev\n\n${runUrl}`
  );
}

function TwitterButton({
  repo,
  trustScore,
  trustLabel,
  runUrl,
}: {
  repo: string;
  trustScore: number;
  trustLabel: string;
  runUrl: string;
}) {
  function handleClick() {
    const text = buildTweetText(repo, trustScore, trustLabel, runUrl);
    const tweetUrl =
      "https://twitter.com/intent/tweet?text=" + encodeURIComponent(text);
    window.open(tweetUrl, "_blank", "noopener,noreferrer");
  }

  return (
    <button
      onClick={handleClick}
      className={cn(
        "flex items-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium transition-all duration-200",
        "border border-[#2A2315] bg-[#141109] text-[#F0EBE3]",
        "hover:border-[#D4920A] hover:text-[#F5B93A]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4920A]"
      )}
      aria-label="Share on X (Twitter)"
    >
      <Share2 size={15} aria-hidden="true" />
      <span>Share on X</span>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Badge embed toggle button
// ---------------------------------------------------------------------------

function BadgeToggleButton({
  expanded,
  onClick,
}: {
  expanded: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-2 rounded-md px-4 py-2.5 text-sm font-medium transition-all duration-200",
        "border bg-[#141109] text-[#F0EBE3]",
        expanded
          ? "border-[#D4920A] text-[#F5B93A]"
          : "border-[#2A2315] hover:border-[#D4920A] hover:text-[#F5B93A]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#D4920A]"
      )}
      aria-expanded={expanded}
      aria-controls="badge-embed-panel"
      aria-label="Add badge to README"
    >
      <Code2 size={15} aria-hidden="true" />
      <span>Add badge to README</span>
      <ChevronDown
        size={13}
        aria-hidden="true"
        className={cn(
          "ml-0.5 transition-transform duration-200",
          expanded ? "rotate-180" : "rotate-0"
        )}
      />
    </button>
  );
}

// ---------------------------------------------------------------------------
// SharePanel
// ---------------------------------------------------------------------------

export function SharePanel({
  runUrl,
  repo,
  trustScore,
  trustLabel,
  className,
}: SharePanelProps) {
  const [showBadge, setShowBadge] = useState(false);

  // Derive owner/repoName from "owner/repo" slug.
  const slashIdx = repo.indexOf("/");
  const owner = slashIdx !== -1 ? repo.slice(0, slashIdx) : repo;
  const repoName = slashIdx !== -1 ? repo.slice(slashIdx + 1) : repo;

  return (
    <div
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-[#2A2315] bg-[#0D0B09] p-5",
        className
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        <div
          className="h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: "#D4920A" }}
          aria-hidden="true"
        />
        <span
          className="text-xs font-semibold uppercase tracking-[0.12em]"
          style={{ color: "#8B8579" }}
        >
          Share result
        </span>
      </div>

      {/* Buttons row */}
      <div className="flex flex-wrap gap-2">
        <TwitterButton
          repo={repo}
          trustScore={trustScore}
          trustLabel={trustLabel}
          runUrl={runUrl}
        />
        <CopyLinkButton url={runUrl} />
        <BadgeToggleButton
          expanded={showBadge}
          onClick={() => setShowBadge((v) => !v)}
        />
      </div>

      {/* Badge embed panel (conditional) */}
      {showBadge && (
        <div
          id="badge-embed-panel"
          className="mt-1 animate-in fade-in slide-in-from-top-1 duration-200"
        >
          <BadgeEmbed owner={owner} repo={repoName} trustScore={trustScore} />
        </div>
      )}
    </div>
  );
}
