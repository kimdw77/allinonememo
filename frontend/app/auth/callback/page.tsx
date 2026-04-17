"use client";

/**
 * app/auth/callback/page.tsx — Magic Link 클릭 후 세션 처리 (클라이언트)
 * implicit flow: URL 해시에서 access_token을 자동으로 읽어 세션 설정
 */
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const supabase = createClient();

    // createBrowserClient가 URL 해시의 access_token을 자동으로 감지해 세션 설정
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        router.replace("/");
      } else {
        router.replace("/login");
      }
    });
  }, [router]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex items-center justify-center">
      <p className="text-white text-sm">로그인 처리 중...</p>
    </div>
  );
}
