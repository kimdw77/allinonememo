import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

export async function POST(request: NextRequest) {
  const body = await request.text();
  const res = await fetch(`${BACKEND}/api/notes/bulk-delete`, {
    method: "POST",
    headers: { "X-API-Key": API_KEY, "Content-Type": "application/json" },
    body,
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
