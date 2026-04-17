import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MyVault",
  description: "나만의 AI 지식저장소",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body className="min-h-screen bg-slate-50">{children}</body>
    </html>
  );
}
