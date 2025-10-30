"use client";

import dynamic from "next/dynamic";

const DynamicChatPanel = dynamic(
  () => import("@/components/ChatPanel").then((module) => ({ default: module.ChatPanel })),
  {
    ssr: false,
  }
);

export default function Page() {
  return (
    <div className="flex min-h-screen flex-col bg-neutral-100 text-neutral-900">
      <header className="border-b border-neutral-200 bg-white px-6 py-5 shadow-md shadow-black/5">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between gap-6">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-neutral-900">
              StatsBomb Analyst & Scouting Workspace
            </h1>
            <p className="mt-2 max-w-xl text-sm text-neutral-500">
              Markdown-first, persona-aware assistant backed by your local StatsBomb + Wyscout data.
            </p>
          </div>
          <div className="rounded-2xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-xs text-neutral-500 shadow-sm">
            <p>FastAPI base: {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}</p>
            <p>AI provider: {process.env.AI_PROVIDER ?? "openai"}</p>
          </div>
        </div>
      </header>
      <DynamicChatPanel />
    </div>
  );
}
