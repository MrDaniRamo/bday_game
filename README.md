# Birthday Trivia

A party trivia game: a TV scoreboard, a buzzer on each team captain's phone, a secret bingo side game, and a host control page. Built with **Python (FastAPI, WebSockets)** and **React (Vite)**.

| Page | Opened on | Purpose |
|---|---|---|
| `/` | TV | Teams, scores, who buzzed, countdown, images and sounds |
| `/team` | Captains' phones | Create a team in the lobby, then buzz |
| `/bingo` | Secret players' phones | 4x4 card of the captain's habits; lines become bonus points |
| `/host` | Host (password) | Run the whole game |

## Quick start (Windows PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --reload
```

In a second window:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173/ for the TV and http://localhost:5173/host for the host (password `party`, change it with `$env:HOST_PASSWORD`). Phones on the same Wi-Fi use `http://<laptop-ip>:5173/team`.

## Learn more

- [`guide/GUIDE.md`](guide/GUIDE.md): how everything works, testing, a party-day checklist, troubleshooting and interview questions.
- [`CLAUDE.md`](CLAUDE.md): the project brief and message protocol.
