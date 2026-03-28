/**
 * Programmatic sitemap — /sitemap.xml
 *
 * Generates URLs for:
 *   - Static pages (home, bugs index, compare index, pricing, quickstart)
 *   - All bug detail pages  (/bugs/[slug])
 *   - All comparison pages  (/compare/[slug])
 *
 * Next.js serialises the returned array to sitemap.xml at build time.
 * Ref: https://nextjs.org/docs/app/api-reference/file-conventions/metadata/sitemap
 */

import type { MetadataRoute } from "next";
import { bugs } from "@/lib/bugs-data";
import { comparisons } from "@/lib/comparisons-data";

export const dynamic = "force-static";

const BASE_URL = "https://nightjarcode.dev";

export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();

  // Static pages
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: BASE_URL,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 1.0,
    },
    {
      url: `${BASE_URL}/bugs`,
      lastModified: now,
      changeFrequency: "weekly",
      priority: 0.9,
    },
    {
      url: `${BASE_URL}/compare`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      url: `${BASE_URL}/pricing`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${BASE_URL}/docs/quickstart`,
      lastModified: now,
      changeFrequency: "monthly",
      priority: 0.8,
    },
  ];

  // Bug detail pages
  const bugPages: MetadataRoute.Sitemap = bugs.map((bug) => ({
    url: `${BASE_URL}/bugs/${bug.slug}`,
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: 0.7,
  }));

  // Comparison pages
  const comparisonPages: MetadataRoute.Sitemap = comparisons.map((c) => ({
    url: `${BASE_URL}/compare/${c.slug}`,
    lastModified: now,
    changeFrequency: "monthly" as const,
    priority: 0.6,
  }));

  return [...staticPages, ...bugPages, ...comparisonPages];
}
