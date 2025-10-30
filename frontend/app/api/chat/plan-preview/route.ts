import { NextResponse } from "next/server";
import { Persona } from "@/lib/constants";
import { resolveApiBase } from "../api-base";

type PlanPreviewPayload = {
  message: string;
  persona: Persona;
  teamContext?: Record<string, unknown> | null;
};

export async function POST(req: Request) {
  const body = (await req.json()) as PlanPreviewPayload | null;

  if (!body || typeof body.message !== "string" || !body.message.trim()) {
    return NextResponse.json({ error: "Message is required." }, { status: 400 });
  }

  if (body.persona !== "Analyst" && body.persona !== "Scouting Evaluator") {
    return NextResponse.json({ error: "Unsupported persona." }, { status: 400 });
  }

  const upstreamResponse = await fetch(`${resolveApiBase()}/api/agent/plan-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      persona: body.persona,
      message: body.message,
      team_context: body.teamContext ?? undefined,
    }),
  });

  if (!upstreamResponse.body) {
    const text = await upstreamResponse.text().catch(() => "");
    return NextResponse.json(
      { error: text || "Planner stream unavailable." },
      { status: upstreamResponse.status || 500 },
    );
  }

  const headers = new Headers(upstreamResponse.headers);
  if (!headers.has("content-type")) {
    headers.set("content-type", "text/event-stream; charset=utf-8");
  }
  headers.set("cache-control", "no-cache");

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers,
  });
}
