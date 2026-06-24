"""
File-based JSON database — no external DB needed.
Stores: user IDs, user count, settings.
"""
import json, os, time
from threading import Lock

DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
_lock = Lock()

def _ensure():
    os.makedirs(DATA_DIR, exist_ok=True)

def _load(path, default):
    _ensure()
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def _save(path, data):
    _ensure()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

# ── Users ────────────────────────────────────────────
def load_users():
    return _load(USERS_FILE, {})

def save_users(u):
    with _lock:
        _save(USERS_FILE, u)

def get_user(user_id):
    uid = str(user_id)
    users = load_users()
    if uid not in users:
        users[uid] = {
            "id": user_id,
            "joined": int(time.time()),
            "banned": False,
            "vip": False,
            "vip_expiry": 0,
            "last_used": 0,
            "daily_count": 0,
            "daily_reset": 0,
        }
        save_users(users)
    return users[uid]

def update_user(user_id, data):
    with _lock:
        users = load_users()
        uid = str(user_id)
        if uid not in users:
            get_user(user_id)
            users = load_users()
        users[uid].update(data)
        _save(USERS_FILE, users)

def all_user_ids():
    return [int(k) for k in load_users()]

def user_count():
    return len(load_users())

# ── Settings ─────────────────────────────────────────
DEFAULTS = {
    "admins": [],                # [{"id": int, "expiry": int}]
    "force_join_channels": [],   # [{"id": int, "title": str, "invite_link": str}]
    "cooldown_seconds": 30,
    "daily_limit": 20,
    "maintenance": False,
    "custom_bypasses": {},       # domain -> "generic"
}

def load_settings():
    s = _load(SETTINGS_FILE, {})
    for k, v in DEFAULTS.items():
        if k not in s:
            s[k] = v
    return s

def save_settings(s):
    with _lock:
        _save(SETTINGS_FILE, s)

def get_setting(key):
    return load_settings().get(key, DEFAULTS.get(key))

def set_setting(key, value):
    with _lock:
        s = load_settings()
        s[key] = value
        _save(SETTINGS_FILE, s)
