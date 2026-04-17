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

    // SIGNED_IN 이벤트 대기 (implicit flow에서 해시 처리 완료 후 발생)
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === "SIGNED_IN" && session) {
        router.replace("/");
      }
    });

    // 3초 안에 SIGNED_IN이 없으면 로그인 페이지로
    const timer = setTimeout(() => {
      supabase.auth.getSession().then(({ data: { session } }) => {
        if (!session) router.replace("/login");
      });
    }, 3000);

    return () => {
      subscription.unsubscribe();
      clearTimeout(timer);
    };
  }, [router]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex items-center justify-center">
      <p className="text-white text-sm">로그인 처리 중...</p>
    </div>
  );
}
