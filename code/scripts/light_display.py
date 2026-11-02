"""claude-light: do sang cac den co session, hieu ung cua cac den chua gan session, nhay den de tim,
gui lai ca thanh den khi board vua cam lai."""
import os
import light_store as store, light_serial as board, light_sessions as sessions, light_watch as watch

# thu tu = so go trong /usb-fx (0 la tat, 1, 2, ...); ten phai co trong FX cua firmware/code.py
FX = {"none": "tắt", "scan": "sóng quét qua lại", "rainbow": "cầu vồng xoay", "breathe": "thở màu",
      "chase": "đèn Noel chạy", "comet": "sao băng", "wave": "sóng màu lạnh", "heart": "nhịp tim"}
NOT_SENT = ". Chưa gửi được xuống board, lần mở session sau sẽ gửi"

def settings_line():
    c = store.cfg()
    return "bri:%s\nfx:%s" % (c["brightness"], c["idle_fx"])

def sync_lines(skip=None):
    """Goi trong store.locked(). Rut cam USB / nap firmware la board quen het mau va do sang, den cua session
    dang ranh toi nhu den trong du van bi giu. Tra lenh dat lai do sang, hieu ung va mau tung den theo file
    trang thai phien; session chi con file cua tien trinh da chet (claude bi tat ngang) thi bo gan, tra den.
    skip: session dang chay hook, tu gui trang thai cua minh sau cac dong nay."""
    m, files = store.load(store.MAP, {}), watch.status_records()
    shown = {}
    for sid, v in list(m.items()):
        if sid == skip:
            continue
        recs = files.get(sid, [])
        live = [(at, r) for ok, at, p, r in recs if ok]
        if live:
            shown[v["led"]] = watch.state_of(max(live, key=lambda x: x[0])[1]) or "ready"
        elif recs:
            del m[sid]
        else:  # chua co file (vua mo session) hoac Claude Code khong ghi file trang thai; trang thai la cung ready
            shown[v["led"]] = "ready"
    store.save(store.MAP, m)
    own = m.get(skip, {}).get("led")
    return [settings_line()] + ["%d:%s" % (n, shown.get(n, "off"))
                                for n in range(int(store.cfg()["num_leds"])) if n != own]

def attach_lines(sid=None):
    # lenh slash: gan board vao WSL neu chua thay cong; vua gan thi gui lai ca thanh truoc lenh cua minh
    if not board.wsl_attach():
        return []
    with store.locked():
        return sync_lines(sid)

def save_and_send(key, value, line):
    c = store.cfg(); c[key] = value; store.save(store.CONFIG, c)
    return board.send("\n".join(attach_lines(os.environ.get("CLAUDE_CODE_SESSION_ID")) + [line]))

def cmd_brightness(n=None):
    if n is None:
        print("Độ sáng đèn có session: %s%%" % store.cfg()["brightness"]); return
    try:
        n = int(str(n).strip().rstrip("%"))
    except ValueError:
        n = -1
    if not 0 <= n <= 100:
        print("Độ sáng phải là số từ 0 đến 100"); return
    ok = save_and_send("brightness", n, "bri:%d" % n)
    msg = "Đã đặt độ sáng đèn có session %d%%" % n
    if n == 0:
        msg += ", các đèn này tắt hẳn"
    elif n < 5:
        msg += ". Dưới 5% màu bị lệch, cam dễ lẫn với đỏ"
    print(msg + ("" if ok else NOT_SENT))

def cmd_fx(name=None):
    name = (name or "").strip().lower()
    names = list(FX)
    if name.isdigit() and int(name) < len(names):  # go so theo thu tu danh sach cho nhanh
        name = names[int(name)]
    if name not in FX:
        if name:
            print("Không có hiệu ứng %s." % name)
        print("Hiệu ứng đèn trống: %s. Chọn số hoặc tên:" % store.cfg()["idle_fx"])
        for n, (k, v) in enumerate(FX.items()):
            print("  %d  %-8s %s" % (n, k, v))
        return
    ok = save_and_send("idle_fx", name, "fx:%s" % name)
    print("Đã đổi hiệu ứng đèn trống sang %s (%s)" % (name, FX[name]) + ("" if ok else NOT_SENT))

def cmd_blink():
    # nhay xanh la 3 lan den cua session nay (board tu nhay roi tra ve mau trang thai), in so den dem tu 1
    cwd = os.getcwd()
    pre = attach_lines(os.environ.get("CLAUDE_CODE_SESSION_ID"))  # truoc khi doc map: co the vua tra den session chet
    m = store.load(store.MAP, {})
    leds = sorted({m[k]["led"] for k in sessions.my_sessions(m, cwd) if k in m})
    if not leds:
        print("Session ở %s chưa gắn đèn nào" % cwd); return
    nums = ", ".join(str(n + 1) for n in leds)
    if board.send("\n".join(pre + ["flash:%d" % n for n in leds])):
        print("Đèn %s đang nháy xanh lá 3 lần" % nums)
    else:
        print("Session này gắn đèn %s nhưng không gửi được xuống board" % nums)
