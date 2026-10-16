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
import random
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

HOST_PASSWORD = os.environ.get("HOST_PASSWORD", "party")
HOST_ONLY = {"release", "lock", "points", "media"}
STATE_FILE = "state.json"  # TODO: implement this to persist the state

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
#clients: set[WebSocket] = set()
connections: dict[WebSocket, dict] = {}  # socket -> {"role": ..., "team": ...}

# ------------------------------------------------------------- New team and State ---
def new_team() -> dict:
    return {
        "score": 0,
        "bingo_bonus": 0,                                       # stays 0 until host applies bingo
        "bingo_lines": 0,                                       # number of completed lines on the bingo card
        "card": [False] * 16,                               # PRIVATE: bingo devices and host only
        "bingo_code": f"{random.randint(0, 9999):04d}",          # PRIVATE: bingo devices and host only       
    }

def new_state() -> dict:
    return {
        "teams": {},                                             # team name -> new_team()
        "buzzers_open": False,                                 # host only
        "buzzed": None,                                          # the team that buzzed, or None
        "media": None,                                           # the current media item, or None
        "bingo_labels": [f"Item {i+1}" for i in range(16)],  # PRIVATE: bingo devices and host only
    }

state = new_state()  # the single global game state, shared by all clients




# ------------------------------------------------------------- HTTP route ---
@app.get("/")
async def read_root():
    """Health check: lets you confirm the server is up from a browser."""
    return {"status": "ok", "game": "Birthday Trivia", "version": "1.0.0"}


# ------------------------------------------------------ sending helpers ---
async def broadcast(message: dict) -> None:
    """Send one JSON message to every connected client."""
    payload = json.dumps(message)
    for ws in list(connections):            # iterate over a COPY: we may remove items
        try:
            await ws.send_text(payload)
        except Exception:
            connections.pop(ws, None)         # dead connection, drop it


async def send_error(ws: WebSocket, detail: str) -> None:
    """Tell ONE client that its message was refused."""
    await ws.send_text(json.dumps({"type": "error", "detail": detail}))


# --------------------------------------------------------- game messages ---
# def handle_message(msg: dict) -> tuple[dict, bool] | None:
#     """Apply one parsed message.

#     Returns (reply, to_everyone) or None if there is nothing to send.
#     to_everyone=True means broadcast; False means answer only the sender.
#     Errors are returned with type "error" and are always sender-only.
#     """
#     kind = msg.get("type")

#     if kind == "ping":
#         return {"type": "pong"}, False

#     if kind == "join":
#         team = str(msg.get("team", "")).strip()[:MAX_TEAM_NAME]
#         if not team:
#             return {"type": "error", "detail": "team is required"}, False
#         log.info("Team %s joined the game", team)
#         connections[ws]["team"] = team
#         return {"type": "joined", "team": team}, True

#     return {"type": "error", "detail": f"unknown message type: {kind}"}, False


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
    conn = {"role": "display", "team": None}
    connections[ws] = conn
    log.info("Client connected (%d total)", len(connections))
    try:
        await send_state(ws, conn)  # send the initial state to the new client
        while True:
            raw = await ws.receive_text()       # waits here until a message arrives
            try:
                msg = parse_message(raw)
            except ValueError:
                await send_error(ws, "bad JSON")
                continue                        # keep the connection open

            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
                continue

            error = handle(state, conn, msg)
            if error:
                await send_error(ws, error)
            else:
                save_state()  # TODO: implement this to persist the state
                await broadcast_state()  # send the updated state to all clients
    except WebSocketDisconnect:
        pass                                    # normal: the client closed the tab
    except Exception:
        log.exception("Unexpected error; closing this connection")
    finally:
        connections.pop(ws, None)                     # always clean up, whatever happened
        log.info("Client disconnected (%d left)", len(connections))

def view_for(state: dict, conn: dict) -> dict:
    """The copy of the state this connection is allowed to see."""
    if conn["role"] == "host":
        return state
    view = {
        "teams": {
            name: {"score": t["score"],
                "bingo_bonus": t["bingo_bonus"],
                "bingo_lines": t["bingo_lines"]}
            for name, t in state["teams"].items()
        },
        "buzzers_open": state["buzzers_open"],
        "buzzed": state["buzzed"],
        "media": state["media"],
    }
    if conn["role"] == "bingo" and conn["team"] in state["teams"]:
        view["my_card"] = state["teams"][conn["team"]]["card"]
        view["bingo_labels"] = state["bingo_labels"]
    return view

async def send_state(ws: WebSocket, conn: dict) -> None:
    """Send the current state to one client."""
    await ws.send_text(json.dumps({"type": "state", "state": view_for(state, conn)}))

async def broadcast_state() -> None:
    """Send the current state to every connected client."""
    for ws, conn in list(connections.items()):            # iterate over a COPY: we may remove items
        try:
            await send_state(ws, conn)
        except Exception:
            connections.pop(ws, None)         # dead connection, drop it

def clean_team_name(value) -> str:
    return str(value or "").strip()[:MAX_TEAM_NAME]

def handle_hello(state: dict, conn: dict, msg: dict) -> str | None:
    """Record who this connection is. Returns an error string or None if OK."""
    role = msg.get("role")
    if role == "host":
        if msg.get("password") != HOST_PASSWORD:
            return "bad password"
        conn["role"], conn["team"] = "host", None
    elif role == "team":
        name = clean_team_name(msg.get("team"))
        if not name:
            return "team name is required"
        conn["role"], conn["team"] = "team", name
        state["teams"].setdefault(name, new_team())
    elif role == "bingo":
        name = clean_team_name(msg.get("team"))
        team = state["teams"].get(name)
        if team is None or team["bingo_code"] != str(msg.get("code","")):
            return "invalid team or code"
        conn["role"], conn["team"] = "bingo", name
    else:
        conn["role"], conn["team"] = "display", None
    return None

def handle(state: dict, conn: dict, msg: dict) -> str | None:
    """Apply one parsed message. Returns an error string or None if OK."""
    kind = msg.get("type")
    if kind == "hello":
        return handle_hello(state, conn, msg)
    if kind in HOST_ONLY and conn["role"] != "host":
        return "host only"

    if kind == "buzz":
        if conn["role"] != "team" or conn["team"] is None:
            return "only teams can buzz"
        if state["buzzers_open"] and state["buzzed"] is None:
            state["buzzed"] = conn["team"]
            state["buzzers_open"] = False
    elif kind == "release":
        state["buzzed"] = None
        state["buzzers_open"] = True
    elif kind == "lock":
        state["buzzers_open"] = False
    elif kind == "points":
        team = msg.get("team")
        if not isinstance(team, str) or team not in state["teams"]:
            return "unknown team"
        try:
            delta = int(msg.get("delta"))
        except (ValueError, TypeError):
            return "invalid delta for points"
        state["teams"][team]["score"] += delta
    elif kind == "media":
        media = msg.get("item")
        if media is not None and not isinstance(media, str):
            return "media item must be a string or null"
        state["media"] = media
    else:
        return f"unknown message type: {kind}"
    return None

def save_state() -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
    pass

def load_state() -> None:
    try:
        with open(STATE_FILE, "r") as f:
            state.update(json.load(f))
        log.info("Loaded state (%d teams)", len(state["teams"]))
    except FileNotFoundError:
        pass
    except ValueError:
        log.warning("state.json is invalid; starting with a fresh state")

load_state()  # load the state from disk when the server starts