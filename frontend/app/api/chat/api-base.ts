import { API_BASE_URL } from "@/lib/constants";

export const resolveApiBase = () =>
  process.env.AGENTSPACE_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? API_BASE_URL;
