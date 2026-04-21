/**
 * middleware.ts — JWT 서명 검증 기반 인증 체크
 * jose 라이브러리로 Supabase JWT를 Edge Runtime에서 검증
 */
import { jwtVerify } from "jose";
import { NextResponse, type NextRequest } from "next/server";

const JWT_SECRET = new TextEncoder().encode(
  process.env.SUPABASE_JWT_SECRET ?? ""
);

async function verifyToken(token: string): Promise<boolean> {
  // JWT_SECRET이 설정되지 않은 경우 존재 여부만 확인 (개발 환경 폴백)
  if (!process.env.SUPABASE_JWT_SECRET) {
    return token.length > 0;
  }
  try {
    await jwtVerify(token, JWT_SECRET, { algorithms: ["HS256"] });
    return true;
  } catch {
    return false;
  }
}

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const token = request.cookies.get("myv-access-token")?.value;

  if (pathname.startsWith("/login")) {
    if (token && (await verifyToken(token))) {
      return NextResponse.redirect(new URL("/", request.url));
    }
    return NextResponse.next();
  }

  if (!token || !(await verifyToken(token))) {
    const response = NextResponse.redirect(new URL("/login", request.url));
    // 만료/위조 토큰 쿠키 제거
    response.cookies.delete("myv-access-token");
    return response;
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api).*)"],
};
