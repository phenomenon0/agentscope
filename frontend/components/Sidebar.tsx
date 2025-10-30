import { Persona, PRESET_TEAMS } from "@/lib/constants";
import { format } from "date-fns";

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

const accentClasses =
  "bg-white border border-neutral-200 shadow-sm shadow-black/5 rounded-2xl";

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

  return (
    <aside className="flex w-full flex-col gap-6 lg:w-96">
      <section className={`${accentClasses} p-6`}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
              Persona
            </h2>
            <p className="mt-1 text-base font-semibold text-neutral-900">{persona}</p>
            <p className="mt-1 text-sm text-neutral-500">{personaCopy[persona]}</p>
          </div>
          <div className="flex gap-2">
            {(["Analyst", "Scouting Evaluator"] as Persona[]).map((option) => {
              const active = persona === option;
              return (
                <button
                  key={option}
                  type="button"
                  onClick={() => onPersonaChange(option)}
                  className={`rounded-xl border px-3 py-2 text-xs font-medium transition ${
                    active
                      ? "border-neutral-900 bg-neutral-900 text-white shadow-sm"
                      : "border-neutral-200 bg-neutral-50 text-neutral-600 hover:border-neutral-300 hover:text-neutral-800"
                  }`}
                >
                  {option}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      <section className={`${accentClasses} p-6`}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
              Team Focus
            </h2>
            <p className="mt-1 text-xl font-semibold text-neutral-900">{teamName ?? team}</p>
            <p className="text-sm text-neutral-500">
              {competitionName ?? "Competition"} · {seasonLabel ?? "Season tbc"}
            </p>
          </div>
          <div className="flex flex-col gap-2">
            {PRESET_TEAMS.map((club) => {
              const active = team === club;
              return (
                <button
                  key={club}
                  type="button"
                  onClick={() => onTeamChange(club)}
                  className={`rounded-lg px-3 py-2 text-xs font-medium transition ${
                    active
                      ? "bg-neutral-900 text-white shadow-sm"
                      : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                  }`}
                >
                  {club}
                </button>
              );
            })}
          </div>
        </div>
        <div className="mt-4 grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500">Table</p>
            <p className="mt-1 text-lg font-semibold text-neutral-900">
              {tablePosition ? `${tablePosition}/${tableSize ?? "?"}` : "—"}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500">Record</p>
            <p className="mt-1 text-lg font-semibold text-neutral-900">
              {wins}W-{draws}D-{losses}L
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-neutral-500">Next</p>
            <p className="mt-1 text-lg font-semibold text-neutral-900">
              {formattedDate ?? "TBC"}
            </p>
            <p className="text-xs text-neutral-500">
              {nextMatch?.opponent ?? "Opponent tbc"}
            </p>
          </div>
        </div>
        {generatedAt && (
          <p className="mt-4 text-xs uppercase tracking-wide text-neutral-400">
            Updated {generatedAt}
          </p>
        )}
      </section>

      {shortTable.length > 0 && (
      <section className={`${accentClasses} p-6`}>
        <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
          League Snapshot
        </h3>
        <ul className="mt-4 space-y-2 text-sm text-neutral-700">
            {shortTable.map((row) => (
              <li
                key={`${row.team_name}-${row.position}`}
                className={`flex items-center justify-between rounded-lg px-3 py-2 ${
                  row.team_name === teamName
                    ? "bg-neutral-900 text-white"
                    : "bg-neutral-100 text-neutral-700"
                }`}
              >
                <span className="font-medium">
                  {row.position ?? "—"}. {row.team_name ?? "Team"}
                </span>
                <span className="text-xs">
                  {typeof row.team_season_points === "number"
                    ? `${row.team_season_points} pts`
                    : "—"}
                </span>
              </li>
            ))}
          </ul>
      </section>
      )}

      {Object.values(highlightGroups).some((items) => (items ?? []).length > 0) && (
        <section className={`${accentClasses} p-6`}>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
            Top Performers
          </h3>
          <div className="mt-4 grid gap-3 text-sm text-neutral-700 sm:grid-cols-3">
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
                  <div key={key} className="rounded-xl bg-neutral-100 p-3 text-center text-xs text-neutral-400">
                    {label}
                    <p className="mt-1 text-neutral-400">No data</p>
                  </div>
                );
              }
              return (
                <div key={key} className="rounded-xl bg-neutral-100 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    {label}
                  </p>
                  <ul className="mt-2 space-y-2">
                    {entries.map((entry) => (
                      <li key={`${key}-${entry.player_name}`} className="text-xs text-neutral-700">
                        <span className="font-semibold text-neutral-900">{entry.player_name}</span>
                        <span className="ml-2 text-neutral-500">{entry.value ?? 0}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {trimmedRoster.length > 0 && (
        <section className={`${accentClasses} p-6`}>
          <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
            Key Squad Minutes
          </h3>
          <div className="mt-4 space-y-2 text-sm text-neutral-700">
            {trimmedRoster.map((player) => (
              <div
                key={player.player_name}
                className="flex items-center justify-between rounded-lg bg-neutral-100 px-3 py-2"
              >
                <div>
                  <p className="font-semibold text-neutral-800">{player.player_name}</p>
                  <p className="text-xs text-neutral-500">
                    {player.position ?? "Role"} · {player.minutes ?? 0}′
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <p className="text-xs text-neutral-500">
                    ⚽ {player.goals ?? 0} · 🎯 {player.assists ?? 0}
                  </p>
                  {onPlayerReport && player.player_name && (
                    <button
                      type="button"
                      onClick={() => onPlayerReport(player)}
                      disabled={reportLoading === player.player_name}
                      className="rounded-lg bg-neutral-900 px-3 py-1 text-[11px] font-semibold text-white shadow-sm transition hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {reportLoading === player.player_name ? "Loading…" : "Report"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {(trimmedUpcoming.length > 0 || trimmedPlayed.length > 0) && (
        <section className={`${accentClasses} divide-y divide-neutral-200`}>
          {trimmedUpcoming.length > 0 && (
            <div className="p-6">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
                Upcoming Fixtures
              </h3>
              <ul className="mt-3 space-y-2 text-sm text-neutral-700">
                {trimmedUpcoming.map((match, index) => (
                  <li key={`upcoming-${index}`} className="rounded-lg bg-neutral-100 px-3 py-2">
                    <p className="font-semibold text-neutral-800">
                      {match.opponent ?? "Opponent"}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {match.date ? format(new Date(match.date), "d MMM") : "Date tbc"} ·{" "}
                      {match.venue ?? "Venue tbc"}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {trimmedPlayed.length > 0 && (
            <div className="p-6">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
                Recent Results
              </h3>
              <ul className="mt-3 space-y-2 text-sm text-neutral-700">
                {trimmedPlayed.map((match, index) => (
                  <li key={`played-${index}`} className="rounded-lg bg-neutral-100 px-3 py-2">
                    <p className="font-semibold text-neutral-800">
                      {match.opponent ?? "Opponent"} · {match.score ?? "Score tbc"}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {match.date ? format(new Date(match.date), "d MMM") : "Date tbc"} ·{" "}
                      {match.venue ?? "Venue"}
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
