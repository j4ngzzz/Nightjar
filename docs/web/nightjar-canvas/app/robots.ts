/**
 * Robots directive — /robots.txt
 *
 * Allows all crawlers and points them to the sitemap.
 * Next.js serialises the returned object to robots.txt at build time.
 * Ref: https://nextjs.org/docs/app/api-reference/file-conventions/metadata/robots
 */

import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/" },
    sitemap: "https://nightjarcode.dev/sitemap.xml",
  };
}
