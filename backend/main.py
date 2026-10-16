"""Birthday Trivia backend.

Clients connect to ws://<host>:8000/ws and exchange JSON messages that all
share one shape: {"type": "<name>", ...extra fields}.

How it works
    1. The server keeps ONE game state in memory (see new_state()).
    2. Every client message is checked and applied to that state by handle().
    3. After every successful change, the state is saved to disk and each
       client is sent its own filtered copy (see view_for()).

Roles (chosen with a "hello" message; every new connection starts as "display")
    display  the shared big screen: sees scores, buzzer and media
    team     a team's phone: can buzz
    bingo    a team's bingo device: also sees that team's private bingo card
    host     the game master: sees everything and controls the game

Messages the server understands
    {"type": "ping"}                                      -> {"type": "pong"} (sender only)
    {"type": "hello", "role": "host", "password": "..."}  -> become the host
    {"type": "hello", "role": "team", "team": "Reds"}     -> join/create a team
    {"type": "hello", "role": "bingo", "team": "Reds", "code": "1234"}
    {"type": "buzz"}                                      -> team only
    {"type": "release"} / {"type": "lock"}                -> host only: open/close buzzers
    {"type": "points", "team": "Reds", "delta": 10}       -> host only
    {"type": "media", "item": "song.mp3" | null}          -> host only

Successful messages broadcast {"type": "state", "state": {...}} to everyone.
Anything invalid gets {"type": "error", "detail": "..."} sent to the sender only.
"""
import json
import logging
import os
import random

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------- config ---
HOST_PASSWORD = os.environ.get("HOST_PASSWORD", "party")  # override in production!
STATE_FILE = "state.json"       # where the game state is saved between restarts
MAX_TEAM_NAME = 24              # keeps the scoreboard readable and limits abuse
BINGO_SQUARES = 16              # a 4x4 bingo card

# Message types only the host may send.
HOST_ONLY = {"release", "lock", "points", "media"}

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("trivia")


# -------------------------------------------------------------- app setup ---
app = FastAPI(title="Birthday Trivia")

# CORS only affects normal HTTP requests made by browser JavaScript (like fetch).
# WebSocket connections are NOT checked by this middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------- game state ---
def new_team() -> dict:
    """A fresh team entry, stored in state["teams"][name]."""
    return {
        "score": 0,
        "bingo_bonus": 0,                                 # stays 0 until host applies bingo
        "bingo_lines": 0,                                 # completed lines on the bingo card
        "card": [False] * BINGO_SQUARES,                  # PRIVATE: bingo device and host only
        "bingo_code": f"{random.randint(0, 9999):04d}",   # PRIVATE: bingo device and host only
    }


def new_state() -> dict:
    """A fresh, empty game."""
    return {
        "teams": {},                 # team name -> new_team()
        "buzzers_open": False,       # True while teams are allowed to buzz
        "buzzed": None,              # name of the team that buzzed first, or None
        "media": None,               # the media item currently shown, or None
        "bingo_labels": [f"Item {i + 1}" for i in range(BINGO_SQUARES)],  # PRIVATE
    }


# The single global game state, shared by all clients.
# Module-level on purpose: this only works with ONE server process.
state = new_state()

# Every currently open socket and who is on the other end.
# socket -> {"role": "display" | "team" | "bingo" | "host", "team": name or None}
connections: dict[WebSocket, dict] = {}


# ------------------------------------------------------------ persistence ---
def save_state() -> None:
    """Write the game state to disk so a server restart doesn't lose the game."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def load_state() -> None:
    """Restore the game state saved by save_state(), if there is one."""
    try:
        with open(STATE_FILE, "r") as f:
            state.update(json.load(f))
        log.info("Loaded state (%d teams)", len(state["teams"]))
    except FileNotFoundError:
        pass                         # first run: nothing saved yet
    except ValueError:
        log.warning("%s is invalid; starting with a fresh state", STATE_FILE)


# --------------------------------------------------------- game messages ---
# These functions are pure game logic: they change `state`/`conn` and return an
# error string, or None on success. They never touch sockets, which makes them
# easy to unit test (see test_game.py).

def clean_team_name(value) -> str:
    """Turn any input into a trimmed team name of at most MAX_TEAM_NAME chars."""
    return str(value or "").strip()[:MAX_TEAM_NAME]


def handle_hello(state: dict, conn: dict, msg: dict) -> str | None:
    """Record who this connection is (its role and team)."""
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
        state["teams"].setdefault(name, new_team())   # create the team on first join

    elif role == "bingo":
        # A bingo device must prove it belongs to the team with the team's code.
        name = clean_team_name(msg.get("team"))
        team = state["teams"].get(name)
        if team is None or team["bingo_code"] != str(msg.get("code", "")):
            return "invalid team or code"
        conn["role"], conn["team"] = "bingo", name

    else:
        conn["role"], conn["team"] = "display", None  # unknown role: read-only screen

    return None


def handle(state: dict, conn: dict, msg: dict) -> str | None:
    """Apply one parsed message to the game state."""
    kind = msg.get("type")

    if kind == "hello":
        return handle_hello(state, conn, msg)

    # Permission check happens once here, so the branches below can trust it.
    if kind in HOST_ONLY and conn["role"] != "host":
        return "host only"

    if kind == "buzz":
        if conn["role"] != "team" or conn["team"] is None:
            return "only teams can buzz"
        # Only the first buzz while buzzers are open counts; later ones are ignored.
        if state["buzzers_open"] and state["buzzed"] is None:
            state["buzzed"] = conn["team"]
            state["buzzers_open"] = False

    elif kind == "release":          # host opens the buzzers for a new question
        state["buzzed"] = None
        state["buzzers_open"] = True

    elif kind == "lock":             # host closes the buzzers without a winner
        state["buzzers_open"] = False

    elif kind == "points":           # host adds (or removes, if negative) points
        team = msg.get("team")
        if not isinstance(team, str) or team not in state["teams"]:
            return "unknown team"
        try:
            delta = int(msg.get("delta"))
        except (ValueError, TypeError):
            return "invalid delta for points"
        state["teams"][team]["score"] += delta

    elif kind == "media":            # host shows a media item, or clears it with null
        media = msg.get("item")
        if media is not None and not isinstance(media, str):
            return "media item must be a string or null"
        state["media"] = media

    else:
        return f"unknown message type: {kind}"

    return None


# ------------------------------------------------------ what clients see ---
def view_for(state: dict, conn: dict) -> dict:
    """The copy of the state this connection is allowed to see.

    The host sees everything. Everyone else gets public info only; a bingo
    device additionally gets its own team's card. Bingo codes are never shared.
    """
    if conn["role"] == "host":
        return state

    view = {
        "teams": {
            name: {
                "score": t["score"],
                "bingo_bonus": t["bingo_bonus"],
                "bingo_lines": t["bingo_lines"],
            }
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


# -------------------------------------------------------- sending helpers ---
def parse_message(raw: str) -> dict:
    """Turn raw text into a dict, or raise ValueError if it is not a JSON object."""
    msg = json.loads(raw)            # json.JSONDecodeError is a ValueError
    if not isinstance(msg, dict):
        raise ValueError("message must be a JSON object")
    return msg


async def send_error(ws: WebSocket, detail: str) -> None:
    """Tell ONE client that its message was refused."""
    await ws.send_text(json.dumps({"type": "error", "detail": detail}))


async def send_state(ws: WebSocket, conn: dict) -> None:
    """Send one client its own view of the current state."""
    await ws.send_text(json.dumps({"type": "state", "state": view_for(state, conn)}))


async def broadcast_state() -> None:
    """Send every connected client its own view of the current state."""
    for ws, conn in list(connections.items()):   # iterate over a COPY: we may remove items
        try:
            await send_state(ws, conn)
        except Exception:
            connections.pop(ws, None)            # dead connection, drop it


# ----------------------------------------------------------------- routes ---
@app.get("/")
async def read_root():
    """Health check: lets you confirm the server is up from a browser."""
    return {"status": "ok", "game": "Birthday Trivia", "version": "1.0.0"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """One running copy of this function per connected client."""
    await ws.accept()
    conn = {"role": "display", "team": None}     # everyone starts as a display
    connections[ws] = conn
    log.info("Client connected (%d total)", len(connections))

    try:
        await send_state(ws, conn)               # new clients get the state right away

        while True:
            raw = await ws.receive_text()        # waits here until a message arrives
            try:
                msg = parse_message(raw)
            except ValueError:
                await send_error(ws, "bad JSON")
                continue                         # keep the connection open

            # Ping doesn't change the game, so answer it directly.
            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
                continue

            error = handle(state, conn, msg)
            if error:
                await send_error(ws, error)      # only the sender hears about errors
            else:
                save_state()
                await broadcast_state()          # everyone sees the change

    except WebSocketDisconnect:
        pass                                     # normal: the client closed the tab
    except Exception:
        log.exception("Unexpected error; closing this connection")
    finally:
        connections.pop(ws, None)                # always clean up, whatever happened
        log.info("Client disconnected (%d left)", len(connections))


# ---------------------------------------------------------------- startup ---
load_state()  # restore the previous game (if any) when the server starts
