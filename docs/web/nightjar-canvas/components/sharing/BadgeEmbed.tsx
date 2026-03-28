"use client";

/**
 * BadgeEmbed — README badge code-snippet panel.
 *
 * Shows three selectable badge styles (flat, flat-square, for-the-badge)
 * with a live SVG preview and copy-ready Markdown + HTML snippets.
 */

import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/cn";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type BadgeStyle = "flat" | "flat-square" | "for-the-badge";

export interface BadgeEmbedProps {
  owner: string;
  repo: string;
  /** 0–100 score used for the preview badge colour. */
  trustScore: number;
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STYLES: { id: BadgeStyle; label: string }[] = [
  { id: "flat", label: "Flat" },
  { id: "flat-square", label: "Flat Square" },
  { id: "for-the-badge", label: "For the Badge" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const NIGHTJAR_BASE = "https://nightjar.dev";

/**
 * Relative URL for the live in-app preview only.
 * Do NOT use this in copy-paste snippets — use absoluteBadgeUrl() instead.
 */
function previewBadgeUrl(owner: string, repo: string, style: BadgeStyle): string {
  return `/api/badge/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}?style=${encodeURIComponent(style)}`;
}

/**
 * Absolute URL for README snippets. GitHub and other external renderers
 * cannot resolve relative paths; they must point to nightjar.dev.
 */
function absoluteBadgeUrl(owner: string, repo: string, style: BadgeStyle): string {
  return `${NIGHTJAR_BASE}/api/badge/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}?style=${encodeURIComponent(style)}`;
}

function markdownSnippet(owner: string, repo: string, style: BadgeStyle): string {
  const imgUrl = absoluteBadgeUrl(owner, repo, style);
  const runUrl = `${NIGHTJAR_BASE}/${owner}/${repo}`;
  return `[![Nightjar Verification](${imgUrl})](${runUrl})`;
}

function htmlSnippet(owner: string, repo: string, style: BadgeStyle): string {
  const imgUrl = absoluteBadgeUrl(owner, repo, style);
  const runUrl = `${NIGHTJAR_BASE}/${owner}/${repo}`;
  return `<a href="${runUrl}"><img src="${imgUrl}" alt="Nightjar Verification"></a>`;
}

// ---------------------------------------------------------------------------
// Copy button
// ---------------------------------------------------------------------------

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const el = document.createElement("textarea");
      el.value = text;
      document.body.appendChild(el);
      el.select();
      // execCommand is deprecated but kept as intentional legacy HTTP fallback.
      document.execCommand("copy");
      document.body.removeChild(el);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <button
      onClick={handleCopy}
      className={cn(
        "flex h-7 w-7 items-center justify-center rounded transition-colors",
        "text-[#8B8579] hover:text-[#F5B93A]",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#D4920A]"
      )}
      aria-label={copied ? "Copied!" : "Copy to clipboard"}
    >
      {copied ? (
        <Check size={14} style={{ color: "#F5B93A" }} />
      ) : (
        <Copy size={14} />
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Code block
// ---------------------------------------------------------------------------

function CodeBlock({ code, label }: { code: string; label: string }) {
  return (
    <div className="flex flex-col gap-1">
      <span
        className="text-[10px] font-semibold uppercase tracking-[0.12em]"
        style={{ color: "#8B8579" }}
      >
        {label}
      </span>
      <div
        className="flex items-center justify-between gap-2 rounded-md border border-[#2A2315] bg-[#141109] px-3 py-2"
      >
        <code
          className="flex-1 overflow-x-auto text-xs"
          style={{ color: "#F0EBE3", fontFamily: "monospace", whiteSpace: "nowrap" }}
        >
          {code}
        </code>
        <CopyButton text={code} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// BadgeEmbed
// ---------------------------------------------------------------------------

export function BadgeEmbed({ owner, repo, trustScore, className }: BadgeEmbedProps) {
  const [activeStyle, setActiveStyle] = useState<BadgeStyle>("flat");

  const previewUrl = previewBadgeUrl(owner, repo, activeStyle);
  const md = markdownSnippet(owner, repo, activeStyle);
  const html = htmlSnippet(owner, repo, activeStyle);

  return (
    <div
      className={cn(
        "flex flex-col gap-4 rounded-lg border border-[#2A2315] bg-[#0D0B09] p-4",
        className
      )}
    >
      {/* Style selector tabs */}
      <div className="flex gap-1">
        {STYLES.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveStyle(id)}
            className={cn(
              "rounded px-3 py-1 text-xs font-medium transition-colors",
              activeStyle === id
                ? "bg-[#2A2315] text-[#F5B93A]"
                : "text-[#8B8579] hover:text-[#F0EBE3]",
              "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#D4920A]"
            )}
            aria-pressed={activeStyle === id}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Live badge preview */}
      <div
        className="flex items-center justify-center rounded-md border border-[#2A2315] bg-[#141109] py-4"
        aria-label="Badge preview"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={previewUrl}
          alt={`Nightjar badge preview — Trust Score ${trustScore}`}
          height={activeStyle === "for-the-badge" ? 28 : 20}
          style={{ imageRendering: "crisp-edges" }}
        />
      </div>

      {/* Markdown snippet */}
      <CodeBlock code={md} label="Markdown" />

      {/* HTML snippet */}
      <CodeBlock code={html} label="HTML" />

      {/* Note about dynamic data */}
      <p
        className="text-[11px] leading-relaxed"
        style={{ color: "#8B8579" }}
      >
        The badge updates automatically — no re-deploy needed. Badge data refreshes every 5 minutes.
      </p>
    </div>
  );
}
