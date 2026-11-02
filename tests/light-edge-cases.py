"""Test cac ca bien cua scripts/light.py. Khong dung den board va ~/.claude-light that.

Chay: python3 tests/light-edge-cases.py   (exit 1 neu co ca FAIL)
"""
import contextlib, importlib.util, io, json, os, subprocess, sys, tempfile

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code", "scripts", "light.py")
spec = importlib.util.spec_from_file_location("light", SRC)
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
S, B, W, K = L.store, L.board, L.watch, L.reconnect  # file/cau hinh, cong serial, theo doi trang thai, giu ket noi
K.spawn = lambda: None  # khong bat tien trinh `keep` that tu test

REAL_SEND, REAL_ATTACH = B.send, B.wsl_attach
SENT = []
B.send = lambda line, retries=4: SENT.append(line) or True
B.wsl_attach = lambda *a: False
FILES = {"CONFIG": "config.json", "MAP": "map.json", "PENDING": "pending.json",
         "MUTED": "muted.json", "LOG": "log.txt", "LOCK": "lock",
         "WATCH": "watch.json", "ATTACH": "attach.json", "KEEPER": "keeper.lock"}

def fresh(num_leds=1, auto=True):
    S.DIR = tempfile.mkdtemp()
    for name, f in FILES.items():
        setattr(S, name, os.path.join(S.DIR, f))
    S.save(S.CONFIG, {"port": None, "num_leds": num_leds, "auto_assign": auto, "debug": False})
    os.environ["CLAUDE_CONFIG_DIR"] = S.DIR  # file trang thai phien <config>/sessions/*.json: khong doc cua may that
    SENT.clear()

def hook(event, sid, cwd, **extra):
    sys.stdin = io.StringIO(json.dumps({"hook_event_name": event, "session_id": sid, "cwd": cwd, **extra}))
    L.cmd_hook()

def cmd(fn, cwd, sid, *args):
    """Chay slash command tu thu muc cwd; sid=None gia lap thieu CLAUDE_CODE_SESSION_ID."""
    real_getcwd, env = os.getcwd, os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
    if sid:
        os.environ["CLAUDE_CODE_SESSION_ID"] = sid
    os.getcwd = lambda: cwd
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            fn(*args)
    finally:
        os.getcwd = real_getcwd
        os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
        if env:
            os.environ["CLAUDE_CODE_SESSION_ID"] = env
    return out.getvalue().strip()

def m(): return S.load(S.MAP, {})
def p(): return S.load(S.PENDING, {})
def led(sid): return m().get(sid, {}).get("led")

results = []
def check(name, ok, detail):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "\n     " + detail))

X, XC = "/proj", "/proj/code"

for sid, mode in ((None, "doan theo cwd"), ("A", "co session_id")):
    fresh()
    hook("SessionStart", "A", X)
    hook("PostToolUse", "A", XC)          # Bash `cd code`: hook bao cwd moi
    SENT.clear()
    out = cmd(L.cmd_disconnect, XC, sid)
    check("disconnect sau khi cd (%s)" % mode, "A" not in m() and SENT == ["0:off"],
          "in %r, map=%s, sent=%s" % (out, m(), SENT))

    fresh(num_leds=2)
    hook("SessionStart", "A", X)
    hook("PostToolUse", "A", XC)
    SENT.clear()
    cmd(L.cmd_connect, XC, sid, 2)
    check("connect sau khi cd (%s)" % mode, led("A") == 1 and not p() and SENT == ["0:off\n1:ready"],
          "map=%s pending=%s sent=%s" % (m(), p(), SENT))

fresh(num_leds=2)
hook("SessionStart", "A", X)
cmd(L.cmd_disconnect, X, "A")
hook("PostToolUse", "A", XC)              # cd sau khi disconnect: khong duoc tu gan lai
check("disconnect roi cd", "A" not in m(), "map=%s" % m())

fresh(num_leds=2)
hook("SessionStart", "A", X)
hook("SessionStart", "B", X)
cmd(L.cmd_connect, X, "B", 1)
check("2 session cung cwd, B connect den 1", led("B") == 0 and led("A") != 0, "map=%s" % m())

fresh(num_leds=2)
hook("SessionStart", "A", X)
hook("SessionStart", "B", X)
cmd(L.cmd_disconnect, X, "B")
check("2 session cung cwd, B disconnect", led("A") == 0 and "B" not in m(), "map=%s" % m())

fresh(num_leds=3)
hook("SessionStart", "B", "/other")       # B -> 0
hook("SessionStart", "A", X)              # A -> 1
cmd(L.cmd_connect, X, "A", 3)             # A chuyen sang den 3 (chi so 2)
hook("SessionEnd", "A", X, reason="clear")
hook("SessionStart", "A2", X, source="clear")
check("/clear giu den da chon", led("A2") == 2 and not p(), "map=%s pending=%s" % (m(), p()))

fresh(num_leds=1, auto=False)
cmd(L.cmd_connect, X, None, 1)
hook("SessionStart", "A", X)
hook("SessionEnd", "A", X, reason="clear")
hook("SessionStart", "A2", X, source="clear")
check("/clear khi auto_assign tat", led("A2") == 0, "map=%s" % m())

fresh(num_leds=1)
hook("SessionStart", "A", X)
hook("SessionEnd", "A", X, reason="logout")
check("thoat binh thuong khong de lai pending", not m() and not p(), "map=%s pending=%s" % (m(), p()))

fresh(num_leds=1)
hook("SessionStart", "A", X)
hook("PostToolUse", "A", XC)
hook("SessionEnd", "A", XC, reason="clear")   # pending ghi theo XC
hook("SessionStart", "A2", X, source="clear")  # A2 o X: pending XC bi treo
SENT.clear()
hook("SessionStart", "B", XC)             # session moi tu gan: khong duoc gianh den cua A2
check("session moi khong gianh den dang bi chiem",
      led("A2") == 0 and "B" not in m() and SENT == ["bri:5\nfx:scan\n0:ready"],
      "map=%s pending=%s sent=%s" % (m(), p(), SENT))

fresh(num_leds=1)
hook("SessionStart", "A", X)
cmd(L.cmd_connect, "/y", "B", 1)          # B gianh den 1 (chi so 0), A bi day ra
SENT.clear()
hook("SessionEnd", "A", X)
check("session bi day ra ket thuc", SENT == [] and led("B") == 0, "sent=%s map=%s" % (SENT, m()))

# Nguoi dung dem den tu 1 den 8; map.json va lenh xuong board van dem tu 0
fresh(num_leds=8)
outs = [cmd(L.cmd_connect, X, "A", v) for v in ("0", "9", "8")]
sent = list(SENT)
outs.append(cmd(L.cmd_disconnect, X, "A"))
check("usb-connect dem tu 1: 0 va 9 bi tu choi, 8 la den cuoi (chi so 7)",
      outs == ["Số đèn phải từ 1 đến 8"] * 2 + ["Đã gán đèn 8 cho session ở /proj", "Đã bỏ gán đèn 8 cho session ở /proj"]
      and sent == ["7:ready"] and SENT[-1] == "7:off",
      "in %r, sent=%s" % (outs, SENT))

# /usb-blink: board nhay den cua session nay, in so den dem tu 1; chua gan den thi bao va khong gui gi
fresh(num_leds=3)
hook("SessionStart", "B", "/y"); hook("SessionStart", "A", X); SENT.clear()
outs = [cmd(L.display.cmd_blink, X, "A"), cmd(L.display.cmd_blink, "/z", "C")]
check("usb-blink nhay dung den cua session, chua gan den thi bao",
      outs == ["Đèn 2 đang nháy xanh lá 3 lần", "Session ở /z chưa gắn đèn nào"] and SENT == ["flash:1"],
      "in %r, sent=%s" % (outs, SENT))

fresh()
out = cmd(L.cmd_disconnect, X, "A")
check("disconnect khi chua gan den", "chưa gán đèn nào" in out, "in %r" % out)

fresh()
hook("SessionStart", "A", X); SENT.clear()
hook("Notification", "A", X, notification_type="idle_prompt")
hook("PreToolUse", "A", X, tool_name="AskUserQuestion")
check("idle_prompt -> ready, AskUserQuestion -> wait", SENT == ["0:ready", "0:wait"], "sent=%s" % SENT)

# Dang hoi nguoi dung (file trang thai phien ghi "waiting") ma subagent chay nen van goi tool: hook cua no cung
# session_id, kem agent_id. Den phai giu do; Stop cua luot chinh luc subagent dang xin quyen cung vay
fresh()
hook("SessionStart", "A", X)
os.makedirs(os.path.join(S.DIR, "sessions"))
STATUS_A = os.path.join(S.DIR, "sessions", "1.json")
def status_a(status, why=None):
    S.save(STATUS_A, {"sessionId": "A", "pid": os.getpid(), "status": status, "waitingFor": why})
status_a("waiting", "input needed"); SENT.clear()
hook("PreToolUse", "A", X, tool_name="Bash", agent_id="sub1")
hook("PostToolUse", "A", X, tool_name="Bash", agent_id="sub1")
hook("Stop", "A", X)
status_a("waiting", "dialog open")        # nguoi dung tu mo /model: khong phai Claude dang cho
hook("PreToolUse", "A", X, tool_name="Bash", agent_id="sub1")
status_a("busy")                          # da tra loi: hook ke tiep ve cam
hook("PostToolUse", "A", X, tool_name="AskUserQuestion")
check("dang hoi nguoi dung: hook cua subagent va Stop khong doi den do thanh cam/xanh",
      SENT == ["0:wait", "0:wait", "0:wait", "0:busy", "0:busy"], "sent=%s" % SENT)

# Esc/Ctrl+C luc tool dang chay: Stop khong chay, chi co PostToolUseFailure kem is_interrupt
fresh()
hook("SessionStart", "A", X); SENT.clear()
hook("PostToolUseFailure", "A", X, tool_name="Bash", error="loi", is_interrupt=False)
hook("PostToolUseFailure", "A", X, tool_name="Bash", error="interrupted", is_interrupt=True)
check("tool loi -> busy, bi ngat -> ready", SENT == ["0:busy", "0:ready"], "sent=%s" % SENT)

# Esc/Ctrl+C (ke ca ngay sau Enter) va duyet quyen xong: khong hook nao chay. Claude Code ghi trang thai
# vao <config>/sessions/<pid>.json; tien trinh nen doi den theo moi lan trang thai doi sau luc gui prompt
fresh()
hook("SessionStart", "A", X); SENT.clear()
spawned, real_popen = [], subprocess.Popen
subprocess.Popen = lambda argv, **kw: spawned.append(argv)
try:
    hook("UserPromptSubmit", "A", X)
finally:
    subprocess.Popen = real_popen
argv = spawned[0][2:] if spawned else []
check("UserPromptSubmit chay tien trinh theo doi trang thai",
      argv[:3] == ["watch", "A", S.load(S.WATCH, {}).get("A")] and len(argv) == 4 and argv[3].isdigit(),
      "spawned=%s" % spawned)

dead = subprocess.Popen([sys.executable, "-c", "pass"]); dead.wait()
DEAD_PID = dead.pid  # claude bi tat ngang: file trang thai con, tien trinh thi khong

def run_watch(steps, token="t1", pid=None):
    """steps: trang thai Claude Code ghi lan luot, moi lan sleep mot buoc; het buoc thi co luot moi."""
    fresh(); hook("SessionStart", "A", X); SENT.clear()
    os.environ["CLAUDE_CONFIG_DIR"] = S.DIR
    os.makedirs(os.path.join(S.DIR, "sessions"))
    S.save(os.path.join(S.DIR, "sessions", "999.json"), {"sessionId": "B", "status": "idle", "statusUpdatedAt": 9e12})
    S.save(S.WATCH, {"A": token})
    queue = list(steps)
    def tick(s):
        if not queue:
            S.save(S.WATCH, {"A": "luot-moi"}); return
        status, at, why = (queue.pop(0) + (None,))[:3]
        S.save(os.path.join(S.DIR, "sessions", "123.json"),
               {"sessionId": "A", "pid": pid, "status": status, "waitingFor": why, "statusUpdatedAt": at, "updatedAt": at})
    real_sleep, L.time.sleep = L.time.sleep, tick
    try:
        W.cmd_watch("A", "t1", "1000")
    finally:
        L.time.sleep = real_sleep
        os.environ.pop("CLAUDE_CONFIG_DIR")
    return list(SENT)
# Rut USB cam lai: board quen het mau, den cua session dang ranh toi nhu den trong du van bi giu. Mo session
# thi gui lai mau tung den theo file trang thai phien; session chi con file cua tien trinh da chet thi tra den
fresh(num_leds=4)
S.save(S.MAP, {s: {"led": n, "cwd": "/" + s} for n, s in enumerate("BCDE")})
os.makedirs(os.path.join(S.DIR, "sessions"))
for f, rec in (("1", {"sessionId": "B", "pid": os.getpid(), "status": "idle"}),
               ("2", {"sessionId": "C", "pid": os.getpid(), "status": "waiting", "waitingFor": "permission prompt"}),
               ("3", {"sessionId": "D", "pid": DEAD_PID, "status": "busy"})):  # E chua co file: coi la san sang
    S.save(os.path.join(S.DIR, "sessions", f + ".json"), rec)
hook("SessionStart", "A", X)
sent_start = list(SENT); SENT.clear()
B.wsl_attach = lambda *a: True            # hook thuong vua tu gan lai board vao WSL
hook("PreToolUse", "C", "/C")
B.wsl_attach = lambda *a: False
check("cam lai board: gui lai mau tung den, session da chet tra den cho session moi",
      "D" not in m() and led("A") == 2 and sent_start == ["bri:5\nfx:scan\n0:ready\n1:wait\n2:off\n3:ready\n2:ready"]
      and SENT == ["bri:5\nfx:scan\n0:ready\n2:ready\n3:ready\n1:wait"],  # C dang xin quyen: giu do
      "map=%s, mo session gui %s, gan lai gui %s" % (m(), sent_start, SENT))

# /usb-sort: den dang gan 1 3 5 6 8 -> 1 2 3 4 5, giu thu tu. D chi con file cua tien trinh da chet: bo gan truoc,
# khong chiem cho. Den pending (gan tay luc chua co session) cung duoc don, khong bi session khac de len
fresh(num_leds=8)
S.save(S.MAP, {"A": {"led": 0, "cwd": "/A"}, "B": {"led": 2, "cwd": "/B"}, "C": {"led": 4, "cwd": "/C"},
               "D": {"led": 5, "cwd": "/D"}, "E": {"led": 7, "cwd": "/E"}})
S.save(S.PENDING, {"/p": 6})
os.makedirs(os.path.join(S.DIR, "sessions"))
S.save(os.path.join(S.DIR, "sessions", "1.json"), {"sessionId": "B", "pid": os.getpid(), "status": "waiting",
                                                   "waitingFor": "permission prompt"})
S.save(os.path.join(S.DIR, "sessions", "2.json"), {"sessionId": "D", "pid": DEAD_PID, "status": "busy"})
out = cmd(L.display.cmd_sort, "/C", "C")
check("usb-sort don den ve lien nhau, giu thu tu, bo session chet",
      {k: v["led"] for k, v in m().items()} == {"A": 0, "B": 1, "C": 2, "E": 4} and p() == {"/p": 3}
      and out == "Đã dồn đèn 3 → 2, 5 → 3, 7 → 4, 8 → 5; session này ở đèn 3"
      and SENT == ["bri:5\nfx:scan\n0:ready\n1:wait\n2:ready\n3:off\n4:ready\n5:off\n6:off\n7:off"],
      "map=%s pending=%s in %r sent=%s" % (m(), p(), out, SENT))
SENT.clear(); out = cmd(L.display.cmd_sort, "/z", None)
check("usb-sort lan hai: da lien nhau thi khong doi", out == "Các đèn đang gán đã liền nhau từ đèn 1, không phải đổi"
      and led("E") == 4, "in %r map=%s" % (out, m()))

# /usb-swap a b: doi hai den cho nhau, ca den pending; mot ben trong thi la chuyen sang; so sai thi in cach dung
fresh(num_leds=5)
S.save(S.MAP, {"A": {"led": 0, "cwd": "/A"}, "B": {"led": 2, "cwd": "/B"}})
S.save(S.PENDING, {"/p": 3})
outs = [cmd(L.display.cmd_swap, "/A", "A", "1 3")]
swapped = ({k: v["led"] for k, v in m().items()}, list(SENT)); SENT.clear()
outs += [cmd(L.display.cmd_swap, "/z", None, "4,2"), cmd(L.display.cmd_swap, "/z", None, "4 5")]
sent_ok = len(SENT); SENT.clear()
outs += [cmd(L.display.cmd_swap, "/z", None, t) for t in ("2 2", "1 6", "3", "")]
usage = "Cách dùng: /session-light:usb-swap <đèn> <đèn>, hai số khác nhau từ 1 đến 5"
check("usb-swap doi hai den, ca den pending, so sai thi in cach dung",
      swapped == ({"A": 2, "B": 0}, ["bri:5\nfx:scan\n0:ready\n1:off\n2:ready\n3:off\n4:off"]) and p() == {"/p": 1}
      and outs == ["Đã đổi đèn 1 ↔ 3; session này ở đèn 3", "Đã đổi đèn 4 ↔ 2",
                   "Đèn 4 và 5 đều chưa gán, không có gì để đổi"] + [usage] * 4 and sent_ok == 2 and not SENT,
      "lan dau %s, pending=%s, in %r, sent=%s" % (swapped, p(), outs, SENT))

# Tat het terminal (khong co SessionEnd) roi `claude -c`: lay den trong nho nhat tu den 1, khong giu den cu
fresh(num_leds=3)
S.save(S.MAP, {"B": {"led": 0, "cwd": "/y"}, "A": {"led": 1, "cwd": X}})
os.makedirs(os.path.join(S.DIR, "sessions"))
S.save(os.path.join(S.DIR, "sessions", "1.json"), {"sessionId": "B", "pid": DEAD_PID, "status": "idle"})
hook("SessionStart", "A", X, source="resume")
resumed = (led("A"), "B" in m(), list(SENT))
# `claude -c` o terminal thu hai khi tien trinh cu cua session van chay: giu den, khong giat cua chinh no
S.save(S.MAP, {"B": {"led": 0, "cwd": "/y"}, "A": {"led": 1, "cwd": X}})
S.save(os.path.join(S.DIR, "sessions", "2.json"), {"sessionId": "A", "pid": os.getpid(), "status": "busy"})
SENT.clear(); hook("SessionStart", "A", X, source="resume")
check("claude -c lay den trong nho nhat, khong giu den cu; tien trinh cu con chay thi giu",
      resumed == (0, False, ["bri:5\nfx:scan\n0:off\n1:off\n2:off\n0:ready"]) and led("A") == 1,
      "lan dau %s, terminal thu hai: map=%s" % (resumed, m()))

# Rut cam USB luc moi session dang ranh: khong hook nao chay. Tien trinh `keep` thay cong co lai thi gui lai ca
# thanh, het session con song thi thoat; da co tien trinh keep khac giu khoa thi thoat ngay
fresh(num_leds=2)
S.save(S.MAP, {"B": {"led": 0, "cwd": "/y"}})
os.makedirs(os.path.join(S.DIR, "sessions"))
B_FILE = os.path.join(S.DIR, "sessions", "1.json")
S.save(B_FILE, {"sessionId": "B", "pid": os.getpid(), "status": "idle"})
script = [False, False, True]
def fake_attach(*a):
    if script:
        return script.pop(0)
    S.save(B_FILE, {"sessionId": "B", "pid": DEAD_PID, "status": "idle"})  # het kich ban: B bi tat
    return False
B.wsl_attach, real_sleep, L.time.sleep = fake_attach, L.time.sleep, lambda s: None
try:
    import fcntl
    with open(S.KEEPER, "w") as other:
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
        K.cmd_keep(check_every=0)  # khoa dang bi giu: thoat ngay, khong dung den kich ban
    untouched = len(script) == 3
    K.cmd_keep(check_every=0)
finally:
    B.wsl_attach, L.time.sleep = (lambda *a: False), real_sleep
os.remove(B_FILE)  # Claude Code khong ghi file trang thai nao: con session trong map thi keep chay tiep
check("tien trinh keep: cong co lai thi gui lai ca thanh, het session song thi thoat, chi mot tien trinh",
      untouched and not script and SENT == ["bri:5\nfx:scan\n0:ready\n1:off"] and K.any_alive(),
      "sent=%s, script=%s, any_alive khi khong co file=%s" % (SENT, script, K.any_alive()))

got = {
    "ngat": run_watch([("busy", 999), ("busy", 999), ("idle", 1500)]),
    "duyet quyen": run_watch([("busy", 999), ("waiting", 1200, "permission prompt"), ("waiting", 1200, "permission prompt"),
                              ("busy", 1300), ("idle", 1500)]),
    "idle cu truoc prompt": run_watch([("idle", 900), ("idle", 900)]),
    "tu mo /model": run_watch([("busy", 999), ("waiting", 1200, "dialog open")]),
    "luot cu": run_watch([("idle", 1500)], token="t0"),
    "claude da tat": run_watch([("busy", 1300), ("idle", 1500)], pid=DEAD_PID),
}
check("doi den theo trang thai: ngat -> ready, duyet quyen -> wait/busy/ready, claude da tat va con lai khong gui",
      got == {"ngat": ["0:ready"], "duyet quyen": ["0:wait", "0:busy", "0:ready"], "idle cu truoc prompt": [],
              "tu mo /model": [], "luot cu": [], "claude da tat": []}, "got=%s" % got)

fresh(num_leds=2)
cfgdir = tempfile.mkdtemp(); os.makedirs(os.path.join(cfgdir, "projects", "-proj"))
with open(os.path.join(cfgdir, "projects", "-proj", "A.jsonl"), "w", encoding="utf-8") as f:
    for rec in ({"type": "ai-title", "aiTitle": "Ten tu dat", "sessionId": "A"},
                {"type": "custom-title", "customTitle": "Bảng trạng thái USB", "sessionId": "A"},  # /rename
                {"type": "ai-title", "aiTitle": "Ten tu dat moi", "sessionId": "A"}):
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
os.environ["CLAUDE_CONFIG_DIR"] = cfgdir
hook("SessionStart", "A", X)
hook("SessionStart", "B", "/y")           # B chua co transcript: in cwd
S.save(S.MUTED, ["/khac"]); S.save(S.PENDING, {"/z": 1})  # status chi in den, khong in muted/pending
out = cmd(L.cmd_status, X, None)
os.environ.pop("CLAUDE_CONFIG_DIR")
check("status chi in ten session tren tung den",
      out.splitlines()[1:] == ["  đèn 1: Bảng trạng thái USB (/proj)", "  đèn 2: /y"], "in %r" % out)

fresh()
for raw in ("", "not json", "{}", '{"hook_event_name":"Stop"}'):
    sys.stdin = io.StringIO(raw); L.cmd_hook()
check("stdin rong/sai", SENT == [], "sent=%s" % SENT)

# Do sang / hieu ung den trong: luu config, board cam lai la mat nen gui lai luc mo session
fresh()
outs = [cmd(L.display.cmd_brightness, X, None, v) for v in ("30%", "101", "abc")]
outs += [cmd(L.display.cmd_fx, X, None, v) for v in ("2", "0", "9", "firefly", "breathe")]  # so theo danh sach; firefly da bo
sent = list(SENT); SENT.clear()
hook("SessionStart", "A", X)
check("doi do sang va hieu ung, gui lai luc mo session",
      sent == ["bri:30", "fx:rainbow", "fx:none", "fx:breathe"] and (S.cfg()["brightness"], S.cfg()["idle_fx"]) == (30, "breathe")
      and SENT == ["bri:30\nfx:breathe\n0:off\n0:ready"],
      "in %r, sent=%s, cfg=%s, mo session gui %s" % (outs, sent, S.cfg(), SENT))

# Lan mo cong dau sau attach, tty con ECHO nen doi status bar CircuitPython xuong board,
# rac nam san trong buf: lenh that van phai den board thanh mot dong rieng
class FakeSerial:
    written = b""
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def write(self, b): FakeSerial.written += b
    def flush(self): pass
fresh(); S.save(S.CONFIG, {"port": "/dev/fake", "num_leds": 1, "auto_assign": True, "debug": False})
real_serial, sys.modules["serial"] = sys.modules.get("serial"), type(sys)("serial")
sys.modules["serial"].Serial = FakeSerial
try:
    REAL_SEND("0:ready")
finally:
    if real_serial: sys.modules["serial"] = real_serial
    else: sys.modules.pop("serial")
junk = "^[]0;\U0001f40dcode.py | 10.3.1^[\\"
lines = [s.strip() for s in (junk + FakeSerial.written.decode()).replace("\r", "\n").split("\n")]
check("lenh dau khong dinh rac trong buf board", "0:ready" in lines, "board doc duoc cac dong %r" % lines)

# Sau attach, node /dev/ttyACM0 la root 0600 mot luc roi udev moi cap quyen dialout:
# wsl_attach chi duoc tra ve khi cong da mo duoc
calls = {"find": 0, "access": 0}
def fake_find():
    calls["find"] += 1
    return None if calls["find"] == 1 else "/dev/ttyACM0"
def fake_access(path, mode):
    calls["access"] += 1
    return calls["access"] >= 3
saved = (B.USBIPD, B.find_port, os.access, L.time.sleep, subprocess.run)
B.USBIPD, B.find_port, os.access, L.time.sleep = SRC, fake_find, fake_access, lambda s: None
subprocess.run = lambda *a, **k: subprocess.CompletedProcess(a, 0, "", "")
try:
    REAL_ATTACH()
finally:
    B.USBIPD, B.find_port, os.access, L.time.sleep, subprocess.run = saved
check("attach cho den khi mo duoc cong", calls["access"] == 3, "os.access goi %d lan" % calls["access"])

# Mat cong: hook tu goi usbipd attach toi da 1 lan moi 30 s (lenh slash luon thu). Cong co lai sau khi mat, du ai
# gan (gan tay, hay usbipd gan xong ma udev cham qua 3 s), thi bao True dung mot lan de hook gui lai ca thanh
fresh(); runs, port = [], [None]
saved = (B.USBIPD, B.find_port, subprocess.run)
B.USBIPD, B.find_port = SRC, lambda: port[0]
subprocess.run = lambda *a, **k: runs.append(a) or subprocess.CompletedProcess(a, 1, "", "khong thay thiet bi")
try:
    res = [REAL_ATTACH(30), REAL_ATTACH(30), REAL_ATTACH()]
    port[0] = "/dev/ttyACM0"
    res += [REAL_ATTACH(30), REAL_ATTACH(30)]
finally:
    B.USBIPD, B.find_port, subprocess.run = saved
check("mat cong: tu gan lai toi da 1 lan moi 30 s, cong co lai thi bao gui lai ca thanh mot lan",
      len(runs) == 2 and res == [False, False, False, True, False], "usbipd chay %d lan, tra %s" % (len(runs), res))

# 3 session mo cung luc: moi session phai co den rieng ngay tu SessionStart
bad = 0
for _ in range(10):
    home = tempfile.mkdtemp(); os.makedirs(os.path.join(home, ".claude-light"))
    with open(os.path.join(home, ".claude-light", "config.json"), "w") as f:
        json.dump({"port": "/nonexistent", "num_leds": 3, "auto_assign": True, "debug": False}, f)
    cfgdir = tempfile.mkdtemp(); os.makedirs(os.path.join(cfgdir, "sessions"))  # SessionStart bat `light.py keep` that:
    S.save(os.path.join(cfgdir, "sessions", "1.json"), {"sessionId": "khac", "pid": 1})  # khong session nao song, thoat
    env = dict(os.environ, HOME=home, CLAUDE_CONFIG_DIR=cfgdir)
    procs = [subprocess.Popen([sys.executable, SRC, "hook"], stdin=subprocess.PIPE, env=env)
             for _ in "ABC"]
    for s, pr in zip("ABC", procs):  # ghi het stdin truoc roi moi doi, de 3 tien trinh chay song song
        pr.stdin.write(json.dumps({"hook_event_name": "SessionStart", "session_id": s, "cwd": "/p" + s}).encode())
        pr.stdin.close()
    for pr in procs:
        pr.wait()
    got = json.load(open(os.path.join(home, ".claude-light", "map.json")))
    bad += len({v["led"] for v in got.values()}) != 3
check("3 session mo cung luc", bad == 0, "%d/10 lan co session mat den" % bad)

print("\n%d/%d pass" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
