import { useCallback, useEffect, useRef, useState } from "react";

// Use the same host name the page was loaded from, so phones on your network
// find the server too (localhost would point at the phone itself).
const WS_URL = `ws://${window.location.hostname}:8000/ws`;

// Connects to the server, keeps the latest state, and reconnects after a drop.
// `identity` is what we say in the hello message, e.g. { role: "display" }.
export function useGame(identity) {
    const [state, setState] = useState(null); // null until the first message
    const [connected, setConnected] = useState(false);
    const [error, setError] = useState(null);
    const wsRef = useRef(null); // the current socket
    const identityRef = useRef(identity); // identity is fixed for this page

    useEffect(() => {
        let stopped = false; // true once the page unmounts
        let timer;

    function connect() {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
            if (wsRef.current !== ws) return; // ignore events from old sockets
            setConnected(true);
            setError(null);
            // Say who we are on EVERY (re)connect: the server forgets after a drop.
            ws.send(JSON.stringify({ type: "hello", ...identityRef.current }));
        };

        ws.onmessage = (event) => {
            if (wsRef.current !== ws) return;
            const msg = JSON.parse(event.data);
            if (msg.type === "state") setState(msg.state);
            else if (msg.type === "error") setError(msg.detail);
        };

        ws.onclose = () => {
            if (wsRef.current !== ws) return;
            setConnected(false);
            if (!stopped) timer = setTimeout(connect, 1000); // try again in 1 s
        };
    }

    connect();
    return () => { // cleanup when the page closes
        stopped = true;
        clearTimeout(timer);
        wsRef.current?.close();
        };
    }, []);

    // Send one message. Does nothing while disconnected.
    const send = useCallback((msg) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(msg));
        }
    }, []);

    return { state, connected, error, send };
}