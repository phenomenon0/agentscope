import { NextResponse } from "next/server";
import { resolveApiBase } from "../api-base";

type Body = {
  sessionId: string;
  keep?: number;
};

export async function POST(req: Request) {
  const body = (await req.json()) as Body | null;
  if (!body || !body.sessionId) {
    return NextResponse.json({ error: "sessionId is required." }, { status: 400 });
  }

  const keep = typeof body.keep === "number" ? body.keep : undefined;
  const params = new URLSearchParams();
  if (keep) {
    params.set("keep", String(keep));
  }

  const upstream = await fetch(
    `${resolveApiBase()}/api/agent/compress/${encodeURIComponent(body.sessionId)}${
      params.toString() ? `?${params.toString()}` : ""
    }`,
    {
      method: "POST",
    },
  );

  const text = await upstream.text();
  let json: any = {};
  if (text) {
    try {
      json = JSON.parse(text);
    } catch {
      json = { error: text };
    }
  }

  if (!upstream.ok) {
    return NextResponse.json(
      { error: json?.error ?? "Compression failed." },
      { status: upstream.status || 500 },
    );
  }

  return NextResponse.json(json);
}
