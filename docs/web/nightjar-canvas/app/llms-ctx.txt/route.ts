/**
 * Route Handler: /llms-ctx.txt
 *
 * Serves the expanded LLM context file from /public with the correct
 * Content-Type header. This file contains the full Nightjar reference
 * document — pipeline stages, CLI reference, competitor comparisons, FAQ,
 * and architecture overview — optimized for LLM consumption.
 *
 * Spec: https://llmstxt.org/ (llms-ctx.txt is the expanded variant)
 */

import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const dynamic = "force-static";
export const runtime = "nodejs";

export async function GET() {
  try {
    const filePath = join(process.cwd(), "public", "llms-ctx.txt");
    const content = await readFile(filePath, "utf-8");

    return new Response(content, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "public, max-age=86400, s-maxage=86400, stale-while-revalidate=604800",
        "X-Robots-Tag": "noindex",
      },
    });
  } catch {
    return new Response("Not found", { status: 404 });
  }
}
