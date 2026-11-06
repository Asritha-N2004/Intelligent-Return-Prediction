import type { NextConfig } from 'next';
const configuredBackend = process.env.API_URL?.trim();
const servicesDeployment = process.env.VERCEL_SERVICES === '1';
if (process.env.VERCEL && !servicesDeployment && !configuredBackend) {
  throw new Error('Set API_URL to your hosted FastAPI HTTPS origin before deploying to Vercel.');
}
const backend = (configuredBackend || 'http://127.0.0.1:8000').replace(/\/+$/, '');
const backendUrl = new URL(backend);
if (process.env.VERCEL && !servicesDeployment && (backendUrl.protocol !== 'https:' || ['localhost', '127.0.0.1', '[::1]'].includes(backendUrl.hostname))) {
  throw new Error('Vercel requires API_URL to be a public HTTPS backend origin, not localhost.');
}
if (backendUrl.pathname !== '/' || backendUrl.search || backendUrl.hash || backendUrl.username || backendUrl.password) {
  throw new Error('API_URL must be an origin without a path, credentials, query, or fragment.');
}
const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || '.next',
  async rewrites() {
    if (servicesDeployment) return [];
    return [
      {source:'/api/:path*',destination:`${backend}/api/:path*`},
      {source:'/reports/:path*',destination:`${backend}/reports/:path*`},
    ];
  },
};
export default nextConfig;
