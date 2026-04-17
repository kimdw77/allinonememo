"use client";

/**
 * app/login/page.tsx — Magic Link 로그인 페이지
 */
import { useState } from "react";
import { createClient } from "@/lib/supabase";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });

    if (error) {
      setError(error.message);
    } else {
      setSent(true);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* 로고 */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-indigo-500 rounded-2xl mb-4 shadow-lg shadow-indigo-500/30">
            <span className="text-2xl">🗄️</span>
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">MyVault</h1>
          <p className="text-slate-400 mt-1 text-sm">나만의 AI 지식저장소</p>
        </div>

        {/* 카드 */}
        <div className="bg-white/5 backdrop-blur-sm border border-white/10 rounded-2xl p-8 shadow-2xl">
          {sent ? (
            /* 이메일 전송 완료 상태 */
            <div className="text-center">
              <div className="text-5xl mb-4">📬</div>
              <h2 className="text-white font-semibold text-lg mb-2">이메일을 확인하세요</h2>
              <p className="text-slate-400 text-sm leading-relaxed">
                <span className="text-indigo-400 font-medium">{email}</span>로<br />
                로그인 링크를 보냈습니다.<br />
                링크를 클릭하면 자동으로 로그인됩니다.
              </p>
              <button
                onClick={() => setSent(false)}
                className="mt-6 text-xs text-slate-500 hover:text-slate-300 transition-colors"
              >
                다른 이메일로 시도
              </button>
            </div>
          ) : (
            /* 로그인 폼 */
            <>
              <h2 className="text-white font-semibold text-lg mb-1">로그인</h2>
              <p className="text-slate-400 text-sm mb-6">
                이메일로 Magic Link를 받아 로그인하세요
              </p>

              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">
                    이메일
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    required
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder:text-slate-600 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                  />
                </div>

                {error && (
                  <p className="text-red-400 text-xs bg-red-400/10 px-3 py-2 rounded-lg">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading || !email}
                  className="w-full py-3 bg-indigo-500 hover:bg-indigo-400 disabled:bg-indigo-500/40 disabled:cursor-not-allowed text-white font-medium text-sm rounded-xl transition-colors shadow-lg shadow-indigo-500/20"
                >
                  {loading ? "전송 중..." : "Magic Link 받기"}
                </button>
              </form>
            </>
          )}
        </div>

        <p className="text-center text-slate-600 text-xs mt-6">
          개인 전용 서비스입니다
        </p>
      </div>
    </div>
  );
}
