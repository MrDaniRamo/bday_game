# backend/main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import json

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Adjust this to your frontend's origin
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"status": "ok", "game": "Birthday Trivia", "version": "1.0.0"}

clients: set[WebSocket] = set()

async def broadcast(message: str):
    for ws in list(clients):
        try:
            await ws.send_text(message)
        except Exception:
            clients.discard(ws)

def handle_message(msg: dict) -> dict | None:
    kind = msg.get("type")
    if kind == "ping":
        return {"type": "pong"}
    if kind == "join":
        team = msg.get("team")
        if not team:
            return {"type": "error", "detail": "team is required"}
        print (f"Team {team} joined the game")
        return {"type": "joined", "team": team}
    return {"type": "error", "detail": f"unknown message type: {kind}"}

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.add(ws)
    try:
        while True:
            #text = await ws.receive_text() # waits for a message from the client
            #await ws.send_text(f"echo: {text}") # sends a message back to the client
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    raise ValueError("message must be a JSON object")
            except ValueError: #JSONcode Error is a ValueError
                await ws.send_text(json.dumps({"type": "error", "detail": "bad JSON"}))
                continue #keep the connection open
    except WebSocketDisconnect:
        print("Client disconnected")
        clients.discard(ws)
