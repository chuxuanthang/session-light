"""claude-light: tim cong serial cua board, gan board vao WSL, gui lenh xuong board."""
import os, time
import light_store as store

# WSL2 khong thay COM port: nho usbipd-win gan board vao (can bind 1 lan bang PowerShell Admin)
USBIPD = "/mnt/c/Program Files/usbipd-win/usbipd.exe"
BOARD_HWID = "2e8a:101f"

def find_port():
    c = store.cfg()
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

def wsl_attach(min_interval=0):
    # Rut cam USB hay mat ket noi usbip giua chung thi cong mat: ghi lai "lost", tren WSL (co usbipd.exe) thi
    # goi usbipd attach; min_interval de board rut han khong ton moi hook ~0.2 s. Tra True khi cong vua co lai
    # sau khi mat, du plugin, usbipd hay nguoi dung gan: board co the da khoi dong lai, quen het mau.
    # Khong goi khi dang giu store.locked()
    with store.locked():
        st = store.load(store.ATTACH, {})
        st = st if isinstance(st, dict) else {}
        if find_port():
            if st.get("lost"):
                store.save(store.ATTACH, dict(st, lost=False))
            return bool(st.get("lost"))
        now = time.time()
        if not os.path.exists(USBIPD) or min_interval and 0 <= now - st.get("tried", 0) < min_interval:
            if not st.get("lost"):
                store.save(store.ATTACH, dict(st, lost=True))
            return False
        store.save(store.ATTACH, dict(st, lost=True, tried=now))
    import subprocess
    try:
        r = subprocess.run([USBIPD, "attach", "--wsl", "--hardware-id", BOARD_HWID],
                           cwd="/mnt/c", capture_output=True, text=True, timeout=15)
    except Exception as e:
        store.log("usbipd attach loi: %r" % e); return False
    store.log("usbipd attach exit=%d %s" % (r.returncode, r.stderr.strip()[-200:]))
    if r.returncode != 0:
        return False
    # cho /dev/ttyACM* hien ra VA mo duoc, toi da ~3s: node moi tao la root 0600,
    # udev doi sang group dialout sau ~0.2s; gui som qua thi send() het luot thu lai
    for _ in range(30):
        port = find_port()
        if port and os.access(port, os.R_OK | os.W_OK):
            with store.locked():
                store.save(store.ATTACH, dict(store.load(store.ATTACH, {}), lost=False))
            return True
        time.sleep(0.1)
    return False  # udev cham: van con "lost", hook sau thay cong se bao True

def send(line, retries=4):
    try:
        import serial
    except ImportError:
        store.log("pyserial chua cai: pip install pyserial")
        return False
    port = find_port()
    if not port:
        store.log("khong tim thay cong serial cua board")
        return False
    for i in range(retries):
        try:
            with serial.Serial(port, 115200, timeout=0.3, write_timeout=0.5) as s:
                # "\n" dau dong cat rac con trong buf cua board thanh dong rieng (board tra "err"
                # cho dong rac, dong rong thi bo qua). Rac co that: lan mo dau sau khi attach,
                # tty con ECHO nen doi lai status bar CircuitPython xuong board.
                s.write(("\n" + line + "\n").encode())
                s.flush()
                store.log("-> " + line)
                return True
        except Exception as e:
            store.log("port busy/loi (%d): %s" % (i, e))
            time.sleep(0.08)
    return False
