"""claude-light: gan session Claude Code voi den (map, pending, muted) va doc ten session."""
import os, json, glob
import light_store as store, light_watch as watch

def led_for(session_id, cwd):
    c = store.cfg()
    m = store.load(store.MAP, {})
    if session_id in m:
        if m[session_id]["cwd"] != cwd:  # session da cd: giu cwd moi de slash command tim thay
            m[session_id]["cwd"] = cwd
            store.save(store.MAP, m)
        return m[session_id]["led"]
    if watch.on_standby(session_id):  # session nen du phong / cua so da dua ra chay nen: chua phai session dang dung
        return None
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

def release(session_id):
    # claude -c / --resume: lay den trong nho nhat (1 -> 8) nhu session moi, khong giu den cu ke ca den gan tay.
    # auto_assign tat thi giu (khong tu gan lai duoc); tien trinh khac cua session nay con song (`claude -c` o
    # terminal thu hai) thi giu: no dang dung den do
    m = store.load(store.MAP, {})
    if session_id not in m or not store.cfg().get("auto_assign"):
        return
    mine = watch.own_pids()
    if any(ok and r.get("pid") not in mine for ok, at, p, r in watch.status_records().get(session_id, [])):
        return
    del m[session_id]
    store.save(store.MAP, m)

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

# Sap lai den (/usb-sort, /usb-swap), goi trong store.locked(). Den trong pending (gan tay luc chua co session, hoac
# /clear dang cho session moi) cung tinh la dang giu va doi so theo, de session mo sau khong de len den cua session khac

def held_leds():
    return {v["led"] for v in store.load(store.MAP, {}).values()} | set(store.load(store.PENDING, {}).values())

def renumber(new):
    # new: {den cu: den moi}, den khong co trong new giu nguyen
    m, pend = store.load(store.MAP, {}), store.load(store.PENDING, {})
    for v in m.values():
        v["led"] = new.get(v["led"], v["led"])
    store.save(store.MAP, m)
    store.save(store.PENDING, {k: new.get(v, v) for k, v in pend.items()})

def compact():
    # don den dang giu ve sat ben trai, giu thu tu: 1 3 5 6 8 -> 1 2 3 4 5. Tra [(den cu, den moi)] den bi doi
    new = {old: n for n, old in enumerate(sorted(held_leds()))}
    renumber(new)
    return [(old, n) for old, n in sorted(new.items()) if old != n]

def swap(a, b):
    # doi den a va b cho nhau (mot ben trong thi la chuyen sang). Tra cac den trong hai den dang duoc giu
    held = held_leds() & {a, b}
    renumber({a: b, b: a})
    return held

def unassign(leds=None):
    # /usb-disconnect <so>: bo gan den trong leds (None la tat ca), ke ca den pending. Session bi bo gan vao muted de
    # hook khong tu gan lai (den usb-connect hoac SessionEnd). Goi trong store.locked(). Tra {den: [(sid, cwd)]}
    m, pend, mu = store.load(store.MAP, {}), store.load(store.PENDING, {}), store.load(store.MUTED, [])
    out = {}
    for k in [k for k, v in m.items() if leds is None or v["led"] in leds]:
        v = m.pop(k)
        out.setdefault(v["led"], []).append((k, v["cwd"]))
        if k not in mu:
            mu.append(k)
    for c in [c for c, n in pend.items() if leds is None or n in leds]:
        out.setdefault(pend.pop(c), [])
    store.save(store.MAP, m); store.save(store.PENDING, pend); store.save(store.MUTED, mu)
    return out

def label(sid, cwd):
    # ten session kem thu muc nhu /usb-status; chua co ten thi chi thu muc
    title = session_title(sid)
    return "%s (%s)" % (title, cwd) if title else cwd

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
