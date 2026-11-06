import { useState } from "react";
import { useGame } from "../useGame.js";
import { useCountdown } from "../lib/useCountdown.js";
import Scoreboard from "../components/Scoreboard.jsx";
import MediaLayer from "../components/MediaLayer.jsx";

const IDENTITY = { role: "display" };   // defined outside so it never changes

export default function Display() {
  const { state, connected } = useGame(IDENTITY);
  const seconds = useCountdown(state?.release_in);
  // Browsers block sound until the page has been clicked once.
  const [audioReady, setAudioReady] = useState(false);

  if (!state) {
    return (
      <main className="stage">
        <p className="status">Connecting to the game server…</p>
      </main>
    );
  }

  const lobby = state.phase === "lobby";
  let status = "Buzzers locked";
  if (lobby) status = "Pick your team on your phone!";
  else if (state.buzzed) status = `${state.teams[state.buzzed]?.name} buzzed first!`;
  else if (state.buzzers_open) status = "Buzzers open";

  return (
    <main className="stage">
      <header>
        <h1>Birthday Trivia</h1>
        {!audioReady && (
          <button className="start" onClick={() => setAudioReady(true)}>
            Click to enable sound
          </button>
        )}
        {!connected && <span className="offline">Reconnecting…</span>}
      </header>

      <p className={state.buzzed ? "status buzzed" : "status"}>{status}</p>
      {seconds !== null && <p className="countdown">Buzzers reopen in {seconds}</p>}

      {/* With an image up, a wide TV shows it BESIDE the scores so all teams stay visible. */}
      <div className={state.media?.type === "image" ? "arena with-media" : "arena"}>
        <MediaLayer media={state.media} audioReady={audioReady} />
        <Scoreboard teams={state.teams} buzzed={state.buzzed} />
      </div>
    </main>
  );
}
