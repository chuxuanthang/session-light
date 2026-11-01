"""claude-light: duong dan, doc/ghi JSON, khoa file, cau hinh va log."""
import os, json, time, contextlib

HOME = os.path.expanduser("~")
DIR = os.path.join(HOME, ".claude-light")
CONFIG = os.path.join(DIR, "config.json")
MAP = os.path.join(DIR, "map.json")          # {session_id: {"led": n, "cwd": "..."}}
PENDING = os.path.join(DIR, "pending.json")  # {cwd: led}
MUTED = os.path.join(DIR, "muted.json")      # [cwd hoac session_id] da disconnect: khong tu gan lai
LOG = os.path.join(DIR, "log.txt")
LOCK = os.path.join(DIR, "lock")
WATCH = os.path.join(DIR, "watch.json")      # {session_id: token cua tien trinh theo doi luot hien tai}

def claude_dir():
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude")

def load(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save(path, data):
    os.makedirs(DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

@contextlib.contextmanager
def locked():
    # nhieu session ban hook cung luc: khoa de khong ghi de map.json cua nhau
    os.makedirs(DIR, exist_ok=True)
    with open(LOCK, "w") as f:
        try:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
        except ImportError:  # Windows khong co fcntl: chay khong khoa
            pass
        yield

def cfg():
    c = {"port": None, "num_leds": 8, "auto_assign": True, "debug": False,
         "brightness": 5, "idle_fx": "scan"}
    c.update(load(CONFIG, {}))
    if not os.path.exists(CONFIG):
        save(CONFIG, c)
    return c

def log(msg):
    if cfg().get("debug"):
        os.makedirs(DIR, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + msg + "\n")
