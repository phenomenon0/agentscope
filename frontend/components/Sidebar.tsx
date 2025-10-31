import { Persona, PRESET_TEAMS } from "@/lib/constants";
import { format } from "date-fns";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Sparkles, Target, Users, TrendingUp, CalendarDays } from "lucide-react";

type MatchRow = {
  date?: string;
  opponent?: string;
  venue?: string;
  result?: string | null;
  score?: string | null;
};

type TableRow = {
  team_name?: string;
  position?: number;
  team_season_points?: number;
};

type RosterRow = {
  player_name?: string;
  position?: string | null;
  minutes?: number;
  goals?: number;
  assists?: number;
  value?: number | string | null;
};

type SidebarProps = {
  persona: Persona;
  onPersonaChange: (persona: Persona) => void;
  team: string;
  onTeamChange: (team: string) => void;
  teamName?: string | null;
  competitionName?: string | null;
  seasonLabel?: string | null;
  tablePosition?: number | null;
  tableSize?: number | null;
  record?: Record<string, number> | null;
  nextMatch?: MatchRow | null;
  generatedAt?: string | null;
  table?: TableRow[] | null;
  roster?: RosterRow[] | null;
  played?: MatchRow[] | null;
  upcoming?: MatchRow[] | null;
  topStats?: Record<string, RosterRow[]> | null;
  onPlayerReport?: (player: RosterRow) => void;
  reportLoading?: string | null;
};

const personaCopy: Record<Persona, string> = {
  Analyst: "Rapid data takes grounded in StatsBomb metrics.",
  "Scouting Evaluator": "Deep scouting synthesis with comps and tactical fit.",
};

export function Sidebar({
  persona,
  onPersonaChange,
  team,
  onTeamChange,
  teamName,
  competitionName,
  seasonLabel,
  tablePosition,
  tableSize,
  record,
  nextMatch,
  generatedAt,
  table,
  roster,
  played,
  upcoming,
  topStats,
  onPlayerReport,
  reportLoading,
}: SidebarProps) {
  const wins = record?.won ?? 0;
  const draws = record?.drawn ?? 0;
  const losses = record?.lost ?? 0;
  const formattedDate =
    nextMatch?.date && typeof nextMatch.date === "string"
      ? format(new Date(nextMatch.date), "d MMM")
      : undefined;
  const shortTable = (table ?? []).slice(0, 6);
  const trimmedRoster = (roster ?? []).slice(0, 12);
  const trimmedUpcoming = (upcoming ?? []).slice(0, 5);
  const trimmedPlayed = (played ?? []).slice(0, 5);
  const highlightGroups = topStats ?? {};

  const cardClass = "glass-panel relative overflow-hidden rounded-[28px] p-6";

  return (
    <aside className="flex w-full flex-col gap-6 lg:w-[360px]">
      <section className={cardClass}>
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/40 via-transparent to-slate-100/30" />
        <div className="relative flex items-center justify-between gap-3">
          <div className="space-y-2">
            <Badge
              variant="secondary"
              className="flex w-max items-center gap-2 border border-white/40 bg-white/70 text-[11px] font-semibold uppercase tracking-[0.3em] text-neutral-600"
            >
              <Sparkles className="h-3.5 w-3.5 text-slate-500" /> Persona
            </Badge>
            <p className="text-lg font-semibold text-neutral-900">{persona}</p>
            <p className="max-w-[220px] text-sm text-neutral-600">{personaCopy[persona]}</p>
          </div>
          <div className="flex flex-col gap-2">
            {(["Analyst", "Scouting Evaluator"] as Persona[]).map((option) => {
              const active = persona === option;
              return (
                <button
                  key={option}
                  type="button"
                  onClick={() => onPersonaChange(option)}
                  className={cn(
                    "rounded-full px-4 py-2 text-xs font-semibold uppercase tracking-wide transition",
                    "border border-white/50 bg-white/80 text-neutral-600 transition hover:bg-white",
                    active && "border-slate-900 bg-slate-900 text-white shadow-[0_10px_28px_-14px_rgba(15,23,42,0.45)]"
                  )}
                >
                  {option}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      <section className={cardClass}>
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/45 via-transparent to-slate-100/35" />
        <div className="relative space-y-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <Badge
                variant="secondary"
                className="mb-3 flex w-max items-center gap-2 border border-white/40 bg-white/70 text-[10px] font-semibold uppercase tracking-[0.35em] text-neutral-600"
              >
                <Target className="h-3.5 w-3.5 text-slate-500" /> Team Focus
              </Badge>
              <p className="text-xl font-semibold text-neutral-900">{teamName ?? team}</p>
              <p className="text-sm text-neutral-600">
                {competitionName ?? "Competition"} · {seasonLabel ?? "Season tbc"}
              </p>
            </div>
            <div className="grid gap-2">
              {PRESET_TEAMS.map((club) => {
                const active = team === club;
                return (
                  <button
                    key={club}
                    type="button"
                    onClick={() => onTeamChange(club)}
                    className={cn(
                      "rounded-full px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide transition",
                      "border border-white/50 bg-white/80 text-neutral-600 hover:bg-white",
                      active && "border-slate-900 bg-slate-900 text-white shadow-[0_12px_24px_-18px_rgba(17,24,39,0.45)]"
                    )}
                  >
                    {club}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4 text-center">
            <div className="rounded-2xl border border-white/30 bg-white/40 p-3 backdrop-blur">
              <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-neutral-500">Table</p>
              <p className="mt-2 text-lg font-semibold text-neutral-900">
                {tablePosition ? `${tablePosition}/${tableSize ?? "?"}` : "—"}
              </p>
            </div>
            <div className="rounded-2xl border border-white/30 bg-white/40 p-3 backdrop-blur">
              <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-neutral-500">Record</p>
              <p className="mt-2 text-lg font-semibold text-neutral-900">
                {wins}W-{draws}D-{losses}L
              </p>
            </div>
            <div className="rounded-2xl border border-white/30 bg-white/40 p-3 backdrop-blur">
              <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-neutral-500">Next</p>
              <p className="mt-2 text-lg font-semibold text-neutral-900">
                {formattedDate ?? "TBC"}
              </p>
              <p className="text-xs text-neutral-500">{nextMatch?.opponent ?? "Opponent tbc"}</p>
            </div>
          </div>

          {generatedAt && (
            <p className="text-xs uppercase tracking-[0.35em] text-neutral-400">
              Updated {generatedAt}
            </p>
          )}
        </div>
      </section>

      {shortTable.length > 0 && (
        <section className={cardClass}>
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/45 via-transparent to-slate-100/35" />
          <div className="relative space-y-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.35em] text-neutral-500">
              <TrendingUp className="h-3.5 w-3.5 text-slate-500" />
              League Snapshot
            </div>
            <ul className="space-y-2 text-sm text-neutral-700">
              {shortTable.map((row) => (
                <li
                  key={`${row.team_name}-${row.position}`}
                  className={cn(
                    "flex items-center justify-between rounded-2xl border border-white/30 px-4 py-3 text-sm font-medium transition",
                    "bg-white/45 backdrop-blur hover:bg-white/60",
                    row.team_name === teamName && "border-transparent bg-gradient-to-r from-neutral-900 to-slate-900 text-white hover:brightness-110"
                  )}
                >
                  <span>
                    {row.position ?? "—"}. {row.team_name ?? "Team"}
                  </span>
                  <span className="text-xs text-neutral-500">
                    {typeof row.team_season_points === "number"
                      ? `${row.team_season_points} pts`
                      : "—"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      )}

      {Object.values(highlightGroups).some((items) => (items ?? []).length > 0) && (
        <section className={cardClass}>
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/45 via-transparent to-slate-100/35" />
          <div className="relative space-y-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.35em] text-neutral-500">
              <Users className="h-3.5 w-3.5 text-slate-500" />
              Top Performers
            </div>
            <div className="grid gap-3 text-sm text-neutral-700 sm:grid-cols-3">
              {(
                [
                  ["goals", "Goals"],
                  ["assists", "Assists"],
                  ["minutes", "Minutes"],
                ] as const
              ).map(([key, label]) => {
                const entries = highlightGroups[key] ?? [];
                if (!entries.length) {
                  return (
                    <div
                      key={key}
                      className="rounded-2xl border border-white/30 bg-white/40 p-4 text-center text-xs text-neutral-400 backdrop-blur"
                    >
                      {label}
                      <p className="mt-2 text-neutral-400">No data</p>
                    </div>
                  );
                }
                return (
                  <div key={key} className="rounded-2xl border border-white/30 bg-white/45 p-4 backdrop-blur">
                    <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                      {label}
                    </p>
                    <ul className="mt-3 space-y-2">
                      {entries.map((entry) => (
                        <li key={`${key}-${entry.player_name}`} className="flex items-center justify-between text-xs text-neutral-700">
                          <span className="font-semibold text-neutral-900">{entry.player_name}</span>
                          <span className="text-neutral-500">{entry.value ?? 0}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {trimmedRoster.length > 0 && (
        <section className={cardClass}>
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/45 via-transparent to-slate-100/35" />
          <div className="relative space-y-4">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.35em] text-neutral-500">
              <Users className="h-3.5 w-3.5 text-slate-500" />
              Key Squad Minutes
            </div>
            <div className="space-y-3 text-sm text-neutral-700">
              {trimmedRoster.map((player) => (
                <div
                  key={player.player_name}
                  className="flex items-center justify-between rounded-2xl border border-white/30 bg-white/45 px-4 py-3 backdrop-blur"
                >
                  <div>
                    <p className="font-semibold text-neutral-800">{player.player_name}</p>
                    <p className="text-xs text-neutral-500">
                      {player.position ?? "Role"} · {player.minutes ?? 0}′
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <p className="text-xs font-semibold text-neutral-500">
                      ⚽ {player.goals ?? 0} · 🎯 {player.assists ?? 0}
                    </p>
                    {onPlayerReport && player.player_name && (
                      <button
                        type="button"
                        onClick={() => onPlayerReport(player)}
                        disabled={reportLoading === player.player_name}
                        className={cn(
                          "rounded-full px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-white",
                          "bg-slate-900 shadow-[0_12px_26px_-20px_rgba(15,23,42,0.45)] transition hover:bg-slate-800",
                          "disabled:cursor-not-allowed disabled:bg-slate-400"
                        )}
                      >
                        {reportLoading === player.player_name ? "Loading…" : "Report"}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {(trimmedUpcoming.length > 0 || trimmedPlayed.length > 0) && (
        <section className={cn(cardClass, "divide-y divide-white/25")}
        >
          {trimmedUpcoming.length > 0 && (
            <div className="space-y-4 p-6">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.35em] text-neutral-500">
                <CalendarDays className="h-3.5 w-3.5 text-slate-500" />
                Upcoming Fixtures
              </div>
              <ul className="space-y-3 text-sm text-neutral-700">
                {trimmedUpcoming.map((match, index) => (
                  <li
                    key={`upcoming-${index}`}
                    className="rounded-2xl border border-white/40 bg-white/80 px-4 py-3"
                  >
                    <p className="font-semibold text-neutral-800">
                      {match.opponent ?? "Opponent"}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {match.date ? format(new Date(match.date), "d MMM") : "Date tbc"} · {match.venue ?? "Venue tbc"}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {trimmedPlayed.length > 0 && (
            <div className="space-y-4 p-6">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.35em] text-neutral-500">
                <CalendarDays className="h-3.5 w-3.5 text-slate-500" />
                Recent Results
              </div>
              <ul className="space-y-3 text-sm text-neutral-700">
                {trimmedPlayed.map((match, index) => (
                  <li
                    key={`played-${index}`}
                    className="rounded-2xl border border-white/40 bg-white/80 px-4 py-3"
                  >
                    <p className="font-semibold text-neutral-800">
                      {match.opponent ?? "Opponent"} · {match.score ?? "Score tbc"}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {match.date ? format(new Date(match.date), "d MMM") : "Date tbc"} · {match.venue ?? "Venue"}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}
    </aside>
  );
}
