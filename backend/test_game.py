import json
import pytest

from main import (TEAM_COLORS, auto_release, handle, new_state, seconds_left,
                  view_for)

_ids = iter(range(1, 10**6))


def phone():
    """A fresh connection that has said hello as a team (no team yet)."""
    return {"id": next(_ids), "role": "team", "team": None}


def host():
    return {"id": next(_ids), "role": "host", "team": None}


def claim(s, conn, name, color):
    err = handle(s, conn, {"type": "claim", "name": name, "color": color})
    assert err is None, err
    return conn.pop("reply")


@pytest.fixture
def game():
    """Two claimed teams, game started. Returns (state, reds_conn, blues_conn, ids)."""
    s = new_state()
    a, b = phone(), phone()
    ra = claim(s, a, "Reds", TEAM_COLORS[0])
    rb = claim(s, b, "Blues", TEAM_COLORS[3])
    assert handle(s, host(), {"type": "phase", "phase": "playing"}) is None
    return s, a, b, (ra["team_id"], rb["team_id"])


# ---------- joining ----------
def test_claim_creates_a_team_and_a_private_token():
    s = new_state()
    c = phone()
    reply = claim(s, c, "  Greens  ", TEAM_COLORS[2])
    team = s["teams"][reply["team_id"]]
    assert team["name"] == "Greens" and team["claimed"] and team["color"] == TEAM_COLORS[2]
    assert reply["token"] == team["token"] and c["team"] == reply["team_id"]


def test_name_and_color_must_be_unique_and_valid():
    s = new_state()
    claim(s, phone(), "Reds", TEAM_COLORS[0])
    other = phone()
    assert "name" in handle(s, other, {"type": "claim", "name": "reds", "color": TEAM_COLORS[1]})
    assert "color" in handle(s, other, {"type": "claim", "name": "Blues", "color": TEAM_COLORS[0]})
    assert handle(s, other, {"type": "claim", "name": "Blues", "color": "#123456"})
    assert handle(s, other, {"type": "claim", "name": "  ", "color": TEAM_COLORS[1]})
    assert len(s["teams"]) == 1


def test_one_phone_cannot_claim_two_teams():
    s = new_state()
    c = phone()
    claim(s, c, "Reds", TEAM_COLORS[0])
    assert handle(s, c, {"type": "claim", "name": "Blues", "color": TEAM_COLORS[1]})


def test_no_new_teams_after_the_game_starts(game):
    s, *_ = game
    assert "started" in handle(s, phone(), {"type": "claim", "name": "Late", "color": TEAM_COLORS[5]})


def test_captain_edits_name_and_color_only_in_the_lobby():
    s = new_state()
    c = phone()
    tid = claim(s, c, "Reds", TEAM_COLORS[0])["team_id"]
    assert handle(s, c, {"type": "team_edit", "name": "Crimson", "color": TEAM_COLORS[4]}) is None
    assert s["teams"][tid]["name"] == "Crimson"
    # keeping your own name/color is not a clash
    assert handle(s, c, {"type": "team_edit", "name": "Crimson", "color": TEAM_COLORS[4]}) is None
    handle(s, host(), {"type": "phase", "phase": "playing"})
    assert handle(s, c, {"type": "team_edit", "name": "X", "color": TEAM_COLORS[1]}) is not None


def test_resume_needs_the_right_token_and_takes_control():
    s = new_state()
    old = phone()
    r = claim(s, old, "Reds", TEAM_COLORS[0])
    new = phone()
    bad = {"type": "hello", "role": "team", "team_id": r["team_id"], "token": "nope"}
    assert handle(s, new, bad) is not None and new["team"] is None
    good = {**bad, "token": r["token"]}
    assert handle(s, new, good) is None and new["team"] == r["team_id"]
    handle(s, host(), {"type": "phase", "phase": "playing"})
    s["buzzers_open"] = True
    handle(s, old, {"type": "buzz"})              # the replaced phone is ignored
    assert s["buzzed"] is None
    handle(s, new, {"type": "buzz"})
    assert s["buzzed"] == r["team_id"]


def test_host_can_free_a_team_so_a_new_captain_takes_it(game):
    s, a, b, (ra, rb) = game
    token = s["teams"][ra]["token"]
    assert handle(s, a, {"type": "free_team", "team_id": ra}) is not None    # host only
    handle(s, host(), {"type": "free_team", "team_id": ra})
    ghost = phone()
    assert handle(s, ghost, {"type": "hello", "role": "team", "team_id": ra, "token": token})
    taker = phone()
    assert handle(s, taker, {"type": "claim", "team_id": ra}) is None
    assert s["teams"][ra]["token"] != token and taker["team"] == ra
    assert handle(s, phone(), {"type": "claim", "team_id": rb})              # still claimed


def test_host_can_remove_a_team(game):
    s, a, b, (ra, rb) = game
    s["buzzers_open"] = True
    handle(s, a, {"type": "buzz"})
    handle(s, host(), {"type": "remove_team", "team_id": ra})
    assert ra not in s["teams"] and s["buzzed"] is None and s["release_at"] is None


def test_cannot_start_with_no_teams():
    assert handle(new_state(), host(), {"type": "phase", "phase": "playing"}) is not None


def test_going_back_to_the_lobby_stops_the_round(game):
    s, a, *_ = game
    s["buzzers_open"] = True
    handle(s, a, {"type": "buzz"})
    handle(s, host(), {"type": "phase", "phase": "lobby"})
    assert s["buzzed"] is None and s["buzzers_open"] is False


# ---------- buzzer ----------
def test_first_buzz_wins(game):
    s, a, b, (ra, rb) = game
    s["buzzers_open"] = True
    handle(s, a, {"type": "buzz"})
    handle(s, b, {"type": "buzz"})
    assert s["buzzed"] == ra and s["buzzers_open"] is False


def test_buzz_ignored_when_locked_or_in_the_lobby(game):
    s, a, *_ = game
    handle(s, a, {"type": "buzz"})
    assert s["buzzed"] is None
    s["phase"], s["buzzers_open"] = "lobby", True
    handle(s, a, {"type": "buzz"})
    assert s["buzzed"] is None


def test_release_clears_winner_and_reopens(game):
    s, a, *_ = game
    s["buzzers_open"] = True
    handle(s, a, {"type": "buzz"})
    handle(s, host(), {"type": "release"})
    assert s["buzzed"] is None and s["buzzers_open"] is True


def test_points_by_id_and_validation(game):
    s, a, b, (ra, rb) = game
    assert handle(s, a, {"type": "points", "team": ra, "delta": 10}) is not None
    h = host()
    handle(s, h, {"type": "points", "team": ra, "delta": 10})
    handle(s, h, {"type": "points", "team": ra, "delta": -3})
    assert s["teams"][ra]["score"] == 7
    assert handle(s, h, {"type": "points", "team": "Nope", "delta": 1})
    assert handle(s, h, {"type": "points", "team": ra, "delta": "x"})
    assert handle(s, h, {"type": "points", "team": [ra], "delta": 1})


def test_wrong_host_password():
    s, conn = new_state(), {"id": 1, "role": "display", "team": None}
    err = handle(s, conn, {"type": "hello", "role": "host", "password": "nope"})
    assert err is not None and conn["role"] == "display"


# ---------- bingo ----------
def bingo_phone():
    return {"id": next(_ids), "role": "bingo", "team": None, "board": None}


def pick(s, conn, board_id="b1"):
    assert handle(s, conn, {"type": "bingo_pick", "board_id": board_id}) is None
    return conn.pop("reply")


def tick(s, conn, squares):
    for i in squares:
        assert handle(s, conn, {"type": "bingo_mark", "index": i, "marked": True}) is None


def test_a_board_can_only_be_taken_once():
    s = new_state()
    first, second = bingo_phone(), bingo_phone()
    reply = pick(s, first, "b1")
    assert reply["board_id"] == "b1" and reply["token"] == s["boards"]["b1"]["token"]
    assert "taken" in handle(s, second, {"type": "bingo_pick", "board_id": "b1"})
    assert handle(s, second, {"type": "bingo_pick", "board_id": "nope"}) is not None
    # one board each
    assert handle(s, first, {"type": "bingo_pick", "board_id": "b2"}) is not None


def test_bingo_phone_resumes_with_its_token_and_takes_control():
    s = new_state()
    old = bingo_phone()
    r = pick(s, old)
    new = bingo_phone()
    hello = {"type": "hello", "role": "bingo", "board_id": "b1", "token": "nope"}
    assert handle(s, new, hello) is not None and new["board"] is None
    assert handle(s, new, {**hello, "token": r["token"]}) is None and new["board"] == "b1"
    assert handle(s, old, {"type": "bingo_mark", "index": 0, "marked": True}) is not None
    assert handle(s, new, {"type": "bingo_mark", "index": 0, "marked": True}) is None


def test_lines_are_counted():
    from main import count_lines
    assert count_lines([False] * 16) == 0
    assert count_lines([True] * 16) == 10
    row = [i < 4 for i in range(16)]
    assert count_lines(row) == 1
    diag = [i in (0, 5, 10, 15) for i in range(16)]
    assert count_lines(diag) == 1
    anti = [i in (3, 6, 9, 12) for i in range(16)]
    assert count_lines(anti) == 1
    col_and_row = [i < 4 or i % 4 == 0 for i in range(16)]
    assert count_lines(col_and_row) == 2


def test_bad_marks_are_refused():
    s = new_state()
    c = bingo_phone()
    pick(s, c)
    for bad in ({"index": 16, "marked": True}, {"index": -1, "marked": True},
                {"index": "3", "marked": True}, {"index": True, "marked": True},
                {"index": 3, "marked": "yes"}, {"index": 3}):
        assert handle(s, c, {"type": "bingo_mark", **bad}) is not None
    assert not any(s["boards"]["b1"]["marks"])


def test_only_the_board_owner_can_mark_and_team_phones_cannot():
    s = new_state()
    c = bingo_phone()
    pick(s, c)
    assert handle(s, phone(), {"type": "bingo_mark", "index": 0, "marked": True}) is not None
    assert handle(s, bingo_phone(), {"type": "bingo_mark", "index": 0, "marked": True}) is not None


def test_marking_can_be_closed_by_the_host():
    s = new_state()
    c = bingo_phone()
    pick(s, c)
    assert handle(s, c, {"type": "bingo_open", "open": False}) is not None     # host only
    handle(s, host(), {"type": "bingo_open", "open": False})
    assert "closed" in handle(s, c, {"type": "bingo_mark", "index": 0, "marked": True})
    assert handle(s, host(), {"type": "bingo_open", "open": "no"}) is not None


def test_bingo_works_in_the_lobby_before_the_game_starts():
    s = new_state()
    assert s["phase"] == "lobby"
    c = bingo_phone()
    pick(s, c)
    tick(s, c, [0, 1, 2, 3])
    assert view_for(s, c)["my_board"]["lines"] == 1


def test_player_picks_a_team_from_the_dropdown_later(game):
    s, a, b, (ra, rb) = game
    c = bingo_phone()
    pick(s, c)
    assert handle(s, c, {"type": "bingo_team", "team_id": "t99"}) is not None
    assert handle(s, c, {"type": "bingo_team", "team_id": ra}) is None
    assert view_for(s, c)["my_board"]["team"] == ra
    assert handle(s, c, {"type": "bingo_team", "team_id": rb}) is None     # can change it
    assert handle(s, c, {"type": "bingo_team", "team_id": None}) is None   # or clear it


def test_bonus_waits_for_the_host_and_is_not_added_twice(game):
    s, a, b, (ra, rb) = game
    c = bingo_phone()
    pick(s, c)
    tick(s, c, [0, 1, 2, 3, 4, 8, 12])        # a row and a column
    handle(s, c, {"type": "bingo_team", "team_id": ra})
    assert s["teams"][ra]["bingo_bonus"] == 0                      # nothing until the end
    assert handle(s, c, {"type": "apply_bingo"}) is not None       # host only
    handle(s, host(), {"type": "apply_bingo"})
    handle(s, host(), {"type": "apply_bingo"})                     # pressed twice
    assert s["teams"][ra]["bingo_lines"] == 2 and s["teams"][ra]["bingo_bonus"] == 20
    assert s["teams"][rb]["bingo_bonus"] == 0
    s["teams"][ra]["score"] = 5
    # the bonus is separate from the score
    assert view_for(s, host())["teams"][ra]["score"] == 5


def test_bonus_follows_a_changed_team_and_removed_team(game):
    s, a, b, (ra, rb) = game
    c = bingo_phone()
    pick(s, c)
    tick(s, c, [0, 1, 2, 3])
    handle(s, c, {"type": "bingo_team", "team_id": ra})
    handle(s, host(), {"type": "apply_bingo"})
    handle(s, c, {"type": "bingo_team", "team_id": rb})
    handle(s, host(), {"type": "apply_bingo"})
    assert s["teams"][ra]["bingo_bonus"] == 0 and s["teams"][rb]["bingo_bonus"] == 10
    handle(s, host(), {"type": "remove_team", "team_id": rb})
    assert s["boards"]["b1"]["team"] is None


def test_host_can_free_a_board(game):
    s = game[0]
    c = bingo_phone()
    token = pick(s, c)["token"]
    handle(s, host(), {"type": "bingo_free", "board_id": "b1"})
    ghost = bingo_phone()
    assert handle(s, ghost, {"type": "hello", "role": "bingo", "board_id": "b1", "token": token})
    assert handle(s, bingo_phone(), {"type": "bingo_pick", "board_id": "b1"}) is None


def test_marks_and_tokens_never_reach_public_views(game):
    s, a, b, (ra, rb) = game
    c = bingo_phone()
    token = pick(s, c)["token"]
    tick(s, c, [0, 1, 2, 3])
    for conn in ({"id": 5, "role": "display", "team": None, "board": None}, a,
                 bingo_phone()):
        text = json.dumps(view_for(s, conn))
        assert "marks" not in text and token not in text and "phrase" not in text
        assert "my_board" not in text
        assert s["teams"][ra]["token"] not in text and "session" not in text
    host_text = json.dumps(view_for(s, host()))
    assert token not in host_text and '"token"' not in host_text
    mine = view_for(s, c)["my_board"]
    assert mine["marks"][:4] == [True] * 4 and len(mine["phrases"]) == 16
    assert "token" not in json.dumps(mine)


def test_every_preset_board_has_16_phrases():
    from boards import BOARDS
    assert len({b["id"] for b in BOARDS}) == len(BOARDS)
    assert all(len(b["phrases"]) == 16 for b in BOARDS)


def test_you_tells_a_phone_if_it_is_in_control(game):
    s, a, *_ = game
    assert view_for(s, a)["you"]["controller"] is True
    stale = {**a, "id": 12345}
    assert view_for(s, stale)["you"]["controller"] is False


# ---------- automatic reopening ----------
def open_round(game, seconds=5):
    s = game[0]
    s["auto_release_seconds"] = seconds
    s["buzzers_open"] = True
    return s


def test_buzz_starts_the_countdown(game):
    s = open_round(game, 5)
    handle(s, game[1], {"type": "buzz"})
    assert 4.5 < seconds_left(s) <= 5.0


def test_no_countdown_when_automatic_reopening_is_off(game):
    s = open_round(game, 0)
    handle(s, game[1], {"type": "buzz"})
    assert s["release_at"] is None and seconds_left(s) is None


def test_host_release_and_lock_cancel_the_countdown(game):
    for kind in ("lock", "release"):
        s = open_round(game, 5)
        s["buzzed"] = None
        handle(s, game[1], {"type": "buzz"})
        handle(s, host(), {"type": kind})
        assert s["release_at"] is None


def test_buzzers_reopen_only_when_time_is_up(game):
    s = open_round(game, 5)
    handle(s, game[1], {"type": "buzz"})
    due = s["release_at"]
    assert auto_release(s, due - 1) is False and s["buzzed"] == game[3][0]
    assert auto_release(s, due) is True
    assert s["buzzed"] is None and s["buzzers_open"] is True and s["release_at"] is None


def test_nothing_to_reopen_when_nobody_buzzed(game):
    assert auto_release(open_round(game, 5), 10**12) is False


def test_only_host_can_change_the_delay_and_it_is_validated(game):
    s, a, *_ = game
    assert handle(s, a, {"type": "auto_release", "seconds": 3}) is not None
    assert handle(s, host(), {"type": "auto_release", "seconds": 3}) is None
    for bad in (-1, 61, "x", None, float("nan")):
        assert handle(s, host(), {"type": "auto_release", "seconds": bad}) is not None
    assert s["auto_release_seconds"] == 3


# ---------- host page: reset and media ----------
def test_reset_needs_the_password_and_only_the_host(game):
    s, a, b, (ra, rb) = game
    assert handle(s, a, {"type": "reset", "password": "party"}) == "reset is host only"
    assert handle(s, host(), {"type": "reset"}) == "type the host password to reset"
    assert ra in s["teams"]                            # nothing changed


def test_reset_starts_a_fresh_game_in_the_same_dict(game):
    s, a, b, (ra, rb) = game
    c = bingo_phone()
    pick(s, c)
    tick(s, c, [0, 1, 2, 3])
    handle(s, host(), {"type": "points", "team": ra, "delta": 5})
    same = s
    assert handle(s, host(), {"type": "reset", "password": "party"}) is None
    assert s is same                                   # other code keeps its reference
    assert s["teams"] == {} and s["phase"] == "lobby"
    assert not any(board["claimed"] for board in s["boards"].values())
    # old phones lose control: their tokens point at nothing now
    assert handle(s, a, {"type": "buzz"}) is None and s["buzzed"] is None
    assert handle(s, c, {"type": "bingo_mark", "index": 0, "marked": True}) \
        == "you do not control a board"


def test_only_the_host_view_lists_media_files(game):
    s, a, b, ids = game
    files = view_for(s, host())["media_files"]
    assert {"name": "test.png", "type": "image", "src": "/media/test.png"} in files
    assert all(f["type"] in ("image", "sound") for f in files)
    assert "media_files" not in view_for(s, a)


def test_media_files_are_served_over_http():
    from fastapi.testclient import TestClient
    from main import app
    response = TestClient(app).get("/media/test.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


# ---------- look: quiz until the host reveals the secret bingo ----------
def test_theme_starts_as_quiz_and_everyone_sees_it(game):
    s, a, b, ids = game
    assert view_for(s, a)["theme"] == "quiz"
    assert view_for(s, {"id": 99, "role": "display", "team": None, "board": None})["theme"] == "quiz"


def test_only_the_host_can_reveal_and_the_value_is_checked(game):
    s, a, b, ids = game
    assert handle(s, a, {"type": "theme", "theme": "reveal"}) == "theme is host only"
    assert handle(s, host(), {"type": "theme", "theme": "disco"}) == "theme must be quiz or reveal"
    assert handle(s, host(), {"type": "theme", "theme": "reveal"}) is None
    assert view_for(s, a)["theme"] == "reveal"
    assert handle(s, host(), {"type": "theme", "theme": "quiz"}) is None   # can go back


def test_reset_goes_back_to_the_quiz_look(game):
    s, a, b, ids = game
    handle(s, host(), {"type": "theme", "theme": "reveal"})
    handle(s, host(), {"type": "reset", "password": "party"})
    assert s["theme"] == "quiz"


# ---------- shuffled cards ----------
def test_each_card_gets_a_shuffled_order_of_all_16_phrases():
    s = new_state()
    for board in s["boards"].values():
        assert sorted(board["order"]) == list(range(16))     # every phrase once


def test_the_player_sees_the_phrases_in_the_shuffled_order():
    from boards import BOARDS
    s = new_state()
    s["boards"]["b1"]["order"] = list(reversed(range(16)))   # a known shuffle
    c = bingo_phone()
    pick(s, c, "b1")
    shown = view_for(s, c)["my_board"]["phrases"]
    assert shown == list(reversed(BOARDS[0]["phrases"]))


def test_lines_count_on_the_squares_as_shown_not_the_original_order():
    s = new_state()
    s["boards"]["b1"]["order"] = list(reversed(range(16)))
    c = bingo_phone()
    pick(s, c, "b1")
    tick(s, c, [0, 1, 2, 3])                                 # the top row on screen
    assert view_for(s, c)["my_board"]["lines"] == 1


def test_the_order_never_reaches_other_roles(game):
    s, a, b, ids = game
    display = {"id": 77, "role": "display", "team": None, "board": None}
    for conn in (a, display, host(), bingo_phone()):
        assert '"order"' not in json.dumps(view_for(s, conn))
