"""Chay firmware/code.py tren CPython voi board/neopixel/supervisor gia: hieu ung, lenh, nhap nhay.

Chay: python3 tests/firmware-effects.py   (exit 1 neu co ca FAIL)
"""
import contextlib, io, os, sys, types

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "code", "firmware", "code.py")

class FakePixels(list):
    def __init__(self, pin, n, brightness, auto_write):
        super().__init__([(0, 0, 0)] * n); self.brightness = brightness
    def fill(self, c): self[:] = [c] * len(self)
    def show(self): pass

for name, attrs in (("board", {"GP29": 29, "GP16": 16}), ("neopixel", {"NeoPixel": FakePixels}),
                    ("supervisor", {})):
    mod = types.ModuleType(name); mod.__dict__.update(attrs); sys.modules[name] = mod
F = {}
exec(open(SRC, encoding="utf-8").read().split("# Chao")[0], F)  # bo phan chao va vong lap vo han

results = []
def check(name, ok, detail):
    results.append(ok)
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "\n     " + detail))

def say(*lines):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        for line in lines:
            F["handle"](line)
    return out.getvalue().split()

# Moi hieu ung chay 16 s di qua moc quay vong 3600 s: mau phai la so nguyen 0..255, khong nem loi
F["states"][:] = ["ready", "busy", "off", "off", "wait", "off", "off", "off"]
bad = []
for fx in F["FX"]:
    F["fx"] = fx
    for k in range(160):
        try:
            F["render"]((3592 + k * 0.1) % 3600)
        except Exception as e:
            bad.append((fx, k, repr(e))); break
        bad += [(fx, k, c) for c in F["px"] if not all(isinstance(v, int) and 0 <= v <= 255 for v in c)]
check("hieu ung qua moc 3600 s, mau trong 0..255", not bad, "loi: %s" % bad[:3])

got = say("fx:breathe", "fx:firefly", "bri:30", "bri:abc", "ping")
check("lenh fx / bri / ping, mac dinh scan, khong con firefly",
      F["IDLE_FX"] == "scan" and got == ["ok", "err", "ok", "err", "pong"] and F["fx"] == "breathe",
      "IDLE_FX=%s, tra %s, fx=%s" % (F["IDLE_FX"], got, F["fx"]))

# bri: chi doi den co session; den chay hieu ung giu 5% (255 * 0.05 -> toi da 12)
F["fx"] = "rainbow"; F["render"](5.0)
session, deco = F["px"][0], [F["px"][i] for i in (2, 3, 5, 6, 7)]
check("bri:30 chi doi den co session, den hieu ung giu 5%",
      session == (0, 76, 0) and max(max(c) for c in deco) == 12,
      "den 0 (ready) %s, den hieu ung %s" % (session, deco))

# Den vua chuyen sang wait phai sang ngay, du dung luc pha nhap nhay chung dang toi
F["bri"] = 1.0; F["clock"] = lambda: 10.7
say("4:wait")
F["render"](10.7); first = F["px"][4]
F["render"](11.3); later = F["px"][4]
check("wait sang ngay luc vua nhan, 0.5 s sau thi toi", first == (255, 0, 0) and later == (25, 0, 0),
      "luc nhan %s, 0.6 s sau %s" % (first, later))

print("\n%d/%d pass" % (sum(results), len(results)))
sys.exit(0 if all(results) else 1)
