/**
 * middleware.ts — 쿠키 존재 여부 기반 인증 체크
 * Supabase가 ECC(P-256) JWT로 전환하여 엣지에서 서명 검증 대신 쿠키 유무만 확인.
 * 실제 데이터 보안은 백엔드 API_SECRET_KEY로 보장됨.
 */
import { NextResponse, type NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const token = request.cookies.get("myv-access-token")?.value;

  if (pathname.startsWith("/login")) {
    if (token) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api).*)"],
};
