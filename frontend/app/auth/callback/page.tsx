"use client";

/**
 * app/auth/callback/page.tsx — Magic Link 클릭 후 세션 처리
 * 클라이언트에서 code를 처리해 localStorage의 code verifier를 사용
 */
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

export default function AuthCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const supabase = createClient();
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");

    if (code) {
      // 클라이언트에서 처리 → localStorage의 code verifier 접근 가능
      supabase.auth.exchangeCodeForSession(code).then(({ error }) => {
        if (!error) {
          router.replace("/");
        } else {
          router.replace("/login");
        }
      });
      return;
    }

    // 해시 방식 fallback (#access_token=xxx)
    const hash = window.location.hash;
    if (hash) {
      const hashParams = new URLSearchParams(hash.slice(1));
      const access_token = hashParams.get("access_token");
      const refresh_token = hashParams.get("refresh_token");
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

    router.replace("/login");
  }, [router]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex items-center justify-center">
      <p className="text-white text-sm">로그인 처리 중...</p>
    </div>
  );
}
