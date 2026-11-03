#!/usr/bin/env python3
"""
claude-light: gui trang thai session Claude Code xuong den USB.

Cach dung:
  light.py hook              (duoc Claude Code goi, doc JSON tu stdin)
  light.py connect <n>       gan session o thu muc hien tai vao den n (1-8, den 1 ben trai, bo trong = 1)
  light.py disconnect [n]    bo gan den n (1-8, 0 la tat ca), bo trong la den cua thu muc hien tai; tat den
  light.py status            in bang den -> session
  light.py test              chay thu cac mau
  light.py brightness [0-100]  doi do sang den co session (phan tram), bo trong de xem
  light.py blink             nhay xanh la 3 lan den cua session o thu muc hien tai
  light.py sort              don den dang gan ve lien nhau tu den 1, giu thu tu (1 3 5 -> 1 2 3)
  light.py swap <a> <b>      doi hai den cho nhau (1-8)
  light.py fx [so|ten]       doi hieu ung den trong: 0 none | 1 scan | 2 rainbow | 3 breathe | 4 chase | 5 comet | 6 wave | 7 heart
  light.py send <n>:<state>  gui lenh tho (debug), n dem tu 0
  light.py watch ...         (noi bo) theo doi trang thai session trong luot
  light.py keep              (noi bo) tien trinh nen tu gan lai board, gui lai mau khi board cam lai

File cau hinh: ~/.claude-light/config.json
  {"port": null, "num_leds": 8, "auto_assign": true, "debug": false, "brightness": 5, "idle_fx": "scan"}

Module cung thu muc: light_store (file, cau hinh, log), light_serial (cong serial, usbipd),
light_sessions (gan session voi den), light_watch (theo doi trang thai ngoai hook),
light_display (do sang, hieu ung den trong).

Nguoi dung dem den tu 1 (connect, status, disconnect); map.json va lenh xuong board dem tu 0.
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # nap duoc ca khi import tu noi khac (test)
import light_store as store, light_serial as board, light_sessions as sessions, light_watch as watch
import light_display as display, light_reconnect as reconnect

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
# Stop ma con Agent/Workflow chay nen (background_tasks): Claude Code van ghi phien "busy", den giu cam. Shell nen
# (dev server), monitor thi khong tinh, giong Claude Code
BACKGROUND_WORK = {"subagent", "workflow"}

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
    if event == "Stop" and any(isinstance(t, dict) and t.get("type") in BACKGROUND_WORK
                               for t in data.get("background_tasks") or ()):
        state = "busy"
    store.log("event=%s sid=%s cwd=%s" % (event, sid[:8], cwd))
    if not state or not sid:
        return
    # board quen het mau moi lan cam lai: gui lai ca thanh luc mo session (ke ca session khong co den) va khi
    # hook vua tu gan lai board vao WSL (toi da 1 lan moi 30 s, board rut han thi khong ton moi hook)
    resync = board.wsl_attach(0 if event == "SessionStart" else 30) or event == "SessionStart"
    with store.locked():
        if event == "SessionStart" and data.get("source") == "resume":
            sessions.release(sid)
        lines = display.sync_lines(sid) if resync else []  # truoc khi gan: den cua session da chet duoc tra
        if event == "SessionEnd":
            led = sessions.end_session(sid, cwd, data.get("reason"))
        else:
            led = sessions.led_for(sid, cwd)
    if led is not None:
        # hop thoai can nguoi con mo thi giu do (hook subagent chay nen, Stop luc subagent xin quyen)
        if state in ("busy", "ready") and not data.get("is_interrupt") and watch.user_waiting(sid):
            state = "wait"
        lines.append("%d:%s" % (led, state))
    if lines:
        board.send("\n".join(lines))
    if event == "SessionStart":
        reconnect.spawn()
    if led is not None:
        if event == "UserPromptSubmit":
            watch.watch_turn(sid, started)

def cmd_connect(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        print("Cách dùng: /session-light:usb-connect <số đèn>"); return
    total = int(store.cfg()["num_leds"])
    if not 1 <= n <= total:
        print("Số đèn phải từ 1 đến %d" % total); return
    led = n - 1
    cwd = os.getcwd()
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    lines = display.attach_lines(sid)
    with store.locked():
        mu = [x for x in store.load(store.MUTED, []) if x not in (cwd, sid)]
        store.save(store.MUTED, mu)
        m = store.load(store.MAP, {})
        mine = sessions.my_sessions(m, cwd)
        old = {m[k]["led"] for k in mine if k in m} - {led}
        for k in [k for k, v in m.items() if v["led"] == led and k not in mine]:
            del m[k]  # last-wins: day session khac dang giu den nay
        if sid:
            m[sid] = {"led": led, "cwd": cwd}
        for k in mine:
            if k in m:
                m[k]["led"] = led
        pend = store.load(store.PENDING, {})
        assigned = any(k in m for k in mine)
        if assigned:
            pend.pop(cwd, None)
        else:  # khong biet session_id va chua co session nao o cwd: hook ke tiep se chot
            pend[cwd] = led
        store.save(store.MAP, m); store.save(store.PENDING, pend)
    board.send("\n".join(lines + ["%d:off" % x for x in old] + ["%d:ready" % led]))
    if assigned:
        print("Đã gán đèn %d cho session ở %s" % (n, cwd))
    else:
        print("Đèn %d sẽ được gán cho session ở %s" % (n, cwd))

def cmd_disconnect(n=None):
    if n is not None:  # /usb-disconnect <so>: den bat ky, 0 la tat ca
        return display.cmd_disconnect_led(n)
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
        print("Đã bỏ gán đèn %s cho session ở %s" % (", ".join(str(x + 1) for x in sorted(leds)), cwd))
    else:
        print("Session ở %s chưa gán đèn nào, đã tắt tự gán cho thư mục này" % cwd)

def cmd_status():
    c = store.cfg(); m = store.load(store.MAP, {})
    print("Cổng: %s   số đèn: %d" % (board.find_port() or "không thấy", int(c["num_leds"])))
    for n in range(int(c["num_leds"])):
        owner = [(sid, v["cwd"]) for sid, v in m.items() if v["led"] == n]
        if not owner:
            print("  đèn %d: (trống)" % (n + 1)); continue
        print("  đèn %d: %s" % (n + 1, sessions.label(*owner[0])))

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
            cmd_connect(args[1] if len(args) > 1 else 1)  # khong go so -> den 1
        elif args[0] == "disconnect":
            cmd_disconnect(*args[1:2])
        elif args[0] == "status":
            cmd_status()
        elif args[0] in ("brightness", "fx"):  # display.cmd_brightness / cmd_fx
            getattr(display, "cmd_" + args[0])(args[1] if len(args) > 1 else None)
        elif args[0] in ("blink", "sort", "test"):  # display.cmd_blink / cmd_sort / cmd_test
            getattr(display, "cmd_" + args[0])()
        elif args[0] == "swap":
            display.cmd_swap(" ".join(args[1:]))
        elif args[0] == "keep":
            reconnect.cmd_keep()
        elif args[0] == "watch" and len(args) > 3:
            watch.cmd_watch(*args[1:4])
        elif args[0] == "send" and len(args) > 1:
            print("ok" if board.send(args[1]) else "fail")
        else:
            print(__doc__)
    except Exception as e:
        store.log("loi: %r" % e)
    sys.exit(0)
