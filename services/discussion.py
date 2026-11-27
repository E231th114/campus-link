"""Deadline policy and the allowed reaction vocabulary."""
from services.emoji import RECOMMENDED, allowed_code

import math
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
PRESETS = {"1h": 3600, "24h": 86400, "3d": 259200, "1w": 604800}


def parse_deadline(mode, custom, now):
    if mode == "none":
        return 0
    if mode in PRESETS:
        return now + PRESETS[mode]
    if mode != "custom":
        raise ValueError("unknown deadline")
    date = datetime.strptime(custom, "%Y-%m-%dT%H:%M").replace(tzinfo=JST)
    epoch = int(date.timestamp())
    if epoch <= now:
        raise ValueError("deadline has passed")
    return epoch


def availability(post, now):
    end = post.get("deadline", 0)
    left = end - now
    if post["solved"]:
        status = "解決済み"
    elif post.get("paused"):
        status = "受付停止"
    elif end and left <= 0:
        status = "回答受付終了"
    elif end and left <= 3600:
        status = "期限間近"
    else:
        status = "回答受付中"
    post.update(status=status, accepting=status in ("回答受付中", "期限間近"))
    if end:
        post["end_jst"] = datetime.fromtimestamp(end, JST).strftime("%Y/%m/%d %H:%M:%S")
        for unit, label in ((86400, "日"), (3600, "時間"), (60, "分")):
            if left >= unit or unit == 60:
                post["remaining"] = "残り" + str(math.ceil(left / unit)) + label if left > 0 else ""
                break


def reaction_state(store, key, viewer):
    # Immutable revisions make a repeated or late request for the same revision harmless.
    latest = {}
    for row in store.rows("emoji-" + key):
        code = allowed_code(row["emoji"], key)
        if not code:
            continue
        pair = (row["owner"], code)
        if pair not in latest or row["revision"] > latest[pair]["revision"]:
            latest[pair] = row
    state = {code: {"count": 0, "mine": False, "revision": 0} for code in RECOMMENDED if allowed_code(code, key)}
    for (owner, code), row in latest.items():
        if row["active"] or owner == viewer:
            state.setdefault(code, {"count": 0, "mine": False, "revision": 0})
            state[code]["count"] += int(row["active"])
            if owner == viewer:
                state[code].update(mine=row["active"], revision=row["revision"])
    return state
