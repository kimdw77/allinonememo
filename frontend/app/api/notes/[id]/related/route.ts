/**
 * app/api/notes/[id]/related/route.ts — 연관 노트 조회 프록시
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

export async function GET(
  _request: NextRequest,
  { params }: { params: { id: string } }
) {
  const res = await fetch(`${BACKEND}/api/notes/${params.id}/related`, {
    headers: { "X-API-Key": API_KEY },
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
