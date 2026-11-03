#!/bin/bash
# stop backend, delete saved game, start fresh
python - <<'PY'
import os,signal
for d in os.listdir("/proc"):
    if d.isdigit():
        try: c=open(f"/proc/{d}/cmdline").read().split("\0")
        except OSError: continue
        if c[:4]==["python","-m","uvicorn","main:app"]: os.kill(int(d),signal.SIGTERM)
PY
sleep 1; rm -f backend/state.json
(cd backend && AUTO_RELEASE_SECONDS=2 nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 > ../backend.log 2>&1 &)
sleep 3
