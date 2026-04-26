/**
 * app/api/tasks/route.ts — 태스크 목록 조회 프록시
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

export async function GET(req: NextRequest) {
  const { searchParams } = req.nextUrl;
  const qs = searchParams.toString();
  const res = await fetch(`${BACKEND}/api/tasks${qs ? `?${qs}` : ""}`, {
    headers: { "X-API-Key": API_KEY },
    cache: "no-store",
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
