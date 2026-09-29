# backend/main.py
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def read_root():
    return {"status": "ok", "game": "Birthday Trivia", "version": "1.0.0"}

