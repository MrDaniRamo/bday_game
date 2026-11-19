"""Birthday Trivia backend (game state, roles, lobby, buzzer logic).

Clients connect to ws://<host>:8000/ws and exchange JSON messages that all
share one shape: {"type": "<name>", ...extra fields}.

Roles: display (default), team (buzzer phone), bingo (secret card), host.
After every accepted message the server sends each connection its own view
of the shared game state, containing only what that role may see.

Anything invalid gets {"type": "error", "detail": "..."} sent to the sender only.
"""
import asyncio
import json
import logging
import random
import os
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from boards import BOARDS

HOST_PASSWORD = os.environ.get("HOST_PASSWORD", "party")
HOST_ONLY = {"release", "lock", "points", "media", "auto_release",
             "phase", "free_team", "remove_team",
             "bingo_open", "bingo_free", "apply_bingo", "reset", "theme"}
# Bonus points for each completed bingo line, added when the host applies bingo.
POINTS_PER_LINE = int(os.environ.get("POINTS_PER_LINE", "10"))
# The 10 winning lines on a 4x4 card, as square numbers 0..15 (row by row).
LINES = (
    [[r * 4 + c for c in range(4)] for r in range(4)]        # 4 rows
    + [[r * 4 + c for r in range(4)] for c in range(4)]      # 4 columns
    + [[0, 5, 10, 15], [3, 6, 9, 12]]                        # 2 diagonals
)
# Fixed palette: every team gets a different color, and the TV can rely on them.
TEAM_COLORS = ["#ff3d7f", "#ffc63d", "#2bd9a8", "#4da3ff",
               "#b57bff", "#ff8a3d", "#7be0ff", "#c8e64c"]
# Seconds after a buzz before the buzzers reopen by themselves (0 = the host does it).
AUTO_RELEASE_SECONDS = float(os.environ.get("AUTO_RELEASE_SECONDS", "5"))
# The look of the TV and captain phones: "quiz" all night, "reveal" after the
# host reveals the secret bingo. Bingo and host pages always use the reveal look.
THEMES = ("quiz", "reveal")
STATE_FILE = "state.json"
# Images and sounds the host can put on the TV. Drop files into backend/media/.
MEDIA_DIR = Path(__file__).parent / "media"
MEDIA_TYPES = {".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image",
               ".webp": "image", ".mp3": "sound", ".wav": "sound", ".ogg": "sound",
               ".m4a": "sound"}

# ----------------------------------------------------------------- setup ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("trivia")

MAX_TEAM_NAME = 24          # keeps the scoreboard readable and limits abuse

@asynccontextmanager
async def lifespan(app: FastAPI):
    reschedule_release()        # resume a countdown that was running before a restart
    yield


app = FastAPI(title="Birthday Trivia", lifespan=lifespan)

# CORS only affects normal HTTP requests made by browser JavaScript (like fetch).
# WebSocket connections are NOT checked by this middleware.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    # also allow the page when opened through your computer's network address
    allow_origin_regex=(
        r"http://(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+"
        r"|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+):5173"
    ),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the media folder: http://<laptop>:8000/media/<file name>
MEDIA_DIR.mkdir(exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# Every currently connected socket. Module-level on purpose: all connections
# must see the same dict. This only works with ONE server process.
connections: dict[WebSocket, dict] = {}  # socket -> {"id", "role", "team"}
_conn_ids = iter(range(1, 10**9))

# ------------------------------------------------------------- New team and State ---
def new_team(name: str = "", color: str = TEAM_COLORS[0]) -> dict:
    return {
        "name": name,
        "color": color,
        "claimed": False,                          # True while a captain owns it
        "token": None,                             # PRIVATE: the captain's secret
        "score": 0,
        "bingo_bonus": 0,                          # stays 0 until host applies bingo
        "bingo_lines": 0,                          # set when the host applies bingo
    }


def shuffled_order() -> list[int]:
    """A random order for a card's 16 phrases: order[square] = phrase number."""
    return random.sample(range(16), 16)


def new_board() -> dict:
    return {
        "claimed": False,          # True while a player owns the board
        "token": None,             # PRIVATE: the player's secret, like a captain's
        "marks": [False] * 16,     # PRIVATE: which squares the player ticked
        "team": None,              # the team id the player picked in the dropdown
        # Shuffled once per game, so every party gets a fresh layout, but a refresh
        # or a server restart keeps it. Marks are by SQUARE, so lines still count
        # on the card exactly as the player sees it.
        "order": shuffled_order(),
    }


def board_phrases(board_id: str, board: dict) -> list[str]:
    """The card's phrases in the order they appear on its 16 squares."""
    phrases = board_info(board_id)["phrases"]
    return [phrases[i] for i in board["order"]]


def count_lines(marks: list) -> int:
    """How many of the 10 possible lines are completely ticked."""
    return sum(all(marks[i] for i in line) for line in LINES)


def new_state() -> dict:
    return {
        "phase": "lobby",            # "lobby" (teams join and edit) or "playing"
        "theme": "quiz",             # look of the TV and phones, one of THEMES
        "next_id": 1,                # teams are keyed by an id like "t1", never by name
        "teams": {},                 # team id -> new_team()
        "buzzers_open": False,       # True while teams may buzz
        "buzzed": None,              # the id of the team that buzzed, or None
        "media": None,               # the current media item, or None
        "bingo_open": True,          # bingo players may mark squares (works in any phase)
        "boards": {b["id"]: new_board() for b in BOARDS},   # PRIVATE: marks per board
        "auto_release_seconds": AUTO_RELEASE_SECONDS,   # host can change it
        "release_at": None,          # unix time the buzzers reopen, or None
    }

state = new_state()  # the single global game state, shared by all clients


# ------------------------------------------------------------- HTTP route ---
@app.get("/")
async def read_root():
    """Health check: lets you confirm the server is up from a browser."""
    return {"status": "ok", "game": "Birthday Trivia", "version": "3.0.0"}


# ------------------------------------------------------ sending helpers ---
async def send_error(ws: WebSocket, detail: str) -> None:
    """Tell ONE client that its message was refused."""
    await ws.send_text(json.dumps({"type": "error", "detail": detail}))


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
    conn = {"id": next(_conn_ids), "role": "display", "team": None, "board": None}
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

            conn.pop("reply", None)
            error = handle(state, conn, msg)
            if error:
                await send_error(ws, error)
            else:
                reply = conn.pop("reply", None)   # private answer, e.g. a token
                if reply:
                    await ws.send_text(json.dumps(reply))
                save_state()
                reschedule_release()      # start, restart or cancel the countdown
                await broadcast_state()   # send each client its own view
    except WebSocketDisconnect:
        pass                                    # normal: the client closed the tab
    except Exception:
        log.exception("Unexpected error; closing this connection")
    finally:
        connections.pop(ws, None)                     # always clean up, whatever happened
        log.info("Client disconnected (%d left)", len(connections))

def board_info(board_id: str) -> dict:
    """The fixed part of a board (title and phrases), from boards.py."""
    return next(b for b in BOARDS if b["id"] == board_id)


def list_media() -> list[dict]:
    """The images and sounds in the media folder, for the host's media panel.

    Read from disk every time, so a file you drop in shows up without a restart.
    """
    return [{"name": f.name, "type": MEDIA_TYPES[f.suffix.lower()],
             "src": f"/media/{f.name}"}
            for f in sorted(MEDIA_DIR.iterdir())
            if f.is_file() and f.suffix.lower() in MEDIA_TYPES]


def public_team(t: dict) -> dict:
    return {"name": t["name"], "color": t["color"], "claimed": t["claimed"],
            "score": t["score"], "bingo_bonus": t["bingo_bonus"],
            "bingo_lines": t["bingo_lines"]}


def controls(state: dict, conn: dict) -> bool:
    """True if this connection is the one that controls its team."""
    team = state["teams"].get(conn["team"])
    return conn["role"] == "team" and team is not None and team.get("session") == conn["id"]


def view_for(state: dict, conn: dict) -> dict:
    """The copy of the state this connection is allowed to see."""
    if conn["role"] == "host":
        host_teams = {tid: {k: v for k, v in t.items() if k not in ("token", "session")}
                      for tid, t in state["teams"].items()}
        host_boards = {bid: {"title": board_info(bid)["title"], "claimed": b["claimed"],
                             "marks": b["marks"], "lines": count_lines(b["marks"]),
                             "team": b["team"]}
                       for bid, b in state["boards"].items()}
        return {**state, "colors": TEAM_COLORS, "teams": host_teams, "boards": host_boards,
                "release_in": seconds_left(state), "media_files": list_media(),
                "points_per_line": POINTS_PER_LINE}
    view = {
        "phase": state["phase"],
        "theme": state["theme"],
        "colors": TEAM_COLORS,          # the palette: phones need no copy of it
        "teams": {tid: public_team(t) for tid, t in state["teams"].items()},
        "buzzers_open": state["buzzers_open"],
        "buzzed": state["buzzed"],
        "media": state["media"],
        "release_in": seconds_left(state),    # seconds until the buzzers reopen, or None
    }
    if conn["role"] == "team":
        view["you"] = {"team": conn["team"], "controller": controls(state, conn)}
    # Which boards exist and whether they are taken: no marks, no teams.
    view["boards"] = {bid: {"title": board_info(bid)["title"], "taken": b["claimed"]}
                      for bid, b in state["boards"].items()}
    view["bingo_open"] = state["bingo_open"]
    if conn["role"] == "bingo" and conn["board"] in state["boards"]:
        b = state["boards"][conn["board"]]
        view["my_board"] = {
            "id": conn["board"], "title": board_info(conn["board"])["title"],
            "phrases": board_phrases(conn["board"], b),
            "marks": b["marks"], "lines": count_lines(b["marks"]),
            "team": b["team"], "controller": b.get("session") == conn["id"],
        }
    return view

async def send_state(ws: WebSocket, conn: dict) -> None:
    """Send this connection its view of the state."""
    await ws.send_text(json.dumps({"type": "state", "state": view_for(state, conn)}))

async def broadcast_state() -> None:
    """Send every connection its own view of the state."""
    for ws, conn in list(connections.items()):            # iterate over a COPY: we may remove items
        try:
            await send_state(ws, conn)
        except Exception:
            connections.pop(ws, None)         # dead connection, drop it

def clean_team_name(value) -> str:
    return str(value or "").strip()[:MAX_TEAM_NAME]


def check_name_and_color(state: dict, msg: dict, ignore: str | None = None):
    """Validate a name + color pair. Returns (name, color, error)."""
    name = clean_team_name(msg.get("name"))
    color = msg.get("color")
    if not name:
        return None, None, "team name is required"
    if color not in TEAM_COLORS:
        return None, None, "pick one of the colors"
    for tid, t in state["teams"].items():
        if tid == ignore:
            continue
        if t["name"].casefold() == name.casefold():
            return None, None, "that team name is taken"
        if t["color"] == color:
            return None, None, "that color is taken"
    return name, color, None


def handle_hello(state: dict, conn: dict, msg: dict) -> str | None:
    """Record who this connection is. Returns an error string or None if OK."""
    role = msg.get("role")
    if role == "host":
        if msg.get("password") != HOST_PASSWORD:
            return "bad password"
        conn["role"], conn["team"] = "host", None
    elif role == "team":
        tid, token = msg.get("team_id"), msg.get("token")
        if tid is None:                       # a new phone that has not claimed a team yet
            conn["role"], conn["team"] = "team", None
            return None
        team = state["teams"].get(tid) if isinstance(tid, str) else None
        if team is None or not team["claimed"] or token != team["token"]:
            return "that team is not yours any more"
        conn["role"], conn["team"] = "team", tid
        team["session"] = conn["id"]    # newest phone takes over; older ones lose control
    elif role == "bingo":
        bid, token = msg.get("board_id"), msg.get("token")
        if bid is None:                       # a new bingo phone that has no board yet
            conn["role"], conn["team"], conn["board"] = "bingo", None, None
            return None
        board = state["boards"].get(bid) if isinstance(bid, str) else None
        if board is None or not board["claimed"] or token != board["token"]:
            return "that board is not yours any more"
        conn["role"], conn["team"], conn["board"] = "bingo", None, bid
        board["session"] = conn["id"]         # newest phone takes over, like a captain
    else:
        conn["role"], conn["team"], conn["board"] = "display", None, None
    return None


def claim_team(state: dict, conn: dict, msg: dict) -> str | None:
    """A captain takes an unclaimed team (host-freed) or creates a new one (lobby only)."""
    if conn["role"] != "team":
        return "say hello as a team first"
    if conn["team"] is not None:
        return "you already control a team"
    tid = msg.get("team_id")
    if tid is not None:                       # taking over a team the host freed
        team = state["teams"].get(tid) if isinstance(tid, str) else None
        if team is None or team["claimed"]:
            return "that team is not available"
    else:
        if state["phase"] != "lobby":
            return "the game has already started"
        name, color, error = check_name_and_color(state, msg)
        if error:
            return error
        tid = f"t{state['next_id']}"
        state["next_id"] += 1
        team = state["teams"][tid] = new_team(name, color)
    team["claimed"] = True
    team["token"] = secrets.token_urlsafe(16)
    team["session"] = conn["id"]
    conn["team"] = tid
    conn["reply"] = {"type": "claimed", "team_id": tid, "token": team["token"]}
    return None


def board_controller(state: dict, conn: dict) -> dict | None:
    """The board this connection controls, or None."""
    board = state["boards"].get(conn.get("board"))
    if conn["role"] == "bingo" and board and board.get("session") == conn["id"]:
        return board
    return None


def handle_bingo(state: dict, conn: dict, msg: dict) -> str | None:
    kind = msg.get("type")
    if kind == "bingo_pick":
        if conn["role"] != "bingo":
            return "say hello as a bingo player first"
        if conn["board"] is not None:
            return "you already have a board"
        bid = msg.get("board_id")
        board = state["boards"].get(bid) if isinstance(bid, str) else None
        if board is None or board["claimed"]:
            return "that board is taken"
        board.update(claimed=True, token=secrets.token_urlsafe(16), session=conn["id"])
        conn["board"] = bid
        conn["reply"] = {"type": "board_claimed", "board_id": bid, "token": board["token"]}
        return None
    board = board_controller(state, conn)
    if board is None:
        return "you do not control a board"
    if kind == "bingo_mark":
        if not state["bingo_open"]:
            return "bingo is closed"
        i, on = msg.get("index"), msg.get("marked")
        if type(i) is not int or not 0 <= i < 16 or type(on) is not bool:
            return "bad square"
        board["marks"][i] = on
    elif kind == "bingo_team":
        tid = msg.get("team_id")
        if tid is not None and (not isinstance(tid, str) or tid not in state["teams"]):
            return "unknown team"
        board["team"] = tid
    return None


def handle(state: dict, conn: dict, msg: dict) -> str | None:
    """Apply one parsed message. Returns an error string or None if OK."""
    kind = msg.get("type")
    if kind == "hello":
        return handle_hello(state, conn, msg)
    if kind in HOST_ONLY and conn["role"] != "host":
        return f"{kind} is host only"

    if kind in ("bingo_pick", "bingo_mark", "bingo_team"):
        return handle_bingo(state, conn, msg)
    if kind == "claim":
        return claim_team(state, conn, msg)
    elif kind == "team_edit":
        if not controls(state, conn):
            return "you do not control a team"
        if state["phase"] != "lobby":
            return "teams are locked once the game starts"
        name, color, error = check_name_and_color(state, msg, ignore=conn["team"])
        if error:
            return error
        state["teams"][conn["team"]].update(name=name, color=color)
    elif kind == "buzz":
        # only the controlling phone, only while playing, only while open, first wins
        if (controls(state, conn) and state["phase"] == "playing"
                and state["buzzers_open"] and state["buzzed"] is None):
            state["buzzed"] = conn["team"]
            state["buzzers_open"] = False
            state["release_at"] = release_time(state)     # start the countdown
    elif kind == "phase":
        value = msg.get("phase")
        if value not in ("lobby", "playing"):
            return "phase must be lobby or playing"
        if value == "playing" and not any(t["claimed"] for t in state["teams"].values()):
            return "no team has joined yet"
        state["phase"] = value
        if value == "lobby":                  # going back to the lobby stops any round
            state["buzzers_open"], state["buzzed"], state["release_at"] = False, None, None
    elif kind == "free_team":
        team = state["teams"].get(msg.get("team_id"))
        if team is None:
            return "unknown team"
        team.update(claimed=False, token=None, session=None)
    elif kind == "remove_team":
        tid = msg.get("team_id")
        if tid not in state["teams"]:
            return "unknown team"
        del state["teams"][tid]
        for board in state["boards"].values():            # nobody scores for a deleted team
            if board["team"] == tid:
                board["team"] = None
        if state["buzzed"] == tid:
            state["buzzed"], state["release_at"] = None, None
    elif kind == "bingo_open":
        if type(msg.get("open")) is not bool:
            return "open must be true or false"
        state["bingo_open"] = msg["open"]
    elif kind == "bingo_free":
        board = state["boards"].get(msg.get("board_id"))
        if board is None:
            return "unknown board"
        board.update(claimed=False, token=None, session=None)
    elif kind == "apply_bingo":
        apply_bingo(state)
    elif kind == "theme":
        if msg.get("theme") not in THEMES:
            return "theme must be quiz or reveal"
        state["theme"] = msg["theme"]
    elif kind == "reset":
        # Wipes teams, scores and bingo cards. The host types the password again
        # as a "are you sure?" check, so a stray click cannot end the party.
        if msg.get("password") != HOST_PASSWORD:
            return "type the host password to reset"
        fresh = new_state()
        state.clear()
        state.update(fresh)     # change the SAME dict: everyone else holds a reference
    elif kind == "release":
        state["buzzed"] = None
        state["buzzers_open"] = True
        state["release_at"] = None                        # no countdown needed
    elif kind == "lock":
        state["buzzers_open"] = False
        state["release_at"] = None                        # the host wants them closed
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
        media = msg.get("media")
        if media is not None and not isinstance(media, dict):
            return "media must be an object or null"
        state["media"] = media
    elif kind == "auto_release":
        try:
            seconds = float(msg.get("seconds"))
        except (TypeError, ValueError):
            return "seconds must be a number"
        if not 0 <= seconds <= 60:                        # also rejects nan and inf
            return "seconds must be between 0 and 60"
        state["auto_release_seconds"] = seconds
    else:
        return f"unknown message type: {kind}"
    return None


def apply_bingo(state: dict) -> None:
    """Turn every board's lines into bonus points for the team it was assigned to.

    The bonus is RECALCULATED from scratch each time, so pressing the button twice
    gives the same result instead of adding the points twice.
    """
    for team in state["teams"].values():
        team["bingo_lines"] = 0
    for board in state["boards"].values():
        team = state["teams"].get(board["team"])
        if team is not None:
            team["bingo_lines"] += count_lines(board["marks"])
    for team in state["teams"].values():
        team["bingo_bonus"] = team["bingo_lines"] * POINTS_PER_LINE


# ------------------------------------------------- automatic reopening ---
def release_time(state: dict) -> float | None:
    """When the buzzers should reopen after a buzz happening now (None = never)."""
    seconds = state["auto_release_seconds"]
    return time.time() + seconds if seconds > 0 else None


def seconds_left(state: dict) -> float | None:
    """Seconds until the buzzers reopen, for the countdown on screens."""
    due = state["release_at"]
    if due is None or state["buzzed"] is None:
        return None
    return max(0.0, round(due - time.time(), 1))


def auto_release(state: dict, now: float) -> bool:
    """Reopen the buzzers if the winner's time is up. Returns True if it did."""
    due = state["release_at"]
    if state["buzzed"] is None or due is None or now < due:
        return False
    state["buzzed"] = None
    state["buzzers_open"] = True
    state["release_at"] = None
    return True


release_task: asyncio.Task | None = None


async def release_when_due() -> None:
    """Background timer: wait until release_at, then reopen and tell everyone."""
    while True:
        remaining = state["release_at"] - time.time()
        if remaining <= 0:
            break
        await asyncio.sleep(remaining)      # may wake a hair early, so loop and check
    if auto_release(state, time.time()):
        save_state()
        await broadcast_state()


def reschedule_release() -> None:
    """Make the timer match the state. Call after every accepted message."""
    global release_task
    if release_task is not None:
        release_task.cancel()               # a release or lock cancels the countdown
        release_task = None
    if state["release_at"] is not None and state["buzzed"] is not None:
        release_task = asyncio.create_task(release_when_due())

def save_state() -> None:
    """Write the game to disk (a team's live session id is NOT saved)."""
    saved = {**state,
             "teams": {tid: {k: v for k, v in t.items() if k != "session"}
                       for tid, t in state["teams"].items()},
             "boards": {bid: {k: v for k, v in b.items() if k != "session"}
                        for bid, b in state["boards"].items()}}
    with open(STATE_FILE, "w") as f:
        json.dump(saved, f)

def load_state() -> None:
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
        if "next_id" not in data or "boards" not in data:   # older version
            log.warning("state.json is from an older version; starting fresh")
            return
        state.update(data)
        for board in state["boards"].values():    # a save from before shuffling
            board.setdefault("order", shuffled_order())
        log.info("Loaded state (%d teams)", len(state["teams"]))
    except FileNotFoundError:
        pass
    except ValueError:
        log.warning("state.json is invalid; starting with a fresh state")

load_state()  # load the state from disk when the server starts
