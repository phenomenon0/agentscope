import classNames from "classnames";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatAttachment } from "@/lib/store/chat-store";
import { VisualizationGallery } from "./VisualizationGallery";

type MessageBubbleProps = {
  role: "user" | "assistant" | "system";
  content: string;
  planPreview?: boolean;
  attachments?: ChatAttachment[];
};

const roleStyles: Record<MessageBubbleProps["role"], string> = {
  user: "self-end border-neutral-300 bg-neutral-100 text-neutral-900",
  assistant: "self-start border-neutral-200 bg-white text-neutral-900 shadow-sm",
  system: "self-center border-amber-300 bg-amber-50 text-amber-800",
};

const roleLabel: Record<MessageBubbleProps["role"], string> = {
  user: "You",
  assistant: "Agent",
  system: "System",
};

export function MessageBubble({ role, content, planPreview, attachments }: MessageBubbleProps) {
  const renderedContent = planPreview ? `_${content}_` : content;
  const label = planPreview && role === "assistant" ? "Plan Preview" : roleLabel[role];
  const hasAttachments = Array.isArray(attachments) && attachments.length > 0;

  return (
    <article className={classNames("max-w-3xl rounded-3xl border px-5 py-4 text-sm leading-relaxed", roleStyles[role])}>
      <header className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        {label}
      </header>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        className="markdown text-neutral-900 [&>h1]:text-lg [&>h2]:text-base [&>h3]:text-sm [&>ul]:list-disc [&>ul]:pl-6 [&>ol]:list-decimal [&>ol]:pl-6 [&>p]:mt-2 [&>p:first-child]:mt-0"
      >
        {renderedContent}
      </ReactMarkdown>
      {hasAttachments && <VisualizationGallery attachments={attachments} className="mt-4" />}
    </article>
  );
}
