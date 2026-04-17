/** @type {import('next').NextConfig} */
const nextConfig = {
  // Railway 백엔드 API 프록시
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
