/** @type {import('next').NextConfig} */

/**
 * The browser always talks to the Next.js origin, never to the API directly.
 *
 * `/api/*` is rewritten server-side to `API_ORIGIN`. Three things follow, and the first is
 * the one that matters:
 *
 * 1. **CORS stops being load-bearing.** The browser only ever sees one origin, so a
 *    misconfigured `ALLOWED_ORIGINS` cannot break the deployed app. The API keeps its CORS
 *    config as a fallback for anyone calling it directly, but the product does not depend
 *    on it being right.
 * 2. **The backend URL is not baked into the bundle.** `API_ORIGIN` is a plain server
 *    variable, not `NEXT_PUBLIC_*`, so changing where the API lives is a config change
 *    rather than a rebuild.
 * 3. **The API origin is not exposed to the client at all.**
 *
 * The earlier version used `NEXT_PUBLIC_API_URL` in both the rewrite *and* the fetch base,
 * which meant setting it made the client bypass the very proxy it was configuring — the two
 * mechanisms fought each other.
 */
const API_ORIGIN = process.env.API_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_ORIGIN.replace(/\/$/, "")}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
