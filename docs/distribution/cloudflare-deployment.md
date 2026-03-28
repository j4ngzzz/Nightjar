# Cloudflare Pages Deployment Guide

Step-by-step guide for deploying the Nightjar Next.js frontend to Cloudflare Pages at nightjarcode.dev.

---

## Prerequisites

- Cloudflare account with nightjarcode.dev domain added (or transferred to Cloudflare DNS)
- GitHub repository: github.com/j4ngzzz/Nightjar (or a separate frontend repo if the Next.js canvas is separate)
- Node.js 18+ locally

---

## Part 1: Build Configuration

### Next.js Configuration for Cloudflare Pages

Cloudflare Pages runs Next.js via the `@cloudflare/next-on-pages` adapter. This is required — Cloudflare's Edge runtime is not Node.js; it is the V8 Isolate runtime (Workerd).

**Install the adapter:**
```bash
npm install --save-dev @cloudflare/next-on-pages
```

**`next.config.js` minimum required settings:**
```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required for Cloudflare Pages
  // Do NOT use 'standalone' output — that's for Docker/Node deployments
  // Cloudflare uses its own build process via next-on-pages
  images: {
    // Cloudflare's image optimization is handled via CF Images, not Next.js
    unoptimized: true,
  },
}

module.exports = nextConfig
```

**`wrangler.toml` in the project root:**
```toml
name = "nightjarcode"
compatibility_date = "2024-09-23"
compatibility_flags = ["nodejs_compat"]

pages_build_output_dir = ".vercel/output/static"

[vars]
# Non-secret environment variables go here
NEXT_PUBLIC_SITE_URL = "https://nightjarcode.dev"
```

**`package.json` build script:**
```json
{
  "scripts": {
    "build": "next build",
    "pages:build": "npx @cloudflare/next-on-pages",
    "pages:dev": "npx wrangler pages dev .vercel/output/static --compatibility-flag=nodejs_compat",
    "deploy": "npm run pages:build && wrangler pages deploy"
  }
}
```

**`.gitignore` additions:**
```
.vercel/
.wrangler/
```

---

## Part 2: Cloudflare Pages Project Setup

### Step 1: Connect the Repository

1. Go to https://dash.cloudflare.com → Workers & Pages → Create application → Pages
2. Connect to Git → Select GitHub → Authorize → Select `j4ngzzz/Nightjar` (or your frontend repo)
3. Click "Begin setup"

### Step 2: Build Settings

Fill in the Cloudflare Pages build configuration form:

| Field | Value |
|-------|-------|
| Project name | `nightjarcode` |
| Production branch | `master` (matches your current branch) |
| Build command | `npx @cloudflare/next-on-pages` |
| Build output directory | `.vercel/output/static` |
| Root directory | `/docs/web` (if frontend lives there) or `/` if it's at repo root |

**Note on root directory:** Check where `package.json` lives for the Next.js app. The `docs/web/` directory exists in this repo (listed in git status). Adjust the root directory field accordingly.

### Step 3: Environment Variables in the Dashboard

Add these in Pages → Settings → Environment variables. Set for both Production and Preview unless noted.

| Variable | Value | Secret? |
|----------|-------|---------|
| `NODE_VERSION` | `18` | No |
| `NEXT_PUBLIC_SITE_URL` | `https://nightjarcode.dev` | No |
| `NEXT_PUBLIC_GITHUB_REPO` | `https://github.com/j4ngzzz/Nightjar` | No |
| `NEXT_PUBLIC_PYPI_PACKAGE` | `nightjarzzz` | No |

Do not add any API keys or secrets to the Pages environment unless needed. Cloudflare Workers/Pages Secrets (encrypted, not visible after save) are available under Settings → Environment variables → Add secret.

### Step 4: Deploy

Click "Save and Deploy." The first build runs immediately. Build time for a Next.js + Cloudflare adapter is typically 2–5 minutes.

---

## Part 3: Custom Domain Setup for nightjarcode.dev

### If nightjarcode.dev DNS is already on Cloudflare

1. Pages → Your project → Custom domains → Add custom domain
2. Enter `nightjarcode.dev`
3. Cloudflare will automatically create a CNAME record: `nightjarcode.dev → nightjarcode.pages.dev`
4. Also add `www.nightjarcode.dev` as a second custom domain (redirects to apex)

### If nightjarcode.dev DNS is NOT yet on Cloudflare

1. Go to Cloudflare Dashboard → Add site → enter `nightjarcode.dev`
2. Select Free plan → Continue
3. Cloudflare will scan existing DNS records (usually accurate)
4. Change the nameservers at your registrar to the two Cloudflare nameservers provided
5. Wait for propagation (minutes to hours)
6. Once DNS is active, proceed with the Custom domains step above

### Verify HTTPS

Cloudflare issues a free Universal SSL certificate automatically. After the custom domain is added:
- Visit https://nightjarcode.dev — should load with green padlock
- Check that HTTP redirects to HTTPS (Cloudflare handles this automatically with SSL/TLS mode = "Full (strict)")

**Recommended SSL/TLS setting:** SSL/TLS → Overview → set to "Full (strict)"

---

## Part 4: Edge Caching Strategy

### Default Cloudflare Cache Behavior

Cloudflare Pages automatically caches all static assets (JS, CSS, images, fonts) at the edge with long cache lifetimes. Next.js static pages are served from edge locations globally with no additional configuration needed.

### Custom Cache Rules for /scan/ and /bugs/ Pages

The `/scan/` and `/bugs/` pages contain security research data that may be updated. Configure cache rules to balance freshness with edge performance.

**Create a Cache Rule in Cloudflare Dashboard:**
Path: Rules → Cache Rules → Create rule

**Rule 1: Static scan results (updated rarely)**
```
Rule name: scan-pages-cache
When: URI path starts with /scan/
Cache eligibility: Eligible for cache
Edge TTL: Override — 24 hours
Browser TTL: Override — 1 hour
```

Rationale: Scan results don't change between quarterly runs. 24-hour edge cache is aggressive but appropriate. The 1-hour browser TTL ensures users who re-check get fresh data within an hour.

**Rule 2: Bug report pages (stable after publication)**
```
Rule name: bugs-pages-cache
When: URI path starts with /bugs/
Cache eligibility: Eligible for cache
Edge TTL: Override — 7 days
Browser TTL: Override — 1 hour
```

Rationale: Individual bug report pages are immutable once published (you may update a "fixed in version X" field, but the finding itself doesn't change). 7-day edge cache is safe.

**Rule 3: API routes — never cache**
```
Rule name: no-cache-api
When: URI path starts with /api/
Cache eligibility: Bypass cache
```

Rationale: If you add a `/api/badge/[owner]/[repo]` endpoint for Nightjar Verified badges, it must always be fresh.

**Rule 4: Home and docs pages**
```
Rule name: landing-pages-cache
When: URI path equals / OR starts with /docs/
Cache eligibility: Eligible for cache
Edge TTL: Override — 1 hour
Browser TTL: Override — 5 minutes
```

Rationale: Landing page and docs change frequently during early-stage development. 1-hour edge cache is a reasonable balance.

### On-Demand Cache Purge

When you publish a new scan run or update a bug report, purge the relevant paths:

```bash
# Purge specific path
curl -X POST "https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/purge_cache" \
  -H "Authorization: Bearer {CF_API_TOKEN}" \
  -H "Content-Type: application/json" \
  --data '{"files":["https://nightjarcode.dev/scan/fastmcp", "https://nightjarcode.dev/scan/"]}'
```

Or use the Cloudflare Dashboard: Caching → Configuration → Purge Cache → Custom Purge → enter the URLs.

For a full scan release (new quarterly run), purge the entire `/scan/` path:
- Caching → Configuration → Purge Cache → Purge Everything (last resort, use sparingly)

---

## Part 5: Performance and Headers

### Security Headers

Add these via Cloudflare Transform Rules or `_headers` file in the Pages project root.

**`public/_headers` file (place in Next.js `public/` directory):**
```
/*
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()

/scan/*
  Cache-Control: public, max-age=3600, s-maxage=86400

/bugs/*
  Cache-Control: public, max-age=3600, s-maxage=604800
```

### Content Security Policy

Add to `next.config.js` (adjust based on what third-party scripts you load):
```js
const securityHeaders = [
  {
    key: 'Content-Security-Policy',
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline'",  // Required for Next.js inline scripts
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: https:",
      "connect-src 'self' https://api.nightjarcode.dev",
    ].join('; ')
  }
]
```

---

## Part 6: Preview Deployments

Cloudflare Pages creates a preview deployment for every branch push and pull request. This is useful for reviewing the /scan/ and /bugs/ pages before publishing new findings.

**Preview URL format:** `https://{branch-name}.nightjarcode.pages.dev`

**Protect preview deployments with Cloudflare Access (recommended):**
1. Zero Trust → Access → Applications → Add application → Self-hosted
2. Application domain: `*.nightjarcode.pages.dev`
3. Policy: require GitHub or email login to access

This prevents scan findings from being publicly accessible before you're ready to publish them.

---

## Part 7: Deployment Checklist

Before first production deploy:

- [ ] `wrangler.toml` present at project root
- [ ] `@cloudflare/next-on-pages` installed as dev dependency
- [ ] `next.config.js` has `images.unoptimized: true`
- [ ] Build command set to `npx @cloudflare/next-on-pages`
- [ ] Build output directory set to `.vercel/output/static`
- [ ] Environment variables added in Cloudflare Dashboard
- [ ] Custom domain `nightjarcode.dev` added to project
- [ ] SSL/TLS set to Full (strict)
- [ ] Cache rules configured for `/scan/` and `/bugs/`
- [ ] Security headers (`_headers` file or Transform Rules) in place
- [ ] Preview protection (Cloudflare Access) configured
- [ ] Test https://nightjarcode.dev loads correctly
- [ ] Test https://www.nightjarcode.dev redirects to apex
- [ ] Test a `/scan/` page and `/bugs/` page loads

---

## Troubleshooting Common Issues

**Build error: "Module not found: Can't resolve 'async_hooks'"**
Cause: Node.js built-in module used in code path that runs at the Edge.
Fix: Ensure the problematic import is only in server-side code, or add `experimental.serverComponentsExternalPackages` to `next.config.js`.

**Build error: "@cloudflare/next-on-pages: Unexpected token"**
Cause: Using a Next.js feature not supported by the Edge runtime (e.g., `fs`, `path`, `crypto` from Node.js).
Fix: Move the offending code to a Cloudflare Worker (separate from Pages) or use the Web Crypto API instead.

**Custom domain shows "Error 1001: DNS resolution error"**
Cause: DNS change hasn't propagated, or the CNAME is misconfigured.
Fix: Wait up to 48 hours for propagation; verify the CNAME in Cloudflare DNS dashboard points to `nightjarcode.pages.dev`.

**Pages builds succeed but site shows old version**
Cause: Aggressive edge cache not invalidated.
Fix: Use Purge Cache in the Cloudflare dashboard after each deployment. Cloudflare Pages should auto-purge on deploy but the custom cache rules may override this.

**`next/image` not working**
Cause: `unoptimized: true` is set, which disables Next.js image optimization.
Fix: This is expected. Use standard `<img>` tags or configure Cloudflare Images as your image optimization layer.
