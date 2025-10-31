"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { BubbleBackground } from "@/components/animate-ui/components/backgrounds/bubble";
import { Button } from "@/components/ui/button";
import { Menu, X, ServerCog } from "lucide-react";
import { cn } from "@/lib/utils";

const DynamicChatPanel = dynamic(
  () => import("@/components/ChatPanel").then((module) => ({ default: module.ChatPanel })),
  {
    ssr: false,
  }
);

export default function Page() {
  const [metaOpen, setMetaOpen] = useState(false);

  return (
    <div className="relative min-h-screen overflow-hidden text-neutral-900">
      <BubbleBackground className="absolute inset-0" />

      <div className="relative z-10 flex min-h-screen flex-col">
        <header className="flex items-center border-b border-white/30 bg-white/60 px-4 py-3 backdrop-blur-xl md:px-8">
          <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-neutral-500">Agentscope</p>
              <h1 className="text-xl font-semibold tracking-tight text-neutral-900 md:text-2xl">
                StatsBomb Analyst Workspace
              </h1>
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-9 w-9 rounded-full border border-white/60 bg-white/70 text-neutral-600 shadow-sm transition hover:bg-white/90 md:hidden"
                onClick={() => setMetaOpen((open) => !open)}
              >
                {metaOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
                <span className="sr-only">Toggle environment details</span>
              </Button>
              <EnvironmentPopover open={metaOpen} onOpenChange={setMetaOpen} />
            </div>
          </div>
        </header>
        <DynamicChatPanel />
      </div>
    </div>
  );
}

function EnvironmentPopover({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (value: boolean) => void;
}) {
  return (
    <div className="relative hidden md:block">
      <details
        className="group [&_summary]:list-none"
        open={open}
        onToggle={(event) => onOpenChange((event.target as HTMLDetailsElement).open)}
      >
        <summary>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="flex items-center gap-2 rounded-full border border-white/60 bg-white/75 px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-neutral-600 shadow-[0_12px_30px_-28px_rgba(15,23,42,0.28)] transition hover:bg-white/95"
          >
            <ServerCog className="h-3.5 w-3.5 text-slate-500" />
            Session meta
          </Button>
        </summary>
        <div
          className={cn(
            "absolute right-0 mt-3 w-64 rounded-2xl border border-white/70 bg-white/85 p-4 text-[11px]",
            "font-semibold uppercase tracking-[0.25em] text-neutral-600 shadow-[0_24px_55px_-34px_rgba(15,23,42,0.4)] backdrop-blur"
          )}
        >
          <p className="text-[10px] font-semibold tracking-[0.35em] text-neutral-400">API baseline</p>
          <p className="mt-1 break-all text-neutral-600">
            {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}
          </p>
          <p className="mt-3 text-[10px] font-semibold tracking-[0.35em] text-neutral-400">Model provider</p>
          <p className="mt-1 text-neutral-600">{process.env.AI_PROVIDER ?? "openai"}</p>
        </div>
      </details>
    </div>
  );
}
