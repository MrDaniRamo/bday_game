"""Birthday Trivia backend (Part 1: WebSocket skeleton).

Clients connect to ws://<host>:8000/ws and exchange JSON messages that all
share one shape: {"type": "<name>", ...extra fields}.

Messages the server understands
    {"type": "ping"}                  -> replies {"type": "pong"} to the sender only
    {"type": "join", "team": "Reds"}  -> broadcasts {"type": "joined", "team": "Reds"}

Anything invalid gets {"type": "error", "detail": "..."} sent to the sender only.
"""
import json
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# ----------------------------------------------------------------- setup ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("trivia")

MAX_TEAM_NAME = 24          # keeps the scoreboard readable and limits abuse

app = FastAPI(title="Birthday Trivia")

# CORS only affects normal HTTP requests made by browser JavaScript (like fetch).
# WebSocket connections are NOT checked by this middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Every currently connected socket. Module-level on purpose: all connections
# must see the same set. This only works with ONE server process.
clients: set[WebSocket] = set()


# ------------------------------------------------------------- HTTP route ---
@app.get("/")
async def read_root():
    """Health check: lets you confirm the server is up from a browser."""
    return {"status": "ok", "game": "Birthday Trivia", "version": "1.0.0"}


# ------------------------------------------------------ sending helpers ---
async def broadcast(message: dict) -> None:
    """Send one JSON message to every connected client."""
    payload = json.dumps(message)
    for ws in list(clients):            # iterate over a COPY: we may remove items
        try:
            await ws.send_text(payload)
        except Exception:
            clients.discard(ws)         # dead connection, drop it


async def send_error(ws: WebSocket, detail: str) -> None:
    """Tell ONE client that its message was refused."""
    await ws.send_text(json.dumps({"type": "error", "detail": detail}))


# --------------------------------------------------------- game messages ---
def handle_message(msg: dict) -> tuple[dict, bool] | None:
    """Apply one parsed message.

    Returns (reply, to_everyone) or None if there is nothing to send.
    to_everyone=True means broadcast; False means answer only the sender.
    Errors are returned with type "error" and are always sender-only.
    """
    kind = msg.get("type")

    if kind == "ping":
        return {"type": "pong"}, False

    if kind == "join":
        team = str(msg.get("team", "")).strip()[:MAX_TEAM_NAME]
        if not team:
            return {"type": "error", "detail": "team is required"}, False
        log.info("Team %s joined the game", team)
        return {"type": "joined", "team": team}, True

    return {"type": "error", "detail": f"unknown message type: {kind}"}, False


def parse_message(raw: str) -> dict:
    """Turn raw text into a dict, or raise ValueError if it is not a JSON object."""
    msg = json.loads(raw)               # json.JSONDecodeError is a ValueError
    if not isinstance(msg, dict):
        raise ValueError("message must be a JSON object")
    return msg


# ------------------------------------------------------ WebSocket endpoint ---
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    log.info("Client connected (%d total)", len(clients))
    try:
        while True:
            raw = await ws.receive_text()       # waits here until a message arrives
            try:
                msg = parse_message(raw)
            except ValueError:
                await send_error(ws, "bad JSON")
                continue                        # keep the connection open

            result = handle_message(msg)
            if result is None:
                continue
            reply, to_everyone = result
            if to_everyone:
                await broadcast(reply)
            else:
                await ws.send_text(json.dumps(reply))
    except WebSocketDisconnect:
        pass                                    # normal: the client closed the tab
    except Exception:
        log.exception("Unexpected error; closing this connection")
    finally:
        clients.discard(ws)                     # always clean up, whatever happened
        log.info("Client disconnected (%d left)", len(clients))