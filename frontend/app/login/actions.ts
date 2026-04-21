"use server";

/**
 * actions.ts — 로그인 서버 액션 (OTP 서버 검증으로 세션 쿠키 보장)
 */
import { redirect } from "next/navigation";
import { createServerActionClient } from "@/lib/supabase-server";

export async function verifyOtpAction(email: string, token: string) {
  const supabase = createServerActionClient();

  const { error } = await supabase.auth.verifyOtp({
    email,
    token,
    type: "email",
  });

  if (error) {
    return { error: error.message };
  }

  redirect("/");
}
