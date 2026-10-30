"""Test cac ca bien cua scripts/light.py. Khong dung den board va ~/.claude-light that.

Chay: python3 tests/light-edge-cases.py   (exit 1 neu co ca FAIL)
"""
import contextlib, importlib.util, io, json, os, subprocess, sys, tempfile

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code", "scripts", "light.py")
spec = importlib.util.spec_from_file_location("light", SRC)
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)

SENT = []
L.send = lambda line, retries=4: SENT.append(line) or True
L.wsl_attach = lambda: None
FILES = {"CONFIG": "config.json", "MAP": "map.json", "PENDING": "pending.json",
         "MUTED": "muted.json", "LOG": "log.txt", "LOCK": "lock"}

def fresh(num_leds=1, auto=True):
    L.DIR = tempfile.mkdtemp()
    for name, f in FILES.items():
        setattr(L, name, os.path.join(L.DIR, f))
    L.save(L.CONFIG, {"port": None, "num_leds": num_leds, "auto_assign": auto, "debug": False})
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

def m(): return L.load(L.MAP, {})
def p(): return L.load(L.PENDING, {})
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
    cmd(L.cmd_connect, XC, sid, 1)
    check("connect sau khi cd (%s)" % mode, led("A") == 1 and not p() and "0:off" in SENT,
          "map=%s pending=%s sent=%s" % (m(), p(), SENT))

fresh(num_leds=2)
hook("SessionStart", "A", X)
cmd(L.cmd_disconnect, X, "A")
hook("PostToolUse", "A", XC)              # cd sau khi disconnect: khong duoc tu gan lai
check("disconnect roi cd", "A" not in m(), "map=%s" % m())

fresh(num_leds=2)
hook("SessionStart", "A", X)
hook("SessionStart", "B", X)
cmd(L.cmd_connect, X, "B", 0)
check("2 session cung cwd, B connect 0", led("B") == 0 and led("A") != 0, "map=%s" % m())

fresh(num_leds=2)
hook("SessionStart", "A", X)
hook("SessionStart", "B", X)
cmd(L.cmd_disconnect, X, "B")
check("2 session cung cwd, B disconnect", led("A") == 0 and "B" not in m(), "map=%s" % m())

fresh(num_leds=3)
hook("SessionStart", "B", "/other")       # B -> 0
hook("SessionStart", "A", X)              # A -> 1
cmd(L.cmd_connect, X, "A", 2)             # A chuyen sang 2
hook("SessionEnd", "A", X, reason="clear")
hook("SessionStart", "A2", X, source="clear")
check("/clear giu den da chon", led("A2") == 2 and not p(), "map=%s pending=%s" % (m(), p()))

fresh(num_leds=1, auto=False)
cmd(L.cmd_connect, X, None, 0)
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
check("session moi khong gianh den dang bi chiem", led("A2") == 0 and "B" not in m() and SENT == [],
      "map=%s pending=%s sent=%s" % (m(), p(), SENT))

fresh(num_leds=1)
hook("SessionStart", "A", X)
cmd(L.cmd_connect, "/y", "B", 0)          # B gianh den 0, A bi day ra
SENT.clear()
hook("SessionEnd", "A", X)
check("session bi day ra ket thuc", SENT == [] and led("B") == 0, "sent=%s map=%s" % (SENT, m()))

fresh()
out = cmd(L.cmd_disconnect, X, "A")
check("disconnect khi chua gan den", "chưa gán đèn nào" in out, "in %r" % out)

fresh()
hook("SessionStart", "A", X); SENT.clear()
hook("Notification", "A", X, notification_type="idle_prompt")
hook("PreToolUse", "A", X, tool_name="AskUserQuestion")
check("idle_prompt bo qua, AskUserQuestion -> wait", SENT == ["0:wait"], "sent=%s" % SENT)

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
L.save(L.MUTED, ["/khac"]); L.save(L.PENDING, {"/z": 1})  # status chi in den, khong in muted/pending
out = cmd(L.cmd_status, X, None)
os.environ.pop("CLAUDE_CONFIG_DIR")
check("status chi in ten session tren tung den",
      out.splitlines()[1:] == ["  đèn 0: Bảng trạng thái USB (/proj)", "  đèn 1: /y"], "in %r" % out)

fresh()
for raw in ("", "not json", "{}", '{"hook_event_name":"Stop"}'):
    sys.stdin = io.StringIO(raw); L.cmd_hook()
check("stdin rong/sai", SENT == [], "sent=%s" % SENT)

# 3 session mo cung luc: moi session phai co den rieng ngay tu SessionStart
bad = 0
for _ in range(10):
    home = tempfile.mkdtemp(); os.makedirs(os.path.join(home, ".claude-light"))
    with open(os.path.join(home, ".claude-light", "config.json"), "w") as f:
        json.dump({"port": "/nonexistent", "num_leds": 3, "auto_assign": True, "debug": False}, f)
    env = dict(os.environ, HOME=home)
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
