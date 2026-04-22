/**
 * app/api/notes/upload/route.ts — 파일 업로드 프록시
 * multipart/form-data를 백엔드로 그대로 전달
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

export async function POST(request: NextRequest) {
  const formData = await request.formData();

  const res = await fetch(`${BACKEND}/api/notes/upload`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY },
    body: formData,
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
