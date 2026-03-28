/**
 * Route Handler: /llms.txt
 *
 * Serves the llms.txt file from /public with the correct Content-Type header.
 * On Cloudflare Pages, static files in /public are served automatically, but
 * this explicit handler ensures text/plain; charset=utf-8 is set rather than
 * relying on the CDN's MIME inference.
 *
 * Spec: https://llmstxt.org/
 */

import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const dynamic = "force-static";
export const runtime = "nodejs";

export async function GET() {
  try {
    const filePath = join(process.cwd(), "public", "llms.txt");
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
