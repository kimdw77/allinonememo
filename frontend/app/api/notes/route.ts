/**
 * app/api/notes/route.ts — 노트 목록/생성 프록시
 * 서버사이드에서 X-API-Key 헤더를 추가하여 백엔드로 전달
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

function backendHeaders() {
  return { "X-API-Key": API_KEY, "Content-Type": "application/json" };
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const res = await fetch(`${BACKEND}/api/notes?${searchParams.toString()}`, {
    headers: backendHeaders(),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(request: NextRequest) {
  const body = await request.text();
  const res = await fetch(`${BACKEND}/api/notes`, {
    method: "POST",
    headers: backendHeaders(),
    body,
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
