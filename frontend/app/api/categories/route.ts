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
  const { searchParams } = new URL(request.url);
  const action = searchParams.get("action");
  const body = await request.text();

  // action=merge → /api/categories/merge
  // action=delete → /api/categories/delete
  // action=update → /api/categories/update
  // (기본) → /api/categories (카테고리 생성)
  const endpoint = action ? `/api/categories/${action}` : "/api/categories";
  const res = await fetch(`${BACKEND}${endpoint}`, {
    method: "POST",
    headers: backendHeaders(),
    body,
  });

  if (res.status === 204) return new NextResponse(null, { status: 204 });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
