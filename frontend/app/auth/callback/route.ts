/**
 * app/auth/callback/route.ts — Magic Link 이메일 클릭 후 세션 교환 처리
 * code(PKCE) 방식과 token_hash(OTP) 방식 모두 지원
 */
import { createServerClient } from "@supabase/ssr";
import { type EmailOtpType } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const token_hash = searchParams.get("token_hash");
  const type = searchParams.get("type") as EmailOtpType | null;

  const response = NextResponse.redirect(new URL("/", request.url));

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet: { name: string; value: string; options?: object }[]) {
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options as Parameters<typeof response.cookies.set>[2])
          );
        },
      },
    }
  );

  // token_hash 방식 (Magic Link 기본)
  if (token_hash && type) {
    const { error } = await supabase.auth.verifyOtp({ token_hash, type });
    if (!error) return response;
  }

  // code 방식 (PKCE)
  if (code) {
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return response;
  }

  // 실패 시 로그인 페이지로 (디버그: 파라미터 포함)
  const debugUrl = new URL("/login", request.url);
  debugUrl.searchParams.set("debug", `code=${code},token_hash=${token_hash},type=${type}`);
  return NextResponse.redirect(debugUrl);
}
