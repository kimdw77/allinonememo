/**
 * middleware.ts — 인증 미들웨어 (OTP 로그인 기반)
 */
import { NextResponse, type NextRequest } from "next/server";
import { createMiddlewareClient } from "@/lib/supabase-server";

export async function middleware(request: NextRequest) {
  const { supabase, response } = createMiddlewareClient(request);

  const {
    data: { session },
  } = await supabase.auth.getSession();

  const pathname = request.nextUrl.pathname;

  // 로그인 페이지는 인증 불필요
  if (pathname.startsWith("/login")) {
    // 이미 로그인된 경우 대시보드로
    if (session) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return response;
  }

  // 비로그인 → 로그인 페이지로
  if (!session) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api).*)"],
};
