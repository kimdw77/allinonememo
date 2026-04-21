/**
 * app/api/categories/[name]/route.ts — 카테고리 삭제 프록시
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

function backendHeaders() {
  return { "X-API-Key": API_KEY };
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: { name: string } }
) {
  const encodedName = encodeURIComponent(params.name);
  const res = await fetch(`${BACKEND}/api/categories/${encodedName}`, {
    method: "DELETE",
    headers: backendHeaders(),
  });
  return new NextResponse(null, { status: res.status });
}
