/**
 * app/api/notes/bulk-reclassify/route.ts — 일괄 재분류 프록시
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

export async function POST(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const res = await fetch(
    `${BACKEND}/api/notes/bulk-reclassify?${searchParams.toString()}`,
    {
      method: "POST",
      headers: { "X-API-Key": API_KEY },
    }
  );
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
