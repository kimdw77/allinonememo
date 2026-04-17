"use client";

/**
 * app/auth/callback/page.tsx — Magic Link 클릭 후 세션 처리
 * URL 해시에서 access_token을 직접 읽어 세션 설정
 */
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const supabase = createClient();
    const hash = window.location.hash;

    if (hash) {
      // URL 해시에서 토큰 추출 (#access_token=xxx&refresh_token=xxx)
      const params = new URLSearchParams(hash.slice(1));
      const access_token = params.get("access_token");
      const refresh_token = params.get("refresh_token");

      if (access_token && refresh_token) {
        supabase.auth.setSession({ access_token, refresh_token }).then(({ error }) => {
          if (!error) {
            router.replace("/");
          } else {
            router.replace("/login");
          }
        });
        return;
      }
    }

    // 해시가 없으면 기존 세션 확인
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
