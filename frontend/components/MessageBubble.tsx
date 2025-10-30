import classNames from "classnames";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatAttachment, ToolCall } from "@/lib/store/chat-store";
import { VisualizationGallery } from "./VisualizationGallery";
import { ToolExecutionTimeline } from "./ToolExecutionTimeline";
import { Card, CardHeader, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type MessageBubbleProps = {
  role: "user" | "assistant" | "system";
  content: string;
  planPreview?: boolean;
  attachments?: ChatAttachment[];
  toolCalls?: ToolCall[];
};

const roleStyles: Record<MessageBubbleProps["role"], string> = {
  user: "self-end border-neutral-300 bg-neutral-100",
  assistant: "self-start border-neutral-200 bg-white shadow-sm",
  system: "self-center border-amber-300 bg-amber-50",
};

const roleLabel: Record<MessageBubbleProps["role"], { label: string; variant: "default" | "secondary" | "outline" }> = {
  user: { label: "You", variant: "secondary" },
  assistant: { label: "Agent", variant: "default" },
  system: { label: "System", variant: "outline" },
};

export function MessageBubble({ role, content, planPreview, attachments, toolCalls }: MessageBubbleProps) {
  const renderedContent = planPreview ? `_${content}_` : content;
  const label = planPreview && role === "assistant" ? "Plan Preview" : roleLabel[role].label;
  const badgeVariant = planPreview ? "outline" : roleLabel[role].variant;
  const hasAttachments = Array.isArray(attachments) && attachments.length > 0;
  const hasToolCalls = Array.isArray(toolCalls) && toolCalls.length > 0;

  return (
    <Card className={classNames("max-w-3xl", roleStyles[role])}>
      <CardHeader className="pb-3">
        <Badge variant={badgeVariant} className="w-fit">
          {label}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        {hasToolCalls && <ToolExecutionTimeline toolCalls={toolCalls} />}
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          className="markdown text-neutral-900 text-sm leading-relaxed [&>h1]:text-lg [&>h1]:font-semibold [&>h2]:text-base [&>h2]:font-semibold [&>h3]:text-sm [&>h3]:font-semibold [&>ul]:list-disc [&>ul]:pl-6 [&>ol]:list-decimal [&>ol]:pl-6 [&>p]:mt-2 [&>p:first-child]:mt-0 [&>code]:rounded [&>code]:bg-neutral-100 [&>code]:px-1.5 [&>code]:py-0.5 [&>code]:text-xs"
        >
          {renderedContent}
        </ReactMarkdown>
        {hasAttachments && <VisualizationGallery attachments={attachments} />}
      </CardContent>
    </Card>
  );
}
