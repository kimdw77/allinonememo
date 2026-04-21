/**
 * route.ts — 로그아웃: 쿠키 삭제
 */
import { NextResponse } from "next/server";

export async function POST() {
  const response = NextResponse.json({ success: true });
  response.cookies.delete("myv-access-token");
  response.cookies.delete("myv-refresh-token");
  return response;
}
