/**
 * app/api/categories/route.ts — 카테고리 목록/추가 프록시
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

function backendHeaders() {
  return { "X-API-Key": API_KEY, "Content-Type": "application/json" };
}

export async function GET() {
  const res = await fetch(`${BACKEND}/api/categories`, { headers: backendHeaders() });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function POST(request: NextRequest) {
  const body = await request.text();
  const res = await fetch(`${BACKEND}/api/categories`, {
    method: "POST",
    headers: backendHeaders(),
    body,
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
