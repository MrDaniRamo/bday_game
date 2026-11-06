import json, os, time
from playwright.sync_api import sync_playwright
from websockets.sync.client import connect
URL = "http://localhost:5173"
PHONE = {"viewport": {"width": 390, "height": 760}, "device_scale_factor": 1, "is_mobile": True, "has_touch": True}
class Host:
    def __init__(s):
        s.ws = connect("ws://localhost:8000/ws"); s.send({"type":"hello","role":"host","password":"party"}); s.last=None; s.drain()
    def send(s,o): s.ws.send(json.dumps(o))
    def drain(s,t=0.3):
        try:
            while True:
                m=json.loads(s.ws.recv(timeout=t))
                if m["type"]=="state": s.last=m["state"]
        except TimeoutError: pass
    def cmd(s,o): s.send(o); s.drain()
def ok(l,c): print(("PASS " if c else "FAIL ")+l); assert c
h = Host()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM_PATH"))
    A = b.new_context(**PHONE).new_page(); B = b.new_context(**PHONE).new_page()
    A.goto(URL+"/bingo"); A.wait_for_selector("text=Pick your card")
    A.click("text=Board 1"); A.wait_for_selector(".card")
    ok("A has board 1 in the lobby, no teams yet", "No teams yet" in A.inner_text("select"))
    B.goto(URL+"/bingo"); B.wait_for_selector("text=Pick your card")
    ok("B sees board 1 taken", B.get_by_role("button", name="Board 1 (taken)").is_disabled())
    B.click("text=Board 2"); B.wait_for_selector(".card")
    for i in (0,1,2,3,4,8,12): A.click(f".square >> nth={i}")
    A.wait_for_function("document.querySelector('.lines').innerText==='Lines: 2'"); ok("2 lines counted by server", True)
    A.screenshot(path="v_bingo_card.png")
    A.reload(); A.wait_for_selector(".card"); ok("reload keeps card and marks", A.locator(".square.on").count()==7)
    cap = b.new_context(**PHONE).new_page(); cap.goto(URL+"/team"); cap.wait_for_selector("#team-name")
    cap.fill("#team-name","Reds"); cap.click(".swatch >> nth=0"); cap.click("button[type=submit]"); cap.wait_for_selector("text=Waiting for the host")
    A.wait_for_function("document.querySelector('#bingo-team').options.length===2"); ok("team appears in the dropdown", True)
    A.select_option("#bingo-team", label="Reds"); A.wait_for_selector("text=count for this team")
    h.drain(1)
    ok("host sees board 1 -> Reds with 2 lines", h.last["boards"]["b1"]["lines"]==2 and h.last["teams"][h.last["boards"]["b1"]["team"]]["name"]=="Reds")
    D = b.new_context(viewport={"width":1280,"height":720}).new_page(); D.goto(URL+"/"); D.wait_for_selector(".status")
    ok("display page never mentions bingo", "ingo" not in D.inner_text("body"))
    h.cmd({"type":"bingo_open","open":False}); A.wait_for_selector("text=closed bingo")
    ok("squares disabled when closed", A.locator(".square").first.is_disabled())
    h.cmd({"type":"bingo_open","open":True}); A.wait_for_function("!document.querySelector('.square').disabled")
    A2 = A.context.new_page(); A2.goto(URL+"/bingo"); A2.wait_for_selector(".card")
    A.wait_for_selector("text=Another phone is using"); ok("old tab loses card", A.locator(".square:not([disabled])").count()==0)
    A.click("text=Take control back"); A2.wait_for_selector("text=Another phone"); ok("take back works", True); A2.close()
    h.cmd({"type":"phase","phase":"playing"})
    h.cmd({"type":"apply_bingo"}); h.cmd({"type":"apply_bingo"})
    tid=[i for i,t in h.last["teams"].items() if t["name"]=="Reds"][0]
    ok("bonus applied once: 2 lines = 20", h.last["teams"][tid]["bingo_bonus"]==20)
    D.wait_for_function("document.querySelector('.board li .score').innerText.startsWith('20')")
    ok("display total shows 20 with the bonus", "+20 bingo" in D.inner_text(".board li .score"))
    h.cmd({"type":"bingo_free","board_id":"b2"}); B.wait_for_selector("text=Pick your card"); ok("freed board sends B back", True)
    B.click("text=Board 2"); B.wait_for_selector(".card"); ok("B can pick it again", True)
    b.close()
print("ALL PASS")
