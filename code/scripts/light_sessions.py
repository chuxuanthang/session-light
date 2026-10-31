"""claude-light: gan session Claude Code voi den (map, pending, muted) va doc ten session."""
import os, json, glob
import light_store as store

def led_for(session_id, cwd):
    c = store.cfg()
    m = store.load(store.MAP, {})
    if session_id in m:
        if m[session_id]["cwd"] != cwd:  # session da cd: giu cwd moi de slash command tim thay
            m[session_id]["cwd"] = cwd
            store.save(store.MAP, m)
        return m[session_id]["led"]
    used = {v["led"] for v in m.values()}
    pend = store.load(store.PENDING, {})
    led = pend.pop(cwd, None)
    if led is not None:
        store.save(store.PENDING, pend)  # pending chi dung mot lan, ke ca khi den da bi chiem
    if led in used:  # hook khong gianh den cua session khac; chi /usb-connect moi day duoc
        led = None
    mu = store.load(store.MUTED, [])
    if led is None and c.get("auto_assign") and cwd not in mu and session_id not in mu:
        for n in range(int(c["num_leds"])):
            if n not in used:
                led = n
                break
    if led is None:
        return None
    m[session_id] = {"led": led, "cwd": cwd}
    store.save(store.MAP, m)
    return led

def end_session(session_id, cwd, reason):
    mu = store.load(store.MUTED, [])
    if session_id in mu:
        mu.remove(session_id); store.save(store.MUTED, mu)
    m = store.load(store.MAP, {})
    if session_id not in m:  # chua gan den hoac da bi day ra: khong tat den cua session khac
        return None
    led = m.pop(session_id)["led"]
    store.save(store.MAP, m)
    if reason == "clear":  # /clear tao session_id moi: de session moi nhan lai dung den nay
        pend = store.load(store.PENDING, {}); pend[cwd] = led; store.save(store.PENDING, pend)
    return led

def session_title(sid):
    # ten tren tab terminal: Claude Code ghi vao transcript; ten dat bang /rename uu tien hon ten tu dat
    found = {}
    for path in glob.glob(os.path.join(store.claude_dir(), "projects", "*", glob.escape(sid) + ".jsonl")):
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
