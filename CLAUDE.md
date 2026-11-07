# Birthday Trivia: project brief for Claude Code

A trivia game for the owner's birthday, also used as **interview practice** (Python FastAPI + React/Vite).
The owner wants Claude Code to **build the remaining parts and write explanatory guides** so they can
understand the code (what, why, how to test, interview questions). Build first, verify, then explain.

## Working rules
- Windows + PowerShell user. Use `python -m uvicorn`, `python -m pytest`, `curl.exe`. Give commands for PowerShell.
- Keep code readable and commented for a learner. Prefer small functions. No new dependencies without a reason.
- Run `python -m pytest` (backend) and `npm run build` (frontend) before saying something works.
- Guides: step-by-step, short code excerpts, checkpoints, troubleshooting table, interview questions.
  Write them as PDF or Markdown into `guide/`. Say honestly what was not tested (real phones, Wi-Fi, firewall).
- The server is the single source of truth. Never trust the client. Secrets never go to roles that must not see them.

## The game
1. **Main TV display** (`/`): team names (in their colors), scores, who buzzed, countdown, images/sounds from the host.
2. **Team phone** (`/team`): exactly ONE captain per team controls the buzzer. In the pre-game **lobby** the captain
   creates the team (name + color from a fixed palette, both unique) and can edit them until the host starts the game.
   A private token (saved in localStorage) lets the captain resume after refresh/restart; a newer phone with the token takes control.
3. **Host page** (`/host`, password): start game, release/lock buzzers, reopen delay, add points per team,
   free/remove teams, media, bingo panel. Currently a placeholder.
4. **Buzzer**: server decides the first buzz (handler is synchronous, no race). After a buzz the buzzers reopen by
   themselves after `AUTO_RELEASE_SECONDS` (default 5); the host can also release/lock manually.
5. **Secret bingo** (`/bingo`): separate devices, secret. Preset 4x4 cards in `backend/boards.py` (16 phrases/habits of
   each team's captain). The party has **5 teams**, so there are 5 cards (`b1`..`b5`). One player per card (private token). Player ticks squares; the SERVER counts lines (10 possible).
   Player picks their team from a drop-down once teams exist. Works before the game starts. At the end the host sends
   `apply_bingo`, which sets each team's `bingo_bonus = lines * POINTS_PER_LINE` (idempotent). Scoreboard total = score + bonus.

## Status
DONE and verified (42 pytest tests; Playwright phone tests `e2e.py`, `e2e_bingo.py`, `e2e_host.py`):
backend `backend/main.py`, `backend/boards.py`, `backend/test_game.py`; frontend display, team phone, bingo page,
and the host page (`frontend/src/pages/Host.jsx`: login, start/lobby, buzzers + reopen delay, points, free/remove,
media from `backend/media/`, bingo panel with apply and reveal, password-confirmed reset). Guide: `guide/GUIDE.md`.
Looks: `quiz` (black stage, sticker cards, marker font) for TV + team phones until the host reveals the bingo,
then `reveal` (70s game-show set: blue wall, red/orange/yellow/maroon stripes and rings, marquee bulbs); bingo + host always `reveal`. Set by `lib/useTheme.js` as `<html data-theme>`; colors/fonts are tokens in `index.css`.
TODO:
- Real phrases are in `backend/boards.py` (cards Max, Oto, Pato, Aldape, Gugin), but some are still "falta"
  placeholders: Max 6, Gugin 4 (Pato is complete). Replace them when the owner sends the missing phrases.
- Dry run on real phones over Wi-Fi (see Network below), then the party-day checklist in the guide.
- The old PDF guides are outdated; `guide/GUIDE.md` replaces them.

## Message protocol (JSON over WebSocket `/ws`, shape `{"type": ..., ...}`)
hello{role: display|team|bingo|host, ...}; team: claim{name,color | team_id}, team_edit{name,color}, buzz;
host: phase, release, lock, points{team(id),delta}, media, auto_release{seconds}, free_team, remove_team,
bingo_open, bingo_free, apply_bingo, reset{password}, theme{theme: quiz|reveal}; bingo: bingo_pick{board_id}, bingo_mark{index,marked}, bingo_team{team_id}.
Server replies: `state` (per-role filtered view), `error{detail}` (sender only), private `claimed` / `board_claimed` with a token.
Teams are keyed by id (`t1`, `t2`...), not name. Game state is saved to `backend/state.json` (delete it, or use the host Reset, to start fresh).
Media: files in `backend/media/` are served at `:8000/media/<name>`; the host view lists them as `media_files`.

## Commands
Backend (from `backend/`, virtual env active): `python -m pip install -r requirements.txt`,
`python -m uvicorn main:app --host 0.0.0.0 --reload`, `python -m pytest`. Env: `HOST_PASSWORD` (default `party`),
`AUTO_RELEASE_SECONDS`, `POINTS_PER_LINE`.
Frontend (from `frontend/`): `npm install`, `npm run dev` (vite listens on the network), `npm run build`.
Browser tests: `pip install playwright websockets` then `playwright install chromium`; run `python e2e.py`,
`python e2e_bingo.py` and `python e2e_host.py` (one per fresh start) from the project root with both servers up and a fresh `state.json` (`reset.sh` is a bash helper; on
Windows delete `backend/state.json` and restart the backend; the e2e scripts also assume `AUTO_RELEASE_SECONDS=2`).

## Network (phones)
Same Wi-Fi, open `http://<laptop-ip>:5173/team`. Windows: set network to Private, allow ports 5173 and 8000 in the firewall.
CORS already allows private-network origins on port 5173 (WebSockets are not subject to CORS).
`tools/make_qr.py` makes a QR for the team page. Never publish the bingo link; send it privately.
