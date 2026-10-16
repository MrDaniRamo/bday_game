import json
import main

from main import handle, new_state, new_team, view_for

REDS = {"role": "team", "team": "Reds"}
BLUES = {"role": "team", "team": "Blues"}

def host():
    return {"role": "host", "team": None}

def make():
    s = new_state()
    s["teams"] = {"Reds": new_team(), "Blues": new_team()}
    return s

def test_first_buzz_wins():
    s = make()
    s["buzzers_open"] = True
    handle(s, REDS, {"type": "buzz"})
    handle(s, BLUES, {"type": "buzz"})
    assert s["buzzed"] == "Reds"
    
def test_buzz_ignored_when_locked():
    s = make()
    handle(s, REDS, {"type": "buzz"})
    assert s["buzzed"] is None

def test_only_host_can_add_points():
    s = make()
    err = handle(s, REDS, {"type": "points", "team": "Reds", "delta": 10})
    assert err == "host only"
    assert s["teams"]["Reds"]["score"] == 0