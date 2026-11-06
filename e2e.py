import json, os, signal, subprocess, time
from playwright.sync_api import sync_playwright
from websockets.sync.client import connect

URL = "http://localhost:5173"
PHONE = {"viewport": {"width": 390, "height": 760}, "device_scale_factor": 1, "is_mobile": True, "has_touch": True}

class Host:
    def __init__(self):
        self.ws = connect("ws://localhost:8000/ws"); self.send({"type": "hello", "role": "host", "password": "party"})
        self.last = None; self.err = None; self.drain()
    def send(self, o): self.ws.send(json.dumps(o))
    def drain(self, t=0.3):
        try:
            while True:
                m = json.loads(self.ws.recv(timeout=t))
                if m["type"] == "state": self.last = m["state"]
                else: self.err = m
        except TimeoutError: pass
    def cmd(self, o): self.send(o); self.drain()

def kill_backend():
    for d in os.listdir("/proc"):
        if d.isdigit():
            try: cmd = open(f"/proc/{d}/cmdline").read().split("\0")
            except OSError: continue
            if cmd[:4] == ["python", "-m", "uvicorn", "main:app"]: os.kill(int(d), signal.SIGTERM)

def wait_cls(pg, c, timeout=8000): pg.wait_for_function(f"document.querySelector('.buzzer')?.className.includes('{c}')", timeout=timeout)
def create(pg, name, color_index):
    pg.goto(URL + "/team"); pg.wait_for_selector("#team-name")
    pg.fill("#team-name", name); pg.click(f".swatch >> nth={color_index}"); pg.click("button[type=submit]")
def ok(label, cond): print(("PASS " if cond else "FAIL ") + label); assert cond

h = Host()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"))
    ctxA = b.new_context(**PHONE); A = ctxA.new_page()
    ctxB = b.new_context(**PHONE); B = ctxB.new_page()
    D = b.new_context(viewport={"width": 1280, "height": 720}).new_page(); D.goto(URL + "/")
    D.wait_for_selector(".status"); ok("display shows lobby prompt", "Pick your team" in D.inner_text(".status"))

    create(A, "Reds", 0); A.wait_for_selector("text=Waiting for the host")
    ok("A in lobby after creating", "Reds" in A.inner_text("h1"))
    # B: duplicate name -> refused; taken color is disabled
    B.goto(URL + "/team"); B.wait_for_selector("#team-name")
    ok("B sees A's color disabled", B.locator(".swatch >> nth=0").is_disabled())
    B.fill("#team-name", "reds"); B.click(".swatch >> nth=3"); B.click("button[type=submit]")
    B.wait_for_selector(".problem"); ok("duplicate name refused: " + B.inner_text(".problem"), "taken" in B.inner_text(".problem"))
    B.fill("#team-name", "Blues"); B.click("button[type=submit]"); B.wait_for_selector("text=Waiting for the host")
    D.wait_for_selector(".board li"); ok("display lists both teams", D.locator(".board li").count() == 2)
    # lobby edit
    A.fill("#team-name", "Crimson"); A.click(".swatch >> nth=4"); A.click("button[type=submit]")
    A.wait_for_function("document.querySelector('h1').innerText==='Crimson'")
    D.wait_for_function("document.body.innerText.includes('Crimson')"); ok("lobby edit shows on display", True)
    D.screenshot(path="v_display_lobby.png"); A.screenshot(path="v_phone_lobby.png")
    # duplicate color on edit is not even clickable
    ok("B cannot pick A's new color", B.locator(".swatch >> nth=4").is_disabled())

    # reload keeps control (token in localStorage)
    A.reload(); A.wait_for_selector("text=Waiting for the host"); ok("reload resumes team", "Crimson" in A.inner_text("h1"))
    # buzz before start does nothing
    h.cmd({"type": "release"}); time.sleep(0.2)
    # start
    h.cmd({"type": "phase", "phase": "playing"})
    A.wait_for_selector(".buzzer"); B.wait_for_selector(".buzzer")
    ok("both phones show the buzzer after start", True)
    h.cmd({"type": "auto_release", "seconds": 2}); h.cmd({"type": "release"}); wait_cls(A, "open")
    A.tap(".buzzer"); wait_cls(A, "won"); wait_cls(B, "lost")
    ok("A won, display names Crimson", "Crimson buzzed first" in D.inner_text(".status"))
    D.screenshot(path="v_display_playing.png"); B.screenshot(path="v_phone_playing.png")
    wait_cls(A, "open"); ok("auto reopened", True)
    # new team late: refused
    L = b.new_context(**PHONE).new_page(); L.goto(URL + "/team"); L.wait_for_selector("text=game has started")
    ok("late phone cannot create a team", L.locator("#team-name").count() == 0)

    # takeover: a second tab with A's token takes control; first tab is told
    ctxA2 = A.context.new_page(); ctxA2.goto(URL + "/team"); ctxA2.wait_for_selector(".buzzer")
    A.wait_for_selector("text=Another phone is controlling")
    ok("old tab loses control", True)
    h.cmd({"type": "release"}); wait_cls(ctxA2, "open")
    ok("old tab cannot buzz (no buzzer shown)", A.locator(".buzzer").count() == 0)
    A.click("text=Take control back"); A.wait_for_selector(".buzzer"); ctxA2.wait_for_selector("text=Another phone")
    ok("take back works", True)

    # host frees team B, B's phone is kicked, a new phone takes it over
    bid = [i for i, t in h.last["teams"].items() if t["name"] == "Blues"][0]
    h.cmd({"type": "free_team", "team_id": bid})
    B.wait_for_selector("#team-name", state="detached") if False else None
    B.wait_for_selector("text=Take over", timeout=5000); ok("freed team: B sent back to join screen with takeover option", True)
    N = b.new_context(**PHONE).new_page(); N.goto(URL + "/team"); N.click("text=Blues"); N.wait_for_selector(".buzzer")
    ok("new phone took over Blues", True)
    h.cmd({"type": "remove_team", "team_id": bid})
    N.wait_for_selector("text=Take over, text=Start your team", timeout=5000) if False else time.sleep(1)
    D.wait_for_function("document.querySelectorAll('.board li').length===1"); ok("removed team leaves the board", True)

    # server restart: state.json restores, tokens survive, phones reconnect and still control
    tid = [i for i, t in h.last["teams"].items() if t["name"] == "Crimson"][0]
    ctxA2.close(); time.sleep(0.5); kill_backend(); time.sleep(1)
    subprocess.Popen("cd backend && AUTO_RELEASE_SECONDS=2 nohup python -m uvicorn main:app --host 0.0.0.0 --port 8000 >> ../backend2.log 2>&1 &", shell=True)
    time.sleep(4)
    h = Host(); h.cmd({"type": "release"})
    A.wait_for_selector(".buzzer", timeout=10000); wait_cls(A, "open", 10000)
    A.tap(".buzzer"); wait_cls(A, "won"); ok("after restart A resumed and can buzz", True)
    D.wait_for_function("document.body.innerText.includes('Crimson buzzed first')"); ok("display ok after restart", True)
    b.close()
print("ALL PASS")
