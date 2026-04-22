/**
 * app/api/notes/duplicates/route.ts — 중복 노트 감지 프록시
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const res = await fetch(
    `${BACKEND}/api/notes/duplicates?${searchParams.toString()}`,
    { headers: { "X-API-Key": API_KEY } }
  );
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
