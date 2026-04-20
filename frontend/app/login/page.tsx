"use client";

/**
 * app/login/page.tsx — 이메일 OTP 2단계 로그인 페이지
 */
import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

type Step = "email" | "otp";

export default function LoginPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 1단계: 이메일로 OTP 코드 발송
  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithOtp({ email });

    if (error) {
      setError(error.message);
    } else {
      setStep("otp");
    }
    setLoading(false);
  };

  // 2단계: OTP 코드 입력 → 세션 생성
  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    const supabase = createClient();
    const { error } = await supabase.auth.verifyOtp({
      email,
      token: otp,
      type: "email",
    });

    if (error) {
      setError("코드가 올바르지 않거나 만료되었습니다.");
    } else {
      router.push("/");
      router.refresh();
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
          {step === "email" ? (
            <>
              <h2 className="text-white font-semibold text-lg mb-1">로그인</h2>
              <p className="text-slate-400 text-sm mb-6">
                이메일로 6자리 인증 코드를 받아 로그인하세요
              </p>

              <form onSubmit={handleSendOtp} className="space-y-4">
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
                  {loading ? "전송 중..." : "인증 코드 받기"}
                </button>
              </form>
            </>
          ) : (
            <>
              <button
                onClick={() => { setStep("email"); setError(""); setOtp(""); }}
                className="text-slate-500 hover:text-slate-300 text-xs mb-4 flex items-center gap-1 transition-colors"
              >
                ← 이메일 변경
              </button>

              <h2 className="text-white font-semibold text-lg mb-1">코드 입력</h2>
              <p className="text-slate-400 text-sm mb-6">
                <span className="text-indigo-400 font-medium">{email}</span>로<br />
                보낸 인증 코드를 입력하세요
              </p>

              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">
                    인증 코드
                  </label>
                  <input
                    type="text"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, "").slice(0, 8))}
                    placeholder="12345678"
                    required
                    maxLength={8}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl text-white placeholder:text-slate-600 text-sm text-center tracking-[0.5em] text-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                  />
                </div>

                {error && (
                  <p className="text-red-400 text-xs bg-red-400/10 px-3 py-2 rounded-lg">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading || otp.length < 6}
                  className="w-full py-3 bg-indigo-500 hover:bg-indigo-400 disabled:bg-indigo-500/40 disabled:cursor-not-allowed text-white font-medium text-sm rounded-xl transition-colors shadow-lg shadow-indigo-500/20"
                >
                  {loading ? "확인 중..." : "로그인"}
                </button>

                <button
                  type="button"
                  onClick={handleSendOtp}
                  disabled={loading}
                  className="w-full text-xs text-slate-500 hover:text-slate-300 transition-colors"
                >
                  코드 재전송
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
