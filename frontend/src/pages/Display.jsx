import { useState } from "react";
import { useGame } from "../useGame.js";
import Scoreboard from "../components/Scoreboard.jsx";
import MediaLayer from "../components/MediaLayer.jsx";

const IDENTITY = { role: "display" }; // defined outside so it never changes

export default function Display() {
    const { state, connected } = useGame(IDENTITY);
    // Browsers block sound until the page has been clicked once.
    const [audioReady, setAudioReady] = useState(false);

    if (!state) {
        return (
            <main className="stage">
                <p className="status">Connecting to the game server…</p>
            </main>
        );
    }
    
    let status = "Buzzers locked";
    if (state.buzzed) status = `${state.buzzed} buzzed first!`;
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
            
            <MediaLayer media={state.media} audioReady={audioReady} />
            <Scoreboard teams={state.teams} buzzed={state.buzzed} />
        </main>
    );
}