import { NextResponse } from "next/server";
import { resolveApiBase } from "../api-base";

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url);
  const sessionId = searchParams.get("sessionId");
  const maxLookback = searchParams.get("maxLookback");

  if (!sessionId) {
    return NextResponse.json({ error: "sessionId query parameter required." }, { status: 400 });
  }

  const upstreamUrl = new URL(`${resolveApiBase()}/api/agent/tool-calls`);
  upstreamUrl.searchParams.set("session_id", sessionId);
  if (maxLookback) {
    upstreamUrl.searchParams.set("max_lookback", maxLookback);
  }

  const upstreamResponse = await fetch(upstreamUrl.toString(), {
    headers: { "Content-Type": "application/json" },
    cache: "no-store",
  });

  const text = await upstreamResponse.text();
  let payload: any = {};
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch (error) {
      payload = { error: text };
    }
  }

  return NextResponse.json(payload, { status: upstreamResponse.status });
}
