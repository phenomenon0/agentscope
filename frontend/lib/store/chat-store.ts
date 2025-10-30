"use client";

import { create } from "zustand";
import { Persona, PRESET_TEAMS } from "@/lib/constants";

export type ChatAttachment = {
  id: string;
  type: "image";
  src: string;
  path?: string;
  alt?: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  planPreview?: boolean;
  streamingDone?: boolean;
  attachments?: ChatAttachment[];
  metadata?: Record<string, unknown>;
};

type ChatState = {
  persona: Persona;
  team: string;
  sessionId: string | null;
  messages: ChatMessage[];
  chatError: string | null;
  isLoading: boolean;
  reportLoading: string | null;
  compressLoading: boolean;
  setPersona: (persona: Persona) => void;
  setTeam: (team: string) => void;
  setSessionId: (sessionId: string | null) => void;
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, updater: (message: ChatMessage) => ChatMessage) => void;
  clearMessages: () => void;
  setChatError: (message: string | null) => void;
  setIsLoading: (isLoading: boolean) => void;
  setReportLoading: (player: string | null) => void;
  setCompressLoading: (loading: boolean) => void;
};

export const useChatStore = create<ChatState>((set) => ({
  persona: "Analyst",
  team: PRESET_TEAMS[0],
  sessionId: null,
  messages: [],
  chatError: null,
  isLoading: false,
  reportLoading: null,
  compressLoading: false,
  setPersona: (persona) => set({ persona }),
  setTeam: (team) => set({ team }),
  setSessionId: (sessionId) => set({ sessionId }),
  addMessage: (message) =>
    set((state) => ({
      messages: [...state.messages, message],
    })),
  updateMessage: (id, updater) =>
    set((state) => ({
      messages: state.messages.map((message) =>
        message.id === id ? updater(message) : message,
      ),
    })),
  clearMessages: () => set({ messages: [] }),
  setChatError: (chatError) => set({ chatError }),
  setIsLoading: (isLoading) => set({ isLoading }),
  setReportLoading: (player) => set({ reportLoading: player }),
  setCompressLoading: (compressLoading) => set({ compressLoading }),
}));
