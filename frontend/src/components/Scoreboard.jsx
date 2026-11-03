// Team list, highest total first. The team that buzzed is highlighted.
// `teams` is keyed by team id; `buzzed` is a team id too.
export default function Scoreboard({ teams, buzzed }) {
  // Derived data: computed on every render, never stored in state.
  const rows = Object.entries(teams)
    .filter(([, t]) => t.claimed)               // a freed team waits for a new captain
    .map(([id, t]) => ({ id, ...t, total: t.score + t.bingo_bonus }))
    .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));

  if (rows.length === 0) {
    return <p className="empty">Waiting for teams to join…</p>;
  }

  return (
    <ol className="board">
      {rows.map((team) => (
        <li key={team.id}
            className={team.id === buzzed ? "lit" : ""}
            style={{ borderLeft: `1.2rem solid ${team.color}` }}>
          <span className="name">{team.name}</span>
          <span className="score">
            {team.total}
            {team.bingo_bonus > 0 && <small className="bonus">incl. +{team.bingo_bonus} bingo</small>}
          </span>
        </li>
      ))}
    </ol>
  );
}
