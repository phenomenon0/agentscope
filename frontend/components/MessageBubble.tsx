import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Loader2 } from "lucide-react";
import type { ChatAttachment, ToolCall } from "@/lib/store/chat-store";
import { VisualizationGallery } from "./VisualizationGallery";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type MessageBubbleProps = {
  role: "user" | "assistant" | "system";
  content: string;
  planPreview?: boolean;
  statusHint?: "thinking";
  toolCallNames?: string[];
  attachments?: ChatAttachment[];
  toolCalls?: ToolCall[];
  onImagesLoaded?: () => void;
};

const roleGlows: Record<MessageBubbleProps["role"], string> = {
  user: "from-slate-300/40 via-transparent to-transparent",
  assistant: "from-slate-200/35 via-transparent to-transparent",
  system: "from-amber-300/35 via-transparent to-transparent",
};

const roleLabel: Record<MessageBubbleProps["role"], { label: string; variant: "default" | "secondary" | "outline" }> = {
  user: { label: "You", variant: "secondary" },
  assistant: { label: "Agent", variant: "default" },
  system: { label: "System", variant: "outline" },
};

const formatToolLabel = (name: string) =>
  name
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

export function MessageBubble({
  role,
  content,
  planPreview: _planPreview,
  statusHint,
  toolCallNames,
  attachments,
  onImagesLoaded,
}: MessageBubbleProps) {
  if (statusHint === "thinking") {
    return (
      <div className="flex flex-col gap-2 self-start rounded-full border border-slate-200 bg-white/85 px-4 py-3 text-[11px] font-medium uppercase tracking-[0.28em] text-neutral-500 shadow-[0_12px_28px_-24px_rgba(15,23,42,0.35)]">
        <span className="flex items-center gap-2">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-500" />
          Thinking
        </span>
        {toolCallNames && toolCallNames.length > 0 && (
          <div className="flex flex-wrap gap-1 text-[10px] font-semibold uppercase tracking-[0.25em] text-slate-500">
            {toolCallNames.map((name) => (
              <span
                key={name}
                className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-600"
              >
                {formatToolLabel(name)}
              </span>
            ))}
          </div>
        )}
      </div>
    );
  }

  const renderedContent = content;
  const label = roleLabel[role].label;
  const badgeVariant = roleLabel[role].variant;
  const hasAttachments = Array.isArray(attachments) && attachments.length > 0;
  const hasContent = typeof renderedContent === "string" && renderedContent.trim().length > 0;

  return (
    <Card
      className={cn(
        "relative border border-slate-200 bg-white/85",
        "rounded-[24px] shadow-[0_18px_40px_-28px_rgba(15,23,42,0.35)]",
        // Width constraints based on content
        !hasAttachments && "max-w-3xl",
        hasAttachments && "w-full",
        // Alignment
        role === "user" && "self-end",
        role === "assistant" && "self-start",
        role === "system" && "self-center"
      )}
    >
      <div
        className={cn(
          "pointer-events-none absolute -inset-px opacity-60 blur-2xl",
          "bg-gradient-to-br",
          roleGlows[role]
        )}
      />
      <CardHeader className="relative flex flex-col gap-2 pb-3">
        <Badge
          variant={badgeVariant}
          className={cn(
            "w-fit rounded-full border border-slate-200 bg-slate-100 text-xs font-semibold uppercase tracking-[0.25em] text-neutral-600",
          )}
        >
          {label}
        </Badge>
      </CardHeader>
      <CardContent className="relative space-y-5 pt-0">
        {hasContent && (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            className="markdown text-sm leading-relaxed text-neutral-900 [&>h1]:text-xl [&>h1]:font-semibold [&>h2]:text-lg [&>h3]:text-base [&>ul]:list-disc [&>ul]:pl-6 [&>ol]:list-decimal [&>ol]:pl-6 [&>p]:mt-3 [&>p:first-child]:mt-0 [&>code]:rounded-lg [&>code]:bg-white/70 [&>code]:px-2 [&>code]:py-1 [&>code]:text-xs"
          >
            {renderedContent}
          </ReactMarkdown>
        )}
        {hasAttachments && <VisualizationGallery attachments={attachments} onAllImagesLoaded={onImagesLoaded} />}
      </CardContent>
    </Card>
  );
}
