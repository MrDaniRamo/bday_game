import { useEffect, useState } from "react";
import { useGame } from "../useGame.js";
import { useCountdown } from "../lib/useCountdown.js";
import BuzzerButton from "../components/BuzzerButton.jsx";
import ColorPicker from "../components/ColorPicker.jsx";
import { buzzerStatus } from "../lib/buzzer.js";
import { clearTeam, loadTeam, saveTeam } from "../lib/savedTeam.js";

const MAX_TEAM_NAME = 24;               // same limit as the server
const NEW_PHONE = { role: "team" };     // hello without a team yet

export default function Team() {
  const [saved, setSaved] = useState(loadTeam);   // { team_id, token } or null

  if (!saved) {
    return (
      <JoinScreen
        onClaimed={(team_id, token) => {
          saveTeam(team_id, token);
          setSaved({ team_id, token });
        }}
      />
    );
  }
  return (
    <TeamGame
      saved={saved}
      onForget={() => {
        clearTeam();
        setSaved(null);
      }}
    />
  );
}

// Name + color form, used both to create a team and to edit it in the lobby.
function TeamForm({ colors, takenColors, initial, submitLabel, onSubmit, error }) {
  const [name, setName] = useState(initial.name);
  const [color, setColor] = useState(initial.color);

  function handleSubmit(event) {
    event.preventDefault();
    onSubmit(name.trim(), color);
  }

  return (
    <form onSubmit={handleSubmit}>
      <label htmlFor="team-name">Team name</label>
      <input
        id="team-name"
        value={name}
        maxLength={MAX_TEAM_NAME}
        autoComplete="off"
        onChange={(event) => setName(event.target.value)}
      />
      <span className="label">Team color</span>
      <ColorPicker colors={colors} taken={takenColors} value={color} onChange={setColor} />
      {error && <p className="problem">{error}</p>}
      <button type="submit" disabled={!name.trim() || !color}>{submitLabel}</button>
    </form>
  );
}

function takenColorsOf(state, exceptId) {
  return Object.entries(state.teams)
    .filter(([id]) => id !== exceptId)
    .map(([, t]) => t.color);
}

// Step 1: a phone with no team creates one (or takes over one the host freed).
function JoinScreen({ onClaimed }) {
  const { state, error, send } = useGame(NEW_PHONE, (msg) => {
    if (msg.type === "claimed") onClaimed(msg.team_id, msg.token);
  });

  if (!state) return <main className="screen"><p className="hint">Connecting…</p></main>;

  const free = Object.entries(state.teams).filter(([, t]) => !t.claimed);
  const open = state.phase === "lobby";

  return (
    <main className="screen join">
      <h1>Start your team</h1>

      {free.length > 0 && (
        <section className="choices">
          <p className="hint">Your captain left? Take over:</p>
          {free.map(([id, t]) => (
            <button key={id} type="button" style={{ background: t.color }}
              onClick={() => send({ type: "claim", team_id: id })}>
              {t.name}
            </button>
          ))}
        </section>
      )}

      {open ? (
        <TeamForm
          colors={state.colors}
          takenColors={takenColorsOf(state, null)}
          initial={{ name: "", color: "" }}
          submitLabel="Create team"
          error={error}
          onSubmit={(name, color) => send({ type: "claim", name, color })}
        />
      ) : (
        <p className="hint">The game has started, so new teams can no longer join.</p>
      )}
    </main>
  );
}

// Step 2: we own a team. Lobby = edit it; playing = buzz.
function TeamGame({ saved, onForget }) {
  const identity = { role: "team", ...saved };
  const { state, connected, error, send, clearError } = useGame(identity);
  const seconds = useCountdown(state?.release_in);   // hooks go before any early return

  // The token is no good: refused at hello, or the host freed/removed our team.
  const myId = state?.you?.team;
  const me = state?.teams[myId];
  const lostTeam = error === "that team is not yours any more"
    || (state && myId && (!me || !me.claimed));
  useEffect(() => {
    if (lostTeam) onForget();
  }, [lostTeam, onForget]);

  if (!state) return <main className="screen"><p className="hint">Connecting…</p></main>;

  if (!me) return <main className="screen"><p className="hint">Joining…</p></main>;

  if (!state.you.controller) {
    return (
      <main className="screen">
        <h1 style={{ color: me.color }}>{me.name}</h1>
        <p className="hint">Another phone is controlling this team.</p>
        <button type="button" className="big"
          onClick={() => send({ type: "hello", ...identity })}>
          Take control back
        </button>
      </main>
    );
  }

  if (state.phase === "lobby") {
    return (
      <main className="screen join">
        <h1 style={{ color: me.color }}>{me.name}</h1>
        <p className="hint">Change your name or color until the host starts the game.</p>
        <TeamForm
          key={`${me.name}${me.color}`}
          colors={state.colors}
          takenColors={takenColorsOf(state, myId)}
          initial={me}
          submitLabel="Save"
          error={error}
          onSubmit={(name, color) => {
            clearError();
            send({ type: "team_edit", name, color });
          }}
        />
        <p className="hint">Waiting for the host to start…</p>
      </main>
    );
  }

  const status = buzzerStatus(state, myId, connected);
  return (
    <main className="screen game">
      <header>
        <h1 style={{ color: me.color }}>{me.name}</h1>
        <p className="score">{me.score + me.bingo_bonus}</p>
      </header>

      <BuzzerButton status={status} state={state} onBuzz={() => send({ type: "buzz" })} />

      {seconds !== null && <p className="countdown">Buzzers reopen in {seconds}</p>}
      {error && <p className="problem">{error}</p>}
    </main>
  );
}
