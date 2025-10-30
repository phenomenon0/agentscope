"use client";

import { useState } from "react";
import { CheckCircle2, Circle, Loader2, XCircle, ChevronDown, ChevronRight, Search, Database, BarChart3, FileText, Globe } from "lucide-react";
import { cn } from "@/lib/utils";

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
  const [isExpanded, setIsExpanded] = useState(false);
  const Icon = getToolIcon(toolCall.tool_name);
  const hasDetails = toolCall.input || toolCall.output;

  const statusIcon = {
    running: <Loader2 className="h-4 w-4 animate-spin text-blue-500" />,
    completed: <CheckCircle2 className="h-4 w-4 text-green-500" />,
    failed: <XCircle className="h-4 w-4 text-red-500" />,
  }[toolCall.status];

  const statusColor = {
    running: "border-blue-200 bg-blue-50",
    completed: "border-green-200 bg-green-50",
    failed: "border-red-200 bg-red-50",
  }[toolCall.status];

  return (
    <div className={cn("rounded-lg border p-3 transition-colors", statusColor)}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 flex-1 min-w-0">
          <div className="flex-shrink-0 mt-0.5">
            {statusIcon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <Icon className="h-3.5 w-3.5 text-neutral-600 flex-shrink-0" />
              <span className="text-sm font-medium text-neutral-900 truncate">
                {formatToolName(toolCall.tool_name)}
              </span>
            </div>
            {toolCall.duration_ms && (
              <span className="text-xs text-neutral-500">
                {formatDuration(toolCall.duration_ms)}
              </span>
            )}
          </div>
        </div>
        {hasDetails && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex-shrink-0 rounded p-1 hover:bg-white/50 transition-colors"
            aria-label={isExpanded ? "Collapse details" : "Expand details"}
          >
            {isExpanded ? (
              <ChevronDown className="h-4 w-4 text-neutral-600" />
            ) : (
              <ChevronRight className="h-4 w-4 text-neutral-600" />
            )}
          </button>
        )}
      </div>

      {isExpanded && hasDetails && (
        <div className="mt-3 space-y-2 border-t border-neutral-200/50 pt-3">
          {toolCall.input && Object.keys(toolCall.input).length > 0 && (
            <div>
              <div className="text-xs font-semibold text-neutral-600 mb-1">Input:</div>
              <pre className="text-xs bg-white/60 rounded p-2 overflow-x-auto border border-neutral-200/50">
                {JSON.stringify(toolCall.input, null, 2)}
              </pre>
            </div>
          )}
          {toolCall.output && (
            <div>
              <div className="text-xs font-semibold text-neutral-600 mb-1">Output:</div>
              <pre className="text-xs bg-white/60 rounded p-2 overflow-x-auto border border-neutral-200/50 max-h-32">
                {toolCall.output}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ToolExecutionTimeline({ toolCalls, className }: ToolExecutionTimelineProps) {
  if (!toolCalls || toolCalls.length === 0) {
    return null;
  }

  const completedCount = toolCalls.filter(tc => tc.status === "completed").length;
  const runningCount = toolCalls.filter(tc => tc.status === "running").length;
  const failedCount = toolCalls.filter(tc => tc.status === "failed").length;

  return (
    <div className={cn("rounded-2xl border border-neutral-200 bg-white p-4 shadow-sm", className)}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
          <h4 className="text-xs font-semibold uppercase tracking-wider text-neutral-600">
            Tool Execution
          </h4>
        </div>
        <div className="flex items-center gap-3 text-xs text-neutral-500">
          {completedCount > 0 && (
            <span className="flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-green-500" />
              {completedCount}
            </span>
          )}
          {runningCount > 0 && (
            <span className="flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin text-blue-500" />
              {runningCount}
            </span>
          )}
          {failedCount > 0 && (
            <span className="flex items-center gap-1">
              <XCircle className="h-3 w-3 text-red-500" />
              {failedCount}
            </span>
          )}
        </div>
      </div>

      <div className="space-y-2">
        {toolCalls.map((toolCall) => (
          <ToolCallItem key={toolCall.id} toolCall={toolCall} />
        ))}
      </div>
    </div>
  );
}
