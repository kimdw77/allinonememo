/**
 * app/api/notes/graph/route.ts — 노트 그래프 데이터 프록시
 */
import { NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

export async function GET() {
  const res = await fetch(`${BACKEND}/api/notes/graph`, {
    headers: { "X-API-Key": API_KEY },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
