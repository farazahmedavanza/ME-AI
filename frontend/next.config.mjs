/** @type {import('next').NextConfig} */
const backend =
  process.env.BACKEND_URL ||
  process.env.INTERNAL_API_URL ||
  "http://127.0.0.1:8000";
const backendOrigin = backend.replace(/\/$/, "");

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
