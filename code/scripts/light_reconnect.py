"""claude-light: tien trinh nen tu gan lai board va gui lai mau ca thanh khi board cam lai.

Hook chi chay khi session co su kien: rut USB cam lai (hay ket noi usbip tu dut) luc moi session dang ranh thi
khong ai biet, den toi den khi co prompt moi. SessionStart bat `light.py keep`, moi luc chi mot tien trinh (giu
flock tren keeper.lock): moi giay goi wsl_attach, mat cong thi tren WSL goi usbipd attach moi 5 s, cong co lai
thi gui lai ca thanh. Thoat khi khong con session nao trong map.json con song.
"""
import os, sys, time
import light_store as store, light_serial as board, light_watch as watch, light_display as display

LIGHT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "light.py")

def spawn():
    # tien trinh thua tu thoat ngay vi khong lay duoc khoa. Windows khong co fcntl: chi dua vao hook
    if os.name == "nt":
        return
    import subprocess
    subprocess.Popen([sys.executable, LIGHT, "keep"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)

def any_alive():
    # Claude Code khong ghi file trang thai nao thi khong biet duoc: con session trong map la coi nhu con song
    m, files = store.load(store.MAP, {}), watch.status_records()
    return bool(m) and (not files or any(ok for sid in m for ok, at, p, r in files.get(sid, [])))

def cmd_keep(poll=1, attach_every=5, check_every=60):
    import fcntl
    os.makedirs(store.DIR, exist_ok=True)
    f = open(store.KEEPER, "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return  # da co tien trinh keep khac
    checked = None
    while True:
        try:
            now = time.time()
            if checked is None or not 0 <= now - checked < check_every:  # dong ho WSL hay bi chinh lui
                checked = now
                if not any_alive():
                    # nha khoa roi xem lai: session vua mo luc nay da bat keep moi va bi tu choi thi chay tiep
                    fcntl.flock(f, fcntl.LOCK_UN)
                    if not any_alive():
                        return
                    try:
                        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except OSError:
                        return  # keep moi da giu khoa
            if board.wsl_attach(attach_every):
                with store.locked():
                    lines = display.sync_lines()
                board.send("\n".join(lines))
        except Exception as e:
            store.log("keep loi: %r" % e)
        time.sleep(poll)
