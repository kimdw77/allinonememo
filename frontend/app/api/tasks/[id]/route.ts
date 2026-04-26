/**
 * app/api/tasks/[id]/route.ts — 태스크 수정·삭제 프록시
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

export async function PATCH(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const body = await req.json();
  const res = await fetch(`${BACKEND}/api/tasks/${params.id}`, {
    method: "PATCH",
    headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export async function DELETE(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const res = await fetch(`${BACKEND}/api/tasks/${params.id}`, {
    method: "DELETE",
    headers: { "X-API-Key": API_KEY },
  });
  return new NextResponse(null, { status: res.status });
}
