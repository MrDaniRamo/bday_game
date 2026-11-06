import { useEffect, useRef, useState } from "react";
import { useGame } from "../useGame.js";
import { useCountdown } from "../lib/useCountdown.js";
import { useTheme } from "../lib/useTheme.js";
import Scoreboard from "../components/Scoreboard.jsx";
import MediaLayer from "../components/MediaLayer.jsx";

const IDENTITY = { role: "display" };   // defined outside so it never changes
const REVEAL_MS = 7000;                 // how long the "plot twist" animation stays up

export default function Display() {
  const { state, connected } = useGame(IDENTITY);
  const seconds = useCountdown(state?.release_in);
  // Browsers block sound until the page has been clicked once.
  const [audioReady, setAudioReady] = useState(false);
  const theme = state?.theme ?? "quiz";
  useTheme(theme);
  const revealing = useRevealMoment(theme);

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
        <h1>
          Birthday Trivia
          {theme === "reveal" && <span className="twist-tag">+ secret bingo!</span>}
        </h1>
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

      {revealing && (
        <div className="reveal-overlay" role="alert">
          <p className="twist-1">Plot twist!</p>
          <p className="twist-2">Let's get ready for a Game Changer!</p>
          <p className="twist-3">BINGO!</p>
        </div>
      )}
    </main>
  );
}

// True for a few seconds right after the host switches the look from quiz to
// reveal, so the TV can play its "plot twist" moment. Opening the page when the
// look is ALREADY "reveal" does not replay it.
function useRevealMoment(theme) {
  const [revealing, setRevealing] = useState(false);
  const previous = useRef(null);

  useEffect(() => {
    const was = previous.current;
    previous.current = theme;
    if (!(was === "quiz" && theme === "reveal")) return;
    setRevealing(true);
    const timer = setTimeout(() => setRevealing(false), REVEAL_MS);
    return () => {               // the look changed again, or the page closed
      clearTimeout(timer);
      setRevealing(false);
    };
  }, [theme]);

  return revealing;
}
