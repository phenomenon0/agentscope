"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import {
  Sparkles,
  ArrowRight,
  Loader2,
  Send,
  TrendingUp,
  CalendarDays,
  MessageCircle,
} from "lucide-react";
import {
  Persona,
  API_BASE_URL,
  DEFAULT_COMPETITION_ID,
  DEFAULT_SEASON_LABEL,
  PRESET_TEAMS,
} from "@/lib/constants";
import { MessageBubble } from "./MessageBubble";
import { ToolExecutionTimeline } from "./ToolExecutionTimeline";
import {
  ChatAttachment,
  ChatMessage,
  ToolCall,
  useChatStore,
} from "@/lib/store/chat-store";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const fetcher = async (url: string) => {
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return res.json();
};

const personaDescriptions: Record<Persona, string> = {
  Analyst: "Rapid-fire data takes grounded in StatsBomb metrics and context windows.",
  "Scouting Evaluator": "Long-form scouting synthesis with comps, archetypes, and tactical fit.",
};

const formatToolName = (name: string) =>
  name
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

const toTeamUrl = (team: string) =>
  `${API_BASE_URL}/api/team/context?competition_id=${DEFAULT_COMPETITION_ID}&season_label=${encodeURIComponent(
    DEFAULT_SEASON_LABEL,
  )}&team_name=${encodeURIComponent(team)}`;

const makeId = () =>
  typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

export function ChatPanel() {
  const persona = useChatStore((state) => state.persona);
  const setPersona = useChatStore((state) => state.setPersona);
  const team = useChatStore((state) => state.team);
  const setTeam = useChatStore((state) => state.setTeam);
  const sessionId = useChatStore((state) => state.sessionId);
  const sessionIdRef = useRef<string | null>(sessionId);
  const setSessionId = useChatStore((state) => state.setSessionId);
  const messages = useChatStore((state) => state.messages);
  const addMessage = useChatStore((state) => state.addMessage);
  const updateMessage = useChatStore((state) => state.updateMessage);
  const clearMessages = useChatStore((state) => state.clearMessages);
  const chatError = useChatStore((state) => state.chatError);
  const setChatError = useChatStore((state) => state.setChatError);
  const isLoading = useChatStore((state) => state.isLoading);
  const setIsLoading = useChatStore((state) => state.setIsLoading);
  const setReportLoading = useChatStore((state) => state.setReportLoading);
  const compressLoading = useChatStore((state) => state.compressLoading);
  const setCompressLoading = useChatStore((state) => state.setCompressLoading);

  const { data: teamData, error: teamError, isLoading: loadingTeam, mutate } = useSWR(
    toTeamUrl(team),
    fetcher,
    {
      refreshInterval: 60_000,
    },
  );

  const teamContext = useMemo(() => {
    if (!teamData) return null;
    return {
      team_name: teamData.team_name,
      competition_name: teamData.competition_name,
      season_label: teamData.season_label,
      table_position: teamData.table_position,
      table_size: teamData.table_size,
      record: teamData.record,
      next_match: teamData.next_match,
      generated_at: teamData.generated_at ?? new Date().toISOString().split("T")[0],
      team_summary: teamData.team_summary,
    };
  }, [teamData]);

  const recordDisplay = useMemo(() => {
    const record = teamContext?.record;
    if (!record) {
      return "—";
    }
    const wins = typeof record.won === "number" ? record.won : 0;
    const draws = typeof record.drawn === "number" ? record.drawn : 0;
    const losses = typeof record.lost === "number" ? record.lost : 0;
    return `${wins}W-${draws}D-${losses}L`;
  }, [teamContext]);

  const nextMatchInfo = useMemo(() => {
    const nextMatch = teamContext?.next_match;
    if (!nextMatch) {
      return { opponent: "Opponent TBC", venue: "", date: "—" };
    }
    const opponent =
      typeof nextMatch.opponent === "string" && nextMatch.opponent.trim().length > 0
        ? nextMatch.opponent
        : "Opponent TBC";
    const venue =
      typeof nextMatch.venue === "string" && nextMatch.venue.trim().length > 0
        ? nextMatch.venue
        : "";
    const rawDate = typeof nextMatch.date === "string" ? nextMatch.date : undefined;
    let formattedDate = rawDate ?? "—";
    if (rawDate) {
      const parsed = new Date(rawDate);
      if (!Number.isNaN(parsed.getTime())) {
        formattedDate = parsed.toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        });
      }
    }
    return { opponent, venue, date: formattedDate };
  }, [teamContext]);

  const generatedAtDisplay = useMemo(() => {
    const generatedAt = teamContext?.generated_at;
    if (!generatedAt) {
      return null;
    }
    const parsed = new Date(generatedAt);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric" });
    }
    return generatedAt;
  }, [teamContext]);

  const activeToolNames = useMemo(() => {
    const names = new Set<string>();
    messages.forEach((message) => {
      message.toolCallNames?.forEach((name) => {
        if (name && name.trim().length > 0) {
          names.add(name);
        }
      });
      message.toolCalls?.forEach((call) => {
        const name = call.tool_name;
        if (name && name.trim().length > 0) {
          names.add(name);
        }
      });
    });
    return Array.from(names).slice(0, 4);
  }, [messages]);

  const messageCount = messages.length;
  const personaTheme = useMemo(() => {
    if (persona === "Analyst") {
      return {
        gradient: "from-white via-[#eef5ff] to-[#f7fbff]",
        activeButton: "border-[#0f172a] bg-[#0f172a] text-white shadow-[0_18px_38px_-24px_rgba(15,23,42,0.55)]",
        chip: "bg-[#e6eeff] text-[#1d4ed8]",
        statBorder: "border-[#dbe7ff]",
        statTint: "bg-[#f5f7ff]",
      } as const;
    }
    return {
      gradient: "from-white via-[#fff2e5] to-[#fff8f1]",
      activeButton: "border-[#7c2d12] bg-[#7c2d12] text-white shadow-[0_18px_38px_-24px_rgba(124,45,18,0.45)]",
      chip: "bg-[#ffe8d8] text-[#b45309]",
      statBorder: "border-[#fde3c7]",
      statTint: "bg-[#fff4ec]",
    } as const;
  }, [persona]);


  const toolExecutionEvents = useMemo(() => {
    const seen = new Set<string>();
    const events: ToolCall[] = [];
    messages.forEach((message) => {
      if (!Array.isArray(message.toolCalls)) {
        return;
      }
      message.toolCalls.forEach((call, index) => {
        const key =
          (call.id && typeof call.id === "string" && call.id.length > 0)
            ? call.id
            : `${call.tool_name}-${call.timestamp ?? index}`;
        if (seen.has(key)) {
          return;
        }
        seen.add(key);
        events.push(call);
      });
    });
    return events.sort((a, b) => {
      const timeA = a.timestamp ?? 0;
      const timeB = b.timestamp ?? 0;
      if (timeA === timeB) {
        return 0;
      }
      return timeB - timeA;
    });
  }, [messages]);

  const activeToolEvents = useMemo(
    () => toolExecutionEvents.filter((event) => event.status !== "completed"),
    [toolExecutionEvents],
  );

  const showToolTimeline = activeToolEvents.length > 0;

  const heroSummary = useMemo(() => {
    const summary = teamContext?.team_summary;
    if (!summary) {
      return personaDescriptions[persona];
    }
    if (typeof summary === "string") {
      return summary;
    }
    if (Array.isArray(summary)) {
      const textual = summary.filter((item) => typeof item === "string") as string[];
      if (textual.length > 0) {
        return textual.join(" • ");
      }
    }
    if (typeof summary === "object" && summary !== null) {
      const points =
        typeof summary.team_season_points === "number"
          ? `${summary.team_season_points} pts`
          : undefined;
      const goalDifferenceValue =
        typeof summary.goal_difference === "number"
          ? summary.goal_difference
          : typeof summary.team_season_gd === "number"
            ? summary.team_season_gd
            : undefined;
      const goalDifference =
        typeof goalDifferenceValue === "number"
          ? `${goalDifferenceValue >= 0 ? "+" : ""}${goalDifferenceValue} GD`
          : undefined;
      const xgFor =
        typeof summary.team_season_np_xg_pg === "number"
          ? summary.team_season_np_xg_pg
          : typeof summary.team_season_xg_pg === "number"
            ? summary.team_season_xg_pg
            : undefined;
      const xgAgainst =
        typeof summary.team_season_np_xg_conceded_pg === "number"
          ? summary.team_season_np_xg_conceded_pg
          : typeof summary.team_season_xg_per_sp_conceded === "number"
            ? summary.team_season_xg_per_sp_conceded
            : undefined;
      const aggression =
        typeof summary.team_season_aggression === "number"
          ? `${Math.round(summary.team_season_aggression * 100)}th percentile aggression`
          : undefined;
      const pace =
        typeof summary.team_season_pace_towards_goal === "number"
          ? `${summary.team_season_pace_towards_goal.toFixed(1)} m/s pace`
          : undefined;

      const snippets: string[] = [];
      if (points || goalDifference) {
        snippets.push(
          [`On ${points ?? "steady form"}`, goalDifference ? `with ${goalDifference}` : null]
            .filter(Boolean)
            .join(" "),
        );
      }
      if (typeof xgFor === "number" && typeof xgAgainst === "number") {
        snippets.push(
          `xG profile ${xgFor.toFixed(2)} for / ${xgAgainst.toFixed(2)} against per game`,
        );
      }
      if (pace) {
        snippets.push(`Transitions at ${pace}`);
      }
      if (aggression) {
        snippets.push(aggression);
      }

      if (snippets.length > 0) {
        return snippets.join(". ");
      }
    }
    return personaDescriptions[persona];
  }, [teamContext?.team_summary, persona]);

  const [inputValue, setInputValue] = useState("");
  const toolPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const chatContainerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

  const scrollToBottom = useCallback((instant = false, offset = 0) => {
    const container = chatContainerRef.current;
    if (!container) {
      return;
    }
    // Scroll to bottom with optional offset to keep some content visible
    const scrollTop = container.scrollHeight - container.clientHeight - offset;
    container.scrollTo({
      top: Math.max(0, scrollTop),
      behavior: instant ? "auto" : "smooth"
    });
  }, []);

  const convertResponseAttachments = useCallback(
    (value: unknown): ChatAttachment[] => {
      if (!Array.isArray(value)) {
        return [];
      }
      const attachments: ChatAttachment[] = [];
      const seen = new Set<string>();
      value.forEach((item) => {
        if (!item || typeof item !== "object") {
          return;
        }
        const record = item as Record<string, unknown>;
        if (record.type !== "image") {
          return;
        }
        const rawSrc = typeof record.src === "string" ? record.src.trim() : "";
        const rawPath = typeof record.path === "string" ? record.path.trim() : undefined;
        const alt =
          typeof record.alt === "string" && record.alt.length > 0 ? record.alt : undefined;
        let src = rawSrc;
        const normalizedPath =
          rawPath && rawPath.length > 0 ? rawPath.replace(/\\/g, "/") : undefined;
        if (!src) {
          if (normalizedPath) {
            src = `/api/viz?path=${encodeURIComponent(normalizedPath)}`;
          } else {
            return;
          }
        }
        const key = `${src}|${normalizedPath ?? ""}`;
        if (seen.has(key)) {
          return;
        }
        seen.add(key);
        attachments.push({
          id: makeId(),
          type: "image",
          src,
          path: normalizedPath,
          alt,
        });
      });
      return attachments;
    },
    [],
  );

  const extractAttachments = useCallback(
    (metadata: Record<string, unknown> | null | undefined): ChatAttachment[] => {
      if (!metadata) {
        return [];
      }
      const attachments: ChatAttachment[] = [];
      const seen = new Set<string>();
      const defaultAlt =
        typeof metadata.viz_type === "string" && metadata.viz_type.length > 0
          ? metadata.viz_type
          : undefined;

      const registerImagePath = (candidate: unknown, alt?: string) => {
        if (typeof candidate !== "string" || candidate.trim().length === 0) {
          return;
        }
        const normalized = candidate.replace(/\\/g, "/");
        const src = `/api/viz?path=${encodeURIComponent(normalized)}`;
        if (seen.has(src)) {
          return;
        }
        seen.add(src);
        attachments.push({
          id: makeId(),
          type: "image",
          src,
          path: normalized,
          alt,
        });
      };

      const registerImageData = (data: unknown, mime?: unknown, alt?: string) => {
        if (typeof data !== "string" || data.trim().length === 0) {
          return;
        }
        const trimmed = data.trim();
        const mediaType = typeof mime === "string" && mime.length > 0 ? mime : "image/png";
        const src = trimmed.startsWith("data:") ? trimmed : `data:${mediaType};base64,${trimmed}`;
        if (seen.has(src)) {
          return;
        }
        seen.add(src);
        attachments.push({
          id: makeId(),
          type: "image",
          src,
          alt,
        });
      };

      registerImagePath((metadata as Record<string, unknown>).image_path, defaultAlt);
      registerImageData((metadata as Record<string, unknown>).image_data, (metadata as Record<string, unknown>).image_mime_type, defaultAlt);

      const imagePaths = (metadata as Record<string, unknown>).image_paths;
      if (Array.isArray(imagePaths)) {
        imagePaths.forEach((item) => registerImagePath(item, defaultAlt));
      }

      const images = (metadata as Record<string, unknown>).images;
      if (Array.isArray(images)) {
        images.forEach((item) => {
          if (typeof item === "string") {
            registerImagePath(item, defaultAlt);
          } else if (item && typeof item === "object") {
            const maybePath = (item as Record<string, unknown>).path;
            const maybeAlt = (item as Record<string, unknown>).alt;
            const altText =
              typeof maybeAlt === "string" && maybeAlt.length > 0 ? maybeAlt : defaultAlt;
            if (maybePath) {
              registerImagePath(maybePath, altText);
            }
            const maybeData = (item as Record<string, unknown>).data;
            const maybeMime = (item as Record<string, unknown>).mime_type;
            if (maybeData) {
              registerImageData(maybeData, maybeMime, altText);
            }
          }
        });
      }

      return attachments;
    },
    [],
  );

  const mergeAttachments = useCallback(
    (primary: ChatAttachment[], secondary: ChatAttachment[]): ChatAttachment[] => {
      const seen = new Set<string>();
      const combined: ChatAttachment[] = [];
      const add = (attachment: ChatAttachment) => {
        const key = `${attachment.src}|${attachment.path ?? ""}`;
        if (seen.has(key)) {
          return;
        }
        seen.add(key);
        combined.push(attachment);
      };
      primary.forEach(add);
      secondary.forEach(add);
      return combined;
    },
    [],
  );

  const stopToolPolling = useCallback(() => {
    if (toolPollRef.current) {
      clearInterval(toolPollRef.current);
      toolPollRef.current = null;
    }
  }, []);

  const fetchToolCalls = useCallback(
    async (sessionKey: string, messageId: string) => {
      if (!sessionKey || !messageId) {
        return;
      }
      try {
        const response = await fetch(
          `/api/chat/tool-calls?sessionId=${encodeURIComponent(sessionKey)}`,
          { cache: "no-store" },
        );
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        const toolCalls = Array.isArray(payload.tool_calls) ? (payload.tool_calls as ToolCall[]) : [];
        const toolCallNames = toolCalls
          .map((call: any) => (typeof call?.tool_name === "string" ? call.tool_name : ""))
          .filter((name: string): name is string => Boolean(name));
        const uniqueNames = Array.from(new Set(toolCallNames));
        updateMessage(messageId, (message) => ({
          ...message,
          toolCallNames: uniqueNames,
          toolCalls: toolCalls.length > 0 ? toolCalls : message.toolCalls,
        }));
        // Don't scroll during tool polling - only on final message
      } catch (error) {
        console.error("Tool polling failed", error);
      }
    },
    [updateMessage],
  );

  const startToolPolling = useCallback(
    (sessionKey: string, messageId: string) => {
      if (!sessionKey || !messageId) {
        return;
      }
      stopToolPolling();

      const run = () => {
        void fetchToolCalls(sessionKey, messageId);
      };

      run();
      toolPollRef.current = setInterval(run, 1200);
    },
    [fetchToolCalls, stopToolPolling],
  );

  useEffect(() => {
    void mutate();
  }, [team, mutate]);

  useEffect(() => {
    return () => {
      stopToolPolling();
    };
  }, [stopToolPolling]);

  // Only auto-scroll when new messages are added (not on updates)
  const prevMessageCountRef = useRef(messages.length);
  useEffect(() => {
    if (messages.length > prevMessageCountRef.current) {
      // New message added - scroll smoothly
      scrollToBottom();
      prevMessageCountRef.current = messages.length;
    }
  }, [messages, scrollToBottom]);

  const resetConversation = useCallback(async () => {
    stopToolPolling();
    const activeSession = sessionIdRef.current;
    if (activeSession) {
      try {
        await fetch(`/api/chat?sessionId=${encodeURIComponent(activeSession)}`, {
          method: "DELETE",
        });
      } catch (error) {
        console.error("Failed to reset session", error);
      }
    }
    clearMessages();
    setSessionId(null);
    sessionIdRef.current = null;
    setChatError(null);
    setReportLoading(null);
    setCompressLoading(false);
  }, [clearMessages, setChatError, setSessionId, setReportLoading, setCompressLoading, stopToolPolling]);

  useEffect(() => {
    void resetConversation();
  }, [persona, team, resetConversation]);

  const compressConversation = useCallback(async () => {
    if (!sessionId) {
      setChatError("Start a chat before compressing the context.");
      return;
    }
    setCompressLoading(true);
    try {
      const response = await fetch("/api/chat/compress", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId, keep: 6 }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.error ?? "Compression failed.");
      }
      if (data.status === "skipped") {
        setChatError(data.reason ?? "Nothing to compress yet.");
        return;
      }
      const summary = typeof data.summary === "string" ? data.summary : "(summary unavailable)";
      const summaryMessage: ChatMessage = {
        id: makeId(),
        role: "system",
        content: `_${summary}_`,
      };
      addMessage(summaryMessage);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Compression failed.";
      setChatError(message);
    } finally {
      setCompressLoading(false);
    }
  }, [sessionId, addMessage, setChatError, setCompressLoading]);

  const sendChatMessage = async () => {
    const userContent = inputValue.trim();
    if (!userContent) {
      return;
    }

    let activeSession = sessionIdRef.current;
    if (!activeSession) {
      activeSession = typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : Math.random().toString(36).slice(2);
      sessionIdRef.current = activeSession;
      setSessionId(activeSession);
    }

    const userMessage: ChatMessage = {
      id: makeId(),
      role: "user",
      content: userContent,
    };

    setInputValue("");
    setIsLoading(true);
    setChatError(null);

    addMessage(userMessage);

    const assistantMessageId = makeId();
    addMessage({
      id: assistantMessageId,
      role: "assistant",
      content: "",
      statusHint: "thinking",
      toolCallNames: [],
    });

    startToolPolling(activeSession, assistantMessageId);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          persona,
          message: userContent,
          teamContext,
          sessionId: activeSession,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.error ?? "Agent execution error.");
      }

      const nextSessionId: string | null = data.session_id ?? activeSession;
      setSessionId(nextSessionId);
      sessionIdRef.current = nextSessionId;

      const replyText = typeof data.reply === "string" ? data.reply : JSON.stringify(data.reply ?? "");
      const metadata = data.metadata as Record<string, unknown> | undefined;
      const primaryAttachments = convertResponseAttachments(data.attachments);
      const metadataAttachments = extractAttachments(metadata);
      const attachments = mergeAttachments(primaryAttachments, metadataAttachments);
      const toolCalls = Array.isArray(data.tool_calls) ? (data.tool_calls as ToolCall[]) : [];

      updateMessage(assistantMessageId, (message) => {
        let finalContent = replyText.trim();
        if (!finalContent) {
          if (attachments.length > 0) {
            finalContent = "Generated visuals attached below.";
          } else if (toolCalls.length > 0) {
            finalContent = "Tool run completed.";
          } else {
            finalContent = "Agent finished with no textual reply.";
          }
        }
        return {
          ...message,
          content: finalContent,
          metadata,
          attachments: attachments.length > 0 ? attachments : undefined,
          toolCalls: toolCalls.length > 0 ? (toolCalls as ToolCall[]) : message.toolCalls,
          toolCallNames: undefined,
          streamingDone: true,
          statusHint: undefined,
        };
      });

      // Delay scroll to let images render and layout settle
      // Use multiple RAF to ensure DOM has fully updated
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setTimeout(() => {
            scrollToBottom(true); // instant scroll for final message

            // Backup scroll after images have loaded
            setTimeout(() => {
              scrollToBottom(true);
            }, 800);
          }, 100);
        });
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Agent execution error.";
      setChatError(message);
      updateMessage(assistantMessageId, (existing) => ({
        ...existing,
        content: message,
        streamingDone: true,
        toolCalls: undefined,
        toolCallNames: undefined,
        statusHint: undefined,
      }));
    } finally {
      stopToolPolling();
      setIsLoading(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (isLoading) {
      return;
    }
    await sendChatMessage();
  };

  return (
    <div className="relative mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 pb-16 pt-10 lg:px-8">
      <main
        className={cn(
          "relative flex min-h-[75vh] flex-1 flex-col overflow-hidden rounded-[40px]",
          "border border-white/30 bg-white/70 shadow-[0_45px_120px_-60px_rgba(15,23,42,0.32)] backdrop-blur-2xl"
        )}
      >
        <header
          className={cn(
            "relative flex flex-col gap-3 border-b border-white/30 px-5 py-4 sm:px-7 sm:py-5",
            "bg-gradient-to-br",
            personaTheme.gradient
          )}
        >
          <div className="flex flex-wrap items-center justify-between gap-3 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-500">
            <div className="flex items-center gap-2">
              <Badge
                variant="secondary"
                className="flex items-center gap-2 rounded-full border border-white/50 bg-white/75 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-600"
              >
                <Sparkles className="h-3.5 w-3.5 text-slate-500" />
                Intelligence Mode
              </Badge>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.3em]">
              <span className={cn("rounded-full px-3 py-1 shadow-sm", personaTheme.chip)}>
                {teamContext?.competition_name ?? "Competition TBD"}
              </span>
              <span className={cn("rounded-full px-3 py-1 shadow-sm", personaTheme.chip)}>
                Season {teamContext?.season_label ?? DEFAULT_SEASON_LABEL}
              </span>
              {generatedAtDisplay && (
                <span className="rounded-full border border-white/60 bg-white/70 px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-500">
                  Updated {generatedAtDisplay}
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="flex-1 min-w-[220px] space-y-4">
              <div className="flex flex-wrap gap-2">
                {(["Analyst", "Scouting Evaluator"] as Persona[]).map((option) => {
                  const isActive = persona === option;
                  return (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setPersona(option)}
                      className={cn(
                        "rounded-full px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.3em] transition",
                        "border border-white/60 bg-white/75 text-neutral-600 hover:bg-white",
                        isActive && personaTheme.activeButton
                      )}
                    >
                      {option}
                    </button>
                  );
                })}
              </div>

              <div className="space-y-2">
                <h1 className="text-2xl font-semibold tracking-tight text-neutral-900 md:text-3xl">
                  Precision reports for {teamContext?.team_name ?? team}
                </h1>
                <p className="max-w-2xl text-sm leading-snug text-neutral-600">
                  {heroSummary}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-600">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8 rounded-full border-transparent bg-white/70 px-3 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-600 shadow-[0_10px_24px_-20px_rgba(15,23,42,0.3)] transition hover:bg-white"
                  onClick={() => {
                    void resetConversation();
                  }}
                >
                  <ArrowRight className="mr-2 h-4 w-4 -rotate-45" />
                  New thread
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-8 rounded-full border-transparent bg-white/70 px-3 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-600 shadow-[0_10px_24px_-20px_rgba(15,23,42,0.3)] transition hover:bg-white"
                  onClick={() => {
                    void compressConversation();
                  }}
                  disabled={!sessionId || compressLoading}
                >
                  {compressLoading ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
                      Summarising…
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-slate-500" />
                      Summarise
                    </span>
                  )}
                </Button>
              </div>

              <div className="flex flex-wrap gap-1.5 overflow-x-auto pr-2 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-600">
                {PRESET_TEAMS.map((club) => {
                  const isActive = team === club;
                  return (
                    <button
                      key={club}
                      type="button"
                      onClick={() => setTeam(club)}
                      className={cn(
                        "rounded-full px-3 py-1 transition",
                        "border border-white/60 bg-white/75 hover:bg-white",
                        isActive && personaTheme.activeButton
                      )}
                    >
                      {club}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="w-full max-w-lg flex-shrink-0">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3 sm:gap-3">
                <div
                  className={cn(
                    "rounded-xl border p-4 backdrop-blur-sm shadow-[0_18px_38px_-32px_rgba(15,23,42,0.35)]",
                    personaTheme.statBorder,
                    personaTheme.statTint
                  )}
                >
                  <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.35em] text-neutral-500">
                    <TrendingUp className="h-3.5 w-3.5 text-slate-500" />
                    Season pulse
                  </div>
                  <p className="mt-3 text-lg font-semibold text-neutral-900">{recordDisplay}</p>
                  <p className="text-xs text-neutral-500">
                    {teamContext?.season_label ?? DEFAULT_SEASON_LABEL}
                  </p>
                </div>
                <div
                  className={cn(
                    "rounded-xl border p-4 backdrop-blur-sm shadow-[0_18px_38px_-32px_rgba(15,23,42,0.35)]",
                    personaTheme.statBorder,
                    personaTheme.statTint
                  )}
                >
                  <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.35em] text-neutral-500">
                    <CalendarDays className="h-3.5 w-3.5 text-slate-500" />
                    Next fixture
                  </div>
                  <p className="mt-3 text-sm font-semibold text-neutral-900">{nextMatchInfo.opponent}</p>
                  <p className="text-xs text-neutral-600">{nextMatchInfo.date}</p>
                  {nextMatchInfo.venue && (
                    <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-500">
                      {nextMatchInfo.venue}
                    </p>
                  )}
                </div>
                <div
                  className={cn(
                    "rounded-xl border p-4 backdrop-blur-sm shadow-[0_18px_38px_-32px_rgba(15,23,42,0.35)]",
                    personaTheme.statBorder,
                    personaTheme.statTint
                  )}
                >
                  <div className="flex items-center gap-2 text-[9px] font-semibold uppercase tracking-[0.35em] text-neutral-500">
                    <MessageCircle className="h-3.5 w-3.5 text-slate-500" />
                    Session signal
                  </div>
                  <p className="mt-3 text-lg font-semibold text-neutral-900">{messageCount}</p>
                  <p className="text-xs text-neutral-500">Messages in thread</p>
                  <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.3em] text-neutral-500">
                    {activeToolEvents.length > 0
                      ? `${activeToolEvents.length} tool${activeToolEvents.length === 1 ? "" : "s"} running`
                      : "Tools idle"}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </header>

        {showToolTimeline && (
          <div className="px-8 pt-4">
            <ToolExecutionTimeline toolCalls={activeToolEvents} />
          </div>
        )}

        {loadingTeam && <p className="px-8 pt-3 text-xs text-neutral-500">Refreshing team context…</p>}
        {teamError && (
          <p className="px-8 text-xs text-red-500">Team context error: {teamError.message}</p>
        )}

        <div
          ref={chatContainerRef}
          className="relative flex flex-1 flex-col gap-5 overflow-y-auto px-8 py-6 pb-12 scrollbar-thin"
        >
          {messages.length === 0 && (
            <div className="relative mx-auto max-w-xl overflow-hidden rounded-3xl border border-white/40 bg-white/85 px-8 py-10 text-center text-sm text-neutral-600 shadow-[0_16px_35px_-24px_rgba(15,23,42,0.2)]">
              <p className="text-base font-semibold text-neutral-900">
                Launch a scouting prompt to get curated intelligence.
              </p>
              <p className="mt-3 leading-relaxed">
                Blend offline indexes, StatsBomb event detail, and bespoke visualisations without
                leaving the conversation.
              </p>
              <div className="mt-4 flex justify-center gap-2 text-[11px] font-semibold uppercase tracking-[0.25em] text-neutral-500">
                <span>Context memory</span>
                <span>•</span>
                <span>Advanced viz</span>
                <span>•</span>
                <span>Tool traces</span>
              </div>
            </div>
          )}
          {messages.map((message, index) => (
            <MessageBubble
              key={message.id}
              role={message.role as "user" | "assistant" | "system"}
              content={message.content}
              statusHint={message.statusHint}
              toolCallNames={message.toolCallNames}
              planPreview={message.planPreview}
              attachments={message.attachments}
              toolCalls={message.toolCalls}
              onImagesLoaded={() => {
                if (index === messages.length - 1) {
                  scrollToBottom(true, 100);
                }
              }}
            />
          ))}
          {chatError && (
            <div className="rounded-lg border border-red-500 bg-red-50 px-3 py-2 text-sm text-red-600">
              Chat error: {chatError}
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="border-t border-white/35 bg-white/75 px-6 py-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <Textarea
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="Frame a match-day hypothesis or ask for a scouting breakdown…"
              className="h-28 flex-1 resize-none rounded-2xl border-slate-200 bg-white text-sm text-neutral-900 shadow-inner placeholder:text-neutral-500 focus:border-slate-400 focus:ring-2 focus:ring-slate-200"
            />
            <Button
              type="submit"
              disabled={isLoading}
              size="lg"
              className="flex h-14 items-center justify-center gap-2 rounded-2xl bg-slate-900 px-10 text-base font-semibold text-white shadow-[0_16px_28px_-18px_rgba(15,23,42,0.45)] transition hover:bg-slate-800 disabled:bg-slate-400"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" /> Sending…
                </>
              ) : (
                <>
                  Send
                  <Send className="h-5 w-5" />
                </>
              )}
            </Button>
          </div>
        </form>
      </main>
    </div>
  );
}
