/**
 * middleware.ts — 인증 미들웨어 (임시 비활성화)
 * TODO(auth): 로그인 구현 완료 후 인증 체크 복구
 */
import { NextResponse, type NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  return NextResponse.next({ request });
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
