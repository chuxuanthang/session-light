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

Module cung thu muc: light_store (file, cau hinh, log), light_serial (cong serial, usbipd),
light_sessions (gan session voi den), light_watch (theo doi trang thai ngoai hook).
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # nap duoc ca khi import tu noi khac (test)
import light_store as store, light_serial as board, light_sessions as sessions, light_watch as watch

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
# hop thoai nao, nen dua ve xanh
WAIT_NOTIFY = {"permission_prompt", "elicitation_dialog"}

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
    store.log("event=%s sid=%s cwd=%s" % (event, sid[:8], cwd))
    if not state or not sid:
        return
    if event == "SessionStart":
        board.wsl_attach()
    with store.locked():
        if event == "SessionEnd":
            led = sessions.end_session(sid, cwd, data.get("reason"))
        else:
            led = sessions.led_for(sid, cwd)
    if led is not None:
        board.send("%d:%s" % (led, state))
        if event == "UserPromptSubmit":
            watch.watch_turn(sid, started)

def cmd_connect(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        print("Cách dùng: /session-light:usb-connect <số đèn>"); return
    c = store.cfg()
    if not 0 <= n < int(c["num_leds"]):
        print("Số đèn phải từ 0 đến %d" % (int(c["num_leds"]) - 1)); return
    board.wsl_attach()
    cwd = os.getcwd()
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    with store.locked():
        mu = [x for x in store.load(store.MUTED, []) if x not in (cwd, sid)]
        store.save(store.MUTED, mu)
        m = store.load(store.MAP, {})
        mine = sessions.my_sessions(m, cwd)
        old = {m[k]["led"] for k in mine if k in m} - {n}
        for k in [k for k, v in m.items() if v["led"] == n and k not in mine]:
            del m[k]  # last-wins: day session khac dang giu den n
        if sid:
            m[sid] = {"led": n, "cwd": cwd}
        for k in mine:
            if k in m:
                m[k]["led"] = n
        pend = store.load(store.PENDING, {})
        assigned = any(k in m for k in mine)
        if assigned:
            pend.pop(cwd, None)
        else:  # khong biet session_id va chua co session nao o cwd: hook ke tiep se chot
            pend[cwd] = n
        store.save(store.MAP, m); store.save(store.PENDING, pend)
    for x in old:
        board.send("%d:off" % x)
    board.send("%d:ready" % n)
    if assigned:
        print("Đã gán đèn %d cho session ở %s" % (n, cwd))
    else:
        print("Đèn %d sẽ được gán cho session ở %s" % (n, cwd))

def cmd_disconnect():
    cwd = os.getcwd()
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    with store.locked():
        m = store.load(store.MAP, {})
        leds = {m.pop(k)["led"] for k in sessions.my_sessions(m, cwd) if k in m}
        store.save(store.MAP, m)
        pend = store.load(store.PENDING, {}); pend.pop(cwd, None); store.save(store.PENDING, pend)
        mu = store.load(store.MUTED, [])
        mu += [x for x in (cwd, sid) if x and x not in mu]
        store.save(store.MUTED, mu)
    for n in leds:
        board.send("%d:off" % n)
    if leds:
        print("Đã bỏ gán đèn %s cho session ở %s" % (", ".join(map(str, sorted(leds))), cwd))
    else:
        print("Session ở %s chưa gán đèn nào, đã tắt tự gán cho thư mục này" % cwd)

def cmd_status():
    c = store.cfg(); m = store.load(store.MAP, {})
    print("Cổng: %s   số đèn: %d" % (board.find_port() or "không thấy", int(c["num_leds"])))
    for n in range(int(c["num_leds"])):
        owner = [(sid, v["cwd"]) for sid, v in m.items() if v["led"] == n]
        if not owner:
            print("  đèn %d: (trống)" % n); continue
        title = sessions.session_title(owner[0][0])
        print("  đèn %d: %s" % (n, "%s (%s)" % (title, owner[0][1]) if title else owner[0][1]))

def cmd_test():
    board.wsl_attach()
    c = store.cfg(); n = int(c["num_leds"])
    for st in ("ready", "busy", "wait", "off"):
        for i in range(n):
            board.send("%d:%s" % (i, st)); time.sleep(0.15)
        time.sleep(0.8)
    print("ok" if board.find_port() else "khong tim thay board")

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
            watch.cmd_watch(*args[1:4])
        elif args[0] == "send" and len(args) > 1:
            print("ok" if board.send(args[1]) else "fail")
        else:
            print(__doc__)
    except Exception as e:
        store.log("loi: %r" % e)
    sys.exit(0)
