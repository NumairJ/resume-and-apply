const BACKEND_INTERNAL_URL =
  process.env.BACKEND_INTERNAL_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    // Rewrites time out after 30s by default, which silently killed resume generation:
    // the browser got a bodyless HTTP 500 while the backend was still working, and no
    // matching line ever appeared in the backend log. A generation runs ~55s, and the
    // guardrail chain may retry twice inside one request, so this leaves real headroom.
    proxyTimeout: 180_000,
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_INTERNAL_URL}/:path*`,
      },
    ];
  },
};

export default nextConfig;
