/**
 * app/api/notes/merge/route.ts — 노트 병합 프록시
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

export async function POST(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const res = await fetch(
    `${BACKEND}/api/notes/merge?${searchParams.toString()}`,
    {
      method: "POST",
      headers: { "X-API-Key": API_KEY },
    }
  );
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
