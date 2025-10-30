import { NextResponse } from "next/server";
import { Persona } from "@/lib/constants";
import { resolveApiBase } from "./api-base";

type ChatRequestPayload = {
  message: string;
  persona: Persona;
  teamContext?: Record<string, unknown> | null;
  sessionId?: string | null;
};

export async function POST(req: Request) {
  const body = (await req.json()) as ChatRequestPayload;

  if (!body || typeof body.message !== "string" || !body.message.trim()) {
    return NextResponse.json({ error: "Message is required." }, { status: 400 });
  }

  if (body.persona !== "Analyst" && body.persona !== "Scouting Evaluator") {
    return NextResponse.json({ error: "Unsupported persona." }, { status: 400 });
  }

  const upstreamResponse = await fetch(`${resolveApiBase()}/api/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: body.sessionId ?? undefined,
      persona: body.persona,
      message: body.message,
      team_context: body.teamContext ?? undefined,
    }),
  });

  const text = await upstreamResponse.text();
  let safeJson: any = {};
  if (text) {
    try {
      safeJson = JSON.parse(text);
    } catch (error) {
      safeJson = { error: text };
    }
  }

  if (!upstreamResponse.ok) {
    return NextResponse.json(
      { error: safeJson?.error ?? "Agent execution error." },
      { status: upstreamResponse.status },
    );
  }

  return NextResponse.json(safeJson);
}

export async function DELETE(req: Request) {
  const { searchParams } = new URL(req.url);
  const sessionId = searchParams.get("sessionId");

  if (!sessionId) {
    return NextResponse.json({ error: "sessionId query parameter required." }, { status: 400 });
  }

  const upstreamResponse = await fetch(`${resolveApiBase()}/api/agent/chat/${sessionId}`, {
    method: "DELETE",
  });

  if (!upstreamResponse.ok) {
    const text = await upstreamResponse.text();
    return NextResponse.json(
      { error: text || "Failed to reset session." },
      { status: upstreamResponse.status },
    );
  }

  const payload = await upstreamResponse.json().catch(() => ({ status: "reset" }));
  return NextResponse.json(payload);
}
