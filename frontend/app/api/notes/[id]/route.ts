/**
 * app/api/notes/[id]/route.ts — 노트 단건 조회/삭제 프록시
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

function backendHeaders() {
  return { "X-API-Key": API_KEY };
}

export async function GET(
  _request: NextRequest,
  { params }: { params: { id: string } }
) {
  const res = await fetch(`${BACKEND}/api/notes/${params.id}`, {
    headers: backendHeaders(),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  const body = await request.json();
  const res = await fetch(`${BACKEND}/api/notes/${params.id}`, {
    method: "PATCH",
    headers: { ...backendHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: { id: string } }
) {
  const res = await fetch(`${BACKEND}/api/notes/${params.id}`, {
    method: "DELETE",
    headers: backendHeaders(),
  });
  return new NextResponse(null, { status: res.status });
}
