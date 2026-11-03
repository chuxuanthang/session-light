"""claude-light: theo doi trang thai session trong luot, ngoai hook.

Hook khong du: bam Esc/Ctrl+C thi khong hook nao chay (Stop khong, idle_prompt cung khong vi phim Ctrl+C
tinh la tuong tac); duyet quyen xong cung khong co hook nao cho den khi tool chay xong. Claude Code ghi
trang thai tung tien trinh vao <config>/sessions/<pid>.json: "busy" suot luot, "waiting" khi co hop thoai
can nguoi (waitingFor cho biet ly do), "idle" ngay khi luot dung. Moi luot chay mot tien trinh nen doc
file do va doi den theo moi lan trang thai doi; ve "idle" thi tra den xanh roi thoat.
"""
import os, sys, glob, time
import light_store as store, light_serial as board

LIGHT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "light.py")
IDLE = ("idle", "shell")  # "shell": ranh nhung dang o che do `!` bash
NOT_WAIT = (None, "dialog open")  # nguoi dung tu mo /model, /config...: khong phai Claude dang cho

def alive(pid):
    # claude bi tat ngang (dong terminal) thi khong co SessionEnd, file trang thai cu van ghi "busy"
    if os.name == "nt" or not isinstance(pid, int):
        return True  # Windows: os.kill(pid, 0) la gui Ctrl+C, khong dung de kiem tra duoc
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        pass  # con song nhung khong co quyen gui tin hieu
    return True

def proc_start(pid):
    # starttime (truong 22 cua /proc/<pid>/stat, tinh tu luc boot), Claude Code ghi vao procStart. Khong co /proc: None
    try:
        with open("/proc/%d/stat" % pid) as f:
            return f.read().rsplit(")", 1)[1].split()[19]
    except (OSError, ValueError, IndexError, TypeError):
        return None

def running(rec):
    # tien trinh ghi file con song va dung la no: tat WSL ngang (may treo) thi file cu khong ai xoa, pid dem lai tu
    # dau nen trung tien trinh moi; khi do starttime khac procStart
    pid = rec.get("pid")
    if not alive(pid):
        return False
    start = proc_start(pid) if rec.get("procStart") else None
    return start is None or start == str(rec["procStart"])

def standby(rec):
    # tien trinh con chay nhung khong phai session dang dung: cua so da dua session ra chay nen (parkedJobId, phim <-:
    # cua so chi con xem danh sach agent, hoi thoai chay tiep o job nen, session khac) hoac session nen du phong daemon
    # bat san cho job sau (spare, Claude Code xoa co khi job bat dau chay)
    return bool(rec.get("parkedJobId") or rec.get("spare"))

def status_records():
    # moi lan `claude -c` la mot tien trinh moi cung sessionId: {sessionId: [(session that, updatedAt, duong dan, noi dung)]}
    out = {}
    for p in glob.glob(os.path.join(store.claude_dir(), "sessions", "*.json")):
        r = store.load(p, {})
        if isinstance(r, dict) and r.get("sessionId"):
            out.setdefault(r["sessionId"], []).append((running(r) and not standby(r), r.get("updatedAt", 0), p, r))
    return out

def on_standby(sid):
    # hook khong gan den cho session dang cho (du phong, hoac cua so da dua ra chay nen)
    return any(standby(r) and running(r) for ok, at, p, r in status_records().get(sid, []))

def status_file(sid):
    # chi lay file cua tien trinh con song, moi nhat
    live = [(at, p) for ok, at, p, r in status_records().get(sid, []) if ok]
    return max(live)[1] if live else None

def own_pids():
    # tien trinh claude dang chay hook nay nam trong chuoi cha; may khong co /proc thi chi lay cha truc tiep
    pids, pid = set(), os.getppid()
    while pid > 1 and pid not in pids:
        pids.add(pid)
        try:
            with open("/proc/%d/stat" % pid) as f:
                pid = int(f.read().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return pids

def state_of(rec):
    # trang thai den theo file trang thai phien; None la khong doi (vd nguoi dung tu mo /model)
    status = rec.get("status")
    return ("ready" if status in IDLE else "busy" if status == "busy" else
            "wait" if status == "waiting" and rec.get("waitingFor") not in NOT_WAIT else None)

def user_waiting(sid):
    # dang co hop thoai can nguoi (cau hoi, xin quyen, ke ca cua subagent): file trang thai phien ghi "waiting"
    # suot luc do. Subagent chay nen van ban PreToolUse/PostToolUse cung session_id, khong duoc de den do
    path = status_file(sid)
    return bool(path) and state_of(store.load(path, {})) == "wait"

def watch_turn(sid, since_ms):
    token = "%d.%d" % (os.getpid(), since_ms)
    with store.locked():  # luot moi thay token: tien trinh cu tu thoat. Bo token cua session da ket thuc
        m = store.load(store.MAP, {})
        w = {k: v for k, v in store.load(store.WATCH, {}).items() if k in m}
        w[sid] = token; store.save(store.WATCH, w)
    import subprocess
    detach = {"creationflags": 0x208} if os.name == "nt" else {"start_new_session": True}
    subprocess.Popen([sys.executable, LIGHT, "watch", sid, token, str(since_ms)],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **detach)

def cmd_watch(sid, token, since_ms):
    since, path, seen, end = int(since_ms), None, None, time.time() + 6 * 3600
    while time.time() < end:
        time.sleep(0.25)
        if store.load(store.WATCH, {}).get(sid) != token or sid not in store.load(store.MAP, {}):
            return  # co luot moi, hoac session da ket thuc / bo gan den
        rec = store.load(path, {}) if path else {}
        if rec.get("sessionId") != sid or not running(rec) or standby(rec):
            path = status_file(sid)
            if not path:
                return  # khong co file trang thai (Claude Code khong ghi, hoac claude da tat)
            continue
        status, at = rec.get("status"), rec.get("statusUpdatedAt", 0)
        if at <= since or at == seen:
            continue  # chua doi tu luc gui prompt (hook UserPromptSubmit da bat cam)
        seen = at
        state = state_of(rec)
        led = store.load(store.MAP, {}).get(sid, {}).get("led")
        store.log("status=%s/%s sid=%s" % (status, rec.get("waitingFor"), sid[:8]))
        if state and led is not None:
            board.send("%d:%s" % (led, state))
        if status in IDLE:
            return
