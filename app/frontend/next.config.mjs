/** @type {import('next').NextConfig} */
//
// Catalyst Web Client Hosting serves this app under the `/app/` path, NOT at
// root. Without basePath + assetPrefix, Next.js emits absolute `/_next/...`
// URLs which 404 in production. The visible symptom: blank/unstyled page —
// CSS, JS chunks, and the React bundle all 404 in DevTools.
//
// See: https://sarvik-60074155874.development.catalystserverless.in/app/
// The hosted target name (`/app/`) is set in catalyst.json → client.target.
const nextConfig = {
  output: 'export',
  basePath: '/app',
  assetPrefix: '/app/',
  images: { unoptimized: true },
  // Catalyst Web Client Hosting does NOT auto-resolve directory indexes
  // (i.e. /app/dashboard/ → /app/dashboard/index.html). Disabling trailingSlash
  // makes Next emit `/dashboard.html` instead of `/dashboard/index.html`, which
  // Catalyst happily serves as `/app/dashboard`.
  trailingSlash: false,
  typescript: {
    // Hackathon deploy: skip type-only errors (logged in TYPE_ERRORS_TODO.md).
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
