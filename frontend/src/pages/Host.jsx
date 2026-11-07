import { useEffect, useState } from "react";
import { useGame } from "../useGame.js";
import { useCountdown } from "../lib/useCountdown.js";
import { useTheme } from "../lib/useTheme.js";

// The host's control panel. Everything here only SENDS requests: the server
// checks the password on every connection and decides what actually happens.

const KEY = "trivia-host-password";   // sessionStorage: forgotten when the tab closes
const POINT_STEPS = [1, 5, 10, -1, -5];

function loadPassword() {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

function savePassword(password) {
  try {
    if (password) sessionStorage.setItem(KEY, password);
    else sessionStorage.removeItem(KEY);
  } catch {
    /* ignore: the host just types it again after a refresh */
  }
}

export default function Host() {
  const [password, setPassword] = useState(loadPassword);
  const [loginError, setLoginError] = useState(null);
  useTheme("reveal");                    // the host page always uses the reveal look

  if (!password) {
    return (
      <Login
        error={loginError}
        onLogin={(value) => {
          savePassword(value);
          setLoginError(null);
          setPassword(value);
        }}
      />
    );
  }
  return (
    <HostPanel
      key={password}            // a new password = a new identity = a fresh connection
      password={password}
      onBadPassword={() => {
        savePassword(null);
        setLoginError("Wrong password, try again.");
        setPassword(null);
      }}
    />
  );
}

function Login({ error, onLogin }) {
  const [value, setValue] = useState("");
  return (
    <main className="screen join">
      <h1>Host login</h1>
      <form onSubmit={(e) => { e.preventDefault(); onLogin(value); }}>
        <label htmlFor="host-password">Password</label>
        <input id="host-password" type="password" value={value}
          autoComplete="current-password" onChange={(e) => setValue(e.target.value)} />
        {error && <p className="problem">{error}</p>}
        <button type="submit" disabled={!value}>Log in</button>
      </form>
    </main>
  );
}

function HostPanel({ password, onBadPassword }) {
  const { state, connected, error, send, clearError } = useGame({ role: "host", password });
  const seconds = useCountdown(state?.release_in);

  useEffect(() => {
    if (error === "bad password") onBadPassword();
  }, [error, onBadPassword]);

  // Host-only fields (like media_files) arrive only after the server accepts the password.
  if (!state || !state.media_files) {
    return <main className="screen"><p className="hint">Connecting…</p></main>;
  }

  // Clear the last error before each new request, so an old one never lingers.
  const act = (msg) => { clearError(); send(msg); };

  return (
    <main className="host">
      <header className="host-top">
        <h1>Host controls</h1>
        <span className={`pill ${state.phase}`}>
          {state.phase === "lobby" ? "Lobby" : "Playing"}
        </span>
        {!connected && <span className="offline">Reconnecting…</span>}
        {state.phase === "lobby" ? (
          <button className="go" onClick={() => act({ type: "phase", phase: "playing" })}>
            Start game
          </button>
        ) : (
          <button onClick={() => {
            if (confirm("Go back to the lobby? Teams can edit their names again.")) {
              act({ type: "phase", phase: "lobby" });
            }
          }}>
            Back to lobby
          </button>
        )}
      </header>

      {error && (
        <p className="problem" role="alert">
          {error} <button className="small" onClick={clearError}>OK</button>
        </p>
      )}

      <BuzzerPanel state={state} seconds={seconds} act={act} />
      <TeamsPanel state={state} act={act} />
      <MediaPanel state={state} act={act} />
      <BingoPanel state={state} act={act} />
      <ResetPanel act={act} />
    </main>
  );
}

function teamName(state, id) {
  return state.teams[id]?.name ?? "?";
}

function BuzzerPanel({ state, seconds, act }) {
  const [delay, setDelay] = useState(String(state.auto_release_seconds));
  let status = "Locked";
  if (state.buzzed) status = `${teamName(state, state.buzzed)} buzzed first`;
  else if (state.buzzers_open) status = "Open: waiting for a buzz";

  return (
    <section className="panel">
      <h2>Buzzers</h2>
      <p className={state.buzzed ? "now buzzed" : "now"}>
        {status}
        {seconds !== null && ` (reopen in ${seconds})`}
      </p>
      {state.phase === "lobby" && <p className="hint">Start the game so teams can buzz.</p>}
      <div className="row">
        <button className="go" onClick={() => act({ type: "release" })}>
          {state.buzzed ? "Release now" : "Open buzzers"}
        </button>
        <button onClick={() => act({ type: "lock" })}>Lock</button>
      </div>
      <form className="row" onSubmit={(e) => {
        e.preventDefault();
        act({ type: "auto_release", seconds: Number(delay) });
      }}>
        <label htmlFor="delay">Reopen after a buzz (seconds, 0 = never)</label>
        <input id="delay" type="number" min="0" max="60" step="0.5" value={delay}
          onChange={(e) => setDelay(e.target.value)} />
        <button type="submit">Set</button>
        <span className="hint">now {state.auto_release_seconds}s</span>
      </form>
    </section>
  );
}

function TeamsPanel({ state, act }) {
  const teams = Object.entries(state.teams);
  return (
    <section className="panel">
      <h2>Teams</h2>
      {teams.length === 0 && <p className="hint">No teams yet. Captains join at /team.</p>}
      <ul className="teams">
        {teams.map(([id, t]) => (
          <li key={id} className={id === state.buzzed ? "lit" : ""}>
            <span className="dot" style={{ background: t.color }} />
            <span className="who">
              <strong>{t.name}</strong>
              <small>{t.claimed ? "captain connected" : "free: waiting for a captain"}</small>
            </span>
            <span className="pts">
              {t.score}
              {t.bingo_bonus > 0 && <small> +{t.bingo_bonus} bingo</small>}
            </span>
            <span className="row">
              {POINT_STEPS.map((d) => (
                <button key={d} className="small"
                  onClick={() => act({ type: "points", team: id, delta: d })}>
                  {d > 0 ? `+${d}` : d}
                </button>
              ))}
              <button className="small" disabled={!t.claimed}
                onClick={() => {
                  if (confirm(`Free ${t.name}? A new phone can then take it over.`)) {
                    act({ type: "free_team", team_id: id });
                  }
                }}>
                Free
              </button>
              <button className="small danger"
                onClick={() => {
                  if (confirm(`Remove ${t.name} and its points for good?`)) {
                    act({ type: "remove_team", team_id: id });
                  }
                }}>
                Remove
              </button>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function MediaPanel({ state, act }) {
  const [url, setUrl] = useState("");
  const current = state.media;
  // A new id every time, so the TV replays a sound even if it is the same file.
  const show = (type, src) => act({ type: "media", media: { id: Date.now(), type, src } });

  return (
    <section className="panel">
      <h2>Images and sounds</h2>
      <p className="now">
        On the TV: {current ? `${current.type} ${current.src}` : "nothing"}
      </p>
      <div className="row">
        <button onClick={() => act({ type: "media", media: null })} disabled={!current}>
          Clear the screen
        </button>
      </div>
      {state.media_files.length === 0 && (
        <p className="hint">Put images or sounds in backend/media/ and they show up here.</p>
      )}
      <ul className="files">
        {state.media_files.map((f) => (
          <li key={f.name}>
            <button className="small" onClick={() => show(f.type, f.src)}>
              {f.type === "image" ? "Show" : "Play"}
            </button>
            <span>{f.name}</span>
          </li>
        ))}
      </ul>
      <form className="row" onSubmit={(e) => {
        e.preventDefault();
        const type = /\.(mp3|wav|ogg|m4a)$/i.test(url) ? "sound" : "image";
        show(type, url.trim());
      }}>
        <label htmlFor="media-url">Or a web address</label>
        <input id="media-url" type="url" placeholder="https://…" value={url}
          onChange={(e) => setUrl(e.target.value)} />
        <button type="submit" disabled={!url.trim()}>Send</button>
      </form>
    </section>
  );
}

function BingoPanel({ state, act }) {
  const boards = Object.entries(state.boards);
  // Preview of what "Apply" will give each team, using the same rule as the server.
  const preview = {};
  for (const [, b] of boards) {
    if (b.team && state.teams[b.team]) preview[b.team] = (preview[b.team] ?? 0) + b.lines;
  }
  const applied = Object.values(state.teams).some((t) => t.bingo_bonus > 0);

  return (
    <section className="panel">
      <h2>Secret bingo</h2>
      <div className="row">
        <span className="now">{state.bingo_open ? "Ticking is open" : "Ticking is closed"}</span>
        <button onClick={() => act({ type: "bingo_open", open: !state.bingo_open })}>
          {state.bingo_open ? "Close ticking" : "Reopen ticking"}
        </button>
      </div>
      <div className="scroll">
        <table className="cards">
          <thead>
            <tr><th>Card</th><th>Player</th><th>Team</th><th>Lines</th><th /></tr>
          </thead>
          <tbody>
            {boards.map(([id, b]) => (
              <tr key={id}>
                <td>{b.title}</td>
                <td>{b.claimed ? "taken" : "free"}</td>
                <td>{b.team ? teamName(state, b.team) : "no team"}</td>
                <td>{b.lines} <small>({b.marks.filter(Boolean).length}/16 ticked)</small></td>
                <td>
                  <button className="small" disabled={!b.claimed}
                    onClick={() => {
                      if (confirm(`Free ${b.title}? Its ticks stay; a new phone can pick it.`)) {
                        act({ type: "bingo_free", board_id: id });
                      }
                    }}>
                    Free
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="hint">
        Bonus if applied now ({state.points_per_line} points a line):{" "}
        {Object.keys(preview).length === 0
          ? "no card has a team yet"
          : Object.entries(preview)
              .map(([tid, lines]) => `${teamName(state, tid)} +${lines * state.points_per_line}`)
              .join(", ")}
      </p>
      <div className="row">
        <button className="go" onClick={() => act({ type: "apply_bingo" })}>
          {applied ? "Apply bingo bonus again" : "Apply bingo bonus"}
        </button>
        <span className="hint">Safe to press twice: it recalculates, it never adds twice.</span>
      </div>
      <RevealControl state={state} act={act} />
    </section>
  );
}

// Switches the TV and captain phones from the quiz look to the reveal look.
function RevealControl({ state, act }) {
  const revealed = state.theme === "reveal";
  return (
    <div className="reveal-control">
      <p className="now">
        TV look: {revealed ? "revealed (bingo look)" : "quiz look (bingo is still secret)"}
      </p>
      <div className="row">
        {revealed ? (
          <button onClick={() => act({ type: "theme", theme: "quiz" })}>
            Back to the quiz look
          </button>
        ) : (
          <button className="go" onClick={() => {
            if (confirm("Reveal the secret bingo? The TV plays the plot twist and changes look.")) {
              act({ type: "theme", theme: "reveal" });
            }
          }}>
            Reveal the secret bingo
          </button>
        )}
      </div>
      <p className="hint">Tip: close ticking and apply the bonus first, then reveal.</p>
    </div>
  );
}

function ResetPanel({ act }) {
  const [typed, setTyped] = useState("");
  return (
    <section className="panel danger-zone">
      <h2>Reset the whole game</h2>
      <p className="hint">
        Deletes every team, score and bingo card. Type the host password to confirm.
      </p>
      <form className="row" onSubmit={(e) => {
        e.preventDefault();
        act({ type: "reset", password: typed });
        setTyped("");
      }}>
        <label htmlFor="reset-password">Password</label>
        <input id="reset-password" type="password" value={typed}
          autoComplete="off" onChange={(e) => setTyped(e.target.value)} />
        <button type="submit" className="danger" disabled={!typed}>Reset game</button>
      </form>
    </section>
  );
}
