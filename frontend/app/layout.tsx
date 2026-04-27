import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "MyVault",
  description: "나만의 AI 지식저장소",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "MyVault",
    startupImage: "/apple-touch-icon.png",
  },
  other: {
    "mobile-web-app-capable": "yes",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" className={inter.className} suppressHydrationWarning>
      <head>
        <meta name="theme-color" content="#6366f1" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="apple-mobile-web-app-title" content="MyVault" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        {/* 다크모드 초기화: 렌더 전 실행해 깜빡임 방지 */}
        <script dangerouslySetInnerHTML={{ __html: `
          (function(){
            var t=localStorage.getItem('mv-theme');
            var d=window.matchMedia('(prefers-color-scheme: dark)').matches;
            if(t==='dark'||(t===null&&d)){document.documentElement.classList.add('dark');}
          })();
        `}} />
      </head>
      <body className="min-h-screen bg-slate-50 dark:bg-slate-900 antialiased transition-colors duration-200">{children}</body>
    </html>
  );
}
