import time
from database import get_user, update_user, get_setting

DAY = 86400

def is_owner(user_id, owner_id):
    return int(user_id) == int(owner_id) if owner_id else False

def is_admin(user_id, owner_id):
    if is_owner(user_id, owner_id):
        return True
    now = int(time.time())
    for a in get_setting("admins"):
        if a["id"] == int(user_id):
            if a.get("expiry", 0) == 0 or a["expiry"] > now:
                return True
    return False

def is_vip(user_id):
    u = get_user(user_id)
    if not u.get("vip"):
        return False
    exp = u.get("vip_expiry", 0)
    if exp == 0 or exp > int(time.time()):
        return True
    update_user(user_id, {"vip": False, "vip_expiry": 0})
    return False

def is_banned(user_id):
    return get_user(user_id).get("banned", False)

def cooldown_left(user_id):
    cd = get_setting("cooldown_seconds") or 0
    if cd <= 0:
        return 0
    last = get_user(user_id).get("last_used", 0)
    return max(0, cd - (int(time.time()) - last))

def daily_status(user_id):
    """Returns (hit_limit: bool, count: int, limit: int)"""
    limit = get_setting("daily_limit") or 0
    if limit <= 0:
        return False, 0, 0
    u = get_user(user_id)
    now = int(time.time())
    count = u.get("daily_count", 0)
    reset = u.get("daily_reset", 0)
    if now - reset >= DAY:
        count = 0
        update_user(user_id, {"daily_count": 0, "daily_reset": now})
    return count >= limit, count, limit

def record_usage(user_id):
    u = get_user(user_id)
    now = int(time.time())
    count = u.get("daily_count", 0)
    reset = u.get("daily_reset", 0)
    if now - reset >= DAY:
        count = 0
        reset = now
    update_user(user_id, {"last_used": now, "daily_count": count + 1, "daily_reset": reset})
