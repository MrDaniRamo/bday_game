"""Browser test for the host page (/host), driving it like the host would.

Needs both servers running and a fresh backend/state.json (see CLAUDE.md).
Run from the project root: python e2e_host.py
"""
import os, time
from playwright.sync_api import sync_playwright

URL = "http://localhost:5173"
PHONE = {"viewport": {"width": 390, "height": 760}, "device_scale_factor": 1, "is_mobile": True, "has_touch": True}
LAPTOP = {"viewport": {"width": 1280, "height": 900}}

def ok(label, cond): print(("PASS " if cond else "FAIL ") + label); assert cond
def wait_text(pg, text, timeout=8000):
    pg.wait_for_function(f"document.body.innerText.includes({text!r})", timeout=timeout)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"))
    H = b.new_context(**LAPTOP).new_page()
    H.on("dialog", lambda d: d.accept())                 # say yes to every "are you sure?"
    D = b.new_context(**LAPTOP).new_page(); D.goto(URL + "/"); D.wait_for_selector(".status")
    D.click("text=Click to enable sound")
    T = b.new_context(**PHONE).new_page()
    G = b.new_context(**PHONE).new_page()

    # --- login ---
    H.goto(URL + "/host"); H.fill("#host-password", "wrong"); H.click("text=Log in")
    H.wait_for_selector("text=Wrong password"); ok("wrong password goes back to login", True)
    H.fill("#host-password", "party"); H.click("text=Log in"); H.wait_for_selector("text=Host controls")
    ok("right password shows the panel", H.locator(".pill").inner_text() == "Lobby")
    H.reload(); H.wait_for_selector("text=Host controls"); ok("refresh keeps the host logged in", True)

    # --- start needs a team ---
    H.click("text=Start game"); H.wait_for_selector("text=no team has joined yet")
    ok("cannot start with no teams", True)

    # --- a captain and a bingo player join ---
    T.goto(URL + "/team"); T.fill("#team-name", "Reds"); T.click(".swatch >> nth=0"); T.click("button[type=submit]")
    T.wait_for_selector("text=Waiting for the host")
    wait_text(H, "captain connected"); ok("host sees the team", "Reds" in H.inner_text(".teams"))
    G.goto(URL + "/bingo"); G.click("text=Max"); G.wait_for_selector(".card")
    for i in (0, 1, 2, 3): G.click(f".square >> nth={i}")
    G.wait_for_function("document.querySelector('.lines').innerText==='Lines: 1'")
    G.select_option("#bingo-team", label="Reds")
    wait_text(H, "Reds +10"); ok("bingo panel previews the bonus", "4/16 ticked" in H.inner_text(".cards"))

    # --- start, buzz, points ---
    H.click("text=Start game"); H.wait_for_selector(".pill.playing"); T.wait_for_selector(".buzzer")
    ok("start game moves the phone to the buzzer", True)
    H.fill("#delay", "2"); H.click("text=Set"); wait_text(H, "now 2s"); ok("reopen delay set to 2s", True)
    H.click("text=Open buzzers"); T.wait_for_selector(".buzzer.open"); T.tap(".buzzer")
    wait_text(H, "Reds buzzed first"); ok("host sees who buzzed", True)
    T.wait_for_selector(".buzzer.won"); ok("the phone shows it won", "You buzzed" in T.inner_text(".buzzer"))
    T.wait_for_selector(".buzzer.open", timeout=6000); ok("buzzers reopen by themselves", True)
    H.click("text=Lock"); T.wait_for_selector(".buzzer.locked"); ok("lock closes the buzzers", True)
    H.click(".teams button:text-is('+10')"); H.click(".teams button:text-is('-1')")
    D.wait_for_function("document.querySelector('.board li .score').innerText.startsWith('9')")
    ok("points show on the TV", T.inner_text(".score") == "9")

    # --- media ---
    H.click(".files li:has-text('test.png') button"); D.wait_for_selector(".media img")
    D.wait_for_function("document.querySelector('.media img').naturalWidth > 0")
    ok("image from backend/media loads on the TV", True)
    H.screenshot(path="v_host_laptop.png", full_page=True); D.screenshot(path="v_display_media.png")
    H.click(".files li:has-text('test.wav') button"); wait_text(H, "On the TV: sound /media/test.wav")
    ok("sound sent (and the image is gone)", D.locator(".media img").count() == 0)
    H.click("text=Clear the screen"); wait_text(H, "On the TV: nothing"); ok("clear the screen", True)

    # --- bingo ---
    H.click("text=Close ticking"); G.wait_for_selector("text=closed bingo"); ok("host closes bingo ticking", True)
    H.click("text=Apply bingo bonus"); wait_text(H, "Apply bingo bonus again")
    D.wait_for_function("document.querySelector('.board li .score').innerText.startsWith('19')")
    ok("bonus applied: 9 + 10 = 19 on the TV", "+10 bingo" in D.inner_text(".board"))
    H.click("text=Apply bingo bonus again"); time.sleep(0.5)
    ok("applying twice does not add twice", D.inner_text(".board li .score").startswith("19"))

    # --- free a team ---
    H.click(".teams button:text-is('Free')"); T.wait_for_selector("text=Take over")
    ok("free team sends the captain to the take-over screen", True)
    T.click("text=Reds"); T.wait_for_selector(".buzzer"); ok("captain takes the team back", True)

    # --- reset ---
    H.fill("#reset-password", "nope"); H.click("text=Reset game")
    H.wait_for_selector("text=type the host password to reset"); ok("reset refuses a wrong password", True)
    H.fill("#reset-password", "party"); H.click("text=Reset game"); H.wait_for_selector(".pill.lobby")
    T.wait_for_selector("text=Start your team"); G.wait_for_selector("text=Pick your card")
    D.wait_for_selector("text=Waiting for teams")
    ok("reset sends phones back to the start and clears the TV", "No teams yet" in H.inner_text(".panel >> nth=1"))

    # --- phone-sized host page ---
    HP = b.new_context(**PHONE).new_page(); HP.goto(URL + "/host")
    HP.fill("#host-password", "party"); HP.click("text=Log in"); HP.wait_for_selector("text=Host controls")
    wide = HP.evaluate("document.documentElement.scrollWidth")
    HP.screenshot(path="v_host_phone.png", full_page=True)
    ok(f"host page fits a phone (width {wide})", wide <= 390)
    b.close()
print("ALL PASS")
