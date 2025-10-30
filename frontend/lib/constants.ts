export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const DEFAULT_COMPETITION_ID = 12; // Serie A default focus
export const DEFAULT_SEASON_LABEL = process.env.NEXT_PUBLIC_SEASON_LABEL ?? "2025/2026";
export const PRESET_TEAMS = ["Juventus", "Barcelona", "Bayer Leverkusen"] as const;

export type Persona = "Analyst" | "Scouting Evaluator";
