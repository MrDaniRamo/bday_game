import { useCallback, useEffect, useRef, useState } from "react";

// Where the game server is.
// - Built pages (npm run build) are served BY the game server, so it is simply
//   the address this page came from: http://192.168.1.23:8000, or a tunnel's
//   https://something.trycloudflare.com. Secure pages must use wss://.
// - In development (npm run dev) Vite serves the pages on port 5173, and the
//   game server is on port 8000 of the same machine.
const { protocol, hostname, host } = window.location;
const SERVER_HOST = import.meta.env.DEV ? `${hostname}:8000` : host;
const SECURE = protocol === "https:";
export const SERVER_URL = `${SECURE ? "https" : "http"}://${SERVER_HOST}`;
const WS_URL = `${SECURE ? "wss" : "ws"}://${SERVER_HOST}/ws`;

// Media paths like "/media/cheer.mp3" live on the backend, not on Vite.
export function mediaUrl(src) {
  return src?.startsWith("/") ? SERVER_URL + src : src;
}

// Connects to the server, keeps the latest state, and reconnects after a drop.
// `identity` is what we say in the hello message, e.g. { role: "display" }.
// `onMessage` (optional) sees every message, e.g. the private "claimed" reply.
export function useGame(identity, onMessage) {
  const [state, setState] = useState(null);        // null until the first message
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);                      // the current socket
  const identityRef = useRef(identity);            // identity is fixed for this page
  const onMessageRef = useRef(onMessage);          // always the latest callback
  onMessageRef.current = onMessage;

  useEffect(() => {
    let stopped = false;                           // true once the page unmounts
    let timer;

    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        if (wsRef.current !== ws) return;          // ignore events from old sockets
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
        onMessageRef.current?.(msg);
      };

      ws.onclose = () => {
        if (wsRef.current !== ws) return;
        setConnected(false);
        if (!stopped) timer = setTimeout(connect, 1000);   // try again in 1 s
      };
    }

    // A phone that was asleep may hold a dead connection that still looks open.
    // When the page becomes visible again, replace the socket with a fresh one.
    function onVisible() {
      if (document.visibilityState !== "visible" || stopped) return;
      clearTimeout(timer);
      const old = wsRef.current;
      connect();                                   // new socket becomes the current one
      old?.close();                                // its events are ignored from now on
    }

    connect();
    document.addEventListener("visibilitychange", onVisible);
    return () => {                                 // cleanup when the page closes
      stopped = true;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
      wsRef.current?.close();
    };
  }, []);

  // Send one message. Does nothing while disconnected.
  const send = useCallback((msg) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return { state, connected, error, send, clearError };
}
