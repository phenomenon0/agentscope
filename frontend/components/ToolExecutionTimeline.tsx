"use client";

import { CheckCircle2, Circle, Loader2, XCircle, ChevronRight, Search, Database, BarChart3, FileText, Globe } from "lucide-react";
import { cn } from "@/lib/utils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";

export type ToolCall = {
  id: string;
  tool_name: string;
  status: "running" | "completed" | "failed";
  input?: Record<string, unknown>;
  output?: string;
  timestamp?: number;
  duration_ms?: number;
};

type ToolExecutionTimelineProps = {
  toolCalls: ToolCall[];
  className?: string;
};

const toolIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  search: Search,
  player: Search,
  team: Search,
  match: Search,
  competition: Database,
  season: Database,
  database: Database,
  index: Database,
  viz: BarChart3,
  plot: BarChart3,
  chart: BarChart3,
  stats: FileText,
  summary: FileText,
  aggregate: FileText,
  web: Globe,
  default: Circle,
};

function getToolIcon(toolName: string): React.ComponentType<{ className?: string }> {
  const lowerName = toolName.toLowerCase();
  for (const [key, Icon] of Object.entries(toolIcons)) {
    if (lowerName.includes(key)) {
      return Icon;
    }
  }
  return toolIcons.default;
}

function formatToolName(toolName: string): string {
  // Convert snake_case to Title Case
  return toolName
    .split("_")
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")
    .replace(" Tool", "");
}

function formatDuration(ms?: number): string {
  if (!ms) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function ToolCallItem({ toolCall }: { toolCall: ToolCall }) {
  const Icon = getToolIcon(toolCall.tool_name);
  const hasDetails = toolCall.input || toolCall.output;

  const statusIcon = {
    running: <Loader2 className="h-4 w-4 animate-spin text-slate-500" />,
    completed: <CheckCircle2 className="h-4 w-4 text-emerald-500" />,
    failed: <XCircle className="h-4 w-4 text-rose-500" />,
  }[toolCall.status];

  const statusColor = {
    running: "border-slate-200 bg-slate-100/70",
    completed: "border-emerald-200 bg-emerald-50/70",
    failed: "border-rose-200 bg-rose-50/70",
  }[toolCall.status];

  return (
    <Collapsible>
      <div className={cn("rounded-2xl border p-3 transition-all backdrop-blur-sm", statusColor)}>
        <div className="flex flex-col gap-3">
          {hasDetails && (
            <CollapsibleContent
              forceMount
              className="order-1 space-y-3 rounded-2xl border border-slate-200 bg-white/95 p-3 text-xs text-neutral-700 shadow-inner data-[state=closed]:hidden"
            >
              {toolCall.input && Object.keys(toolCall.input).length > 0 && (
                <div>
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Input</div>
                  <pre className="max-h-32 overflow-x-auto rounded-xl border border-slate-200 bg-white p-2 text-xs text-neutral-700 shadow-inner">
                    {JSON.stringify(toolCall.input, null, 2)}
                  </pre>
                </div>
              )}
              {toolCall.output && (
                <div>
                  <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Output</div>
                  <pre className="max-h-32 overflow-x-auto rounded-xl border border-slate-200 bg-white p-2 text-xs text-neutral-700 shadow-inner">
                    {toolCall.output}
                  </pre>
                </div>
              )}
            </CollapsibleContent>
          )}

          <div className="order-2 flex min-w-0 items-start justify-between gap-3">
            <div className="flex min-w-0 flex-1 items-start gap-3">
              <div className="mt-0.5 flex-shrink-0">
                {statusIcon}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Icon className="h-3.5 w-3.5 flex-shrink-0 text-neutral-700" />
                  <span className="truncate text-sm font-semibold text-neutral-900">
                    {formatToolName(toolCall.tool_name)}
                  </span>
                </div>
                {toolCall.duration_ms && (
                  <Badge variant="secondary" className="mt-1 h-5 border border-slate-200 bg-white/80 text-[10px] text-neutral-700">
                    {formatDuration(toolCall.duration_ms)}
                  </Badge>
                )}
              </div>
            </div>
            {hasDetails && (
              <CollapsibleTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 flex-shrink-0"
                >
                  <ChevronRight className="h-4 w-4 transition-transform [[data-state=open]>&]:-rotate-90" />
                  <span className="sr-only">Toggle details</span>
                </Button>
              </CollapsibleTrigger>
            )}
          </div>
        </div>
      </div>
    </Collapsible>
  );
}

export function ToolExecutionTimeline({ toolCalls, className }: ToolExecutionTimelineProps) {
  if (!toolCalls || toolCalls.length === 0) {
    return null;
  }

  const completedCount = toolCalls.filter(tc => tc.status === "completed").length;
  const runningCount = toolCalls.filter(tc => tc.status === "running").length;
  const failedCount = toolCalls.filter(tc => tc.status === "failed").length;
  const orderedToolCalls = [...toolCalls]
    .map((call, index) => ({ call, index }))
    .sort((a, b) => {
      const timeA = a.call.timestamp ?? 0;
      const timeB = b.call.timestamp ?? 0;
      if (timeA === timeB) {
        return b.index - a.index;
      }
      return timeB - timeA;
    })
    .map(({ call }) => call);

  return (
    <Card
      className={cn(
        "overflow-hidden rounded-3xl border border-slate-200 bg-white/90",
        "shadow-[0_18px_40px_-32px_rgba(15,23,42,0.3)]",
        className
      )}
    >
      <CardHeader className="relative border-b border-slate-200 pb-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="h-2.5 w-2.5 animate-pulse rounded-full bg-slate-400" />
            <CardTitle className="text-xs font-semibold uppercase tracking-[0.35em] text-neutral-600">
              Tool Execution
            </CardTitle>
          </div>
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-500">
            {completedCount > 0 && (
              <Badge variant="success" className="h-6 gap-1 border border-emerald-200 bg-emerald-50 text-emerald-700">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {completedCount}
              </Badge>
            )}
            {runningCount > 0 && (
              <Badge variant="secondary" className="h-6 gap-1 border border-slate-300 bg-slate-100 text-slate-700">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {runningCount}
              </Badge>
            )}
            {failedCount > 0 && (
              <Badge variant="destructive" className="h-6 gap-1 border border-rose-200 bg-rose-100 text-rose-700">
                <XCircle className="h-3.5 w-3.5" />
                {failedCount}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 p-4">
        {orderedToolCalls.map((toolCall) => (
          <ToolCallItem key={toolCall.id} toolCall={toolCall} />
        ))}
      </CardContent>
    </Card>
  );
}
