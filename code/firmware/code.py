# CircuitPython firmware cho RP2040-Zero: den trang thai Claude Code
# Nhan lenh qua cong serial USB, moi dong dang "<den>:<trang thai>"
#   vi du: 0:busy   0:wait   0:ready   0:off   all:off   0:#ff00ff   ping
import time, sys, board, neopixel, supervisor

# ---- CAU HINH: chan va so bong LED ----
PIN = board.GP29      # Thanh LED. LED onboard: board.GP16
NUM_LEDS = 8          # LED onboard: 1
BRIGHTNESS = 0.25
# ---------------------------------------------------------

COLORS = {
    "ready": (0, 255, 0),      # san sang, khong co luong nao chay
    "busy":  (255, 90, 0),     # dang chay (cam)
    "wait":  (255, 0, 0),      # dang co cau hoi / can xac nhan (nhap nhay)
    "off":   (0, 0, 0),
}
BLINK = {"wait"}

px = neopixel.NeoPixel(PIN, NUM_LEDS, brightness=BRIGHTNESS, auto_write=False)
states = ["off"] * NUM_LEDS
buf = ""

def color_of(state):
    if state.startswith("#") and len(state) == 7:
        try:
            return (int(state[1:3], 16), int(state[3:5], 16), int(state[5:7], 16))
        except ValueError:
            return (0, 0, 0)
    return COLORS.get(state, (0, 0, 0))

def render(phase):
    for i, s in enumerate(states):
        c = color_of(s)
        if s in BLINK and not phase:
            c = (c[0] // 10, c[1] // 10, c[2] // 10)
        px[i] = c
    px.show()

def handle(line):
    line = line.strip().lower()
    if not line:
        return
    if line == "ping":
        print("pong"); return
    if ":" not in line:
        print("err"); return
    idx, state = line.split(":", 1)
    if idx == "all":
        targets = range(NUM_LEDS)
    else:
        try:
            targets = [int(idx)]
        except ValueError:
            print("err"); return
    for t in targets:
        if 0 <= t < NUM_LEDS:
            states[t] = state
    render(True)
    print("ok")

# Chao: nhay nhanh 3 mau roi tat
for c in ((40, 0, 0), (0, 40, 0), (0, 0, 40), (0, 0, 0)):
    px.fill(c); px.show(); time.sleep(0.15)

last = time.monotonic()
phase = True
while True:
    while supervisor.runtime.serial_bytes_available:
        ch = sys.stdin.read(1)
        if ch in ("\n", "\r"):
            handle(buf); buf = ""
        else:
            buf += ch
    now = time.monotonic()
    if now - last >= 0.5:
        phase = not phase
        last = now
        render(phase)
    time.sleep(0.02)
