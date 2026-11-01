# CircuitPython firmware cho RP2040-Zero: den trang thai Claude Code
# Nhan lenh qua cong serial USB, moi dong dang "<den>:<trang thai>"
#   vi du: 0:busy   0:wait   0:ready   0:off   all:off   0:#ff00ff   ping
# Den "off" (chua gan session) chay hieu ung trang tri:
#   fx:none   fx:scan   fx:rainbow   fx:breathe   fx:chase   fx:comet   fx:wave   fx:heart
# Do sang cac den co session, theo phan tram: bri:5   bri:30 (den chay hieu ung giu FX_BRIGHTNESS)
import time, sys, math, board, neopixel, supervisor

# ---- CAU HINH: chan va so bong LED ----
PIN = board.GP29      # Thanh LED. LED onboard: board.GP16
NUM_LEDS = 8          # LED onboard: 1
BRIGHTNESS = 0.05     # den co session, 0..1 luc bat board, host gui bri: de doi; thap hon 0.05 thi mau bi lech
FX_BRIGHTNESS = 0.05  # den chay hieu ung, co dinh
IDLE_FX = "scan"      # hieu ung luc bat board, host gui fx: de doi
# ---------------------------------------------------------

COLORS = {
    "ready": (0, 255, 0),      # san sang, khong co luong nao chay
    "busy":  (255, 90, 0),     # dang chay (cam)
    "wait":  (255, 0, 0),      # dang co cau hoi / can xac nhan (nhap nhay)
    "off":   (0, 0, 0),
}
BLINK = {"wait"}
# hieu ung tranh do / cam / xanh la de khong lan voi den trang thai (tru rainbow)
CYAN, BLUE, VIOLET = (0, 110, 255), (0, 0, 255), (200, 0, 255)

# px.brightness de 1.0, do sang nhan tay theo tung den: den co session theo bri, den hieu ung co dinh.
# Lam tron xuong giong het thu vien neopixel lam voi px.brightness.
px = neopixel.NeoPixel(PIN, NUM_LEDS, brightness=1.0, auto_write=False)
bri = BRIGHTNESS
states = ["off"] * NUM_LEDS
since = [0.0] * NUM_LEDS  # luc moi den nhan trang thai: den vua chuyen sang wait sang ngay
fx = IDLE_FX
buf = ""

def color_of(state):
    if state.startswith("#") and len(state) == 7:
        try:
            return (int(state[1:3], 16), int(state[3:5], 16), int(state[5:7], 16))
        except ValueError:
            return (0, 0, 0)
    return COLORS.get(state, (0, 0, 0))

def dim(c, k):
    return (int(c[0] * k), int(c[1] * k), int(c[2] * k))

def wheel(h):
    # h 0..1 -> mau cau vong bao hoa day du
    h = h % 1 * 6
    i, f = min(int(h), 5), h % 1  # float 30 bit: h % 1 sat 1 nhan 6 co the lam tron thanh 6.0
    up, down = int(255 * f), int(255 * (1 - f))
    return ((255, up, 0), (down, 255, 0), (0, 255, up),
            (0, down, 255), (up, 0, 255), (255, 0, down))[i]

# Moi hieu ung nhan t (giay) va idle (chi so cac den "off"), tra mau cho tung den trong idle.
# Chu ky deu chia het 3600 s de khop voi clock().
def scan(t, idle):
    # mot cham chay qua lai tren day den trong, di ve het 3 s, lo ra ngoai hai dau mot chut
    n = len(idle)
    x = -1 + abs(t / 3 % 1 * 2 - 1) * (n + 1)
    return [dim(CYAN, max(0, 1 - abs(j - x) / 1.5)) for j in range(n)]

def rainbow(t, idle):
    # cau vong xoay mot vong het 3 s, cac den lech mau theo vi tri tren thanh
    return [wheel(t / 3 + i / NUM_LEDS) for i in idle]

def breathe(t, idle):
    # sang len toi di moi 4 s, mau troi dan giua xanh duong va tim moi 12 s
    k = (1 - math.cos(2 * math.pi * t / 4)) / 2
    m = (1 - math.cos(2 * math.pi * t / 12)) / 2
    return [dim((int(150 * m), 0, 255), k)] * len(idle)

def chase(t, idle):
    # den Noel: cu 3 bong sang 1, dich mot bong moi 0.2 s, nhom xen ke xanh duong / tim
    s = int(t / 0.2)  # 18000 buoc moi gio, chia het 6 nen qua moc 3600 s khong nhay
    return [(BLUE, VIOLET)[(j - s) // 3 % 2] if (j - s) % 3 == 0 else (0, 0, 0)
            for j in range(len(idle))]

def comet(t, idle):
    # sao bang chay mot chieu 1.5 s, keo duoi 3 bong, nghi 0.9 s roi chay lai
    n, p = len(idle), t % 2.4 / 1.5
    if p > 1:
        return [(0, 0, 0)] * n
    x = -1 + p * (n + 4)  # dau sao bang di tu -1 den n + 3 de duoi ra het khoi thanh
    return [dim(CYAN, max(0, 1 - (x - j) / 3) if x >= j else max(0, 1 - (j - x) * 2))
            for j in range(n)]

def wave(t, idle):
    # mau troi trong dai xanh lo - xanh duong - tim (wheel 0.5..0.8), song chay doc thanh het 4 s
    return [wheel(0.65 - 0.15 * math.cos(2 * math.pi * (t / 4 - i / NUM_LEDS))) for i in idle]

def beat(d):
    return math.sin(math.pi * d / 0.2) if 0 <= d < 0.2 else 0

def heart(t, idle):
    # nhip tim: hai nhip "thich thich" tim hong (nhip sau nhe hon) roi nghi, 1.5 s mot chu ky
    p = t % 1.5
    return [dim(VIOLET, max(beat(p), 0.6 * beat(p - 0.3)))] * len(idle)

# thu tu phai khop FX trong scripts/light_display.py: host danh so 0, 1, 2, ... theo thu tu do
FX = {"none": lambda t, idle: [(0, 0, 0)] * len(idle),
      "scan": scan, "rainbow": rainbow, "breathe": breathe, "chase": chase, "comet": comet, "wave": wave, "heart": heart}

def clock():
    # giay trong gio hien tai: time.monotonic() la float 30 bit, chay vai ngay la giat;
    # monotonic_ns() la so nguyen nen giu duoc do chinh xac
    return time.monotonic_ns() // 1000000 % 3600000 / 1000

def render(t):
    idle = [i for i, s in enumerate(states) if s == "off"]
    for i, s in enumerate(states):
        c = color_of(s)
        if s in BLINK and int((t - since[i]) * 2) % 2:  # nhap nhay: sang 0.5 s, toi 0.5 s
            c = dim(c, 0.1)
        px[i] = dim(c, bri)
    for i, c in zip(idle, FX[fx](t, idle)):
        px[i] = dim(c, FX_BRIGHTNESS)
    px.show()

def handle(line):
    global fx, bri
    line = line.strip().lower()
    if not line:
        return
    if line == "ping":
        print("pong"); return
    if ":" not in line:
        print("err"); return
    idx, state = line.split(":", 1)
    if idx == "fx":
        if state not in FX:
            print("err"); return
        fx = state
    elif idx == "bri":
        try:
            bri = min(100, max(0, int(state))) / 100
        except ValueError:
            print("err"); return
    else:
        if idx == "all":
            targets = range(NUM_LEDS)
        else:
            try:
                targets = [int(idx)]
            except ValueError:
                print("err"); return
        for t in targets:
            if 0 <= t < NUM_LEDS:
                states[t], since[t] = state, clock()
    print("ok")

# Chao: nhay nhanh 3 mau roi vao hieu ung
for c in ((40, 0, 0), (0, 40, 0), (0, 0, 40), (0, 0, 0)):
    px.fill(dim(c, BRIGHTNESS)); px.show(); time.sleep(0.15)

while True:
    while supervisor.runtime.serial_bytes_available:
        ch = sys.stdin.read(1)
        if ch in ("\n", "\r"):
            try:  # loi thoat khoi vong lap la board dung hinh den khi cam lai
                handle(buf)
            except Exception:
                print("err")
            buf = ""
        else:
            buf += ch
    try:
        render(clock())
    except Exception as e:  # hieu ung loi thi tat no di, den trang thai van chay
        print("fx loi:", e); fx = "none"
    time.sleep(0.02)
