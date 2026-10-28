// Team list, highest total first. The team that buzzed is highlighted.
export default function Scoreboard({ teams, buzzed }) {
    // Derived data: computed on every render, never stored in state.
    const rows = Object.entries(teams)
        .map(([name, t]) => ({ name, total: t.score + t.bingo_bonus }))
        .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));

    if (rows.length === 0) {
        return <p className="empty">Waiting for teams to join…</p>;
    }

    return (
        <ol className="board">
            {rows.map((team) => (
            <li key={team.name} className={team.name === buzzed ? "lit" : ""}>
                <span className="name">{team.name}</span>
                <span className="score">{team.total}</span>
            </li>
            ))}
        </ol>
    );
}