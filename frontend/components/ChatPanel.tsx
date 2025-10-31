"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
import { Sparkles, ArrowRight, Loader2, Send } from "lucide-react";
import {
  Persona,
  API_BASE_URL,
  DEFAULT_COMPETITION_ID,
  DEFAULT_SEASON_LABEL,
} from "@/lib/constants";
import { Sidebar } from "./Sidebar";
import { MessageBubble } from "./MessageBubble";
import {
  ChatAttachment,
  ChatMessage,
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

const toTeamUrl = (team: string) =>
  `${API_BASE_URL}/api/team/context?competition_id=${DEFAULT_COMPETITION_ID}&season_label=${encodeURIComponent(
    DEFAULT_SEASON_LABEL,
  )}&team_name=${encodeURIComponent(team)}`;

const makeId = () =>
  typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : Math.random().toString(36).slice(2);

type RosterEntry = {
  player_name?: string;
  position?: string | null;
  minutes?: number | null;
  goals?: number | null;
  assists?: number | null;
};

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
  const reportLoading = useChatStore((state) => state.reportLoading);
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
        const toolCalls = Array.isArray(payload.tool_calls) ? payload.tool_calls : [];
        const toolCallNames = toolCalls
          .map((call: any) => (typeof call?.tool_name === "string" ? call.tool_name : ""))
          .filter((name: string): name is string => Boolean(name));
        const uniqueNames = Array.from(new Set(toolCallNames));
        updateMessage(messageId, (message) => ({
          ...message,
          toolCallNames: uniqueNames,
          toolCalls: undefined,
        }));
        // Don't scroll during tool polling - only on final message
      } catch (error) {
        console.error("Tool polling failed", error);
      }
    },
    [updateMessage, scrollToBottom],
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

  const handlePlayerReport = useCallback(
    async (player: RosterEntry) => {
      const playerName = player.player_name;
      if (!playerName) {
        return;
      }
      const season = teamContext?.season_label ?? DEFAULT_SEASON_LABEL;
      const competitionId = teamData?.competition_id ?? DEFAULT_COMPETITION_ID;

      setReportLoading(playerName);
      try {
        const params = new URLSearchParams({
          player_name: playerName,
          season_label: season,
        });
        if (competitionId) {
          params.set("competition_id", String(competitionId));
        }

        const response = await fetch(`/api/player/report?${params.toString()}`);
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data?.error ?? "Unable to build player report.");
        }

        const highlights = (data.highlights ?? []) as Array<{ label?: string; value?: number }>;
        const metrics = (data.metrics ?? {}) as Record<string, unknown>;

        let markdown = `### Player Snapshot: ${data.player_name ?? playerName}`;
        markdown += `\n- Team: ${data.team_name ?? "n/a"}`;
        markdown += `\n- Season: ${data.season_label ?? season}`;

        if (highlights.length) {
          markdown += "\n\n**Highlights**\n";
          for (const item of highlights) {
            markdown += `- ${item.label ?? "Metric"}: ${item.value ?? 0}\n`;
          }
        }

        const keyMetrics = [
          ["player_season_minutes", "Minutes"],
          ["player_season_goals", "Goals"],
          ["player_season_assists", "Assists"],
          ["player_season_xg", "xG"],
          ["player_season_xa", "xA"],
          ["player_season_shots", "Shots"],
        ] as const;

        const metricLines = keyMetrics
          .map(([key, label]) => {
            const value = metrics[key];
            if (value === null || value === undefined || value === "") {
              return null;
            }
            return `- ${label}: ${value}`;
          })
          .filter(Boolean);

        if (metricLines.length) {
          markdown += "\n**Key Season Metrics**\n" + metricLines.join("\n") + "\n";
        }

        const assistantMessage: ChatMessage = {
          id: makeId(),
          role: "assistant",
          content: markdown,
        };
        addMessage(assistantMessage);
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to generate player report.";
        setChatError(message);
      } finally {
        setReportLoading(null);
      }
    },
    [teamContext?.season_label, teamData?.competition_id, addMessage, setChatError, setReportLoading],
  );

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
      const toolCalls = Array.isArray(data.tool_calls) ? data.tool_calls : [];

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
          toolCalls: undefined,
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
    <div className="relative mx-auto flex w-full max-w-7xl flex-col gap-8 px-4 pb-12 pt-10 lg:flex-row lg:px-8">

      <Sidebar
        persona={persona}
        onPersonaChange={setPersona}
        team={team}
        onTeamChange={setTeam}
        teamName={teamContext?.team_name}
        competitionName={teamContext?.competition_name}
        seasonLabel={teamContext?.season_label}
        tablePosition={teamContext?.table_position}
        tableSize={teamContext?.table_size}
        record={teamContext?.record}
        nextMatch={teamContext?.next_match}
        generatedAt={teamContext?.generated_at}
        table={teamData?.table ?? null}
        roster={teamData?.roster_table ?? null}
        played={teamData?.matches_played ?? null}
        upcoming={teamData?.matches_upcoming ?? null}
        topStats={teamData?.top_stats ?? null}
        onPlayerReport={handlePlayerReport}
        reportLoading={reportLoading}
      />

      <main
        className={cn(
          "glass-panel relative flex h-[calc(100vh-4.5rem)] flex-1 flex-col overflow-hidden",
          "rounded-[28px]"
        )}
      >
        <header className="relative border-b border-white/40 bg-white/70 px-8 py-7 backdrop-blur">
          <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-3">
              <Badge
                variant="secondary"
                className="flex w-max items-center gap-2 border border-white/40 bg-white/70 text-xs font-medium uppercase tracking-[0.2em] text-neutral-600"
              >
                <Sparkles className="h-3.5 w-3.5 text-slate-500" />
                Live Analytics Workspace
              </Badge>
              <div>
                <h1 className="text-2xl font-semibold text-neutral-900 lg:text-3xl">Chat Workspace</h1>
                <p className="mt-2 max-w-xl text-sm text-neutral-600">
                  {persona === "Analyst"
                    ? "📊 Rapid data takes synthesised into slick Markdown dashboards with context-rich tool traces."
                    : "🧠 Scouting-grade breakdowns with comps, action archetypes, and tactical alignments drawn from your tool calls."}
                </p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 rounded-full border-slate-300 bg-white/70 text-neutral-700 transition hover:bg-white"
                onClick={() => {
                  void resetConversation();
                }}
              >
                <ArrowRight className="mr-2 h-4 w-4 -rotate-45" />
                Reset conversation
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9 rounded-full border-slate-300 bg-white/70 text-neutral-700 transition hover:bg-white"
                onClick={() => {
                  void compressConversation();
                }}
                disabled={!sessionId || compressLoading}
              >
                {compressLoading ? (
                  <span className="flex items-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-slate-500" />
                    Compressing…
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-slate-500" />
                    Compress & continue
                  </span>
                )}
              </Button>
            </div>
          </div>
        </header>

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
              <p className="text-base font-semibold text-neutral-900">Ask about players, fixtures, or scouting fit.</p>
              <p className="mt-3 leading-relaxed">
                The workspace orchestrates offline indexes, live StatsBomb, and Wyscout layers before surfacing a polished, citeable answer.
              </p>
              <div className="mt-4 flex justify-center gap-2 text-[11px] font-semibold uppercase tracking-[0.25em] text-neutral-500">
                <span>Offline Index</span>
                <span>•</span>
                <span>Advanced Viz</span>
                <span>•</span>
                <span>Web Sanity</span>
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
                // For the last message, scroll to bottom with some breathing room
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

        <form onSubmit={handleSubmit} className="border-t border-white/40 bg-white/70 px-6 py-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <Textarea
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="Ask about Bukayo Saka's execution range or scouting fit…"
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
