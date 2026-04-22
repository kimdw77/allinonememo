/**
 * app/api/stats/route.ts — 통계 API 프록시
 */
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

export async function GET() {
  const res = await fetch(`${BACKEND}/api/stats`, {
    headers: { "X-API-Key": API_KEY },
    next: { revalidate: 60 },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
