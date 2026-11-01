"""claude-light: do sang cac den co session va hieu ung cua cac den chua gan session."""
import light_store as store, light_serial as board

FX = {"scan": "sóng quét qua lại", "rainbow": "cầu vồng xoay", "breathe": "thở màu", "none": "tắt"}
NOT_SENT = ". Chưa gửi được xuống board, lần mở session sau sẽ gửi"

def settings_line():
    c = store.cfg()
    return "bri:%s\nfx:%s" % (c["brightness"], c["idle_fx"])

def save_and_send(key, value, line):
    c = store.cfg(); c[key] = value; store.save(store.CONFIG, c)
    board.wsl_attach()
    return board.send(line)

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
    if name not in FX:
        if name:
            print("Không có hiệu ứng %s." % name)
        print("Hiệu ứng đèn trống: %s. Chọn một trong:" % store.cfg()["idle_fx"])
        for k, v in FX.items():
            print("  %-8s %s" % (k, v))
        return
    ok = save_and_send("idle_fx", name, "fx:%s" % name)
    print("Đã đổi hiệu ứng đèn trống sang %s (%s)" % (name, FX[name]) + ("" if ok else NOT_SENT))
