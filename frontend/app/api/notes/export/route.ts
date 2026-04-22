import { NextRequest, NextResponse } from "next/server";

const BACKEND = process.env.NEXT_PUBLIC_API_URL!;
const API_KEY = process.env.API_SECRET_KEY!;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const res = await fetch(`${BACKEND}/api/notes/export?${searchParams.toString()}`, {
    headers: { "X-API-Key": API_KEY },
  });

  const contentType = res.headers.get("content-type") ?? "application/octet-stream";
  const disposition = res.headers.get("content-disposition") ?? "";
  const body = await res.arrayBuffer();

  return new NextResponse(body, {
    status: res.status,
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": disposition,
    },
  });
}
