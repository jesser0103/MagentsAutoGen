/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  experimental: {
    serverComponentsExternalPackages: ['pg'],
  },
  async rewrites() {
    // Local development talks to Uvicorn on localhost. Docker Compose supplies
    // INTERNAL_API_URL=http://api:8000 and overrides this fallback.
    const apiUrl =
      process.env.INTERNAL_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      'http://127.0.0.1:8000';
    return [
      {
        // Proxy /api/* to FastAPI, EXCEPT /api/auth/* which is served by the
        // Better Auth route handler. Plain rewrites are "afterFiles": they run
        // before dynamic routes, so an unfiltered /api/:path* would shadow the
        // [...all] catch-all auth route.
        source: '/api/:path((?!auth(?:/|$)).+)',
        destination: `${apiUrl}/api/:path`,
      },
    ];
  },
};

export default nextConfig;
