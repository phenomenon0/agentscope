"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import useSWR from "swr";
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
  const plannerAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    sessionIdRef.current = sessionId;
  }, [sessionId]);

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

  useEffect(() => {
    void mutate();
  }, [team, mutate]);

  const resetConversation = useCallback(async () => {
    if (plannerAbortRef.current) {
      plannerAbortRef.current.abort();
      plannerAbortRef.current = null;
    }
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
    setChatError(null);
    setReportLoading(null);
    setCompressLoading(false);
  }, [clearMessages, setChatError, setSessionId, setReportLoading, setCompressLoading]);

  useEffect(() => {
    void resetConversation();
  }, [persona, team, resetConversation]);

  const streamPlanPreview = useCallback(
    async (
      previewId: string,
      payload: { persona: Persona; message: string; teamContext: typeof teamContext },
    ) => {
      plannerAbortRef.current?.abort();
      const controller = new AbortController();
      plannerAbortRef.current = controller;

      const placeholder = "Gathering plan from Claude Haiku…";
      let accumulated = placeholder;
      const updateContent = (content: string, done = false) => {
        updateMessage(previewId, (msg) => ({
          ...msg,
          content,
          planPreview: true,
          streamingDone: done,
        }));
      };

      updateContent(accumulated);

      try {
        const response = await fetch("/api/chat/plan-preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            persona: payload.persona,
            message: payload.message,
            teamContext: payload.teamContext,
          }),
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          const fallbackText = await response.text().catch(() => "Plan preview unavailable.");
          throw new Error(fallbackText || "Plan preview unavailable.");
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) {
            break;
          }
          buffer += decoder.decode(value, { stream: true });
          let delimiterIndex: number;
          while ((delimiterIndex = buffer.indexOf("\n\n")) !== -1) {
            const rawChunk = buffer.slice(0, delimiterIndex).trim();
            buffer = buffer.slice(delimiterIndex + 2);
            if (!rawChunk.startsWith("data:")) {
              continue;
            }
            const payloadText = rawChunk.slice(5).trim();
            if (!payloadText) {
              continue;
            }
            if (payloadText === "[DONE]") {
              updateContent(accumulated, true);
              plannerAbortRef.current = null;
              return;
            }
            const stripped = payloadText.replace(/^\*+|\*+$/g, "").trim();
            if (!stripped) {
              continue;
            }
            accumulated =
              accumulated === placeholder || !accumulated ? stripped : `${accumulated}\n${stripped}`;
            updateContent(accumulated);
          }
        }

        updateContent(accumulated, true);
      } catch (error) {
        if (!controller.signal.aborted) {
          const message =
            error instanceof Error ? error.message : "Plan preview unavailable.";
          updateContent(`Plan preview unavailable: ${message}`, true);
        }
      } finally {
        if (plannerAbortRef.current === controller) {
          plannerAbortRef.current = null;
        }
      }
    },
    [updateMessage],
  );

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
    if (!inputValue.trim()) {
      return;
    }

    const userContent = inputValue.trim();
    const userMessage: ChatMessage = {
      id: makeId(),
      role: "user",
      content: userContent,
    };

    setInputValue("");
    setIsLoading(true);
    setChatError(null);

    const previewId = makeId();
    addMessage(userMessage);
    addMessage({
      id: previewId,
      role: "assistant",
      content: "Gathering plan from Claude Haiku…",
      planPreview: true,
    });

    void streamPlanPreview(previewId, { persona, message: userContent, teamContext });

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          persona,
          message: userContent,
          teamContext,
          sessionId,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data?.error ?? "Agent execution error.");
      }

      setSessionId(data.session_id ?? null);
      const replyText = typeof data.reply === "string" ? data.reply : JSON.stringify(data.reply ?? "");
      const metadata = data.metadata as Record<string, unknown> | undefined;
      const primaryAttachments = convertResponseAttachments(data.attachments);
      const metadataAttachments = extractAttachments(metadata);
      const attachments = mergeAttachments(primaryAttachments, metadataAttachments);
      const toolCalls = Array.isArray(data.tool_calls) ? data.tool_calls : [];

      const assistantMessage: ChatMessage = {
        id: makeId(),
        role: "assistant",
        content: replyText,
        metadata,
        ...(attachments.length > 0 ? { attachments } : {}),
        ...(toolCalls.length > 0 ? { toolCalls } : {}),
      };
      addMessage(assistantMessage);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Agent execution error.";
      setChatError(message);
    } finally {
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
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-6 lg:flex-row">
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

      <main className="flex h-[calc(100vh-3rem)] flex-1 flex-col overflow-hidden rounded-3xl border border-neutral-200 bg-white shadow-xl shadow-black/5">
        <header className="flex items-start justify-between gap-4 border-b border-neutral-200 bg-neutral-50 px-6 py-5">
          <div>
            <h1 className="text-xl font-semibold text-neutral-900">Chat Workspace</h1>
            <p className="text-sm text-neutral-500">
            {persona === "Analyst"
              ? "📊 Rapid data responses with Markdown summaries."
              : "🧠 Deep scouting breakdown with comparisons, tactical deployment, and development notes."}
          </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => {
                void resetConversation();
              }}
              className="rounded-lg border border-neutral-300 px-3 py-2 text-xs font-medium text-neutral-600 hover:border-neutral-400 hover:text-neutral-800"
            >
              Reset conversation
            </button>
            <button
              type="button"
              onClick={() => {
                void compressConversation();
              }}
              disabled={!sessionId || compressLoading}
              className="rounded-lg border border-neutral-300 px-3 py-2 text-xs font-medium text-neutral-600 hover:border-neutral-400 hover:text-neutral-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {compressLoading ? "Compressing…" : "Compress & continue"}
            </button>
          </div>
        </header>

        {loadingTeam && <p className="px-6 pt-2 text-xs text-neutral-400">Refreshing team context…</p>}
        {teamError && (
          <p className="px-6 text-xs text-red-500">Team context error: {teamError.message}</p>
        )}

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto px-6 py-4 scrollbar-thin bg-white">
          {messages.length === 0 && (
            <div className="mx-auto max-w-xl rounded-2xl border border-dashed border-neutral-300 bg-neutral-50 p-6 text-center text-sm text-neutral-600">
              <p className="text-base font-semibold text-neutral-900">
                Ask about players, fixtures, or scouting fit.
              </p>
              <p className="mt-2">
                The assistant automatically pulls the latest {team} data and can cross-check
                live info with the web search tool if something looks off.
              </p>
            </div>
          )}
          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              role={message.role as "user" | "assistant" | "system"}
              content={message.content}
              planPreview={message.planPreview}
              attachments={message.attachments}
              toolCalls={message.toolCalls}
            />
          ))}
          {chatError && (
            <div className="rounded-lg border border-red-500 bg-red-50 px-3 py-2 text-sm text-red-600">
              Chat error: {chatError}
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="border-t border-neutral-200 bg-neutral-50 p-4">
          <div className="flex items-end gap-3">
            <textarea
              value={inputValue}
              onChange={(event) => setInputValue(event.target.value)}
              placeholder="Ask about Bukayo Saka's execution range or scouting fit…"
              className="h-24 flex-1 resize-none rounded-2xl border border-neutral-300 bg-white px-4 py-3 text-sm text-neutral-900 outline-none transition focus:border-neutral-500 focus:shadow-lg focus:shadow-neutral-200"
            />
            <div className="flex flex-col gap-2">
              <button
                type="submit"
                disabled={isLoading}
                className="rounded-2xl bg-neutral-900 px-5 py-3 text-sm font-semibold text-white shadow-md transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isLoading ? "Sending…" : "Send"}
              </button>
            </div>
          </div>
        </form>
      </main>
    </div>
  );
}
