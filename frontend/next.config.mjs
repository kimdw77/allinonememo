/** @type {import('next').NextConfig} */
const nextConfig = {
  // /api/notes, /api/rss 는 Next.js Route Handler가 처리 (X-API-Key 헤더 추가)
  // 나머지 /api/* 경로만 백엔드로 리라이트
  async rewrites() {
    return [
      {
        source: "/api/webhook/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/webhook/:path*`,
      },
    ];
  },
};

export default nextConfig;
