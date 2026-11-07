# Birthday Trivia: the complete guide

This guide explains the whole project as it is in this repository: what each part does, why it was built that way, how to run and test it, and how to talk about it in a job interview. It replaces the older PDF guides (Parts 1 to 6), which describe an earlier join flow and bingo codes.

**Contents**

1. [The game in one minute](#1-the-game-in-one-minute)
2. [Architecture](#2-architecture)
3. [Running it on Windows](#3-running-it-on-windows)
4. [The message protocol](#4-the-message-protocol)
5. [Why the server decides the buzz](#5-why-the-server-decides-the-buzz)
6. [Roles, views and privacy](#6-roles-views-and-privacy)
7. [Tokens: captains and bingo players](#7-tokens-captains-and-bingo-players)
8. [Lobby and playing phases](#8-lobby-and-playing-phases)
9. [The auto-reopen timer](#9-the-auto-reopen-timer)
10. [Secret bingo scoring](#10-secret-bingo-scoring)
11. [The host page (Part 5)](#11-the-host-page-part-5)
12. [The React side](#12-the-react-side)
13. [Saving and resetting](#13-saving-and-resetting)
14. [Testing](#14-testing)
15. [Party-day checklist](#15-party-day-checklist)
16. [Troubleshooting](#16-troubleshooting)
17. [What has not been tested](#17-what-has-not-been-tested)
18. [Interview questions and answers](#18-interview-questions-and-answers)

---

## 1. The game in one minute

| Page | Who opens it | What it does |
|---|---|---|
| `/` | The TV | Team names in their colors, scores, who buzzed, the countdown, and the host's images and sounds |
| `/team` | One captain per team | Create the team in the lobby (name and color), then a big buzzer |
| `/bingo` | One secret player per team | A 4x4 card of the captain's habits; the server counts completed lines |
| `/host` | You (password) | Start the game, buzzers, points, media, free or remove teams, bingo panel, reset |

All four pages are one React app. `frontend/src/main.jsx` picks the page from the URL.

---

## 2. Architecture

```
  TV (/)        Captain phones (/team)     Bingo phones (/bingo)     Host (/host)
     \                 |                          |                     /
      \________________|__________________________|____________________/
                                    |
                         WebSocket  ws://<laptop>:8000/ws
                                    |
                     FastAPI server (backend/main.py)
                      - one game state dict (the truth)
                      - handle(state, conn, msg) applies a message
                      - view_for(state, conn) filters it per role
                      - state.json on disk, media/ served over HTTP
```

**Key ideas**

- **One source of truth.** The server holds the only real copy of the game, in the `state` dict. Pages never change scores themselves. They send a request and wait for the new state.
- **Full state after every change.** After each accepted message the server sends every connection its own filtered copy of the whole state (`broadcast_state`). At this size (a handful of phones), sending everything is simpler than sending only the changes, and it's harder to get wrong. A page that missed a message is fixed by the next one.
- **Two servers in development.** Vite (port 5173) serves the React pages. FastAPI (port 8000) serves the WebSocket and the media files. The pages connect to port 8000 on the same host name they were loaded from (`useGame.js`), so a phone that opened `http://192.168.1.23:5173/team` talks to `192.168.1.23:8000`.
- **One process only.** `state` and `connections` are module-level variables. That only works with one server process, which is plenty for a party. Scaling out would need shared storage like Redis (see the interview questions).

**Files**

| File | What's in it |
|---|---|
| `backend/main.py` | The whole server: state, message handling, views, timer, saving, media |
| `backend/boards.py` | The preset bingo cards (edit this with your captains' phrases) |
| `backend/test_game.py` | 42 pytest tests of the game rules |
| `backend/media/` | Images and sounds the host can put on the TV |
| `frontend/src/useGame.js` | The WebSocket hook every page uses |
| `frontend/src/pages/*.jsx` | Display, Team, Bingo, Host |
| `frontend/src/components/` | Scoreboard, MediaLayer, BuzzerButton, ColorPicker |
| `frontend/src/lib/` | Small helpers: saved tokens, buzzer status, countdown |
| `e2e.py`, `e2e_bingo.py`, `e2e_host.py` | Browser tests in phone-sized windows |

---

## 3. Running it on Windows

Run these in PowerShell from the project folder.

**Backend, first time**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**Backend, every time** (virtual environment active, inside `backend`)

```powershell
python -m uvicorn main:app --host 0.0.0.0 --reload
```

Checkpoint: http://localhost:8000/ shows `{"status":"ok",...}`.

**Frontend** (a second PowerShell window, inside `frontend`)

```powershell
npm install
npm run dev
```

Checkpoint: http://localhost:5173/ shows "Birthday Trivia", and http://localhost:5173/host asks for a password (`party` unless you set `HOST_PASSWORD`).

**Settings** (set them before starting uvicorn, in the same window)

```powershell
$env:HOST_PASSWORD = "something-secret"
$env:AUTO_RELEASE_SECONDS = "5"
$env:POINTS_PER_LINE = "10"
```

---

## 4. The message protocol

Every message is a JSON object with a `type`. The first message from every page is `hello`, and it's sent again on every reconnect because the server forgets a connection when it drops.

| Sent by | Message | What it does |
|---|---|---|
| anyone | `hello {role, ...}` | Say who you are. Host: `password`. Captain: `team_id` + `token`. Bingo: `board_id` + `token`. |
| captain | `claim {name, color}` or `claim {team_id}` | Create a team (lobby only), or take over a freed team |
| captain | `team_edit {name, color}` | Change name or color (lobby only) |
| captain | `buzz` | Try to buzz |
| bingo | `bingo_pick {board_id}` | Take a free card |
| bingo | `bingo_mark {index, marked}` | Tick or untick square 0 to 15 |
| bingo | `bingo_team {team_id}` | Choose your team in the drop-down (`null` clears it) |
| host | `phase {phase}` | `"playing"` starts the game, `"lobby"` goes back |
| host | `release`, `lock` | Open the buzzers (clears the winner), or close them |
| host | `auto_release {seconds}` | Reopen delay after a buzz, 0 to 60 (0 = never) |
| host | `points {team, delta}` | Add or remove points |
| host | `media {media}` | `{id, type: "image"/"sound", src}` or `null` to clear |
| host | `free_team`, `remove_team {team_id}` | Free a team for a new phone, or delete it |
| host | `bingo_open {open}`, `bingo_free {board_id}` | Close or reopen ticking, free a card |
| host | `apply_bingo` | Turn lines into bonus points |
| host | `reset {password}` | Start a fresh game (password typed again to confirm) |
| host | `theme {theme}` | `"quiz"` (default) or `"reveal"`: the look of the TV and the captains' phones |

**Server replies**

- `state {state}`: the sender's own filtered view, sent to everyone after every accepted change.
- `error {detail}`: sent only to the sender, for example `"that color is taken"`.
- `claimed {team_id, token}` and `board_claimed {board_id, token}`: private replies, sent only to the phone that claimed.

All the host-only types are listed in one place, `HOST_ONLY`, and checked once before any handler runs:

```python
if kind in HOST_ONLY and conn["role"] != "host":
    return f"{kind} is host only"
```

That's safer than remembering a check in every branch.

---

## 5. Why the server decides the buzz

If each phone decided "I was first" from its own clock, phones with slow clocks or slow Wi-Fi would disagree. Instead, a phone only sends `buzz`, and the server decides.

```python
elif kind == "buzz":
    if (controls(state, conn) and state["phase"] == "playing"
            and state["buzzers_open"] and state["buzzed"] is None):
        state["buzzed"] = conn["team"]
        state["buzzers_open"] = False
```

**Why there's no race.** FastAPI runs on one asyncio event loop. `handle()` is a normal (not `async`) function with no `await` inside, so once it starts, nothing else runs until it returns. The first `buzz` to reach the server sets `buzzed`. The second one finds `buzzed` already set and is ignored. No lock is needed.

**Fair enough for a party.** "First" means "first to arrive at the server". A phone on worse Wi-Fi is a few milliseconds behind. Measuring the press time on the phone wouldn't help, because the phone's clock isn't trusted.

---

## 6. Roles, views and privacy

Each connection has a small record: `{"id", "role", "team", "board"}`. `view_for(state, conn)` builds what that role may see.

| Role | Sees |
|---|---|
| display | teams (no tokens), buzzer status, media, which cards are taken (no ticks) |
| team | the same, plus `you: {team, controller}` |
| bingo | the same, plus `my_board` (its phrases, ticks and lines) |
| host | everything except tokens and session ids, plus `media_files` and `points_per_line` |

The rule is **filter on the server, never in the browser**. Hiding something with CSS or a React `if` doesn't protect it, because anyone can open the browser's developer tools and read the WebSocket messages. A test checks this: `test_marks_and_tokens_never_reach_public_views`.

---

## 7. Tokens: captains and bingo players

When a captain creates a team, the server makes a random secret and replies privately:

```python
team["token"] = secrets.token_urlsafe(16)
conn["reply"] = {"type": "claimed", "team_id": tid, "token": team["token"]}
```

The phone stores `{team_id, token}` in `localStorage` (`lib/savedTeam.js`) and sends it in every `hello`. That gives you three things.

- **Resume after a refresh or a server restart.** The token is in the phone and in `state.json`.
- **Nobody else can control your team.** The team id is public, but the token isn't.
- **One controller.** `team["session"]` remembers which connection controls the team. A newer phone with the token takes over, and the older one shows "Take control back". The session id isn't saved to disk, because connection ids restart from 1 after a server restart.

`secrets`, not `random`, is used because `secrets` is designed to be unguessable. Bingo cards work the same way (`board_claimed`, `lib/savedBoard.js`).

When the host **frees** a team, its token is set to `None`, so the old phone's next `hello` fails with "that team is not yours any more". The phone then forgets its saved token and shows the join screen, where any phone can take the team over.

---

## 8. Lobby and playing phases

`state["phase"]` is `"lobby"` or `"playing"`.

- **Lobby:** captains create teams and can change names and colors. Names must be unique (ignoring capital letters), and colors come from a fixed palette of 8, one per team. Buzzing does nothing.
- **Playing:** names are locked, no new teams can be created (a freed team can still be taken over), and buzzing works.
- The host can't start with zero teams. Going back to the lobby stops any round.

Checking `phase` on the server matters. A phone could be modified to send `team_edit` after the start, and the server refuses it anyway.

---

## 9. The auto-reopen timer

After a buzz, the buzzers reopen by themselves after `auto_release_seconds` (default 5, host-adjustable, 0 turns it off).

- The state stores **when** to reopen: `release_at`, a server clock time.
- The views send **how long is left**: `release_in`, in seconds. A phone's clock can be minutes off, so the server never sends it a clock time. `useCountdown.js` adds the seconds left to the phone's own clock.
- `reschedule_release()` runs after every accepted message. It cancels the old background task and starts a new one if a countdown is running. So `release` and `lock` cancel the timer just by clearing `release_at`.
- On startup, the `lifespan` hook calls `reschedule_release()`, so a countdown that was running before a restart continues.
- `auto_release(state, now)` is a plain function that takes the time as an argument. Tests can pass any time without waiting.

---

## 10. Secret bingo scoring

- Cards are preset in `backend/boards.py`: an id, a title and exactly 16 phrases. There are 5 cards, one for each captain: Max, Oto, Pato, Aldape and Gugin. A few squares still say "falta" (Max 6, Gugin 4). **Replace those with real phrases before the party.**
- Bingo works from the start, before any team exists. The team drop-down fills in as captains create teams.
- The phone only says "square 5 is ticked". The **server counts the lines**: 4 rows, 4 columns and 2 diagonals.

```python
def count_lines(marks: list) -> int:
    return sum(all(marks[i] for i in line) for line in LINES)
```

- Nothing shows on the TV until the host presses **Apply bingo bonus**. Then each team gets `bingo_bonus = lines x POINTS_PER_LINE`, and the TV shows the new total with "incl. +20 bingo" under it.
- `apply_bingo` **recalculates from scratch**. Pressing it twice gives the same answer instead of adding twice. That property is called idempotent. It also means that if a player changes team or ticks more squares, pressing Apply again corrects the bonus.

---

## 11. The host page (Part 5)

`frontend/src/pages/Host.jsx`, split into small components, one per panel.

- **Login.** The password goes into `hello`. If the server answers `bad password`, the page shows the login form again. The password is kept in `sessionStorage`, so a refresh doesn't log you out, but closing the tab does.
- **Header:** the phase badge, plus **Start game** or **Back to lobby**.
- **Buzzers:** who buzzed, the countdown, Open/Release, Lock, and the reopen-delay box.
- **Teams:** one row per team, with +1, +5, +10, -1 and -5, Free and Remove. Free and Remove ask "are you sure?" first.
- **Images and sounds:** every file in `backend/media/` gets a Show or Play button, plus a "web address" box and Clear the screen. Each send gets a new `id` (`Date.now()`), so the TV plays the same sound again when you press it twice.
- **Secret bingo:** open or close ticking, a table of every card (taken, team, lines, ticks) with Free, a preview of the bonus, and **Apply bingo bonus**.
- **Reset:** wipes everything. You type the host password again, and the server checks it.

**Media files.** Drop images (`.png`, `.jpg`, `.gif`, `.webp`) or sounds (`.mp3`, `.wav`, `.ogg`, `.m4a`) into `backend/media/`. The server serves them at `http://<laptop>:8000/media/<name>`, and the host list re-reads the folder on every update, so no restart is needed. Use short names without spaces.

**The two looks and the reveal.** The TV and the captains' phones start in the **quiz look**: a black halftone stage, tilted sticker cards and marker lettering. The bingo and host pages always use the **reveal look**, a 70s game-show set: a dusty-blue wall with red, orange, yellow and maroon stripes, ring medallions, marquee light bulbs at the sides of big screens, a peach floor, rounded arch-like cards, and a buzzer made of nested rings. At the end of the night, press **Reveal the secret bingo** in the bingo panel. The TV plays a "Plot twist! Let's get ready for a Game Changer!" animation for about 7 seconds, and then the TV and the phones switch to the reveal look, so the whole party ends in the bingo game's look. **Back to the quiz look** undoes it, and Reset also goes back to the quiz look. A good order: Close ticking, Apply bingo bonus, play a sound, then Reveal.

How it works: the server keeps `state["theme"]` (`"quiz"` or `"reveal"`), and only the host can change it, with `theme {theme}`. Every page calls `useTheme(...)` (`lib/useTheme.js`), which sets `<html data-theme="...">`. `index.css` defines its colors and fonts as tokens (`--bg`, `--card`, `--accent`, ...) once per theme, so changing the attribute changes the whole look. The fonts come from Google Fonts. Without internet, the pages fall back to system fonts and still work.

**Sound on the TV.** Browsers block sound until the page has been clicked. Click "Click to enable sound" on the TV once after opening it.

---

## 12. The React side

**`useGame(identity, onMessage)`** is the one hook every page uses.

- It opens the WebSocket, sends `hello`, and keeps the latest `state`.
- It reconnects 1 second after a drop and says `hello` again.
- When a phone wakes up (`visibilitychange`), it replaces the socket. A sleeping phone can hold a dead connection that still looks open.
- It ignores events from old sockets (`if (wsRef.current !== ws) return`).
- `send(msg)` does nothing while disconnected, instead of throwing an error.

**Derived data isn't stored.** The scoreboard order and totals are computed on each render from `state.teams`. Storing them separately would let them get out of date.

**Pages read, the server decides.** For example, the buzzer button is enabled only when `state.buzzers_open`, but even a hacked button can't win, because the server checks again.

**Hooks before early returns.** React needs the same hooks in the same order on every render. That's why `useCountdown` is called before the `if (!state) return ...` lines.

---

## 13. Saving and resetting

- After every accepted message, `save_state()` writes `backend/state.json`, without the live session ids. On startup, `load_state()` reads it back. A file from an older version is ignored.
- **Fresh game, option 1:** the Reset panel on the host page.
- **Fresh game, option 2:** stop the backend, delete `backend/state.json`, and start it again.
- Reset changes the same `state` dict instead of making a new one (`state.clear(); state.update(fresh)`). Other code holds a reference to that dict, so replacing it would leave them looking at the old game.
- After a reset, the phones' saved tokens no longer match anything. Captains land on "Start your team" and bingo players on "Pick your card".

---

## 14. Testing

**Unit tests (pytest), 42 tests.** These test `handle()`, `view_for()` and the timer functions directly with plain dicts, so there's no network and no waiting.

```powershell
cd backend
python -m pytest
```

They cover joining, unique names and colors, tokens and takeover, the phases, the first buzz, points validation, host-only messages, the timer, bingo counting and secrecy, idempotent apply, media listing and reset.

**Browser tests (Playwright).** These run real Chromium windows at phone size against both servers.

```powershell
pip install playwright websockets
playwright install chromium
```

Start the backend with `$env:AUTO_RELEASE_SECONDS = "2"` and no `state.json`, start `npm run dev`, then from the project root run one script per fresh start:

```powershell
python e2e.py
python e2e_bingo.py
python e2e_host.py
```

- `e2e.py`: lobby, duplicate names, edits, buzz, auto-reopen, takeover, free and remove, server restart.
- `e2e_bingo.py`: pick a card, ticks, reload, team drop-down, secrecy on the TV, apply bonus.
- `e2e_host.py`: drives the host page itself. It covers login, start, the delay box, buzz, lock, points, image and sound, bingo apply (twice), free, reset, and checks that the host page fits a phone.

Delete `backend/state.json` and restart the backend before each script. Each one assumes an empty game. `e2e.py` restarts the backend itself, and its restart command is written for Linux.

---

## 15. Party-day checklist

**The week before**

- [ ] Replace the "falta" placeholders in `backend/boards.py` (Max 6, Gugin 4). Each card must keep exactly 16 phrases.
- [ ] Put your images and sounds in `backend/media/`.
- [ ] Set your own `HOST_PASSWORD`.
- [ ] Do a dry run on real phones (see below).

**Network setup**

- [ ] Laptop and phones on the same Wi-Fi. Guest networks often block phone-to-laptop traffic, so use the main one.
- [ ] Windows: set the Wi-Fi network to **Private**.
- [ ] Allow ports **5173** and **8000** through the Windows firewall, or accept the prompt the first time.
- [ ] Find the laptop IP with `ipconfig` (IPv4 Address, for example `192.168.1.23`).
- [ ] Make a QR for the team page: `python tools/make_qr.py http://192.168.1.23:5173/team` (needs `pip install qrcode[pil]`).
- [ ] Send the bingo link (`http://192.168.1.23:5173/bingo`) **privately** to each bingo player. Never show it on the TV.

**On the night**

1. Start the backend and frontend.
2. Open `/` on the TV and click "enable sound".
3. Open `/host` on your phone or laptop.
4. Bingo players pick their cards whenever they arrive.
5. Captains scan the QR and create teams. Bingo players then pick their team.
6. Press **Start game**.
7. At the end: **Close ticking**, then **Apply bingo bonus**, then **Reveal the secret bingo**.

---

## 16. Troubleshooting

| Problem | Likely cause | Fix |
|---|---|---|
| Phone can't open the page | Firewall, Public network, or a guest Wi-Fi | Set the network to Private, allow ports 5173 and 8000, use the main Wi-Fi |
| Page opens but says "Connecting…" forever | The backend isn't running, or port 8000 is blocked | Check `http://<ip>:8000/` from the phone |
| `No module named pytest` / `fastapi` | The virtual environment isn't active | `.\.venv\Scripts\Activate.ps1`, then `python -m pytest` |
| PowerShell won't run `Activate.ps1` | Execution policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Host login keeps failing | `HOST_PASSWORD` set in a different window | Set it in the same window before starting uvicorn |
| No sound on the TV | Autoplay blocked | Click "Click to enable sound" on the TV |
| Image doesn't appear | Wrong file name, or a file that's not an image | Check it's in `backend/media/` with a supported extension |
| Old teams come back after a restart | `state.json` was restored | Use Reset on the host page, or delete `backend/state.json` |
| "that team is not yours any more" | The host freed or removed the team, or a reset | The phone goes back to the join screen. Take the team over or create it again. |
| Bingo bonus seems wrong | The player changed team after Apply | Press Apply again. It recalculates. |

---

## 17. What has not been tested

The automated tests ran on Linux with headless Chromium in phone-sized windows. These haven't been tried:

- **Real phones** (iOS Safari, Android Chrome) over **real Wi-Fi**.
- The **Windows firewall** and Private network steps.
- **Sound on a real TV browser.** In the tests, the sound message reaches the TV, but nobody listened to it.
- **Many phones at once.** The game will have 10 phones (5 captains, 5 bingo players) plus the TV and the host. That should be fine, but it hasn't been load-tested. The TV layout was checked with 5 teams at 720p and 1080p.
- `e2e.py`'s server restart step on Windows. It uses Linux `/proc` to find the server.

Do a dry run with two or three real phones before the party.

---

## 18. Interview questions and answers

**1. Walk me through the architecture.**
A FastAPI backend holds the whole game in one Python dict and talks to every screen over a WebSocket. The React frontend has four pages that all use one `useGame` hook. After each accepted message, the server sends each client a filtered copy of the whole state, so all screens stay in sync.

**2. Why WebSockets instead of HTTP polling?**
The buzzer needs the server to push changes to everyone immediately. Polling would add delay and waste requests. WebSockets keep one open, two-way connection per screen.

**3. How do you make sure only one team wins a buzz?**
The server decides. The buzz handler is synchronous code on a single asyncio event loop, so messages are handled one at a time. The first `buzz` sets `buzzed` and closes the buzzers. Later ones see that and do nothing.

**4. Why send the full state instead of only the changes?**
It's simpler and it heals itself: a client that missed a message is corrected by the next one. At party scale, the extra bytes don't matter. With thousands of clients, I'd switch to sending only the changes, or patches.

**5. How do you keep secrets away from clients that shouldn't see them?**
`view_for` builds a separate view per role on the server. The TV and phones never receive tokens, bingo phrases or ticks. Hiding data in the UI isn't security, because WebSocket messages are visible in the browser's developer tools. A test checks the views.

**6. How does a captain get back in after a refresh?**
When they create the team, the server gives that phone a random secret token in a private reply. The phone stores it in `localStorage` and sends it in every `hello`. The token is also saved in `state.json`, so it works after a server restart too.

**7. Why `secrets.token_urlsafe` and not `random`?**
`random` is predictable if you know its state. `secrets` uses the operating system's secure random source, so the tokens can't be guessed.

**8. What if two phones use the same token?**
The newest `hello` takes control (`team["session"] = conn["id"]`), and the other phone sees "Take control back". Only one phone can buzz at a time.

**9. How does the auto-reopen work, and why send seconds instead of a time?**
The server stores `release_at` and runs an asyncio task that sleeps until then. After every message, `reschedule_release` cancels and recreates that task to match the state. Clients get "seconds left", because a phone's clock can be wrong. The phone counts down from its own clock.

**10. What does idempotent mean here?**
Pressing Apply bingo twice gives the same result. The bonus is recalculated from the cards instead of added. Retries and double-clicks become harmless.

**11. How did you test it?**
42 pytest unit tests call the pure functions (`handle`, `view_for`, `auto_release`) with plain dicts. Passing the time in as an argument means no waiting. Three Playwright scripts drive real browsers at phone size through full games, including the host page and a server restart.

**12. What are the limits of this design?**
State lives in one process's memory, plus a JSON file. It can't run as several server processes, and there's no database or real user accounts. To scale, I'd move the state into Redis or a database with transactions, use pub/sub to tell every server about changes, and add proper authentication.

**13. How is the host protected?**
The password is checked on the server in `hello`. Every host-only message type is in one `HOST_ONLY` set, checked before any handler runs. Reset needs the password typed again. Over plain `http`, the password isn't encrypted on the Wi-Fi. That's acceptable at home, but for a real deployment I'd use HTTPS/WSS and a proper login.

**14. How do you validate input?**
Never trust the client. The server checks types (`type(i) is not int`), ranges (square 0 to 15, delay 0 to 60, which also rejects NaN), allowed values (the color palette, the phase), unique names (ignoring capitals) and name length. Errors go only to the sender, and the connection stays open.

**15. What would you improve next?**
HTTPS for the host, a proper media upload instead of a folder, an undo for points, and a "results" screen at the end. I'd also add frontend unit tests with Vitest, and move the server into modules (`state.py`, `handlers.py`, `views.py`) as it grows.
