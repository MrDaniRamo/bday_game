import { useEffect, useState } from "react";
import { useGame } from "../useGame.js";
import { clearBoard, loadBoard, saveBoard } from "../lib/savedBoard.js";
import { useTheme } from "../lib/useTheme.js";

const NEW_PLAYER = { role: "bingo" };    // hello without a board yet

export default function Bingo() {
  const [saved, setSaved] = useState(loadBoard);   // { board_id, token } or null
  useTheme("reveal");                              // the secret game has its own look

  if (!saved) {
    return (
      <BoardPicker
        onClaimed={(board_id, token) => {
          saveBoard(board_id, token);
          setSaved({ board_id, token });
        }}
      />
    );
  }
  return (
    <BoardGame
      saved={saved}
      onForget={() => {
        clearBoard();
        setSaved(null);
      }}
    />
  );
}

// Step 1: choose one of the preset boards. A taken board cannot be chosen.
function BoardPicker({ onClaimed }) {
  const { state, error, send } = useGame(NEW_PLAYER, (msg) => {
    if (msg.type === "board_claimed") onClaimed(msg.board_id, msg.token);
  });

  if (!state) return <main className="screen"><p className="hint">Connecting…</p></main>;

  return (
    <main className="screen join">
      <h1>Pick your card</h1>
      <p className="hint">
        Choose the card with your captain's phrases. Each card can only be used once.
      </p>
      <div className="choices">
        {Object.entries(state.boards).map(([id, board]) => (
          <button key={id} type="button" disabled={board.taken}
            onClick={() => send({ type: "bingo_pick", board_id: id })}>
            {board.title}{board.taken ? " (taken)" : ""}
          </button>
        ))}
      </div>
      {error && <p className="problem">{error}</p>}
    </main>
  );
}

// Step 2: the card, plus the team drop-down.
function BoardGame({ saved, onForget }) {
  const identity = { role: "bingo", ...saved };
  const { state, error, send } = useGame(identity);

  const mine = state?.my_board;
  // Refused at hello, or the host freed the board.
  const lost = error === "that board is not yours any more"
    || (mine && !state.boards[mine.id]?.taken);
  useEffect(() => {
    if (lost) onForget();
  }, [lost, onForget]);

  if (!state) return <main className="screen"><p className="hint">Connecting…</p></main>;
  if (!mine) {
    return <main className="screen"><p className="hint">Opening your card…</p></main>;
  }

  const teams = Object.entries(state.teams).filter(([, t]) => t.claimed);
  const canMark = mine.controller && state.bingo_open;

  return (
    <main className="screen bingo">
      <h1>{mine.title}</h1>

      {!mine.controller && (
        <>
          <p className="hint">Another phone is using this card.</p>
          <button type="button" className="big"
            onClick={() => send({ type: "hello", ...identity })}>
            Take control back
          </button>
        </>
      )}

      {/* lang="es": the phrases are in Spanish, so long words break with Spanish rules */}
      <div className="card" role="grid" aria-label="Bingo card" lang="es">
        {mine.phrases.map((phrase, i) => (
          <button key={i} type="button" role="gridcell"
            aria-pressed={mine.marks[i]}
            className={`square ${mine.marks[i] ? "on" : ""}`}
            disabled={!canMark}
            onClick={() => send({ type: "bingo_mark", index: i, marked: !mine.marks[i] })}>
            {phrase}
          </button>
        ))}
      </div>

      <p className="lines">Lines: {mine.lines}</p>
      {!state.bingo_open && <p className="hint">The host has closed bingo.</p>}

      <label htmlFor="bingo-team">Which team are you on?</label>
      <select id="bingo-team" value={mine.team ?? ""} disabled={!mine.controller}
        onChange={(e) => send({ type: "bingo_team", team_id: e.target.value || null })}>
        <option value="">
          {teams.length ? "Choose your team…" : "No teams yet"}
        </option>
        {teams.map(([id, t]) => <option key={id} value={id}>{t.name}</option>)}
      </select>
      <p className="hint">
        {mine.team
          ? "Your lines will count for this team at the end."
          : "Pick a team so your lines count."}
      </p>
      {error && <p className="problem">{error}</p>}
    </main>
  );
}
