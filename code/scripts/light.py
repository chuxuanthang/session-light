#!/usr/bin/env python3
"""
claude-light: gui trang thai session Claude Code xuong den USB.

Cach dung:
  light.py hook              (duoc Claude Code goi, doc JSON tu stdin)
  light.py connect <n>       gan session o thu muc hien tai vao den n
  light.py disconnect        bo gan cho thu muc hien tai, tat den
  light.py status            in bang den -> session
  light.py test              chay thu cac mau
  light.py send <n>:<state>  gui lenh tho (debug)
  light.py watch ...         (noi bo) theo doi trang thai session trong luot

File cau hinh: ~/.claude-light/config.json
  {"port": null, "num_leds": 8, "auto_assign": true, "debug": false}
"""
import sys, os, json, time, contextlib, glob

HOME = os.path.expanduser("~")
DIR = os.path.join(HOME, ".claude-light")
CONFIG = os.path.join(DIR, "config.json")
MAP = os.path.join(DIR, "map.json")          # {session_id: {"led": n, "cwd": "..."}}
PENDING = os.path.join(DIR, "pending.json")  # {cwd: led}
MUTED = os.path.join(DIR, "muted.json")      # [cwd hoac session_id] da disconnect: khong tu gan lai
LOG = os.path.join(DIR, "log.txt")
LOCK = os.path.join(DIR, "lock")
WATCH = os.path.join(DIR, "watch.json")      # {session_id: token cua tien trinh theo doi luot hien tai}
# WSL2 khong thay COM port: nho usbipd-win gan board vao (can bind 1 lan bang PowerShell Admin)
USBIPD = "/mnt/c/Program Files/usbipd-win/usbipd.exe"
BOARD_HWID = "2e8a:101f"

EVENT_STATE = {
    "SessionStart": "ready",
    "UserPromptSubmit": "busy",
    "PreToolUse": "busy",
    "PostToolUse": "busy",
    "PostToolUseFailure": "busy",
    "PermissionRequest": "wait",
    "Notification": "wait",
    "Stop": "ready",
    "StopFailure": "ready",
    "SessionEnd": "off",
}
# Notification: bao do khi can nguoi xu ly. idle_prompt chi ban khi Claude ranh >=60s va khong co
# hop thoai nao, nen dua ve xanh: go den cam ket sau khi bam Esc/Ctrl+C luc Claude dang viet
WAIT_NOTIFY = {"permission_prompt", "elicitation_dialog"}

def load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save(path, data):
    os.makedirs(DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

@contextlib.contextmanager
def locked():
    # nhieu session ban hook cung luc: khoa de khong ghi de map.json cua nhau
    os.makedirs(DIR, exist_ok=True)
    with open(LOCK, "w") as f:
        try:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
        except ImportError:  # Windows khong co fcntl: chay khong khoa
            pass
        yield

def cfg():
    c = {"port": None, "num_leds": 8, "auto_assign": True, "debug": False}
    c.update(load(CONFIG, {}))
    if not os.path.exists(CONFIG):
        save(CONFIG, c)
    return c

def log(msg):
    if cfg().get("debug"):
        os.makedirs(DIR, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")

# ---------- serial ----------
def find_port():
    c = cfg()
    if c.get("port"):
        return c["port"]
    try:
        from serial.tools import list_ports
    except ImportError:
        return None
    for p in list_ports.comports():
        desc = (p.description or "") + " " + (p.manufacturer or "")
        if p.vid == 0x2E8A or "CircuitPython" in desc:
            return p.device
    return None

def wsl_attach():
    # chi chay tren WSL (co usbipd.exe) va khi chua thay cong; may khac bo qua
    if not os.path.exists(USBIPD) or find_port():
        return
    import subprocess
    try:
        r = subprocess.run([USBIPD, "attach", "--wsl", "--hardware-id", BOARD_HWID],
                           cwd="/mnt/c", capture_output=True, text=True, timeout=15)
    except Exception as e:
        log("usbipd attach loi: %r" % e); return
    log("usbipd attach exit=%d %s" % (r.returncode, r.stderr.strip()[-200:]))
    if r.returncode != 0:
        return
    # cho /dev/ttyACM* hien ra VA mo duoc, toi da ~3s: node moi tao la root 0600,
    # udev doi sang group dialout sau ~0.2s; gui som qua thi send() het luot thu lai
    for _ in range(30):
        port = find_port()
        if port and os.access(port, os.R_OK | os.W_OK):
            return
        time.sleep(0.1)

def send(line, retries=4):
    try:
        import serial
    except ImportError:
        log("pyserial chua cai: pip install pyserial")
        return False
    port = find_port()
    if not port:
        log("khong tim thay cong serial cua board")
        return False
    for i in range(retries):
        try:
            with serial.Serial(port, 115200, timeout=0.3, write_timeout=0.5) as s:
                # "\n" dau dong cat rac con trong buf cua board thanh dong rieng (board tra "err"
                # cho dong rac, dong rong thi bo qua). Rac co that: lan mo dau sau khi attach,
                # tty con ECHO nen doi lai status bar CircuitPython xuong board.
                s.write(("\n" + line + "\n").encode())
                s.flush()
                log("-> " + line)
                return True
        except Exception as e:
            log("port busy/loi (%d): %s" % (i, e))
            time.sleep(0.08)
    return False

# ---------- mapping ----------
def led_for(session_id, cwd):
    c = cfg()
    m = load(MAP, {})
    if session_id in m:
        if m[session_id]["cwd"] != cwd:  # session da cd: giu cwd moi de slash command tim thay
            m[session_id]["cwd"] = cwd
            save(MAP, m)
        return m[session_id]["led"]
    used = {v["led"] for v in m.values()}
    pend = load(PENDING, {})
    led = pend.pop(cwd, None)
    if led is not None:
        save(PENDING, pend)  # pending chi dung mot lan, ke ca khi den da bi chiem
    if led in used:  # hook khong gianh den cua session khac; chi /usb-connect moi day duoc
        led = None
    mu = load(MUTED, [])
    if led is None and c.get("auto_assign") and cwd not in mu and session_id not in mu:
        for n in range(int(c["num_leds"])):
            if n not in used:
                led = n
                break
    if led is None:
        return None
    m[session_id] = {"led": led, "cwd": cwd}
    save(MAP, m)
    return led

def end_session(session_id, cwd, reason):
    mu = load(MUTED, [])
    if session_id in mu:
        mu.remove(session_id); save(MUTED, mu)
    m = load(MAP, {})
    if session_id not in m:  # chua gan den hoac da bi day ra: khong tat den cua session khac
        return None
    led = m.pop(session_id)["led"]
    save(MAP, m)
    if reason == "clear":  # /clear tao session_id moi: de session moi nhan lai dung den nay
        pend = load(PENDING, {}); pend[cwd] = led; save(PENDING, pend)
    return led

def session_title(sid):
    # ten tren tab terminal: Claude Code ghi vao transcript; ten dat bang /rename uu tien hon ten tu dat
    root = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")
    found = {}
    for path in glob.glob(os.path.join(root, "projects", "*", glob.escape(sid) + ".jsonl")):
        with open(path, "rb") as f:  # transcript co the ~100MB: loc byte truoc, chi giai ma dong co tieu de
            for line in f:
                if b'-title"' not in line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if isinstance(d, dict) and d.get("type") in ("custom-title", "ai-title"):
                    found[d["type"]] = d.get("customTitle") or d.get("aiTitle")
    return found.get("custom-title") or found.get("ai-title")

def my_sessions(m, cwd):
    # slash command khong co JSON cua hook: lay session_id tu bien moi truong, thieu thi doan theo cwd
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    return [sid] if sid else [k for k, v in m.items() if v["cwd"] == cwd]

# ---------- theo doi trang thai trong luot ----------
# Hook khong du: bam Esc/Ctrl+C thi khong hook nao chay (Stop khong, idle_prompt cung khong vi phim Ctrl+C
# tinh la tuong tac); duyet quyen xong cung khong co hook nao cho den khi tool chay xong. Claude Code ghi
# trang thai tung tien trinh vao <config>/sessions/<pid>.json: "busy" suot luot, "waiting" khi co hop thoai
# can nguoi (waitingFor cho biet ly do), "idle" ngay khi luot dung. Moi luot chay mot tien trinh nen doc
# file do va doi den theo moi lan trang thai doi; ve "idle" thi tra den xanh roi thoat.
IDLE = ("idle", "shell")  # "shell": ranh nhung dang o che do `!` bash
NOT_WAIT = (None, "dialog open")  # nguoi dung tu mo /model, /config...: khong phai Claude dang cho

def status_file(sid):
    root = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")
    recs = ((p, load(p, {})) for p in glob.glob(os.path.join(root, "sessions", "*.json")))
    found = [(r.get("updatedAt", 0), p) for p, r in recs if r.get("sessionId") == sid]
    return max(found)[1] if found else None

def watch_turn(sid, since_ms):
    token = "%d.%d" % (os.getpid(), since_ms)
    with locked():  # luot moi thay token: tien trinh cu tu thoat. Bo token cua session da ket thuc
        m = load(MAP, {})
        w = {k: v for k, v in load(WATCH, {}).items() if k in m}
        w[sid] = token; save(WATCH, w)
    import subprocess
    detach = {"creationflags": 0x208} if os.name == "nt" else {"start_new_session": True}
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "watch", sid, token, str(since_ms)],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **detach)

def cmd_watch(sid, token, since_ms):
    since, path, seen, end = int(since_ms), None, None, time.time() + 6 * 3600
    while time.time() < end:
        time.sleep(0.25)
        if load(WATCH, {}).get(sid) != token or sid not in load(MAP, {}):
            return  # co luot moi, hoac session da ket thuc / bo gan den
        rec = load(path, {}) if path else {}
        if rec.get("sessionId") != sid:
            path = status_file(sid)
            if not path:
                return  # Claude Code khong ghi file trang thai: khong theo doi duoc
            continue
        status, at = rec.get("status"), rec.get("statusUpdatedAt", 0)
        if at <= since or at == seen:
            continue  # chua doi tu luc gui prompt (hook UserPromptSubmit da bat cam)
        seen = at
        state = ("ready" if status in IDLE else "busy" if status == "busy" else
                 "wait" if status == "waiting" and rec.get("waitingFor") not in NOT_WAIT else None)
        led = load(MAP, {}).get(sid, {}).get("led")
        log("status=%s/%s sid=%s" % (status, rec.get("waitingFor"), sid[:8]))
        if state and led is not None:
            send("%d:%s" % (led, state))
        if status in IDLE:
            return

# ---------- commands ----------
def cmd_hook():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    started = int(time.time() * 1000)
    event = data.get("hook_event_name", "")
    sid = data.get("session_id", "")
    cwd = data.get("cwd") or os.getcwd()
    state = EVENT_STATE.get(event)
    if event == "Notification":
        kind = data.get("notification_type")
        state = "wait" if kind in WAIT_NOTIFY else "ready" if kind == "idle_prompt" else None
    if event == "PostToolUseFailure" and data.get("is_interrupt"):
        state = "ready"  # Esc/Ctrl+C luc tool dang chay: Stop khong chay
    if event == "PreToolUse" and data.get("tool_name") == "AskUserQuestion":
        state = "wait"
    log("event=%s sid=%s cwd=%s" % (event, sid[:8], cwd))
    if not state or not sid:
        return
    if event == "SessionStart":
        wsl_attach()
    with locked():
        led = end_session(sid, cwd, data.get("reason")) if event == "SessionEnd" else led_for(sid, cwd)
    if led is not None:
        send("%d:%s" % (led, state))
        if event == "UserPromptSubmit":
            watch_turn(sid, started)

def cmd_connect(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        print("Cách dùng: /session-light:usb-connect <số đèn>"); return
    c = cfg()
    if not 0 <= n < int(c["num_leds"]):
        print("Số đèn phải từ 0 đến %d" % (int(c["num_leds"]) - 1)); return
    wsl_attach()
    cwd = os.getcwd()
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    with locked():
        mu = [x for x in load(MUTED, []) if x not in (cwd, sid)]
        save(MUTED, mu)
        m = load(MAP, {})
        mine = my_sessions(m, cwd)
        old = {m[k]["led"] for k in mine if k in m} - {n}
        for k in [k for k, v in m.items() if v["led"] == n and k not in mine]:
            del m[k]  # last-wins: day session khac dang giu den n
        if sid:
            m[sid] = {"led": n, "cwd": cwd}
        for k in mine:
            if k in m:
                m[k]["led"] = n
        pend = load(PENDING, {})
        assigned = any(k in m for k in mine)
        if assigned:
            pend.pop(cwd, None)
        else:  # khong biet session_id va chua co session nao o cwd: hook ke tiep se chot
            pend[cwd] = n
        save(MAP, m); save(PENDING, pend)
    for x in old:
        send("%d:off" % x)
    send("%d:ready" % n)
    if assigned:
        print("Đã gán đèn %d cho session ở %s" % (n, cwd))
    else:
        print("Đèn %d sẽ được gán cho session ở %s" % (n, cwd))

def cmd_disconnect():
    cwd = os.getcwd()
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    with locked():
        m = load(MAP, {})
        leds = {m.pop(k)["led"] for k in my_sessions(m, cwd) if k in m}
        save(MAP, m)
        pend = load(PENDING, {}); pend.pop(cwd, None); save(PENDING, pend)
        mu = load(MUTED, [])
        mu += [x for x in (cwd, sid) if x and x not in mu]
        save(MUTED, mu)
    for n in leds:
        send("%d:off" % n)
    if leds:
        print("Đã bỏ gán đèn %s cho session ở %s" % (", ".join(map(str, sorted(leds))), cwd))
    else:
        print("Session ở %s chưa gán đèn nào, đã tắt tự gán cho thư mục này" % cwd)

def cmd_status():
    c = cfg(); m = load(MAP, {})
    print("Cổng: %s   số đèn: %d" % (find_port() or "không thấy", int(c["num_leds"])))
    for n in range(int(c["num_leds"])):
        owner = [(sid, v["cwd"]) for sid, v in m.items() if v["led"] == n]
        if not owner:
            print("  đèn %d: (trống)" % n); continue
        title = session_title(owner[0][0])
        print("  đèn %d: %s" % (n, "%s (%s)" % (title, owner[0][1]) if title else owner[0][1]))

def cmd_test():
    wsl_attach()
    c = cfg(); n = int(c["num_leds"])
    for st in ("ready", "busy", "wait", "off"):
        for i in range(n):
            send("%d:%s" % (i, st)); time.sleep(0.15)
        time.sleep(0.8)
    print("ok" if find_port() else "khong tim thay board")

if __name__ == "__main__":
    try:  # in tieng Viet co dau: Windows mac dinh cp1252 se loi
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    args = sys.argv[1:]
    try:
        if not args or args[0] == "hook":
            cmd_hook()
        elif args[0] == "connect":
            cmd_connect(args[1] if len(args) > 1 else 0)  # khong go so -> den 0
        elif args[0] == "disconnect":
            cmd_disconnect()
        elif args[0] == "status":
            cmd_status()
        elif args[0] == "test":
            cmd_test()
        elif args[0] == "watch" and len(args) > 3:
            cmd_watch(*args[1:4])
        elif args[0] == "send" and len(args) > 1:
            print("ok" if send(args[1]) else "fail")
        else:
            print(__doc__)
    except Exception as e:
        log("loi: %r" % e)
    sys.exit(0)
